# QuantMarket 회신: Market Forecast Mart 1차 제공

Quant 모델이 QuantMarket의 시장전망 feature를 직접 소비할 수 있도록 `market_forecast_daily`를 1차 구축했습니다.

## 제공 경로

- DB: `D:\QuantMarket\data\db\market_context.db`
- 테이블: `market_forecast_daily`
- CSV: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_forecast_daily_current.csv`
- Manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`
- Schema: `D:\QuantMarket\service_platform\ai_training\market_context\current\schema.json`
- Coverage report: `D:\QuantMarket\reports\market_context_mart\ai_training_market_context_mart_coverage_latest.json`
- Guide: `D:\QuantMarket\docs\QUANT_MODEL_MARKET_FORECAST_MART_GUIDE_20260513.md`

## 생성 결과

- row count: 20,601
- start date: 2017-01-02
- end date: 2026-05-12
- duplicate key count: 0
- primary key: `asof_date + market_scope + forecast_horizon`
- market_scope: `ALL`, `KOSPI`, `KOSDAQ`
- forecast_horizon: `1d`, `5d`, `20d`

## 제공 필드 요약

- `market_forecast_score`: 높을수록 시장 환경 우호
- `market_forecast_label`: `bullish`, `mild_bullish`, `neutral`, `mild_bearish`, `bearish`
- `risk_regime_label`: 위험선호/위험회피 국면
- `expected_volatility_score`: 변동성 부담
- `drawdown_risk_score`: 하락/낙폭 위험
- `upside_participation_score`: 추세와 breadth 참여도
- `confidence_score`: 입력 feature 완성도와 signal 강도 기준 신뢰도

## 소비 방식

Quant 모델에서는 종목 feature에 아래 기준으로 조인하면 됩니다.

`asof_date + market_scope + forecast_horizon`

예를 들어 단기 모델은 `forecast_horizon='5d'`, 월간 리밸런싱 모델은 `forecast_horizon='20d'`를 우선 테스트하는 방식을 권장합니다.

## 현재 버전의 성격

현재 `market_forecast_daily`는 outcome-trained AI 모델이 아니라 baseline score-combination forecast mart입니다.

다음 단계에서는 실제 forward return과 비교해 예측 성능을 검증하고, 필요하면 AI calibration layer를 추가하는 방식으로 고도화하면 됩니다.

