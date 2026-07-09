# QuantMarket WD03 Market Analysis Canonical Policy

작성일: 2026-07-09
대상: QuantOpsScheduler / Harness
소유 thread: QuantMarket 마켓분석 thread

## 결론

WD03_MARKET_ANALYSIS는 QuantMarket의 기존 직접 지시 기준인 `마켓분석 진행`으로 처리한다.
단순 요약 보고가 아니라 public payload 생성, QuantService handoff current 갱신, GCS 게시까지 완료해야 한다.

## 역할 경계

### WD02 / 시장데이터수집 thread

- 지수, 환율, 금리, 국내외 macro, 수급 등 원천/수집성 데이터 갱신
- 수집 범위, 누락, 대체 소스, freshness 보고
- WD03 public payload 생성 또는 GCS 게시를 완료 처리하지 않음

### WD03 / QuantMarket 마켓분석 thread

- WD01/WD02 완료 상태 확인
- 시장분석 payload 생성
- 3축 그래프 입력 mart freshness 확인
- QuantService handoff current 갱신
- GCS current publish 필수 수행
- publish 결과와 known issues 보고

## `run_daily_market_ai_training_update.py` 책임

이 스크립트는 QuantMarket 마켓분석 thread 책임이다.
WD02 시장데이터수집 thread가 직접 호출하면 책임 경계가 흐려진다.

운영 자동화에서 사용할 때는 반드시 아래 profile을 사용한다.

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\run_daily_market_ai_training_update.py --profile operational --expected-asof <target_asof>
```

`--profile operational` 범위:

- market context mart 갱신
- external/global context feature 반영
- domestic flow derivatives 반영
- macro event/surprise mart 반영
- calibrated forecast/current model input mart 갱신
- validation/monitoring/readiness 갱신
- Quant model handoff manifest 갱신

`--profile full` 범위:

- operational 범위 전체
- AI v1.1 fast model 학습
- AI v1.1 vs calibration 비교

`--profile full`은 연구/비교 단계가 포함되므로 Harness WD02/WD03의 일반 운영 자동화에서 기본 호출하면 안 된다.

## asof 표기 원칙

### publish_asof

시장 브리핑 payload와 GCS current 게시 기준 시각이다.
예: `2026-07-09T22:00:00+09:00`

사용처:

- `quantservice_market_manifest.json.asof`
- public market briefing payload
- GCS history prefix 날짜

### data_asof

mart/forecast/current 입력 데이터가 실제로 커버하는 최신 거래일이다.
예: `market_model_input_daily_current.csv max(asof_date) = 2026-07-08`

사용처:

- 3축 그래프 입력 mart freshness 판단
- Quant model handoff `latest_asof_date`
- known issues 보고

### Quant model handoff

- `expected_asof_date`: Quant/Harness target asof
- `latest_asof_date`: primary forecast current 파일에서 실제 사용 가능한 최신 asof
- `production_ready`: `expected_asof_date == latest_asof_date`이고 필수 scope가 모두 있을 때만 true

따라서 `publish_asof=2026-07-09T22:00:00+09:00` 이더라도,
`latest_asof_date=2026-07-08`이면 Quant model handoff는 production_ready=false가 맞다.

## WD03 completed 조건

아래 조건을 모두 만족해야 completed로 보고한다.

- market_analysis public payload 생성 완료
- QuantService handoff current 갱신 완료
- GCS current publish 완료
- remote publish report 생성 완료
- current manifest의 publish_asof 확인 완료
- 3축 그래프가 stale mart를 단순 carry-forward만으로 표시하지 않는지 확인 완료
- data_asof와 publish_asof가 다르면 known_issues에 분리 보고

## Harness 반영 문구

WD03 요청에는 아래 문구를 포함한다.

```text
QuantMarket WD03는 기존 사용자가 직접 지시하던 "마켓분석 진행" 범위로 수행한다.
단순 요약 보고가 아니라 market_analysis public payload 생성, QuantService handoff current 갱신, GCS current publish까지 필수 완료 조건이다.

WD03 시작 전 3축 그래프 입력 mart freshness를 확인한다.
- market_model_input_daily_current.csv max(asof_date)
- market_forecast_ai_calibrated_daily_current.csv max(asof_date)

위 data_asof가 target asof보다 과거이면, QuantMarket 마켓분석 thread에서 운영용 mart refresh를 수행한다.
호출 시에는 연구/비교 단계가 제외된 다음 명령만 사용한다.
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\run_daily_market_ai_training_update.py --profile operational --expected-asof <target_asof>

WD02 시장데이터수집 thread는 이 스크립트를 직접 호출하지 않는다.

publish_asof와 data_asof는 분리해서 보고한다.
Quant model handoff는 expected_asof와 latest_asof가 다르면 production_ready=false로 유지하고, 이를 known_issues에 명시한다.
GCS 게시 실패 시 completed가 아니라 blocked 또는 failed로 보고한다.
```
