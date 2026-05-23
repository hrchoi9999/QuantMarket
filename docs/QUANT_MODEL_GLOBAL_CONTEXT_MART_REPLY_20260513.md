# QuantMarket 회신: Global Context Mart 1차 제공

Quant 모델 AI 학습용 market context mart에 FRED 기반 `global_context_daily`를 1차 canonical 산출물로 추가했습니다.

## 제공 경로

- DB: `D:\QuantMarket\data\db\market_context.db`
- 테이블: `global_context_daily`
- CSV: `D:\QuantMarket\service_platform\ai_training\market_context\current\global_context_daily_current.csv`
- Manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`
- Schema: `D:\QuantMarket\service_platform\ai_training\market_context\current\schema.json`
- Coverage report: `D:\QuantMarket\reports\market_context_mart\ai_training_market_context_mart_coverage_latest.json`
- Guide: `D:\QuantMarket\docs\QUANT_MODEL_GLOBAL_CONTEXT_MART_GUIDE_20260513.md`

## 생성 결과

- row count: 2,453
- start date: 2017-01-02
- end date: 2026-05-12
- duplicate key count: 0
- primary key: `asof_date`
- join key: `asof_date`

## 주요 제공 Score

- `global_risk_on_score`: 높을수록 글로벌 위험선호 우호
- `external_macro_pressure_score`: 높을수록 외부 매크로 부담
- `rate_pressure_score`: 높을수록 금리 부담
- `usd_pressure_score`: 높을수록 달러/원화 부담
- `credit_stress_score`: 높을수록 신용 부담
- `risk_aversion_score`: 높을수록 변동성/위험회피 부담
- `inflation_pressure_score`: 높을수록 물가 부담
- `commodity_pressure_score`: 높을수록 원자재 부담

## 소비 방식

Quant 모델에서는 기존 종목 feature 또는 `market_context_daily`에 `asof_date` 기준으로 left join하면 됩니다.

`global_context_daily`는 시장 범위별 데이터가 아니므로 `market_scope`를 두지 않았습니다. `ALL/KOSPI/KOSDAQ`별 행에 동일 값을 붙여야 하면 Quant 모델 쪽에서 조인 후 scope별로 확장하면 됩니다.

## 주의 사항

- 결측값은 `null`로 유지합니다. 0으로 대체하지 마세요.
- 신용스프레드 관련 필드는 FRED 응답 가능 구간 제한으로 결측률이 높습니다.
- 더 엄격한 point-in-time 학습이 필요하면 Quant 모델 쪽에서 `asof_date` 기준 1거래일 lag 또는 release lag를 적용해 주세요.

