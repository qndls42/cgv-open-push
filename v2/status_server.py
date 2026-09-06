"""
로컬 상태 확인 페이지 (http://127.0.0.1:5000).
외부 패키지 없이 표준 라이브러리 http.server 만 사용한다.
"""

import html
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

log = logging.getLogger("cgv-open-push")


def tail(path: str, n: int = 60) -> str:
    if not os.path.exists(path):
        return "(로그 파일 없음)"
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 64 * 1024))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
        return "\n".join(reversed(lines[-n:]))
    except OSError as e:
        return f"(로그 읽기 실패: {e})"


def render(status: Dict[str, Any], log_path: str, interval: int) -> str:
    blocked = status.get("blocked")
    err = status.get("last_error")
    color = "#e06666" if (blocked or not status.get("last_check_at")) else "#1D976C"
    targets = "".join(
        f"<li><b>{html.escape(t['name'])}</b> — {html.escape(t['filter'])}<br>"
        f"회차 {t['showings']}건, 날짜 {', '.join(t['dates']) or '-'} "
        f"<small>({t['checked_at']})</small></li>"
        for t in status.get("targets", {}).values()
    ) or "<li>아직 조회 결과가 없습니다.</li>"
    notes = "".join(
        f"<li><b>{html.escape(n['title'])}</b> <small>{n['at']}</small><ul>"
        + "".join(f"<li>{html.escape(l)}</li>" for l in n["lines"][:30])
        + "</ul></li>"
        for n in status.get("recent_notifications", [])
    ) or "<li>아직 보낸 알림이 없습니다.</li>"
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="15">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CGV 예매 오픈 알리미 (로컬)</title>
<style>
 body{{font-family:system-ui,Apple SD Gothic Neo,Malgun Gothic,sans-serif;margin:1.5rem;color:#333;background:#fafafa}}
 .badge{{display:inline-block;padding:.3rem .8rem;border-radius:1rem;color:#fff;background:{color}}}
 pre{{background:#f0f0f0;padding:1rem;white-space:pre-wrap;font-size:.85rem;max-height:50vh;overflow:auto}}
 small{{color:#888}} ul{{line-height:1.6}}
</style></head><body>
<h1>CGV 예매 오픈 알리미 <small>(로컬)</small></h1>
<p><span class="badge">{'차단됨' if blocked else ('정상' if status.get('last_check_at') else '대기중')}</span>
 시작 {status.get('started_at')} · 마지막 조회 {status.get('last_check_at') or '-'} · 조회 {status.get('check_count')}회 · 주기 {interval}초</p>
{f'<p style="color:#c00">마지막 오류 ({status.get("last_error_at")}): {html.escape(str(err))}</p>' if err else ''}
<h2>감시 대상</h2><ul>{targets}</ul>
<h2>최근 알림</h2><ul>{notes}</ul>
<h2>로그</h2><pre>{html.escape(tail(log_path))}</pre>
</body></html>"""


def start_status_server(monitor, host: str, port: int, log_path: str) -> threading.Thread:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path.startswith("/status.json"):
                body = json.dumps(monitor.status, ensure_ascii=False).encode("utf-8")
                ctype = "application/json; charset=utf-8"
            else:
                body = render(monitor.status, log_path, monitor.interval).encode("utf-8")
                ctype = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):  # 접근 로그는 조용히
            return

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, name="status-server", daemon=True)
    thread.start()
    log.info("상태 페이지: http://%s:%d", "127.0.0.1" if host in ("0.0.0.0", "") else host, port)
    return thread
