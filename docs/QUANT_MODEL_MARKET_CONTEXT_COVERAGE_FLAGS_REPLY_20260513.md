# QuantMarket Market Context Coverage/Null Flag 보강 회신

- 작성일: 2026-05-13
- 대상: Quant 모델 쓰레드
- 목적: AI 학습용 `market_model_input_daily` mart의 결측/커버리지 해석 안정성 보강

## 완료 사항

최종 소비용 wide mart인 `market_model_input_daily`에 source group별 coverage/null flag를 추가했습니다.

## 갱신 버전

- schema_version: `market_model_input_daily.v3`
- feature_version: `qm_market_model_input_features.v3_coverage_flags_20260513`

## 추가된 coverage 구조

각 source group마다 아래 컬럼을 제공합니다.

- `{source_group}_available_flag`
- `{source_group}_coverage_ratio`
- `{source_group}_null_count`
- `{source_group}_expected_feature_count`

공통 coverage 컬럼도 추가했습니다.

- `source_group_available_count`
- `source_group_expected_count`
- `overall_feature_coverage_ratio`
- `overall_null_count`
- `coverage_quality_label`
- `coverage_policy`

## Source group

- `forecast_context`
- `domestic_market_context`
- `risk_context`
- `flow_context`
- `global_macro_context`
- `external_market_context`
- `ai_calibration_context`

## 산출 경로

- DB: `D:\QuantMarket\data\db\market_context.db`
- DB table: `market_model_input_daily`
- CSV: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_model_input_daily_current.csv`
- manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`
- schema: `D:\QuantMarket\service_platform\ai_training\market_context\current\schema.json`
- report: `D:\QuantMarket\reports\market_model_input_mart\market_model_input_daily_latest.md`

## 재생성 결과

- rows: 20,601
- columns: 141
- date range: 2017-01-02 ~ 2026-05-12
- duplicate key count: 0

## Coverage summary

| source group | available rate | avg coverage | avg nulls | expected features |
|---|---:|---:|---:|---:|
| forecast_context | 1.0 | 0.992136 | 0.047182 | 6 |
| domestic_market_context | 1.0 | 1.0 | 0.0 | 16 |
| risk_context | 1.0 | 1.0 | 0.0 | 4 |
| flow_context | 0.003932 | 0.003145 | 4.984273 | 5 |
| global_macro_context | 1.0 | 0.904801 | 2.094364 | 22 |
| external_market_context | 0.960682 | 0.951216 | 1.317169 | 27 |
| ai_calibration_context | 1.0 | 0.944954 | 0.220183 | 4 |

## Coverage quality distribution

- high: 6,030 rows
- medium: 14,310 rows
- low: 261 rows
- very_low: 0 rows

## Quant 모델 소비 가이드

- 숫자 결측을 0으로 바로 채우지 말고, 먼저 `{source_group}_available_flag`와 `{source_group}_coverage_ratio`를 함께 사용하세요.
- `flow_context`는 과거 장기 구간 대부분이 원천 부재입니다. `flow_context_available_flag=0`인 row의 flow 관련 null은 중립값이 아니라 “수집 원천 없음”으로 해석해야 합니다.
- 최신 구간은 대체로 `coverage_quality_label=high`입니다.
- 학습 feature 선택 시 `overall_feature_coverage_ratio`, `coverage_quality_label`, source별 `*_coverage_ratio`를 품질 feature 또는 sample weighting feature로 사용할 수 있습니다.
- categorical인 `coverage_quality_label`은 `high/medium/low/very_low` 값셋으로 고정합니다.

## 다음 보강 후보

- 국면 전환 delta feature
- target/검증 mart 분리
- forecast 성능 모니터링 mart
