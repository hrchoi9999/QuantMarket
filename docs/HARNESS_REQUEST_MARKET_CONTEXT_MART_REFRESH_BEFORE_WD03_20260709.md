# QuantMarket -> Harness 작업요청서

작성일: 2026-07-09
대상: QuantOpsScheduler / Harness thread
요청 주체: QuantMarket 마켓분석 thread

## 요청 요약

WD03_MARKET_ANALYSIS 실행 전에 QuantMarket의 3축 그래프 입력 mart가 최신 기준일로 갱신되었는지 확인하고, stale이면 갱신 단계를 명시적으로 수행하도록 Harness flow를 보완해 주세요.

## 발생한 문제

- 시장 브리핑의 `시장흐름 3축 그래프`에서 2026-06-26 이후 값이 반복 표시되었습니다.
- 원인은 그래프 생성 로직이 `service_platform/ai_training/market_context/current/market_model_input_daily_current.csv`를 사용했는데, 이 파일의 max `asof_date`가 2026-06-26에 멈춰 있었기 때문입니다.
- WD02 public payload 생성과 WD03 요약 확인은 수행됐지만, 3축 그래프 입력 mart 갱신이 Harness 단계에 명시되어 있지 않아 stale mart가 계속 이월되었습니다.

## QuantMarket에서 조치한 내용

- `src/quantmarket_market/market_state_composite.py` 수정.
- `market_model_input_daily_current.csv`가 target asof보다 오래된 경우, DB에 저장된 기존 `detail` payload의 3축 값을 날짜별로 복구해 그래프에 보강하도록 했습니다.
- 현재 기준일은 실행 시점의 최신 `market_component_scores` / intraday blend 값으로 덮어써서 최신 포인트가 stale 값으로 남지 않게 했습니다.
- 로컬 payload 재생성 및 2026-06-26~2026-07-08 구간 3축 값 변동 확인 완료.

## Harness 수정 요청

WD03_MARKET_ANALYSIS 전에 아래 freshness check를 추가해 주세요.

1. `D:\QuantMarket\service_platform\ai_training\market_context\current\market_model_input_daily_current.csv`의 max `asof_date` 확인
2. max `asof_date`가 Harness target `asof`보다 과거이면 WD03를 바로 진행하지 말고 `blocked` 또는 `needs_market_context_mart_refresh`로 보고
3. 사용자의 직접 지시 범위에 해당하는 경우에만 QuantMarket thread에 아래 작업을 요청
   - `run_daily_market_ai_training_update.py --expected-asof <target_asof>` 또는 동일한 market context mart 갱신 단계
   - 이후 market-analysis public payload 재생성
4. 새 forecast/context 재생성이 금지된 좁은 WD03 요청이라면, WD03 보고서의 `known_issues`에 mart stale을 반드시 명시

## 권장 Harness 판정 규칙

- WD01/WD02가 completed라도 `market_model_input_daily_current.csv` max date가 target asof와 다르면 WD03는 정상 completed로 처리하지 않는 것이 안전합니다.
- 단, QuantMarket 코드에는 DB payload fallback이 추가되었으므로 웹 그래프 표시 자체는 방어됩니다.
- 근본 해결은 Harness가 3축 입력 mart freshness를 WD03 선행조건으로 관리하는 것입니다.

## 확인 기준

정상 조건:

- `market_model_input_daily_current.csv` max `asof_date` = target asof
- `market_forecast_ai_calibrated_daily_current.csv` max `asof_date` = target asof
- `quantservice_market_manifest.json` asof = target asof `T19:00:00+09:00`
- `api_v1_market_analysis_detail.json`의 `data.market_state_composite.composite_chart.series[*].points`에서 target 기간 값이 단순 carry-forward만으로 채워지지 않음

## 참고 파일

- `D:\QuantMarket\src\quantmarket_market\market_state_composite.py`
- `D:\QuantMarket\service_platform\ai_training\market_context\current\market_model_input_daily_current.csv`
- `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current\api_v1_market_analysis_detail.json`
