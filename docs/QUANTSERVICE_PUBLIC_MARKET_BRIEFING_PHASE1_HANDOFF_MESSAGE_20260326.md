QS 전달 메시지

QuantMarket 쪽에서 시장브리핑 고도화 1차 public payload를 추가 생산했고, GCS current까지 반영해 두었습니다.

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

최신 manifest에는 아래가 반영돼 있습니다.
- `optional_files`
- `api_endpoints`
- `data_lineage.public_rollout_phase = market_briefing_enhancement_phase1`

중요:
- 이번 1차 public 반영은 `정식 시장브리핑` 강화입니다.
- `장중 intraday / 선물 / 수급`은 아직 public 미반영입니다.
- admin 전용으로만 유지해 주세요.

최신 기준시각:
- `2026-03-26T17:06:37+09:00`

공용 base URL:
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current`

작업지시문:
- `D:\QuantMarket\docs\QUANTSERVICE_PUBLIC_MARKET_BRIEFING_PHASE1_TASK_PROMPT_20260326.md`
