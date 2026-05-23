QS 요청 제출처: QS-Master
권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
공개 반영 포함 여부: Yes
Admin only 여부: No
관련 시스템: QuantMarket

작업 목적:
- 공개 시장 관련 페이지 전반에서 `정식 시장상태` 계열 표현을 `퀀트모델 시장 흐름` 중심 표현으로 정리합니다.
- 사용자가 이 값을 `오늘 오름/내림`이 아니라 `퀀트모델이 계산한 흐름 판단`으로 이해할 수 있게 합니다.

배경:
- 현재 공개 페이지에서는 `정식 시장상태`, `정식 시장상태(전일 종가 기준)` 같은 표현이 남아 있어 사용자에게 의미가 직관적으로 전달되지 않습니다.
- 이 값은 단순 전일 상승/하락이 아니라, 최근 추세 / breadth / 변동성 / 방어자산 선호를 반영한 퀀트모델 기준 흐름입니다.
- 따라서 공개 표현도 그 뜻에 맞게 바꾸는 것이 필요합니다.

QuantMarket 반영 완료 사항:
- public payload에서 `state_intraday_bridge.medium_term_label`을 `퀀트모델 시장 흐름`으로 변경했습니다.
- `state_intraday_bridge.medium_term_description` 추가
  - `최근 추세와 시장 내부 신호를 반영한 퀀트모델 기준 흐름입니다.`
- `state_intraday_bridge.intraday_label`을 `오늘 장중 흐름`으로 정리했습니다.
- `state_intraday_bridge.intraday_description` 추가
  - `당일 지수, breadth, 선물, 수급을 반영한 장중 흐름 참고값입니다.`
- `bridge_text`, `basis_lines` 내부 표현도 `정식 시장상태` -> `퀀트모델 시장 흐름`으로 변경했습니다.

사용 파일:
- `quantservice_market_page.json`
- `quantservice_market_home.json`
- `quantservice_market_today.json`
- `api_v1_market_analysis_page.json`
- `api_v1_market_analysis_home.json`
- `api_v1_market_analysis_today_bridge.json`

주요 사용 필드:
- `state_intraday_bridge.medium_term_label`
- `state_intraday_bridge.medium_term_description`
- `state_intraday_bridge.medium_term_state_label`
- `state_intraday_bridge.intraday_label`
- `state_intraday_bridge.intraday_description`
- `state_intraday_bridge.intraday_state_label`
- `state_intraday_bridge.display_label`
- `state_intraday_bridge.bridge_text`
- `state_intraday_bridge.basis_lines[]`

반영 대상 페이지:
1. 홈
2. 시장 브리핑
3. 오늘의 추천
4. 이번 주 모델 기준안
5. 그 외 시장 관련 용어가 직접 노출되는 페이지/섹션

반영 원칙:
1. `정식 시장상태`라는 표현은 공개 UI에서 사용하지 않습니다.
2. `정식 시장상태(전일 종가 기준)`라는 표현도 공개 UI에서 제거합니다.
3. 첫 번째 상태 라벨/막대는 `퀀트모델 시장 흐름`으로 표기합니다.
4. 두 번째 상태 라벨/막대는 `오늘 장중 흐름`으로 표기합니다.
5. 필요하면 작은 도움말 문구로 `medium_term_description`, `intraday_description`을 사용합니다.

권장 UI 문구:
- `퀀트모델 시장 흐름: 상승`
- `오늘 장중 흐름: 강한 약세`
- `상승 유지, 단기 조정 동반`
- `퀀트모델 시장 흐름은 상승이지만, 오늘 장중에는 단기 조정 흐름이 나타납니다.`

페이지별 반영 가이드:

1. 홈
- 시장 관련 요약 카드에서 첫 번째 라벨을 `퀀트모델 시장 흐름`으로 변경
- 두 번째 라벨은 `오늘 장중 흐름` 사용
- 설명 문구가 있으면 `최근 추세와 시장 내부 신호를 반영한 퀀트모델 기준 흐름입니다.` 정도로 짧게 사용 가능

2. 시장 브리핑
- 상단 2단 막대 제목을 아래처럼 통일
  - 첫 번째: `퀀트모델 시장 흐름`
  - 두 번째: `오늘 장중 흐름`
- `bridge_text`, `basis_lines`는 payload 값을 그대로 사용
- 기존 정식/기준/전일 종가 기준 등 혼합 표현이 남아 있으면 제거

3. 오늘의 추천
- 시장 브리지 영역에서 첫 줄은 `퀀트모델 시장 흐름`
- 둘째 줄은 `오늘 장중 흐름`
- 짧은 설명은 `display_label` 또는 `bridge_text` 활용

4. 이번 주 모델 기준안
- 시장 배경/시장 상태 관련 라벨이 있으면 `퀀트모델 시장 흐름`으로 통일
- 오늘 흐름과 같이 보여 줄 경우 `오늘 장중 흐름` 사용
- `모델 기준안`과 연결되는 페이지인 만큼 가장 우선적으로 용어를 정리하는 것이 좋습니다.

5. 기타 시장 관련 페이지
- 시장 상태, 시장 흐름, 모델 브리핑, 배경 해석 등 관련 섹션에 `정식 시장상태` 문구가 남아 있으면 모두 제거
- 동일 개념은 동일 용어로 통일

금지 표현:
- `정식 시장상태`
- `정식 시장상태(전일 종가 기준)`
- 동일 의미의 혼합 표현을 페이지마다 다르게 쓰는 것

권장 설명 문구:
- `퀀트모델 시장 흐름은 최근 추세와 시장 내부 신호를 반영한 모델 기준 흐름입니다.`
- `오늘 장중 흐름은 당일 지수와 수급 흐름을 반영한 장중 참고값입니다.`

QA 체크리스트:
- [ ] 홈에서 `정식 시장상태` 표현이 제거되었는가
- [ ] 시장 브리핑 페이지 2단 막대 제목이 `퀀트모델 시장 흐름` / `오늘 장중 흐름`으로 통일되었는가
- [ ] 오늘의 추천 페이지 시장 브리지도 같은 용어를 쓰는가
- [ ] 이번 주 모델 기준안 페이지에서도 같은 용어를 쓰는가
- [ ] 공개 페이지 어디에도 `정식 시장상태` 문구가 남아 있지 않은가
- [ ] 설명 문구가 사용자를 더 헷갈리게 하지 않고, 모델 기준 흐름과 장중 흐름의 차이를 자연스럽게 설명하는가
