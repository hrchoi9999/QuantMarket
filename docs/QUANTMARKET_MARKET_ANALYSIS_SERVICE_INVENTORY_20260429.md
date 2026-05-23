# QuantMarket 시장 분석 서비스 기획용 데이터 인벤토리

작성일: 2026-04-29  
목적: `시장 분석` 메뉴 기획에 앞서,  
1) 현재 수집/저장 중인 데이터,  
2) 기존 수집기/API로 확장 가능한 데이터,  
3) 추가 수집이 필요한 데이터,  
4) 그 조합으로 제공 가능한 서비스  
를 한 번에 정리한다.

---

## 1. 현재 수집/저장 중인 데이터

현재 QuantMarket은 아래 4개 축의 데이터를 이미 생산하고 있다.

### A. 종가 기반 공식 시장 데이터
- KOSPI / KOSDAQ / KOSPI200 일별 OHLC
- USD/KRW 일별 값
- 금리 수동 seed / carry-forward
- 저장 테이블
  - `market_index_daily`
  - `market_fx_daily`
  - `market_rates_daily`

### B. 종가 기반 시장 특징/점수/상태
- 시장 feature
  - 1일/5일/20일/60일 수익률
  - 20일선/60일선 위 종목 비율
  - 상승/하락 종목 비율
  - 실현변동성 / drawdown
  - 달러 / 금리 / 방어자산 흐름
- 시장 component score
  - trend
  - breadth
  - risk
  - defensive_flow
- 시장 상태 history
  - state_label
  - state_score
  - prev_state
  - state_change_direction
- 저장 테이블
  - `market_features_hourly`
  - `market_component_scores`
  - `market_state_history`
  - `market_state_transition_stats`
  - `market_asset_relative_strength_hourly`

### C. 장중 intraday 참고 데이터
- 장중 index snapshot
  - KOSPI / KOSDAQ / KOSPI200
- 장중 FX snapshot
  - USD/KRW
- 장중 breadth
  - KRX 우선
  - 실패 시 Naver breadth fallback
- 장중 futures snapshot
  - 코스피200 선물
- 장중 flow signal
  - 프로그램
  - 외국인
  - 기관
- 장중 상태 요약
- 저장 테이블
  - `market_intraday_index_snapshot`
  - `market_intraday_fx_snapshot`
  - `market_intraday_breadth`
  - `market_intraday_futures_snapshot`
  - `market_intraday_flow_signal`
  - `market_intraday_state`

### D. 야간 / 다음 거래일 preview 데이터
- 미국 상장 한국 ETF
  - `EWY`
- 미국 선물
  - `ES=F`
  - `NQ=F`
- USD/KRW
- WTI
- 미국 10년 금리
- Google News RSS 기반 overnight risk headline
- next-day preview score / label / supporting_points / risk_points
- 저장 테이블
  - `market_overnight_asset_snapshot`
  - `market_overnight_news_context`
  - `market_next_day_preview_state`

### E. 공개 handoff / history payload
- current payload
  - `quantservice_market_home.json`
  - `quantservice_market_today.json`
  - `quantservice_market_page.json`
  - `quantservice_market_timeline.json`
  - `quantservice_market_asset_strength.json`
  - `quantservice_market_state_transition.json`
  - `quantservice_market_next_day_preview.json`
- history payload
  - `quantservice_market_timeline_history.json`
  - `quantservice_market_asset_strength_history.json`
  - `quantservice_market_state_transition_history.json`
  - `quantservice_market_next_day_preview_history.json`

---

## 2. 현재 코드/기존 API로 이미 수집 가능한 정보

이 항목은 “새로운 외부 계약 없이, 지금 코드에 있는 수집기 또는 이미 쓰는 라이브러리로 확장 가능한 범위”다.

### A. KRX / FinanceDataReader 축
- KOSPI / KOSDAQ / KOSPI200 종가
- KRX 장중 breadth 보조 데이터
- 추가 확장 가능
  - 업종 지수
  - 테마 지수
  - 추가 KRX 파생 지수

### B. Yahoo chart 축
- 한국 지수 장중 시세
- 미국 선물
- 미국 주요 지수 프록시
- 원달러
- 유가
- 미국 10년 금리
- 추가 확장 가능
  - S&P500 / NASDAQ / DOW / RUSSELL
  - VIX
  - DXY 성격의 대체 프록시
  - 섹터 ETF

### C. Naver 금융 축
- 시장 전체 종목 breadth fallback
- 코스피200 선물
- 프로그램 매매
- 외국인/기관 수급
- 추가 확장 가능
  - 업종별 등락 지도
  - 거래대금 상위
  - 시가총액 상위
  - 급등/급락 종목 집계

### D. Google News RSS 축
- 시장 분위기 뉴스
- overnight risk headline
- 지정 키워드 기반 risk event 수집
- 추가 확장 가능
  - FOMC / CPI / 전쟁 / 유가 / 환율 키워드 분리
  - US / KR market context 분리 정교화

### E. Quant read-only 축
- breadth 계산용 주식 universe
- 대표 ETF 기반 방어자산/금/인버스 흐름
- regime score
- 추가 확장 가능
  - 섹터 breadth
  - 스타일별 강도
  - ETF 회전 신호

---

## 3. 아직 추가 수집이 필요한 정보

이 항목은 `시장 분석` 메뉴를 풍성하게 만들기 위해 새로 붙여야 하는 영역이다.

### A. DART 공시 데이터
현재 QuantMarket에는 DART 수집기가 없다.

필요 데이터 예시:
- 일별 공시 건수
- 실적 공시
- 유상증자 / CB / BW
- 자사주 취득/처분
- 최대주주 지분변동
- 투자주의 / 관리종목 / 상장폐지 관련 공시

이걸로 가능한 서비스:
- 공시 이벤트 heatmap
- 시장 리스크 공시 흐름
- 업종/시총별 공시 강도 비교

### B. KRX 상세 시장 구조 데이터
현재는 핵심 지수/폭넓은 breadth 수준까지만 있음.

추가 필요:
- 업종별 지수
- 업종별 거래대금
- 시총 구간별 강도
- 52주 신고가/신저가 상세
- 투자자별 순매수 세부 breakdown

이걸로 가능한 서비스:
- 업종 rotation board
- 대형/중형/소형 상대강도
- 내부 확산 맵

### C. 미국시장 정식 패널 데이터
현재는 Yahoo 기반 proxy 성격이 강함.

추가 필요:
- 미국 주요 지수 일별 정식 패널
- 섹터 ETF
- VIX
- Treasury term spread
- 달러인덱스
- macro calendar

이걸로 가능한 서비스:
- 미국시장 대시보드
- KR 증시와 US 위험선호 연동 패널
- 글로벌 risk-on / risk-off 모니터

### D. 기업/실적/펀더멘털 축
현재 QuantMarket은 시장 상태 중심이다.

추가 필요:
- 실적 발표 일정
- EPS surprise
- valuation snapshot
- 배당/자사주/소각 이벤트

이걸로 가능한 서비스:
- 시장 분석 + 펀더멘털 연결 화면
- 실적 시즌 리스크 지도

### E. 뉴스 정규화 / 이벤트 분류
현재는 headline 수집과 risk keyword 정도다.

추가 필요:
- 이벤트 분류 체계
  - 지정학
  - 통화정책
  - 물가
  - 실적
  - 규제
- 뉴스 중요도 점수
- 이벤트 시계열

이걸로 가능한 서비스:
- 리스크 이벤트 타임라인
- 최근 7일 시장 충격 요인 요약

---

## 4. 데이터 유형별 제공 가능한 서비스

### 1) 현재 데이터만으로 당장 가능한 서비스

#### a. 시장 상태 차트 서비스
- 상태점수 timeline
- trend / breadth / risk / defensive_flow 분해 차트
- 상태 전이 이력

#### b. 자산 강도 대시보드
- KOSPI / KOSDAQ / GOLD / BOND / USDKRW / INVERSE 상대강도
- 최근 20일 수익률 비교
- strength rank 변화

#### c. 장중 참고 보드
- 오늘 장중 흐름
- 선물/수급/환율/장중 breadth
- 장중 상태와 종가 기반 상태 비교

#### d. 내일 시장 전망 참고
- 야간 선물 / 미국장 / 환율 / 유가 / 미10년
- overnight preview history

### 2) 기존 API 확장만으로 가능한 서비스

#### a. KRX + Naver 기반 시장 모니터
- 업종 강도 보드
- 거래대금 상위 섹터
- 신고가/신저가 breadth panel

#### b. Yahoo 기반 글로벌 연결 대시보드
- 미국 주요 지수/선물/금리/유가/금 통합 패널
- KR-US 연동 비교 차트

#### c. 뉴스 컨텍스트 보드
- 최근 headline 흐름
- risk keyword 빈도
- overnight risk timeline

### 3) 추가 수집이 들어가야 가능한 서비스

#### a. DART 공시 분석 서비스
- 오늘의 주요 공시
- 리스크 공시 캘린더
- 실적/자금조달/자사주 이벤트 흐름

#### b. 업종 / 스타일 / 시총 구조 분석
- 업종 rotation map
- 대형/중형/소형 강도
- 성장/가치/배당 스타일 비교

#### c. 미국시장 정식 분석 화면
- US macro dashboard
- sector ETF rotation
- volatility regime panel

---

## 5. 우선순위 제안

### 우선순위 A: 지금 바로 서비스화 가능
- 시장 상태 차트
- 자산 강도 차트
- 상태 전이 차트
- 내일 시장 전망 참고 차트
- 장중 참고 보드 일부 공개 여부 검토

### 우선순위 B: 기존 수집기 확장으로 빠르게 가능
- KRX 업종/거래대금 panel
- Naver 업종 breadth / 시장 내부 강도 보드
- Yahoo 글로벌 연동 panel

### 우선순위 C: 새 수집기 개발 필요
- DART 공시 분석
- 뉴스 이벤트 분류 엔진
- 미국시장 정식 macro/sector 패널

---

## 6. 추천 서비스 묶음

### 서비스 1. `시장 브리핑`
- 현재처럼 해석형 요약 유지

### 서비스 2. `시장 분석`
- 차트/데이터형 대시보드
- 현재 데이터만으로 1차 오픈 가능

### 서비스 3. `공시/이벤트 분석`
- DART 중심
- 2차 개발

### 서비스 4. `글로벌 연동 분석`
- 미국시장 / 환율 / 금리 / 유가
- 2차~3차 개발

---

## 7. 한 줄 결론

지금 이미 쌓여 있는 데이터만으로도  
`시장 상태 / 자산 강도 / 상태 전이 / 야간 전망` 중심의 `시장 분석` 메뉴 1차 서비스는 충분히 가능하다.

그 다음 고도화의 핵심은

- `DART 공시`
- `KRX 업종/시장구조`
- `미국시장 정식 패널`
- `뉴스 이벤트 분류`

이 4축을 추가하는 것이다.
