# QuantService AI Brief Blocks Task Prompt (2026-03-24)

이번 작업은 `D:\QuantService`에서 진행합니다.

## 작업 목표
시장분석 페이지 상단의 막대그래프 위에 `시장분석 내용` 블록을 추가한다.
이 블록은 두 개의 작은 카드로 나누어 아래 두 AI 분석 요약을 보여 준다.
- ChatGPT
- 제미나이

각 AI 블록은 약 4줄 분량의 짧은 시장 브리핑을 표시한다.

## 데이터 소스
QuantMarket handoff current 경로 또는 원격 current URL에서 아래 파일을 읽는다.
- `quantservice_market_page.json`
- `quantservice_market_manifest.json`

핵심 필드:
- `quantservice_market_page.json -> ai_briefs`

예상 구조:
- `ai_briefs.enabled`
- `ai_briefs.title`
- `ai_briefs.layout`
- `ai_briefs.providers[]`
- `providers[].provider`
- `providers[].label`
- `providers[].enabled`
- `providers[].summary_lines[]`
- `providers[].generated_at`
- `providers[].source`

## 화면 배치 지시
시장분석 페이지 상단 구조를 아래 순서로 구성한다.
1. 페이지 제목 및 현재 시장상태 헤더
2. `시장분석 내용` 블록
3. 그 아래 기존 막대그래프/시장상태 시각화
4. 그 아래 핵심 해석 카드와 신호/지표 영역

즉 `AI 요약 블록`은 막대그래프 바로 위에 위치해야 한다.

## AI 요약 블록 UI 요구사항
- 섹션 제목: `시장분석 내용`
- 그 아래 2개의 작은 카드 배치
- 좌측 카드: `ChatGPT`
- 우측 카드: `제미나이`
- 각 카드에는 최대 4줄의 짧은 문장 표시
- 너무 작은 글씨를 쓰지 않는다
- 카드 높이는 지나치게 크지 않게 유지한다
- 카드 배경/테두리로 두 블록이 명확히 구분되게 한다
- 모바일에서는 2열이 무너지면 1열로 자연스럽게 내려온다

## 내용 표시 규칙
- `providers[].enabled == true` 이고 `summary_lines`가 있으면 줄 단위로 출력
- 각 줄은 bullet 없이 짧은 문장 형태로 표시해도 되고, 얇은 구분선 없이 줄바꿈만 써도 된다
- 4줄보다 길게 늘어지지 않게 한다
- 줄 수가 4줄 미만이면 그대로 표시한다

## fallback 규칙
AI 요약이 아직 준비되지 않은 경우:
- 전체 페이지를 깨뜨리지 않는다
- 다음 중 하나를 택한다.
  - `시장분석 내용 준비 중` 보조 문구만 표시
  - 또는 AI 블록 섹션 전체를 숨김

권장:
- `ai_briefs.enabled == false` 이면 섹션을 숨기거나, 아주 짧은 placeholder만 표시
- 데이터가 비어 있어도 막대그래프와 본문 시장분석은 정상 표시해야 한다

## 스타일 가이드
- 40~60대 사용자 기준 가독성 우선
- 작은 카드지만 텍스트가 답답하지 않게 여백 확보
- 제목 > 카드 제목 > 본문 줄 순서의 위계를 분명히 한다
- 색상보다 텍스트 라벨로 구분한다
- 카드 제목은 굵게, 본문은 읽기 편한 행간 사용
- 시각적으로 과한 장식은 피한다

## 구현 항목
1. market-analysis loader/view model에 `ai_briefs` 포함
2. 시장분석 템플릿 상단에 `시장분석 내용` 섹션 추가
3. `ChatGPT` / `제미나이` 2개 카드 렌더링
4. `enabled`/empty 상태 fallback 처리
5. 모바일 반응형 정리

## 검증 항목
- 시장분석 페이지 상단에서 막대그래프 위에 AI 블록이 보이는가
- `ChatGPT`, `제미나이` 카드가 각각 구분되어 보이는가
- 최대 4줄 정도의 요약이 읽기 쉽게 보이는가
- 데이터가 없을 때도 페이지가 깨지지 않는가
- 모바일에서 카드가 과도하게 좁아지지 않는가

## 참고
현재 QuantMarket payload는 `ai_briefs` 자리를 이미 포함하도록 준비되어 있다.
다만 실제 ChatGPT/Gemini 실응답이 채워지지 않은 시점에는 `enabled=false`일 수 있으므로,
QuantService는 이 상태를 정상 fallback으로 처리해야 한다.
