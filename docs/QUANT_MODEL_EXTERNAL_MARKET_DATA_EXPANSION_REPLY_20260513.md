# QuantMarket 회신: 외부시장 데이터 확장 1차 완료

FRED 기반 macro context에 이어 Yahoo 기반 글로벌 ETF/시장 proxy 데이터를 추가 수집하고, Quant 모델 AI 학습용 mart에 연결했습니다.

## 수집 원천

- Source: Yahoo Finance chart API
- 저장 DB: `D:\QuantMarket\data\db\global_market_context.db`
- 원천 테이블:
- `global_asset_registry`
- `global_asset_daily`

## 수집 결과

- asset count: 26
- daily rows: 60,785
- date range: 2017-01-03 ~ 2026-05-12
- failed assets: 0

## 수집 자산 범위

- 미국 대표지수 ETF: `SPY`, `QQQ`, `IWM`, `DIA`
- 글로벌/신흥국/한국 proxy: `ACWI`, `EEM`, `EWY`
- 미국 섹터 ETF: `XLK`, `XLY`, `XLI`, `XLF`, `XLE`, `XLB`, `XLC`, `XLRE`, `XLV`, `XLP`, `XLU`
- 채권/신용: `TLT`, `IEF`, `SHY`, `HYG`, `LQD`
- 원자재/달러: `GLD`, `USO`, `UUP`

## 신규 feature mart

- DB: `D:\QuantMarket\data\db\market_context.db`
- 테이블: `external_market_context_daily`
- CSV: `D:\QuantMarket\service_platform\ai_training\market_context\current\external_market_context_daily_current.csv`
- row count: 2,352
- date range: 2017-01-03 ~ 2026-05-12
- schema version: `ai_market_context_mart.v1.3`
- feature version: `qm_ai_market_context_features.v1.4`

## 주요 feature

- `external_asset_risk_on_score`: 외부시장 위험선호 종합 score
- `us_equity_momentum_score`: 미국 대표지수 ETF momentum
- `us_growth_risk_score`: 나스닥/성장주 위험선호
- `us_smallcap_risk_score`: 미국 소형주 위험선호
- `us_sector_risk_on_score`: 경기민감 섹터 대비 방어 섹터 상대강도
- `global_breadth_proxy_score`: 미국 섹터 ETF 기반 breadth proxy
- `korea_proxy_momentum_score`: 미국 상장 한국 ETF `EWY` momentum
- `credit_proxy_score`: `HYG - LQD` 신용위험 appetite proxy
- `safe_haven_pressure_score`: 장기채/금/달러 기반 방어 압력
- `commodity_risk_score`: 유가 proxy 부담
- `dollar_risk_score`: 달러 강세 부담

## 시장전망 mart 반영

`market_forecast_daily` baseline 전망에 신규 `external_asset_risk_on_score`를 반영했습니다.

- forecast model version: `qm_market_forecast_baseline_v0.2_20260513`
- 신규 baseline field:
- `baseline_external_asset_risk_on_score`

## AI calibration 재검증 결과

외부시장 feature 반영 후 `market_forecast_ai_calibrated_daily`를 재생성했습니다.

| scope | horizon | prediction corr | score corr | directional win rate |
|---|---|---:|---:|---:|
| KOSPI | 20d | 0.300948 | 0.265224 | 0.589489 |
| ALL | 20d | 0.266857 | 0.275780 | 0.581061 |
| KOSPI | 5d | 0.156623 | 0.134035 | 0.559547 |
| ALL | 5d | 0.125576 | 0.135845 | 0.550689 |
| KOSPI | 1d | 0.114281 | 0.108152 | 0.555992 |
| KOSDAQ | 20d | 0.150545 | 0.190847 | 0.569162 |

## 해석

- 외부시장 데이터 확장 후 `KOSPI 20d`가 가장 강한 예측 조합으로 유지되며, prediction corr이 0.300948까지 개선됐습니다.
- `ALL 20d`도 score corr 0.275780으로 양호합니다.
- `KOSPI 1d`는 기존보다 개선됐지만, 단기 예측은 여전히 보조 feature로 사용하는 것이 안전합니다.
- `KOSDAQ`은 일부 개선됐으나 `KOSPI/ALL` 대비 안정성은 낮습니다.

## Quant 모델 권장 적용

우선순위:

- `market_scope=KOSPI`, `forecast_horizon=20d`
- `market_scope=ALL`, `forecast_horizon=20d`
- `market_scope=KOSPI`, `forecast_horizon=5d`
- `market_scope=ALL`, `forecast_horizon=5d`

권장 feature:

- `market_forecast_ai_calibrated_daily.predicted_forward_return`
- `market_forecast_ai_calibrated_daily.calibrated_forecast_score`
- `market_forecast_ai_calibrated_daily.calibration_confidence_score`
- `external_market_context_daily.external_asset_risk_on_score`
- `external_market_context_daily.korea_proxy_momentum_score`
- `external_market_context_daily.us_sector_risk_on_score`
- `external_market_context_daily.credit_proxy_score`

## 주의 사항

- Yahoo ETF 데이터는 공식 지수 데이터가 아니라 거래 가능한 proxy입니다.
- 이 mart는 Quant 모델 학습/검증용 feature이며 공개 웹 투자전망 문구로 직접 사용하지 않습니다.
- 결측값은 null 유지 원칙입니다.

