# QS-Master 작업요청서: 시장 환경 지표 공개 메뉴 연동

- QS 요청 제출처: QS-Master
- 권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
- 공개 반영 포함 여부: Yes
- Admin only 여부: No
- 관련 시스템: QuantMarket

## 작업명
redbot.co.kr `시장 환경 지표` 메뉴 추가 및 QM 시장환경지표 payload 차트 렌더링

## 배경
QuantMarket에서 국내 시장 원천 데이터, FRED 매크로/금리 데이터, Yahoo 글로벌 시장 데이터를 웹 차트용 public payload로 제공합니다.
QS는 계산이나 재가공 없이 remote handoff JSON을 읽어 공개 페이지에 그래프로 표시하면 됩니다.

## QM 제공 파일
base URL:

`https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current`

신규 파일:

- `quantservice_market_environment_indicators.json`
- `api_v1_market_environment_indicators.json`
- `quantservice_market_environment_indicators_manifest.json`

주요 payload shape:

- `market`
- `asof`
- `generated_at`
- `timezone`
- `title`
- `description`
- `chart_policy`
- `sections[]`
- `compliance_meta`
- `notice_block`

`sections[]` 순서는 고정입니다.

1. `domestic_source`: 국내 시장 원천 데이터
2. `fred_macro`: FRED 매크로/금리 데이터
3. `yahoo_global`: Yahoo 글로벌 시장 데이터

각 section의 `series[]` 필드:

- `series_id`
- `display_name_kr`
- `category_label_kr`
- `source_provider`
- `source_detail`
- `source_tier`
- `unit`
- `frequency`
- `start_date`
- `end_date`
- `row_count`
- `period_label`
- `latest_date`
- `latest_value`
- `chart_type`
- `default_chart_height_px`
- `popup_enabled`
- `points[]`: `{ date, value }`

## QS 구현 요청
1. redbot.co.kr 상단 메뉴에 `시장 환경 지표`를 추가해 주세요.
2. 신규 페이지에서 `quantservice_market_environment_indicators.json`을 remote handoff로 읽어 주세요.
3. 섹션 표시 순서는 반드시 `국내 시장 원천 데이터` → `FRED 매크로/금리 데이터` → `Yahoo 글로벌 시장 데이터` 순서로 고정해 주세요.
4. 모든 series는 선 그래프 카드로 표시해 주세요.
5. 기본 그래프는 작게 표시해 주세요.
   - 기본 높이: payload의 `default_chart_height_px`, 기본값 160px
   - 모바일: 1열
   - 데스크톱: 2열 또는 3열 카드형
6. 그래프 카드를 클릭하면 팝업/모달로 확대 그래프를 보여 주세요.
   - 팝업 그래프 높이: payload `chart_policy.popup_chart_height_px`, 기본값 420px
7. 그래프 제목은 `display_name_kr`를 사용해 주세요.
8. 그래프 하단 또는 우측에 아래 정보를 표시해 주세요.
   - `period_label`
   - `source_provider`
   - `source_detail`
9. section에 `coverage_warning`이 있으면 section 상단에 안내 배지 또는 안내문으로 표시해 주세요.
10. `notice_block`은 페이지 하단에 표시해 주세요.
11. 데이터 없는 series는 숨기지 말고 `데이터 준비 중` 상태로 표시해 주세요.

## UI 문구 가이드
페이지 제목:

`시장 환경 지표`

페이지 설명:

`국내 지수와 환율, 미국 금리와 물가, 글로벌 ETF 흐름을 한 화면에서 확인하는 공개형 시장 데이터입니다.`

데이터 안내:

`차트는 화면 성능을 위해 최근 3년 구간을 우선 표시하며, 각 지표의 전체 보유기간은 기간 정보로 함께 제공합니다.`

주의 문구:

`본 정보는 공개 시장 데이터의 흐름을 보여주는 참고 자료이며, 특정 종목이나 자산의 매수·매도 권유가 아닙니다.`

## 완료 기준
1. `/market-environment-indicators` 또는 QS가 정한 공개 경로에서 페이지 접근 가능
2. 신규 메뉴 `시장 환경 지표` 노출
3. 국내/FRED/Yahoo 순서 정상 표시
4. 모든 지표가 선 그래프로 표시
5. 카드 클릭 시 확대 팝업 정상 표시
6. 기간과 자료 근거 표시
7. `coverage_warning`과 `notice_block` 표시
8. remote payload 누락/빈 series에도 페이지 깨짐 없음

## 비고
- QM은 시장 환경 지표 payload 생산만 담당합니다.
- QS는 UI, 라우팅, 메뉴, 그래프 렌더링, 팝업 동작을 담당합니다.
- 해당 정보는 모든 사용자에게 동일하게 제공되는 공개 참고 정보이며 개인별 투자자문이 아닙니다.
