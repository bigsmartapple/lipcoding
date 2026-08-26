"""카카오 '나에게 보내기' API 연동 (액세스 토큰 갱신 + 메시지 발송)."""
from __future__ import annotations

import json

import requests

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_MEMO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

# 카카오 기본 text 템플릿의 text 필드는 최대 200자까지 표시된다.
TEXT_TEMPLATE_LIMIT = 200
# 실제 전송 전 [i/N] 같은 접두어가 붙을 여유를 남겨둔다.
CHUNK_SAFETY_LIMIT = 180


def refresh_access_token(rest_api_key: str, refresh_token: str) -> dict:
    """리프레시 토큰으로 새 액세스 토큰을 발급받는다.

    응답에 refresh_token이 포함되면 만료가 임박해 재발급된 것이므로,
    호출한 쪽에서 새 값을 저장(예: GitHub Secret 갱신)해야 한다.
    """
    resp = requests.post(
        KAKAO_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def send_text_message(access_token: str, text: str, link_url: str, button_title: str = "뉴스 더보기") -> dict:
    """카카오톡 '나에게 보내기'로 기본 text 템플릿 메시지를 전송한다."""
    template_object = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": link_url, "mobile_web_url": link_url},
        "button_title": button_title,
    }
    resp = requests.post(
        KAKAO_MEMO_SEND_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template_object, ensure_ascii=False)},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def split_into_chunks(text: str, limit: int = CHUNK_SAFETY_LIMIT) -> list[str]:
    """줄 단위로 text를 limit 이하의 조각으로 나눈다."""
    lines = text.split("\n")
    chunks: list[str] = []
    current = ""

    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit and current:
            chunks.append(current)
            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks or [text[:limit]]


def send_briefing(access_token: str, full_text: str, link_url: str) -> None:
    """긴 브리핑 텍스트를 여러 메시지로 나누어 순서대로 전송한다."""
    raw_chunks = split_into_chunks(full_text)
    total = len(raw_chunks)

    for idx, chunk in enumerate(raw_chunks, 1):
        prefix = f"[{idx}/{total}]\n" if total > 1 else ""
        message = f"{prefix}{chunk}"[:TEXT_TEMPLATE_LIMIT]
        send_text_message(access_token, message, link_url)
