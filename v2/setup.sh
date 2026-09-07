#!/usr/bin/env bash
# CGV 예매 오픈 알리미 v2 - 원클릭 설치 + 실행 (macOS / Linux)
set -e
cd "$(dirname "$0")"

command -v python3 >/dev/null 2>&1 || { echo "[오류] python3 가 없습니다. https://www.python.org/downloads/"; exit 1; }

if [ ! -d .venv ]; then
  echo "[1/4] 가상환경 생성 중..."
  python3 -m venv .venv
fi
echo "[2/4] 패키지 설치 중..."
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt

if [ ! -f .env ]; then
  echo "[3/4] 알림 설정"
  echo "  Discord 웹훅 URL 을 붙여넣고 Enter (그냥 Enter 면 ntfy 폰 알림이 자동 설정됩니다)"
  read -r -p "> 웹훅 URL: " WEBHOOK
  if [ -n "$WEBHOOK" ]; then
    printf 'DISCORD_WEBHOOK_URL=%s\n' "$WEBHOOK" > .env
    echo "  .env 에 저장했습니다."
  else
    : > .env
  fi
fi

echo "[4/4] 알림 테스트"
.venv/bin/python main.py test-notify
echo
echo "------------------------------------------------------------"
echo " 위 테스트 메시지가 도착했는지 확인하세요. 지금부터 감시를 시작합니다."
echo " 상태 페이지: http://127.0.0.1:5000  (종료: Ctrl+C, 다음부터는 ./run.sh)"
echo "------------------------------------------------------------"
exec .venv/bin/python main.py run
