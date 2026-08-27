"""매일 아침 카드·금융권 뉴스를 요약해 카카오톡 '나에게 보내기'로 전송하는 진입점.

카드업계·금융권을 합쳐 최신순으로 최대 3건만 골라 하나의 list 템플릿 메시지로
보낸다 (카카오 list 템플릿은 실제로 2~3개 항목만 안정적으로 동작한다 — 1개면
400 에러, 4개 이상이면 카카오가 임의로 3개까지만 보여준다). 각 항목은 실제
기사 URL로 연결된다.

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

REQUIRED_ENV_VARS = [
    "KAKAO_REST_API_KEY",
    "KAKAO_REFRESH_TOKEN",
]


def _more_link() -> str:
    """"더보기" 버튼이 카드·금융 관련 기사를 더 볼 수 있는 구글 뉴스 검색 결과로 가게 한다."""
    all_keywords = [kw for keywords in SECTIONS.values() for kw in keywords]
    query = " OR ".join(all_keywords)
    params = urlencode({"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    return f"{GOOGLE_NEWS_SEARCH_PAGE}?{params}"


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

    articles = [
        {**article, "category": category} for category, arts in sections.items() for article in arts
    ]
    articles.sort(key=lambda a: a["pub_date"], reverse=True)
    top_articles = articles[:MAX_LIST_CONTENTS]

    header_title = f"📊 카드·금융 브리핑 ({today})"

    if not top_articles:
        text = f"{header_title}\n\n오늘은 카드·금융권 주요 뉴스가 확인되지 않았습니다."
        print(text)
        send_text_message(access_token, text, FALLBACK_LINK_URL, button_title="더보기")
        print("카카오톡 브리핑 발송 완료")
        return 0

    print(header_title)
    for article in top_articles:
        print(f"  - [{article['category']}] {article['title']} ({article['press']})")

    if len(top_articles) == 1:
        # 카카오 list 템플릿은 항목이 1개면 400 에러를 낸다(2개 이상 필요).
        article = top_articles[0]
        text = f"{header_title}\n[{article['category']}] {article['title']} ({article['press']})"
        send_text_message(access_token, text, article["link"])
    else:
        contents = [
            {
                "title": f"[{article['category']}] {article['title']}",
                "description": article["press"],
                "image_url": article["icon_url"],
                "link": article["link"],
            }
            for article in top_articles
        ]
        send_list_message(access_token, header_title, _more_link(), contents, button_title="관련기사 더보기")

    print("카카오톡 브리핑 발송 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
