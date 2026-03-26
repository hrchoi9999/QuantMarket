이번 작업은 `D:\QuantService`에서 진행합니다.

작업 목적:
- QuantMarket이 새로 제공하는 `시장브리핑 고도화 1차 public payload`를 redbot.co.kr 공개 페이지에 실제 반영합니다.
- 이번 작업은 `공개 시장브리핑 페이지 고도화`가 핵심입니다.
- 이번 1차에서는 `정식 시장브리핑(전일 종가 기준)` 관련 정보만 public에 반영합니다.

이번 작업에서 공개 사이트에 실제 반영할 대상 페이지:
1. 홈
2. 시장브리핑
3. 오늘의 추천

중요 원칙:
1. 이번 작업은 공개 사이트 반영 작업입니다.
2. 기존 공개 시장브리핑을 더 풍성하게 만드는 것이 목적입니다.
3. 장중 intraday / 선물 / 수급은 아직 공개 반영하지 않습니다.
4. QuantService는 UI/표시 계층만 담당하고, 데이터 계산/해석 생산은 QuantMarket이 담당합니다.

운영 base URL:
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current`

기존 public 파일:
- `quantservice_market_home.json`
- `quantservice_market_today.json`
- `quantservice_market_page.json`
- `quantservice_market_manifest.json`

이번에 추가된 public 파일:
- `quantservice_market_timeline.json`
- `quantservice_market_asset_strength.json`
- `quantservice_market_state_transition.json`
- `quantservice_market_model_background.json`

대응 API 파일:
- `api_v1_market_analysis_timeline.json`
- `api_v1_market_analysis_asset_strength.json`
- `api_v1_market_analysis_state_transition.json`
- `api_v1_market_analysis_model_background.json`

manifest 확인 포인트:
- `optional_files.timeline`
- `optional_files.asset_strength`
- `optional_files.state_transition`
- `optional_files.model_background`

이번 작업에서 공개 사이트에 반영할 내용:

## 1. 홈 페이지 공개 반영
목표:
- 홈에서 현재 시장브리핑을 조금 더 풍성하게 보여 주되 과하게 무겁지 않게 유지합니다.

기존 사용 파일:
- `quantservice_market_home.json`

추가 반영 권장 데이터:
- `quantservice_market_asset_strength.json`
또는
- `quantservice_market_state_transition.json`

권장 공개 반영안:
1. 기존 시장브리핑 요약 카드 유지
2. 그 아래 또는 내부에 작은 추가 정보 1개만 노출

추천 표시안 A:
- `상대강도 상위 자산 2개`
예:
- 현재 강한 자산: `KOSPI`, `KOSDAQ`

추천 표시안 B:
- `현재 상태 지속시간`
예:
- 현재 상승 상태가 `31.1시간` 이어지는 중

중요:
- 홈은 간결해야 하므로 timeline 전체나 state transition 전체를 크게 넣지 않습니다.
- 추가 정보는 `작은 보조 카드` 수준으로만 넣습니다.

## 2. 시장브리핑 페이지 공개 반영
목표:
- 공개 시장브리핑 페이지를 이번 1차의 핵심 반영 페이지로 고도화합니다.

기존 유지 섹션:
- 헤더 상태 요약
- AI 브리핑 2블록
- 4개 점검 카드
- 우호/주의 신호
- 주요 지표 상세
- 주의사항

이번에 공개로 추가할 신규 섹션:
1. 상태 타임라인
2. 모델 해석 백그라운드
3. 자산군 상대강도
4. 상태 전이 요약

권장 배치 순서:
1. 헤더 상태 요약
2. AI 브리핑 2블록
3. 상태 타임라인
4. 4개 점검 카드
5. 모델 해석 백그라운드
6. 우호/주의 신호
7. 자산군 상대강도
8. 상태 전이 요약
9. 주요 지표 상세
10. 활용 가이드 / 주의사항

### A. 상태 타임라인
사용 파일:
- `quantservice_market_timeline.json`

표시 항목:
- `title`
- `description`
- `current_state.state_label`
- `current_state.total_score`
- `trend_direction`
- `points[]`

권장 UI:
- 최근 흐름을 보여 주는 작은 line chart 또는 step chart
- 상태 라벨과 total_score 변화 흐름을 함께 보여 줌
- 세부 component score는 tooltip/보조 정보 수준으로 처리 가능

### B. 모델 해석 백그라운드
사용 파일:
- `quantservice_market_model_background.json`

표시 항목:
- `briefing_tone`
- `summary_line`
- `reference_note`
- `model_background_points[]`
- `favorable_signals[]`
- `caution_signals[]`

권장 UI:
- 별도 강조 카드
- 제목: `모델 해석 백그라운드`
- 부제 또는 설명 1줄 포함

### C. 자산군 상대강도
사용 파일:
- `quantservice_market_asset_strength.json`

표시 항목:
- `assets[]`
- `top_assets[]`
- `bottom_assets[]`

권장 UI:
- rank 순서 표 또는 카드 리스트
- `asset_group`
- `strength_rank`
- `strength_label`
- `ret_20d`
- `strength_score`

권장 표현:
- `현재 상대적으로 강한 자산`
- `현재 상대적으로 약한 자산`

### D. 상태 전이 요약
사용 파일:
- `quantservice_market_state_transition.json`

표시 항목:
- `current.current_state`
- `current.prev_state`
- `current.duration_hours`
- `current.transition_count_5d`
- `current.transition_count_20d`
- `current.stability_score`
- `recent_changes[]`

권장 UI:
- 상단 요약 카드 3~4개
- 하단 최근 변화 리스트

예시 문구:
- `현재 상승 상태가 31.1시간 이어지고 있습니다.`
- `최근 5일 상태 전이는 4회입니다.`

## 3. 오늘의 추천 페이지 공개 반영
목표:
- 오늘의 추천 페이지에서 현재 시장배경을 조금 더 자연스럽게 연결합니다.

기존 사용 파일:
- `quantservice_market_today.json`

추가 사용 파일:
- `quantservice_market_model_background.json`

권장 공개 반영안:
1. 기존 시장 브리지 영역 유지
2. 그 아래에 `이번 해석 배경` 1~2줄 추가

표시 항목:
- `briefing_tone`
- `model_background_points[0]`
- `model_background_points[1]`

중요:
- 오늘의 추천 핵심 콘텐츠를 밀어내지 않게 짧게 유지
- 긴 표나 긴 리스트는 넣지 않음

이번 작업에서 공개 사이트에 반영하지 않는 것:
- `admin_market_intraday_summary.json`
- `admin_market_intraday_detail.json`
- 장중 `futures`
- 장중 `flow_signals`
- 장중 `signal_overlay`

즉, 이번 1차는 공개 사이트에 아래만 반영하면 됩니다.
- `상태 타임라인`
- `자산군 상대강도`
- `상태 전이 요약`
- `모델 해석 백그라운드`

구현 항목:
1. market-analysis public loader에 optional payload 4종 추가
2. 홈 public loader에 요약용 optional 연결
3. 오늘의 추천 public loader에 model background 연결
4. 시장브리핑 페이지에 신규 섹션 4개 추가
5. 홈 페이지에 소형 추가 정보 반영
6. 오늘의 추천 페이지에 배경 설명 반영
7. optional payload 누락 시 graceful fallback 처리

fallback 규칙:
1. optional payload가 없으면 기존 public UI 유지
2. 특정 payload 로드 실패 시 해당 섹션만 숨김
3. 전체 페이지는 깨지지 않아야 함

QA 체크리스트:
- [ ] 홈에 시장브리핑 추가 정보가 자연스럽게 들어가는가?
- [ ] 시장브리핑 페이지에 신규 4개 섹션이 정상 렌더링되는가?
- [ ] 오늘의 추천 페이지에 배경 정보가 과하지 않게 들어가는가?
- [ ] 기존 공개 시장브리핑 핵심 구조가 망가지지 않는가?
- [ ] optional payload 누락 시 기존 UI가 정상 유지되는가?
- [ ] 장중 intraday 데이터가 public에 노출되지 않는가?
- [ ] 모바일에서도 섹션 순서와 가독성이 자연스러운가?
