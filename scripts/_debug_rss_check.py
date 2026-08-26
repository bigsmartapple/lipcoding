"""임시 진단 스크립트: 후보 RSS 피드 URL들이 실제로 응답하는지 확인한다."""
import sys

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

CANDIDATES = [
    "https://www.yna.co.kr/rss/economy.xml",
    "https://www.yna.co.kr/rss/finance.xml",
    "https://www.mk.co.kr/rss/30000001/",
    "https://www.mk.co.kr/rss/50100032/",
    "https://www.hankyung.com/feed/economy",
    "https://www.hankyung.com/feed/finance",
    "http://rss.hankyung.com/economy.xml",
    "https://biz.chosun.com/site/data/rss/rss.xml",
    "https://www.edaily.co.kr/rss/economy.xml",
    "https://www.fnnews.com/rss/r20/fn_realestate_news.xml",
    "https://www.fnnews.com/rss/f_editorial.xml",
    "http://www.asiae.co.kr/rss/economic.xml",
    "https://www.asiae.co.kr/rss/economic.htm",
    "http://biz.heraldcorp.com/rss/",
    "https://biz.heraldcorp.com/rss_all.php",
]

for url in CANDIDATES:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        ctype = resp.headers.get("Content-Type", "")
        snippet = resp.text[:200].replace("\n", " ")
        print(
            f"[DEBUG] url={url} status={resp.status_code} ctype={ctype!r} "
            f"len={len(resp.text)} snippet={snippet!r}",
            file=sys.stderr,
        )
    except requests.RequestException as exc:
        print(f"[DEBUG] url={url} EXCEPTION={exc!r}", file=sys.stderr)
