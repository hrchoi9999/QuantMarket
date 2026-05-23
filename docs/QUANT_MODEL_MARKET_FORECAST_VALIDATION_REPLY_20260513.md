# QuantMarket 회신: market_forecast_daily 성능 검증 1차 결과

`market_forecast_daily`를 KOSPI/KOSDAQ ETF proxy forward return 기준으로 1차 검증했습니다.

## 검증 산출물

- Report JSON: `D:\QuantMarket\reports\market_forecast_validation\market_forecast_validation_latest.json`
- Report MD: `D:\QuantMarket\reports\market_forecast_validation\market_forecast_validation_latest.md`
- Detail CSV: `D:\QuantMarket\reports\market_forecast_validation\market_forecast_validation_detail_latest.csv`
- Label summary CSV: `D:\QuantMarket\reports\market_forecast_validation\market_forecast_validation_label_summary_latest.csv`
- Quintile summary CSV: `D:\QuantMarket\reports\market_forecast_validation\market_forecast_validation_quintile_summary_latest.csv`

## 검증 방식

- `market_forecast_daily`의 `asof_date + market_scope + forecast_horizon`을 기준으로 이후 ETF proxy forward return을 연결했습니다.
- KOSPI: KODEX 코스피 `226490`
- KOSDAQ: KODEX 코스닥150 `229200`
- ALL: KOSPI 60% + KOSDAQ 40% 일간수익률 합성 proxy
- Horizon: `1d`, `5d`, `20d`

## 핵심 결과

| scope | horizon | rows | pearson | spearman | Q5-Q1 mean return spread | Q5-Q1 win rate spread |
|---|---|---:|---:|---:|---:|---:|
| ALL | 1d | 2,288 | 0.031917 | 0.051376 | 0.00143963 | 0.09388646 |
| ALL | 5d | 2,284 | 0.073953 | 0.064424 | 0.00645498 | 0.07658643 |
| ALL | 20d | 2,269 | 0.064757 | 0.056538 | 0.01797347 | 0.07488987 |
| KOSPI | 1d | 2,288 | 0.042025 | 0.051727 | 0.00174696 | 0.069869 |
| KOSPI | 5d | 2,284 | 0.088650 | 0.056515 | 0.00708757 | 0.04157549 |
| KOSPI | 20d | 2,269 | 0.091797 | 0.065871 | 0.02088829 | 0.05851286 |
| KOSDAQ | 1d | 2,288 | 0.010264 | 0.025381 | -0.00050412 | 0.05676856 |
| KOSDAQ | 5d | 2,284 | 0.037373 | 0.031706 | 0.00318006 | 0.04376368 |
| KOSDAQ | 20d | 2,269 | 0.031221 | 0.019499 | 0.00671516 | -0.00440528 |

## 해석

- `market_forecast_daily`는 1차 baseline임에도 KOSPI와 ALL의 `5d`, `20d`에서 약한 양의 예측력이 확인됩니다.
- KOSPI 20d가 가장 양호합니다. Pearson 0.091797, Q5-Q1 평균 forward return spread 2.09%p 수준입니다.
- ALL 5d/20d도 상위 score 구간이 하위 score 구간보다 평균수익률과 승률이 높습니다.
- KOSDAQ은 방향성은 일부 있으나 KOSPI/ALL 대비 약합니다. 특히 KOSDAQ 1d와 20d는 calibration 전 단독 사용에는 보수적으로 접근하는 것이 좋습니다.

## 권장 사용

- 1차 Quant 모델 테스트에서는 `KOSPI/ALL + 5d/20d`를 우선 사용하세요.
- `market_forecast_score`, `risk_regime_label`, `expected_volatility_score`, `drawdown_risk_score`, `upside_participation_score`를 함께 넣고 feature importance를 확인하는 것을 권장합니다.
- KOSDAQ 단기 예측은 아직 강하지 않으므로 종목 모델에서 보조 feature로만 사용하는 것이 좋습니다.

## 다음 단계

- Horizon별/market_scope별 가중치 재조정
- 실제 forward return 기반 supervised calibration layer 추가
- Walk-forward 검증 추가
- 하락장/상승장 regime별 부분검증 추가

