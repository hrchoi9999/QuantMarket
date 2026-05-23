# EIA 공식 에너지 데이터 수집 연동

## 목적
- 미국 에너지 가격/재고 데이터를 EIA 공식 API에서 직접 수집한다.
- 유가, 에너지 재고, 인플레이션 비용 압력, 위험자산 환경 분석의 원천 데이터로 사용한다.

## API 키
- 파일 경로: `D:\QuantMarket\config\eia_api_key.txt`
- 대체 환경변수: `EIA_API_KEY`
- `config/*.txt`는 `.gitignore`에 포함되어 git에 올라가지 않는다.

## 1차 수집 대상
- `EIA_WTI_SPOT`: `PET.RWTC.D`
- `EIA_BRENT_SPOT`: `PET.RBRTE.D`
- `EIA_US_CRUDE_STOCKS`: `PET.WCESTUS1.W`
- `EIA_CUSHING_CRUDE_STOCKS`: `PET.W_EPC0_SAX_YCUOK_MBBL.W`
- `EIA_GASOLINE_STOCKS`: `PET.WGTSTUS1.W`
- `EIA_DISTILLATE_STOCKS`: `PET.WDISTUS1.W`

## 실행
```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\collect_eia_global_data.py
```

## 적용 방식
- EIA 데이터는 `global_market_context.db`의 `global_observation`에 `source='EIA'`로 저장된다.
- `시장 환경 지표` payload에는 EIA 지표가 `source_provider='EIA'`로 표시된다.
- Forecast feature 반영은 후속 단계에서 energy pressure score로 별도 설계한다.

## 파이프라인
- `run_daily_market_ai_training_update.py`에 EIA 수집 단계가 추가되어 있다.
- 키가 없으면 수집은 `skipped`로 종료되어 전체 파이프라인을 막지 않는다.
