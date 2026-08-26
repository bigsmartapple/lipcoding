"""매일 아침 카드·금융권 뉴스를 요약해 카카오톡 '나에게 보내기'로 전송하는 진입점.

기사마다 실제 기사 URL을 카카오 메시지의 링크로 넣어서, 메시지를 탭하면
해당 언론사 홈페이지가 아니라 그 기사 본문으로 바로 연결되도록 한다.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime

from fetch_news import KST, fetch_briefing_sections
from kakao_client import refresh_access_token, send_text_message

FALLBACK_LINK_URL = "https://finance.naver.com/news/"
SEND_INTERVAL_SECONDS = 1

REQUIRED_ENV_VARS = [
    "KAKAO_REST_API_KEY",
    "KAKAO_REFRESH_TOKEN",
]


def main() -> int:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        print(f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing)}", file=sys.stderr)
        return 1

    rest_api_key = os.environ["KAKAO_REST_API_KEY"]
    refresh_token = os.environ["KAKAO_REFRESH_TOKEN"]

    token_data = refresh_access_token(rest_api_key, refresh_token)
    access_token = token_data["access_token"]

    if token_data.get("refresh_token"):
        print(
            "::warning::카카오 refresh_token이 재발급되었습니다. "
            "GitHub Secret(KAKAO_REFRESH_TOKEN)을 새 값으로 업데이트해야 다음 실행이 정상 동작합니다.",
            file=sys.stderr,
        )

    sections = fetch_briefing_sections()
    today = datetime.now(KST).strftime("%Y-%m-%d")
    total_articles = sum(len(articles) for articles in sections.values())

    header_text = f"📊 카드·금융 브리핑 ({today})"
    if total_articles:
        counts = ", ".join(f"{cat} {len(arts)}건" for cat, arts in sections.items() if arts)
        header_text += f"\n{counts}"
    else:
        header_text += "\n\n오늘은 카드·금융권 주요 뉴스가 확인되지 않았습니다."

    print(header_text)
    send_text_message(access_token, header_text, FALLBACK_LINK_URL, button_title="더보기")
    time.sleep(SEND_INTERVAL_SECONDS)

    for category, articles in sections.items():
        for article in articles:
            press = f" - {article['press']}" if article["press"] else ""
            text = f"[{category}] {article['title']}{press}"
            print(text)
            send_text_message(access_token, text, article["link"])
            time.sleep(SEND_INTERVAL_SECONDS)

    print("카카오톡 브리핑 발송 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
