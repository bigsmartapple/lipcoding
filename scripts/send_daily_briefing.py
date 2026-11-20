"""매일 아침 카드업계 뉴스를 요약해 카카오톡 '나에게 보내기'로 전송하는 진입점.

카테고리별로 list 템플릿 메시지를 보내며, 메시지 안의 기사 항목마다 실제 기사
URL을 링크로 넣어서 항목을 탭하면 그 기사로 바로 연결되게 한다. list 템플릿은
한 메시지에 MAX_LIST_CONTENTS(3)개까지만 들어가므로, 그보다 많으면 여러
메시지로 나눠 보낸다. 반대로 항목이 1개뿐이면 카카오가 400 에러를 내므로
그런 경우엔 text 템플릿으로 대체한다.

카카오 메시지의 link(web_url)는 카카오 개발자 콘솔 [앱 설정 > 플랫폼 > Web
도메인]에 등록된 도메인으로만 정상 동작한다. fetch_news가 더 이상 언론사를
site:로 제한하지 않고 검색하기 때문에, 구글 뉴스가 돌려주는 기사 링크는
이제 등록되지 않은 도메인일 수도 있다 — 그런 링크를 그대로 보내면 카카오가
오류를 내거나 링크가 열리지 않을 수 있어, 등록된 도메인이 아니면 안전한
기본 링크(FALLBACK_LINK_URL)로 대체한다(`_safe_link`). 새 언론사의 도메인을
안정적으로 쓰려면 그 도메인을 Web 도메인에 등록하고 KNOWN_LINK_DOMAINS에도
추가해야 한다.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from urllib.parse import urlencode, urlparse

from fetch_news import KST, SECTIONS, fetch_briefing_sections
from kakao_client import MAX_LIST_CONTENTS, refresh_access_token, send_list_message, send_text_message
from sent_history import load_history, record_sent, save_history

# 카카오 콘솔 Web 도메인에 등록된 도메인이어야 링크가 정상 동작한다.
FALLBACK_LINK_URL = "https://www.yna.co.kr"
GOOGLE_NEWS_SEARCH_PAGE = "https://news.google.com/search"

# 카카오 콘솔 [앱 설정 > 플랫폼 > Web 도메인]에 등록돼 있는 것으로 확인된
# 도메인들. 기사 링크의 도메인이 이 목록에 없으면 FALLBACK_LINK_URL로
# 대체한다 — 등록 안 된 도메인 링크를 그대로 보내면 카카오 발송이 실패하거나
# 링크가 열리지 않을 수 있기 때문이다.
KNOWN_LINK_DOMAINS = {
    "yna.co.kr",
    "mk.co.kr",
    "mt.co.kr",
    "hankyung.com",
    "heraldcorp.com",
    "chosun.com",
}


def _safe_link(link: str) -> str:
    host = urlparse(link).netloc.replace("www.", "")
    return link if host in KNOWN_LINK_DOMAINS else FALLBACK_LINK_URL


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

    history = load_history()
    sections = fetch_briefing_sections(exclude_titles=set(history.keys()))
    today = datetime.now(KST).strftime("%Y-%m-%d")
    total_articles = sum(len(articles) for articles in sections.values())

    if not total_articles:
        text = f"📊 카드업계 브리핑 ({today})\n\n오늘은 카드업계 주요 뉴스가 확인되지 않았습니다."
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
            header_title = f"📊 카드업계 브리핑 ({today}){page}"
            contents = [
                {
                    "title": article["title"],
                    "description": article["press"],
                    "image_url": article["icon_url"],
                    "link": _safe_link(article["link"]),
                }
                for article in chunk
            ]
            print(header_title)
            for article in chunk:
                print(f"  - {article['title']} ({article['press']})")

            if len(chunk) == 1:
                # 카카오 list 템플릿은 항목이 1개면 400 에러를 낸다(2개 이상 필요).
                # 이런 경우엔 text 템플릿으로 그 기사 링크를 바로 보낸다.
                article = chunk[0]
                text = f"{header_title}\n{article['title']} ({article['press']})"
                send_text_message(access_token, text, _safe_link(article["link"]))
            else:
                send_list_message(access_token, header_title, more_link, contents, button_title="관련기사 더보기")

    sent_titles = [article["title"] for articles in sections.values() for article in articles]
    save_history(record_sent(history, sent_titles))

    print("카카오톡 브리핑 발송 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
