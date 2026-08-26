"""임시 진단 스크립트: 머니투데이 후보 RSS URL을 확인한다."""
import sys
import xml.etree.ElementTree as ET

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

CANDIDATES = [
    "https://rss.mt.co.kr/mt_news.xml",
    "https://rss.mt.co.kr/mt_totalnews.xml",
    "https://rss.mt.co.kr/mt_economy.xml",
    "https://www.mt.co.kr/rss/",
    "https://news.mt.co.kr/rss/",
    "http://rss.mt.co.kr/mt_news.xml",
    "https://rss.mt.co.kr/mtview.xml",
    "https://rss.mt.co.kr/mt_stock.xml",
]

for url in CANDIDATES:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        ctype = resp.headers.get("Content-Type", "")
        print(f"[DEBUG] url={url} status={resp.status_code} ctype={ctype!r} len={len(resp.text)}", file=sys.stderr)
        if resp.status_code == 200 and "xml" in ctype.lower():
            try:
                root = ET.fromstring(resp.content)
                items = root.findall(".//item")
                print(f"[DEBUG]   item_count={len(items)}", file=sys.stderr)
                for item in items[:3]:
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    print(f"[DEBUG]     title={title!r} link={link!r}", file=sys.stderr)
            except ET.ParseError as exc:
                print(f"[DEBUG]   PARSE_ERROR={exc!r}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"[DEBUG] url={url} EXCEPTION={exc!r}", file=sys.stderr)
