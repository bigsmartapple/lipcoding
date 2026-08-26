"""카카오 '나에게 보내기' 최초 인증용 1회성 로컬 스크립트.

로컬 PC에서 실행해 브라우저로 카카오 로그인 동의를 받고,
GitHub Actions에서 사용할 refresh_token을 발급받는다.

사용법:
    python scripts/get_kakao_token.py --rest-api-key <카카오 REST API 키>

사전 준비:
    1. https://developers.kakao.com 에서 애플리케이션 생성
    2. [카카오 로그인] 활성화, Redirect URI에 아래 --redirect-uri 값(기본
       http://localhost:8888/oauth)을 정확히 등록
    3. [카카오 로그인 > 동의항목]에서 "카카오톡 메시지 전송" 항목을 사용 설정
"""
from __future__ import annotations

import argparse
import http.server
import urllib.parse
import webbrowser

import requests

KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
DEFAULT_REDIRECT_URI = "http://localhost:8888/oauth"


def _wait_for_authorization_code(port: int) -> str:
    captured: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            captured["code"] = params.get("code", [""])[0]

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("인증이 완료되었습니다. 이 창은 닫아도 됩니다.".encode("utf-8"))

        def log_message(self, format, *args):  # noqa: A002
            return  # 콘솔 로그 억제

    server = http.server.HTTPServer(("localhost", port), Handler)
    server.handle_request()  # 요청 1건만 처리하고 종료
    return captured.get("code", "")


def main() -> None:
    parser = argparse.ArgumentParser(description="카카오 refresh_token 최초 발급")
    parser.add_argument("--rest-api-key", required=True, help="카카오 개발자 콘솔의 REST API 키")
    parser.add_argument("--redirect-uri", default=DEFAULT_REDIRECT_URI)
    args = parser.parse_args()

    port = urllib.parse.urlparse(args.redirect_uri).port or 8888

    authorize_url = (
        f"{KAKAO_AUTHORIZE_URL}?"
        + urllib.parse.urlencode(
            {
                "client_id": args.rest_api_key,
                "redirect_uri": args.redirect_uri,
                "response_type": "code",
                "scope": "talk_message",
            }
        )
    )

    print("브라우저에서 카카오 로그인 동의 화면을 엽니다...")
    print(authorize_url)
    webbrowser.open(authorize_url)

    code = _wait_for_authorization_code(port)
    if not code:
        print("인증 코드를 받지 못했습니다. Redirect URI 설정을 확인하세요.")
        return

    resp = requests.post(
        KAKAO_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": args.rest_api_key,
            "redirect_uri": args.redirect_uri,
            "code": code,
        },
        timeout=10,
    )
    resp.raise_for_status()
    token_data = resp.json()

    print("\n토큰 발급 완료. 아래 refresh_token을 GitHub Secret(KAKAO_REFRESH_TOKEN)에 등록하세요.\n")
    print(f"access_token  : {token_data['access_token']}")
    print(f"refresh_token : {token_data['refresh_token']}")
    print(f"만료(초)       : {token_data.get('expires_in')}")
    print(f"refresh 만료(초): {token_data.get('refresh_token_expires_in')}")


if __name__ == "__main__":
    main()
