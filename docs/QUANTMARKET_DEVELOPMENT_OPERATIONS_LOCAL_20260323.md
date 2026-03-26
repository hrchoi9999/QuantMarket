# QuantMarket 개발단계 운영안 (로컬 PC)

## 운영 기준

- 개발단계는 `D:\QuantMarket` 로컬 PC에서 운영한다.
- 운영 시간 가정:
  - PC 켜짐: 오전 10시 전후
  - PC 꺼짐: 오후 9시 전후
- 스케줄은 24시간 반복으로 설정하되, PC가 켜져 있는 시간에만 실제 실행된다.

## 시간당 한 번에 수행되는 작업

1. 공식 시장지표 수집
   - KOSPI / KOSDAQ / KOSPI200
   - USD/KRW
2. 금리 계층 갱신
   - 개발단계: `kr_rates_manual_seed.csv` 우선
   - 없으면 기존 적재 값 carry-forward
3. `D:\Quant` read-only adapter 조회
   - breadth universe
   - 대표 방어 ETF 상대강도
   - regime 참고값
4. 시장 상태 계산
5. `market_analysis.db` 갱신
6. QuantService 소비용 snapshot/API-ready JSON 갱신

## 실행 환경

- 기본 Python:
  - `D:\Quant\venv64\Scripts\python.exe`

## 로컬 운영 방식

권장 실행 주기:
- 매시 05분
- 시작 시각: 00:05
- 반복: 24시간

## 제공 스크립트

- 실행 스크립트:
  - `D:\QuantMarket\scripts\run_dev_market_analysis.ps1`
- 작업 스케줄러 등록:
  - `D:\QuantMarket\scripts\register_dev_market_analysis_task.ps1`
- 작업 스케줄러 해제:
  - `D:\QuantMarket\scripts\unregister_dev_market_analysis_task.ps1`
- 금리 seed 업데이트:
  - `D:\QuantMarket\scripts\update_kr_rates_manual_seed.ps1`
- 금리 seed 검증:
  - `D:\QuantMarket\validate_kr_rates_manual_seed.py`

## 금리 관리 파일

- `D:\QuantMarket\data\reference\kr_rates_manual_seed.csv`

채워 넣을 컬럼:
- `date`
- `rate_code`
- `rate_name`
- `value`
- `source`

## 금리 입력 예시

```powershell
powershell -ExecutionPolicy Bypass -File D:\QuantMarket\scripts\update_kr_rates_manual_seed.ps1 -Date 2026-03-23 -Base 2.75 -Cd91 3.12 -Ktb3y 2.65 -Ktb5y 2.74
```

검증 예시:

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_kr_rates_manual_seed.py --date 2026-03-23
```

개발단계에서는 이 값을 갱신하면 다음 시간당 파이프라인에서 `market_rates_daily`에 자동 반영된다.

## 로그 위치

- `D:\QuantMarket\reports\market_analysis\logs\`
