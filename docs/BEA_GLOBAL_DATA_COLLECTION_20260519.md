# BEA 공식 매크로 데이터 수집 연동

## 목적
- 미국 성장/소비/소득/PCE 물가 데이터를 BEA 공식 API에서 직접 수집한다.
- 기존 `global_market_context.db`의 `global_observation` 테이블을 유지하고 `source='BEA'`로 분리 저장한다.

## API 키
- 파일 경로: `D:\QuantMarket\config\bea_api_key.txt`
- 대체 환경변수: `BEA_API_KEY`
- `config/*.txt`는 `.gitignore`에 포함되어 git에 올라가지 않는다.

## 1차 수집 대상
- `BEA_GDP`: NIPA `T10105`, line `1`, quarterly
- `BEA_REAL_GDP`: NIPA `T10106`, line `1`, quarterly
- `BEA_PCE`: NIPA `T10105`, line `2`, quarterly
- `BEA_REAL_PCE`: NIPA `T10106`, line `2`, quarterly
- `BEA_PERSONAL_INCOME`: NIPA `T20100`, line `1`, monthly
- `BEA_PCE_PRICE_INDEX`: NIPA `T20304`, line `1`, monthly

## 실행
```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\collect_bea_global_data.py
```

## 적용 방식
- BEA 데이터는 원천 확보 및 시장 환경 지표 payload 표시 대상이다.
- Forecast feature 반영은 후속 단계에서 성장/소비 momentum score로 별도 설계한다.
- `run_daily_market_ai_training_update.py`에는 BEA 수집 단계가 추가되어 있다.

## 주의
- BEA API는 무료지만 UserID/API key가 필요하다.
- `bea_api_key.txt`가 없으면 수집은 실패한다.
