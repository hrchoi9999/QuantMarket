# QuantMarket Market Forecast AI Model V1.1 회신

- 작성일: 2026-05-14
- 대상: Quant 모델 쓰레드

## 완료

AI 예측모델 v1.1을 구현하고 학습/검증/최신 예측 산출을 완료했습니다.

## 핵심 변경

- feature 수: 167개 -> 41개 curated feature
- 검증 방식: chronological split -> walk-forward expanding validation
- 모델 후보: Ridge / ElasticNet / HGB
- scope/horizon별 최적 후보 자동 선택
- promotion gate 자동 판정

## 산출물

- prediction CSV: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_forecast_ai_v1_1_predictions_current.csv`
- feature set: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_forecast_ai_v1_1_feature_set_current.json`
- report: `D:\QuantMarket\reports\market_forecast_ai_model_v1_1\market_forecast_ai_v1_1_report_latest.md`
- validation CSV: `D:\QuantMarket\reports\market_forecast_ai_model_v1_1\market_forecast_ai_v1_1_validation_latest.csv`
- metrics CSV: `D:\QuantMarket\reports\market_forecast_ai_model_v1_1\market_forecast_ai_v1_1_metrics_latest.csv`
- model artifacts: `D:\QuantMarket\models\market_forecast_ai_v1_1`

## 승격 판단

- promotion_status: `promote_candidate`
- reason: 20d scope 중 2개 이상이 corr/hit threshold 통과

## 주요 성능

| scope | horizon | model | corr | hit |
|---|---|---|---:|---:|
| ALL | 20d | HGB | 0.226224 | 0.594845 |
| KOSPI | 20d | HGB | 0.196729 | 0.564442 |
| KOSDAQ | 20d | HGB | 0.144547 | 0.561798 |

## 결론

AI v1.1은 v1보다 크게 개선되었고, 20d 중기 시장전망 기준으로 production 후보 승격 조건을 통과했습니다.

단, 실제 production 반영 전에는 다음 확인을 권장합니다.

- 기존 ridge calibration과 동일 기간 직접 비교
- 최근 60d monitoring과 결합한 안정성 확인
- Quant 모델 쪽 소비 방식 확정
