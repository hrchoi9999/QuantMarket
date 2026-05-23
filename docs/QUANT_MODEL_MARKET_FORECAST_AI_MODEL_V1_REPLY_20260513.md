# QuantMarket Market Forecast AI Model V1 회신

- 작성일: 2026-05-13
- 대상: Quant 모델 쓰레드

## 완료

AI 예측모델 v1을 학습/검증/저장했습니다.

## 산출물

- prediction CSV: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_forecast_ai_v1_predictions_current.csv`
- model artifacts: `D:\QuantMarket\models\market_forecast_ai_v1`
- report: `D:\QuantMarket\reports\market_forecast_ai_model_v1\market_forecast_ai_v1_report_latest.md`
- validation CSV: `D:\QuantMarket\reports\market_forecast_ai_model_v1\market_forecast_ai_v1_validation_latest.csv`
- metrics CSV: `D:\QuantMarket\reports\market_forecast_ai_model_v1\market_forecast_ai_v1_metrics_latest.csv`

## 모델

- model_version: `qm_market_forecast_ai_v1_20260513`
- target: `target_forward_return`
- feature_count: 167
- model type: per `market_scope + forecast_horizon` HistGradientBoostingRegressor
- prediction rows: 9

## 승격 판단

- promotion_status: `research_only`
- reason: 20d validation이 최소 기준을 통과하지 못함
- 기준: 20d scope 중 최소 2개가 `corr >= 0.10` 및 `hit >= 0.53` 충족 필요

## 결론

AI v1은 연구 후보로 저장했지만 production forecast로 승격하지 않습니다.
현재는 기존 walk-forward ridge calibration layer가 더 안정적입니다.

## 다음 개선 방향

- v1.1에서는 feature selection 축소
- walk-forward validation 기준으로 재설계
- target을 단순 forward return이 아니라 downside-adjusted return으로 변경 검토
- regime별 별도 모델 또는 ensemble gating 검토
