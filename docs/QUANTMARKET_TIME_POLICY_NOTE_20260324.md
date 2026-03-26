# QuantMarket Time Policy Note

작성일: 2026-03-24
대상: QuantMarket / QuantService 연동 담당

## 목적
QuantMarket이 생산하는 시장분석 데이터의 모든 기준 시각을 `KST(Asia/Seoul, +09:00)`로 통일하기 위한 운영 원칙을 정리합니다.

## 시간 정책
1. `asof`는 항상 KST 기준 시각으로 저장합니다.
2. `created_at`, `generated_at`, `fetched_at`, remote publish `updated`도 모두 KST 오프셋 포함 문자열로 저장합니다.
3. UTC `Z` 표기는 QuantMarket 생산 payload 기준으로 사용하지 않습니다.
4. 사용자가 미래 시각으로 파이프라인을 실행해도, 실제 current payload에는 `현재 KST 시각`으로 자동 보정됩니다.

## 적용 범위
다음 출력에 동일하게 적용합니다.
- `market_analysis_summary.json`
- `market_analysis_detail.json`
- `market_analysis_manifest.json`
- `quantservice_market_home.json`
- `quantservice_market_today.json`
- `quantservice_market_page.json`
- `quantservice_market_manifest.json`
- `api_v1_market_analysis_*.json`
- `market_ai_generation_status_latest.json`
- `market_context_latest.json`
- `remote_publish_status_latest.json`

## 현재 구현 상태
반영 코드:
- `D:\QuantMarket\src\quantmarket_market\analytics.py`
- `D:\QuantMarket\src\quantmarket_market\pipeline.py`
- `D:\QuantMarket\src\quantmarket_market\remote_publish.py`

핵심 구현:
- `normalize_asof_kst()`
- `now_kst()`
- `format_kst()`
- remote publish `updated` KST 변환

## 확인 예시
최신 검증 기준:
- `page_asof`: `2026-03-24T16:36:56+09:00`
- `ai_generated_at`: `2026-03-24T16:36:56+09:00`
- `context_fetched_at`: `2026-03-24T16:36:56+09:00`
- `remote_updated_sample`: `2026-03-24T16:37:08+09:00`

## QuantService 참고 사항
1. 기준시각 표시는 KST 문자열을 그대로 사용하면 됩니다.
2. 별도 UTC 변환 없이 payload의 `asof` 값을 우선 신뢰하면 됩니다.
3. 만약 과거 `18:00` 같은 미래 시각이 보인다면, QuantMarket current 문제가 아니라 QuantService 캐시 또는 이전 응답 재사용 가능성을 먼저 점검해 주세요.
