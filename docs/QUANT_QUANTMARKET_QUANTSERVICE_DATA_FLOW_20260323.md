# QUANT_QUANTMARKET_QUANTSERVICE_DATA_FLOW_20260323.md

## 1. 목적

이 문서는 `Quant`, `QuantMarket`, `QuantService` 3개 작업축 사이의 데이터 전달 구조를 정의한다.

핵심 원칙은 다음과 같다.

1. 포트폴리오/백테스트 데이터는 `Quant`가 책임진다.
2. 시장분석/공식 시장데이터는 `QuantMarket`이 책임진다.
3. `QuantService`는 화면/UI/API 소비 계층이며 계산 책임을 갖지 않는다.
4. `Quant`와 `QuantMarket`은 서로의 결과를 참조할 수 있지만, 각자 자신의 도메인 데이터를 직접 publish 한다.

---

## 2. 역할 분리

### A. Quant

담당 범위:

- 포트폴리오 모델
- 백테스트
- 모델 성능평가
- 사용자용 포트폴리오 payload
- user report / portfolio snapshot
- quant_service.db / quant_service_detail.db

대표 산출물:

- 포트폴리오 추천 데이터
- 모델 성능 데이터
- holdings / changes / recommendation payload

### B. QuantMarket

담당 범위:

- 공식 시장데이터 수집
- 시장 feature 계산
- 7단계 시장상태 산출
- 시장분석 정량/정성 payload
- 시장분석 전용 DB / snapshot / API

대표 산출물:

- market analysis summary
- market analysis detail
- market state history
- AI-assisted market commentary

### C. QuantService

담당 범위:

- UI / 페이지 / 렌더링
- 데이터 adapter
- stale-data 처리
- Quant / QuantMarket payload 소비

주의:

- QuantService는 포트폴리오 계산을 하지 않는다.
- QuantService는 시장상태 계산을 하지 않는다.
- QuantService는 수치를 재계산하지 않는다.

---

## 3. 권장 데이터 전달 구조

### 3-1. 포트폴리오 데이터 흐름

`Quant` -> `QuantService`

권장 소스:

- `D:\Quant\service_platform\web\public_data\current\user_model_catalog.json`
- `D:\Quant\service_platform\web\public_data\current\user_recommendation_report.json`
- `D:\Quant\service_platform\web\public_data\current\user_performance_summary.json`
- `D:\Quant\service_platform\web\public_data\current\user_recent_changes.json`
- 또는 `Quant` API

### 3-2. 시장분석 데이터 흐름

`QuantMarket` -> `QuantService`

권장 소스:

- `D:\QuantMarket\service_platform\web\public_data\current\market_analysis_summary.json`
- `D:\QuantMarket\service_platform\web\public_data\current\market_analysis_detail.json`
- `D:\QuantMarket\service_platform\web\public_data\current\market_analysis_manifest.json`
- 또는 `QuantMarket` API

### 3-3. Quant 와 QuantMarket 사이의 관계

`QuantMarket`은 초기 P1 단계에서 `Quant`의 데이터를 읽어 시장분석 정량 feature를 만드는 것을 허용한다.

단, 원칙은 아래와 같다.

- `D:\Quant`는 읽기 전용 참조
- `D:\QuantMarket`이 직접 계산/저장/발행
- 결과 publish는 `QuantMarket`이 책임짐

즉 시장분석 데이터는 `Quant` API를 재사용하는 것이 아니라, `QuantMarket`이 직접 DB와 payload를 만들고 `QuantService`에 전달하는 구조가 맞다.

---

## 4. 인터페이스 원칙

### 4-1. QuantService가 기대해야 하는 것

- 포트폴리오 데이터는 `Quant`에서 받음
- 시장분석 데이터는 `QuantMarket`에서 받음
- 두 소스는 독립적일 수 있음
- UI 계층에서는 동일한 adapter 규격으로 흡수하는 것이 좋음

### 4-2. API / snapshot 형태

권장 방식:

- 초기: JSON snapshot 기반
- 이후: HTTP API로 전환

즉 처음에는 파일로 개발해도 좋고, response shape를 그대로 HTTP endpoint로 올릴 수 있게 만든다.

---

## 5. QuantService 연동 권장 방식

### 옵션 A. 두 소스를 직접 소비

- Quant snapshot/API
- QuantMarket snapshot/API

장점:
- 구현이 단순

단점:
- 프론트/서비스 계층이 2개 소스를 직접 알아야 함

### 옵션 B. QuantService adapter/backend 계층에서 통합

권장:

- QuantService 내부 adapter/backend가
  - Quant 포트폴리오 데이터
  - QuantMarket 시장분석 데이터
  를 각각 읽고 정리한 후 UI에 전달

장점:
- UI가 원천 출처를 몰라도 됨
- 장기적으로 가장 안정적

---

## 6. 권장 최종 구조

- `Quant`
  - portfolio / backtest / recommendation domain
- `QuantMarket`
  - market analysis / official market data domain
- `QuantService`
  - presentation domain

이 구조를 장기 기준으로 고정하는 것을 권장한다.
