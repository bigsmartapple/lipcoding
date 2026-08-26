"""임시 진단 스크립트: 머니투데이 RSS 후보 마지막 확인."""
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
    "https://www.mt.co.kr/rss/mt_news.xml",
    "https://www.mt.co.kr/rss/economy.xml",
    "https://news.mt.co.kr/rss.xml",
    "https://www.mt.co.kr/rss/rss.html",
    "https://www.mt.co.kr/sitemap.xml",
]

for url in CANDIDATES:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
        ctype = resp.headers.get("Content-Type", "")
        print(
            f"[DEBUG] url={url} final_url={resp.url} status={resp.status_code} "
            f"ctype={ctype!r} len={len(resp.text)}",
            file=sys.stderr,
        )
        if resp.status_code == 200 and ("xml" in ctype.lower() or resp.text.lstrip().startswith("<?xml")):
            try:
                root = ET.fromstring(resp.content)
                items = root.findall(".//item")
                print(f"[DEBUG]   item_count={len(items)} root_tag={root.tag!r}", file=sys.stderr)
                for item in items[:2]:
                    print(f"[DEBUG]     title={item.findtext('title', '')!r}", file=sys.stderr)
            except ET.ParseError as exc:
                print(f"[DEBUG]   PARSE_ERROR={exc!r} snippet={resp.text[:300]!r}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"[DEBUG] url={url} EXCEPTION={exc!r}", file=sys.stderr)
