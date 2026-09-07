"""
CGV 예매 오픈 알리미 v2 (로컬 PC 실행용)

사용법
  python main.py run                      # 감시 시작 (config.json 사용)
  python main.py theaters [검색어]         # 극장 코드 찾기   예) python main.py theaters 용산
  python main.py probe <극장코드> [날짜]   # 해당 극장의 상영 시간표/원본 필드 확인
  python main.py test-notify              # 알림 채널 테스트
  python main.py phone                    # 폰(ntfy 앱)에서 알림 받는 방법/구독 주소 출력
  python main.py check                    # 한 번만 조회하고 종료 (cron/작업 스케줄러용)

설정은 같은 폴더의 config.json 에서 읽는다. (없으면 config.example.json 을 복사해 만들 것)
민감한 값은 환경 변수 또는 같은 폴더의 .env 파일(KEY=VALUE 한 줄씩)로 줄 수 있다:
  DISCORD_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, NTFY_TOPIC

알림 채널을 아무것도 설정하지 않으면 첫 실행 때 ntfy 토픽(임의의 긴 이름)을 자동으로 만들어
config.json 에 저장한다. 폰에 ntfy 앱을 설치하고 그 토픽을 구독하면 바로 푸시 알림을 받을 수 있다.
"""

import json
import logging
import os
import secrets
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
ENV_PATH = os.path.join(HERE, ".env")
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


def load_dotenv(path: str) -> None:
    """아주 단순한 .env 로더: KEY=VALUE, # 주석, 따옴표 허용. 이미 있는 환경 변수는 덮어쓰지 않는다."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def load_config() -> dict:
    load_dotenv(ENV_PATH)
    if not os.path.exists(CONFIG_PATH):
        shutil.copyfile(EXAMPLE_PATH, CONFIG_PATH)
        print(f"config.json 이 없어 기본 설정(영등포타임스퀘어 모든 상영관)을 복사했습니다: {CONFIG_PATH}")
        print("다른 극장/영화를 감시하려면 이 파일의 targets 를 수정하세요.")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    # 환경 변수가 있으면 우선
    for env, key in (
        ("DISCORD_WEBHOOK_URL", "discord_webhook_url"),
        ("TELEGRAM_BOT_TOKEN", "telegram_bot_token"),
        ("TELEGRAM_CHAT_ID", "telegram_chat_id"),
        ("NTFY_TOPIC", "ntfy_topic"),
    ):
        if os.environ.get(env):
            config[key] = os.environ[env]
    if not [t for t in config.get("targets", []) if t.get("enabled", True)]:
        sys.exit("config.json 의 targets 가 비어 있습니다. 감시할 극장을 1개 이상 넣어주세요.")
    ensure_push_channel(config)
    return config


def ensure_push_channel(config: dict) -> None:
    """알림 채널이 하나도 없으면 ntfy 토픽을 자동 생성해 config.json 에 저장한다."""
    has_channel = any(
        (config.get(k) or "").strip() if isinstance(config.get(k), str) else config.get(k)
        for k in ("ntfy_topic", "discord_webhook_url", "telegram_bot_token")
    )
    if has_channel:
        return
    topic = "cgv-open-push-" + secrets.token_urlsafe(9).replace("-", "").replace("_", "")
    config["ntfy_topic"] = topic
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            on_disk = json.load(f)
        on_disk["ntfy_topic"] = topic
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(on_disk, f, ensure_ascii=False, indent=2)
        log.info("알림 채널이 없어 ntfy 토픽을 자동 생성했습니다: %s", topic)
    except (OSError, ValueError) as e:
        log.warning("ntfy 토픽을 config.json 에 저장하지 못했습니다: %s", e)


def phone_guide(notifier: Notifier) -> str:
    if not notifier.ntfy_topic:
        return "ntfy 토픽이 설정되어 있지 않습니다. (Discord/텔레그램 알림만 사용 중)"
    return (
        "\n📱 폰에서 알림 받는 방법 (ntfy)\n"
        "  1. 폰에 'ntfy' 앱 설치 (Android: Play 스토어 / iPhone: App Store, 무료)\n"
        "  2. 앱에서 + (구독) 을 누르고 아래 토픽 이름을 그대로 입력\n"
        f"     토픽: {notifier.ntfy_topic}\n"
        f"     주소: {notifier.ntfy_url}\n"
        "  3. 폰 설정에서 ntfy 앱 알림 허용 (iPhone 은 앱 설정에서 'Instant delivery' 켜기 권장)\n"
        "  ※ 토픽 이름을 아는 사람은 누구나 구독/발행할 수 있으니 공개하지 마세요.\n"
        "     브라우저에서도 위 주소를 열면 알림을 볼 수 있습니다.\n"
    )


# ----------------------------------------------------------------------- commands
def cmd_run(once: bool = False) -> None:
    config = load_config()
    notifier = Notifier(config)
    monitor = Monitor(config, notifier, STATE_PATH)
    if once:
        monitor.check_once()
        return
    if notifier.ntfy_topic:
        print(phone_guide(notifier), flush=True)
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
    print(phone_guide(notifier))
    notifier.send("[테스트] CGV 예매 오픈 알리미", "알림 설정이 정상입니다. 이 메시지가 폰에 떴다면 준비 끝!")


def cmd_phone() -> None:
    config = load_config()
    print(phone_guide(Notifier(config)))


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
        elif cmd == "phone":
            cmd_phone()
        else:
            print(__doc__)
            sys.exit(1)
    except CgvBlockedError as e:
        sys.exit(f"오류: {e}")


if __name__ == "__main__":
    main(sys.argv)
