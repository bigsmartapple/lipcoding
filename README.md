# lipcoding
lipcoding competition

## 카드·금융 카카오톡 아침 브리핑

매일 아침 카드사·금융권 관련 뉴스를 요약해 카카오톡 "나에게 보내기"로 자동 발송하는
GitHub Actions 워크플로우입니다.

- 뉴스 수집: 네이버 뉴스 검색 결과 페이지 크롤링 (카드업계 / 금융권 키워드, API 키 불필요)
- 발송: 카카오 "나에게 보내기" API (`POST /v2/api/talk/memo/default/send`)
- 스케줄: GitHub Actions cron, 매일 08:00 KST

### 1. 카카오 앱 설정 및 refresh_token 발급

1. https://developers.kakao.com 에서 애플리케이션 생성 후 REST API 키 확인
2. [카카오 로그인] 활성화
3. [카카오 로그인 > Redirect URI]에 `http://localhost:8888/oauth` 등록
   (다른 값을 쓰려면 아래 명령의 `--redirect-uri`도 동일하게 지정)
4. [카카오 로그인 > 동의항목]에서 "카카오톡 메시지 전송" 항목 활성화
5. 로컬(본인 PC)에서 아래 명령을 실행해 최초 1회 로그인 동의 후 refresh_token 발급

   ```bash
   pip install -r requirements.txt
   python scripts/get_kakao_token.py --rest-api-key <카카오 REST API 키>
   ```

   브라우저에서 카카오 로그인 동의를 완료하면 터미널에 `refresh_token`이 출력됩니다.

> "나에게 보내기"는 카카오 계정 본인에게만 메시지를 전송합니다. 다른 사람에게 보내려면
> 카카오톡 채널 비즈니스 메시지(알림톡/친구톡) 연동이 별도로 필요합니다.

### 2. GitHub Secrets 등록

저장소 Settings → Secrets and variables → Actions 에 아래 2개를 등록합니다.

| Secret 이름 | 값 |
| --- | --- |
| `KAKAO_REST_API_KEY` | 카카오 앱 REST API 키 |
| `KAKAO_REFRESH_TOKEN` | 1단계에서 발급받은 refresh_token |

### 3. 실행 확인

- 자동 실행: 매일 08:00 KST, `.github/workflows/daily-briefing.yml`
- 수동 실행: GitHub 저장소 Actions 탭 → "Daily Card & Finance Kakao Briefing" → Run workflow
- 로컬 테스트:

  ```bash
  export KAKAO_REST_API_KEY=...
  export KAKAO_REFRESH_TOKEN=...
  cd scripts && python send_daily_briefing.py
  ```

### 참고 사항

- 카카오 refresh_token은 기본적으로 약 2개월 후 만료됩니다. 만료 전 재발급 옵션이
  켜져 있다면 실행 중 새 refresh_token이 발급될 수 있으며, 이 경우 워크플로우 로그에
  경고가 출력됩니다 — `KAKAO_REFRESH_TOKEN` Secret을 새 값으로 업데이트해야 다음 실행이
  정상 동작합니다.
- 기본 text 템플릿은 200자 제한이 있어, 브리핑 내용이 길면 `[1/N]` 형식으로 여러 건으로
  나뉘어 순차 발송됩니다.
- 뉴스 수집은 네이버 검색 결과 페이지(`search.naver.com`)를 크롤링하는 방식이라 API 키가
  필요 없지만, 네이버가 페이지의 HTML 구조를 바꾸면 크롤링이 깨질 수 있습니다. 브리핑이
  계속 "뉴스가 확인되지 않았습니다"로만 온다면 `scripts/fetch_news.py`의 CSS 선택자
  (`a.news_tit`)가 여전히 유효한지 확인하세요.
