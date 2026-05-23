# Kiwoom REST Market Data Collection

작성일: 2026-05-19

## 목적

KRX 자동 수집은 로그인 세션 제약이 커서 운영 안정성이 낮다.  
따라서 QuantMarket의 국내 시장 수급성 데이터는 Kiwoom REST API를 우선 원천으로 사용한다.

## 적용 범위

- Kiwoom REST 인증 키는 `D:\Quant\config`에서 read-only로 읽는다.
- 키 파일 값은 DB, payload, report, log에 저장하지 않는다.
- QuantMarket 산출물과 DB 저장은 모두 `D:\QuantMarket` 안에서만 수행한다.

## 1차 구현

- 신규 수집 스크립트:
  - `D:\QuantMarket\collect_kiwoom_investor_flows.py`
- 신규 수집 모듈:
  - `D:\QuantMarket\src\quantmarket_market\kiwoom_investor_flow_collector.py`
- 사용 TR:
  - `ka10059`
- 대상 universe:
  - 기본값 `D:\Quant\data\universe\universe_mix_top400_latest.csv`
- 저장 DB:
  - `D:\QuantMarket\data\db\market_analysis.db`
- 저장 테이블:
  - `kiwoom_stock_investor_flow_daily`
  - `market_investor_flow_daily`
  - `market_source_collection_status`

## 산출 방식

- 종목별 투자자 수급을 수집한다.
- 주요 투자자:
  - 외국인
  - 기관합계
  - 개인
- 종목별 수급을 KOSPI, KOSDAQ, ALL 단위로 합산한다.
- 시장 합산값은 KRX 전체시장 공식값이 아니라 top universe 기반 proxy다.
- `source_status='proxy_top_universe'`로 명시한다.

## Mart 반영

`domestic_flow_derivatives_daily`는 아래 순서로 데이터를 사용한다.

1. QuantMarket 직접 수집 Kiwoom REST 데이터
2. 기존 Quant read-only `ai_feature_ext.db` 데이터
3. 장중 flow fallback

신규 feature version:

- `qm_domestic_flow_derivatives_v2_kiwoom_qm_20260519`

## 실행 예시

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\collect_kiwoom_investor_flows.py --start 2026-05-18 --end 2026-05-19 --sleep 0.03
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\build_domestic_flow_derivatives_daily.py
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\build_market_model_input_mart.py
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\build_market_forecast_ai_calibration.py
```

## 2026-05-19 검증

- Kiwoom REST full universe 수집 성공
- universe count: 400
- saved rows: 10,400
- error count: 0
- `domestic_flow_derivatives_daily_current.csv` 재생성 완료
- `market_model_input_daily_current.csv` 재생성 완료
- `market_forecast_ai_calibrated_daily_current.csv` 재생성 완료
- Quant model handoff manifest 갱신 완료

## 운영 주의

- `--limit` 옵션은 API 테스트용이다.
- `--limit` 실행 시 시장 합산값은 저장하지 않는다.
- 운영 수집은 limit 없이 실행한다.
- KRX official collector는 optional 보조 원천으로만 유지한다.
