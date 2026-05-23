# QUANTMARKET_VIDEO_PAYLOAD_PREP_NOTE_20260327.md

## 목적

`D:\QuantYoutube`가 `D:\QuantMarket` 시장 브리핑 산출물을 안정적으로 소비할 수 있도록,
영상용 public payload 계층의 구현 가능 범위와 우선순위를 정리한다.

## 전제 정리

- QuantMarket은 upstream producer
- QuantYoutube는 downstream consumer
- QuantYoutube는 DB나 admin payload를 직접 읽지 않는다
- 영상도 공개형 참고 정보 원칙을 유지한다
- 장중 참고 정보는 퀀트모델 시장 흐름을 덮어쓰지 않는다
- current + snapshot 구조를 기본으로 한다

## 1. 구현 가능 범위

현재 QuantMarket 구조를 기준으로 아래는 구현 가능하다.

### A. hourly_intraday video payload
가능

근거:
- 장중 intraday snapshot이 이미 15분 단위로 수집되고 있음
- 공개 시장브리핑 payload에 장중 브리지 정보가 이미 연결되어 있음
- 지수 / 환율 / breadth / 선물 / 수급이 일정 수준 구조화되어 있음

안정 보장 가능 범위:
- `market`
- `asof`
- `content_mode=hourly_intraday`
- `reference_date`
- `freshness`
- `source_type`
- `notice_block`
- `compliance_meta`
- `state_label`
- `state_score`
- `summary_line`
- `reference_note`
- `positive_signals`
- `warning_signals`
- `display_metrics`
- `session_status`
- `direction_label`
- `intraday_summary_line`
- `indexes`
- `fx`
- `intraday_notice`
- `title_candidates`
- `hook_line`
- `caption_lines`
- `narration_lines`
- `tags`
- `content_hash`
- `material_change_flag`

주의:
- 이 payload는 `공개형 시장 브리핑 + 장중 참고` 기반이어야 하며,
  admin 전용 원시 signal을 그대로 노출하지 않는 래핑이 필요함

### B. market_close video payload
가능

근거:
- 현재 public market briefing current가 이미 close-briefing 중심 구조를 갖고 있음
- 상태 라벨, 점수, component, 자산강도, 모델 백그라운드가 정리되어 있음

안정 보장 가능 범위:
- 공통 필드 전체
- 브리핑 핵심 필드 전체
- 자산/모델 연결 필드 전체
- 영상 메타 보조 필드 대부분
- `content_hash`
- `material_change_flag`

### C. weekly_model_bridge video payload
가능, 다만 1차는 lightweight bridge 형태 권장

근거:
- `model_background`, `asset_strength`, `state_transition` 조합으로 주간용 bridge payload를 만들 수 있음
- 다만 주간 기준안과 완전 결합된 payload는 향후 QuantYoutube와 사용 시나리오를 맞춰가며 확장하는 편이 안전함

1차 권장 범위:
- `weekly_model_bridge`
- `briefing_tone`
- `model_background_points`
- `top_assets`
- `bottom_assets`
- `weekly_title_candidates`
- `weekly_caption_lines`
- `content_hash`
- `material_change_flag`

## 2. 우선순위 A 범위

우선순위 A는 아래 3개로 정리하는 것이 가장 현실적이다.

1. `market_video_hourly_intraday.json`
2. `market_video_close_briefing.json`
3. `market_video_manifest.json`

이 단계에서 함께 포함 가능한 것:
- current + snapshot 구조
- manifest의 lineage / freshness / visibility
- content_hash
- material_change_flag
- title/hook/caption/narration 보조 필드의 기본형

우선순위 A에서 보장 수준:
- QuantYoutube가 DB 조회 없이 JSON만 읽어 storyboard -> caption -> narration 설계 가능
- 장중 참고와 퀀트모델 시장 흐름을 명확히 분리 가능
- 동일 내용 반복 업로드를 줄이기 위한 fingerprint 제공 가능

## 3. 예상 산출 파일명 / 저장 위치

### current 경로 권장

- `D:\QuantMarket\service_platform\web\public_dataideo\current\market_video_hourly_intraday.json`
- `D:\QuantMarket\service_platform\web\public_dataideo\current\market_video_close_briefing.json`
- `D:\QuantMarket\service_platform\web\public_dataideo\current\market_video_weekly_model_bridge.json`
- `D:\QuantMarket\service_platform\web\public_dataideo\current\market_video_manifest.json`

### QuantYoutube handoff current 경로 권장

- `D:\QuantMarket\service_platform\web\public_data\handoff\quantyoutube\current\market_video_hourly_intraday.json`
- `D:\QuantMarket\service_platform\web\public_data\handoff\quantyoutube\current\market_video_close_briefing.json`
- `D:\QuantMarket\service_platform\web\public_data\handoff\quantyoutube\current\market_video_weekly_model_bridge.json`
- `D:\QuantMarket\service_platform\web\public_data\handoff\quantyoutube\current\market_video_manifest.json`

### snapshot 경로 권장

- `D:\QuantMarket\service_platform\web\public_dataideo\snapshot\YYYY-MM-DD\market_video_hourly_intraday_YYYYMMDDTHHMMSS.json`
- `D:\QuantMarket\service_platform\web\public_dataideo\snapshot\YYYY-MM-DD\market_video_close_briefing_YYYYMMDDTHHMMSS.json`
- `D:\QuantMarket\service_platform\web\public_dataideo\snapshot\YYYY-MM-DD\market_video_weekly_model_bridge_YYYYMMDDTHHMMSS.json`
- `D:\QuantMarket\service_platform\web\public_dataideo\snapshot\YYYY-MM-DD\market_video_manifest_YYYYMMDDTHHMMSS.json`

## content hash / material change 검토

가능

권장 규칙:
- `content_hash`: 핵심 사용자 노출 필드만 normalize 후 sha256
- `material_change_flag`: 직전 current 대비 아래 변화가 있으면 true
  - state_label 변화
  - intraday direction_label 변화
  - display_label 변화
  - top_assets / bottom_assets 변화
  - summary_line 또는 hook_line 의미 변화
  - state_score 절대 변화폭이 threshold 초과

1차 threshold 예시:
- `state_score` 변화폭 >= 0.25
- `intraday total_score` 변화폭 >= 0.35
- `top_assets[0]` 또는 `bottom_assets[0]` 변화
- `display_label` 변화

## manifest에 담을 항목

가능

권장 manifest 필드:
- `generated_at`
- `asof`
- `reference_date`
- `freshness`
- `files`
- `lineage`
- `visibility`
- `source_groups`
- `content_modes`
- `change_detection_rule`
- `notice_block`
- `compliance_meta`

## QuantYoutube에 먼저 회신할 3줄 요약

1. 구현 가능 범위
- `hourly_intraday`, `market_close`, `weekly_model_bridge` 모두 구현 가능하며,
  우선은 `hourly_intraday + market_close + manifest`를 안정형 public video payload로 먼저 제공하는 것이 적절합니다.

2. 우선순위 A 범위
- 우선순위 A는 `market_video_hourly_intraday.json`, `market_video_close_briefing.json`, `market_video_manifest.json` 3종과
  `current + snapshot`, `content_hash`, `material_change_flag`, `freshness/lineage/visibility`까지 포함하는 범위로 정리할 수 있습니다.

3. 예상 산출 파일명 / 저장 위치
- current:
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantyoutube\current\market_video_hourly_intraday.json`
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantyoutube\current\market_video_close_briefing.json`
  - `D:\QuantMarket\service_platform\web\public_data\handoff\quantyoutube\current\market_video_manifest.json`
- snapshot:
  - `D:\QuantMarket\service_platform\web\public_dataideo\snapshot\YYYY-MM-DD\...`
