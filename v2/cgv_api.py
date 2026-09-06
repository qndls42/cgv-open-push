"""
리뉴얼된 CGV(https://cgv.co.kr) 비공개 API 클라이언트.

- 베이스 URL : https://api.cgv.co.kr
- 모든 요청에는 X-TIMESTAMP / X-SIGNATURE 헤더가 필요하다.
  서명 = base64( HMAC-SHA256( secret, f"{timestamp}|{path}|{body}" ) )
  (secret 은 CGV 프론트엔드 번들에 하드코딩되어 있는 값이다.)

사용하는 엔드포인트
- GET /cnm/atkt/searchRegnList      : 지역/극장 목록      (coCd)
- GET /cnm/atkt/searchOnlyCgvMovList: 극장+날짜 영화 목록  (coCd, siteNo, scnYmd)
- GET /cnm/atkt/searchMovScnInfo    : 극장+날짜 상영 시간표 (coCd, siteNo, scnYmd, rtctlScopCd=08)
- GET /cnm/atkt/searchSchByMov      : 극장+날짜+영화 시간표 (coCd, siteNo, scnYmd, movNo, rtctlScopCd=01)
"""

import base64
import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional

import requests

BASE_URL = "https://api.cgv.co.kr"
COMPANY_CODE = "A420"
SIGNING_SECRET = "ydqXY0ocnFLmJGHr_zNzFcpjwAsXq_8JcBNURAkRscg"

THEATER_LIST_PATH = "/cnm/atkt/searchRegnList"
MOVIE_LIST_PATH = "/cnm/atkt/searchOnlyCgvMovList"
SCHEDULE_BY_SITE_PATH = "/cnm/atkt/searchMovScnInfo"
SCHEDULE_BY_MOVIE_PATH = "/cnm/atkt/searchSchByMov"
SITE_SCOPE_CODE = "08"
MOVIE_SCOPE_CODE = "01"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://cgv.co.kr",
    "Referer": "https://cgv.co.kr/cnm/movieBook",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
}


class CgvBlockedError(Exception):
    """CGV(Cloudflare) 가 요청을 차단(401/403)했을 때."""


class CgvApiError(Exception):
    """그 외 API 오류."""


def make_signature(path: str, timestamp: str, body: str = "") -> str:
    payload = f"{timestamp}|{path}|{body}".encode("utf-8")
    digest = hmac.new(SIGNING_SECRET.encode("utf-8"), payload, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


class CgvClient:
    def __init__(self, timeout: float = 15.0, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    # ---------------------------------------------------------------- low level
    def get(self, path: str, params: Dict[str, str]) -> Dict[str, Any]:
        timestamp = str(int(time.time()))
        headers = {
            "X-TIMESTAMP": timestamp,
            "X-SIGNATURE": make_signature(path, timestamp),
        }
        response = self.session.get(
            BASE_URL + path, params=params, headers=headers, timeout=self.timeout
        )
        if response.status_code in (401, 403):
            raise CgvBlockedError(
                f"CGV 가 요청을 차단했습니다 (HTTP {response.status_code}). "
                "서버/클라우드 IP 는 차단되는 경우가 많으니 가정용 PC 회선에서 실행하세요."
            )
        if response.status_code != 200:
            raise CgvApiError(f"HTTP {response.status_code}: {response.text[:200]}")
        try:
            data = response.json()
        except ValueError:
            raise CgvApiError(f"JSON 파싱 실패: {response.text[:200]}")
        # statusCode 0 또는 200 이 정상 응답
        status = data.get("statusCode")
        if status not in (None, 0, 200, "0", "200"):
            raise CgvApiError(f"statusCode={status} message={data.get('statusMessage')}")
        return data

    # ---------------------------------------------------------------- high level
    def theaters(self) -> List[Dict[str, str]]:
        """전체 극장 목록. [{theaterCode, theaterName, regionCode, regionName}, ...]"""
        data = self.get(THEATER_LIST_PATH, {"coCd": COMPANY_CODE})
        result = []
        for region in data.get("data") or []:
            for site in region.get("siteList") or []:
                if not site.get("siteNo") or not site.get("siteNm"):
                    continue
                result.append(
                    {
                        "theaterCode": site["siteNo"],
                        "theaterName": site["siteNm"],
                        "regionCode": region.get("regnGrpCd") or "",
                        "regionName": region.get("regnGrpNm") or "",
                    }
                )
        return result

    def movies(self, theater_code: str, play_date: str) -> List[Dict[str, Any]]:
        """특정 극장/날짜에 상영하는 영화 목록 (raw 항목: movNo, movNm, cratgClsNm ...)."""
        data = self.get(
            MOVIE_LIST_PATH,
            {"coCd": COMPANY_CODE, "siteNo": theater_code, "scnYmd": play_date},
        )
        return [m for m in (data.get("data") or []) if m.get("movNo")]

    def schedule(self, theater_code: str, play_date: str) -> List[Dict[str, Any]]:
        """특정 극장/날짜의 전체 상영 회차 (raw 항목 그대로 반환).

        웹 예매 페이지가 실제로 호출하는 searchMovScnInfo(rtctlScopCd=08) 를 사용한다.
        """
        data = self.get(
            SCHEDULE_BY_SITE_PATH,
            {
                "coCd": COMPANY_CODE,
                "siteNo": theater_code,
                "scnYmd": play_date,
                "rtctlScopCd": SITE_SCOPE_CODE,
            },
        )
        return [s for s in (data.get("data") or []) if s.get("scnYmd")]

    def schedule_by_movie(
        self, theater_code: str, play_date: str, movie_code: str
    ) -> List[Dict[str, Any]]:
        """특정 극장/날짜/영화 상영 회차 (fallback 용)."""
        data = self.get(
            SCHEDULE_BY_MOVIE_PATH,
            {
                "coCd": COMPANY_CODE,
                "siteNo": theater_code,
                "scnYmd": play_date,
                "movNo": movie_code,
                "rtctlScopCd": MOVIE_SCOPE_CODE,
            },
        )
        return [s for s in (data.get("data") or []) if s.get("scnYmd")]
