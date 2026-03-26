이번 작업은 `D:\QuantService`에서 진행합니다.

작업 목적:
- 공개 시장브리핑 페이지에서 사용자가 가장 혼란스러워하는 `정식 시장상태`와 `오늘 장중 흐름`의 차이를 명확히 설명하도록 UI를 보완합니다.
- 동시에 `퀀트투자 모델 브리핑`이 1시간마다 실제 시장을 더 잘 따라가도록 새 payload 필드를 반영합니다.

중요 배경:
- 정식 시장상태는 `전일 종가 기준` 중기 상태입니다.
- 오늘 장중 흐름은 별도 장중 참고 레이어입니다.
- 따라서 `정식 시장상태=상승`, `오늘 장중 흐름=약세`가 동시에 나올 수 있습니다.
- 이 둘을 분리해서 보여 주지 않으면 사용자 혼란과 불신이 생깁니다.

운영 base URL:
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current`

이번에 public payload에 추가된 핵심 필드:
- `quantservice_market_page.json.state_intraday_bridge`
- `quantservice_market_home.json.hero.state_intraday_bridge`
- `quantservice_market_today.json.market_bridge.state_intraday_bridge`
- `quantservice_market_today.json.headline.state_intraday_bridge`

`state_intraday_bridge` 구조:
- `enabled`
- `medium_term_label`
- `medium_term_state_label`
- `medium_term_state_score`
- `intraday_label`
- `alignment`
- `display_label`
- `bridge_text`
- `basis_lines[]`
- `intraday.asof`
- `intraday.direction_label`
- `intraday.total_score`
- `intraday.summary_line`
- `intraday.futures`
- `intraday.flow`

예시 의미:
- `medium_term_label = 정식 시장상태(전일 종가 기준)`
- `intraday_label = 오늘 장중 흐름(참고용)`
- `display_label = 상승 유지, 단기 조정 동반`
- `bridge_text = 정식 시장상태는 상승이지만, 오늘 장중에는 단기 조정 흐름이 나타납니다.`

공개 페이지 반영 지시:

## 1. 시장브리핑 페이지
가장 중요하게 반영해야 할 페이지입니다.

### A. 헤더 영역 보강
기존:
- `시장상태: 상승`

변경:
- `정식 시장상태(전일 종가 기준): 상승`
- 그 아래 또는 옆에 `오늘 장중 흐름(참고용): 강한 약세`
- 그 아래에 `display_label`
- 그 아래에 `bridge_text`

즉 헤더에 아래 4줄 구조를 권장합니다.
1. 정식 시장상태
2. 오늘 장중 흐름
3. 사용자용 통합 라벨(`display_label`)
4. 짧은 설명(`bridge_text`)

### B. 근거 2줄 표시
`basis_lines[]`를 헤더 바로 아래 또는 tooltip/설명 카드로 표시합니다.

예:
- 정식 시장상태 근거: 공식 지표와 내부 breadth 기준으로 상승 흐름이 우세합니다.
- 장중 흐름 근거: 코스피·코스닥 약세, 원달러 강세, 외국인/프로그램 순매도 우위가 나타났습니다.

### C. 상태 오해 방지 문구
화면에서 `시장상태`만 단독으로 크게 노출하지 말고, 반드시 아래 중 하나를 함께 씁니다.
- `정식 시장상태(전일 종가 기준)`
- `중기 시장상태(전일 종가 기준)`

권장하지 않음:
- 그냥 `시장상태: 상승`

## 2. 홈 페이지
사용 파일:
- `quantservice_market_home.json.hero.state_intraday_bridge`

반영 목표:
- 홈에서도 `상승인데 왜 오늘 떨어지지?` 같은 혼란을 줄입니다.

권장 반영:
- 기존 hero 요약 유지
- 그 아래에 짧은 한 줄만 추가
- 사용 값:
  - `display_label`
  - `bridge_text`

예:
- `상승 유지, 단기 조정 동반`
- `정식 시장상태는 상승이지만, 오늘 장중에는 단기 조정 흐름이 나타납니다.`

홈에서는 `basis_lines` 전체를 길게 노출하지 않아도 됩니다.

## 3. 오늘의 추천 페이지
사용 파일:
- `quantservice_market_today.json.market_bridge.state_intraday_bridge`

권장 반영:
- 기존 market bridge 아래에 짧은 보조 문구 1줄 추가
- 사용 값:
  - `display_label`
  - `bridge_text`

목표:
- 오늘의 추천을 읽는 사용자가 현재 시장 배경을 더 자연스럽게 이해하게 함

## 4. 퀀트투자 모델 브리핑(AI 블록) 반영
이번에 QuantMarket 쪽에서 AI 브리핑 입력이 개선되었습니다.

개선 포인트:
- 장중 `intraday` 방향 반영
- 장중 `futures` 반영
- 장중 `flow` 반영
- `정식 시장상태 vs 오늘 장중 흐름` 차이 반영
- 1시간마다 초점이 조금씩 달라지도록 입력 개선

QS에서 할 일:
- 별도 로직 추가는 필요 없음
- 기존처럼 `ai_briefs.providers[]`만 그대로 렌더링하면 됨
- 다만 UI 설명 문구는 아래처럼 보완 권장
  - `정식 시장상태와 오늘 흐름을 함께 반영한 참고 브리핑`

## 5. 표현 원칙
반드시 유지할 표현:
- `정식 시장상태(전일 종가 기준)`
- `오늘 장중 흐름(참고용)`
- `상승 유지, 단기 조정 동반` 같은 브리지형 라벨

피해야 할 표현:
- `시장상태: 상승`만 단독 표시
- `오늘 하락인데 시스템이 틀린 것처럼 보이게 하는 단순 라벨`

fallback 규칙:
1. `state_intraday_bridge.enabled != true` 이면 기존 UI 유지
2. `intraday` 정보가 없으면 `정식 시장상태(전일 종가 기준)`만 표시
3. 전체 페이지는 깨지지 않아야 함

QA 체크리스트:
- [ ] 공개 시장브리핑 페이지에서 `정식 시장상태`와 `오늘 장중 흐름`이 분리되어 보이는가?
- [ ] `display_label`과 `bridge_text`가 자연스럽게 노출되는가?
- [ ] 홈에서도 혼란을 줄이는 한 줄 설명이 들어가는가?
- [ ] 오늘의 추천 페이지에도 짧은 배경 설명이 들어가는가?
- [ ] AI 브리핑이 이전보다 오늘 시장 흐름을 더 직접 반영해 보이는가?
- [ ] `시장상태: 상승`만 단독으로 보여 주는 구간이 남아 있지 않은가?
