"""
알림 전송 모듈.

지원 채널
- console  : 항상 동작 (터미널 출력)
- discord  : Discord 웹훅 URL (봇 생성 불필요)
- telegram : 텔레그램 봇 토큰 + chat_id
"""

import logging
from typing import Any, Dict, List

import requests

log = logging.getLogger("cgv-open-push")

DISCORD_LIMIT = 1900  # 디스코드 메시지 최대 2000자


def _chunks(text: str, limit: int) -> List[str]:
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit and current:
            parts.append(current)
            current = ""
        current += line
    if current:
        parts.append(current)
    return parts


class Notifier:
    def __init__(self, config: Dict[str, Any]):
        self.discord_webhook = (config.get("discord_webhook_url") or "").strip()
        self.telegram_token = (config.get("telegram_bot_token") or "").strip()
        self.telegram_chat_id = str(config.get("telegram_chat_id") or "").strip()
        self.timeout = 15

    @property
    def targets(self) -> List[str]:
        result = ["console"]
        if self.discord_webhook:
            result.append("discord")
        if self.telegram_token and self.telegram_chat_id:
            result.append("telegram")
        return result

    def send(self, title: str, body: str) -> None:
        text = f"**{title}**\n{body}" if body else f"**{title}**"
        print(text, flush=True)
        if self.discord_webhook:
            self._send_discord(text)
        if self.telegram_token and self.telegram_chat_id:
            self._send_telegram(f"{title}\n{body}")

    # ------------------------------------------------------------------ discord
    def _send_discord(self, text: str) -> None:
        for part in _chunks(text, DISCORD_LIMIT):
            try:
                r = requests.post(
                    self.discord_webhook,
                    json={"content": part, "username": "CGV 예매 오픈 알리미"},
                    timeout=self.timeout,
                )
                if r.status_code >= 300:
                    log.error("discord webhook 실패 %s: %s", r.status_code, r.text[:200])
            except requests.RequestException as e:
                log.error("discord webhook 오류: %s", e)

    # ----------------------------------------------------------------- telegram
    def _send_telegram(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        for part in _chunks(text, 4000):
            try:
                r = requests.post(
                    url,
                    json={"chat_id": self.telegram_chat_id, "text": part},
                    timeout=self.timeout,
                )
                if r.status_code >= 300:
                    log.error("telegram 전송 실패 %s: %s", r.status_code, r.text[:200])
            except requests.RequestException as e:
                log.error("telegram 전송 오류: %s", e)
