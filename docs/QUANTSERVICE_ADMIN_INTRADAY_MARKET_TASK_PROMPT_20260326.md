이번 작업은 `D:\QuantService`에서 진행합니다.

작업 목적:
- QuantMarket이 생성하는 장중 현재 지표(`intraday snapshot`)를 QS의 `/admin` 하위 페이지에서만 볼 수 있도록 연결합니다.
- 이 데이터는 공개 시장 브리핑이 아니라 `장중 참고 레이어`입니다.
- 사용자 최종 승인 전까지 공개 페이지에는 반영하지 않습니다.

중요 원칙:
1. admin 전용 페이지에서만 노출합니다.
2. public `시장 브리핑` 페이지와 분리합니다.
3. `정식 시장 브리핑(종가 기준)`과 `장중 현재 지표(장중 참고)`를 구분해서 표시합니다.
4. 이 데이터는 아직 `admin_only_pre_publish` 단계입니다.

QuantMarket admin intraday payload 위치:
- `D:\QuantMarket\service_platform\web\public_data\handoff\quantservice\admin_market\current`

대상 파일:
- `admin_market_intraday_summary.json`
- `admin_market_intraday_detail.json`
- `admin_market_intraday_manifest.json`

파일 의미:
1. `admin_market_intraday_summary.json`
- 장중 현재 방향 요약
- session_status
- direction_label
- total_score
- summary_line
- 주요 지수 현재값

2. `admin_market_intraday_detail.json`
- 장중 현재 상태 detail
- 지수별 현재값 / 등락률 / fallback 여부
- 환율 정보
- breadth 정보
- futures 정보
- flow_signals 정보
- notice / description

3. `admin_market_intraday_manifest.json`
- admin 전용 intraday 파일셋 설명

현재 QuantMarket 운영 기준:
- 지수/환율: live
- breadth: KRX 실패 시 네이버 금융 전체 종목 페이지 집계로 대체
- futures: 네이버 금융 `FUT` 페이지 기반 live 수집
- flow: 네이버 금융 시간별 순매수 iframe 기반 live 수집
- 따라서 최신 정상 상태에서는 `session_status = live` 이면서 `breadth.source = naver:sise_market_sum:*`, `signal_overlay.futures_source = naver:sise_index:FUT`, `signal_overlay.flow_source = naver:programDealTrendTime+investorDealTrendTime` 가 나올 수 있습니다.

권장 admin route:
- `/admin/market-briefing-lab/intraday`
또는
- 기존 `/admin/market-briefing-lab` 내부 하단 섹션

권장 섹션 제목:
- `장중 현재 지표`
부제:
- `정식 시장 브리핑과 별도로 보는 장중 참고 레이어`

표시 규칙:
1. `session_status = live`
- 장중 흐름으로 정상 표시
- direction_label, total_score, summary_line 표시
- breadth source가 `naver:sise_market_sum`이어도 정상 live breadth로 표시 가능
- 다만 tooltip 또는 작은 설명으로 `개발단계 대체 원천` 정도는 표시 가능

2. `session_status = live_indexes_only`
- 지수/환율 live는 정상이나 breadth가 아직 붙지 않은 상태입니다.
- 아래 문구를 함께 표시해 주세요.
  - `지수 중심 참고`
  - `종목 확산 데이터는 아직 연결되지 않아 지수와 환율 중심으로만 해석합니다.`
- breadth 카드가 fallback이면 `준비 중` 또는 `미연결`로 표시해 주세요.

3. `session_status = fallback_prev_close`
- 실시간 판단처럼 보이게 하면 안 됨
- 아래처럼 분명히 표시
  - `전일 기준 참고`
  - `장중 실시간 수집이 아직 붙지 않아 전일 종가 기준 참고 스냅샷입니다.`
- 강세/약세로 과장 표시하지 않습니다.

권장 UI 구성:
1. 상단 상태 바
- session_status badge
- direction_label
- asof
- reference_close_date

2. 주요 지수 카드
- KOSPI
- KOSDAQ
- KOSPI200
- 현재값
- change_pct
- fallback 여부

3. 환율 카드
- USD/KRW
- 현재값
- change_pct
- fallback 여부

4. breadth 카드
- KOSPI breadth
- KOSDAQ breadth
- advancers / decliners / positive_ratio
- source 표시 가능
- fallback 상태면 `미연결` badge와 함께 설명 문구 표시

5. 선물 카드
- FUT 현재가
- change_pct
- 약정수량
- `signal_overlay.futures_overlay.relative_label`
- 예: `현물 대비 선물 우위 / 현물 대비 선물 약세 / 현물과 유사`

6. 수급 카드
- 프로그램 전체 순매수
- 프로그램 비차익 순매수
- 외국인 순매수
- 기관계 순매수
- `direction_label`, `strength_label` 표시
- 단위는 `억원`

7. 설명 영역
- summary_line
- notice

중요 문구 원칙:
- `정식 시장 브리핑`을 대체하는 것처럼 보이면 안 됨
- `장중 참고`, `현재 지표`, `전일 기준 참고`, `지수 중심 참고` 같은 표현을 써야 함
- 실시간 수집 실패 시 약세/강세를 단정하지 말아야 함

접근 제어:
- 관리자 계정만 접근 가능
- 공개 메뉴 미노출
- 비로그인 접근 차단

QA 체크리스트:
- [ ] admin 계정만 접근 가능한가?
- [ ] public 시장 브리핑 페이지에는 노출되지 않는가?
- [ ] session_status가 `live`일 때 breadth 값과 source가 정상 노출되는가?
- [ ] session_status가 `live_indexes_only`일 때 breadth를 정상 live 값처럼 오인하지 않게 표시되는가?
- [ ] session_status가 fallback일 때 `전일 기준 참고`로 표시되는가?
- [ ] 실시간 실패 시 잘못된 강세/약세 메시지가 나오지 않는가?
- [ ] 지수 카드 / 환율 카드 / breadth / futures / flow_signals / notice가 정상 렌더링되는가?
