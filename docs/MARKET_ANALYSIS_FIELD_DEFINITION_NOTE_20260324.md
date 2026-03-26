# QuantMarket Field Definition Note

작성일: 2026-03-24
대상: QuantService 시장분석 소비 레이어

## 1. 지수 수익률 필드 의미

아래 필드는 모두 QuantMarket 내부에서 `period return ratio`로 계산됩니다.
계산식은 `최근 종가 / N거래일 전 종가 - 1` 입니다.

대상 필드:
- `kospi_20d_ret`
- `kospi_60d_ret`
- `kosdaq_20d_ret`

의미 정리:
- 자료형 의미: 기간 수익률 ratio
- 예시: `0.052` 는 `+5.2%`
- 따라서 사용자 화면에서 `%`로 보이게 하려면 `100`을 곱해 표시하는 것이 맞습니다.

권장 사용자 라벨:
- `kospi_20d_ret` -> `코스피 1개월 수익률`
- `kospi_60d_ret` -> `코스피 3개월 수익률`
- `kosdaq_20d_ret` -> `코스닥 1개월 수익률`

주의 메모:
- 현재 원천 시계열 정합성 확인 전까지는 위 3개 필드를 사용자 화면 기본 노출보다 내부 검증용으로 우선 사용하는 것을 권장합니다.
- 이 메모는 handoff의 `metric_definitions.*.visibility_note` 와 `display_metrics.*.default_visible=false` 에도 반영했습니다.

## 2. 사용자용 설명 추가 항목

이번 반영으로 handoff에 아래 설명 메타데이터가 추가되었습니다.

추가 위치:
- `quantservice_market_page.json.descriptions`
- `quantservice_market_page.json.metric_definitions`
- `quantservice_market_page.json.display_metrics`
- `api_v1_market_analysis_detail.json.data.metric_definitions`
- `api_v1_market_analysis_detail.json.data.display_metrics`

설명 예시:
- `state_score`: 상태점수는 여러 시장 신호를 합쳐 현재 장세의 강도를 한눈에 보여 주는 합성 점수입니다.
- `breadth`: breadth는 지수 몇 개가 아니라 시장 안쪽 종목들이 얼마나 넓게 따라오는지를 뜻합니다.
- `market health`: 시장 건강도는 일부 대형주만 오르는지, 많은 종목이 함께 움직이는지를 보여 줍니다.
- `market risk`: 시장 흔들림은 최근 변동성과 낙폭을 반영한 경계 수준입니다.

## 3. display field 추가

QuantService가 바로 쓰기 쉽도록 `display_metrics`를 추가했습니다.

예:
- ratio 계열 -> `%` 변환값 포함
- 금리 변화폭 계열 -> `bp` 변환값 포함

따라서 QuantService는 raw `metrics`를 직접 변환하지 않고도 `display_metrics`를 우선 사용할 수 있습니다.

## 4. 업로드 원칙 유지 여부

현재 QuantMarket 원격 publish 로직은 아래 원칙을 유지합니다.
- current 파일 세트 업로드 후 `quantservice_market_manifest.json` 마지막 갱신
- 파일은 UTF-8 JSON 저장
- manifest에는 `upload_policy.manifest_written_last=true` 명시

관련 코드:
- `D:\QuantMarket\src\quantmarket_market\remote_publish.py`
- `D:\QuantMarket\src\quantmarket_market\payloads.py`
