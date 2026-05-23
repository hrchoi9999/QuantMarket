# QuantMarket Kiwoom Korea Night Futures Integration Note

작성일: 2026-05-11

## 목적

`내일 시장 전망 참고` payload에서 한국 관련 야간 신호를 EWY 단일 프록시에만 의존하지 않고,
Kiwoom REST 기반 국내 야간선물 후보 데이터를 함께 수집할 수 있도록 보조 원천을 추가한다.

## 적용 범위

- 대상 payload:
  - `quantservice_market_next_day_preview.json`
  - `api_v1_market_analysis_next_day_preview.json`
  - `market_next_day_preview.json`
- 신규 자산 코드:
  - `KOSPI200_NIGHT_FUT`
- 병행 유지 자산 코드:
  - `KOREA_PROXY_EWY`

## 현재 구현

- Kiwoom REST 인증은 `D:\Quant\config`의 키 파일을 read-only로 읽는다.
- 키 파일 값은 로그, payload, 문서에 저장하지 않는다.
- Kiwoom REST 수집 실패 또는 가격 필드 미확인 시에도 payload에는 fallback 행을 남긴다.
- 기존 Yahoo 기반 EWY, S&P500 선물, 나스닥100 선물, USD/KRW, WTI, US10Y 수집은 유지한다.

## payload 필드

`overnight_assets[]`에 아래 행이 추가된다.

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

정상 수집 시에는 `price`, `change_pct`, `source`, `is_fallback=false`가 제공된다.

## 해석 로직

- `KOSPI200_NIGHT_FUT`가 정상 수집되면 내일 전망의 `overnight_futures_bias`에 우선 반영한다.
- `KOREA_PROXY_EWY`는 해외 시장에서 보는 한국 관련 위험자산 프록시로 계속 반영한다.
- 두 신호가 함께 있으면 `biases.korea_signal_alignment`에 아래 값을 제공한다.
  - `aligned`: 방향 일치
  - `mixed`: 방향 불일치
  - `single_source`: 한쪽만 사용 가능
  - `unavailable`: 둘 다 사용 불가

## 현재 테스트 결과

- Kiwoom REST token 발급: 정상
- 기본 후보 TR:
  - endpoint: `/api/dostk/stkinfo`
  - api-id: `ka10001`
  - body: `{"stk_cd": "A0166000"}`
- 응답: 정상 처리이나 가격/등락률 필드 없음
- 결론: 인증과 adapter는 동작하지만, 국내 야간선물 전용 REST TR 확정이 필요하다.

## 운영 기준

- 현재 PC 개발 단계에서는 fallback-safe 방식으로 유지한다.
- Kiwoom에서 국내 야간선물 또는 해외/파생 전용 REST TR이 확인되면 아래 환경변수만 바꿔 재테스트한다.
  - `QUANTMARKET_KIWOOM_KOREA_FUTURES_ENDPOINT`
  - `QUANTMARKET_KIWOOM_KOREA_FUTURES_API_ID`
  - `QUANTMARKET_KIWOOM_KOREA_FUTURES_BODY`
- 전용 TR 확인 전까지 EWY 프록시는 계속 유지한다.

## 참고

Kiwoom 공식 REST API 공개 가이드는 현재 국내주식 중심의 REST 범주를 제공한다.
따라서 파생/야간선물 전용 REST TR은 별도 확인 또는 Kiwoom Q&A 확인이 필요하다.
