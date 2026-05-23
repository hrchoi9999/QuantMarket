QS 요청 제출처: QS-Master
권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
공개 반영 포함 여부: Yes
Admin only 여부: No
관련 시스템: QuantMarket

# 시장 브리핑 `시장 분위기` 블록 UI 분리 반영 요청

## 배경
- QuantMarket의 `시장 분위기` payload는 현재 Gemini 단일 provider로 운영됩니다.
- `summary_lines`는 이제 정확히 6줄이며, 아래 형식으로 제공됩니다.
  - 1~3줄: `긍정:`으로 시작하는 긍정 요인
  - 4~6줄: `리스크:`로 시작하는 리스크 요인
- 현재 공개 페이지에서는 이 6줄이 한 덩어리로 보일 수 있어 가독성이 떨어집니다.

## 반영 목적
- 사용자가 시장 분위기를 더 직관적으로 읽을 수 있도록,
  - 블록 제목 앞에 Gemini 마크를 표시하고
  - 본문을 `긍정적 요인` / `리스크 요인` 2개 소블록으로 나누어
  - 각각 3줄씩 보여 주도록 UI를 조정합니다.

## 대상 payload
- `quantservice_market_page.json`
- `api_v1_market_analysis_page.json`

## 참고 필드
- `ai_briefs.enabled`
- `ai_briefs.title`
- `ai_briefs.providers[0].provider`
- `ai_briefs.providers[0].theme_label`
- `ai_briefs.providers[0].summary_lines`

## payload 전제
- `provider`는 현재 `gemini`만 내려옵니다.
- `summary_lines`는 총 6줄입니다.
- 각 줄은 다음 접두어를 가집니다.
  - `긍정:`
  - `리스크:`

## UI 반영 요청
1. AI 브리핑 블록의 메인 제목 `시장 분위기` 앞에 Gemini 마크를 표시해 주세요.
2. 기존의 작은 제목 `시장 분위기`는 사용하지 말고, 아래 2개 소블록으로 분리해 주세요.
   - `긍정적 요인`
   - `리스크 요인`
3. `summary_lines` 1~3줄은 `긍정적 요인` 블록에 표시해 주세요.
4. `summary_lines` 4~6줄은 `리스크 요인` 블록에 표시해 주세요.
5. 표시할 때 각 줄의 접두어는 다음처럼 정리해 주세요.
   - `긍정:` 제거 후 문장 본문만 표시
   - `리스크:` 제거 후 문장 본문만 표시
6. 각 소블록은 정확히 3줄이 보이도록 고정해 주세요.
7. 모바일에서는 2개 블록을 세로 스택으로, 데스크톱에서는 가로 2열 또는 가독성 좋은 2블록 배치로 보여 주세요.
8. 전체 톤은 과한 경고 UI보다, 정보 정리형 카드 느낌으로 정돈해 주세요.

## 권장 표시 예시
- 메인 타이틀: `[Gemini 마크] 시장 분위기`
- 소블록 1: `긍정적 요인`
- 소블록 2: `리스크 요인`

## 매핑 기준
- `summary_lines[0:3]` -> `긍정적 요인`
- `summary_lines[3:6]` -> `리스크 요인`

## fallback 처리
- `summary_lines`가 6줄이 아니면 기존 단일 리스트 fallback 렌더링을 유지해 주세요.
- `provider != gemini` 이거나 provider가 비어 있으면 기존 generic AI 브리핑 렌더링 또는 미노출 처리로 fallback 해 주세요.

## 완료 기준
- 공개 시장 브리핑 페이지에서 `시장 분위기` 제목 앞에 Gemini 마크가 보입니다.
- 기존 작은 제목 `시장 분위기` 대신 `긍정적 요인` / `리스크 요인` 2개 블록이 보입니다.
- 각 블록에 3줄씩 정확히 매핑되어 표시됩니다.
- 모바일/데스크톱 모두 줄바꿈과 간격이 자연스럽고 읽기 쉽습니다.
