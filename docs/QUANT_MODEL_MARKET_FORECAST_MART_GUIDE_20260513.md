# QuantMarket Market Forecast Mart Guide

작성일: 2026-05-13

## 목적

QuantMarket이 생산하는 국내 시장 context, 글로벌 매크로 context, 위험/수급 context를 종합해 Quant 모델 AI 학습에서 바로 사용할 수 있는 시장전망 feature mart를 제공한다.

이 mart는 공개 웹 문구나 투자자문성 전망이 아니라, Quant 모델의 종목/ETF/AI overlay 학습에 투입하기 위한 정량 feature다.

## 제공 위치

- DB: `D:\QuantMarket\data\db\market_context.db`
- 테이블: `market_forecast_daily`
- CSV current: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_forecast_daily_current.csv`
- Manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`
- Schema: `D:\QuantMarket\service_platform\ai_training\market_context\current\schema.json`
- Coverage report: `D:\QuantMarket\reports\market_context_mart\ai_training_market_context_mart_coverage_latest.json`

## Key

- Primary key: `asof_date + market_scope + forecast_horizon`
- Join key: `asof_date + market_scope + forecast_horizon`
- `market_scope`: `ALL`, `KOSPI`, `KOSDAQ`
- `forecast_horizon`: `1d`, `5d`, `20d`

## 핵심 필드

- `market_forecast_score`: 시장전망 score. 높을수록 시장 환경이 우호적이다.
- `market_forecast_label`: `bullish`, `mild_bullish`, `neutral`, `mild_bearish`, `bearish`
- `risk_regime_label`: `risk_on_high`, `risk_on_moderate`, `neutral`, `risk_off_moderate`, `risk_off_high`
- `expected_volatility_score`: 높을수록 변동성 부담이 크다.
- `drawdown_risk_score`: 높을수록 하락/낙폭 위험이 크다.
- `upside_participation_score`: 높을수록 추세와 breadth 참여도가 좋다.
- `confidence_score`: 0~1. 입력 feature 완성도와 signal 강도 기준 신뢰도다.

## Baseline 구성 요소

- 국내 시장 상태: `baseline_market_state_score`
- 추세: `baseline_trend_score`
- breadth: `baseline_breadth_score`
- risk-on: `baseline_risk_on_score`
- risk-off: `baseline_risk_off_score`
- 글로벌 위험선호: `baseline_global_risk_on_score`
- 외부 매크로 부담: `baseline_external_macro_pressure_score`
- 수급/스마트머니: `baseline_smart_money_score`

## Horizon별 해석

- `1d`: 단기 시장 편향. 수급, 외부위험, risk-off 부담을 상대적으로 더 반영한다.
- `5d`: 1주 단위 균형 전망. 추세, breadth, 위험 환경을 균형 있게 반영한다.
- `20d`: 월간/스윙 성격 전망. 추세와 breadth 비중이 상대적으로 높다.

## 현재 모델 버전

- Forecast model version: `qm_market_forecast_baseline_v0.1_20260513`
- Mart schema version: `ai_market_context_mart.v1.2`
- Mart feature version: `qm_ai_market_context_features.v1.3`

## 주의 사항

- 현재 버전은 outcome-trained AI 모델이 아니라 baseline score-combination forecast mart다.
- 이후 실제 1d/5d/20d forward return과 비교해 supervised learning 또는 calibration layer를 추가할 수 있다.
- 결측값은 null로 유지한다. Quant 모델 쪽에서 임의로 0 대체하지 않는 것을 권장한다.
- 더 엄격한 point-in-time 학습이 필요하면 `asof_date` 기준 1거래일 lag 정책을 적용한다.

