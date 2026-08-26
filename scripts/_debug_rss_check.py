"""임시 진단 스크립트: 구글 뉴스 RSS로 머니투데이(site:mt.co.kr) 기사 검색이 되는지 확인."""
import sys
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

QUERIES = ["site:mt.co.kr 카드", "site:mt.co.kr 금융", "site:news.mt.co.kr 은행"]

for q in QUERIES:
    url = f"https://news.google.com/rss/search?q={quote(q)}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        ctype = resp.headers.get("Content-Type", "")
        print(f"[DEBUG] q={q!r} status={resp.status_code} ctype={ctype!r} len={len(resp.text)}", file=sys.stderr)
        if resp.status_code == 200:
            try:
                root = ET.fromstring(resp.content)
                items = root.findall(".//item")
                print(f"[DEBUG]   item_count={len(items)}", file=sys.stderr)
                for item in items[:5]:
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    source = item.findtext("source", "")
                    print(f"[DEBUG]     title={title!r} source={source!r} link={link!r}", file=sys.stderr)
            except ET.ParseError as exc:
                print(f"[DEBUG]   PARSE_ERROR={exc!r} snippet={resp.text[:300]!r}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"[DEBUG] q={q!r} EXCEPTION={exc!r}", file=sys.stderr)
