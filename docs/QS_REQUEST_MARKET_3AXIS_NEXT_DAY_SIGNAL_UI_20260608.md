# QuantService 작업요청서: 시장 현황판 3축 그래프 익일 신호 테스트 UI 반영

작성일: 2026-06-08

## 배경

QuantMarket에서 시장 현황판 3축 그래프 payload에 `익일 신호 테스트`를 제공합니다.

2026-06-14 개정: 익일 신호를 `series[].points`에 넣으면 x축 마지막 날짜가 익일로 밀리면서 당일 포인트가 누락되어 보이는 문제가 반복되었습니다. 따라서 익일 신호는 본 그래프 날짜축 계산에서 제외되는 `preview_points`로 분리합니다.

## QuantMarket 제공 데이터

대상 파일:

- `quantservice_market_page.json`
- `api_v1_market_analysis_page.json`
- `quantservice_market_today.json`
- `api_v1_market_analysis_today_bridge.json`

위 파일의 `market_state_composite.composite_chart.series[].preview_points`에 아래 형태의 익일 포인트가 포함됩니다.

```json
{
  "date": "2026-06-09",
  "value": -0.6212,
  "label": "익일",
  "point_role": "next_day_signal_test",
  "display_label": "익일 금융환경 테스트",
  "preview_label": "장초반 경계 흐름",
  "official_score_impact": false,
  "experiment_status": "validation_required",
  "color": "#2563eb",
  "date_axis_policy": "exclude_from_main_axis",
  "point_color_policy": "same_as_parent_series",
  "tooltip_policy": "same_as_regular_point"
}
```

동일 내용은 `market_state_composite.composite_chart.preview_points`에도 `series_id` 포함 형태로 제공됩니다.

현재 적용 축:

- `financial_environment`: 익일 금융환경 테스트
- `medium_term_model_outlook`: 익일 종합 신호 테스트
- `short_term_market_condition`: 익일 단기상황 테스트

`medium_term_model_outlook`의 익일 포인트는 정식 퀀트모델 재학습/예측값이 아니라, 야간/장외 종합 신호를 퀀트모델 전망축과 비교하기 위한 테스트 포인트입니다.

## 요청 사항

1. x축 날짜 계산은 `series[].points`와 `reference_indices[].points`만 사용해 주세요.
2. `series[].preview_points`는 본 날짜축에 포함하지 말고, 차트 오른쪽 preview layer로 오버레이해 주세요.
3. preview point의 색상, 점 모양, tooltip 세부 UI는 해당 parent series와 동일하게 표시해 주세요.
4. 사용자 화면에서는 preview point를 실데이터 포인트와 시각적으로 구분하지 않도록 해 주세요.
5. 데이터 내부의 `point_role`, `official_score_impact=false`, `experiment_status`는 유지하되, 기본 tooltip에서는 기존 포인트와 같은 정보 구조를 사용해 주세요.
6. 별도 안내문이 필요하면 차트 밖 주석 영역에만 `익일 신호 테스트는 정식 점수 미반영`으로 표시해 주세요.

## 주의

- 익일 포인트는 정식 시장 현황판 점수 계산과 본 그래프 날짜축 계산에 포함되지 않습니다.
- UI에서는 preview point의 색상과 상세 표시를 parent series와 일관되게 유지해야 합니다.
- QuantMarket은 데이터 생산만 담당하며, 실제 그래프 렌더링 스타일 변경은 QuantService에서 처리해야 합니다.
