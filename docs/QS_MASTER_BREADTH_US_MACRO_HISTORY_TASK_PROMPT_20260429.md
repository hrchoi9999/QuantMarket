QS 요청 제출처: QS-Master
권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
공개 반영 포함 여부: Yes
Admin only 여부: No
관련 시스템: QuantMarket

작업명:
시장 분석 메뉴 내 breadth / US macro history 차트 반영 요청

배경:
- QuantMarket에서 `시장 내부 확산 상세`와 `미국/글로벌 매크로 패널`의 current payload에 더해, 차트 렌더링용 history payload를 추가로 제공하기 시작했습니다.
- 이번 요청은 `시장 분석` 메뉴에서 breadth와 US macro를 단순 현재값 카드가 아니라 시계열 차트 중심으로 보여주기 위한 QS 구현 요청입니다.
- 데이터는 공개형 참고 정보이며, 특정 투자행동을 권유하는 표현 없이 시장 구조와 야간 환경을 이해하는 용도로 사용합니다.

QuantMarket upstream 완료 상태:
1. breadth current
- `quantservice_market_breadth_detail.json`
- `api_v1_market_analysis_breadth_detail.json`

2. breadth history
- `quantservice_market_breadth_detail_history.json`
- `api_v1_market_analysis_breadth_detail_history.json`

3. US macro current
- `quantservice_market_us_macro_panel.json`
- `api_v1_market_analysis_us_macro_panel.json`

4. US macro history
- `quantservice_market_us_macro_panel_history.json`
- `api_v1_market_analysis_us_macro_panel_history.json`

공개 URL:
- breadth history
  - `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/history/quantservice_market_breadth_detail_history.json`
- US macro history
  - `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/history/quantservice_market_us_macro_panel_history.json`

breadth history 구조:
- top-level
  - `series`: 종가 기준 breadth 시계열
  - `close_series`: 종가 기준 breadth 시계열
  - `intraday_series`: 장중 breadth 시계열
  - `summary.latest_close_asof`
  - `summary.latest_intraday_asof`
  - `summary.close_points`
  - `summary.intraday_points`
- `close_series[]` 주요 필드
  - `asof`
  - `above_20dma_ratio`
  - `above_60dma_ratio`
  - `adv_dec_ratio`
  - `new_high_count`
  - `new_low_count`
  - `breadth_proxy_flag`
  - `breadth_regime_label`
- `intraday_series[]` 주요 필드
  - `asof`
  - `session_date`
  - `universe_code`
  - `advancers`
  - `decliners`
  - `flat_count`
  - `adv_dec_ratio`
  - `positive_ratio`
  - `source_tier`
  - `status_label`

US macro history 구조:
- top-level
  - `series`: overnight asset 시계열
  - `asset_series`: 자산별 overnight 시계열
  - `preview_series`: next-day preview 시계열
  - `summary.latest_asset_asof`
  - `summary.latest_preview_asof`
  - `summary.asset_points`
  - `summary.preview_points`
- `asset_series[]` 주요 필드
  - `asof`
  - `session_date`
  - `asset_code`
  - `asset_name`
  - `asset_group`
  - `price`
  - `change_value`
  - `change_pct`
  - `source_tier`
  - `direction_label`
  - `status_label`
- `preview_series[]` 주요 필드
  - `asof`
  - `reference_session`
  - `preview_label`
  - `preview_score`
  - `overnight_futures_bias`
  - `global_risk_bias`
  - `overnight_fx_bias`
  - `headline_line`
  - `summary_line`

반영 요청:
1. `시장 분석` 메뉴의 breadth 영역에 breadth history 차트를 추가해 주세요.
2. `close_series`를 사용해 아래 차트를 우선 반영해 주세요.
- `20일선 위 종목 비율` 추이
- `60일선 위 종목 비율` 추이
- `상승/하락 종목 비율` 추이
3. `intraday_series`를 사용해 아래 보조 차트 또는 토글형 차트를 추가해 주세요.
- KOSPI positive_ratio 추이
- KOSDAQ positive_ratio 추이
- 필요하면 KOSPI/KOSDAQ를 토글 또는 2라인으로 구분
4. `시장 분석` 메뉴의 US macro 영역에 us macro history 차트를 추가해 주세요.
5. `asset_series`를 사용해 아래 차트를 우선 반영해 주세요.
- `미국 상장 한국 ETF` 변화율 추이
- `S&P500 선물` 변화율 추이
- `나스닥100 선물` 변화율 추이
- `USD/KRW` 변화율 추이
- `WTI` 변화율 추이
- `미국 10년 금리` 변화율 추이
6. `preview_series`를 사용해 아래 보조 차트를 추가해 주세요.
- `preview_score` 추이
- `overnight_futures_bias`
- `global_risk_bias`
- `overnight_fx_bias`
7. current payload와 history payload를 함께 사용해, 차트 상단에는 최신 값 요약, 하단에는 추이 차트가 오도록 구성해 주세요.

UI 원칙:
- breadth는 `시장 내부 확산`이라는 개념이 직관적으로 보이도록 비율 중심으로 표현
- 종가 breadth와 장중 breadth는 같은 영역에 두되, 서로 다른 데이터 축임을 명확히 표시
- US macro는 `야간 시장 환경 참고` 성격이 드러나도록 표현
- 선물/환율/유가/금리의 방향을 색만으로 구분하지 말고 텍스트와 범례를 함께 제공
- 40~60대 사용자도 읽기 쉽게 축, 범례, 기준 시각, 단위를 분명히 표시

표현 가이드:
- breadth 섹션 권장 제목: `시장 내부 확산 흐름`
- US macro 섹션 권장 제목: `미국/글로벌 야간 흐름`
- 보조 설명 예시:
  - `이 차트는 시장 안쪽 종목들의 확산 흐름을 보여주는 공개형 참고 정보입니다.`
  - `야간 글로벌 지표는 다음 거래일 장초반 환경을 참고하기 위한 정보이며, 국내 퀀트모델 시장 흐름 자체를 대체하지 않습니다.`

Fallback 규칙:
- `series=[]` 또는 해당 하위 배열이 비어 있으면 차트 대신 `히스토리 데이터 축적 중` 안내를 표시
- `intraday_series=[]`이면 종가 breadth 차트만 표시
- `preview_series=[]`이면 asset 차트만 표시
- payload 일부 누락 시 페이지 전체가 깨지지 않도록 안전하게 skip 처리

완료 기준:
1. `시장 분석` 메뉴에서 breadth history 차트가 노출됨
2. `시장 분석` 메뉴에서 US macro history 차트가 노출됨
3. current 요약값과 history 차트가 함께 자연스럽게 연결됨
4. 종가/장중, 국내/야간 데이터 축이 혼동 없이 구분됨
5. 공개형 비자문 표현 원칙이 유지됨
