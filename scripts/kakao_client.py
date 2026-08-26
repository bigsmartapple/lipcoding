"""카카오 '나에게 보내기' API 연동 (액세스 토큰 갱신 + 메시지 발송)."""
from __future__ import annotations

import json

import requests

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_MEMO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

# 카카오 기본 text 템플릿의 text 필드는 최대 200자까지 표시된다.
TEXT_TEMPLATE_LIMIT = 200


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


def send_text_message(access_token: str, text: str, link_url: str, button_title: str = "기사 보기") -> dict:
    """카카오톡 '나에게 보내기'로 기본 text 템플릿 메시지를 전송한다.

    link_url이 각 기사의 실제 URL이어야, 메시지에 붙는 버튼/링크가 해당 기사로
    바로 연결된다 (모든 메시지에 같은 링크를 쓰면 그 링크로만 연결된다).
    """
    template_object = {
        "object_type": "text",
        "text": text[:TEXT_TEMPLATE_LIMIT],
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
