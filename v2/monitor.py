"""
예매 오픈 감시 로직.

설정된 극장마다 오늘부터 lookahead_days 일까지의 상영 시간표를 주기적으로 조회하고,
직전 조회 결과와 비교해 새로 생긴 회차(= 예매 오픈)를 알림으로 보낸다.

상영 회차 하나의 식별키 = (날짜, 영화코드, 상영관, 시작시각)
"""

import json
import logging
import os
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from cgv_api import CgvBlockedError, CgvClient

log = logging.getLogger("cgv-open-push")
# 한국은 서머타임이 없으므로 고정 오프셋으로 충분하다.
# (Windows Python 에는 zoneinfo 시간대 DB 가 없어 ZoneInfo("Asia/Seoul") 이 실패한다)
KST = timezone(timedelta(hours=9), "KST")

# 상영관 이름/유형이 들어 있을 가능성이 높은 raw 필드 후보 (앞에서부터 우선)
SCREEN_KEY_CANDIDATES = (
    "scnsNm", "scrnNm", "sscnsNm", "thabNm", "expoNm", "scnsClsNm",
    "spclScnsNm", "sctnNm", "screenNm", "scnsNo", "scrnNo",
)
MOVIE_NAME_KEYS = ("movNm", "prodNm", "movieNm")
MOVIE_CODE_KEYS = ("movNo", "movieNo", "prodNo")


def now_kst() -> datetime:
    return datetime.now(KST)


def yyyymmdd(d: datetime) -> str:
    return d.strftime("%Y%m%d")


# 조회 주기 하한. 이보다 짧게 두면 CGV 에 차단당하기 쉽다.
MIN_INTERVAL_SEC = 10.0


def parse_interval(value: Any) -> Tuple[float, float]:
    """조회 주기 설정을 (최소, 최대) 초로 해석한다.

    - 300            -> (300, 300)   고정 주기
    - [10, 30]       -> (10, 30)     매 회차 이 범위의 난수
    - {"min":10,"max":30} -> (10, 30)
    """
    if isinstance(value, dict):
        low, high = value.get("min", 300), value.get("max", value.get("min", 300))
    elif isinstance(value, (list, tuple)) and value:
        low = value[0]
        high = value[1] if len(value) > 1 else value[0]
    else:
        low = high = value
    try:
        low, high = float(low), float(high)
    except (TypeError, ValueError):
        low = high = 300.0
    if high < low:
        low, high = high, low
    if low < MIN_INTERVAL_SEC:
        log.warning("조회 주기 %.0f초는 너무 짧아 %.0f초로 올립니다.", low, MIN_INTERVAL_SEC)
        low = MIN_INTERVAL_SEC
        high = max(high, MIN_INTERVAL_SEC)
    return low, high


def first_value(item: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def fmt_time(raw: Any) -> str:
    s = str(raw or "")
    if ":" in s or len(s) != 4:
        return s
    return f"{s[:2]}:{s[2:]}"


def fmt_date(raw: str) -> str:
    try:
        d = datetime.strptime(raw, "%Y%m%d")
        weekday = "월화수목금토일"[d.weekday()]
        return f"{d.month}/{d.day}({weekday})"
    except ValueError:
        return raw


class Showing:
    """raw 시간표 항목을 다루기 쉽게 감싼 객체."""

    __slots__ = ("raw", "date", "movie_code", "movie_name", "screen", "start", "end", "seats", "total")

    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw
        self.date = str(raw.get("scnYmd") or "")
        self.movie_code = first_value(raw, MOVIE_CODE_KEYS)
        self.movie_name = first_value(raw, MOVIE_NAME_KEYS)
        self.screen = first_value(raw, SCREEN_KEY_CANDIDATES)
        self.start = fmt_time(raw.get("scnsrtTm"))
        self.end = fmt_time(raw.get("scnendTm"))
        self.seats = str(raw.get("frSeatCnt") or raw.get("frtmpSeatCnt") or "")
        self.total = str(raw.get("stcnt") or "")

    @property
    def key(self) -> str:
        return "|".join([self.date, self.movie_code or self.movie_name, self.screen, self.start])

    @property
    def search_text(self) -> str:
        # 필터 키워드 매칭용: 항목의 모든 값을 한 문자열로 합친다 (필드명을 몰라도 동작)
        return " ".join(str(v) for v in self.raw.values() if v not in (None, "")).lower()

    def line(self) -> str:
        parts = [fmt_date(self.date), f"{self.start}~{self.end}".strip("~")]
        if self.screen:
            parts.append(self.screen)
        parts.append(self.movie_name or self.movie_code)
        if self.seats and self.total:
            parts.append(f"{self.seats}/{self.total}석")
        return " · ".join(p for p in parts if p)


class Target:
    def __init__(self, cfg: Dict[str, Any]):
        self.theater_code = str(cfg["theater_code"])
        self.name = cfg.get("name") or f"CGV {self.theater_code}"
        self.screen_keywords = [k.lower() for k in cfg.get("screen_keywords", []) if k]
        self.movie_keywords = [k.lower() for k in cfg.get("movie_keywords", []) if k]
        self.exclude_keywords = [k.lower() for k in cfg.get("exclude_keywords", []) if k]
        # 특정 날짜만 감시 (예: ["20260912"] 또는 ["2026-09-12"]). 비우면 모든 날짜
        self.dates = {str(d).replace("-", "").replace(".", "").strip() for d in cfg.get("dates", []) if d}
        self.enabled = bool(cfg.get("enabled", True))
        # 상태 저장용 고유 키 (같은 극장에 여러 대상을 둘 수 있으므로 이름까지 포함)
        self.id = f"{self.theater_code}|{self.name}"

    def accepts(self, showing: Showing) -> bool:
        if self.dates and showing.date not in self.dates:
            return False
        text = showing.search_text
        if self.exclude_keywords and any(k in text for k in self.exclude_keywords):
            return False
        if self.screen_keywords and not any(k in text for k in self.screen_keywords):
            return False
        if self.movie_keywords:
            movie = (showing.movie_name or "").lower()
            if not any(k in movie or k in text for k in self.movie_keywords):
                return False
        return True

    def describe(self) -> str:
        bits = [f"{self.name}({self.theater_code})"]
        if self.dates:
            bits.append("날짜=" + "/".join(fmt_date(d) for d in sorted(self.dates)))
        if self.screen_keywords:
            bits.append("상영관=" + "/".join(self.screen_keywords))
        if self.movie_keywords:
            bits.append("영화=" + "/".join(self.movie_keywords))
        if self.exclude_keywords:
            bits.append("제외=" + "/".join(self.exclude_keywords))
        return " ".join(bits)


class Monitor:
    def __init__(self, config: Dict[str, Any], notifier, state_path: str):
        self.client = CgvClient(timeout=float(config.get("request_timeout_sec", 15)))
        self.notifier = notifier
        self.targets = [t for t in (Target(c) for c in config.get("targets", [])) if t.enabled]
        self.interval_min, self.interval_max = parse_interval(config.get("check_interval_sec", 300))
        self.lookahead_days = int(config.get("lookahead_days", 14))
        self.request_delay = float(config.get("request_delay_sec", 1.0))
        self.notify_on_first_run = bool(config.get("notify_on_first_run", False))
        self.notify_removed = bool(config.get("notify_removed", False))
        self.state_path = state_path
        self.state: Dict[str, Any] = self._load_state()
        self.lock = threading.Lock()
        # 상태 페이지용 정보
        self.status: Dict[str, Any] = {
            "started_at": now_kst().isoformat(timespec="seconds"),
            "last_check_at": None,
            "last_error": None,
            "last_error_at": None,
            "check_count": 0,
            "blocked": False,
            "targets": {},
            "recent_notifications": [],
        }

    @property
    def interval_text(self) -> str:
        if self.interval_min == self.interval_max:
            return f"{self.interval_min:.0f}"
        return f"{self.interval_min:.0f}~{self.interval_max:.0f}"

    def next_interval(self) -> float:
        """다음 조회까지 기다릴 시간. 범위가 주어졌으면 매번 다른 난수를 쓴다."""
        if self.interval_min == self.interval_max:
            return self.interval_min
        return random.uniform(self.interval_min, self.interval_max)

    # ------------------------------------------------------------------ state
    def _load_state(self) -> Dict[str, Any]:
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError) as e:
                log.warning("상태 파일을 읽지 못해 새로 시작합니다: %s", e)
        return {}

    def _save_state(self) -> None:
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.state_path)

    # ---------------------------------------------------------------- fetching
    def dates(self, targets: Optional[List[Target]] = None) -> List[str]:
        """조회할 날짜 목록.

        대상이 모두 특정 날짜(dates)를 지정했다면 그 날짜만 조회한다.
        날짜를 지정하지 않은 대상이 하나라도 있으면 오늘부터 lookahead_days 일까지 전부 조회한다.
        """
        targets = self.targets if targets is None else targets
        today = now_kst()
        today_str = yyyymmdd(today)

        if targets and all(t.dates for t in targets):
            wanted = sorted({d for t in targets for d in t.dates if d >= today_str})
            if wanted:
                return wanted
            # 지정한 날짜가 모두 지났으면 오늘만 확인
            return [today_str]

        days = self.lookahead_days
        # 날짜를 지정한 대상이 섞여 있으면 그 날짜까지는 조회 범위에 포함
        for target in targets:
            for d in target.dates:
                try:
                    delta = (datetime.strptime(d, "%Y%m%d").date() - today.date()).days
                except ValueError:
                    continue
                days = max(days, min(delta, 60))
        return [yyyymmdd(today + timedelta(days=i)) for i in range(days + 1)]

    def fetch_theater(self, theater_code: str, targets: Optional[List[Target]] = None) -> List[Showing]:
        """극장 하나의 회차를 가져온다 (필터 적용 전)."""
        result: List[Showing] = []
        dates = self.dates(targets)
        for index, date in enumerate(dates):
            for raw in self.client.schedule(theater_code, date):
                result.append(Showing(raw))
            if index < len(dates) - 1:
                time.sleep(self.request_delay)
        return result

    # -------------------------------------------------------------------- diff
    def check_once(self) -> None:
        # 같은 극장을 감시하는 대상들은 한 번만 조회해서 공유한다
        by_theater: Dict[str, List[Target]] = {}
        for target in self.targets:
            by_theater.setdefault(target.theater_code, []).append(target)

        for theater_code, targets in by_theater.items():
            try:
                showings = self.fetch_theater(theater_code, targets)
            except CgvBlockedError as e:
                self._record_error(str(e), blocked=True)
                log.error("%s: %s", theater_code, e)
                return
            except Exception as e:  # noqa: BLE001 - 어떤 오류든 루프는 계속 돌아야 한다
                self._record_error(f"{theater_code}: {e}")
                log.exception("극장 %s 조회 실패", theater_code)
                continue

            for target in targets:
                current = {s.key: s for s in showings if target.accepts(s)}
                self._diff_and_notify(target, current)

        with self.lock:
            self.status["last_check_at"] = now_kst().isoformat(timespec="seconds")
            self.status["check_count"] += 1
            self.status["blocked"] = False

    def _diff_and_notify(self, target: Target, current: Dict[str, Showing]) -> None:
        with self.lock:
            previous: Optional[Dict[str, str]] = self.state.get(target.id)
            current_lines = {k: s.line() for k, s in current.items()}
            if previous is None:
                log.info("%s: 첫 조회, 회차 %d건을 기준으로 저장", target.name, len(current))
                if self.notify_on_first_run and current:
                    self._notify(target, "현재 예매 가능 회차", [current_lines[k] for k in sorted(current_lines)])
            else:
                added = [current_lines[k] for k in sorted(current_lines.keys() - previous.keys())]
                removed = [previous[k] for k in sorted(previous.keys() - current_lines.keys())]
                if added:
                    log.info("%s: 새 회차 %d건", target.name, len(added))
                    self._notify(target, "예매 오픈 알림", added)
                if removed:
                    log.info("%s: 사라진 회차 %d건 %s", target.name, len(removed), removed[:5])
                    if self.notify_removed:
                        self._notify(target, "회차 삭제/마감", removed)
                if not added and not removed:
                    log.info("%s: 변동 없음 (%d건)", target.name, len(current))
            self.state[target.id] = current_lines
            self._save_state()
            self.status["targets"][target.id] = {
                "name": target.name,
                "filter": target.describe(),
                "showings": len(current),
                "dates": sorted({s.date for s in current.values()}),
                "checked_at": now_kst().isoformat(timespec="seconds"),
            }

    def _record_error(self, message: str, blocked: bool = False) -> None:
        with self.lock:
            self.status["last_error"] = message
            self.status["last_error_at"] = now_kst().isoformat(timespec="seconds")
            if blocked:
                self.status["blocked"] = True

    def _notify(self, target: Target, title: str, lines: List[str]) -> None:
        # 날짜별로 묶어서 보기 좋게
        body = "\n".join(f"- {line}" for line in lines)
        full_title = f"[{target.name}] {title} ({len(lines)}건)"
        self.notifier.send(full_title, body)
        self.status["recent_notifications"].insert(
            0, {"at": now_kst().isoformat(timespec="seconds"), "title": full_title, "lines": lines}
        )
        del self.status["recent_notifications"][20:]

    # -------------------------------------------------------------------- loop
    def run_forever(self) -> None:
        log.info("감시 시작: %s", "; ".join(t.describe() for t in self.targets))
        log.info("조회 주기 %s초, 조회 날짜 %s, 알림 채널 %s",
                 self.interval_text, ", ".join(self.dates()), self.notifier.targets)
        while True:
            started = time.monotonic()
            self.check_once()
            elapsed = time.monotonic() - started
            wait = max(MIN_INTERVAL_SEC, self.next_interval() - elapsed)
            if self.status.get("blocked"):
                wait = max(wait, 600.0)  # 차단당했으면 10분 이상 쉬었다가 재시도
                log.warning("차단 상태입니다. %d초 후 재시도", int(wait))
            time.sleep(wait)
