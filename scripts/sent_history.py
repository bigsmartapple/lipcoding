"""여러 날에 걸쳐 같은 기사가 중복 발송되지 않도록, 최근 보낸 기사 제목을 기록한다.

fetch_news.MAX_ARTICLE_AGE_HOURS(26시간) 때문에 어제 보낸 기사가 오늘 다시
수집 대상에 들어올 수 있어서, 최근 며칠간 보낸 기사 제목을 저장소의 JSON
파일에 남겨두고 다음 실행에서 걸러낸다. GitHub Actions 러너는 매번 새로
초기화되므로, 이 파일은 워크플로우가 실행 후 커밋해서 저장소에 남겨야
다음 실행에서도 이어서 참조할 수 있다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "sent_history.json"
RETENTION_DAYS = 3


def load_history() -> dict[str, str]:
    """제목 -> 보낸 시각(ISO) 기록을 읽는다. 보관 기간이 지난 항목은 뺀다."""
    if not HISTORY_PATH.exists():
        return {}
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return _prune(data)


def record_sent(history: dict[str, str], titles: list[str]) -> dict[str, str]:
    """방금 보낸 기사 제목들을 history에 추가하고, 보관 기간이 지난 항목은 뺀 결과를 반환한다."""
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = dict(history)
    for title in titles:
        updated[title] = now_iso
    return _prune(updated)


def save_history(history: dict[str, str]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _prune(history: dict[str, str]) -> dict[str, str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    pruned = {}
    for title, sent_at in history.items():
        try:
            sent_dt = datetime.fromisoformat(sent_at)
        except ValueError:
            continue
        if sent_dt >= cutoff:
            pruned[title] = sent_at
    return pruned
