QS 요청 제출처: QS-Master
권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
공개 반영 포함 여부: Yes
Admin only 여부: No
관련 시스템: QuantMarket

작업명:
시장 분석 메뉴 내 DART 공시 요약 패널 및 히스토리 차트 반영 요청

배경:
- QuantMarket에서 OpenDART 기반 공개형 시장 공시 요약 payload를 실제 데이터로 생산하기 시작했습니다.
- 이번 요청은 DART 데이터를 `시장 분석` 메뉴 안에서 공개형 데이터 패널로 노출하기 위한 QS 구현 요청입니다.
- 본 데이터는 특정 종목 추천이나 개별 자문 목적이 아니라, 시장 전반의 공시 흐름을 참고용으로 보여주는 공개형 정보입니다.

QuantMarket upstream 완료 상태:
1. current payload
- `quantservice_market_dart_summary.json`
- `api_v1_market_analysis_dart_summary.json`

2. history payload
- `quantservice_market_dart_summary_history.json`
- `api_v1_market_analysis_dart_summary_history.json`

3. 공개 URL
- current:
  - `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current/quantservice_market_dart_summary.json`
- history:
  - `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/history/quantservice_market_dart_summary_history.json`

4. 현재 payload 의미
- `reference_date`: 공시 기준일
- `filing_count_total`: 기준일 전체 공시 건수
- `market_breakdown.kospi_count`: 유가증권시장 공시 건수
- `market_breakdown.kosdaq_count`: 코스닥시장 공시 건수
- `risk_event_count`: 리스크 성격 공시 건수
- `filing_count_by_type[]`: 유형별 공시 건수
- `highlights[]`: 주요 공시 예시
- `recent_filings[]`: 최근 공시 목록

5. history series row 의미
- `asof`
- `reference_date`
- `filing_count_total`
- `kospi_count`
- `kosdaq_count`
- `risk_event_count`
- `funding_count`
- `shareholder_count`
- `earnings_count`
- `governance_count`
- `general_count`
- `type_counts[]`

반영 요청:
1. `시장 분석` 메뉴 안에 `DART 공시 흐름` 패널을 추가해 주세요.
2. current payload를 사용해 아래 정보를 카드/표 형식으로 노출해 주세요.
- 공시 기준일
- 전체 공시 건수
- 코스피 / 코스닥 공시 건수
- 리스크 공시 건수
- 유형별 공시 건수
3. history payload를 사용해 아래 차트를 추가해 주세요.
- 일자별 전체 공시 건수 추이
- 일자별 리스크 공시 건수 추이
4. `highlights[]`는 `주요 공시 예시` 블록으로 3~5건 정도 보여 주세요.
5. `recent_filings[]`는 최근 공시 목록으로 보여 주되, 종목 추천처럼 보이지 않게 공시 제목 중심으로 표시해 주세요.
6. 공시 원문 링크가 있으면 새 창으로 연결하되, 링크 라벨은 `공시 원문 보기`처럼 중립적으로 표시해 주세요.

UI 원칙:
- `시장 브리핑`의 해석형 UI와 다르게, `시장 분석`에서는 데이터 패널형으로 표현
- 공시 건수 증감이 곧 투자판단 신호처럼 보이지 않게 표현
- `리스크 공시`는 의미를 설명하되, 과도한 경고 UI나 공포형 표현은 지양
- 40~60대 사용자도 읽기 쉽게 제목, 범례, 단위, 기준일을 명확히 표기

표현 가이드:
- 권장 제목: `DART 공시 흐름`
- 보조 설명 예시:
  - `상장사 공시 흐름을 OpenDART 기준으로 정리한 공개형 참고 정보입니다.`
  - `공시 건수는 시장 상황 이해를 돕는 참고 지표이며, 특정 종목의 매수·매도 판단을 직접 제시하지 않습니다.`

Fallback 규칙:
- current payload의 `enabled=false`이면 패널 대신 안내 문구를 표시
- history payload의 `series=[]`이면 차트 영역에는 `히스토리 데이터 축적 중` 안내를 표시
- payload 누락 시 페이지 전체가 깨지지 않도록 안전하게 skip 처리

완료 기준:
1. `시장 분석` 메뉴에서 DART 공시 흐름 패널이 노출됨
2. current payload 기준 요약 정보가 정상 표시됨
3. history payload 기준 차트가 정상 표시됨
4. 공시 원문 링크와 최근 공시 목록이 무리 없이 노출됨
5. 공개형 비자문 표현 원칙을 유지함
