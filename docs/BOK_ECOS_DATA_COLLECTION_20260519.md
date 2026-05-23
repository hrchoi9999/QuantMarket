# BOK ECOS 공식 데이터 수집 연동

## 목적
- 국내 환율/금리 원천을 수동 seed 중심에서 BOK ECOS 공식 데이터 중심으로 보강한다.
- 기존 `market_fx_daily`, `market_rates_daily` 구조는 유지한다.

## API 키
- 파일 경로: `D:\QuantMarket\config\bok_ecos_api_key.txt`
- 대체 환경변수: `BOK_ECOS_API_KEY` 또는 `ECOS_API_KEY`
- `config/*.txt`는 `.gitignore`에 포함되어 git에 올라가지 않는다.

## 수집 대상
- `USDKRW`: `731Y001 / D / 0000001`
- `CD91`: `817Y002 / D / 010502000`
- `KTB3Y`: `817Y002 / D / 010200000`
- `KTB5Y`: `817Y002 / D / 010200001`
- `BASE`: `722Y001 / M / 0101000`

## 실행
```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\collect_bok_ecos_market_data.py --start 2000-01-01 --end 2026-05-19
```

## 파이프라인 반영 방식
- `run_market_analysis_pipeline.py` 실행 시 BOK API 키가 있으면 자동 수집한다.
- BOK 수집 성공 시 `market_rates_daily`의 `rate_source`는 `bok_ecos`가 된다.
- BOK 키가 없거나 수집 실패 시 기존 `manual_seed` 또는 `carry_forward` fallback을 사용한다.

## 주의
- 기준금리는 ECOS 월간 자료라 `YYYY-MM-01` 날짜로 저장한다.
- 일별 금리 및 환율은 ECOS 일별 자료 날짜 그대로 저장한다.
