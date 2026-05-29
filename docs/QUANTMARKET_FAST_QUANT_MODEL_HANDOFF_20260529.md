# QuantMarket Fast Quant Model Handoff

## 목적

데이터수집 쓰레드가 Quant model-run-only 전에 사용할 수 있도록, 이미 생성된 QuantMarket `current` 산출물만 Quant handoff 폴더로 복사하고 계약 검증을 수행한다.

## 실행

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\run_quant_model_handoff_fast.py --expected-asof 2026-05-28
```

## 포함 작업

- `service_platform\ai_training\market_context\current` 산출물 확인
- `service_platform\quant_model_handoff\market_context\current` 갱신
- `quant_model_handoff_manifest.json` 생성
- `validate_quant_model_handoff.py --expected-asof <date>`와 동일한 계약 검증

## 제외 작업

- 원천 데이터 수집
- AI 학습
- `build_market_forecast_ai_model_v1_1.py`
- `compare_market_forecast_ai_v1_1_vs_calibration.py`
- 모델 promotion, threshold, label, calibration 정책 변경

## 실패 기준

`market_forecast_ai_calibrated_daily_current.csv`의 최신 `asof_date`가 `--expected-asof`와 다르거나, 20d `ALL`, `KOSPI`, `KOSDAQ` 행이 없으면 실패한다. 이 경우 마켓분석 쓰레드에서 market model input과 calibrated forecast 산출물을 먼저 갱신해야 한다.
