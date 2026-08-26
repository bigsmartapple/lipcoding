"""매일 아침 카드·금융권 뉴스를 요약해 카카오톡 '나에게 보내기'로 전송하는 진입점.

카테고리별로 list 템플릿 메시지를 보내며, 메시지 안의 기사 항목마다 실제 기사
URL을 링크로 넣어서 항목을 탭하면 그 기사로 바로 연결되게 한다. list 템플릿은
한 메시지에 MAX_LIST_CONTENTS(3)개까지만 들어가므로, 그보다 많으면 여러
메시지로 나눠 보낸다.

카카오 메시지의 link(web_url)는 카카오 개발자 콘솔 [앱 설정 > 플랫폼 > Web
도메인]에 등록된 도메인으로만 정상 동작한다. RSS_FEEDS/GOOGLE_NEWS_SITES에
새 언론사를 추가하면 그 도메인도 Web 도메인에 등록해야 링크가 열린다.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from urllib.parse import urlencode

from fetch_news import KST, SECTIONS, fetch_briefing_sections
from kakao_client import MAX_LIST_CONTENTS, refresh_access_token, send_list_message, send_text_message

# 카카오 콘솔 Web 도메인에 등록된 도메인이어야 링크가 정상 동작한다.
FALLBACK_LINK_URL = "https://www.yna.co.kr"
GOOGLE_NEWS_SEARCH_PAGE = "https://news.google.com/search"


def _category_more_link(category: str) -> str:
    """"더보기" 버튼이 그 카테고리 관련 기사를 더 볼 수 있는 구글 뉴스 검색 결과로 가게 한다."""
    query = " OR ".join(SECTIONS[category])
    params = urlencode({"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    return f"{GOOGLE_NEWS_SEARCH_PAGE}?{params}"

REQUIRED_ENV_VARS = [
    "KAKAO_REST_API_KEY",
    "KAKAO_REFRESH_TOKEN",
]


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


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

    if not total_articles:
        text = f"📊 카드·금융 브리핑 ({today})\n\n오늘은 카드·금융권 주요 뉴스가 확인되지 않았습니다."
        print(text)
        send_text_message(access_token, text, FALLBACK_LINK_URL, button_title="더보기")
        print("카카오톡 브리핑 발송 완료")
        return 0

    for category, articles in sections.items():
        if not articles:
            continue

        more_link = _category_more_link(category)
        chunks = _chunk(articles, MAX_LIST_CONTENTS)
        for idx, chunk in enumerate(chunks, 1):
            page = f" [{idx}/{len(chunks)}]" if len(chunks) > 1 else ""
            header_title = f"📊 카드·금융 브리핑 ({today}) · {category}{page}"
            contents = [
                {
                    "title": article["title"],
                    "description": article["press"],
                    "image_url": article["icon_url"],
                    "link": article["link"],
                }
                for article in chunk
            ]
            print(header_title)
            for article in chunk:
                print(f"  - {article['title']} ({article['press']})")

            send_list_message(access_token, header_title, more_link, contents, button_title="관련기사 더보기")

    print("카카오톡 브리핑 발송 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
