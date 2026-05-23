# QuantMarket AI 학습용 Market Context Mart 소비 계약

## 계약 버전

- schema_version: `ai_market_context_mart.v1`
- feature_version: `qm_ai_market_context_features.v1.1`
- source_version: `quantmarket_market_analysis_db.v1+quant_price_db_readonly.v1`
- timezone: `Asia/Seoul`

## Canonical 경로

- DB: `D:\QuantMarket\data\db\market_context.db`
- Current CSV 폴더: `D:\QuantMarket\service_platform\ai_training\market_context\current`
- Manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`
- Schema JSON: `D:\QuantMarket\service_platform\ai_training\market_context\current\schema.json`
- Theme crosswalk: `D:\QuantMarket\service_platform\ai_training\market_context\current\theme_bucket_crosswalk_current.csv`
- Coverage report: `D:\QuantMarket\reports\market_context_mart\ai_training_market_context_mart_coverage_latest.json`

## Canonical 파일명

- `market_context_daily_current.csv`
- `theme_context_daily_current.csv`
- `theme_context_daily_quant_bucket_current.csv`
- `risk_context_daily_current.csv`
- `flow_context_daily_current.csv`
- `manifest.json`
- `schema.json`
- `theme_bucket_crosswalk_current.csv`

## 조인 계약

- `market_context_daily`: `asof_date + market_scope`
- `theme_context_daily`: `asof_date + theme_bucket`
- `theme_context_daily_quant_bucket`: `asof_date + quant_theme_bucket`
- `risk_context_daily`: `asof_date`
- `flow_context_daily`: `asof_date + market_scope`

`market_scope` 값셋은 `ALL`, `KOSPI`, `KOSDAQ`으로 고정한다.

## Theme Bucket 계약

현재 QuantMarket은 sector/theme ETF proxy 기반의 `theme_bucket`을 제공한다.
Quant 모델 쪽 실제 STOCK `theme_bucket` 17개는 `theme_bucket_crosswalk_current.csv` 기준으로 전부 매핑했다.
Quant 모델은 직접 조인 편의를 위해 `theme_context_daily_quant_bucket_current.csv`를 우선 사용하면 된다.

Crosswalk 필드:

- `quant_theme_bucket`
- `quantmarket_theme_bucket`
- `theme_name_kr`
- `proxy_ticker`
- `proxy_name`
- `mapping_confidence`
- `mapping_reason`
- `is_active`

## Quant Theme Bucket 매핑

| quant_theme_bucket | quantmarket_theme_bucket | proxy_ticker | mapping_confidence |
|---|---|---|---:|
| `semiconductor_tech` | `sector_it` | `139260` | 0.92 |
| `biotech_healthcare` | `sector_healthcare` | `227540` | 0.90 |
| `bank_insurance` | `sector_financials` | `139270` | 0.93 |
| `software_platform` | `sector_it` | `139260` | 0.68 |
| `battery_chemical` | `sector_energy_chemicals` | `139250` | 0.74 |
| `steel_machinery` | `sector_steel_materials` | `139240` | 0.72 |
| `energy_utility_infra` | `sector_energy_chemicals` | `139250` | 0.66 |
| `auto_mobility` | `sector_consumer_discretionary` | `139290` | 0.64 |
| `electronics_it` | `sector_it` | `139260` | 0.90 |
| `construction_materials` | `sector_construction` | `139220` | 0.78 |
| `consumer_retail` | `sector_consumer_discretionary` | `139290` | 0.82 |
| `consumer_food` | `sector_consumer_staples` | `227560` | 0.86 |
| `shipbuilding_defense` | `sector_heavy_industries` | `139230` | 0.76 |
| `media_game_entertainment` | `sector_communication` | `315270` | 0.75 |
| `holding_company` | `sector_financials` | `139270` | 0.45 |
| `logistics_transport` | `sector_industrials` | `227550` | 0.62 |
| `telecom` | `sector_communication` | `315270` | 0.86 |

Low confidence 기준은 `mapping_confidence < 0.70`이다.
현재 low confidence bucket은 `software_platform`, `energy_utility_infra`, `auto_mobility`, `holding_company`, `logistics_transport`이다.
이들은 전용 proxy ETF가 없어 광역 섹터 proxy로 근사했다.

## Flow Context 결측 처리

`flow_context_daily`는 장기 학습 조인의 안정성을 위해 2017-01-02 이후 전체 `asof_date x market_scope` 행을 제공한다.
다만 QM 장중 수급 원천은 2026-03-26 이후부터 존재하므로, 원천이 없는 구간은 아래 기준으로 고정한다.

- 수급 값: null
- `flow_context_available`: `0`
- `flow_coverage_flag`: `0`
- `flow_source_start_date`: 원천 시작일이 확인되면 `2026-03-26`

실제 수급 값이 있는 행은 다음과 같다.

- `flow_context_available`: `1`
- `flow_coverage_flag`: `1`
- `source_quality`: `intraday_aggregate_recent_only`

## ETF Proxy 산출 방식

장기 market/theme/risk feature는 `D:\Quant\data\db\price.db`를 읽기 전용으로 참조한 ETF proxy 기반이다.
모든 산출물은 `D:\QuantMarket`에만 저장한다.

Market proxy:

- KOSPI: `226490`, KODEX 코스피
- KOSDAQ: `229200`, KODEX 코스닥150
- ALL: KOSPI 60% + KOSDAQ 40% 일간 수익률 합성 지수

Risk proxy:

- USDKRW: `138230`, KIWOOM 미국달러선물
- GOLD: `132030`, KODEX 골드선물(H)
- BOND: `114260`, KODEX 국고채3년
- INVERSE: `114800`, KODEX 인버스

Theme proxy:

- `sector_it`: `139260`, TIGER 200 IT
- `sector_financials`: `139270`, TIGER 200 금융
- `sector_consumer_discretionary`: `139290`, TIGER 200 경기소비재
- `sector_industrials`: `227550`, TIGER 200 산업재
- `sector_consumer_staples`: `227560`, TIGER 200 생활소비재
- `sector_healthcare`: `227540`, TIGER 200 헬스케어
- `sector_energy_chemicals`: `139250`, TIGER 200 에너지화학
- `sector_steel_materials`: `139240`, TIGER 200 철강소재
- `sector_construction`: `139220`, TIGER 200 건설
- `sector_heavy_industries`: `139230`, TIGER 200 중공업
- `sector_communication`: `315270`, TIGER 200 커뮤니케이션서비스

ETF 교체/상장폐지 정책:

- v1.1에서는 고정 proxy ticker를 사용한다.
- proxy ETF가 상장 전인 구간은 해당 theme row가 생성되지 않거나 rolling feature가 null일 수 있다.
- proxy 변경이 필요하면 `feature_version`을 올리고 crosswalk와 schema를 함께 갱신한다.

## Point-In-Time 기준

- 모든 rolling feature는 `asof_date` 또는 그 이전 가격만 사용한다.
- daily proxy feature는 해당 거래일 장마감 이후 확정 데이터로 취급한다.
- 학습 데이터가 장중 예측 기준이면 동일일 종가 feature를 사용하지 말고 다음 거래일 이후로 lag 처리해야 한다.
- current 파일은 재생성 시 overwrite한다.
- 과거 원천 정정이나 proxy 산식 변경이 발생하면 `feature_version`을 증가시키고 전체 mart를 재산출한다.

## Null 정책

- 산출 불가 값은 null로 유지한다.
- 학습 전처리에서 0 대체 여부는 Quant 모델 쪽에서 별도 판단한다.
- QM mart 생성 단계에서는 임의 0 대체를 하지 않는다.

## Validation Summary

상세 검증 결과는 아래 파일을 기준으로 확인한다.

- `D:\QuantMarket\reports\market_context_mart\ai_training_market_context_mart_coverage_latest.json`

포함 항목:

- 테이블별 row count
- date coverage
- market_scope coverage
- theme_bucket coverage
- Quant theme 기준 mapping coverage
- 주요 필드 null rate
- label distribution
- duplicate key count
- missing date count
