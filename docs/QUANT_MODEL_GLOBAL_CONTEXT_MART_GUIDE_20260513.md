# QuantMarket Global Context Mart Guide

작성일: 2026-05-13

## 목적

Quant 모델의 AI 학습/검증에서 국내 시장 context에 글로벌 매크로/위험 환경을 결합할 수 있도록, FRED 기반 `global_context_daily`를 AI 학습용 market context mart에 1차 canonical 산출물로 추가한다.

## 제공 위치

- DB: `D:\QuantMarket\data\db\market_context.db`
- 테이블: `global_context_daily`
- CSV current: `D:\QuantMarket\service_platform\ai_training\market_context\current\global_context_daily_current.csv`
- Manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`
- Schema: `D:\QuantMarket\service_platform\ai_training\market_context\current\schema.json`
- Coverage report: `D:\QuantMarket\reports\market_context_mart\ai_training_market_context_mart_coverage_latest.json`

## 조인 기준

- 기본 키: `asof_date`
- 권장 조인: 종목 feature 또는 기존 `market_context_daily`에 `asof_date` 기준 left join
- `market_scope`별로 값이 달라지는 데이터가 아니므로 `ALL/KOSPI/KOSDAQ`으로 복제하지 않는다.
- Quant 모델에서 `market_scope` 단일 테이블 형태가 필요하면 consumer 측에서 `asof_date` 기준 조인 후 scope별 행에 동일 값을 확장한다.

## 주요 Score 방향성

- `global_risk_on_score`: 높을수록 글로벌 위험선호 환경이 우호적이다.
- `external_macro_pressure_score`: 높을수록 외부 매크로 부담이 크다.
- `rate_pressure_score`: 높을수록 미국 금리 부담이 크다.
- `usd_pressure_score`: 높을수록 달러/원화 약세 부담이 크다.
- `credit_stress_score`: 높을수록 신용스프레드 부담이 크다.
- `risk_aversion_score`: 높을수록 변동성/위험회피 부담이 크다.
- `inflation_pressure_score`: 높을수록 미국 물가 부담이 크다.
- `commodity_pressure_score`: 높을수록 원자재 가격/변동성 부담이 크다.

## 원천 Level/Ratio 필드

- 금리: `us_10y_rate`, `us_2y_rate`, `us_real_10y_rate`, `breakeven_10y`
- 금리차: `yield_curve_10y_2y`, `yield_curve_10y_3m`
- 변동성/신용: `vix_level`, `hy_spread`, `ig_spread`
- 환율/달러: `dxy_level`, `usdkrw_level`
- 원자재: `wti_level`
- 물가/고용: `cpi_yoy`, `core_cpi_yoy`, `ppi_yoy`, `unrate`, `payrolls_3m_change`

## 결측 처리

- 산출 불가 값은 `null`로 유지한다.
- 0 대체는 하지 않는다.
- `credit_stress_score`, `hy_spread`, `ig_spread`는 현재 FRED 응답 가능 구간이 짧아 결측률이 높을 수 있다.

## PIT 기준

- FRED 관측치의 `asof_date`는 원천 series의 관측일/발표일 기준이다.
- 일별 금리/환율/변동성 데이터는 해당 날짜에 관측 가능한 값으로 취급한다.
- 월별 물가/고용 데이터는 해당 월 observation을 trailing 방식으로 사용한다.
- 학습 label 생성 시 보수적 PIT가 필요하면 Quant 모델 쪽에서 `asof_date` 기준 1거래일 lag 또는 release lag 정책을 추가 적용한다.

## 버전

- Mart schema version: `ai_market_context_mart.v1.1`
- Mart feature version: `qm_ai_market_context_features.v1.2`
- Global source feature version: `fred_global_context_v1_20260513`
- Global source schema version: `global_context_daily_v1`

