QS 요청 제출처: QS-Master
권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
공개 반영 포함 여부: Yes
Admin only 여부: No
관련 시스템: QuantMarket

작업 목적:
- 공개 `내일 시장 전망 참고` 카드에서 국내시장 관련 야간선물 신호가 사용자에게 직접 보이도록 UI를 보완합니다.
- 현재 QuantMarket payload에는 `KOSPI200_NIGHT_FUT`가 포함되어 있으나, 공개 페이지에서는 이 자산 항목이 아직 명시적으로 드러나지 않는 것으로 보입니다.

배경:
- QuantMarket public payload의 `overnight_assets`에는 현재 아래 자산이 포함됩니다.
  - `KOSPI200_NIGHT_FUT`
  - `KOREA_PROXY_EWY`
  - `SP500_FUT`
  - `NASDAQ100_FUT`
  - `USDKRW`
  - `WTI`
  - `US10Y`
- 이 중 `KOSPI200_NIGHT_FUT`는 한국시장 장초반 참고에 가장 직접적인 국내 야간선물 신호이므로, 공개 카드에서도 우선 노출하는 것이 적절합니다.

사용 파일:
- `quantservice_market_next_day_preview.json`
- `api_v1_market_analysis_next_day_preview.json`

사용 필드:
- `overnight_assets[]`
- `preview_label`
- `headline_line`
- `summary_line`
- `supporting_points[]`
- `risk_points[]`
- `display_title`
- `display_subtitle`
- `active_now`

핵심 반영 요청:
1. `내일 시장 전망 참고` 카드에서 `overnight_assets`를 실제로 사용해 주세요.
2. `asset_code = KOSPI200_NIGHT_FUT`가 있으면 국내 야간선물 항목을 첫 번째 또는 최상단에 우선 노출해 주세요.
3. `KOSPI200_NIGHT_FUT`가 없을 때만 `KOREA_PROXY_EWY`를 한국시장 대체 항목으로 사용해 주세요.
4. 자산 노출은 길게 표를 늘리기보다 1~3개 핵심 자산 요약 형태가 적절합니다.

권장 표시 방식:
- 카드 내부에 `야간 핵심 자산` 또는 `야간 자산 흐름` 작은 섹션 추가
- 노출 우선순위:
  1. `KOSPI200_NIGHT_FUT`
  2. `SP500_FUT`
  3. `USDKRW`
- 표시 항목:
  - 자산명
  - 등락률 또는 방향
  - 짧은 상태 라벨

권장 라벨 예시:
- `코스피200 야간선물 +0.42%`
- `S&P500 선물 +0.30%`
- `원달러 +0.12%`

표현 원칙:
1. `KOSPI200_NIGHT_FUT`는 `국내 야간선물` 또는 `코스피200 야간선물`로 사용자 친화적으로 표시
2. `KOREA_PROXY_EWY`는 공개 화면에서 기본 우선 노출 대상이 아님
3. 프록시를 써야 하는 경우에는 `미국 상장 한국 ETF`로 표시
4. 자문형 문구 금지

노출 조건:
- `active_now = true`일 때 기본 노출
- `active_now = false`면 섹션 숨김 또는 약한 톤 처리

fallback 규칙:
1. `KOSPI200_NIGHT_FUT` 존재 시 이를 우선 표시
2. `KOSPI200_NIGHT_FUT` 누락 시 `KOREA_PROXY_EWY`로 fallback
3. 둘 다 없으면 한국시장 항목은 숨기고 글로벌 자산만 표시 가능
4. payload 누락 시 기존 카드 구조 유지

QA 체크리스트:
- [ ] `내일 시장 전망 참고` 카드에서 국내 야간선물이 실제로 보이는가
- [ ] `KOSPI200_NIGHT_FUT`가 있을 때 EWY보다 우선 노출되는가
- [ ] `active_now=true` 구간에서만 자연스럽게 보이는가
- [ ] 모바일에서도 카드가 과밀하지 않은가
- [ ] 기존 공개 페이지 레이아웃이 깨지지 않는가
