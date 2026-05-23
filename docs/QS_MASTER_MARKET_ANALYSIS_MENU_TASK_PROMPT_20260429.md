QS 요청 제출처: QS-Master
권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
공개 반영 포함 여부: Yes
Admin only 여부: No
관련 시스템: QuantMarket

# redbot `시장 분석` 메뉴 1차 반영 요청

## 목적
- redbot.co.kr 상단 메뉴에 `시장 분석` 메뉴를 추가합니다.
- 기존 `시장 브리핑`과 별도로, 시장 데이터를 표와 차트 중심으로 보여주는 공개형 데이터 열람 페이지를 구성합니다.

## 역할 구분
- `시장 브리핑`: 해석형 요약
- `시장 분석`: 데이터/차트형 상세

## 1차 반영 범위
- 새 상단 메뉴: `시장 분석`
- 차트 중심 1차 페이지 구성
- QuantMarket이 이미 제공 중인 history payload를 우선 사용

## QM에서 현재 제공 가능한 payload
- `quantservice_market_timeline_history.json`
- `quantservice_market_asset_strength_history.json`
- `quantservice_market_state_transition_history.json`
- `quantservice_market_next_day_preview_history.json`

공개 URL base 예시:
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/history/...`

## 권장 페이지 섹션

### 1. 상단 개요
- 기준 시각
- 시장 구분
- 데이터 상태
- 데이터 출처 안내

### 2. 시장 상태 차트
- 상태점수 timeline
- trend / breadth / risk / defensive_flow component score chart

### 3. 자산 강도 차트
- 주요 자산군 상대강도
- 최근 20일 수익률 비교

### 4. 상태 전이 차트
- 최근 상태 변화 이력
- stability / transition count 참고

### 5. 내일 시장 전망 참고 차트
- overnight preview history
- 야간 자산 변동률

## UI 원칙
- `시장 브리핑`보다 데이터/그래프 중심으로 설계
- 과도한 해석 문구보다 source / 시각 / 범례 / 단위 안내를 강화
- 모바일에서는 차트를 세로 스택
- 데스크톱에서는 2열 배치 가능

## copy 원칙
- 공개형 참고 정보
- 비자문 원칙 유지
- 장중 / 종가 / 야간 참고를 구분해서 표시

## 참고
- QuantMarket 내부 설계 메모:
  - `D:\\QuantMarket\\docs\\QUANTMARKET_MARKET_ANALYSIS_MENU_SERVICE_PLAN_20260429.md`

## 완료 기준
- redbot 상단 메뉴에 `시장 분석`이 추가됨
- history payload 기반 차트 3~4개가 정상 렌더링됨
- `시장 브리핑`과 역할이 혼동되지 않음
- 공개형 비자문 표시 원칙이 유지됨
