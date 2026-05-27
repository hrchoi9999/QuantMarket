# Index Forecast Handoff

`current` 폴더는 시장별 지수 방향성 연구 모델의 읽기 전용 전달 인터페이스다.

## 경로

- `D:\QuantMarket\service_platform\index_forecast_handoff\current`

## 읽는 순서

1. `index_forecast_handoff_manifest.json` 확인
2. `production_ready=true`, `quality.ok=true`, `errors=[]` 확인
3. `index_forecast_signal_current.csv` 또는 `index_forecast_signal_current.json` 로드
4. 조인 키는 `asof_date`, `market_scope`, `forecast_horizon`

## 고정 계약

- 시장: `KOSPI`, `KOSDAQ`, `KOSPI200`
- horizon: `5d`, `10d`, `20d`, `60d`
- 방향: `down`, `sideways`, `up`
- `ALL`은 포함하지 않는다.
- `recommended_exposure`는 0.0~1.0 범위의 지수 노출 비중이다.
- 현재 단계는 `release_stage=research_beta`다.

## 주요 파일

- `index_forecast_signal_current.csv`: 기본 소비 파일
- `index_forecast_signal_current.json`: 동일 데이터의 JSON 버전
- `index_forecast_handoff_manifest.json`: asof, readiness, source, output 목록
- `index_forecast_signal_quality_report.json`: 품질검사 결과
- `index_forecast_signal_schema.json`: 기본 schema와 허용값

## 검증 명령

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\validate_index_forecast_handoff.py --expected-asof 2026-05-22
```

정상 조건:

- `ok=true`
- `errors=[]`
- `row_count=12`
