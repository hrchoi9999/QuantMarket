# QUANTMARKET_TO_QS_PUBLIC_MARKET_BRIEFING_ROLLOUT_PLAN_20260326.md

## 목적
지금까지 admin 환경에서 검증해 온 시장브리핑 고도화 요소를 `redbot.co.kr` 실 운영 페이지에 단계적으로 반영하기 위한 공개 설계와 작업 범위를 정리한다.

이 문서는 아래 3가지를 함께 다룬다.
- 어떤 정보를 public에 먼저 노출할지
- QuantMarket(QM)과 QuantService(QS)가 각각 무엇을 담당할지
- 실제 공개 반영 전 필요한 개발/QA/운영 작업

## 전제
- `QM`은 시장브리핑 데이터의 생산자다.
- `QS`는 public/admin UI와 API 소비 계층이다.
- 장 종료 후 브리핑과 장중 현재 지표는 같은 것으로 보이면 안 된다.
- admin에서 먼저 검증한 뒤 public에 단계적으로 올린다.
- 법적/표현 리스크 때문에 설명형/참고형 문구를 유지한다.

## 현재까지 QM에서 준비된 데이터
### 1. 공개용 정식 시장브리핑 current
현재 public handoff/current에서 이미 제공 중인 항목
- 시장상태 라벨
- 상태점수
- header_state
- component_cards
- positive/warning signals
- display_metrics
- AI 브리핑(`시장 해석 참고`, `시장 분위기 참고`)
- compliance_meta / notice_block
- component status badge(`좋음/보통/나쁨`)

주요 파일
- `quantservice_market_home.json`
- `quantservice_market_today.json`
- `quantservice_market_page.json`
- `quantservice_market_manifest.json`
- `api_v1_market_analysis_*`

### 2. admin 전용 고도화 브리핑 데이터
현재 admin에서 검증 중인 항목
- 시장 타임라인
- 자산군 상대강도
- 상태 전이 요약
- 모델 배경 브리지
- 장중 intraday snapshot
- 장중 breadth
- 장중 선물(`FUT`)
- 장중 수급(`PROGRAM_TOTAL_NET`, `PROGRAM_NONARB_NET`, `FOREIGNER_NET`, `INSTITUTION_NET`)

주요 admin 파일
- `admin_market_timeline.json`
- `admin_market_asset_strength.json`
- `admin_market_state_transition.json`
- `admin_market_model_background.json`
- `admin_market_intraday_summary.json`
- `admin_market_intraday_detail.json`
- `admin_market_manifest.json`
- `admin_market_intraday_manifest.json`

## 공개 운영 반영 원칙
### 1. public에는 `정식 브리핑`을 중심으로 둔다
public 페이지의 주축은 장 종료 후 계산되는 정식 시장브리핑이다.

public 핵심 메시지
- 현재 시장상태
- 현재 시장 해석
- 모델 해석상 우호/주의 신호
- 주요 지표 점검

### 2. 장중 정보는 별도 `참고 레이어`로 둔다
장중 intraday는 정식 상태를 덮어쓰지 않는다.

표시 원칙
- `정식 시장 브리핑(전일 종가 기준)`
- `장중 현재 지표(참고용)`
를 시각적으로 분리한다.

### 3. 공개 반영은 2단계가 적절하다
#### 1단계
- public 기존 시장브리핑 페이지 고도화
- 타임라인 / 자산강도 / 상태전이 / 모델배경 추가
- 장중 정보는 아직 공개 미반영 또는 아주 작은 배너 수준만 검토

#### 2단계
- 장중 현재 지표를 public에 제한적으로 반영
- 상단 보조바 또는 별도 접힘 섹션으로만 노출
- 충분한 운영 안정성 검증 후 적용

## 페이지별 공개 설계
## 홈(`/`)
### 목적
사용자가 10초 안에 현재 시장과 모델 해석 배경을 이해하게 한다.

### 권장 반영 요소
- 현재 시장상태 라벨
- 한 줄 브리핑 요약
- 핵심 신호 2개
- 4개 점검 카드 미리보기
- `시장브리핑 자세히 보기` 링크

### 반영 소스
- `quantservice_market_home.json`

### 공개 1단계 추가 후보
- 최근 상태 타임라인 미니 3포인트
- 자산군 강도 상위 2개

### UI 원칙
- 숫자 과다 노출 금지
- 시장 브리핑 카드 1개 + 작은 미리보기 수준 유지

## 시장브리핑(`/market-analysis` 또는 운영 경로)
### 목적
시장과 자산을 가장 깊게 해석하는 메인 페이지

### 공개 1단계 권장 구성
1. 헤더 상태 요약
2. AI 브리핑 2블록
3. 상태 타임라인
4. 4개 점검 카드
5. 모델 해석 포인트
6. 우호/주의 신호
7. 자산군 상대강도
8. 주요 지표 상세
9. 활용 가이드 / 주의문구

### 현재 QM 기준으로 바로 연결 가능한 데이터
- public 기존 page payload
- admin timeline payload
- admin asset strength payload
- admin state transition payload
- admin model background payload

### 새 public payload로 정리 권장
QM에서 아래를 신규 public payload로 재구성하는 것이 좋다.
- `market_briefing_timeline.json`
- `market_briefing_asset_strength.json`
- `market_briefing_state_transition.json`
- `market_briefing_model_background.json`

이유
- admin payload를 그대로 public에 쓰면 필드가 실험적일 수 있다.
- public용 shape는 더 단순하고 안정적으로 별도 고정하는 편이 좋다.

### 공개 2단계 장중 섹션 권장안
페이지 상단 또는 헤더 하단에 작은 보조 영역 추가
- 제목: `장중 현재 지표(참고용)`
- 상태: `강세/약세/혼조`
- 기준시각
- 요약 1줄
- 지수/환율 간단 표시
- 자세히 보기 또는 접힘 확장

장중 상세는 처음부터 크게 노출하지 않는 것이 좋다.

## 오늘의 추천(`/today`)
### 목적
오늘의 추천 페이지가 현재 시장 해석 배경을 짧게 가져가도록 한다.

### 권장 반영 요소
- 현재 시장상태 라벨
- 브리핑 톤
- reference text
- 주의 신호 1~2개
- 시장브리핑 페이지 링크

### 반영 소스
- `quantservice_market_today.json`
- 향후 public model background bridge payload

## 성과(`/performance` 계열)
### 목적
성과 숫자를 시장 환경과 함께 읽게 한다.

### 권장 반영 요소
- 해당 구간 시장상태 분포
- 평균 상태점수
- 주요 전환 시점
- 당시 브리핑 요약 1개

### 반영 소스
- admin timeline/state transition 이력 기반 public 재구성 payload 필요

### 공개 시점
- 1차보다는 2차 이후가 적절
- 이력 축적이 더 필요함

## 변경내역(`/changes` 계열)
### 목적
운영상태 + 브리핑 변화 이력을 함께 보여 준다.

### 권장 반영 요소
- 기존 상태/운영 상태 영역
- 최근 시장상태 변화
- 최근 브리핑 변화 포인트
- 최근 publish freshness

### 반영 소스
- 기존 상태 영역
- manifest / state transition summary / recent payload history

## 공개 반영 우선순위
### 우선순위 A: 바로 추진 가능
1. 시장브리핑 메인 페이지 고도화
- 타임라인
- 자산군 상대강도
- 상태전이 요약
- 모델 해석 백그라운드

2. 홈/오늘의 추천 요약 강화
- 자산군 강도 축약
- 브리핑 포인트 축약

### 우선순위 B: 검토 후 반영
3. 장중 현재 지표 public 축소 노출
- 상단 배너 또는 접힘 영역
- 정식 브리핑과 엄격 분리

### 우선순위 C: 이력 축적 후 반영
4. 성과 페이지 시장 환경 설명
5. 변경내역 페이지 브리핑 변화 요약

## QM 개발 작업
### 1. public 전용 payload 정리
현재 admin payload에서 public 반영이 필요한 항목을 별도 current로 생성

권장 신규 payload
- `market_briefing_timeline.json`
- `market_briefing_asset_strength.json`
- `market_briefing_state_transition.json`
- `market_briefing_model_background.json`

### 2. manifest 확장
public manifest에 아래를 추가
- optional files 목록
- freshness rule
- visibility
- data lineage

### 3. 장중 public용 축약 payload 설계
장중 공개가 결정되면 아래처럼 별도 소형 payload 추천
- `market_intraday_public_summary.json`

포함 권장 필드
- asof
- session_status
- direction_label
- summary_line
- indexes(축약)
- fx(축약)
- notice

### 4. 표현/컴플라이언스 점검
- 장중 수급/선물 문구가 자문처럼 읽히지 않는지 점검
- `참고용`, `보조지표`, `정식 브리핑과 별도` 문구 유지

## QS 개발 작업
### 1. public 시장브리핑 페이지 확장
- 타임라인 섹션 추가
- 자산강도 섹션 추가
- 상태전이 요약 섹션 추가
- 모델 배경 섹션 추가

### 2. 홈/오늘 페이지 요약 연결
- 기존 market home/today에 축약 데이터 배치
- 메인 콘텐츠를 밀어내지 않는 선에서 카드형 추가

### 3. 장중 공개는 분리 설계
공개 반영 시 아래 원칙 유지
- 별도 레이블: `장중 현재 지표(참고용)`
- `정식 시장 브리핑(전일 종가 기준)`과 시각 분리
- 장중 실패 시 `전일 기준 참고` 또는 숨김 처리

### 4. fallback 처리
- optional payload 미존재 시 기존 public UI 유지
- 장중 unavailable 시 섹션 숨김 또는 준비 중 처리

## 공개 전 QA 체크리스트
### 데이터
- 모든 시간 KST인지
- 미래 시각 없는지
- public payload와 admin payload가 섞이지 않는지
- 장중 정보가 정식 상태를 덮어쓰지 않는지

### 표현
- 자문/추천형 표현 없는지
- `참고`, `브리핑`, `해석`, `보조지표` 문구 유지되는지
- 장중 수급/선물 해석이 과장되지 않는지

### UX
- 40~60대 사용자 기준 가독성 유지되는지
- 홈은 짧고, 시장브리핑 페이지는 충분히 깊은지
- 장중 정보가 과도하게 튀지 않는지

### 운영
- optional payload 누락 시 graceful fallback 되는지
- stale 시 manifest 기준 경고가 가능한지
- 캐시 이슈 없이 기준시각이 맞게 보이는지

## 권장 롤아웃 순서
### Step 1
QM
- public timeline / asset strength / state transition / model background payload 생성

QS
- 시장브리핑 메인 페이지 고도화
- 홈/오늘 요약 강화

### Step 2
admin/public 병행 검증
- 데이터 해석 문구 안정성 확인
- 모바일/데스크탑 UI 확인
- stale/fallback 확인

### Step 3
장중 current 지표 public 축소 반영 여부 결정
- 승인 시에만 QS public에 제한 반영
- 미승인 시 admin 유지

## 최종 권장 결론
지금까지 개발된 고도화 내용 중 public에 먼저 올릴 것은 아래 4개가 가장 적절하다.
- 상태 타임라인
- 자산군 상대강도
- 상태 전이 요약
- 모델 해석 백그라운드

장중 선물/수급/현재지표는 이미 admin에서 유의미하지만, public은 한 단계 더 검증 후 `작은 참고 레이어`로 올리는 것이 가장 안전하다.
