# QuantMarket Daily Validation and Remote Config

## 원격 게시 기본값

아래 값은 코드 기본값으로 고정했다. 환경변수로 덮어쓸 수 있다.

- bucket: `quantservice-489808-market-analysis`
- base_url: `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current`
- credentials: `D:\QuantService\data\gcp\quantmarket-handoff-uploader.json`

관련 파일:

- `D:\QuantMarket\src\quantmarket_market\config.py`
- `D:\QuantMarket\scripts\run_dev_market_analysis.ps1`
- `D:\QuantMarket\scripts\register_dev_market_analysis_task.ps1`

## 통합 검증

로컬 산출물, QuantService handoff, Quant model handoff를 한 번에 확인한다.

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_quantmarket_daily.py --expected-asof 2026-05-29
```

원격 GCS current까지 확인한다.

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_quantmarket_daily.py --expected-asof 2026-05-29 --check-remote
```

## 검증 범위

- `market_analysis.db` 최신 시장상태 및 주요 테이블 row count
- local current snapshot 필수 파일
- QuantService handoff 필수 파일과 asof 일관성
- Quant model handoff `20d ALL/KOSPI/KOSDAQ` 계약
- 원격 GCS 대표 JSON fetch 및 핵심 asof 확인

시장환경지표 JSON은 별도 라이브 갱신 주기를 갖기 때문에 원격 smoke check에서 존재와 JSON 파싱만 확인한다.
