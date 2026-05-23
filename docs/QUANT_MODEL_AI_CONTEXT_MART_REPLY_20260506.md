# QuantMarket 회신: AI 학습용 시장 Context Mart 제공

## 요청 개요

- 요청 출처: Quant 모델 쓰레드
- 작업명: AI 학습용 시장 context mart 제공 요청
- 목적: valuation AI 및 S/T/I/C 모델 overlay에서 시장 국면별 feature를 조인할 수 있도록 daily mart 제공
- 기준 원칙: point-in-time 산출, 수치형 feature 우선, 결측은 null 유지, `D:\Quant`는 읽기 전용

## 생성 결과

- 생성 DB: `D:\QuantMarket\data\db\market_context.db`
- CSV 산출 경로: `D:\QuantMarket\service_platform\ai_training\market_context\current`
- 커버리지 리포트 JSON: `D:\QuantMarket\reports\market_context_mart\ai_training_market_context_mart_coverage_latest.json`
- 커버리지 리포트 MD: `D:\QuantMarket\reports\market_context_mart\ai_training_market_context_mart_reply_latest.md`
- 생성 시각: `2026-05-06T18:35:11+09:00`
- 스키마 버전: `ai_market_context_mart.v1`
- 피처 버전: `qm_ai_market_context_features.v1.1`
- 소비 계약 문서: `D:\QuantMarket\docs\QUANT_MODEL_AI_CONTEXT_MART_CONSUMER_CONTRACT_20260506.md`
- manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`
- schema JSON: `D:\QuantMarket\service_platform\ai_training\market_context\current\schema.json`
- theme crosswalk: `D:\QuantMarket\service_platform\ai_training\market_context\current\theme_bucket_crosswalk_current.csv`

## 제공 테이블

| table | rows | start | end | 비고 |
|---|---:|---|---|---|
| `market_context_daily` | 6,855 | 2017-01-02 | 2026-05-04 | `ALL/KOSPI/KOSDAQ` 3개 scope |
| `theme_context_daily` | 24,639 | 2017-01-02 | 2026-05-04 | 11개 sector/theme ETF proxy |
| `theme_context_daily_quant_bucket` | 37,853 | 2017-01-02 | 2026-05-04 | Quant 모델 실제 17개 theme_bucket 기준 파생 mart |
| `risk_context_daily` | 2,285 | 2017-01-02 | 2026-05-04 | USD/KRW, 금, 채권, 인버스 proxy |
| `flow_context_daily` | 6,855 | 2017-01-02 | 2026-05-04 | 전체 날짜 x scope 행 제공, 실제 수급 값은 coverage flag로 구분 |

## Canonical Current 파일명

- `market_context_daily_current.csv`
- `theme_context_daily_current.csv`
- `theme_context_daily_quant_bucket_current.csv`
- `risk_context_daily_current.csv`
- `flow_context_daily_current.csv`
- `manifest.json`
- `schema.json`
- `theme_bucket_crosswalk_current.csv`

## Quant Theme Mapping Coverage

- Quant 모델 STOCK `theme_bucket`: 17개
- 매핑 완료 bucket: 17개
- unmapped bucket: 없음
- 최신 Quant 분류 기준일: 2026-04-22
- mapped stock row coverage: 100.0%, 400 / 400 rows
- low confidence mapping: `software_platform`, `energy_utility_infra`, `auto_mobility`, `holding_company`, `logistics_transport`

## 라벨 값셋

- `market_state_label`: `strong_up`, `up`, `neutral`, `down`, `strong_down`
- `volatility_regime_label`: `low`, `normal`, `high`, `stress`

## Market State Label 분포

- `up`: 2,340 rows
- `down`: 2,045 rows
- `neutral`: 1,556 rows
- `strong_down`: 914 rows
- `strong_up`: 현재 산출 구간에서는 0 rows

## Theme Bucket Coverage

- `sector_communication`: 1,789 rows, 2019-01-15 ~ 2026-05-04
- `sector_construction`: 2,285 rows, 2017-01-02 ~ 2026-05-04
- `sector_consumer_discretionary`: 2,285 rows, 2017-01-02 ~ 2026-05-04
- `sector_consumer_staples`: 2,285 rows, 2017-01-02 ~ 2026-05-04
- `sector_energy_chemicals`: 2,285 rows, 2017-01-02 ~ 2026-05-04
- `sector_financials`: 2,285 rows, 2017-01-02 ~ 2026-05-04
- `sector_healthcare`: 2,285 rows, 2017-01-02 ~ 2026-05-04
- `sector_heavy_industries`: 2,285 rows, 2017-01-02 ~ 2026-05-04
- `sector_industrials`: 2,285 rows, 2017-01-02 ~ 2026-05-04
- `sector_it`: 2,285 rows, 2017-01-02 ~ 2026-05-04
- `sector_steel_materials`: 2,285 rows, 2017-01-02 ~ 2026-05-04

## 주요 결측률

- `market_context_daily`: 요청 필드 기준 주요 결측 없음
- `risk_context_daily`: 요청 필드 기준 주요 결측 없음
- `theme_context_daily`: 초기 rolling window 구간에서 수익률/회전 점수 일부 null 발생 가능
- `flow_context_daily`: 과거 구간은 full date row를 만들고 값은 null, `flow_context_available=0`, `flow_coverage_flag=0`으로 제공

## 원천 및 제한사항

- 2017년 이후 장기 history는 `D:\Quant\data\db\price.db`를 읽기 전용으로 참조했습니다.
- 모든 산출물은 `D:\QuantMarket`에만 생성했습니다.
- KOSPI/KOSDAQ 장기 시장 feature는 공식 지수 원천이 아니라 ETF proxy 기반입니다.
- theme feature는 sector/theme ETF proxy 기반입니다.
- flow feature의 실제 값은 QM 장중 snapshot 누적이 시작된 2026-03-26 이후 `ALL` scope 중심으로만 제공합니다.
- 산출 불가 값은 0으로 대체하지 않고 null로 유지했습니다.

## Quant 모델 쓰레드 사용 가이드

- 종목 feature와 `market_context_daily.asof_date + market_scope`로 조인하면 됩니다.
- 전체 공통 risk feature는 `risk_context_daily.asof_date`로 조인하면 됩니다.
- Quant 모델 실제 theme 기준 조인은 `theme_context_daily_quant_bucket.asof_date + quant_theme_bucket` 또는 CSV `theme_context_daily_quant_bucket_current.csv`를 사용하면 됩니다.
- flow feature는 현재 coverage가 짧으므로 학습용 장기 feature보다 최근 진단/검증용으로 먼저 사용하는 것을 권장합니다.
- 자세한 schema, 값 범위, score 방향성, PIT/revision 정책은 소비 계약 문서를 기준으로 확인하면 됩니다.
