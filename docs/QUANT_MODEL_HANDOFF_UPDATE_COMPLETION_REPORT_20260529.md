# Quant 모델 쓰레드 전달용 handoff 업데이트 완료보고

작성일: 2026-05-29

## 요약

QuantMarket 시장데이터 수집 파이프라인에 Quant 모델용 fast handoff 단계를 반영했고, 현재 확정 산출물 기준으로 handoff 갱신 및 검증을 완료했습니다.

## 완료 내용

- 신규 fast handoff 실행 파일 적용:
  - `D:\QuantMarket\run_quant_model_handoff_fast.py`
- 정기 시장데이터 수집/publish 파이프라인에 fast handoff 단계 포함:
  - `D:\QuantMarket\scripts\run_dev_market_analysis.ps1`
- 기존 full AI training/update 파이프라인 대신, 이미 확정된 `current` 산출물만 복사/검증하도록 분리
- AI 학습, AI v1.1 비교, 모델 promotion, threshold/label/calibration 정책 변경은 실행하지 않음

## handoff 실행 결과

실행 명령:

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\run_quant_model_handoff_fast.py --expected-asof 2026-05-28
```

결과:

- status: `ok`
- expected_asof: `2026-05-28`
- generated_at: `2026-05-29T21:06:58+09:00`
- handoff_dir:
  - `D:\QuantMarket\service_platform\quant_model_handoff\market_context\current`
- manifest:
  - `D:\QuantMarket\service_platform\quant_model_handoff\market_context\current\quant_model_handoff_manifest.json`

## 검증 결과

검증 명령:

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_quant_model_handoff.py --expected-asof 2026-05-28
```

검증 결과:

- ok: `true`
- target_asof: `2026-05-28`
- latest_asof: `2026-05-28`
- required_horizon: `20d`
- required_scopes:
  - `ALL`
  - `KOSPI`
  - `KOSDAQ`
- matched_scopes:
  - `ALL`
  - `KOSDAQ`
  - `KOSPI`
- errors: `[]`
- manifest `status.production_ready`: `true`

## 20d forecast row 확인

`market_forecast_ai_calibrated_daily_current.csv` 기준:

| asof_date | forecast_horizon | market_scope | predicted_forward_return |
|---|---:|---|---:|
| 2026-05-28 | 20d | ALL | 0.0131779 |
| 2026-05-28 | 20d | KOSDAQ | 0.03900666 |
| 2026-05-28 | 20d | KOSPI | 0.01166523 |

## 운영 원칙

앞으로 QuantMarket 시장데이터 수집 파이프라인의 최종 완료 조건은 아래까지 포함합니다.

```text
원천 데이터 수집
→ public current 갱신/게시
→ QuantService handoff 갱신/게시
→ Quant 모델 handoff 생성/검증
```

단, Quant 모델 handoff는 이미 확정된 market context / calibrated forecast 산출물을 기준으로 생성합니다. expected asof 기준 산출물이 준비되지 않은 경우 데이터수집 쓰레드에서 AI 학습이나 calibration을 실행하지 않고 실패 처리한 뒤, 마켓분석 쓰레드에 산출물 갱신을 요청합니다.

## Quant 모델 쓰레드 요청

Quant 모델 쓰레드에서는 아래 조건을 기준으로 후속 `model-run-only` 실행 가능 여부를 판단해 주세요.

- `quant_model_handoff_manifest.json`
  - `asof_date = 2026-05-28`
  - `latest_asof_date = 2026-05-28`
  - `status.production_ready = true`
- `market_forecast_ai_calibrated_daily_current.csv`
  - `forecast_horizon=20d`
  - `market_scope=ALL/KOSPI/KOSDAQ` row 존재
  - `predicted_forward_return` 값 존재
- `validate_quant_model_handoff.py --expected-asof 2026-05-28`
  - `ok=true`
  - `errors=[]`
