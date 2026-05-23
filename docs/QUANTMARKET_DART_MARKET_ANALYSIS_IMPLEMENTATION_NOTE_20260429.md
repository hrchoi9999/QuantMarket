# QuantMarket DART 시장분석 구현 메모

작성일: 2026-04-29

## 목적
- `시장 분석` 메뉴 확장을 위해 OpenDART 기반 공시 흐름 요약을 QuantMarket이 직접 수집/저장/배포한다.

## 구현 범위

### 1. OpenDART 수집
- 사용 endpoint
  - `https://opendart.fss.or.kr/api/list.json`
- 인증
  - 환경변수 `DART_API_KEY` 우선 사용
  - 대체로 `OPENDART_API_KEY`도 허용
- 조회 조건
  - `corp_cls=Y` 유가
  - `corp_cls=K` 코스닥
  - 최근 3일 범위 검색
  - `last_reprt_at=Y`

### 2. 저장 테이블
- `market_dart_disclosure_event`
  - 최신 기준일 공시 개별 row 저장
- `market_dart_summary_state`
  - 공시 건수/유형별 건수/리스크 건수/하이라이트 요약 저장

### 3. 공개 payload
- `quantservice_market_dart_summary.json`
- `api_v1_market_analysis_dart_summary.json`
- `quantservice_market_dart_summary_history.json`
- `api_v1_market_analysis_dart_summary_history.json`

## 현재 분류 체계
- 리스크 공시
- 자금조달
- 지분/자사주
- 실적/정기보고
- 지배구조/의사결정
- 일반 공시

## 현재 리스크 키워드 예시
- 관리종목
- 상장폐지
- 영업정지
- 횡령 / 배임
- 회생절차 / 파산
- 감사의견
- 소송
- 부도
- 거래정지
- 실질심사
- 상장적격성
- 이의신청

## 현재 payload 핵심 필드
- `reference_date`
- `filing_count_total`
- `market_breakdown`
  - `kospi_count`
  - `kosdaq_count`
- `risk_event_count`
- `filing_count_by_type`
- `highlights`
- `recent_filings`

## 운영 원칙
- DART는 `official` 계층으로 취급
- 공시 자체를 투자판단 권유로 표현하지 않음
- 공개형 참고 정보로만 노출
- 수집 실패 시 최신 저장 요약 또는 비활성 상태로 fallback

## 현재 한계
- 공시 유형 분류는 `report_nm` 키워드 기반 1차 규칙이다
- 아직 업종/시가총액 bucket 요약은 없음

## 다음 개선 후보
1. 리스크 공시 세부 severity 규칙 보강
2. 업종/시총 bucket 매핑 추가
3. 주요 공시 유형별 상세 drilldown payload 추가
4. 공시 유형별 주간/월간 집계 보드 추가
