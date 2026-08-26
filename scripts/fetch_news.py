"""카드·금융권 뉴스를 주요 언론사 RSS 피드에서 키워드로 필터링해 가져온다.

네이버 뉴스 검색(search.naver.com)은 GitHub Actions 같은 클라우드 서버 IP에서의
요청을 403으로 차단하기 때문에, 대신 언론사가 직접 제공하는 RSS 피드(기계가
읽도록 만들어진 포맷이라 이런 차단이 없다)에서 기사를 모아 카드/금융 키워드로
필터링하는 방식을 사용한다.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# 카드/금융 뉴스가 고르게 섞여 있는 것으로 확인된 경제지 RSS 피드
RSS_FEEDS = [
    "https://www.yna.co.kr/rss/economy.xml",
    "https://www.mk.co.kr/rss/30000001/",
    "https://www.mk.co.kr/rss/50100032/",
]

KST = timezone(timedelta(hours=9))
MAX_ARTICLE_AGE_HOURS = 26
ARTICLES_PER_SECTION = 5

# 카테고리별 제목 필터링 키워드 (먼저 매칭되는 카테고리로 분류)
SECTIONS: dict[str, list[str]] = {
    "카드업계": ["카드사", "카드업계", "신용카드", "체크카드"],
    "금융권": ["금융지주", "시중은행", "금융위원회", "핀테크", "금융권", "저축은행", "은행권"],
}

# 인사/부고/동정 등 브리핑 가치가 낮은 정형 기사 제외
EXCLUDE_KEYWORDS = ["[인사]", "[부고]", "[동정]", "[포토]", "[사진]", "[알림]"]


def _press_name(link: str) -> str:
    try:
        return urlparse(link).netloc.replace("www.", "")
    except ValueError:
        return ""


def _fetch_feed_items(url: str) -> list[dict]:
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_text = item.findtext("pubDate") or ""
        if not title or not link:
            continue

        try:
            pub_date = parsedate_to_datetime(pub_date_text)
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue

        items.append({"title": title, "link": link, "pub_date": pub_date})

    return items


def fetch_briefing_sections() -> dict[str, list[dict]]:
    """카테고리별 최신 카드·금융 뉴스를 반환한다."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_ARTICLE_AGE_HOURS)

    all_items: list[dict] = []
    for feed_url in RSS_FEEDS:
        try:
            all_items.extend(_fetch_feed_items(feed_url))
        except (requests.RequestException, ET.ParseError):
            continue

    sections: dict[str, list[dict]] = {category: [] for category in SECTIONS}
    seen_titles: set[str] = set()

    for item in sorted(all_items, key=lambda a: a["pub_date"], reverse=True):
        title = item["title"]
        if title in seen_titles or item["pub_date"] < cutoff:
            continue
        if any(keyword in title for keyword in EXCLUDE_KEYWORDS):
            continue

        for category, keywords in SECTIONS.items():
            if len(sections[category]) >= ARTICLES_PER_SECTION:
                continue
            if any(keyword in title for keyword in keywords):
                seen_titles.add(title)
                sections[category].append(
                    {
                        "title": title,
                        "link": item["link"],
                        "press": _press_name(item["link"]),
                        "pub_date": item["pub_date"],
                    }
                )
                break

    return sections
