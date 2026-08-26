"""카드·금융권 뉴스를 네이버 뉴스 검색 API에서 수집한다."""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests

NAVER_NEWS_SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"

# 카테고리별 검색 키워드
SECTIONS: dict[str, list[str]] = {
    "카드업계": ["카드사", "신용카드업계", "카드업계"],
    "금융권": ["금융지주", "시중은행", "금융위원회", "핀테크"],
}

ARTICLES_PER_SECTION = 5
MAX_ARTICLE_AGE_HOURS = 26
KST = timezone(timedelta(hours=9))


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def _press_name(link: str) -> str:
    try:
        host = urlparse(link).netloc
    except ValueError:
        return ""
    return host.replace("www.", "")


def _search_naver_news(keyword: str, client_id: str, client_secret: str, display: int = 10) -> list[dict]:
    resp = requests.get(
        NAVER_NEWS_SEARCH_URL,
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
        params={"query": keyword, "display": display, "sort": "date"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def fetch_briefing_sections(naver_client_id: str, naver_client_secret: str) -> dict[str, list[dict]]:
    """카테고리별 최신 카드·금융 뉴스를 반환한다."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_ARTICLE_AGE_HOURS)

    sections: dict[str, list[dict]] = {}
    for category, keywords in SECTIONS.items():
        seen_titles: set[str] = set()
        collected: list[dict] = []

        for keyword in keywords:
            try:
                items = _search_naver_news(keyword, naver_client_id, naver_client_secret)
            except requests.RequestException:
                continue

            for item in items:
                title = _strip_html(item.get("title", ""))
                if not title or title in seen_titles:
                    continue

                try:
                    pub_date = parsedate_to_datetime(item.get("pubDate", ""))
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    continue

                if pub_date < cutoff:
                    continue

                link = item.get("originallink") or item.get("link", "")
                seen_titles.add(title)
                collected.append(
                    {
                        "title": title,
                        "link": link,
                        "press": _press_name(link),
                        "pub_date": pub_date,
                    }
                )

        collected.sort(key=lambda a: a["pub_date"], reverse=True)
        sections[category] = collected[:ARTICLES_PER_SECTION]

    return sections
