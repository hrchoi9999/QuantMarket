QS 요청 제출처: QS-Master
권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
공개 반영 포함 여부: Yes
Admin only 여부: No
관련 시스템: QuantMarket

작업 목적:
- `QuantMarket`이 이미 제공을 시작한 `내일 시장 전망 참고` payload를 redbot.co.kr 공개 시장 관련 페이지에 안전하게 연결합니다.
- 이 레이어는 기존 `퀀트모델 시장 흐름`과 `오늘 장중 흐름`을 대체하지 않고, 별도 참고 레이어로만 사용합니다.

배경:
- 사용자에게 다음 거래일 장초반 참고 정보를 제공하기 위해 야간 선물 / 미국장 / 달러 / 유가 / 미국 금리 / 리스크 뉴스를 종합한 별도 레이어가 필요합니다.
- 이 값은 기존 시장브리핑 본문에 섞지 않고, `내일 시장 전망 참고`라는 독립 영역으로 보여 주는 것이 가장 안전합니다.

중요 원칙:
1. `퀀트모델 시장 흐름`을 덮어쓰지 않습니다.
2. `오늘 장중 흐름`을 덮어쓰지 않습니다.
3. `내일 시장 전망 참고`는 별도 카드/블록으로만 표시합니다.
4. 자문형 표현은 금지합니다.
5. 공개 문구는 참고형 / 확률형만 사용합니다.

예시 허용 문구:
- `장초반 부담 가능성`
- `상승 출발 가능성`
- `야간 흐름상 우호적`
- `다음 거래일 참고 정보`

금지 문구:
- `내일 상승 확정`
- `반드시 반등`
- `지금 사야`

현재 QuantMarket 제공 파일:
- `quantservice_market_next_day_preview.json`
- `api_v1_market_analysis_next_day_preview.json`
- `market_next_day_preview_manifest.json`

핵심 필드:
- `active_now`
- `active_window`
- `reference_session`
- `preview_label`
- `preview_score`
- `headline_line`
- `summary_line`
- `supporting_points`
- `risk_points`
- `overnight_assets`
- `market_flow_label`
- `market_flow_score`
- `market_flow_reference_note`
- `content_hash`
- `material_change_flag`
- `display_title`
- `display_subtitle`
- `notice_block`
- `compliance_meta`

권장 페이지 반영 범위:

1. 시장 브리핑
- 위치: 상단 상태 블록 아래 또는 AI 브리핑 아래
- 형태: `내일 시장 전망 참고` 카드 1개
- 노출 조건:
  - `active_now=true` 우선 노출
  - `active_now=false`이면 숨기거나 매우 약한 톤의 예약 영역으로만 처리
- 포함:
  - `display_title`
  - `preview_label`
  - `headline_line`
  - `summary_line`
  - `supporting_points` 2개 내외
  - `risk_points` 1~2개
  - `notice_block.short_notice`

2. 홈
- 위치: 시장브리핑 요약 카드 하단의 작은 보조 라인
- 형태: 1줄 요약
- 노출 조건:
  - `active_now=true`일 때만 기본 노출 권장
- 포함:
  - `preview_label`
  - 또는 `headline_line` 축약본

3. 오늘의 추천
- 위치: 기존 시장 브리지 영역 하단의 짧은 참고 문구
- 형태: 1~2줄
- 포함:
  - `preview_label`
  - `summary_line` 또는 `headline_line` 축약본

4. 이번 주 모델 기준안
- 위치: 시장 배경 참고 블록
- 형태: 작은 보조 카드
- 포함:
  - `preview_label`
  - `summary_line`
  - `supporting_points[0]`

표현 가이드:
- 카드 제목: `내일 시장 전망 참고`
- 설명 문구는 `다음 거래일 장초반 참고 정보입니다.` 수준으로 짧게
- `퀀트모델 시장 흐름`과 같은 시각 강도로 보이지 않게 한 단계 약한 톤 사용
- 색상도 예측/전망처럼 과장하지 않고 중립적으로 유지

fallback 규칙:
1. payload가 없으면 섹션을 숨깁니다.
2. `active_now=false`이면 기본은 숨김 처리하고, 필요하면 내부 정책에 따라 약한 예고형 톤만 사용합니다.
3. `material_change_flag=false`이어도 최신값은 읽을 수 있게 하되, 강조 노출은 줄일 수 있습니다.
4. `notice_block`이 없으면 기본 고지문을 사용합니다.
5. 어떤 경우에도 기존 시장브리핑 UI를 깨뜨리지 않습니다.

공개 반영 단계 권장:
1. 1차: `시장 브리핑` 페이지만 반영
2. 2차: `홈`, `오늘의 추천`
3. 3차: `이번 주 모델 기준안`

QA 체크리스트:
- [ ] `내일 시장 전망 참고`가 기존 시장상태를 덮어쓰지 않는가
- [ ] `퀀트모델 시장 흐름` / `오늘 장중 흐름` / `내일 시장 전망 참고`가 서로 다른 레이어로 이해되는가
- [ ] 자문형 표현 없이 참고형 문구로만 노출되는가
- [ ] payload 미도착 시 기존 공개 페이지가 그대로 유지되는가
- [ ] 모바일에서도 과하게 길거나 복잡하지 않은가

