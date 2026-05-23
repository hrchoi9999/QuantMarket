# QUANTMARKET_NEXT_DAY_PREVIEW_DESIGN_NOTE_20260401.md

## 목적

`QuantMarket`에 `내일 시장 전망 참고` 레이어를 별도로 추가한다.

이 레이어는 기존 공개 시장브리핑을 대체하지 않는다.

- `퀀트모델 시장 흐름`
  - 장마감 후 확정 데이터 기준
  - 기존 구조 유지
- `오늘 장중 흐름`
  - 당일 현물/환율/수급/선물 기준
  - 기존 intraday 구조 유지
- `내일 시장 전망 참고`
  - 야간 선물 / 미국장 / 달러 / 유가 / 미국 금리 / 주요 뉴스 기반
  - 다음 거래일 장초반 참고 정보

## 핵심 원칙

1. 기존 `퀀트모델 시장 흐름`을 덮어쓰지 않는다.
2. 장중 레이어와 야간 전망 레이어를 분리한다.
3. 전망은 확률형 / 참고형 문구만 사용한다.
4. 자문형 문구를 금지한다.
5. `18:00 ~ 익일 08:30` 운영 시간을 별도로 둔다.

## 사용자 노출 개념

권장 라벨:

- `퀀트모델 시장 흐름`
- `오늘 장중 흐름`
- `내일 시장 전망 참고`

권장 공개 문구 예시:

- `야간 선물은 약세 쪽입니다.`
- `미국 위험자산 흐름은 부담 요인입니다.`
- `달러 강세가 이어져 내일 장초반 경계가 필요합니다.`
- `다만 퀀트모델 시장 흐름 자체를 바꾸는 수준으로 해석하진 않습니다.`

금지 문구 예시:

- `내일 상승 확정`
- `반드시 반등`
- `지금 사야`
- `확실한 기회`

## 우선 수집 대상

### 최소 야간 데이터

1. `KOSPI200` 야간선물 또는 대체 가능한 한국 관련 선물
2. `S&P500` 선물
3. `NASDAQ100` 선물
4. `USD/KRW` 야간 흐름 가능 시 포함
5. `WTI` 유가
6. `미국 10년물 금리`
7. 주요 리스크 뉴스 헤드라인

### 수집 우선순위

1. 선물 3종
2. 달러 / 유가
3. 미국 금리
4. 뉴스

## 계산 지표

지표는 단순하게 4개로 고정한다.

1. `overnight_futures_bias`
2. `global_risk_bias`
3. `overnight_fx_bias`
4. `next_day_preview_score`

### 지표 의미

- `overnight_futures_bias`
  - 한국 관련 선물과 미국 선물 방향을 종합한 야간 방향성
- `global_risk_bias`
  - 미국 선물 / 유가 / 미국 금리 / 리스크 뉴스 기반 위험선호/회피 분위기
- `overnight_fx_bias`
  - 달러 강약과 원화 부담 정도
- `next_day_preview_score`
  - 위 3개 축을 합친 참고용 점수

## 신규 테이블 설계

### 1. market_overnight_asset_snapshot

목적:
- 야간 자산별 원천 snapshot 저장

권장 컬럼:

- `market`
- `asof`
- `session_date`
- `asset_code`
- `asset_name`
- `asset_group`
- `price`
- `change_value`
- `change_pct`
- `open`
- `high`
- `low`
- `prev_close`
- `source`
- `is_fallback`
- `created_at`

예상 asset_code:

- `KOSPI200_FUT_OVERNIGHT`
- `SP500_FUT`
- `NASDAQ100_FUT`
- `USDKRW`
- `WTI`
- `US10Y`

### 2. market_overnight_news_context

목적:
- 야간 전망용 뉴스 문맥 저장

권장 컬럼:

- `market`
- `asof`
- `session_date`
- `headline_count`
- `risk_headline_count`
- `caution_bias`
- `context_json`
- `created_at`

### 3. market_next_day_preview_state

목적:
- 다음 거래일 전망 참고용 합성 상태 저장

권장 컬럼:

- `market`
- `asof`
- `reference_session`
- `preview_label`
- `preview_score`
- `overnight_futures_bias`
- `global_risk_bias`
- `overnight_fx_bias`
- `headline_line`
- `summary_line`
- `supporting_points_json`
- `risk_points_json`
- `overnight_assets_json`
- `source`
- `created_at`

## payload 설계

### current 파일

- `market_next_day_preview.json`
- `quantservice_market_next_day_preview.json`
- `api_v1_market_analysis_next_day_preview.json`
- `market_next_day_preview_manifest.json`

### 예상 경로

- snapshot current
  - `D:\QuantMarket\service_platform\web\public_data\current\market_next_day_preview.json`
- QuantService handoff current
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current\quantservice_market_next_day_preview.json`
- API-ready current
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\current\api_v1_market_analysis_next_day_preview.json`

### snapshot history 권장 경로

- `D:\QuantMarket\service_platform\web\public_data\next_day_preview\snapshot\YYYY-MM-DD\market_next_day_preview_YYYYMMDDTHHMMSS.json`

## payload 최소 필드

### 공통

- `market`
- `asof`
- `reference_session`
- `content_mode`
- `source_type`
- `freshness`
- `notice_block`
- `compliance_meta`

### 핵심 브리핑

- `preview_label`
- `preview_score`
- `headline_line`
- `summary_line`
- `supporting_points`
- `risk_points`
- `overnight_assets`

### 연결 필드

- `market_flow_label`
- `market_flow_score`
- `market_flow_reference_note`

### 메타 보조 필드

- `title_candidates`
- `hook_line`
- `caption_lines`
- `narration_lines`
- `tags`
- `content_hash`
- `material_change_flag`

## 권장 payload 예시

```json
{
  "market": "KR",
  "asof": "2026-04-01T22:00:00+09:00",
  "reference_session": "2026-04-02",
  "content_mode": "next_day_preview",
  "source_type": "public_next_day_preview",
  "market_flow_label": "상승",
  "market_flow_score": 1.08,
  "preview_label": "장초반 부담 가능성",
  "preview_score": -0.72,
  "headline_line": "야간 선물과 미국 위험자산 흐름은 내일 장초반 부담 요인으로 읽힙니다.",
  "summary_line": "다만 현재 퀀트모델 시장 흐름 자체를 바꾸는 수준으로 해석하진 않습니다.",
  "supporting_points": [
    "나스닥 선물이 약세입니다.",
    "달러 강세가 이어지고 있습니다."
  ],
  "risk_points": [
    "유가 상승이 부담 요인입니다."
  ],
  "overnight_assets": [
    {"asset_code": "NASDAQ100_FUT", "change_pct": -0.8},
    {"asset_code": "USDKRW", "change_pct": 0.3}
  ],
  "notice_block": {
    "short_notice": "다음 거래일 참고 정보입니다.",
    "long_notice": "이 정보는 공개형 참고 브리핑이며 개별 투자자문이 아닙니다."
  }
}
```

## manifest 설계

파일:

- `market_next_day_preview_manifest.json`

권장 필드:

- `market`
- `asof`
- `generated_at`
- `reference_session`
- `content_modes`
- `files`
- `freshness`
- `lineage`
- `visibility`
- `source_groups`
- `change_detection_rule`
- `notice_block`
- `compliance_meta`

### visibility 예시

- `public_next_day_preview`
- `public_market_briefing`
- `admin_only_intraday`

## 운영 시간 권장

### 수집 / 생성

- `18:00`
- `19:00`
- `20:00`
- `22:00`
- `23:00`
- `익일 06:00`
- `익일 07:00`
- `익일 08:00`

### 기준

- 장중에는 기본적으로 노출하지 않음
- `08:30` 이후에는 `오늘 장중 흐름`이 우선

## material change 규칙

권장 기준:

- `preview_label` 변경
- `headline_line` 변경
- `next_day_preview_score` 변화폭 `>= 0.35`
- 선물 방향 부호 변경
- `supporting_points[0]` 또는 `risk_points[0]` 변경

## 구현 우선순위

### 우선순위 A

1. 신규 테이블 3종
2. 원천 수집기
3. `market_next_day_preview.json`
4. `quantservice_market_next_day_preview.json`
5. `market_next_day_preview_manifest.json`
6. `content_hash / material_change_flag`

### 우선순위 B

1. `api_v1_market_analysis_next_day_preview.json`
2. title/hook/caption/narration 보조 필드
3. QY downstream용 video bridge 호환 필드

## QS-Master 반영 방향

공개 웹 반영 시 아래 위치를 권장한다.

1. `시장 브리핑`
   - 상단 또는 AI 브리핑 아래에 작은 `내일 시장 전망 참고` 카드
2. `홈`
   - 작은 요약 라인 1개
3. `이번 주 모델 기준안`
   - 내일 장초반 참고 문구 연결 가능

단, 기존 `퀀트모델 시장 흐름`과 혼합하지 않고 별도 레이어로 유지한다.

