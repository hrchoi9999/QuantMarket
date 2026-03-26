# QUANTMARKET_P1_NUMERIC_MARKET_ANALYSIS_TASK_20260323.md

## 1. 작업명

P1 정량 시장분석 데이터 생성
(`D:\Quant`의 기존 DB를 읽어 `QuantMarket`에서 시장분석용 정량 데이터를 생성)

## 2. 목표

이번 P1의 목표는 `D:\Quant`에 이미 존재하는 DB/원천 데이터를 읽어서, `D:\QuantMarket` 안에서 시장분석용 정량 데이터를 생성할 수 있게 만드는 것이다.

즉 이번 단계는:

- `Quant` 데이터를 읽는다
- `QuantMarket`에서 계산한다
- `QuantMarket` DB와 payload를 만든다
- `D:\Quant`는 절대 수정하지 않는다

## 3. 절대 원칙

1. `D:\Quant`는 읽기 전용
2. `D:\QuantMarket`에서만 구현/계산/저장
3. `D:\Quant` DB schema 수정 금지
4. `D:\Quant` 파일 overwrite 금지
5. 필요 데이터는 read-only query로만 가져올 것

## 4. 이번 P1에서 읽을 기존 데이터

### A. price.db

경로:
- `D:\Quant\data\db\price.db`

목적:
- ETF/주식 가격 기반 breadth 계산
- 대표 ETF 상대강도 계산
- 변동성/낙폭 계산

읽을 대상 예:
- `prices_daily`
- `instrument_master`
- `etf_meta`

### B. regime.db

경로:
- `D:\Quant\data\db\regime.db`

목적:
- 기존 regime 상태를 참고 feature로 활용 가능
- 단, 시장상태 메인 라벨은 별도로 계산

읽을 대상 예:
- `regime_history`

### C. 기타 reference

- `D:\Quant\data\universe\...`
- 대표 ETF / universe 파일들

## 5. 이번 P1에서 QuantMarket 안에 만들 것

### 코드 경로 제안

- `D:\QuantMarket\src\collectors\market\...`
- `D:\QuantMarket\src\features\market\...`
- `D:\QuantMarket\src\pipelines\run_market_analysis_pipeline.py`
- `D:\QuantMarket\src\publishers\build_market_analysis_snapshots.py`

### DB 경로 제안

- `D:\QuantMarket\data\db\market_analysis.db`

### payload 경로 제안

- `D:\QuantMarket\service_platform\web\public_data\current\market_analysis_summary.json`
- `D:\QuantMarket\service_platform\web\public_data\current\market_analysis_detail.json`
- `D:\QuantMarket\service_platform\web\public_data\current\market_analysis_manifest.json`

## 6. P1 정량 데이터 계산 범위

### A. 공식 시장지표 수집/저장

우선 구현:
- KOSPI (`1001`)
- KOSDAQ (`2001`)
- KOSPI200 (`1028`)
- USD/KRW
- 주요 금리 series

### B. 내부 정량 feature 생성

우선 구현:
- 코스피 1D / 5D / 20D / 60D 수익률
- 코스닥 1D / 5D / 20D / 60D 수익률
- 20일선 위 종목 비율
- 60일선 위 종목 비율
- 상승 종목 / 하락 종목 비율
- 신고가 / 신저가 수
- 최근 20일 변동성
- 최근 5일 / 20일 최대 낙폭
- 달러 / 금 / 채권 / 인버스 상대강도

### C. 구성 점수

- `trend_score`
- `breadth_score`
- `risk_score`
- `defensive_flow_score`
- `total_score`
- `state_label`

## 7. 산출 목표

P1 완료 시 아래가 가능해야 한다.

1. `D:\Quant`의 DB를 읽어 시장분석 정량 데이터 생성
2. `D:\QuantMarket`에 독립 DB 저장
3. 7단계 시장상태 산출
4. 웹서비스용 summary/detail payload 생성
5. 향후 AI 해설 입력으로 사용할 structured snapshot 확보

## 8. 우선 구현 순서

1. `market_analysis.db` 초기 스키마 생성
2. 공식 시장지표 수집기 작성
3. `D:\Quant` read-only adapter 작성
4. breadth / volatility / relative strength 계산기 작성
5. 상태 점수 계산기 작성
6. summary/detail payload 생성기 작성
7. validate 스크립트 작성

## 9. 완료 기준

1. `D:\Quant`를 수정하지 않는다.
2. `D:\QuantMarket`에서 정량 시장분석 데이터가 독립 생성된다.
3. summary/detail payload가 생성된다.
4. QuantService가 이후 직접 소비 가능한 구조가 된다.
