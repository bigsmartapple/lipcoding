"""카드업계 뉴스를 주요 언론사 RSS 피드에서 키워드로 필터링해 가져온다.

네이버 뉴스 검색(search.naver.com)은 GitHub Actions 같은 클라우드 서버 IP에서의
요청을 403으로 차단하기 때문에, 대신 다음 두 경로에서 기사를 모은다.
1. 언론사가 직접 제공하는 RSS 피드 (연합뉴스, 매일경제 — 기계가 읽도록 만들어진
   포맷이라 이런 차단이 없다)
2. 구글 뉴스 RSS의 site: 검색 (머니투데이는 자체 RSS 서비스를 중단(HTTP 410)해서
   대체 수단으로, 매일경제는 자체 RSS 카테고리에 카드/금융 키워드 기사가 없는
   날을 보완하기 위해, 한국경제·헤럴드경제·조선일보는 자체 RSS가 없거나 접근이
   막혀 있어 대체 수단으로 각각 site:mt.co.kr / site:mk.co.kr /
   site:hankyung.com / site:heraldcorp.com / site:chosun.com으로 검색해 가져온다)

한 언론사가 같은 소식을 여러 건(제목만 다르게) 올려서 브리핑 한 카테고리를
독점하는 것을 막기 위해, 언론사별로 최대 MAX_PER_PRESS건까지만 우선 채우고
언론사를 번갈아가며 고른다(`_diversify`). 또 어제 이미 보낸 기사가
MAX_ARTICLE_AGE_HOURS(26시간) 안에 다시 걸려 중복 발송되는 것을 막기 위해,
호출하는 쪽(send_daily_briefing.py)이 최근 보낸 기사 제목을 `sent_history`
모듈로 기록해뒀다가 `exclude_titles`로 넘겨준다.
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

# 자체 RSS가 없는 언론사는 구글 뉴스 site: 검색으로 대체한다
GOOGLE_NEWS_SEARCH_URL = "https://news.google.com/rss/search"
GOOGLE_NEWS_SITES = ["mt.co.kr", "mk.co.kr", "hankyung.com", "heraldcorp.com", "chosun.com"]

KST = timezone(timedelta(hours=9))
MAX_ARTICLE_AGE_HOURS = 26
ARTICLES_PER_SECTION = 5
# 한 언론사가 같은 카테고리의 슬롯을 이 개수보다 많이 차지하지 못하게 한다
# (단, 다른 언론사에 기사가 없어 슬롯이 남으면 그때는 상한을 넘겨서도 채운다)
MAX_PER_PRESS = 2

# 카테고리별 제목 필터링 키워드 (먼저 매칭되는 카테고리로 분류)
SECTIONS: dict[str, list[str]] = {
    "카드업계": [
        "카드사",
        "카드업계",
        "신용카드",
        "체크카드",
        "KB카드",
        "삼성카드",
        "현대카드",
        "신한카드",
        "롯데카드",
        "하나카드",
        "우리카드",
        "농협카드",
        "NH카드",
        "비씨카드",
        "카카오페이카드",
    ],
}

# 인사/부고/동정 등 브리핑 가치가 낮은 정형 기사 + 원치 않는 주제(저축은행) +
# "신용카드"가 들어간다는 이유만으로 걸려드는 불법 신용카드 현금화 광고 제외
EXCLUDE_KEYWORDS = [
    "[인사]",
    "[부고]",
    "[동정]",
    "[포토]",
    "[사진]",
    "[알림]",
    "저축은행",
    "현금화",
    "카드깡",
    "정보이용료",
]

# 카카오톡은 메시지 본문에 도메인 형태 문자열(예: yna.co.kr)이 있으면 자동으로
# 링크로 인식해 우리가 지정한 기사 링크 대신 그 도메인의 홈페이지로 연결해버린다.
# 그래서 언론사명은 도메인이 아니라 한글 이름으로 표시한다.
PRESS_NAME_BY_HOST = {
    "yna.co.kr": "연합뉴스",
    "mk.co.kr": "매일경제",
}


def _host_of(link: str) -> str:
    try:
        return urlparse(link).netloc.replace("www.", "")
    except ValueError:
        return ""


def _press_name(host: str) -> str:
    return PRESS_NAME_BY_HOST.get(host, "")


def _icon_url(host: str) -> str:
    """list 템플릿은 항목마다 image_url이 필수라서, 언론사 파비콘을 아이콘으로 쓴다."""
    return f"https://www.google.com/s2/favicons?sz=64&domain={host}"


def _fetch_feed_items(url: str) -> list[dict]:
    """언론사 자체 RSS 피드에서 기사를 가져온다."""
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

        host = _host_of(link)
        items.append(
            {
                "title": title,
                "link": link,
                "press": _press_name(host),
                "host": host,
                "pub_date": pub_date,
            }
        )

    return items


def _fetch_google_news_site_items(site: str, keyword: str) -> list[dict]:
    """구글 뉴스 RSS에서 특정 사이트(site:)와 키워드로 기사를 검색한다."""
    query = f"site:{site} {keyword}"
    resp = requests.get(
        GOOGLE_NEWS_SEARCH_URL,
        params={"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
        headers=REQUEST_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        press = (item.findtext("source") or "").strip()
        pub_date_text = item.findtext("pubDate") or ""
        if not title or not link:
            continue

        # 구글 뉴스는 제목 끝에 " - 언론사명"을 붙이는데, 원문 제목에 이미
        # 언론사명이 붙어있으면 중복으로 두 번 붙는 경우가 있어 모두 제거한다.
        if press:
            suffix = f" - {press}"
            while title.endswith(suffix):
                title = title[: -len(suffix)].strip()

        try:
            pub_date = parsedate_to_datetime(pub_date_text)
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue

        items.append({"title": title, "link": link, "press": press, "host": site, "pub_date": pub_date})

    return items


def _diversify(items: list[dict]) -> list[dict]:
    """한 언론사가 슬롯을 독점하지 않도록 언론사별로 최대 MAX_PER_PRESS건까지
    먼저 채우고 번갈아가며 고른다. items는 최신순으로 정렬돼 있다고 가정한다.
    1차 라운드로 채우고도 슬롯이 남으면(다른 언론사에 기사가 없는 경우) 2차
    라운드에서 상한 없이 나머지를 채운다.
    """
    by_press: dict[str, list[dict]] = {}
    order: list[str] = []
    for item in items:
        key = item["press"] or "기타"
        if key not in by_press:
            by_press[key] = []
            order.append(key)
        by_press[key].append(item)

    selected: list[dict] = []
    counts: dict[str, int] = {key: 0 for key in order}

    for cap in (MAX_PER_PRESS, ARTICLES_PER_SECTION):
        progressed = True
        while len(selected) < ARTICLES_PER_SECTION and progressed:
            progressed = False
            for key in order:
                if len(selected) >= ARTICLES_PER_SECTION:
                    break
                if not by_press[key] or counts[key] >= cap:
                    continue
                selected.append(by_press[key].pop(0))
                counts[key] += 1
                progressed = True

    return selected


def fetch_briefing_sections(exclude_titles: set[str] | None = None) -> dict[str, list[dict]]:
    """카테고리별 최신 카드업계 뉴스를 반환한다.

    exclude_titles에 담긴 제목의 기사는 (이미 발송된 것으로 보고) 제외한다.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_ARTICLE_AGE_HOURS)
    exclude_titles = exclude_titles or set()

    all_items: list[dict] = []
    for feed_url in RSS_FEEDS:
        try:
            all_items.extend(_fetch_feed_items(feed_url))
        except (requests.RequestException, ET.ParseError):
            continue

    for site in GOOGLE_NEWS_SITES:
        for keywords in SECTIONS.values():
            for keyword in keywords:
                try:
                    all_items.extend(_fetch_google_news_site_items(site, keyword))
                except (requests.RequestException, ET.ParseError):
                    continue

    candidates: dict[str, list[dict]] = {category: [] for category in SECTIONS}
    seen_titles: set[str] = set()

    for item in sorted(all_items, key=lambda a: a["pub_date"], reverse=True):
        title = item["title"]
        if title in seen_titles or title in exclude_titles or item["pub_date"] < cutoff:
            continue
        if any(keyword in title for keyword in EXCLUDE_KEYWORDS):
            continue

        for category, keywords in SECTIONS.items():
            if any(keyword in title for keyword in keywords):
                seen_titles.add(title)
                candidates[category].append(
                    {
                        "title": title,
                        "link": item["link"],
                        "press": item["press"],
                        "icon_url": _icon_url(item["host"]),
                        "pub_date": item["pub_date"],
                    }
                )
                break

    return {category: _diversify(items) for category, items in candidates.items()}
