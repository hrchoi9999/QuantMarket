# 마켓분석 쓰레드 작업 요청서

작성일: 2026-05-29

## 요청 목적

`run_daily_market_ai_training_update.py` 안에 섞여 있는 두 업무 영역을 분리해 주세요.

현재 이 파일은 시장데이터수집 쓰레드가 수행해야 할 Quant 모델 handoff 운영 작업과, 마켓분석 쓰레드가 담당해야 할 AI 학습/모델 연구 작업을 함께 실행합니다.

그 결과 시장데이터수집 파이프라인에서 Quant 모델 handoff만 갱신하려 해도 AI 학습 및 비교 단계까지 수행되어 실행 시간이 과도하게 길어집니다.

## 현재 문제

최근 실행 기준 전체 소요 시간은 약 17분 이상이었습니다.

주요 병목:

- `build_market_forecast_ai_calibration.py`: 약 380초
- `collect_kiwoom_investor_flows.py`: 약 209초
- `build_domestic_flow_derivatives_daily.py`: 약 168초
- `build_global_context_features.py`: 약 85초
- `build_market_forecast_ai_model_v1_1.py`: 약 38초

특히 `build_market_forecast_ai_model_v1_1.py`와 `compare_market_forecast_ai_v1_1_vs_calibration.py`는 운영 handoff의 필수 조건이 아니라 마켓분석/모델 연구 영역입니다.

## 역할 분리 원칙

### 시장데이터수집 쓰레드 담당

- 원천 데이터 수집
- current payload 갱신
- QuantService public handoff 게시
- Quant 모델용 handoff 파일 생성/복사
- handoff manifest 생성
- handoff 검증

시장데이터수집 쓰레드는 모델 학습, calibration 정책 변경, 성능 비교, 모델 승격 판단을 하지 않습니다.

### 마켓분석 쓰레드 담당

- forecast calibration 생성/개선
- AI 모델 학습/재학습
- AI v1.1 성능 비교
- 모델 승격 판단
- feature/label/threshold 변경
- 백테스트 및 성능 평가

## 요청 작업

### 1. 운영용 Quant handoff fast pipeline 분리

예시 파일명:

```text
run_quant_model_handoff_fast.py
```

또는 기존 네이밍 규칙에 맞는 이름으로 조정 가능합니다.

이 fast pipeline은 다음만 수행해야 합니다.

1. 이미 생성된 확정 산출물 확인
2. Quant 모델 handoff 디렉터리로 필요한 파일 복사
3. `quant_model_handoff_manifest.json` 생성
4. `production_ready` 판정
5. `validate_quant_model_handoff.py` 통과 가능 상태 보장

### 2. fast pipeline에서 제외할 작업

아래 작업은 fast pipeline에서 제외해 주세요.

- `build_market_forecast_ai_model_v1_1.py`
- `compare_market_forecast_ai_v1_1_vs_calibration.py`
- 신규 AI 학습
- 모델 성능 비교
- 모델 승격 판단
- threshold/label/calibration 정책 변경

### 3. full/research pipeline은 마켓분석 쓰레드용으로 유지

기존 `run_daily_market_ai_training_update.py`는 이름을 유지하거나 아래처럼 명확히 바꿀 수 있습니다.

```text
run_market_analysis_research_training_update.py
```

이 full pipeline은 마켓분석 쓰레드가 필요할 때 실행하는 연구/학습용 파이프라인으로 두면 됩니다.

## fast handoff 필수 검증 조건

fast handoff는 아래 조건을 만족해야 합니다.

- `quant_model_handoff_manifest.json` 존재
- `manifest.asof_date = expected_asof`
- `manifest.latest_asof_date = expected_asof`
- `status.production_ready = true`
- `market_forecast_ai_calibrated_daily_current.csv` 존재
- `forecast_horizon=20d` 기준 아래 row 존재
  - `ALL`
  - `KOSPI`
  - `KOSDAQ`
- 각 row의 `predicted_forward_return`이 비어 있지 않음

검증 명령:

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_quant_model_handoff.py --expected-asof YYYY-MM-DD
```

## asof mismatch 처리 원칙

fast handoff 실행 시 확정 forecast/context 산출물이 expected asof보다 오래된 경우, 데이터수집 쓰레드에서 AI 학습이나 calibration을 직접 실행하지 않습니다.

대신 아래 상태로 실패 처리하고 마켓분석 쓰레드에 요청합니다.

```text
forecast/context 산출물이 expected_asof 기준으로 준비되지 않았습니다.
마켓분석 쓰레드에서 market_model_input / calibrated forecast 산출물을 갱신해 주세요.
```

## 기대 결과

분리 후 시장데이터수집 파이프라인의 최종 완료 조건은 다음으로 정의합니다.

```text
원천 데이터 수집 → public current 갱신/게시 → QuantService handoff 갱신/게시 → Quant 모델 handoff 생성/검증
```

단, Quant 모델 handoff는 이미 확정된 forecast/context 산출물을 기준으로 생성하며, AI 학습/모델 연구 단계는 포함하지 않습니다.

## 최근 확인된 정상 handoff 예시

2026-05-29 실행 결과:

- handoff 경로:
  - `D:\QuantMarket\service_platform\quant_model_handoff\market_context\current`
- expected asof:
  - `2026-05-28`
- 검증 결과:
  - `ok=true`
  - `latest_asof=2026-05-28`
  - `required_horizon=20d`
  - `matched_scopes=ALL,KOSDAQ,KOSPI`
  - `errors=[]`

