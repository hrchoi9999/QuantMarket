# QuantMarket Market Context PIT/Lag 보강 회신

- 작성일: 2026-05-13
- 대상: Quant 모델 쓰레드
- 목적: AI 학습용 market context mart의 point-in-time 안정성 보강

## 완료 사항

1. FRED/Yahoo 해외 데이터 KST 사용 가능일 보정
- 기존: source `asof_date`와 한국 시장 `asof_date`를 직접 조인
- 변경: US/FRED/Yahoo source date는 KST 기준 다음 영업일부터 사용 가능하도록 조정
- 원천일은 별도 컬럼으로 보존

2. FRED 월간 macro release lag 보강
- CPI, Core CPI, PPI, 실업률, 고용 등 월간 macro 지표는 관측월 기준 즉시 사용하지 않음
- 보수적으로 `관측일 + 21 calendar days` 이후부터 feature 계산에 사용

3. mart schema/version 갱신
- `ai_market_context_mart.v1.4`
- `qm_ai_market_context_features.v1.5`
- baseline forecast model version: `qm_market_forecast_baseline_v0.3_pit_lag_20260513`
- wide input mart schema: `market_model_input_daily.v2`
- wide input mart feature version: `qm_market_model_input_features.v2_pit_lag_20260513`

## 추가된 PIT 컬럼

`global_context_daily`
- `global_source_asof_date`
- `global_pit_available_date`
- `global_pit_lag_rule`
- `monthly_macro_release_lag_days`

`external_market_context_daily`
- `external_source_asof_date`
- `external_pit_available_date`
- `external_pit_lag_rule`

`market_model_input_daily`
- 위 PIT 컬럼들이 wide mart에도 함께 포함됨

## 산출 경로

- DB: `D:\QuantMarket\data\db\market_context.db`
- wide mart table: `market_model_input_daily`
- wide mart CSV: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_model_input_daily_current.csv`
- manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`
- schema: `D:\QuantMarket\service_platform\ai_training\market_context\current\schema.json`
- PIT 보강 리포트: `D:\QuantMarket\reports\market_model_input_mart\market_model_input_daily_latest.md`

## 재생성 결과

- `market_model_input_daily` rows: 20,601
- date range: 2017-01-02 ~ 2026-05-12
- primary key: `asof_date + market_scope + forecast_horizon`
- duplicate key count: 0

## 재검증 결과 요약

PIT lag 적용 후에도 20거래일 전망축의 신호는 유지되었습니다.

- KOSPI 20d AI calibration prediction corr: 0.311046
- KOSPI 20d directional win: 0.593456
- ALL 20d AI calibration prediction corr: 0.272682
- ALL 20d directional win: 0.586019
- 1d 전망축은 여전히 약하므로 단기 예측 feature로는 보수적으로 사용 권장

## Quant 모델 소비 가이드

- 기본 조인 mart: `market_model_input_daily`
- 조인 키: `asof_date + market_scope + forecast_horizon`
- theme feature는 기존처럼 별도 `theme_context_daily_quant_bucket`을 `asof_date + quant_theme_bucket`으로 조인
- `global_source_asof_date`, `external_source_asof_date`는 설명/감사용 원천일이며 모델 feature로 직접 사용하지 않는 것을 권장
- `global_pit_available_date`, `external_pit_available_date`는 `asof_date`와 동일해야 정상
- null은 0으로 대체하지 말고 모델별 imputation policy를 별도로 적용

## 남은 보강 후보

- coverage/null flag 상세화
- 국면 전환 delta feature 추가
- target/검증 mart 분리
- forecast 성능 모니터링 mart 추가
