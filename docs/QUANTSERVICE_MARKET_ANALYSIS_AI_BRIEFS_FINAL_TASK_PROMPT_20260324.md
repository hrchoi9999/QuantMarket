# QuantService Market Analysis AI Briefs Integration Task Prompt (2026-03-24)

이번 작업은 `D:\QuantService`에서 진행합니다.

## 작업 배경
QuantMarket은 이제 시장분석 handoff JSON 안에 아래 AI 요약 블록을 함께 제공한다.
- `ChatGPT` 4줄 요약
- `제미나이` 4줄 요약

이 데이터는 시장분석 페이지 상단의 막대그래프 위에 배치되어야 한다.

QuantService는 이 데이터를 계산하지 않고, QuantMarket이 제공한 handoff를 읽어 그대로 UI에 반영한다.

## 원격 handoff source
운영 기준 base URL:
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current`

주요 파일:
- `quantservice_market_page.json`
- `quantservice_market_manifest.json`

## 핵심 데이터 구조
`quantservice_market_page.json` 안에 아래 필드가 포함된다.
- `ai_briefs.enabled`
- `ai_briefs.title`
- `ai_briefs.layout`
- `ai_briefs.providers[]`

각 provider 구조:
- `provider`: `chatgpt` | `gemini`
- `label`: `ChatGPT` | `제미나이`
- `enabled`: bool
- `generated_at`: string | null
- `source`: string
- `summary_lines`: string[]

현재 consumer slot:
- `market_analysis.ai_brief_blocks`

## 작업 목표
시장분석 페이지 상단에서:
1. 현재 시장상태 헤더를 보여 준다.
2. 그 바로 아래 `시장분석 내용` 섹션을 추가한다.
3. 그 안에 `ChatGPT`, `제미나이` 2개의 작은 요약 블록을 보여 준다.
4. 그 아래에 기존 막대그래프/시장상태 시각화 블록을 둔다.

즉 순서는 아래와 같다.
- 시장상태 헤더
- 시장분석 내용 AI 2블록
- 막대그래프/상태 시각화
- 핵심 해석 카드
- 신호 및 지표

## UI 요구사항
### 섹션 제목
- 제목: `시장분석 내용`
- 제목은 막대그래프보다 위에 둔다.

### 카드 구성
- 카드 2개
- 좌측: `ChatGPT`
- 우측: `제미나이`
- 각 카드 안에는 4줄 정도의 짧은 시장 브리핑 표시
- 각 줄은 줄바꿈 기준으로 자연스럽게 보여 준다.
- bullet은 필수 아님

### 스타일 가이드
- 40~60대 사용자 가독성 우선
- 작은 카드지만 글씨가 너무 작지 않게 한다
- 충분한 패딩과 줄간격을 준다
- 카드 제목은 굵게
- 카드 본문은 4줄 내에서 답답하지 않게
- 모바일에서는 2열이 깨지면 1열로 자연스럽게 내려온다
- 색상보다는 레이블과 구조로 구분한다

## 데이터 표시 규칙
### 정상 상태
- `ai_briefs.enabled == true` 이면 섹션을 표시한다.
- 각 provider에서 `enabled == true` 이고 `summary_lines`가 있으면 해당 카드 표시
- `ChatGPT`, `제미나이` 중 하나만 데이터가 있어도 있는 카드만 보여도 됨
- 둘 다 있으면 2개 카드 모두 노출

### fallback 상태
- `ai_briefs.enabled == false` 이면 섹션 전체를 숨기거나 `시장분석 내용 준비 중` 문구만 짧게 표시
- 한 provider만 비어 있으면 다른 provider 카드는 그대로 보여 준다.
- 시장분석 페이지 본문과 막대그래프는 AI 요약이 없어도 정상 표시되어야 한다.

권장 fallback:
- 두 provider 모두 비활성: 섹션 숨김 또는 placeholder 1줄
- 하나만 활성: 활성 카드만 표시하거나 비활성 카드는 `준비 중` 표시

## 구현 항목
1. market-analysis loader/view model에 `ai_briefs` 반영
2. 시장분석 템플릿 상단에 `시장분석 내용` 섹션 추가
3. `ChatGPT` / `제미나이` 카드 2개 렌더링
4. `enabled` / empty fallback 처리
5. 모바일 반응형 정리

## 검증 항목
- 막대그래프 위에 `시장분석 내용` 섹션이 보이는가
- `ChatGPT`, `제미나이` 카드 구분이 명확한가
- 각 카드에 최대 4줄 정도의 짧은 문장이 읽기 좋게 표시되는가
- 한 provider만 활성일 때도 레이아웃이 깨지지 않는가
- 둘 다 비활성일 때 페이지가 깨지지 않는가
- 모바일에서 카드 폭과 줄바꿈이 자연스러운가

## 참고 payload 예시
현재 운영 payload에서는 아래와 같이 들어온다.
- `ChatGPT`: `source=openai:gpt-4.1-mini`
- `제미나이`: `source=gemini:gemini-2.5-flash`

즉 QuantService는 별도 계산 없이 `summary_lines[]`만 그대로 렌더링하면 된다.
