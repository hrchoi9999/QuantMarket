# BLS 공식 매크로 데이터 수집 연동

## 목적
- 미국 물가/고용 데이터의 원천을 FRED 보조 구조에서 BLS 공식 API 우선 구조로 보강한다.
- 기존 `global_market_context.db`의 `global_observation` 테이블을 유지하고 `source='BLS'`로 분리 저장한다.

## 수집 대상
- `CPIAUCSL`: `CUSR0000SA0` 미국 CPI
- `CPILFESL`: `CUSR0000SA0L1E` 미국 Core CPI
- `PPIACO`: `WPU00000000` 미국 PPI
- `UNRATE`: `LNS14000000` 미국 실업률
- `PAYEMS`: `CES0000000001` 미국 비농업고용
- `CES0500000003`: `CES0500000003` 미국 민간 평균시간당임금

## 실행
```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\collect_bls_global_data.py --start-year 2000 --end-year 2026
```

## 적용 방식
- `global_context_daily` 생성 시 BLS 월간 물가/고용 관측치를 우선 사용한다.
- BLS 관측치가 없으면 기존 FRED 관측치를 fallback으로 사용한다.
- 월간 macro 값은 기존 PIT 원칙대로 관측월 이후 21일 release lag를 적용한다.

## 파이프라인
- `run_daily_market_ai_training_update.py`에 BLS 수집 단계를 추가했다.
- 순서: Treasury 수집 -> BLS 수집 -> global context 생성.

## 주의
- BLS API는 키 없이 사용 가능한 공개 API다.
- 요청 구간은 안정성을 위해 10년 단위 chunk로 나눠 호출한다.
