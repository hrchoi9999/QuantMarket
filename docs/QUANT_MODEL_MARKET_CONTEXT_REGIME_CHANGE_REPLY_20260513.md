# QuantMarket Market Context 국면 변화 Feature 보강 회신

- 작성일: 2026-05-13
- 대상: Quant 모델 쓰레드
- 목적: 시장 상태의 절대 레벨뿐 아니라 개선/둔화/전환/안정성 정보를 AI 학습 feature로 제공

## 완료 사항

최종 소비용 wide mart `market_model_input_daily`에 backward-looking 국면 변화 feature를 추가했습니다.

## 갱신 버전

- schema_version: `market_model_input_daily.v4`
- feature_version: `qm_market_model_input_features.v4_regime_change_20260513`

## 추가된 주요 feature

점수 변화율:
- `market_state_score_delta_1d`
- `market_state_score_delta_5d`
- `market_state_score_delta_20d`
- `trend_score_delta_5d`
- `trend_score_delta_20d`
- `breadth_score_delta_5d`
- `breadth_score_delta_20d`
- `risk_score_delta_5d`
- `risk_score_delta_20d`
- `risk_on_score_delta_5d`
- `risk_on_score_delta_20d`
- `risk_off_score_delta_5d`
- `risk_off_score_delta_20d`
- `global_risk_on_score_delta_5d`
- `global_risk_on_score_delta_20d`
- `external_asset_risk_on_score_delta_5d`
- `external_asset_risk_on_score_delta_20d`
- `market_forecast_score_delta_1d`
- `market_forecast_score_delta_5d`
- `market_forecast_score_delta_20d`
- `calibrated_forecast_score_delta_5d`
- `calibrated_forecast_score_delta_20d`

전환/안정성:
- `previous_market_state_label`
- `state_change_flag`
- `state_change_direction`
- `transition_count_5d`
- `transition_count_20d`
- `days_since_state_change`
- `regime_stability_score`
- `regime_momentum_label`

coverage:
- `regime_change_context_available_flag`
- `regime_change_context_coverage_ratio`
- `regime_change_context_null_count`
- `regime_change_context_expected_feature_count`

## 산출 경로

- DB: `D:\QuantMarket\data\db\market_context.db`
- DB table: `market_model_input_daily`
- CSV: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_model_input_daily_current.csv`
- manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`
- schema: `D:\QuantMarket\service_platform\ai_training\market_context\current\schema.json`
- report: `D:\QuantMarket\reports\market_model_input_mart\market_model_input_daily_latest.md`

## 재생성 결과

- rows: 20,601
- columns: 176
- date range: 2017-01-02 ~ 2026-05-12
- duplicate key count: 0

## Regime momentum distribution

- stable: 8,847 rows
- improving_accelerating: 4,887 rows
- deteriorating_accelerating: 4,753 rows
- improving: 1,056 rows
- deteriorating: 1,013 rows
- unknown: 45 rows

## State change summary

| scope | horizon | state changes | avg transition 20d | avg stability |
|---|---|---:|---:|---:|
| ALL | 1d | 389 | 3.387942 | 0.400437 |
| ALL | 5d | 389 | 3.387942 | 0.400437 |
| ALL | 20d | 389 | 3.387942 | 0.400437 |
| KOSPI | 1d | 355 | 3.093054 | 0.457667 |
| KOSPI | 5d | 355 | 3.093054 | 0.457667 |
| KOSPI | 20d | 355 | 3.093054 | 0.457667 |
| KOSDAQ | 1d | 455 | 3.946702 | 0.348100 |
| KOSDAQ | 5d | 455 | 3.946702 | 0.348100 |
| KOSDAQ | 20d | 455 | 3.946702 | 0.348100 |

## PIT 기준

- 모든 국면 변화 feature는 동일 `market_scope + forecast_horizon` 내 과거 row만 사용합니다.
- delta, transition count, days since state change는 미래 상태나 미래 수익률을 사용하지 않습니다.
- 따라서 AI 학습 feature로 사용할 수 있는 PIT-safe 파생 feature입니다.

## Quant 모델 소비 가이드

- `market_state_score_delta_5d`, `market_state_score_delta_20d`는 중기 국면 개선/둔화 판단에 우선 사용 가능합니다.
- `market_forecast_score_acceleration_5d`는 전망 점수의 개선 속도 또는 둔화 속도 feature로 사용할 수 있습니다.
- `transition_count_20d`가 높고 `regime_stability_score`가 낮으면 상태가 흔들리는 구간으로 해석할 수 있습니다.
- `regime_momentum_label`은 categorical feature이며 값셋은 `stable/improving/improving_accelerating/deteriorating/deteriorating_accelerating/unknown`입니다.

## 다음 보강 후보

- target/검증 mart 분리
- forecast 성능 모니터링 mart
- AI 모델 고도화 시 regime feature 반영 실험
