QS 요청 제출처: QS-Master
권장 담당 쓰레드: QS-Public-Web, QS-QM-Handoff
공개 반영 포함 여부: Yes
Admin only 여부: No
관련 시스템: QuantMarket

작업명:
redbot.co.kr `시장 분석` 메뉴 1차 공개 구현 요청

배경:
- QuantMarket 쪽에서 `시장 분석` 1차용 public payload를 먼저 완료했습니다.
- 이번 요청은 기획 검토 단계가 아니라, 준비된 QuantMarket payload를 사용해 공개 웹 메뉴와 탭형 UI를 실제 구현하는 작업 요청입니다.
- 기존 `시장 브리핑` 메뉴는 유지하고, `시장 분석`은 데이터/차트형 상세 페이지로 분리합니다.

운영 원칙:
- `시장 브리핑`: 해석형 요약
- `시장 분석`: 데이터/차트형 상세
- 공개형 비자문 원칙 유지
- 장중 참고 데이터와 종가 기준 데이터는 시각적으로 분리

QuantMarket upstream 완료 상태:
1. 메뉴/탭 계약 payload 완료
- `quantservice_market_analysis_tabs.json`
- `api_v1_market_analysis_tabs.json`

2. 장중/야간 참고 통합 payload 완료
- `quantservice_market_live_context.json`
- `api_v1_market_analysis_live_context.json`

3. 데이터 해설 payload 완료
- `quantservice_market_data_guide.json`
- `api_v1_market_analysis_data_guide.json`

4. 기존 current/history payload 유지
- `quantservice_market_timeline.json`
- `quantservice_market_timeline_history.json`
- `quantservice_market_state_transition.json`
- `quantservice_market_state_transition_history.json`
- `quantservice_market_asset_strength.json`
- `quantservice_market_asset_strength_history.json`
- `quantservice_market_next_day_preview.json`
- `quantservice_market_next_day_preview_history.json`

공개 base URL:
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current`

history base URL:
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/history`

핵심 current payload 예시:
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current/quantservice_market_analysis_tabs.json`
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current/quantservice_market_live_context.json`
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current/quantservice_market_data_guide.json`

핵심 history payload 예시:
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/history/quantservice_market_timeline_history.json`
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/history/quantservice_market_asset_strength_history.json`
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/history/quantservice_market_state_transition_history.json`
- `https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/history/quantservice_market_next_day_preview_history.json`

1차 탭 구성 요청:
1. `시장 상태`
- 상태점수 timeline 차트
- trend / breadth / risk / defensive_flow 구성요소 차트
- 상태 전이 요약

2. `자산 강도`
- 자산군 상대강도 차트
- 최근 20일 수익률 비교
- 강도 순위 변화

3. `장중/야간 참고`
- `quantservice_market_live_context.json` 사용
- 오늘 장중 흐름
- 퀀트모델 시장 흐름과 장중 흐름의 bridge
- 내일 시장 전망 참고

4. `데이터 해설`
- `quantservice_market_data_guide.json` 사용
- 지표 의미
- official / official_delayed / proxy / fallback 설명
- 공개형 비자문 안내

UI 원칙:
- 한 페이지에 모든 정보를 길게 쌓지 말고 탭으로 분리
- 40~60대 사용자도 보기 쉽게 제목, 범례, 축 라벨, 설명문을 명확히 표시
- 색만으로 상태를 구분하지 말고 텍스트 라벨을 함께 표시
- 현재값 current와 시계열 history가 자연스럽게 이어지게 구성

표현 주의:
- `시장 분석`은 데이터 열람형 공개 정보 페이지로 표현
- 특정 자산 매수/매도 권유처럼 보이는 문구 금지
- `장중/야간 참고`는 참고 레이어임을 분명히 표시
- `퀀트모델 시장 흐름`과 `오늘 장중 흐름`은 다른 축임을 혼동 없이 보여줄 것

완료 기준:
1. redbot.co.kr 상단 메뉴에 `시장 분석` 추가
2. `시장 분석` 페이지에 4개 탭이 구현됨
3. QuantMarket current/history payload 기반 차트가 정상 렌더링됨
4. 모바일/데스크톱 모두 가독성이 확보됨
5. `시장 브리핑`은 유지되며 `시장 분석`과 역할이 분리되어 보임

비고:
- 이번 요청은 QuantMarket upstream 데이터 준비가 완료된 상태에서의 공개 UI 구현 요청입니다.
- 추가 데이터 축이 필요하면 2차에서 DART, KRX 세부 breadth, 미국시장 상세 패널을 확장 예정입니다.
