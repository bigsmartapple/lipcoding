"""카드업계 뉴스를 주요 언론사 RSS 피드와 구글 뉴스 검색에서 키워드로
필터링해 가져온다.

네이버 뉴스 검색(search.naver.com)은 GitHub Actions 같은 클라우드 서버 IP에서의
요청을 403으로 차단하기 때문에, 대신 다음 두 경로에서 기사를 모은다.
1. 언론사가 직접 제공하는 RSS 피드 (연합뉴스, 매일경제 — 기계가 읽도록 만들어진
   포맷이라 이런 차단이 없다)
2. 구글 뉴스 RSS 검색 (키워드별로, 언론사 제한 없이 검색한다)

예전에는 구글 뉴스 검색을 site:mt.co.kr / site:mk.co.kr / site:hankyung.com /
site:heraldcorp.com / site:chosun.com 식으로 특정 언론사에만 제한해서 썼는데,
그 목록에 없는 언론사(예: 이투데이, 파이낸셜투데이, 폴리뉴스 등)가 보도한
기사는 다른 곳에서 전혀 받아 적지 않는 한 계속 누락됐다 — "BC카드, AI
스타트업 피클과 '에이전틱 페이' 기술검증" 기사가 그런 경우였다. 언론사
목록을 하나씩 추가하는 방식은 끝이 없어서, 이제 언론사 제한 없이 키워드만
검색한다. 품질 낮은 언론사나 한 언론사의 중복 보도는 기존 EXCLUDE_KEYWORDS
필터링과 언론사별 상한(`_diversify`)으로 걸러낸다.

한 언론사가 같은 소식을 여러 건(제목만 다르게) 올려서 브리핑 한 카테고리를
독점하는 것을 막기 위해, 언론사별로 최대 MAX_PER_PRESS건까지만 우선 채우고
언론사를 번갈아가며 고른다(`_diversify`). 언론사 제한 없이 검색하게 되면서
여러 언론사가 같은 사건을 제목만 다르게 보도한 기사가 한 브리핑에 함께
뽑히는 경우가 늘었는데, 이는 제목 문자열 유사도로 걸러낸다(`_is_near_duplicate`,
DUPLICATE_TITLE_SIMILARITY_THRESHOLD). 또 어제 이미 보낸 기사가
MAX_ARTICLE_AGE_HOURS(26시간) 안에 다시 걸려 중복 발송되는 것을 막기 위해,
호출하는 쪽(send_daily_briefing.py)이 최근 보낸 기사 제목을 `sent_history`
모듈로 기록해뒀다가 `exclude_titles`로 넘겨준다.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
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

GOOGLE_NEWS_SEARCH_URL = "https://news.google.com/rss/search"

KST = timezone(timedelta(hours=9))
MAX_ARTICLE_AGE_HOURS = 26
ARTICLES_PER_SECTION = 5
# 한 언론사가 같은 카테고리의 슬롯을 이 개수보다 많이 차지하지 못하게 한다
# (단, 다른 언론사에 기사가 없어 슬롯이 남으면 그때는 상한을 넘겨서도 채운다)
MAX_PER_PRESS = 2
# 여러 언론사가 같은 사건을 제목만 다르게 보도하는 경우(예: "KB국민카드,
# 발달장애 청소년 현악단 후원"과 "KB국민카드, 발달장애 청소년 오케스트라
# 'KB 알레그로' 정기연주회 개최") 제목 문자열 유사도로 걸러낸다. 실제로
# 같은 사건을 다룬 제목 쌍은 0.57~0.82, 같은 회사의 서로 다른 사건은
# 0.17~0.48 수준으로 나와 0.55를 기준으로 나뉜다(0.6으로는 "KB국민카드,
# 'KB 알레그로'로 발달장애 청소년 무대 경험 지원"과 "KB국민카드, 발달장애
# 청소년 오케스트라 정기공연"처럼 공통 고유명사 없이 겹치는 쌍(0.57)을
# 놓쳐서 낮췄다).
DUPLICATE_TITLE_SIMILARITY_THRESHOLD = 0.55

# 같은 사건인데 두 언론사가 제목 구조를 완전히 다르게 써서(예: "KB국민카드
# 후원 'KB 알레그로', 제2회 정기연주회 성료"와 "KB국민카드, 발달장애
# 청소년 오케스트라 'KB 알레그로' 개최") 문자열 유사도가 낮게 나오는
# 경우가 있다. 이런 경우에도 행사/상품명처럼 따옴표로 묶인 고유명사는
# 그대로 반복되는 경우가 많아, 같은 카드사 키워드를 공유하면서 따옴표
# 안의 문구도 일치하면 같은 사건으로 보고 중복 처리한다(일반 명사는
# 보통 짧게 끝나므로 2자 이상만 본다).
QUOTE_PATTERN = re.compile(r"['‘’\"“”`]([^'‘’\"“”`]{2,})['‘’\"“”`]")

# 카테고리별 제목 필터링 키워드 (먼저 매칭되는 카테고리로 분류)
# 실제 기사 제목은 보통 정식 사명을 쓰기 때문에("KB카드"가 아니라 "KB국민카드",
# "NH카드"가 아니라 "NH농협카드") 약칭만 쓰면 대부분의 기사를 놓친다 — 정식
# 사명에 포함되는 부분 문자열로 맞춰야 한다.
SECTIONS: dict[str, list[str]] = {
    "카드업계": [
        "카드사",
        "카드업계",
        "신용카드",
        "체크카드",
        "국민카드",
        "삼성카드",
        "현대카드",
        "신한카드",
        "롯데카드",
        "하나카드",
        "우리카드",
        "농협카드",
        "비씨카드",
        "BC카드",
        "카카오페이카드",
    ],
}

_ALL_SECTION_KEYWORDS = [kw for kws in SECTIONS.values() for kw in kws]


def _shared_brand_keyword(a: str, b: str) -> bool:
    """두 제목이 같은 카드사 키워드를 공유하는지 본다(따옴표 문구 중복 판단에 쓴다)."""
    return any(kw in a and kw in b for kw in _ALL_SECTION_KEYWORDS)

# 인사/부고/동정 등 브리핑 가치가 낮은 정형 기사 + 원치 않는 주제(저축은행) +
# "신용카드"가 들어간다는 이유만으로 걸려드는 불법 신용카드 현금화 광고 +
# 카드사가 스폰서로만 등장하는 스포츠 행사 기사(카드업계 동향이 아님) 제외
EXCLUDE_KEYWORDS = [
    "[인사]",
    "[부고]",
    "[동정]",
    "[포토]",
    "[사진]",
    "[알림]",
    # 매일경제가 스포츠 현장 기사에 붙이는 섹션 태그. 우리카드 여자배구단 관련
    # 기사가 매번 다른 종목/포지션 용어를 써서 개별 단어 추가로는 끝까지 못
    # 막았는데, 이 태그는 거의 항상 함께 붙어 있어 더 안정적인 신호다.
    "[MK현장]",
    "저축은행",
    "현금화",
    "카드깡",
    "정보이용료",
    "테니스",
    "당구",
    "PBA",
    "마라톤",
    "골프",
    "축구",
    "야구",
    "농구",
    "배구",
    "핸드볼",
    "컬링",
    "스포츠단",
    "e스포츠",
    # 기사 제목이 종목명 대신 리그/협회 약칭만 쓰는 경우가 많아 약칭도 함께 제외한다
    # (예: 우리카드 V-리그 배구단 기사는 "배구" 없이 "KOVO"만 쓰는 경우가 흔함)
    "KOVO",
    "V리그",
    "KBL",
    "KBO",
    "K리그",
    # 종목명이나 리그 약칭 없이 "리그 경기" 같은 일반 표현만 쓰는 기사도 있어
    # (예: 우리카드 여자배구단 경기 기사가 "배구"/"V리그" 없이 "리그 경기"라고만
    # 쓰는 경우) 일반적인 "리그"라는 단어 자체를 제외한다. 금융/카드업계 기사에서
    # "리그"가 쓰일 일은 거의 없어 안전하다.
    "리그",
    # 연예인 개인 일화/방송 예능 소재 기사에 "카드사"가 우연히 언급되는 경우가 있어
    # (예: 게임 결제 중 카드사 도난 문자를 받은 연예인 비하인드 토크 기사) 제외한다.
    "현질",
    # 카드사가 운영하는 프로 스포츠단(예: 우리카드 여자배구단) 기사가 "배구"
    # 같은 종목명 없이 중계/선수단 용어만 쓰는 경우가 있어 함께 제외한다.
    "응원중계",
    "공격수",
    "드래프트",
    "사령탑",
    "선수단",
    "쾌승",
    "세터",
    "개막전",
    "역전승",
    # 기사 섹션 태그가 언론사마다 달라서(예: "[MK현장]", "[장충리뷰]", "[장충 현장]")
    # 태그 하나씩 쫓아가는 방식은 끝이 없다 — 대신 우리카드 홈경기장인 "장충체육관"의
    # 줄임말 "장충" 자체를 제외한다. 카드업계 기사에는 거의 쓰이지 않는 단어다.
    "장충",
    # 언론사 제한 없이 검색하게 되면서(언론사 목록 제한 폐지) 스포츠 전문
    # 매체(예: 스포츠타임스)의 경기 기사까지 들어오기 시작했다 — 이런 매체는
    # 자체 섹션 태그와 경기 결과 표현을 또 다르게 쓴다(예: "[게임노트] '리누스
    # 41점 맹활약' KB손해보험, 우리카드에 3-2 승리로 시즌 첫 승"). 아래
    # EXCLUDE_PRESS_KEYWORDS가 이런 매체를 언론사명으로 걸러내는 더 안정적인
    # 방법이라, 제목 쪽은 참고용으로만 남겨둔다.
    "[게임노트]",
    "맹활약",
    # "감독"은 스포츠팀 감독 기사뿐 아니라 "금융감독원"(정식 금융 규제기관명)에도
    # 들어가는 글자라 EXCLUDE_KEYWORDS에 넣지 않는다 — 넣으면 금융감독원 관련
    # 정상적인 카드업계 기사까지 함께 걸러진다.
    # 게임 커뮤니티(예: 인벤)의 자유게시판/잡담 글이 "체크카드" 같은 단어를
    # 우연히 포함해 매칭되는 경우가 있다(예: "[잡담] 체크카드 새로 받았는데
    # 이쁘다"). "[잡담]"은 뉴스가 아니라 커뮤니티 게시판 글임을 나타내는
    # 태그라 통째로 제외한다.
    "[잡담]",
]

# 언론사 제한 없이 검색하게 되면서 스포츠/연예 전문 매체(예: 스포츠타임스,
# 데일리스포츠한국, 톱스타뉴스, 당구 전문지 빌리어즈)나 뉴스 매체가 아닌
# 게임 커뮤니티(예: 인벤)의 글까지 들어온다. 이런 곳은 글마다 표현이 다
# 달라서 제목 키워드로는 끝없이 쫓아가야 하는데, 매체명 자체에
# "스포츠"/"스타"/"빌리어즈"/"인벤" 같은 표시가 있어 매체명으로 거르는
# 게 훨씬 안정적이다. 카드사가 스폰서인 당구 선수단 경기 기사("NH농협카드
# 투톱의 희비…정수빈은 8강행")가 "빌리어즈"를, 게임 커뮤니티 잡담 글
# ("[잡담] 체크카드 새로 받았는데 이쁘다")이 "인벤"을 추가한 계기였다.
# 카드업계 관련 정상 언론사 중에는 이런 표현이 들어간 이름이 없다.
EXCLUDE_PRESS_KEYWORDS = ["스포츠", "톱스타", "빌리어즈", "인벤"]

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


def _fetch_google_news_keyword_items(keyword: str) -> list[dict]:
    """구글 뉴스 RSS에서 언론사 제한 없이 키워드로 기사를 검색한다.

    구글 뉴스가 <pubDate>에 실제 최초 발행일이 아니라 최근 재색인/재노출
    시점을 넣어주는 경우가 있어(예: 2023~2024년 보도자료가 오늘 날짜로
    둔갑해 들어온 적이 있다), "when:2d" 연산자로 구글 자체의 최신성 판단을
    한 번 더 걸어 오래된 기사가 섞여 들어올 여지를 줄인다. 이후 코드의
    pub_date 기준 cutoff 필터링과 이중으로 걸린다.
    """
    query = f"{keyword} when:2d"
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

        # 언론사를 site:로 제한하지 않으므로, 파비콘에 쓸 host는 실제 기사
        # 링크에서 직접 뽑아야 한다(예전에는 site 파라미터를 그대로 썼다).
        host = _host_of(link)
        items.append({"title": title, "link": link, "press": press, "host": host, "pub_date": pub_date})

    return items


def _quoted_phrases(title: str) -> set[str]:
    return {m.strip() for m in QUOTE_PATTERN.findall(title)}


def _is_near_duplicate(title: str, existing_titles: list[str]) -> bool:
    """제목이 이미 선정된 기사들 중 하나와 사실상 같은 사건을 다룬 것인지 본다."""
    title_quotes = _quoted_phrases(title)
    for other in existing_titles:
        if SequenceMatcher(None, title, other).ratio() >= DUPLICATE_TITLE_SIMILARITY_THRESHOLD:
            return True
        if title_quotes and _shared_brand_keyword(title, other) and title_quotes & _quoted_phrases(other):
            return True
    return False


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
    rss_ok = rss_fail = 0
    for feed_url in RSS_FEEDS:
        try:
            all_items.extend(_fetch_feed_items(feed_url))
            rss_ok += 1
        except (requests.RequestException, ET.ParseError) as e:
            rss_fail += 1
            print(f"[뉴스 수집] RSS 피드 실패: {feed_url} ({e})")

    google_ok = google_fail = 0
    for keywords in SECTIONS.values():
        for keyword in keywords:
            try:
                all_items.extend(_fetch_google_news_keyword_items(keyword))
                google_ok += 1
            except (requests.RequestException, ET.ParseError) as e:
                google_fail += 1
                print(f"[뉴스 수집] 구글 뉴스 검색 실패: keyword={keyword} ({e})")

    raw_count = len(all_items)
    matched_count = 0
    excluded_by_history = 0
    excluded_as_duplicate = 0

    candidates: dict[str, list[dict]] = {category: [] for category in SECTIONS}
    seen_titles: set[str] = set()

    for item in sorted(all_items, key=lambda a: a["pub_date"], reverse=True):
        title = item["title"]
        if title in seen_titles or item["pub_date"] < cutoff:
            continue
        if any(keyword in title for keyword in EXCLUDE_KEYWORDS):
            continue
        if any(keyword in item["press"] for keyword in EXCLUDE_PRESS_KEYWORDS):
            continue

        for category, keywords in SECTIONS.items():
            if any(keyword in title for keyword in keywords):
                matched_count += 1
                seen_titles.add(title)
                if title in exclude_titles:
                    excluded_by_history += 1
                    break
                if _is_near_duplicate(title, [c["title"] for c in candidates[category]]):
                    excluded_as_duplicate += 1
                    break
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

    sections = {category: _diversify(items) for category, items in candidates.items()}
    final_count = sum(len(items) for items in sections.values())
    print(
        f"[뉴스 수집] RSS {rss_ok}/{rss_ok + rss_fail}건 + 구글뉴스 {google_ok}/{google_ok + google_fail}건 "
        f"쿼리 성공 → 원본 기사 {raw_count}건 / 카테고리 매칭 {matched_count}건 / "
        f"발송 이력 제외 {excluded_by_history}건 / 중복 기사 제외 {excluded_as_duplicate}건 / "
        f"최종 선정 {final_count}건"
    )
    return sections
