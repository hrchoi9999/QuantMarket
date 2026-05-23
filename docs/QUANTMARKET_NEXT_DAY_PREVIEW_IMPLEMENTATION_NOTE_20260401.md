# QUANTMARKET_NEXT_DAY_PREVIEW_IMPLEMENTATION_NOTE_20260401.md

## 구현 범위

`내일 시장 전망 참고` 레이어를 `QuantMarket` public payload 체계에 추가했다.

이 레이어는 아래 3단 구조의 세 번째 축이다.

- `퀀트모델 시장 흐름`
- `오늘 장중 흐름`
- `내일 시장 전망 참고`

## 구현 파일

- `src/quantmarket_market/next_day_preview.py`
- `src/quantmarket_market/pipeline.py`
- `src/quantmarket_market/schema.py`
- `src/quantmarket_market/payloads.py`
- `src/quantmarket_market/remote_publish.py`
- `src/quantmarket_market/config.py`

## 신규 테이블

- `market_overnight_asset_snapshot`
- `market_overnight_news_context`
- `market_next_day_preview_state`

## 신규 current 파일

- `service_platform/web/public_data/current/market_next_day_preview.json`
- `service_platform/web/public_data/handoff/quantservice/current/quantservice_market_next_day_preview.json`
- `service_platform/web/public_data/handoff/quantservice/current/api_v1_market_analysis_next_day_preview.json`
- `service_platform/web/public_data/handoff/quantservice/current/market_next_day_preview_manifest.json`

## snapshot history

- `service_platform/web/public_data/next_day_preview/snapshot/YYYY-MM-DD/`

## 핵심 필드

- `active_now`
- `reference_session`
- `preview_label`
- `preview_score`
- `headline_line`
- `summary_line`
- `supporting_points`
- `risk_points`
- `overnight_assets`
- `market_flow_label`
- `content_hash`
- `material_change_flag`

## 현재 원천

- Yahoo chart
  - `EWY`
  - `ES=F`
  - `NQ=F`
  - `KRW=X`
  - `CL=F`
  - `^TNX`
- Google News RSS

## 운영 원칙

- 기존 `퀀트모델 시장 흐름`을 덮어쓰지 않는다.
- `오늘 장중 흐름`을 덮어쓰지 않는다.
- `내일 시장 전망 참고`는 별도 참고 카드로만 사용한다.
- `active_now=true`인 시간대는 `18:00 ~ 익일 08:30` KST 기준이다.
- 문구는 참고형/확률형으로만 유지한다.

## 검증 상태

- 로컬 current 생성 확인
- DB 적재 확인
- GCS public current publish 확인
- `quantservice_market_next_day_preview.json` 원격 current 반영 확인
