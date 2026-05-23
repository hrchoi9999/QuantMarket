# QuantMarket 회신: market_forecast_daily AI Calibration Layer 1차 구축

`market_forecast_daily` baseline 전망값을 실제 forward return으로 보정하는 1차 AI calibration layer를 구축했습니다.

## 제공 경로

- DB: `D:\QuantMarket\data\db\market_context.db`
- 테이블: `market_forecast_ai_calibrated_daily`
- CSV current: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_forecast_ai_calibrated_daily_current.csv`
- Manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`
- Schema: `D:\QuantMarket\service_platform\ai_training\market_context\current\schema.json`
- Calibration report: `D:\QuantMarket\reports\market_forecast_ai_calibration\market_forecast_ai_calibration_latest.md`
- Calibration validation CSV: `D:\QuantMarket\reports\market_forecast_ai_calibration\market_forecast_ai_calibration_validation_latest.csv`

## 생성 결과

- row count: 20,601
- start date: 2017-01-02
- end date: 2026-05-12
- key: `asof_date + market_scope + forecast_horizon`
- model version: `qm_market_forecast_ai_calibration_ridge_v0.1_20260513`
- schema version: `market_forecast_ai_calibration.v1`

## 제공 필드

- `predicted_forward_return`: AI calibration이 추정한 horizon별 forward return
- `calibrated_forecast_score`: 예측 수익률을 과거 분포 기준 score화한 값
- `calibrated_forecast_label`: `bullish`, `mild_bullish`, `neutral`, `mild_bearish`, `bearish`
- `calibration_confidence_score`: 0~1 신뢰도
- `training_sample_count`: 해당 예측 시점에 사용 가능한 과거 학습 샘플 수
- `baseline_market_forecast_score`: 원래 baseline 전망 score
- `baseline_market_forecast_label`: 원래 baseline 전망 label

## 학습/검증 방식

- 모델: walk-forward ridge calibration
- 각 `market_scope + forecast_horizon`별로 별도 보정
- 각 날짜의 예측값은 해당 날짜 이전에 forward return이 확인된 데이터만 사용
- 즉, historical prediction에도 미래 데이터 누수가 없도록 구성
- 최신일처럼 아직 forward return이 없는 row도 과거 전체 학습 샘플로 production prediction 제공

## Walk-forward 검증 결과 요약

| scope | horizon | rows | prediction corr | score corr | directional win rate |
|---|---|---:|---:|---:|---:|
| ALL | 1d | 2,036 | -0.074760 | -0.026138 | 0.541749 |
| ALL | 5d | 2,032 | 0.130030 | 0.139251 | 0.555610 |
| ALL | 20d | 2,017 | 0.263313 | 0.267360 | 0.599901 |
| KOSPI | 1d | 2,036 | 0.087308 | 0.080303 | 0.546169 |
| KOSPI | 5d | 2,032 | 0.161583 | 0.138320 | 0.557579 |
| KOSPI | 20d | 2,017 | 0.296566 | 0.244614 | 0.593456 |
| KOSDAQ | 1d | 2,036 | 0.015722 | 0.024101 | 0.525540 |
| KOSDAQ | 5d | 2,032 | 0.083894 | 0.107737 | 0.545768 |
| KOSDAQ | 20d | 2,017 | 0.149032 | 0.189154 | 0.576599 |

## 해석

- AI calibration 후 `KOSPI 20d`, `ALL 20d`, `KOSPI 5d`, `ALL 5d`에서 의미 있는 양의 예측 상관이 확인됩니다.
- `KOSPI 20d`가 가장 강합니다. prediction corr 0.296566, directional win rate 0.593456입니다.
- `ALL 20d`도 prediction corr 0.263313, directional win rate 0.599901로 양호합니다.
- `1d`는 noise가 커서 보수적으로 사용해야 합니다. 특히 `ALL 1d`는 calibration score 기준 단기 사용을 권장하지 않습니다.

## Quant 모델 권장 사용

- 1차 적용 우선순위:
- `KOSPI + 20d`
- `ALL + 20d`
- `KOSPI + 5d`
- `ALL + 5d`

- 종목 모델 feature로는 아래 필드를 우선 테스트하세요.
- `predicted_forward_return`
- `calibrated_forecast_score`
- `calibrated_forecast_label`
- `calibration_confidence_score`
- `baseline_market_forecast_score`

## 주의 사항

- 이 값은 Quant 모델 학습용 feature이며, 공개 웹 투자전망 문구가 아닙니다.
- `predicted_forward_return`은 기대수익률의 통계적 추정값이지 수익률 보장이 아닙니다.
- 향후 LightGBM/RandomForest/Logistic calibration 등으로 추가 고도화할 수 있습니다.

