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

아래 조건 중 하나라도 만족하지 못하면 실패한다.

- `market_forecast_ai_calibrated_daily_current.csv`의 최신 `asof_date`가 `--expected-asof`와 일치
- 20d `ALL`, `KOSPI`, `KOSDAQ` 행 존재
- 20d `ALL`, `KOSPI`, `KOSDAQ` 행의 `predicted_forward_return` 값 존재
- `quant_model_handoff_manifest.json`의 `status.production_ready = true`

이 경우 데이터수집 쓰레드에서 AI 학습이나 calibration을 직접 실행하지 않는다. 마켓분석 쓰레드에서 market model input과 calibrated forecast 산출물을 먼저 갱신해야 한다.

## 구현 참고

`run_quant_model_handoff_fast.py`와 `run_daily_market_ai_training_update.py`는 공통 handoff 모듈을 재사용한다.

- 공통 모듈: `D:\QuantMarket\src\quantmarket_market\quant_model_handoff.py`
- fast runner: 이미 생성된 `current` 산출물 복사/검증만 수행
- full runner: AI training/update 실행 후 같은 공통 모듈로 handoff 생성
