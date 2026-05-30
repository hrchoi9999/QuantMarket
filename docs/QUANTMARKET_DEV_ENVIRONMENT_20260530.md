# QuantMarket Development Environment

## 기본 실행 환경

- Workspace: `D:\QuantMarket`
- 기본 Python: `D:\Quant\venv64\Scripts\python.exe`
- Quant read-only root: `D:\Quant`
- QuantService sync target: `D:\QuantService\service_platform\web\public_data\market_analysis\current`
- GCS credential: `D:\QuantService\data\gcp\quantmarket-handoff-uploader.json`

## 의존성

현재 운영은 `D:\Quant\venv64`를 기준으로 한다. 새 환경을 만들 때는 아래 파일을 기준으로 맞춘다.

```powershell
D:\Quant\venv64\Scripts\python.exe -m pip install -r D:\QuantMarket\requirements.txt
D:\Quant\venv64\Scripts\python.exe -m pip install -r D:\QuantMarket\requirements-dev.txt
```

`requirements.txt`는 현재 QuantMarket 코드에서 직접 사용하는 주요 패키지만 고정한다. 전체 shared venv freeze가 아니다.

## 필수 검증 명령

```powershell
D:\Quant\venv64\Scripts\python.exe -m py_compile D:\QuantMarket\run_daily_market_ai_training_update.py D:\QuantMarket\run_quant_model_handoff_fast.py D:\QuantMarket\validate_quantmarket_daily.py
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_quantmarket_daily.py --expected-asof YYYY-MM-DD
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_quantmarket_daily.py --expected-asof YYYY-MM-DD --check-remote
```

## 개발 원칙

- 백업은 작업마다 하지 않고, 사용자 요청 또는 일 1회 원칙을 따른다.
- `D:\Quant`와 `D:\QuantService`는 기본적으로 읽기 전용이며, 명시된 sync/publish 대상만 쓴다.
- 데이터수집 쓰레드 변경분과 마켓분석 모델 변경분은 git commit을 분리한다.
- generated current, DB, reports runtime 산출물은 기본적으로 git 추적 대상이 아니다.
