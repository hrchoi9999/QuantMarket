# QuantMarket 시장 분석 메뉴 서비스 구상안

작성일: 2026-04-29  
관련 시스템: QuantMarket / QuantService(redbot.co.kr)

## 1. 목적

redbot.co.kr 상단 메뉴에 `시장 분석` 메뉴를 추가하고,
기존 `시장 브리핑`의 요약형 설명을 넘어
시장 데이터 자체를 표와 그래프로 보여주는 데이터 열람형 서비스를 구성한다.

핵심 방향은 다음과 같다.

- `시장 브리핑`은 해석형 요약 서비스로 유지
- `시장 분석`은 데이터/차트 중심 서비스로 별도 분리
- 공개형 비자문 원칙 유지
- KRX / DART / Naver / 미국시장 데이터 소스를 신뢰도에 따라 계층화
- QM은 canonical payload를 생산하고 QS는 UI 렌더링만 담당

## 2. 서비스 역할 분리

### 시장 브리핑
- 현재 시장 상태를 짧게 요약
- 퀀트모델 시장 흐름 / 오늘 장중 흐름 / 내일 시장 전망 참고
- 설명형 문구와 상태 해석 중심

### 시장 분석
- 원천 데이터와 시계열 변화를 보여주는 페이지
- 사용자가 직접 숫자와 그래프를 보고 판단 재료를 얻는 영역
- 요약 해설은 최소화하고 데이터 설명과 chart guide를 제공

## 3. `시장 분석` 메뉴의 권장 화면 구조

### A. 상단 개요 바
- 기준 시각
- 시장 구분: KR / US
- 데이터 상태: 장중 / 장마감 / 야간 참고
- 출처 배지: KRX / DART / Naver / US official / proxy

### B. 시장 상태 차트 섹션
- 상태점수 timeline chart
- component score stacked/line chart
  - trend
  - breadth
  - risk
  - defensive_flow
- 상태 전이 이력 chart

### C. 자산 강도 섹션
- KOSPI / KOSDAQ / USDKRW / GOLD / BOND / INVERSE 상대강도 chart
- 최근 20일 수익률 표
- strength rank heatmap

### D. KRX 시장 데이터 섹션
- KOSPI / KOSDAQ / KOSPI200 지수
- 상승/하락 종목 수
- 20일선/60일선 위 종목 비율
- 장중/종가 기준 변동성
- 외국인/기관/프로그램 흐름 요약

### E. DART 공시 흐름 섹션
- 최근 공시 건수
- 유형별 공시 비중
  - 실적
  - 유상증자/CB/BW
  - 자사주
  - 최대주주/지분변동
  - 투자위험 관련 공시
- 공시 이벤트 heat table

### F. Naver/Naver proxy 섹션
- KRX 장중 breadth 보조지표
- 네이버 금융 기반 상승/하락 종목 집계
- 업종별 강세/약세 지도

### G. 미국시장 연계 섹션
- S&P500 / NASDAQ / Dow / Russell
- 미국 10년 금리
- 달러인덱스 또는 USDKRW 연결 환율
- WTI / Gold
- 야간 선물 및 next-day preview 연결

### H. 하단 주의사항 / 데이터 해석 안내
- 본 정보는 공개 데이터 정리 서비스
- 개별 투자자문 아님
- 일부 장중 데이터는 proxy/fallback일 수 있음

## 4. 데이터 출처 계층

### KR 공식 우선
- KRX 지수/파생/기본 시장 데이터
- DART 공시

### KR 보조
- Naver 금융 breadth / 업종 / 장중 보조 정보

### US/Global
- Yahoo/FRED/기타 공식 또는 준공식 공개 데이터
- 미국시장 확장 시 source tier 명시 필요

## 5. QM이 이미 제공 가능한 데이터

현재 QuantMarket은 아래 canonical payload를 이미 생산 중이다.

- `quantservice_market_timeline.json`
- `quantservice_market_asset_strength.json`
- `quantservice_market_state_transition.json`
- `quantservice_market_next_day_preview.json`
- `quantservice_market_timeline_history.json`
- `quantservice_market_asset_strength_history.json`
- `quantservice_market_state_transition_history.json`
- `quantservice_market_next_day_preview_history.json`

즉 `시장 분석` 메뉴 1차의 핵심 차트 뼈대는 이미 상당 부분 공급 가능하다.

## 6. QM에서 추가로 개발하면 좋은 데이터

### 1차 우선
- KRX index panel payload
  - KOSPI / KOSDAQ / KOSPI200
  - ret_1d / ret_5d / ret_20d / ret_60d
  - realized_vol_20d / drawdown_20d
- breadth detail payload
  - advancers
  - decliners
  - flat_count
  - adv_dec_ratio
  - above_20dma_ratio
  - above_60dma_ratio
- DART event summary payload
  - asof
  - filing_count_total
  - filing_count_by_type
  - risk_event_count
- US macro panel payload
  - sp500_ret
  - nasdaq_ret
  - us10y_change
  - dxy_or_usdkrw_change
  - oil_change
  - gold_change

### 2차 확장
- 업종 rotation history
- 수급 flow history
- DART issuer-level clustering
- macro event calendar / FOMC/CPI/실적 시즌 표시

## 7. 권장 payload 묶음

### 기존 재사용
- `timeline_history`
- `asset_strength_history`
- `state_transition_history`
- `next_day_preview_history`

### 신규 권장
- `quantservice_market_index_panel.json`
- `quantservice_market_breadth_detail.json`
- `quantservice_market_dart_summary.json`
- `quantservice_market_us_macro_panel.json`

## 8. 공개 운영 원칙

- 숫자는 raw ratio 유지, QS에서 display 변환
- timestamp는 KST ISO8601 고정
- source tier 명시
  - official
  - official_delayed
  - proxy
  - fallback
- 장중 데이터와 종가 데이터는 시각적으로 구분
- `시장 브리핑`과 `시장 분석`을 혼동하지 않도록 copy 분리

## 9. 권장 구현 순서

### Phase 1
- QS 메뉴 추가: `시장 분석`
- 기존 history payload를 사용한 차트 페이지 오픈
- timeline / asset strength / state transition / next-day preview chart 구성

### Phase 2
- QM 신규 payload 추가
  - index panel
  - breadth detail
  - DART summary
  - US macro panel

### Phase 3
- 업종/수급/공시 확장
- KR / US 전환 UI 정교화

## 10. 결론

이 서비스는 `시장 브리핑`의 대체가 아니라,
그 아래에 깔린 원천 데이터와 시계열을 보여주는 `데이터 열람형 시장 분석 메뉴`로 가는 것이 가장 적절하다.

즉,

- `시장 브리핑`: 해석형
- `시장 분석`: 차트/데이터형

으로 이원화하는 구조가 redbot.co.kr 전체 정보 구조상 가장 자연스럽다.
