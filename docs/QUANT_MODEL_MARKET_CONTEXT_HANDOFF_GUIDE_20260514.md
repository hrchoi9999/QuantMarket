# Quant 모델용 QuantMarket 시장 Context Handoff 가이드

- 작성일: 2026-05-14
- 제공 시스템: QuantMarket
- 소비 시스템: Quant 모델
- 목적: 종목 AI/퀀트 모델 학습에 시장 국면, 글로벌 환경, 중기 주가지수 전망 context를 결합한다.

## 1. 전달 위치

Quant 모델 전달용 파일은 아래 폴더에 정리했습니다.

`D:\QuantMarket\service_platform\quant_model_handoff\market_context\current`

핵심 manifest:

`D:\QuantMarket\service_platform\quant_model_handoff\market_context\current\quant_model_handoff_manifest.json`

## 2. 사용 우선순위

### Primary

`market_forecast_ai_calibrated_daily_current.csv`

현재 가장 안정적인 시장전망 모델입니다.

- 모델: ridge calibration
- 권장 horizon: `20d`
- 권장 사용 컬럼:
  - `predicted_forward_return`
  - `calibrated_forecast_score`
  - `calibrated_forecast_label`
  - `calibration_confidence_score`
  - `training_sample_count`

### Primary Feature Mart

`market_model_input_daily_current.csv`

시장, 글로벌, 국면 변화, coverage, forecast feature가 결합된 wide mart입니다.

권장 사용 컬럼:

- `market_state_score`
- `trend_score`
- `breadth_score`
- `risk_score`
- `risk_on_score`
- `risk_off_score`
- `global_risk_on_score`
- `external_macro_pressure_score`
- `external_asset_risk_on_score`
- `korea_proxy_momentum_score`
- `market_state_score_delta_5d`
- `market_state_score_delta_20d`
- `market_forecast_score_acceleration_5d`
- `transition_count_20d`
- `regime_stability_score`
- `overall_feature_coverage_ratio`
- `coverage_quality_label`

### Theme Context

`theme_context_daily_quant_bucket_current.csv`

종목의 `theme_bucket`과 조인해서 테마/섹터 context를 붙입니다.

권장 사용 컬럼:

- `theme_ret_1w`
- `theme_ret_1m`
- `theme_ret_3m`
- `theme_momentum_score`
- `theme_rotation_score`
- `theme_persistence_days`
- `theme_breadth_positive_ratio`
- `theme_above_sma60_ratio`
- `theme_trading_value_expansion_ratio`
- `leading_theme_rank`
- `mapping_confidence`

### Monitoring

`market_forecast_monitoring_daily_current.csv`

예측 모델의 rolling 성능 확인용입니다.

권장 확인 컬럼:

- `ai_corr_60d`
- `ai_hit_rate_60d`
- `ai_mae_60d`
- `monitoring_quality_label`

### Research Candidate

`market_forecast_ai_v1_1_predictions_current.csv`

AI v1.1은 자체 기준으로는 개선됐지만, 기존 ridge calibration과 직접 비교하면 primary로 승격하지 않습니다.

사용 원칙:

- production primary로 사용하지 않음
- 연구/비교 feature로만 사용
- ridge calibration보다 우수한지 지속 비교

## 3. 조인 기준

시장 context 조인 키:

```text
asof_date + market_scope + forecast_horizon
```

Theme context 조인 키:

```text
asof_date + quant_theme_bucket
```

종목별 market_scope 매핑:

- KOSPI 상장 종목: `market_scope = KOSPI`
- KOSDAQ 상장 종목: `market_scope = KOSDAQ`
- 공통 시장환경: `market_scope = ALL`

권장 방식:

- 종목 소속 시장 feature: `KOSPI` 또는 `KOSDAQ`
- 전체 시장 공통 feature: `ALL`
- 우선 horizon: `20d`
- 보조 horizon: `5d`
- `1d`는 예측 신호가 약하므로 보조/참고만 권장

## 4. 성능 기준

AI 학습 효과는 20거래일 주가지수 예측에서 가장 뚜렷합니다.

기존 baseline 대비 ridge calibration 개선:

| 대상 | baseline corr | ridge corr | 개선폭 | baseline hit | ridge hit |
|---|---:|---:|---:|---:|---:|
| ALL 20d | 0.048 | 0.273 | +0.225 | 49.6% | 58.6% |
| KOSPI 20d | 0.094 | 0.311 | +0.217 | 49.8% | 59.4% |
| KOSDAQ 20d | -0.021 | 0.156 | +0.177 | 47.9% | 57.4% |

AI v1.1과 ridge calibration 직접 비교:

- `ridge calibration`을 primary로 유지
- `AI v1.1`은 research candidate

## 5. Null / Coverage 처리

중요 원칙:

null을 바로 0으로 채우지 마세요.

먼저 아래 컬럼을 확인하세요.

- `overall_feature_coverage_ratio`
- `coverage_quality_label`
- `*_available_flag`
- `*_coverage_ratio`

특히 flow context는 과거 장기 구간 coverage가 낮습니다.

- `flow_context_available_flag = 0`이면 수급 데이터가 중립이라는 뜻이 아닙니다.
- 원천 데이터가 없다는 뜻입니다.

## 6. PIT / Leakage 기준

제공 mart는 point-in-time 보강을 적용했습니다.

- US/FRED/Yahoo source date는 KST 다음 영업일 이후에만 조인
- FRED 월간 macro는 보수적 21일 release lag 적용
- target 컬럼은 feature list에서 제외
- generated_at 컬럼은 feature list에서 제외

검증 결과:

- leakage audit 5개 항목 모두 pass

## 7. Quant 모델 권장 사용 방식

1. 종목 feature에 `asof_date` 기준 market context를 left join
2. 종목의 시장 구분에 따라 `KOSPI/KOSDAQ` feature 조인
3. 별도로 `ALL 20d` feature를 공통 시장환경으로 추가
4. 종목 theme_bucket 기준 `theme_context_daily_quant_bucket_current.csv` 조인
5. `calibrated_forecast_score`, `predicted_forward_return`, `calibration_confidence_score`를 핵심 시장전망 feature로 사용
6. `coverage_quality_label`이 낮은 row는 sample weighting 또는 별도 flag로 처리

## 8. 현재 결론

Quant 모델에 제공할 수 있는 상태입니다.

권장 primary:

```text
ridge calibration 20d forecast
```

권장 적용:

```text
종목 AI 모델의 market context / regime context / 중기 지수전망 feature
```

주의:

```text
AI v1.1은 아직 production primary가 아니라 research candidate입니다.
```
