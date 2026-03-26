QS 전달 메시지

QuantMarket 쪽에서 `정식 시장상태 vs 오늘 장중 흐름` 혼란을 줄이기 위한 public payload 보강을 반영했습니다.

이번에 추가된 핵심 필드:
- `state_intraday_bridge`

반영 위치:
- `quantservice_market_page.json.state_intraday_bridge`
- `quantservice_market_home.json.hero.state_intraday_bridge`
- `quantservice_market_today.json.market_bridge.state_intraday_bridge`

이 필드에는 아래가 들어 있습니다.
- `정식 시장상태(전일 종가 기준)`
- `오늘 장중 흐름(참고용)`
- `display_label`
- `bridge_text`
- `basis_lines[]`

예시:
- `display_label = 상승 유지, 단기 조정 동반`
- `bridge_text = 정식 시장상태는 상승이지만, 오늘 장중에는 단기 조정 흐름이 나타납니다.`

또한 AI 브리핑 입력도 개선해서, 이제는 장중 `intraday / futures / flow`와 정식 상태의 차이를 더 직접 반영합니다.

QS 쪽에서는 공개 페이지에서
- `정식 시장상태`
- `오늘 장중 흐름`
을 분리해서 보여 주도록 UI를 보완해 주세요.

작업지시문:
- `D:\QuantMarket\docs\QUANTSERVICE_PUBLIC_MARKET_BRIEFING_STATE_BRIDGE_AND_AI_REFRESH_TASK_PROMPT_20260326.md`
