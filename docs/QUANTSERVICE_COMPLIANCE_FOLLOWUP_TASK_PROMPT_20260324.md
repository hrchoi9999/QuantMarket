# QuantService 작업지시문 (QuantMarket compliance audit follow-up)

이번 작업은 `D:\QuantService`에서 진행합니다.

## 배경
QuantMarket이 시장 브리핑 handoff를 compliance audit 기준으로 다시 정리했습니다.
이번 변경은 추천형/자문형으로 읽힐 수 있는 구조를 더 줄이고, 설명형 메타데이터를 강화하는 것이 목적입니다.

운영 source:
- https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current

주요 파일:
- quantservice_market_home.json
- quantservice_market_today.json
- quantservice_market_page.json
- quantservice_market_manifest.json
- api_v1_market_analysis_home.json
- api_v1_market_analysis_page.json
- api_v1_market_analysis_summary.json
- api_v1_market_analysis_detail.json
- api_v1_market_analysis_today_bridge.json

## 반드시 반영할 변경

### 1. 설명형 키 사용
구키 사용 금지:
- `action_hint`
- `action_guide`
- `recommended_tone`
- `bridge_text`

신규 키 사용:
- `reference_note`
- `observation_note`
- `market_tone`
- `reference_text`

### 2. AI brief 제목/성격 변경
현재 ai_briefs:
- `title = 시장 브리핑 참고`
- provider `theme_label`
  - ChatGPT -> `시장 해석 참고`
  - 제미나이 -> `시장 분위기`

UI 반영:
- 카드 제목은 `theme_label` 우선 사용
- `대응 전략`, `추천 전략`, `행동 가이드` 같은 제목 금지

### 3. compliance_meta 확장
이제 `compliance_meta`에 아래 키가 포함됩니다.
- `public_same_for_all_users`
- `non_personalized`
- `advisory_action_signal`
- `actual_investment_result`
- `backtest_result`
- `disclaimer_required`
- `consumer_channel`
- `generated_by`
- `intended_use`
- `model_version`
- `calculation_version`
- `asof`
- `refresh_cycle`
- `rebalance_frequency`

활용 지침:
- public reference 성격 확인용으로 사용
- 투자 권유형 UI와 결합 금지
- 페이지 하단 notice 노출 조건 판단에 활용 가능

### 4. notice_block 공통 노출
각 주요 payload에 `notice_block`이 있습니다.

반영 권장:
- 시장분석 페이지 하단: 전체 문구 노출
- 홈 페이지: 축약형 또는 1~2줄 요약 노출
- 오늘 페이지 내 시장 브리지: 소형 notice 노출

### 5. 설명 메타데이터 활용
새로 활용 가능한 필드:
- `header_state.description`
- `header_state.tooltip`
- `component_cards[].description`
- `descriptions`
- `metric_definitions`
- `display_metrics`

반영 권장:
- 카드 tooltip
- 아코디언형 설명문
- 값 옆 help text
- 고령 사용자용 쉬운 설명 텍스트

### 5-1. 지표 카드 상태 배지 사용
이제 `component_cards[].status_badge`가 포함됩니다.

구조:
- `label`: `좋음` | `보통` | `나쁨`
- `tone`: `good` | `neutral` | `bad`
- `reason`: 짧은 판정 설명

UI 반영 원칙:
- 각 지표 카드 우상단에 작은 pill/badge로 표시
- badge 문구는 QuantMarket payload 값을 그대로 사용
- 프론트에서 score를 다시 해석해 badge를 재계산하지 말 것
- 색상만으로 의미를 전달하지 말고 텍스트 `좋음/보통/나쁨`을 함께 표시
- tooltip 또는 보조설명으로 `reason`을 연결할 수 있음

### 6. 지표 노출 주의
현재 아래 필드는 `metric_definitions.*.default_visible=false` 입니다.
- `kospi_20d_ret`
- `kospi_60d_ret`
- `kosdaq_20d_ret`

UI 원칙:
- 사용자 화면 기본 비노출 유지
- 내부 검증/운영용에서만 선택 노출

## 페이지별 반영

### 시장분석 페이지
- `ai_briefs.title` 사용
- provider 제목은 `theme_label` 사용
- `header_state.description` 또는 `tooltip` 연결
- `component_cards[].description` 표시 가능
- `signal_lists.observation_note` 사용
- 하단 `notice_block` 고정 노출

### 홈 페이지
- hero 보조문은 `reference_note`
- 시장 요약 블록 근처 `notice_block` 요약 노출
- `추천`, `전략`, `행동` 문구로 재가공 금지

### 오늘 페이지
- `market_tone`
- `reference_text`
- 시장 브리지 하단 `notice_block`
- 추천형 문구로 재가공 금지

## QA 체크리스트
- [ ] `추천`, `자문`, `대응 전략`, `행동 가이드` 같은 문구가 UI에 남아 있지 않은가?
- [ ] `theme_label`이 `시장 해석 참고` / `시장 분위기`로 표시되는가?
- [ ] `component_cards[].description`을 사용할 수 있는가?
- [ ] `component_cards[].status_badge.label/tone/reason`이 우상단 배지로 정상 표시되는가?
- [ ] `compliance_meta.disclaimer_required=true`를 반영해 notice가 보이는가?
- [ ] default_visible=false 지표가 기본 노출되지 않는가?
- [ ] 시장분석 정보가 종목 추천/비중 조정 CTA와 연결되지 않는가?
