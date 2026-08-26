"""임시 진단 스크립트: 머니투데이 RSS 안내 페이지 원문 + 추가 후보 확인."""
import sys
import xml.etree.ElementTree as ET

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# 1) 머니투데이 RSS 안내 페이지 원문을 그대로 출력 (실제 피드 URL을 찾기 위해)
try:
    resp = requests.get("https://www.mt.co.kr/mtm/mtm_rss.htm", headers=HEADERS, timeout=8)
    print(f"[DEBUG] mtm_rss.htm status={resp.status_code} len={len(resp.text)}", file=sys.stderr)
    print(f"[DEBUG] mtm_rss.htm BODY_START >>>\n{resp.text[:4000]}\n<<< BODY_END", file=sys.stderr)
except requests.RequestException as exc:
    print(f"[DEBUG] mtm_rss.htm EXCEPTION={exc!r}", file=sys.stderr)

# 2) 다른 언론사 RSS 후보 (구형 URL 패턴, 실제 동작 여부 확인)
CANDIDATES = [
    "http://file.mk.co.kr/news/rss/rss_30000001.xml",
    "http://rss.hankyung.com/economy.xml",
    "http://www.fnnews.com/rss/fn_realnews_all.xml",
    "http://biz.heraldm.com/rss/010100000000.xml",
]

for url in CANDIDATES:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        ctype = resp.headers.get("Content-Type", "")
        print(f"[DEBUG] url={url} status={resp.status_code} ctype={ctype!r} len={len(resp.text)}", file=sys.stderr)
        if resp.status_code == 200:
            try:
                root = ET.fromstring(resp.content)
                items = root.findall(".//item")
                print(f"[DEBUG]   item_count={len(items)}", file=sys.stderr)
                for item in items[:2]:
                    print(f"[DEBUG]     title={item.findtext('title', '')!r}", file=sys.stderr)
            except ET.ParseError as exc:
                print(f"[DEBUG]   PARSE_ERROR={exc!r}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"[DEBUG] url={url} EXCEPTION={exc!r}", file=sys.stderr)
