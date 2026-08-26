# lipcoding
lipcoding competition

## 카드·금융 카카오톡 아침 브리핑

매일 아침 카드사·금융권 관련 뉴스를 요약해 카카오톡 "나에게 보내기"로 자동 발송하는
GitHub Actions 워크플로우입니다.

- 뉴스 수집: 연합뉴스·매일경제 RSS 피드 + 머니투데이(구글 뉴스 site: 검색)에서
  카드업계 / 금융권 키워드로 필터링 (API 키 불필요)
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
- 브리핑은 기사 1건당 카카오톡 메시지 1건으로 발송되며, 각 메시지의 링크는 해당
  기사의 실제 URL입니다(모두 같은 링크를 쓰면 카카오톡이 본문 속 언론사 도메인
  텍스트를 자동으로 링크로 인식해 홈페이지로 연결해버리는 문제가 있어, 언론사명은
  도메인이 아닌 한글 이름으로만 표시합니다).
- 뉴스 수집은 연합뉴스·매일경제 RSS 피드(`scripts/fetch_news.py`의 `RSS_FEEDS`)와
  머니투데이(자체 RSS를 HTTP 410로 중단해서, 구글 뉴스 RSS의 `site:mt.co.kr` 검색으로
  대체 — `GOOGLE_NEWS_SITES`)에서 기사를 가져와 제목에 카드/금융 키워드(`SECTIONS`)가
  포함된 것만 골라냅니다. 참고로 네이버 뉴스 검색 페이지(`search.naver.com`)는 GitHub
  Actions 같은 클라우드 서버 IP의 요청을 403으로 차단하기 때문에 크롤링 방식으로는
  사용할 수 없었습니다. 브리핑이 계속 "뉴스가 확인되지 않았습니다"로만 온다면 RSS
  피드 URL이 아직 유효한지, 또는 키워드에 맞는 기사가 최근 26시간 내에 없었는지
  확인하세요.
