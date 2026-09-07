@echo off
chcp 65001 >nul
rem ============================================================
rem  CGV 예매 오픈 알리미 v2 - 원클릭 설치 + 실행 (Windows)
rem  더블클릭하면: 가상환경 생성 -> 패키지 설치 -> 웹훅 입력(.env) -> 알림 테스트 -> 감시 시작
rem  두 번째부터는 run.bat 만 더블클릭하면 됩니다.
rem ============================================================
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo [오류] Python 이 설치되어 있지 않거나 PATH 에 없습니다.
  echo        https://www.python.org/downloads/ 에서 설치할 때 "Add python.exe to PATH" 를 꼭 체크하세요.
  pause
  exit /b 1
)

if not exist .venv (
  echo [1/4] 가상환경 생성 중...
  python -m venv .venv
  if errorlevel 1 ( echo [오류] 가상환경 생성 실패 & pause & exit /b 1 )
)

echo [2/4] 패키지 설치 중...
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 ( echo [오류] 패키지 설치 실패. 인터넷 연결을 확인하세요. & pause & exit /b 1 )

if exist .env goto :env_done
echo [3/4] 알림 설정
echo   Discord 웹훅 URL 을 붙여넣고 Enter 를 누르세요.
echo   (그냥 Enter 를 누르면 Discord 대신 ntfy 폰 알림이 자동으로 설정됩니다)
set "WEBHOOK="
set /p "WEBHOOK=> 웹훅 URL: "
if defined WEBHOOK (
  >.env echo DISCORD_WEBHOOK_URL=%WEBHOOK%
  echo   .env 에 저장했습니다.
) else (
  type nul >.env
)
:env_done

echo [4/4] 알림 테스트
.venv\Scripts\python main.py test-notify
if errorlevel 1 (
  echo.
  echo [오류] 알림 테스트에 실패했습니다. 위 오류 메시지를 확인하세요.
  pause
  exit /b 1
)
echo.
echo ------------------------------------------------------------
echo  위 테스트 메시지가 Discord(또는 ntfy 앱)에 도착했는지 확인하세요.
echo  지금부터 감시를 시작합니다. 상태 페이지: http://127.0.0.1:5000
echo  종료하려면 Ctrl+C 를 누르거나 이 창을 닫으세요. 다음부터는 run.bat 만 실행하면 됩니다.
echo ------------------------------------------------------------
.venv\Scripts\python main.py run
pause
