# QuantService UI Market Analysis Integration Task Prompt (2026-03-23)

## 작업 목적
`QuantService` 웹서비스가 `QuantMarket`이 생성한 시장분석 데이터를 실제 페이지와 API에 반영하도록 UI/라우팅/데이터 로더를 구현한다.

이번 작업은 단순 데이터 표시가 아니라, 아래 3가지를 동시에 만족해야 한다.
- `redbot.co.kr` 상단 메뉴 구조 개편
- `시장분석` 전용 페이지 신설 및 실제 시장분석 데이터 연결
- `홈` / `오늘의 추천` 페이지에 시장분석 요약 정보 자연스럽게 삽입

## 작업 대상 워크스페이스
- `D:\QuantService`

## 연동 원칙
1. `QuantMarket`는 시장분석 데이터의 생산자다.
2. `QuantService`는 UI / 표시 / 사용자 응답 계층만 담당한다.
3. 개발단계에서는 `API 호출`보다 `handoff JSON 읽기`를 우선 사용한다.
4. `QuantService`는 아래 handoff 경로의 JSON을 읽어 화면과 API를 구성한다.

## QuantMarket handoff 입력 경로
로컬 개발 기준 시장분석 handoff 경로:
- `D:\QuantService\service_platform\web\public_data\market_analysis\current`

해당 폴더에 제공되는 파일:
- `quantservice_market_home.json`
- `quantservice_market_today.json`
- `quantservice_market_page.json`
- `quantservice_market_manifest.json`
- `api_v1_market_analysis_home.json`
- `api_v1_market_analysis_page.json`
- `api_v1_market_analysis_summary.json`
- `api_v1_market_analysis_detail.json`
- `api_v1_market_analysis_today_bridge.json`

가장 우선적으로 사용할 파일:
- 홈 요약: `quantservice_market_home.json`
- 오늘의 추천 요약: `quantservice_market_today.json`
- 시장분석 상세 페이지: `quantservice_market_page.json`
- freshness / 파일구성 / 연결규약 확인: `quantservice_market_manifest.json`

## 반드시 반영할 메뉴 개편
현재 상단 메뉴를 아래 순서로 변경한다.
- `홈`
- `시장분석`
- `오늘의 추천`
- `성과`
- `변경내역`
- `의견보내기`
- `로그인`

구현 원칙:
- 메뉴 순서는 반드시 위 순서를 따른다.
- 메뉴명은 한글 기준으로 통일한다.
- 데스크톱과 모바일 모두 동일한 정보 구조를 유지한다.
- 현재 존재하는 `상태` 메뉴는 제거한다.

## 상태 페이지 처리 원칙
기존 상단 메뉴 `상태`에 있던 페이지 내용은 삭제하지 말고, 그 내용을 `변경내역` 페이지 상단으로 이동 배치한다.

구현 원칙:
- 기존 상태 페이지의 운영/배포/스냅샷 상태 정보는 유지한다.
- 해당 상태 카드 또는 상태 배너를 `변경내역` 페이지 최상단에 먼저 보여 준다.
- 그 아래에 기존 변경내역 리스트/표/카드를 이어서 배치한다.
- 사용자가 "현재 시스템 상태 + 최근 변경내역"을 한 화면에서 순서대로 이해할 수 있어야 한다.

권장 순서:
1. 페이지 제목
2. 상태 요약 카드 또는 상태 배너
3. 기준일/업데이트 시각/경고 여부
4. 최근 변경내역 리스트

## 시장분석 페이지 작업 목표
새로운 `시장분석` 메뉴에서 `QuantMarket`의 정량 시장분석 데이터를 상세하게 볼 수 있도록 페이지를 구성한다.

핵심 원칙:
- 데이터는 정량 시장분석 중심으로 보여 준다.
- AI 냄새가 나는 추상 문구보다 숫자와 짧은 해설을 같이 보여 준다.
- 40~60대 사용자가 한 번에 읽기 쉽게 여백, 글자 크기, 시각적 위계를 분명하게 잡는다.
- 복잡한 차트 남발보다 카드/리스트/요약 블록 중심으로 설계한다.

## 시장분석 페이지 권장 정보 구조
`quantservice_market_page.json` 기준으로 아래 순서를 따른다.

### 1. 페이지 헤더 영역
목적:
- 사용자가 현재 시장상태를 첫 화면에서 즉시 이해하게 한다.

표시 요소:
- 페이지 제목: `시장분석`
- 기준 시각 (`asof`)
- 시장상태 라벨 (`header_state.label`)
- 상태 점수 (`header_state.score`)
- 이전 상태 대비 변화 (`header_state.prev_label`, `header_state.change_direction`)
- 한 줄 요약 (`summary_line` 또는 equivalent text)

UI 가이드:
- 상태 라벨은 크고 굵게 표시한다.
- 숫자 점수는 보조 정보로 두되 너무 작지 않게 배치한다.
- 기준시각은 회색 보조텍스트로 표시한다.
- 빨강/초록만으로 의미를 전달하지 말고 텍스트 라벨을 함께 둔다.

### 2. 핵심 해석 카드 영역
목적:
- 시장을 구성하는 4개 핵심 축을 쉽게 읽게 한다.

데이터 소스:
- `component_cards`

권장 카드 항목:
- 시장 방향
- 시장 건강도
- 시장 흔들림
- 방어자산 선호도

카드 구성:
- 항목명
- score
- 1~2문장 summary

UI 가이드:
- 카드 4개를 데스크톱 2x2, 모바일 1열로 배치한다.
- 카드 안 텍스트 크기는 최소 16px 이상을 기본으로 검토한다.
- score는 숫자만 던지지 말고 옆에 상태감 텍스트를 같이 두는 편이 좋다.
- 카드 간 간격을 넉넉히 두고, 얇은 테두리 또는 밝은 배경으로 구분한다.

### 3. 긍정/주의 신호 영역
목적:
- 사용자가 지금 시장에서 무엇이 괜찮고 무엇을 조심해야 하는지 빠르게 알게 한다.

데이터 소스:
- `signal_lists.positive_points`
- `signal_lists.warning_points`
- `signal_lists.action_guide`

권장 배치:
- 좌측: 긍정 신호
- 우측: 주의 신호
- 하단: 대응 가이드

UI 가이드:
- 문장을 1줄 또는 2줄 길이로 유지한다.
- bullet list는 짧고 명확하게 쓴다.
- 대응 가이드는 별도 강조 박스로 빼서 보여 준다.

### 4. 주요 지표 상세 영역
목적:
- 숫자를 보고 싶은 사용자에게 근거를 제공한다.

데이터 소스:
- `metrics`

우선 노출 지표:
- `kospi_20d_ret`
- `kospi_60d_ret`
- `kosdaq_20d_ret`
- `above_20dma_ratio`
- `above_60dma_ratio`
- `adv_dec_ratio`
- `new_high_count`
- `new_low_count`
- `realized_vol_20d`
- `drawdown_20d`
- `usdkrw_20d_ret`
- `rate_cd91_20d_chg`
- `rate_ktb3y_20d_chg`

구성 방식:
- 너무 긴 단일 표 하나로 몰지 말고, 성격별로 2~3개 그룹으로 나눈다.

권장 그룹:
- 지수/추세
- 내부 breadth
- 위험/변동성
- 환율/금리

UI 가이드:
- 표를 쓰더라도 열 수를 과도하게 늘리지 않는다.
- 숫자 오른쪽 정렬, 항목명 왼쪽 정렬을 기본으로 한다.
- 단위와 방향성을 함께 보여 준다.
- 증가/감소 화살표만 믿지 말고 `+/-` 값도 같이 쓴다.

### 5. 데이터 출처 및 업데이트 안내
목적:
- 사용자 신뢰 확보

데이터 소스:
- `data_sources`
- `quantservice_market_manifest.json`

표시 내용:
- 기준 시각
- 생성 주기: 1시간
- 생성 주체: QuantMarket
- 표시 주체: QuantService
- stale 또는 경고 상태가 있으면 상단 또는 하단에 안내

## 홈 페이지 반영 지시
`홈`에서는 시장분석을 상세하게 풀지 말고, 진입 유도형 요약만 보여 준다.

데이터 소스:
- `quantservice_market_home.json`

반드시 포함할 요소:
- 현재 시장상태 라벨
- 한 줄 요약
- 핵심 신호 2개
- 시장분석 페이지로 이동하는 링크 버튼

권장 배치 위치:
- 홈 hero 아래 또는 주요 소개 블록 바로 아래
- 기존 콘텐츠 흐름을 끊지 않는 위치에 배치

권장 섹션 제목 예시:
- `지금 시장은 이렇게 보고 있습니다`
- `오늘의 시장 한눈에 보기`

UI 가이드:
- 작은 요약 카드 또는 가로형 summary section으로 배치
- 홈에서는 숫자 테이블을 길게 노출하지 않는다.
- 클릭하면 `시장분석` 페이지로 자연스럽게 이동하도록 구성한다.

## 오늘의 추천 페이지 반영 지시
`오늘의 추천`에서는 추천 포트폴리오/전략 설명을 방해하지 않도록 시장분석 정보를 브리지 형태로 짧게 넣는다.

데이터 소스:
- `quantservice_market_today.json`

반드시 포함할 요소:
- 현재 시장상태 라벨
- 추천 대응 톤 (`recommended_tone`)
- 짧은 브리지 문구 (`bridge_text`)

권장 배치 위치:
- 페이지 상단 추천 요약 카드 아래
- 또는 전략 추천 블록 바로 위

UI 가이드:
- 한 문단 또는 강조 박스 형태로 짧게 보여 준다.
- 오늘의 추천 핵심 메시지를 밀어내지 않도록 높이를 크게 쓰지 않는다.
- `시장분석 자세히 보기` 링크를 같이 둔다.

## API / Loader 작업 지시
`QuantService` 내부에 시장분석용 loader와 route를 추가한다.

권장 구현 항목:
1. `market_analysis` 전용 data loader 추가
2. `D:\QuantService\service_platform\web\public_data\market_analysis\current` 경로에서 JSON 읽기
3. manifest 기반 freshness / 파일 존재 여부 검증
4. 아래 API route 추가
   - `/api/v1/market-analysis/home`
   - `/api/v1/market-analysis/page`
   - `/api/v1/market-analysis/summary`
   - `/api/v1/market-analysis/detail`
   - `/api/v1/market-analysis/today-bridge`
   - `/api/v1/market-analysis/manifest`
5. 템플릿 렌더링용 view model 구성

주의:
- `QuantService`는 직접 시장분석 계산을 하지 않는다.
- 데이터가 없으면 graceful fallback을 제공한다.
- stale 상태면 마지막 정상 데이터와 경고 문구를 함께 보여 준다.

## 40~60대 사용자 중심 UI 가이드
이번 작업은 일반적인 스타트업풍 UI보다 "읽기 쉬운 정보 전달"을 우선한다.

반드시 지킬 원칙:
- 본문 가독성이 높은 폰트 크기 사용
- 행간을 충분히 확보
- 한 카드 안에 정보 과밀 배치 금지
- 명확한 제목/소제목 구조 사용
- 배경 대비와 텍스트 대비를 충분히 확보
- 의미 없는 장식성 그래픽 최소화
- 복잡한 인터랙션보다 정적인 읽기 흐름 우선
- 모바일에서도 텍스트 끊김과 카드 밀집이 없도록 설계

권장 시각 원칙:
- 핵심 상태 > 해석 카드 > 신호 리스트 > 세부 지표 순으로 시선 흐름 설계
- 1차 정보는 카드/배너/헤더에, 2차 정보는 표/리스트에 배치
- 색상에만 의존하지 말고 라벨/텍스트 병행
- 버튼 문구는 직관적으로 작성

## 구현 우선순위
1. 상단 메뉴 개편
2. 상태 페이지 내용을 변경내역 상단으로 이전
3. 시장분석 loader / route 추가
4. 시장분석 상세 페이지 템플릿 구현
5. 홈 요약 섹션 반영
6. 오늘의 추천 브리지 섹션 반영
7. stale / empty / error fallback 정리
8. 모바일 반응형 정리

## 검증 항목
반드시 확인할 것:
- 상단 메뉴 순서가 정확한가
- `시장분석` 페이지가 handoff JSON으로 정상 렌더링되는가
- `홈`과 `오늘의 추천`에 시장분석 요약이 중복 과다 없이 자연스럽게 들어가는가
- `변경내역` 상단에 기존 상태 정보가 정상 이동했는가
- 데이터가 없을 때도 페이지가 깨지지 않는가
- 모바일/데스크톱 모두 가독성이 유지되는가
- stale 상태에서 사용자 안내 문구가 표시되는가

## 산출물 기대
- 수정된 상단 네비게이션
- `시장분석` 페이지 템플릿 및 라우트
- `홈` / `오늘의 추천` / `변경내역` 반영 완료
- 시장분석 loader / API route 구현
- handoff JSON 기반 실제 동작 확인
- 필요한 경우 간단한 integration note 추가
