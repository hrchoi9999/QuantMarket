# QS-Master 작업요청서: 시장 상태 막대 3라인 종합 그래프 전환

- QS 요청 제출처: QS-Master
- 권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
- 공개 반영 포함 여부: Yes
- Admin only 여부: No
- 관련 시스템: QuantMarket

## 작업명
시장 브리핑 상단 `시장 상태 막대`를 3라인 종합 그래프 + 핵심지표 패널로 전환

## 배경
기존 시장 상태 막대는 단순 막대 중심이라, 현재 QM에서 수집하는 금융시장 환경 지표, 중기 모델 전망, 단기 시장 상황을 한눈에 해석하기 어렵습니다.

QM은 기존 필드와 하위호환성을 유지하면서 신규 payload 필드 `market_state_composite`를 v2로 확장했습니다.

## QM 제공 위치
- `quantservice_market_page.json`
- `quantservice_market_home.json`
- `quantservice_market_today.json`
- API wrapper:
  - `api_v1_market_analysis_page.json`
  - `api_v1_market_analysis_home.json`
  - `api_v1_market_analysis_today_bridge.json`

## 신규 필드
`market_state_composite`

주요 shape:
```json
{
  "enabled": true,
  "schema_version": "market_state_composite.v2",
  "title": "시장 상태 종합판",
  "subtitle": "세 개의 막대가 아니라 세 개의 흐름선을 한 그래프에서 비교합니다.",
  "display_policy": {
    "preferred_layout": "multi_line_chart_with_indicator_panel",
    "mobile_layout": "chart_first_then_indicator_cards",
    "primary_visual": "one_chart_three_colored_lines",
    "avoid_three_separate_bar_charts": true,
    "keep_legacy_state_intraday_bridge": true
  },
  "composite_chart": {
    "graph_type": "multi_line",
    "series": [
      {"series_id": "financial_environment", "label": "금융시장 환경", "color": "#2563eb"},
      {"series_id": "medium_term_model_outlook", "label": "퀀트모델 시장전망", "color": "#dc2626"},
      {"series_id": "short_term_market_condition", "label": "단기 시장상황", "color": "#16a34a"}
    ]
  },
  "key_indicators": {"groups": []},
  "investment_considerations": [],
  "axes": [
    {
      "axis_id": "financial_environment",
      "title": "금융시장 환경",
      "subtitle": "기회와 리스크",
      "graph_type": "dual_gauge"
    },
    {
      "axis_id": "medium_term_model_outlook",
      "title": "퀀트모델 시장 전망",
      "subtitle": "1~6개월 흐름",
      "graph_type": "seven_step_bar"
    },
    {
      "axis_id": "short_term_market_condition",
      "title": "단기 시장 상황",
      "subtitle": "최근 1주일 + 오늘",
      "graph_type": "linear_gauge"
    }
  ],
  "summary": {
    "environment": "...",
    "medium_term": "...",
    "short_term": "...",
    "one_line": "..."
  }
}
```

## 화면 적용 요청
시장 브리핑 상단의 기존 시장상태 막대 영역을 `market_state_composite.composite_chart` 기반 3라인 종합 그래프로 교체해 주세요.

기본 레이아웃:
- 데스크톱: 좌측 65~70%는 하나의 선형 그래프, 우측 30~35%는 핵심지표/고려사항 패널
- 모바일: 그래프 먼저, 핵심지표 그룹과 고려사항은 아래 카드로 스택
- 기존 `state_intraday_bridge`는 fallback으로 유지

그래프 표시:
- `composite_chart.graph_type=multi_line`
- `composite_chart.series[]` 3개를 하나의 그래프 안에 서로 다른 색상으로 표시
- X축: 날짜
- Y축: 점수, -3 ~ +3 고정
- 중립권: -0.3 ~ +0.3 영역을 얇은 배경 밴드로 표시
- 마지막 값에는 마커와 숫자 라벨 표시
- 3개 막대 그래프나 3개 별도 차트로 분리하지 말 것

우측 핵심지표 패널:
- `key_indicators.groups[]`를 그룹별로 표시
- 금융시장 환경: VIX, 미국 10년 금리, 달러지수, WTI, 하이일드 스프레드 등
- 퀀트모델 시장전망: 7단계 시장상태, 시장상태 점수, 20거래일 전망 참고값, 신뢰도 등
- 단기 시장상황: 코스피/코스닥 1주일, 오늘 장중 상태, 선물, 외국인/프로그램 수급 등

투자시 고려사항:
- `investment_considerations[]`를 그래프 하단 또는 우측 하단에 표시
- tone 값에 따라 positive / neutral / warning 정도의 색상만 사용
- 문구는 참고 정보로 표시하고 개별 매수·매도 판단처럼 보이지 않게 할 것

## 표현 가이드
- 제목은 `시장 상태 종합판` 또는 `시장 흐름 종합 보기`
- 그래프 legend는 `composite_chart.series[].label` 사용
- 숫자는 과도한 투자판단 문구 없이 참고 지표로 표시
- `forecast_20d.predicted_forward_return_pct`는 “예측 수익률” 단독 강조 금지
- 권장 표기: `20거래일 전망 참고값`
- 하단에 `interpretation_rules`를 접기/도움말 형태로 노출

## fallback
- `market_state_composite.enabled !== true`이면 기존 `state_intraday_bridge` 렌더링 유지
- 축별 데이터가 일부 없으면 해당 숫자만 `데이터 확인 중`으로 표시
- 페이지 전체 렌더링은 깨지지 않아야 함

## 완료 기준
1. 시장 브리핑 상단에서 3개 선이 하나의 그래프 안에 표시됨
2. 그래프 옆에 핵심지표와 투자시 고려사항이 함께 표시됨
3. 기존 `state_intraday_bridge`만 있는 payload에서도 fallback 정상 동작
4. 모바일 1열 표시 정상
5. 문구가 개별 투자자문으로 보이지 않도록 기존 notice/compliance 유지
