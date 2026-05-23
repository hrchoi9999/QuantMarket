# Quant 모델 전달용 시장 Context 데이터 세팅 회신

- 작성일: 2026-05-14
- 제공: QuantMarket
- 대상: Quant 모델 쓰레드

## 완료

Quant 모델이 사용할 수 있도록 시장 context / 중기 시장전망 / 검증 / 테마 context 데이터를 handoff 폴더에 정리했습니다.

## 전달 폴더

`D:\QuantMarket\service_platform\quant_model_handoff\market_context\current`

## Manifest

`D:\QuantMarket\service_platform\quant_model_handoff\market_context\current\quant_model_handoff_manifest.json`

## 주요 파일

- `market_model_input_daily_current.csv`
- `market_forecast_ai_calibrated_daily_current.csv`
- `market_forecast_monitoring_daily_current.csv`
- `market_forecast_target_daily_current.csv`
- `market_forecast_validation_daily_current.csv`
- `theme_context_daily_quant_bucket_current.csv`
- `theme_bucket_crosswalk_current.csv`
- `market_forecast_ai_v1_1_predictions_current.csv`
- `market_forecast_ai_v1_1_feature_set_current.json`
- `market_model_ready_feature_columns_current.json`
- `manifest.json`
- `schema.json`

## 사용 원칙

- Primary forecast: `market_forecast_ai_calibrated_daily_current.csv`
- Primary model: ridge calibration
- Primary horizon: `20d`
- AI v1.1: research candidate only
- Join key: `asof_date + market_scope + forecast_horizon`
- Theme join key: `asof_date + quant_theme_bucket`

## 설명 문서

`D:\QuantMarket\docs\QUANT_MODEL_MARKET_CONTEXT_HANDOFF_GUIDE_20260514.md`

## 결론

Quant 모델에 전달 가능한 상태입니다.

권장 적용 방식은 종목 AI/퀀트 모델에 시장 국면, 글로벌 환경, coverage, 중기 주가지수 전망 feature를 결합하는 것입니다.
