이번 작업은 `D:\QuantService`에서 진행합니다.

작업 목표:
- 시장분석 페이지 하단의 각 지표 카드 우상단에 `좋음 / 보통 / 나쁨` 상태 배지를 표시합니다.
- 배지 판정은 QuantService에서 다시 계산하지 않고, QuantMarket payload의 `status_badge` 값을 그대로 사용합니다.

운영 source:
- https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current

주요 입력 파일:
- quantservice_market_page.json
- quantservice_market_home.json
- quantservice_market_manifest.json

신규 반영 필드:
- `quantservice_market_page.json.component_cards[].status_badge`
- `quantservice_market_home.json.component_preview[].status_badge`

status_badge 구조:
- `label`: `좋음` | `보통` | `나쁨`
- `tone`: `good` | `neutral` | `bad`
- `reason`: 짧은 판정 설명

예시:
```json
{
  "key": "risk",
  "label": "시장 흔들림",
  "score": -3.0,
  "summary": "최근 변동성과 낙폭이 커져 방어적 해석이 필요합니다.",
  "description": "시장 흔들림은 최근 변동성과 낙폭을 반영한 경계 수준입니다.",
  "status_badge": {
    "label": "나쁨",
    "tone": "bad",
    "reason": "변동성 부담이 큰 편입니다."
  }
}
```

UI 반영 원칙:
1. 각 카드의 우상단에 작은 pill/badge 형태로 표시합니다.
2. 색상만으로 의미를 전달하지 말고 반드시 텍스트 `좋음/보통/나쁨`을 함께 보여 줍니다.
3. tone별 스타일은 아래처럼 권장합니다.
- `good`: 차분한 초록/청록 계열
- `neutral`: 회색/베이지 계열
- `bad`: 차분한 주황/적갈 계열
4. 40~60대 사용자 기준으로 작은 글씨를 피하고, 배지 텍스트는 한눈에 읽히게 합니다.
5. 카드 본문 summary, description과 배지가 충돌하지 않게 상단 여백을 충분히 둡니다.
6. 가능하면 hover/focus/help icon으로 `reason`을 보여 주거나, 모바일에서는 배지 아래 짧은 보조문으로 연결할 수 있습니다.

중요:
- QuantService에서 score를 다시 해석해 badge를 재계산하지 마세요.
- QuantMarket이 제공하는 `status_badge.label/tone/reason`을 source of truth로 사용하세요.
- 카드 제목/설명/notice_block/compliance_meta의 기존 compliance 규칙은 그대로 유지합니다.

페이지별 반영:
- `시장분석` 페이지: `component_cards[].status_badge`를 우상단에 표시
- `홈` 페이지 시장 요약이 component preview를 쓰는 경우: `component_preview[].status_badge`를 동일 규칙으로 사용 가능

QA 체크리스트:
- [ ] `시장 방향 / 시장 건강도 / 시장 흔들림 / 방어자산 선호도` 카드에 배지가 보이는가?
- [ ] 배지 텍스트가 `좋음/보통/나쁨`으로 정확히 표시되는가?
- [ ] `tone`에 맞는 스타일이 적용되는가?
- [ ] score와 별개로 badge를 프론트에서 재계산하지 않는가?
- [ ] 모바일에서도 배지가 줄바꿈 없이 안정적으로 보이는가?
- [ ] 카드 설명문과 badge가 겹치지 않는가?
