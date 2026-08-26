"""카드·금융권 뉴스를 네이버 뉴스 검색 결과 페이지에서 크롤링한다.

API 키가 필요한 네이버 검색 오픈 API 대신, 별도 인증 없이 접근 가능한
https://search.naver.com/search.naver?where=news 페이지를 파싱한다.

주의: 네이버가 검색 결과 페이지의 HTML 마크업(클래스명 등)을 바꾸면 크롤링이
깨질 수 있다. 브리핑이 계속 "뉴스가 확인되지 않았습니다"로만 오면 가장 먼저
_search_naver_news()의 CSS 선택자(a.news_tit)가 여전히 유효한지 확인한다.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

NAVER_NEWS_SEARCH_URL = "https://search.naver.com/search.naver"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

KST = timezone(timedelta(hours=9))
MAX_ARTICLE_AGE_HOURS = 26

# 카테고리별 검색 키워드
SECTIONS: dict[str, list[str]] = {
    "카드업계": ["카드사", "신용카드업계", "카드업계"],
    "금융권": ["금융지주", "시중은행", "금융위원회", "핀테크"],
}

ARTICLES_PER_SECTION = 5
RESULTS_PER_KEYWORD = 15

_RELATIVE_TIME_RE = re.compile(r"(\d+)\s*(분|시간|일)\s*전")
_ABSOLUTE_DATE_RE = re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})\.")


def _press_name(link: str) -> str:
    try:
        return urlparse(link).netloc.replace("www.", "")
    except ValueError:
        return ""


def _parse_published_at(info_text: str, now: datetime) -> datetime | None:
    """검색 결과에 표시되는 "3시간 전" / "2026.08.26." 형태의 시각 텍스트를 파싱한다."""
    match = _RELATIVE_TIME_RE.search(info_text)
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        delta = {
            "분": timedelta(minutes=amount),
            "시간": timedelta(hours=amount),
            "일": timedelta(days=amount),
        }[unit]
        return now - delta

    match = _ABSOLUTE_DATE_RE.search(info_text)
    if match:
        year, month, day = (int(group) for group in match.groups())
        return datetime(year, month, day, tzinfo=KST)

    return None


def _search_naver_news(keyword: str, now: datetime) -> list[dict]:
    resp = requests.get(
        NAVER_NEWS_SEARCH_URL,
        params={"where": "news", "query": keyword, "sort": "1"},
        headers=REQUEST_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    articles = []
    for link_tag in soup.select("a.news_tit")[:RESULTS_PER_KEYWORD]:
        title = html.unescape(link_tag.get("title") or link_tag.get_text(strip=True))
        link = link_tag.get("href", "")
        if not title or not link:
            continue

        info_container = link_tag.find_parent(["div", "li"])
        info_text = info_container.get_text(" ", strip=True) if info_container else ""

        articles.append(
            {
                "title": title,
                "link": link,
                "published_at": _parse_published_at(info_text, now),
            }
        )

    return articles


def fetch_briefing_sections() -> dict[str, list[dict]]:
    """카테고리별 최신 카드·금융 뉴스를 반환한다."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_ARTICLE_AGE_HOURS)

    sections: dict[str, list[dict]] = {}
    for category, keywords in SECTIONS.items():
        seen_titles: set[str] = set()
        collected: list[dict] = []

        for keyword in keywords:
            try:
                items = _search_naver_news(keyword, now)
            except requests.RequestException:
                continue

            for item in items:
                title = item["title"]
                if title in seen_titles:
                    continue

                published_at = item["published_at"]
                if published_at is None or published_at < cutoff:
                    continue

                seen_titles.add(title)
                collected.append(
                    {
                        "title": title,
                        "link": item["link"],
                        "press": _press_name(item["link"]),
                        "pub_date": published_at,
                    }
                )

        collected.sort(key=lambda a: a["pub_date"], reverse=True)
        sections[category] = collected[:ARTICLES_PER_SECTION]

    return sections
