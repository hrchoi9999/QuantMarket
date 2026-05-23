QS 요청 제출처: QS-Master
권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
공개 반영 포함 여부: Yes
Admin only 여부: No
관련 시스템: QuantMarket

# 시장 분석 메뉴 1차 탭형 페이지 반영 요청

## 목적
- redbot.co.kr 상단 메뉴에 `시장 분석` 메뉴를 추가합니다.
- 1차에서는 `시장 분석` 페이지를 탭 구조로 구성해,
  현재 QuantMarket이 제공 중인 데이터들을 성격별로 나누어 보여줍니다.

## 운영 방향
- `시장 브리핑`: 해석형 요약 페이지
- `시장 분석`: 데이터/차트형 상세 페이지

이번 1차에서는 `시장 브리핑`을 바로 홈으로 합치지 말고 유지합니다.
우선 `시장 분석` 페이지를 탭 구조로 오픈한 뒤,
실제 정보량과 사용성을 본 다음 홈 통합 여부를 2차로 검토하는 방향을 권장합니다.

## 1차 탭 구성 요청

### 탭 1. 시장 상태
- 상태점수 timeline
- trend / breadth / risk / defensive_flow 차트
- 상태 전이 요약

사용 payload:
- `quantservice_market_timeline.json`
- `quantservice_market_timeline_history.json`
- `quantservice_market_state_transition.json`
- `quantservice_market_state_transition_history.json`

### 탭 2. 자산 강도
- 자산군 상대강도
- 최근 20일 수익률 비교
- 강도 순위 변화

사용 payload:
- `quantservice_market_asset_strength.json`
- `quantservice_market_asset_strength_history.json`

### 탭 3. 장중/야간 참고
- 오늘 장중 흐름
- 장중 futures / flow 참고
- 내일 시장 전망 참고

사용 payload:
- 기존 public `state_intraday_bridge`
- `quantservice_market_next_day_preview.json`
- `quantservice_market_next_day_preview_history.json`

### 탭 4. 데이터 해설
- 지표 의미 설명
- source 설명
- official / proxy / fallback 구분
- 비자문 안내

## UI 원칙
- 한 페이지에 모든 정보를 길게 쌓기보다 탭으로 구분
- 40~60대 사용자도 보기 쉽게 제목/범례/축 라벨을 명확히 표시
- `시장 브리핑`과 `시장 분석`의 역할이 혼동되지 않게 구성
- 장중 데이터와 종가 데이터는 시각적으로 분리

## 2차 검토 방향
- `시장 분석` 탭 구조가 안정화되고 정보량이 충분해지면
- 기존 `시장 브리핑`을 홈 첫 화면에서 바로 보이게 하는 구조로 재정리할지 검토

## 참고 문서
- `D:\\QuantMarket\\docs\\QUANTMARKET_MARKET_ANALYSIS_PHASE1_TABS_PLAN_20260429.md`

## 완료 기준
- 상단 메뉴에 `시장 분석` 추가
- `시장 분석` 페이지에 4개 탭이 보임
- QuantMarket history/current payload 기반 차트가 정상 렌더링됨
- `시장 브리핑`은 당분간 유지됨
- 향후 홈 통합 판단이 가능하도록 정보 구조가 정리됨
