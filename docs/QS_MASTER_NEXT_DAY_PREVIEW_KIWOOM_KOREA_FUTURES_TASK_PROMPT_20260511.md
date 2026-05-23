# QS-Master 작업요청서

- QS 요청 제출처: QS-Master
- 권장 담당 쓰레드: QS-QM-Handoff, QS-Public-Web
- 공개 반영 포함 여부: Yes
- Admin only 여부: No
- 관련 시스템: QuantMarket

## 작업명

내일 시장 전망 블록의 한국 야간 신호 2원화 표시 반영 요청

## 배경

QuantMarket의 `내일 시장 전망 참고` payload에 한국 관련 야간 신호를 2개 축으로 제공하도록 보강했습니다.

기존:
- `KOREA_PROXY_EWY`: 미국 상장 한국 ETF 기반 해외 프록시

추가:
- `KOSPI200_NIGHT_FUT`: Kiwoom REST 기반 국내 야간선물 후보 신호

현재 Kiwoom REST 인증은 성공하지만, 기본 후보 TR은 가격/등락률을 제공하지 않아 `is_fallback=true`로 내려갈 수 있습니다.
따라서 QS는 값이 있는 경우만 공개 표시하고, fallback 또는 null 값은 숨기거나 "수집 대기"로 처리해 주세요.

## 대상 payload

- `quantservice_market_next_day_preview.json`
- `api_v1_market_analysis_next_day_preview.json`

## 추가/확인 필드

`overnight_assets[]`에 아래 asset code가 제공됩니다.

```json
{
  "asset_code": "KOSPI200_NIGHT_FUT",
  "asset_name": "국내 야간선물(Kiwoom REST)",
  "asset_group": "korea_futures",
  "price": null,
  "change_pct": null,
  "source": "kiwoom_rest_fallback_error:RuntimeError",
  "is_fallback": true
}
```

기존 EWY 프록시는 계속 제공됩니다.

```json
{
  "asset_code": "KOREA_PROXY_EWY",
  "asset_name": "미국 상장 한국 ETF",
  "asset_group": "korea_proxy"
}
```

`biases`에는 아래 값이 추가됩니다.

```json
{
  "korea_signal_alignment": "aligned | mixed | single_source | unavailable"
}
```

## QS 표시 요청

내일 시장 전망 블록의 한국 관련 야간 신호 영역을 아래처럼 표현해 주세요.

- 국내 야간선물: `KOSPI200_NIGHT_FUT`
- 해외 한국 프록시: `KOREA_PROXY_EWY`
- 두 값이 모두 있으면 병행 표시
- 한 값만 있으면 단독 표시
- `is_fallback=true` 또는 `change_pct=null`이면 해당 행은 공개 표시에서 제외

## 권장 문구

- 국내 야간선물: "국내 야간선물"
- 해외 한국 프록시: "미국 상장 한국 ETF"
- 방향 불일치 시: "국내/해외 한국 신호가 엇갈려 장초반 변동성 확인이 필요합니다."

## 완료 기준

1. QS가 `overnight_assets[]`에서 `KOSPI200_NIGHT_FUT`와 `KOREA_PROXY_EWY`를 구분해서 읽을 수 있음
2. 정상 값만 공개 표시하고 fallback/null 값은 숨김 처리됨
3. `korea_signal_alignment=mixed`일 때 방향 엇갈림 안내 문구를 사용할 수 있음
4. 기존 내일 시장 전망 블록 및 기존 EWY 표시는 깨지지 않음
