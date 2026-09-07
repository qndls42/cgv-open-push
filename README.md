<div align="center">

# CGV 예매 오픈 알리미

<p align="center">
  <img src="./img/logo.png" width="160"/>
</p>

by_0w0i0n0g0

image_by_<a href="https://kr.freepik.com/free-photo/3d-render-notification-bell-icon-new-email-message_34503708.htm#query=%EC%95%8C%EB%A6%BC%20%EC%95%84%EC%9D%B4%EC%BD%98&position=0&from_view=keyword&track=ais&uuid=0303dc60-e421-4177-8ab2-29b1326ae712">upklyak</a>

</div>

<br>
<br>

### 📢 안내

당분간 용산 CGV 특별관에 대한 예매 오픈 알리미만 운영될 예정입니다.

추가 건의나 문의사항은 [issues](https://github.com/0w0i0n0g0/cgv-open-push/issues)에 남겨주시면 남겨주시면 최대한 반영할 수 있도록 하겠습니다.

<br>

### 🎥 메가박스 예매 오픈 알리미도 확인해보세요!

[메가박스 예매 오픈 알리미](https://github.com/0w0i0n0g0/megabox-open-push)

<br>

### 🔎 현재 동작하고 있는 알리미는?

> (2026년 6월 기준)

- 용산아이파크몰 IMAX
- 용산아이파크몰 4DX
- 용산아이파크몰 SCREENX

<br>

### 📄 최근 업데이트 내역

**CGV 앱 리뉴얼에 맞추어 수정되었습니다!**

수정으로 인한 오류가 있을 수 있으니, 양해 부탁드립니다.

<br>
<br>

## 알림 받는 방법!

### Discord 앱을 다운받으세요.

설치 후, 설정에서 Discord 앱 알림을 허용해주세요.

<br>

### 아래 초대 링크를 클릭하여 CGV 예매 오픈 알리미 서버에 접속하세요.

https://snapp.wzero.dev/cgv

> 초대 링크가 동작하지 않는다면 [issues](https://github.com/0w0i0n0g0/cgv-open-push/issues)에 문의를 남겨주세요.
>
> 최대한 빠르게 업데이트하도록 하겠습니다.

<br>

### 꼭 확인해주세요.

`전체공지` 채널과 `자주묻는질문` 채널을 꼭 정독한 후 이용해주세요.

<br>
<br>

## 🖥️ 내 PC에서 직접 돌리기 (v2 · 원하는 극장 지정)

`v2/` 폴더에는 **리뉴얼된 CGV(https://cgv.co.kr) API** 를 사용하는 로컬 실행용 버전이 들어 있습니다.
Discord 봇을 만들 필요 없이 **웹훅 URL 하나**만 있으면 되고, 원하는 극장·특별관·영화를 설정 파일로 지정할 수 있습니다.

> `v1/` 은 리뉴얼 이전 API(`ticket.cgv.co.kr`)를 쓰는 예전 버전이라 현재는 동작하지 않습니다.

### 1. 준비물

- Python 3.9 이상 (https://www.python.org/downloads/ · 설치 시 *Add python to PATH* 체크)
- 폰에 **ntfy 앱** (Android / iPhone, 무료) — 별도 계정이나 서버 없이 푸시 알림을 받을 수 있습니다.
  - 첫 실행 때 알리미가 임의의 토픽 이름을 자동으로 만들어 주므로, 그 토픽을 앱에서 구독하기만 하면 됩니다.
  - Discord 로 받고 싶다면 채널 설정 → 연동 → 웹후크 에서 만든 **웹훅 URL** 을 설정에 넣으세요. (텔레그램도 지원)

### 2. 설치 + 실행 (가장 쉬운 방법)

1. 코드를 받습니다. git 이 없으면 GitHub 저장소 페이지의 **Code → Download ZIP** 으로 받아 압축을 풉니다.
   ```bash
   git clone https://github.com/qndls42/cgv-open-push.git
   ```
2. `v2` 폴더의 **`setup.bat`** (Windows) 또는 **`setup.sh`** (macOS/Linux) 를 실행합니다.
   - 가상환경 생성 → 패키지 설치 → Discord 웹훅 URL 입력(`.env` 에 저장) → 알림 테스트 → 감시 시작까지 자동으로 진행됩니다.
   - 웹훅 URL 을 비워 두고 Enter 를 누르면 ntfy 폰 알림이 자동으로 설정됩니다.
3. 두 번째부터는 `run.bat` / `run.sh` 만 실행하면 됩니다.

수동으로 하려면:

```bash
cd cgv-open-push/v2
python -m venv .venv
# Windows
.venv\Scripts\pip install -r requirements.txt
# macOS / Linux
.venv/bin/pip install -r requirements.txt
```

### 3. 감시할 극장 코드 찾기

```bash
python main.py theaters 용산      # 이름으로 검색
python main.py theaters           # 전체 목록
```

자주 쓰는 코드: `0013` 용산아이파크몰 · `0056` 강남 · `0074` 왕십리 · `0059` 영등포타임스퀘어 · `0112` 여의도

```bash
python main.py probe 0013         # 해당 극장의 상영 회차와 원본 필드 확인 (필터 키워드 정할 때 참고)
```

### 4. 설정 (`config.json`)

처음 실행하면 `config.example.json` 이 `config.json` 으로 복사됩니다. 기본값은 **영등포타임스퀘어(0059) 모든 상영관** 입니다.
다른 극장이나 영화를 보고 싶으면 `targets` 를 고치세요.

```jsonc
{
  "targets": [
    { "name": "영등포타임스퀘어",        "theater_code": "0059", "screen_keywords": [] },        // 모든 상영관
    { "name": "영등포타임스퀘어 IMAX",    "theater_code": "0059", "screen_keywords": ["IMAX"] }, // 특정 상영관만
    { "name": "강남 아바타",             "theater_code": "0056", "movie_keywords": ["아바타"] }  // 특정 영화
  ],
  "check_interval_sec": 300,        // 조회 주기 (초). 너무 짧게 잡으면 차단될 수 있음
  "lookahead_days": 14,             // 오늘부터 며칠치 시간표를 볼지
  "notify_on_first_run": false,     // true 면 첫 실행 때 현재 예매 가능 회차도 알림
  "ntfy_topic": "",                 // 비워 두면 첫 실행 때 자동 생성
  "discord_webhook_url": "",        // Discord 로도 받고 싶을 때
  "status_page": { "enabled": true, "host": "127.0.0.1", "port": 5000 }
}
```

| 항목 | 설명 |
|---|---|
| `theater_code` | CGV 극장 코드 (`theaters` 명령으로 확인). 지역 코드는 필요 없습니다. |
| `screen_keywords` | 상영관/유형 키워드. 하나라도 포함된 회차만 감시. 비우면 모든 상영관 (`IMAX`, `4DX`, `SCREENX`, `골드클래스` …) |
| `movie_keywords` | 영화 제목 키워드. 비우면 모든 영화 |
| `exclude_keywords` | 포함되면 무시할 키워드 |
| `ntfy_topic` | 폰 알림용 ntfy 토픽. 비워 두면 자동 생성. 아는 사람은 누구나 구독할 수 있으니 공개하지 마세요 |

**Discord 웹훅 URL 은 `config.json` 대신 같은 폴더에 `.env` 파일을 만들어 넣는 것을 권장합니다.** (`.env` 는 git 에 올라가지 않습니다)

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/....
```

### 5. 실행

```bash
python main.py test-notify        # 알림 채널 테스트 (ntfy 토픽이 없으면 여기서 자동 생성되고 구독 방법이 출력됨)
python main.py phone              # 폰 구독용 토픽 이름 / 주소 다시 보기
python main.py run                # 감시 시작 (Ctrl+C 로 종료)
```

**폰에서 받기**: `test-notify` 가 출력한 토픽 이름을 ntfy 앱의 구독(+)에 입력하면 끝입니다. 테스트 메시지가 폰에 뜨는지 확인하세요.

- 실행 중 http://127.0.0.1:5000 에서 상태·최근 알림·로그를 볼 수 있습니다.
- 처음 실행하면 현재 시간표를 기준으로 저장만 하고, 이후 **새로 생긴 회차(= 예매 오픈)** 만 알립니다.
- 상태는 `state.json` 에 저장되므로 프로그램을 껐다 켜도 이어서 감시합니다.
- 한 번만 조회하고 끝내려면 `python main.py check` (작업 스케줄러 / cron 용).

### 6. 동작 원리와 주의사항

- CGV 웹 예매 페이지가 호출하는 `https://api.cgv.co.kr/cnm/atkt/searchMovScnInfo` 를 극장·날짜별로 조회해 직전 결과와 비교합니다.
- 요청에는 CGV 프론트엔드와 동일한 `X-TIMESTAMP` / `X-SIGNATURE`(HMAC-SHA256) 헤더를 붙입니다.
- **클라우드/서버 IP 는 Cloudflare 에 의해 403 으로 차단되는 경우가 많습니다.** 가정용 PC 회선에서 실행하세요. 차단이 감지되면 10분 이상 쉬었다가 재시도합니다.
- 조회 주기를 너무 짧게 잡거나 극장을 너무 많이 넣으면 차단될 수 있습니다. (기본: 5분마다, 극장당 15회 요청)
- CGV 가 API 를 바꾸면 동작하지 않을 수 있습니다. `python main.py probe <극장코드>` 로 응답을 확인해 보세요.

<br>
<br>

## 사용 전 반드시 읽어주세요.

-  CGV 예매 오픈 알리미는 CGV의 특정 영화관, 특정 영화의 상영 일정을 주기적으로 갱신하여 변동사항을 확인하고, 변동사항이 발생된다면 Discord를 통해 알림을 전송합니다.

- 원활한 운영을 위해 Discord 서버 내에서 예매 오픈 알림을 받는 것 이외에 채널에 메시지를 게시하거나, 서버 운영에 피해가 되는 행동이 발견되면 경고 없이 차단될 수 있습니다. 모든 문의사항은 Github에 게시하여 주시기 바랍니다.

- 이 서비스는 CGV와 어떠한 협의없이 제작되었으며, 인터넷을 통해 모두가 접근 가능하고 공개된 경로로만 정보를 취득합니다.

- 소스코드는 [**AGPL-3.0 license**](https://github.com/0w0i0n0g0/cgv-open-push/blob/main/LICENSE)로 배포되었습니다. 따라서 소스코드를 포함하거나 소스코드의 일부분을 사용, 수정, 2차 가공, 재배포할 때 해당 라이센스의 내용을 지켜주시기 바랍니다.

<br>
<br>

## Stack

> v2 (로컬 버전) 은 Python + requests 만 사용합니다.

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) ![Docker](https://img.shields.io/badge/docker-0db7ed.svg?style=for-the-badge&logo=docker&logoColor=white) ![Discord](https://img.shields.io/badge/Discord-7289DA?style=for-the-badge&logo=discord&logoColor=white)

<br>
<br>

## License

**AGPL-3.0 license**

Read full license [here](https://github.com/0w0i0n0g0/cgv-open-push/blob/main/LICENSE).