"""카카오 '나에게 보내기' API 연동 (액세스 토큰 갱신 + 메시지 발송)."""
from __future__ import annotations

import json
import sys

import requests

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_MEMO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

# 카카오 기본 text 템플릿의 text 필드는 최대 200자까지 표시된다.
TEXT_TEMPLATE_LIMIT = 200
# list 템플릿의 header_title / 각 content title 권장 길이
LIST_HEADER_LIMIT = 60
LIST_TITLE_LIMIT = 60
# 실제 발송 테스트로 확인된, list 템플릿 한 메시지에 들어가는 항목 최대 개수
MAX_LIST_CONTENTS = 3


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


def _send_template(access_token: str, template_object: dict) -> dict:
    """template_object를 카카오 '나에게 보내기' API로 전송한다.

    실패 시 카카오가 돌려준 에러 본문을 stderr에 출력해 원인을 바로
    알 수 있게 한다 (그냥 raise_for_status만 하면 상태 코드만 남는다).
    """
    resp = requests.post(
        KAKAO_MEMO_SEND_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template_object, ensure_ascii=False)},
        timeout=10,
    )
    if not resp.ok:
        print(f"[ERROR] 카카오 메시지 발송 실패: status={resp.status_code} body={resp.text}", file=sys.stderr)
    resp.raise_for_status()
    return resp.json()


def send_text_message(access_token: str, text: str, link_url: str, button_title: str = "기사 보기") -> dict:
    """카카오톡 '나에게 보내기'로 기본 text 템플릿 메시지를 전송한다."""
    template_object = {
        "object_type": "text",
        "text": text[:TEXT_TEMPLATE_LIMIT],
        "link": {"web_url": link_url, "mobile_web_url": link_url},
        "button_title": button_title,
    }
    return _send_template(access_token, template_object)


def send_list_message(
    access_token: str,
    header_title: str,
    header_link: str,
    contents: list[dict],
    button_title: str = "더보기",
) -> dict:
    """카카오톡 '나에게 보내기'로 list 템플릿 메시지를 전송한다.

    contents 각 항목은 {"title", "description", "image_url", "link"} 키를 가지며,
    항목별로 서로 다른 link를 지정할 수 있어 기사마다 실제 URL로 연결된다.
    contents가 MAX_LIST_CONTENTS를 넘으면 앞에서부터 잘라 보낸다 — 호출하는
    쪽에서 미리 청크로 나눠 여러 메시지로 보내야 전체 항목이 누락되지 않는다.
    """
    contents = contents[:MAX_LIST_CONTENTS]
    template_object = {
        "object_type": "list",
        "header_title": header_title[:LIST_HEADER_LIMIT],
        "header_link": {"web_url": header_link, "mobile_web_url": header_link},
        "contents": [
            {
                "title": item["title"][:LIST_TITLE_LIMIT],
                "description": item.get("description", ""),
                "image_url": item["image_url"],
                "image_width": 64,
                "image_height": 64,
                "link": {"web_url": item["link"], "mobile_web_url": item["link"]},
            }
            for item in contents
        ],
        "button_title": button_title,
    }
    return _send_template(access_token, template_object)
