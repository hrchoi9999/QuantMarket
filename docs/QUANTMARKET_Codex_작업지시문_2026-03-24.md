# QUANTMARKET Codex 작업지시문 (2026-03-24)

## 0. 목적

이 문서는 **QuantMarket 시스템**에 대한 Codex 작업지시문입니다.

QuantMarket의 역할은 아래로 한정합니다.

- 국내외 시장자료를 수집·정리·분석한다.
- 시장상태를 설명하는 **단방향 브리핑 정보**를 생성한다.
- 시장 위험도, 유동성, 추세, 변동성, 매크로 환경 등을 **공개형 기준**으로 요약한다.
- Quant 및 QuantService가 참고할 수 있는 **시장 컨텍스트 데이터**를 생산한다.

QuantMarket은 **개별 종목 추천 시스템이 아니다.**  
QuantMarket은 **개인 맞춤 투자판단 시스템이 아니다.**  
QuantMarket은 **매수/매도 자문 시스템이 아니다.**

따라서 QuantMarket이 만들어내는 모든 데이터, API, UI 문구, 알림 문구는 다음 원칙을 따라야 한다.

- 불특정 다수에게 동일하게 제공되는 공개형 정보여야 한다.
- 시장상태 설명 중심이어야 한다.
- 특정 사용자의 자산상황, 성향, 보유종목, 연령, 손실허용도에 따라 결과가 달라지면 안 된다.
- 종목·비중·타이밍 권유형 문구로 보이면 안 된다.
- 투자판단은 이용자 책임이라는 구조가 유지되어야 한다.

---

## 1. QuantMarket의 시스템 정의

### 1-1. 시스템 성격

QuantMarket은 아래 성격으로만 정의한다.

- 시장 데이터 분석 시스템
- 시장상태 브리핑 엔진
- 공개형 리스크 상태 지표 생성 시스템
- 주간/일간 시장 컨텍스트 요약 시스템

### 1-2. 하지 말아야 할 시스템 정의

아래와 같은 방향으로 해석될 수 있는 기능/표현/데이터 구조는 금지한다.

- 오늘 사야 할 종목 추천
- 지금 팔아야 할 종목 추천
- 이번 주 유망주 추천
- 지금이 공격적으로 들어갈 타이밍이라는 직접 권유
- 사용자 맞춤 시장 대응전략 제시
- 보유종목 기준 교체 제안
- 투자성향별 개별 자산배분 제안
- 개인별 손실허용도 기반 대응안 자동 산출

---

## 2. QuantMarket의 허용 기능

QuantMarket에서 허용되는 기능은 아래로 제한한다.

### 2-1. 시장상태 요약

예시:

- 국내 주식시장 상태: 위험중립 / 위험확대 / 방어우위 / 추세회복
- 미국 시장 상태: 추세강세 / 과열경계 / 변동성 확대
- 금리/달러/원자재/변동성 상태 요약
- 전반적 위험온도 표시
- 시장 내부지표 breadth, volatility, trend, macro regime 요약

### 2-2. 공개형 지표 생성

예시:

- market_risk_level
- trend_regime
- volatility_regime
- liquidity_regime
- macro_pressure_score
- sentiment_band
- overseas_market_signal
- domestic_market_signal
- risk_temperature

### 2-3. 브리핑 문장 생성

예시:

- “이번 주 국내 시장은 단기 반등 구간이지만 변동성이 여전히 높은 상태입니다.”
- “대형주 중심의 안정성이 상대적으로 우세한 시장 환경입니다.”
- “과열 신호보다 관망 신호가 우세합니다.”
- “방향성은 개선되고 있으나 추세 확정으로 보기는 이릅니다.”

### 2-4. 공개형 리포트 데이터 제공

예시:

- 주간 시장 요약 데이터
- 지표별 변화 이력
- 시장상태 변동 로그
- 주요 거시 이벤트 캘린더 참고 정보
- 모델 판단에 영향을 준 시장지표 설명

---

## 3. QuantMarket의 금지 기능

아래 기능은 P0 금지 대상으로 본다.

### 3-1. 종목 직접 추천 금지

금지 예시:

- “이번 주 추천 종목 TOP 5”
- “지금 유망한 ETF”
- “이번 주 반드시 담아야 할 종목”
- “방어형 투자자에게 적합한 국내 ETF 추천”

### 3-2. 타이밍 직접 권유 금지

금지 예시:

- “지금은 적극 매수 구간입니다.”
- “이번 주는 공격적으로 비중을 확대하세요.”
- “현 시점에서 반드시 매도해야 합니다.”
- “추격매수 적기입니다.”

### 3-3. 사용자별 대응안 생성 금지

금지 예시:

- 보유종목 입력 후 대응전략 생성
- 연령/자산/목표수익 입력 후 시장대응안 생성
- 손실허용도 입력 후 개인별 투자행동 추천
- “회원님에게 맞는 이번 주 전략” 자동 생성

### 3-4. 챗봇 투자판단 응답 금지

QuantMarket 관련 챗봇/LLM 기능이 아래에 답하면 안 된다.

- “지금 코스피 들어가도 되나요?”
- “이번 주 미국 ETF 비중 늘릴까요?”
- “제 상황에서는 공격적으로 가도 되나요?”
- “이 종목 지금 사도 되나요?”

응답은 아래처럼 제한한다.

- “QuantMarket은 공개형 시장 브리핑 정보를 제공하며, 개별 투자판단에 대한 답변은 제공하지 않습니다.”
- “시장지표 해석 방법과 서비스 이용 방법은 안내할 수 있지만, 개인별 투자판단은 안내하지 않습니다.”

---

## 4. QuantMarket 문구 원칙

QuantMarket은 문구가 매우 중요하다.

### 4-1. 허용 문구 방향

허용 방향:

- 시장상태
- 위험수준
- 추세 여부
- 변동성 환경
- 관찰 포인트
- 참고 정보
- 브리핑
- 공개 기준
- 해석 참고
- 지표 설명

예시:

- “이번 주 시장 브리핑”
- “시장 상태 요약”
- “위험온도”
- “관찰 포인트”
- “모델이 참고하는 시장 환경”
- “시장 해석 참고 정보”

### 4-2. 금지 문구 방향

금지 방향:

- 추천
- 대응전략 추천
- 이번 주 사야 할 자산
- 투자자별 전략
- 개인 맞춤 전략
- 지금 들어가야 할 시장
- AI 추천
- 매수 유망
- 고수익 기대
- 유리한 진입 구간

금지 예시:

- “ChatGPT가 추천하는 대응 전략”
- “Gemini가 알려주는 투자전략”
- “오늘의 추천 시장”
- “이번 주 유망 ETF”
- “공격형 투자자 대응전략”

### 4-3. 대체 문구 예시

| 기존 위험 문구 | 변경 문구 |
|---|---|
| 오늘의 추천 | 이번 주 모델 기준안 |
| AI 추천 대응전략 | 시장 해석 참고 정보 |
| 유망 ETF | 관찰 대상 ETF |
| 공격적 대응 | 위험선호 환경 |
| 방어 전략 추천 | 방어 우위 환경 |
| 지금 매수 적기 | 단기 추세 개선 구간 |

---

## 5. QuantMarket 출력 데이터 규칙

QuantMarket이 외부 시스템에 넘기는 데이터는 **설명형 데이터**로 제한한다.

### 5-1. 허용 출력 필드 예시

```json
{
  "asof_date": "2026-03-24",
  "market_scope": "KR_GLOBAL",
  "domestic_market_regime": "RISK_NEUTRAL",
  "overseas_market_regime": "VOLATILITY_ELEVATED",
  "risk_temperature": 62,
  "trend_score": 58,
  "volatility_score": 71,
  "liquidity_score": 49,
  "macro_pressure_score": 66,
  "market_commentary": [
    "국내 시장은 반등 시도가 있으나 변동성은 아직 높은 상태입니다.",
    "해외 시장은 추세보다 이벤트 민감도가 높은 구간입니다."
  ],
  "compliance_meta": {
    "public_same_for_all_users": true,
    "non_personalized": true,
    "advisory_action_signal": false,
    "intended_use": "market_briefing_reference"
  }
}
```

### 5-2. 금지 출력 필드 예시

아래 필드는 QuantMarket output에서 제거한다.

- recommended_buy_assets
- recommended_sell_assets
- action_now
- user_profile_response
- personalized_strategy
- suggested_portfolio_weight
- recommended_etf_list
- market_entry_signal_for_user
- aggressive_allocation_now

---

## 6. Quant ↔ QuantMarket 경계

QuantMarket은 시장상태를 설명하고, Quant는 이를 모델 입력으로 사용할 수 있다.  
하지만 QuantMarket이 직접 포트폴리오를 만들면 안 된다.

### 허용 경계

- QuantMarket → Quant: 시장상태 feature 전달
- Quant → QuantMarket: 백테스트 해석 시 참고용 시장상태 매핑

### 금지 경계

- QuantMarket → 직접 종목 선정
- QuantMarket → 직접 비중 산출
- QuantMarket → 사용자별 전략 조정
- QuantMarket → 개인 맞춤 자산배분

즉, QuantMarket은 **시장 컨텍스트 공급자**이지 **투자결정 엔진**이 아니다.

---

## 7. QuantService ↔ QuantMarket 경계

QuantService는 QuantMarket 데이터를 UI에 보여줄 수 있다.  
그러나 보여주는 방식도 설명형이어야 한다.

### 허용 방식

- 시장상태 카드
- 위험온도 배지
- 시장 해설 문장
- “이번 주 관찰 포인트”
- “모델이 참고하는 시장 환경”

### 금지 방식

- 시장분석 페이지에서 종목 추천과 직접 연결
- “시장분석 결과 이번 주는 ○○ ETF를 사야 함” 식 연결
- “당신에게 맞는 시장 대응” 식 개인화 연결
- 시장상태를 곧바로 매매행동 버튼과 결합

---

## 8. 필수 주의사항 블록

QuantMarket 관련 모든 주요 페이지/데이터 노출 영역에는 아래와 같은 주의사항 블록을 넣을 수 있도록 구조를 만든다.

### 기본 주의사항 예시

> 본 정보는 공개된 기준에 따라 산출된 시장 브리핑용 참고 정보입니다.  
> 특정 이용자의 투자목적, 재산상황, 투자경험 또는 위험선호를 반영한 개별 자문이 아닙니다.  
> 투자판단은 이용자 본인의 책임이며, 자산가격 변동에 따라 원금손실이 발생할 수 있습니다.

### 성과/모델 연결 시 추가 문구

> 시장상태 정보는 모델 해석을 돕기 위한 참고자료이며, 특정 자산의 매수·매도 또는 비중 확대·축소를 직접 권유하지 않습니다.

---

## 9. UI/페이지 구조 지시

Codex는 QuantMarket UI 또는 API 문서에 아래 구조를 반영한다.

### 9-1. 권장 페이지 섹션

1. 이번 주 시장 상태 요약  
2. 국내 시장 해설  
3. 해외 시장 해설  
4. 주요 지표 변화  
5. 관찰 포인트  
6. 모델 참고용 시장환경  
7. 주의사항  

### 9-2. 피해야 할 페이지 섹션

- 이번 주 추천 종목
- 시장별 추천 ETF
- 투자자별 대응전략
- 공격형/보수형 맞춤 시장조언
- 지금 사야 할 자산

---

## 10. API 정책

QuantMarket API는 **public briefing API**로 정의한다.

### 필수 정책

- 동일 요청에 대해 사용자별 다른 결과를 만들지 않는다.
- user_id 기반 personalization 금지
- age / asset / risk_profile / holdings 입력 금지
- action-oriented response 금지
- explanation-oriented response만 허용
- compliance_meta 필수

### API 예시 네이밍

허용:

- /market/weekly-summary
- /market/regime-overview
- /market/risk-temperature
- /market/commentary
- /market/indicator-history

금지:

- /market/recommendation
- /market/buy-signal
- /market/sell-signal
- /market/personal-strategy
- /market/my-market-action

---

## 11. 챗봇/LLM 사용 제한

QuantMarket 내부에서 생성형 AI를 사용할 수는 있다.  
그러나 출력은 반드시 **설명형 텍스트**로 제한한다.

### 허용 사용

- 지표 기반 시장 브리핑 문장 요약
- 공개형 리포트 초안 작성
- 시장 이벤트 설명 문장 정리
- 용어 설명 생성

### 금지 사용

- “이번 주 어떤 ETF를 살까요?”에 대한 답변 생성
- “내 계좌는 어떻게 조정할까요?”에 대한 답변 생성
- “지금 매수해도 될까요?”에 대한 답변 생성
- 보유종목 기반 사용자별 대응전략 생성

### LLM 시스템 프롬프트 방향

- 투자판단 권유 금지
- 개별성 판단 금지
- 종목/비중/타이밍 권고 금지
- 설명형 시장브리핑만 허용
- 법적 리스크 문구 우선

---

## 12. 개발 우선순위

### P0

- 위험 문구 전수 치환
- 추천형 API/필드 제거
- personalization 입력 차단
- 챗봇 투자질문 차단
- compliance_meta 추가
- 주의사항 블록 공통화

### P1

- 시장상태 데이터 표준 스키마 정리
- 위험온도/추세/변동성 등 핵심 상태값 명칭 표준화
- UI 카드/배지 텍스트 정리
- 문서화 및 내부 운영 가이드 작성

### P2

- 해외시장/매크로/원자재 확장
- 브리핑 자동화 정교화
- 이력 시각화 고도화
- 모델 참고 연결성 개선

---

## 13. QA 체크리스트

배포 전 아래를 반드시 확인한다.

- [ ] 사용자 입력에 따라 시장대응안이 달라지지 않는가?
- [ ] 종목 추천으로 읽힐 문구가 남아 있지 않은가?
- [ ] 비중 확대/축소 권유형 문구가 없는가?
- [ ] AI 추천/매수적기/유망ETF 같은 표현이 제거되었는가?
- [ ] 모든 주요 출력에 주의사항 블록이 연결되는가?
- [ ] API response에 compliance_meta가 포함되는가?
- [ ] 챗봇이 투자판단 질문을 차단하는가?
- [ ] QuantMarket output이 설명형 데이터로만 구성되는가?

---

## 14. Codex 최종 작업 지시

Codex는 QuantMarket을 다음 원칙에 맞게 수정/정리할 것.

1. QuantMarket은 시장상태 브리핑 시스템으로만 정의한다.  
2. 종목 추천, 자산배분 추천, 타이밍 권유, 개인화 대응 기능은 넣지 않는다.  
3. 모든 문구를 추천형에서 설명형으로 바꾼다.  
4. 모든 데이터/API 출력에 compliance 관점을 반영한다.  
5. 챗봇/LLM 기능은 투자판단을 차단하고 서비스 안내/지표 설명/시장 브리핑만 허용한다.  
6. QuantMarket 결과는 Quant와 QuantService의 참고용 공개형 컨텍스트 데이터로만 전달한다.  
7. 페이지/문서/API 명칭에서도 recommendation, buy, sell, personalized 같은 표현을 제거한다.  

