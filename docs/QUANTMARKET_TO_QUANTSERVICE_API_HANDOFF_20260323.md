# QuantMarket -> QuantService integration note

## 목표

QuantMarket의 최종 산출물은 QuantService가 그대로 읽어 API 응답으로 노출하고,
웹 페이지의 적정 슬롯에 연결할 수 있어야 한다.

## 현재 반영 내용

- QuantMarket snapshot은 단순 저장 파일이 아니라 API response shape와 1:1 대응되도록 유지한다.
- `market_analysis_manifest.json` 에 아래 정보를 포함한다.
  - 제공 endpoint 규격
  - QuantService 소비 대상
  - 페이지별 권장 slot mapping
- API-ready snapshot 파일도 함께 생성한다.
  - `api_v1_market_analysis_summary.json`
  - `api_v1_market_analysis_detail.json`
  - `api_v1_market_analysis_today_bridge.json`

## QuantService 연동 가이드

QuantService adapter/backend는 아래 파일을 읽어 각각의 endpoint 응답으로 사용하면 된다.

- `/api/v1/market-analysis/summary?market=KR`
  - source: `api_v1_market_analysis_summary.json`
- `/api/v1/market-analysis/detail?market=KR`
  - source: `api_v1_market_analysis_detail.json`
- `/api/v1/market-analysis/today-bridge?market=KR`
  - source: `api_v1_market_analysis_today_bridge.json`

## 페이지 권장 연결

- 메인 홈 hero: summary
- 메인 홈 핵심 신호: summary.top_signals
- 오늘의 추천 bridge: today_bridge
- 시장 분석 헤더: detail.state
- 시장 분석 컴포넌트 카드: detail.components
- 시장 분석 긍정/주의 신호: detail.positive_points / detail.warning_points

## 원칙

- 계산 책임은 QuantMarket
- 포트폴리오 계산은 Quant
- 렌더링 책임은 QuantService
- QuantService는 수치를 재계산하지 않고, QuantMarket API/snapshot을 전달/표시만 한다.
