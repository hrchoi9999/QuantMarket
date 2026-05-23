# QS-Master 작업요청: 시장 흐름 3축 그래프 주가지수 기준선 표시

- QS 요청 제출처: QS-Master
- 권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
- 공개 반영 포함 여부: Yes
- Admin only 여부: No
- 관련 시스템: QuantMarket

## 배경
QuantMarket 시장 상태 종합판의 3축 그래프에 실제 국내 주가지수 흐름을 함께 비교할 수 있도록 payload를 확장했습니다.

## QM 제공 변경
대상 payload:
- `quantservice_market_page.json`
- `api_v1_market_analysis_page.json`

경로:
- `market_state_composite.composite_chart.reference_indices`

제공 series:
- `KOSPI 기준지수`
- `KOSDAQ 기준지수`
- `KOSPI200 기준지수`

각 series 주요 필드:
- `series_id`
- `label`
- `color`
- `unit`: `indexed_100`
- `base_date`
- `base_value`: `100.0`
- `latest_date`
- `latest_value`
- `latest_close`
- `source`
- `points[]`: `{ date, value, raw_close }`

## 표시 요청
1. 기존 3개 score line은 그대로 유지합니다.
2. `reference_indices`는 보조 y축 기준으로 점선 또는 얇은 중립선으로 표시합니다.
3. 기준선 값은 `base_date=100` 환산값이며, tooltip에는 `raw_close` 실제 종가도 함께 보여 주세요.
4. 범례에서는 점수선과 주가지수 기준선을 구분해 주세요.
5. 보조 y축 라벨은 `주가지수 기준선(기준일=100)`으로 표시해 주세요.

## 주의
- 주가지수 기준선은 시장상태 점수가 아니라 실제 지수 흐름 비교용입니다.
- 상승/하락 색상 의미를 과도하게 부여하지 말고 중립색/점선으로 표시하는 것이 좋습니다.

## 완료 기준
- 시장 흐름 3축 그래프에서 금융시장 환경/퀀트모델 시장전망/단기 시장상황 3개 score line과 KOSPI/KOSDAQ/KOSPI200 기준선이 함께 표시됩니다.
- tooltip에서 기준선 환산값과 실제 종가를 확인할 수 있습니다.
