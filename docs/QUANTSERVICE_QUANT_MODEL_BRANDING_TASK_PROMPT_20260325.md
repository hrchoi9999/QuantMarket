이번 작업은 `D:\QuantService`에서 진행합니다.

작업 배경:
- QuantMarket이 시장 브리핑 handoff의 표현층을 수정해, redbot.co.kr이 단순 시장분석 페이지가 아니라 `퀀트투자 모델 브리핑 서비스`로 읽히도록 표시용 문구를 강화했습니다.
- 이번 작업의 목적은 QuantService UI가 새 표현 체계를 그대로 반영하도록 맞추는 것입니다.

운영 source:
- https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current

주요 입력 파일:
- quantservice_market_home.json
- quantservice_market_today.json
- quantservice_market_page.json
- quantservice_market_manifest.json

핵심 원칙:
1. QuantMarket은 생산자이고, QuantService는 표시 계층입니다.
2. 새 표시용 문구는 payload 값을 우선 사용합니다.
3. 기존 `시장분석`, `오늘의 추천`, `대응 가이드`, `추천 대응 톤` 같은 표현은 사용자 화면에서 제거합니다.
4. 페이지가 `퀀트투자 모델 해석에 필요한 시장 브리핑`으로 읽히도록 정리합니다.

반드시 반영할 메뉴/표현:
- `시장분석` -> `시장 브리핑`
- `오늘의 추천` -> `이번 주 모델 기준안`
- `성과` -> `성과 설명`

QuantMarket에서 새로 제공하는 주요 표시 필드:
- `page_meta.service_definition`
- `page_meta.page_title`
- `page_meta.page_subtitle`
- `service_definition`
- `signal_lists.positive_label`
- `signal_lists.warning_label`
- `signal_lists.observation_title`
- `signal_lists.observation_description`
- `usage_guide_card`
- `today_bridge.tone_label`
- `component_cards[].label`
- `ai_briefs.title`
- `ai_briefs.providers[].theme_label`
- `quantservice_market_manifest.json.branding_copy`

현재 내려가는 권장 문구:
- 서비스 정의: `다양한 시장 데이터 기반의 상황별 퀀트투자 모델 정보 서비스`
- 페이지 제목: `시장 브리핑`
- 페이지 부제: `퀀트투자 모델 해석에 필요한 시장 상태를 같은 기준으로 정리합니다.`
- 긍정 신호 라벨: `모델에 우호적인 신호`
- 주의 신호 라벨: `모델 해석상 주의할 신호`
- 관찰 박스 제목: `이번 주 모델 해석 포인트`
- 브리지 톤 라벨: `브리핑 톤`
- AI 섹션 제목: `퀀트투자 모델 브리핑 참고`
- AI 카드 제목:
  - ChatGPT -> `모델 해석 참고`
  - Gemini -> `시장 분위기 참고`

지표 카드 라벨 변경:
- `시장 방향` -> `시장 추세 점검`
- `시장 건강도` -> `시장 확산 점검`
- `시장 흔들림` -> `시장 변동성 점검`
- `방어자산 선호도` -> `방어자산 선호 점검`

시장 브리핑 페이지 반영 지시:
1. 상단 제목/부제/서비스 정의는 `page_meta`와 `service_definition`을 우선 사용합니다.
2. 기존 `시장분석 내용` 제목은 `ai_briefs.title`로 교체합니다.
3. AI 카드 제목은 `theme_label`을 그대로 사용합니다.
4. 신호 섹션 제목은 아래처럼 교체합니다.
- `긍정 신호` -> `signal_lists.positive_label`
- `주의 신호` -> `signal_lists.warning_label`
5. 기존 `대응 가이드` 또는 유사 제목은 제거하고, 아래 구조로 교체합니다.
- 제목: `signal_lists.observation_title`
- 설명: `signal_lists.observation_description`
- 본문: `signal_lists.observation_note`
6. 페이지 중간 또는 하단에 `usage_guide_card`를 별도 정보 카드로 추가합니다.
- 제목: `이 시장 브리핑은 어디에 쓰이나요?`
- 본문 2줄 표시
- 링크 버튼:
  - `이번 주 모델 기준안 보기`
  - `변경내역 보기`

홈 페이지 반영 지시:
1. 홈 시장요약 블록은 `hero.title`, `hero.subtitle`, `hero.service_definition`을 우선 사용합니다.
2. `시장분석` 진입 버튼/링크는 `시장 브리핑`으로 교체합니다.
3. 이 블록이 `퀀트투자 모델 참고 정보`라는 인상이 보이도록 `service_definition` 또는 `reference_note`를 함께 표시합니다.

이번 주 모델 기준안 페이지 반영 지시:
1. 기존 `오늘의 추천` 표현은 제거합니다.
2. 시장 브리지 영역에서는 `market_bridge.tone_label`을 `브리핑 톤` 라벨로 표시합니다.
3. `추천 대응 톤`, `대응 전략`, `추천 전략` 같은 문구는 사용하지 않습니다.
4. `reference_text`는 `현재 모델 기준안을 읽을 때 함께 볼 시장 브리핑 참고 문장`으로 연결합니다.

표현 금지:
- 시장분석
- 오늘의 추천
- 대응 가이드
- 추천 대응 톤
- 추천 전략
- 매수 기회
- 지금 대응 전략
- 시장 추천

표현 권장:
- 시장 브리핑
- 퀀트투자 모델 브리핑
- 모델 해석 참고
- 시장 분위기 참고
- 이번 주 모델 해석 포인트
- 다양한 시장 데이터 기반의 상황별 퀀트투자 모델 정보 서비스
- 멀티애셋 데이터 기반 퀀트투자 모델
- 모델 포트폴리오 해석 참고 정보

QA 체크리스트:
- [ ] 상단 메뉴가 `시장 브리핑 / 이번 주 모델 기준안 / 성과 설명` 체계로 보이는가?
- [ ] 페이지 제목이 `시장 브리핑`으로 보이는가?
- [ ] 서비스 정의 문구가 화면에 노출되는가?
- [ ] `대응`, `추천` 계열 문구가 주요 UI에서 제거되었는가?
- [ ] 4개 지표 카드가 `점검`형 이름으로 표시되는가?
- [ ] 신호 섹션이 `모델에 우호적인 신호 / 모델 해석상 주의할 신호`로 표시되는가?
- [ ] `이번 주 모델 해석 포인트` 박스가 보이는가?
- [ ] `이 시장 브리핑은 어디에 쓰이나요?` 연결 카드가 보이는가?
- [ ] AI 제목이 `퀀트투자 모델 브리핑 참고`로 보이는가?
- [ ] Gemini 카드 제목이 `시장 분위기 참고`, ChatGPT 카드 제목이 `모델 해석 참고`로 보이는가?
