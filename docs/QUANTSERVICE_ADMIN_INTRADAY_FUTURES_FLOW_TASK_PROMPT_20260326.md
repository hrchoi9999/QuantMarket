이번 작업은 `D:\QuantService`에서 진행합니다.

작업 목적:
- QuantMarket이 확장한 장중 `선물/수급` 보조지표를 QS admin 전용 시장 브리핑 Lab에 연결합니다.
- 이 데이터는 공개 페이지용이 아니라 `/admin` 전용 검토 레이어입니다.
- 사용자 최종 승인 전까지 public 페이지와 public API에는 반영하지 않습니다.

중요 원칙:
1. admin 계정만 접근 가능해야 합니다.
2. 공개 `시장 브리핑` 페이지와 절대 섞지 않습니다.
3. `정식 시장 브리핑(종가 기준)`과 `장중 현재 지표(장중 참고)`를 분리해서 보여 줍니다.
4. 이번 확장은 `선물/수급 보조지표 추가`이며, 방향성 참고용이지 투자판단 문구로 과장하면 안 됩니다.

QuantMarket admin intraday payload 위치:
- `D:\QuantMarket\service_platform\web\public_data\handoff\quantservicedmin_market\current`

대상 파일:
- `admin_market_intraday_summary.json`
- `admin_market_intraday_detail.json`
- `admin_market_intraday_manifest.json`

이번에 추가된 핵심 필드:
1. `admin_market_intraday_summary.json`
- `futures[]`
- `flow_signals[]`
- `signal_overlay.futures_overlay`
- `signal_overlay.flow_overlay`

2. `admin_market_intraday_detail.json`
- `futures[]`
- `flow_signals[]`
- `signal_overlay.futures_overlay`
- `signal_overlay.flow_overlay`
- `signal_overlay.futures_source`
- `signal_overlay.flow_source`
- `signal_overlay.futures_available`
- `signal_overlay.flow_available`

필드 의미:
1. `futures[]`
- 장중 선물 현재값
- 현재는 `FUT` 1종
- 포함 항목:
  - `contract_code`
  - `contract_name`
  - `price`
  - `change_pct`
  - `change_value`
  - `volume`
  - `value_million`
  - `is_fallback`

2. `signal_overlay.futures_overlay`
- 선물 해석용 요약
- 포함 항목:
  - `relative_label`
  - `relative_gap_pct`
  - `price`
  - `change_pct`
  - `volume`
- `relative_label` 예시:
  - `현물 대비 선물 우위`
  - `현물 대비 선물 약세`
  - `현물과 유사`

3. `flow_signals[]`
- 장중 수급 방향성 보조지표
- 현재 제공 항목:
  - `PROGRAM_TOTAL_NET`
  - `PROGRAM_NONARB_NET`
  - `FOREIGNER_NET`
  - `INSTITUTION_NET`
- 포함 항목:
  - `signal_code`
  - `signal_name`
  - `metric_value`
  - `metric_unit`
  - `direction_label`
  - `strength_label`
  - `is_fallback`

4. `signal_overlay.flow_overlay`
- 수급 해석용 짧은 메시지 묶음
- 포함 항목:
  - `messages[]`
  - `signal_codes[]`

현재 원천 설명:
- `futures_source = naver:sise_index:FUT`
- `flow_source = naver:programDealTrendTime+investorDealTrendTime`
- 이 값들은 admin tooltip 또는 작은 회색 설명으로만 노출 가능
- 메인 UI에서는 과도하게 강조하지 않습니다.

권장 admin route:
- `/admin/market-briefing-lab/intraday`
또는
- 기존 `/admin/market-briefing-lab` 안의 `장중 현재 지표` 섹션 하단 확장

권장 UI 구성:
1. 기존 상단 상태 요약
- `session_status`
- `direction_label`
- `total_score`
- `summary_line`

2. 기존 지수/환율/breadth 카드
- 그대로 유지

3. 신규 `선물 카드`
- 카드 제목: `선물 참고`
- 표시 항목:
  - `contract_name`
  - `price`
  - `change_pct`
  - `volume`
  - `relative_label`
- 표현 원칙:
  - `현물 대비 선물 우위/약세/유사`를 직관적으로 보여 줌
  - 해석은 짧게, 과장 없이

4. 신규 `수급 카드`
- 카드 제목: `장중 수급 참고`
- 표시 항목:
  - 프로그램 전체 순매수
  - 프로그램 비차익 순매수
  - 외국인 순매수
  - 기관계 순매수
  - 각 항목의 `direction_label`, `strength_label`
- 단위: `억원`
- 음수면 `순매도 우위`, 양수면 `순매수 우위`

5. 신규 `보조 해석 메모`
- `signal_overlay.flow_overlay.messages[]`를 1~2줄로 표시
- 예:
  - `프로그램과 주요 투자주체 흐름은 순매도 우위입니다.`
  - `외국인 순매도가 큰 편이라 장중 부담 요인으로 읽힙니다.`

표시 규칙:
1. `signal_overlay.futures_available == true`
- 선물 카드 정상 표시

2. `signal_overlay.flow_available == true`
- 수급 카드 정상 표시

3. 둘 중 하나만 가능할 때
- 가능한 카드만 노출
- 불가능한 쪽은 숨기거나 `준비 중` 처리

4. 둘 다 unavailable일 때
- 기존 intraday UI는 유지
- futures/flow 섹션만 숨김

문구 원칙:
- `장중 참고`, `보조지표`, `현재 흐름 참고` 같은 표현 사용
- `매수해야 한다`, `방어해야 한다` 같은 자문형 표현 금지
- `정식 시장 브리핑`을 대체하는 것처럼 보이면 안 됨

QA 체크리스트:
- [ ] admin 계정만 접근 가능한가?
- [ ] public 페이지에는 노출되지 않는가?
- [ ] `futures[]`가 정상 렌더링되는가?
- [ ] `flow_signals[]`가 정상 렌더링되는가?
- [ ] `relative_label`이 카드에 자연스럽게 표시되는가?
- [ ] 수급 값 음수/양수에 따라 `순매도 우위/순매수 우위`가 자연스럽게 보이는가?
- [ ] unavailable 상태에서 레이아웃이 깨지지 않는가?
- [ ] `정식 브리핑`과 `장중 참고`가 혼동되지 않는가?
