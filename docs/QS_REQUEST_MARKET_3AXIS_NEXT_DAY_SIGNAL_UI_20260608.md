# QuantService 작업요청서: 시장 현황판 3축 그래프 익일 신호 테스트 UI 반영

작성일: 2026-06-08

## 배경

QuantMarket에서 시장 현황판 3축 그래프 payload에 `익일 신호 테스트`를 기존 3축 선과 연결되는 보조 포인트로 추가했습니다.

## QuantMarket 제공 데이터

대상 파일:

- `quantservice_market_page.json`
- `api_v1_market_analysis_page.json`
- `quantservice_market_today.json`
- `api_v1_market_analysis_today_bridge.json`

위 파일의 `market_state_composite.composite_chart.series[].points`에 아래 형태의 익일 포인트가 포함됩니다.

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
  "date_tone": "muted"
}
```

현재 적용 축:

- `financial_environment`: 익일 금융환경 테스트
- `short_term_market_condition`: 익일 단기상황 테스트

`medium_term_model_outlook`은 정식 퀀트모델 전망축이므로 익일 테스트 포인트를 붙이지 않습니다.

## 요청 사항

1. 기존 3축 그래프에서 `point_role = next_day_signal_test` 포인트를 같은 선/색상으로 연결 표시해 주세요.
2. 오늘 날짜와 익일 날짜가 함께 보이도록 x축 마지막 라벨에 익일 날짜를 표시해 주세요.
3. 익일 날짜 라벨은 `date_tone = muted` 기준으로 회색 처리해 주세요.
4. 익일 포인트 tooltip에는 `display_label`, `preview_label`, `official_score_impact=false`, `검증 전 실험값` 문구를 표시해 주세요.
5. 범례에는 기존 3축명은 유지하고, 별도 범례를 추가한다면 `익일 신호 테스트는 정식 점수 미반영`으로 표시해 주세요.

## 주의

- 익일 포인트는 정식 시장 현황판 점수 계산에 포함되지 않습니다.
- UI에서는 예측 확정값이 아니라 `익일 신호 테스트` 또는 `검증 전 실험값`으로 표현해야 합니다.
- QuantMarket은 데이터 생산만 담당하며, 실제 그래프 렌더링 스타일 변경은 QuantService에서 처리해야 합니다.
