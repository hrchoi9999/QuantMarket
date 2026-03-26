# QuantMarket 작업 시작 문서 (2026-03-23)

## 목적

이 작업공간은 Redbot/QuantService용 시장분석 기능을 위한 전용 개발 공간이다.
기존 `D:\Quant`의 포트폴리오/백테스트 중심 작업과 분리해서 아래를 담당한다.

- 공식 시장데이터 수집
- 시장분석 feature 계산
- 7단계 시장상태 산출
- 정량/정성 시장분석 payload 생성
- 시장분석 전용 오케스트레이션 설계 및 구현
- 향후 미국시장(`US`) 확장

## 최우선 안정성 원칙

### 1. `D:\Quant`는 참조 전용이다.

이 작업공간에서 `D:\Quant`는 아래 용도로만 사용한다.

- 기존 설계 문서 읽기
- 기존 코드 구조 참고
- 기존 DB/CSV/snapshot 구조 확인
- 공식/보조 데이터 구조 비교

### 2. `D:\Quant`는 절대 수정하지 않는다.

시장분석 개발은 `D:\QuantMarket` 안에서만 수행한다.
다음 행위는 금지한다.

- `D:\Quant` 내 코드 수정
- `D:\Quant` 내 DB 스키마 변경
- `D:\Quant` 내 문서 수정
- `D:\Quant` 내 오케스트레이션 변경
- `D:\Quant` 내 산출물 overwrite

필요한 경우에도 먼저 `D:\QuantMarket`에서 독립 구현/검증을 하고, 이후 별도 승인된 통합 단계에서만 반영 여부를 결정한다.

### 3. 개발 산출물은 모두 `D:\QuantMarket`에 둔다.

예:

- 코드: `D:\QuantMarket\src\...`
- 문서: `D:\QuantMarket\docs\...`
- DB: `D:\QuantMarket\data\db\...`
- snapshot: `D:\QuantMarket\service_platform\...`
- 테스트 산출물: `D:\QuantMarket\reports\...`

## 작업 원칙

1. 이 작업은 `QuantService`가 아니라 `Quant` 성격의 데이터/모델 작업이다.
2. 기존 `D:\Quant` 메인 쓰레드의 포트폴리오 모델 개발과 분리해서 진행한다.
3. 메인 축은 공식 시장지표(KOSPI/KOSDAQ/KOSPI200/환율/금리)다.
4. 내부 breadth와 ETF 상대강도는 보조지표로 사용한다.
5. 정성 분석은 뉴스 나열보다 데이터 기반 해설을 우선한다.
6. AI는 판단기가 아니라 설명 생성기로 사용한다.
7. 처음부터 `KR / US` 다중 시장 확장이 가능하도록 설계한다.

## 반드시 참고할 원문 문서 (읽기 전용, 수정 금지)

- `D:\Quant\docs\MARKET_ANALYSIS_OFFICIAL_DATA_AND_AI_DESIGN_P0_20260323.md`
- `D:\Quant\docs\TASK_13_MARKET_ANALYSIS_PIPELINE_P0_20260323.md`
- `D:\Quant\docs\MARKET_ANALYSIS_DATA_MODEL_20260323.md`
- `D:\Quant\docs\MARKET_ANALYSIS_WEB_PAYLOAD_SPEC_20260323.md`

## 우선 구현 범위 (P0)

1. 공식 시장데이터 수집 구조 정리
   - KOSPI(1001)
   - KOSDAQ(2001)
   - KOSPI200(1028)
   - USD/KRW
   - 기준금리 / CD91 / 국고채 3Y / 국고채 5Y

2. 저장 구조 설계
   - market_analysis.db
   - market_index_daily
   - market_fx_daily
   - market_rates_daily
   - market_features_hourly
   - market_component_scores
   - market_state_history
   - market_analysis_payload
   - market_analysis_ai_notes

3. 시장 상태 점수화
   - trend_score
   - breadth_score
   - risk_score
   - defensive_flow_score
   - total_score
   - 7단계 상태 라벨

4. 웹서비스용 payload 생성
   - market_analysis_summary.json
   - market_analysis_detail.json
   - market_analysis_manifest.json

5. 별도 오케스트레이션 설계
   - run_market_analysis_pipeline.py
   - 초기 1시간 간격 실행 기준

## 사용자에게 보여줄 핵심 구성

### 메인페이지
- 오늘 시장 상태
- 한 줄 요약
- 전일 대비 변화
- 핵심 신호 2개

### 오늘의 추천 페이지
- 시장 상태 요약
- 추천 모델과 연결된 설명
- 대응 가이드 한 줄

### 시장 분석 페이지
- 7단계 상태
- 시장 방향
- 시장 건강도
- 시장 흔들림
- 방어자산 선호도
- 긍정 요인
- 주의 요인
- 대응 가이드
- 선택적 AI 해설

## 성격 구분

- `D:\Quant`
  - 포트폴리오 모델 / 백테스트 / publish
  - 읽기 전용 참조 소스
- `D:\QuantMarket`
  - 시장 분석 / 공식 시장데이터 / 시장상태 / 시장분석 payload
  - 실제 개발 작업 공간
- `D:\QuantService`
  - UI / 페이지 / API 소비 / 렌더링

## 다음 시작 작업 제안

1. `D:\QuantMarket` 프로젝트 구조 생성
2. 공식 시장데이터 수집 모듈 골격 작성
3. `market_analysis.db` 초기 스키마 작성
4. KR 시장 P0 feature 계산기 작성
5. 웹 payload 샘플 생성
