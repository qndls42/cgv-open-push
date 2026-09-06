"""
CGV 예매 오픈 알리미 v2 (로컬 PC 실행용)

사용법
  python main.py run                      # 감시 시작 (config.json 사용)
  python main.py theaters [검색어]         # 극장 코드 찾기   예) python main.py theaters 용산
  python main.py probe <극장코드> [날짜]   # 해당 극장의 상영 시간표/원본 필드 확인
  python main.py test-notify              # 알림 채널 테스트
  python main.py check                    # 한 번만 조회하고 종료 (cron/작업 스케줄러용)

설정은 같은 폴더의 config.json 에서 읽는다. (없으면 config.example.json 을 복사해 만들 것)
민감한 값은 환경 변수로도 줄 수 있다: DISCORD_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import json
import logging
import os
import shutil
import sys
from datetime import timedelta
from logging.handlers import RotatingFileHandler

from cgv_api import CgvBlockedError, CgvClient
from monitor import Monitor, Showing, now_kst, yyyymmdd
from notifier import Notifier
from status_server import start_status_server

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
EXAMPLE_PATH = os.path.join(HERE, "config.example.json")
STATE_PATH = os.path.join(HERE, "state.json")
LOG_PATH = os.path.join(HERE, "cgv-open-push.log")

log = logging.getLogger("cgv-open-push")


def setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    log.setLevel(logging.INFO)
    log.addHandler(file_handler)
    log.addHandler(console)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        shutil.copyfile(EXAMPLE_PATH, CONFIG_PATH)
        print(f"config.json 이 없어 예시 설정을 복사했습니다: {CONFIG_PATH}")
        print("극장 코드/알림 설정을 수정한 뒤 다시 실행하세요.")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    # 환경 변수가 있으면 우선
    for env, key in (
        ("DISCORD_WEBHOOK_URL", "discord_webhook_url"),
        ("TELEGRAM_BOT_TOKEN", "telegram_bot_token"),
        ("TELEGRAM_CHAT_ID", "telegram_chat_id"),
    ):
        if os.environ.get(env):
            config[key] = os.environ[env]
    if not config.get("targets"):
        sys.exit("config.json 의 targets 가 비어 있습니다. 감시할 극장을 1개 이상 넣어주세요.")
    return config


# ----------------------------------------------------------------------- commands
def cmd_run(once: bool = False) -> None:
    config = load_config()
    notifier = Notifier(config)
    monitor = Monitor(config, notifier, STATE_PATH)
    if once:
        monitor.check_once()
        return
    if config.get("status_page", {}).get("enabled", True):
        page = config.get("status_page", {})
        start_status_server(monitor, page.get("host", "127.0.0.1"), int(page.get("port", 5000)), LOG_PATH)
    try:
        monitor.run_forever()
    except KeyboardInterrupt:
        log.info("종료합니다.")


def cmd_theaters(keyword: str = "") -> None:
    client = CgvClient()
    theaters = client.theaters()
    keyword = keyword.strip()
    rows = [t for t in theaters if not keyword or keyword in t["theaterName"] or keyword in t["regionName"]]
    if not rows:
        print("검색 결과가 없습니다.")
        return
    print(f"{'코드':<6} {'지역':<8} 극장")
    for t in rows:
        print(f"{t['theaterCode']:<6} {t['regionName']:<8} {t['theaterName']}")
    print(f"\n총 {len(rows)}개. config.json 의 theater_code 에 코드를 넣으세요.")


def cmd_probe(theater_code: str, date: str = "") -> None:
    client = CgvClient()
    date = date or yyyymmdd(now_kst())
    items = client.schedule(theater_code, date)
    if not items:
        # 오늘 상영이 없으면 앞으로 7일 중 첫 상영일을 찾아본다
        for i in range(1, 8):
            d = yyyymmdd(now_kst() + timedelta(days=i))
            items = client.schedule(theater_code, d)
            if items:
                date = d
                break
    print(f"극장 {theater_code} / {date} 상영 회차 {len(items)}건\n")
    for raw in items:
        print("  " + Showing(raw).line())
    if items:
        print("\n원본 필드 예시 (첫 번째 회차). 상영관 필터 키워드를 정할 때 참고하세요:")
        print(json.dumps(items[0], ensure_ascii=False, indent=2))
        keys = sorted({k for it in items for k in it.keys()})
        print("\n전체 필드 목록:", ", ".join(keys))


def cmd_test_notify() -> None:
    config = load_config()
    notifier = Notifier(config)
    print("알림 채널:", notifier.targets)
    notifier.send("[테스트] CGV 예매 오픈 알리미", "알림 설정이 정상입니다.")


def main(argv) -> None:
    setup_logging()
    cmd = argv[1] if len(argv) > 1 else "run"
    try:
        if cmd == "run":
            cmd_run()
        elif cmd == "check":
            cmd_run(once=True)
        elif cmd == "theaters":
            cmd_theaters(argv[2] if len(argv) > 2 else "")
        elif cmd == "probe":
            if len(argv) < 3:
                sys.exit("사용법: python main.py probe <극장코드> [YYYYMMDD]")
            cmd_probe(argv[2], argv[3] if len(argv) > 3 else "")
        elif cmd == "test-notify":
            cmd_test_notify()
        else:
            print(__doc__)
            sys.exit(1)
    except CgvBlockedError as e:
        sys.exit(f"오류: {e}")


if __name__ == "__main__":
    main(sys.argv)
