QS 요청 제출처: QS-Master
권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
공개 반영 포함 여부: Yes
Admin only 여부: No
관련 시스템: QuantMarket

# QuantMarket AI 브리핑 단일화 반영 요청

## 작업 목적
- 공개 시장 브리핑의 AI 브리핑 영역에서 ChatGPT 기반 `모델 해석` 블록을 제거합니다.
- Gemini 기반 `시장 분위기` 블록만 표시되도록 QS 렌더링을 조정합니다.

## 변경 배경
- QuantMarket에서 ChatGPT/OpenAI API 연동을 중단했습니다.
- 앞으로 QuantMarket payload의 `ai_briefs.providers[]`에는 `provider="gemini"` 항목만 내려갑니다.
- `ai_briefs.layout`은 `single_market_mood_block`으로 내려갈 수 있습니다.

## 대상 payload
- `quantservice_market_page.json`
- `api_v1_market_analysis_page.json`

## 사용 필드
- `ai_briefs.enabled`
- `ai_briefs.title`
- `ai_briefs.layout`
- `ai_briefs.providers[]`
- `ai_briefs.providers[].provider`
- `ai_briefs.providers[].theme_label`
- `ai_briefs.providers[].summary_lines`

## 반영 요청
1. ChatGPT 카드 또는 `모델 해석` 카드가 남아 있으면 미노출 처리해 주세요.
2. `provider="gemini"` 항목만 렌더링해 주세요.
3. 카드 제목은 payload의 `theme_label`을 우선 사용하고, 없으면 `시장 분위기`로 표시해 주세요.
4. 기존 2열 카드 전제를 제거하고, provider가 1개일 때 단일 카드가 자연스럽게 보이도록 해 주세요.
5. `providers[]`가 1개여도 `ai_briefs.enabled=true`이면 섹션이 정상 노출되게 해 주세요.
6. `providers[]`에 enabled 항목이 없으면 섹션은 숨겨 주세요.

## 완료 기준
- 공개 시장 브리핑에서 ChatGPT/모델 해석 카드가 보이지 않습니다.
- Gemini 시장 분위기 카드만 자연스럽게 표시됩니다.
- 홈/시장브리핑/오늘의 추천 중 AI 브리핑을 참조하는 영역에서 레이아웃 깨짐이 없습니다.
- 모바일과 데스크톱 모두 단일 카드 표시가 어색하지 않습니다.
