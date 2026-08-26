"""매일 아침 카드·금융권 뉴스를 요약해 카카오톡 '나에게 보내기'로 전송하는 진입점."""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime

from fetch_news import KST, fetch_briefing_sections
from kakao_client import refresh_access_token, send_briefing

DEFAULT_LINK_URL = "https://finance.naver.com/news/"

REQUIRED_ENV_VARS = [
    "KAKAO_REST_API_KEY",
    "KAKAO_REFRESH_TOKEN",
    "NAVER_CLIENT_ID",
    "NAVER_CLIENT_SECRET",
]


def build_briefing_text(sections: dict[str, list[dict]], today: str) -> str:
    lines = [f"📊 카드·금융 브리핑 ({today})", ""]
    has_articles = False

    for category, articles in sections.items():
        if not articles:
            continue
        has_articles = True
        lines.append(f"■ {category}")
        for idx, article in enumerate(articles, 1):
            press = f" - {article['press']}" if article["press"] else ""
            lines.append(f"{idx}. {article['title']}{press}")
        lines.append("")

    if not has_articles:
        lines.append("오늘은 카드·금융권 주요 뉴스가 확인되지 않았습니다.")

    return "\n".join(lines).strip()


def main() -> int:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        print(f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing)}", file=sys.stderr)
        return 1

    rest_api_key = os.environ["KAKAO_REST_API_KEY"]
    refresh_token = os.environ["KAKAO_REFRESH_TOKEN"]
    naver_client_id = os.environ["NAVER_CLIENT_ID"]
    naver_client_secret = os.environ["NAVER_CLIENT_SECRET"]

    token_data = refresh_access_token(rest_api_key, refresh_token)
    access_token = token_data["access_token"]

    if token_data.get("refresh_token"):
        print(
            "::warning::카카오 refresh_token이 재발급되었습니다. "
            "GitHub Secret(KAKAO_REFRESH_TOKEN)을 새 값으로 업데이트해야 다음 실행이 정상 동작합니다.",
            file=sys.stderr,
        )

    sections = fetch_briefing_sections(naver_client_id, naver_client_secret)
    today = datetime.now(KST).strftime("%Y-%m-%d")
    briefing_text = build_briefing_text(sections, today)

    print(briefing_text)

    send_briefing(access_token, briefing_text, DEFAULT_LINK_URL)
    time.sleep(1)

    print("카카오톡 브리핑 발송 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
