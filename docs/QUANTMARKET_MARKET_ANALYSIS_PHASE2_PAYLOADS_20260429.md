# QuantMarket 시장 분석 2차 Payload 정리

작성일: 2026-04-29

## 목적
- `시장 분석` 메뉴 2차 확장을 위해
- QS가 바로 사용할 수 있는 추가 public payload를 QuantMarket 쪽에서 먼저 준비한다.

## 이번 라운드 구현 범위

### 1. KRX 지수 패널
- 파일
  - `quantservice_market_index_panel.json`
  - `api_v1_market_analysis_index_panel.json`
- 내용
  - KOSPI / KOSDAQ / KOSPI200
  - ret_1d / ret_5d / ret_20d / ret_60d
  - realized_vol_20d
  - drawdown_20d
  - source / source_tier

### 2. breadth 상세 패널
- 파일
  - `quantservice_market_breadth_detail.json`
  - `api_v1_market_analysis_breadth_detail.json`
  - `quantservice_market_breadth_detail_history.json`
  - `api_v1_market_analysis_breadth_detail_history.json`
- 내용
  - 종가 기준 breadth
    - above_20dma_ratio
    - above_60dma_ratio
    - adv_dec_ratio
    - new_high_count
    - new_low_count
    - breadth_universe_count
    - breadth_regime_label
  - 최신 장중 breadth
    - KOSPI
    - KOSDAQ
    - advancers / decliners / flat_count
    - positive_ratio
    - source / source_tier
  - history
    - 종가 breadth 시계열
    - 장중 breadth 시계열
    - close_series / intraday_series 분리 제공

### 3. 미국/글로벌 매크로 패널
- 파일
  - `quantservice_market_us_macro_panel.json`
  - `api_v1_market_analysis_us_macro_panel.json`
  - `quantservice_market_us_macro_panel_history.json`
  - `api_v1_market_analysis_us_macro_panel_history.json`
- 내용
  - 미국 상장 한국 ETF
  - S&P500 선물
  - 나스닥100 선물
  - USD/KRW
  - WTI
  - 미국 10년 금리
  - next-day preview headline 연계
  - history
    - asset별 overnight 시계열
    - next-day preview 요약 시계열
    - asset_series / preview_series 분리 제공

### 4. DART 공시 요약 계약 payload
- 파일
  - `quantservice_market_dart_summary.json`
  - `api_v1_market_analysis_dart_summary.json`
  - `quantservice_market_dart_summary_history.json`
  - `api_v1_market_analysis_dart_summary_history.json`
- 현재 상태
  - `enabled=true`
  - `status_label=정상`
  - OpenDART `list.json` 기반 실제 공시 요약이 연결됨
  - 최근 기준일 공시 건수 / 유형별 건수 / 리스크 공시 / highlights 제공
  - history payload는 `reference_date` 기준 최신 요약만 일자별로 정리

## 운영 판단

### 바로 공개 가능한 것
- index panel
- breadth detail
- us macro panel

### 아직 수집기 연결이 더 필요한 것
- 업종 rotation
- 투자자별 세부 수급 history

## 비고
- 이번 2차는 새 인증 없이 현재 QuantMarket DB에 이미 쌓이는 데이터만으로 우선 확장했다.
- DART 수집기는 이번 라운드에서 연결되었고, breadth / us macro도 차트형 history payload까지 확장되었다.
