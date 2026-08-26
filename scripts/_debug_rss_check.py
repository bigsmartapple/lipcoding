"""임시 진단 스크립트: 유효한 RSS 피드의 실제 기사 구조를 확인한다."""
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
    "https://www.yna.co.kr/rss/economy.xml",
    "https://www.mk.co.kr/rss/30000001/",
    "https://www.mk.co.kr/rss/50100032/",
]

for url in CANDIDATES:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        print(f"[DEBUG] url={url} item_count={len(items)}", file=sys.stderr)
        for item in items[:6]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            category = item.findtext("category", "")
            print(
                f"[DEBUG]   title={title!r} category={category!r} pubDate={pub_date!r} link={link!r}",
                file=sys.stderr,
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[DEBUG] url={url} EXCEPTION={exc!r}", file=sys.stderr)
