# QUANTMARKET_MARKET_BRIEFING_EXPANSION_PLAN_20260325.md

## 목적
현재 QuantMarket의 시장 브리핑 기능을 기반으로,
1. 사용자에게 더 풍성한 시장/자산 해석 정보를 제공할 수 있는 추가 서비스 후보를 정리하고,
2. 이를 가능하게 하기 위해 필요한 누적 데이터, 기록관리, 시계열 분석 구조를 정리한다.

---

## 1. 현재 시스템에서 이미 저장되고 있는 데이터

현재 `market_analysis.db`와 운영 산출물 기준으로 확인한 저장 구조는 아래와 같다.

### 1-1. 일별 원천 데이터
- `market_index_daily`
  - 시장 대표지수 일별 시계열
  - 현재 약 91 거래일 누적
- `market_fx_daily`
  - 환율 일별 시계열
  - 현재 약 91 거래일 누적
- `market_rates_daily`
  - 금리 일별 시계열
  - 현재 약 90 거래일 누적

### 1-2. 시간별 분석 결과
- `market_features_hourly`
  - 정량 feature 스냅샷 저장
  - 예: 수익률, breadth, 변동성, drawdown, 환율/금리 변화 등
  - 현재 약 39개 시점 누적
- `market_component_scores`
  - trend / breadth / risk / defensive_flow / total_score 저장
- `market_state_history`
  - 7단계 시장상태 라벨과 이전 상태 대비 변화 저장
- `market_analysis_payload`
  - summary / detail / today_bridge payload 저장

### 1-3. 파일 기반 운영 기록
- `reports/market_analysis/logs/*.log`
  - 시간별 실행 로그
- `reports/market_analysis/remote_publish_*.json`
  - GCS publish 결과 이력
- `reports/market_analysis/remote_publish_status_latest.json`
  - 최신 publish 상태
- `reports/market_analysis/market_context_latest.json`
  - 최신 뉴스/시장 컨텍스트
- `reports/market_analysis/market_ai_generation_status_latest.json`
  - 최신 AI 생성 상태

### 1-4. 현재 구조의 강점
- 시장 원천 데이터와 분석 결과가 이미 분리되어 있다.
- 시간별 feature / component / state 이력이 있어서 기본적인 시계열 분석의 출발점이 있다.
- payload도 시점별로 DB에 남기고 있어 사용자 노출 결과의 일부 추적이 가능하다.

---

## 2. 현재 구조에서 부족한 점

현재 시스템은 `현재 시점 브리핑 생산`에는 충분하지만, `장기 누적 해석 서비스`를 만들기에는 아래가 부족하다.

### 2-1. 시장 컨텍스트의 이력 저장 부족
현재 뉴스/리스크 컨텍스트는 `latest` 파일만 있고 DB 누적 저장이 없다.
그래서 아래 분석이 어렵다.
- 어느 시점에 어떤 뉴스 맥락이 붙었는지
- 위험 뉴스가 많았던 시간대와 상태 변화의 관계
- AI 문장과 뉴스의 연결 추적

### 2-2. AI 브리핑의 DB 이력 부족
- `market_analysis_ai_notes` 테이블은 있으나 현재 row 수는 0이다.
- 실제 AI 생성 결과는 파일/수동 저장 위주여서 장기 비교가 어렵다.

### 2-3. publish / 소비 이력의 구조화 부족
현재는 publish 결과 JSON 파일은 남지만, 아래 분석이 어렵다.
- 어떤 시각에 어떤 payload version이 나갔는지
- publish 실패율
- QuantService 반영 지연
- stale 데이터 발생 구간

### 2-4. 자산군별 상세 상태 시계열 부족
현재는 멀티애셋 배경 feature 일부만 있고, 자산군별 상태 테이블은 없다.
그래서 아래 서비스가 어렵다.
- 주식/채권/달러/금 각각의 체력 비교
- 어느 자산군이 최근 1주/1개월 동안 상대적으로 강했는지
- 모델 포트폴리오 변화 배경 설명

### 2-5. 상태 지속성/전이 분석용 구조 부족
`market_state_history`는 현재 라벨과 이전 라벨 중심이다.
하지만 아래는 별도 파생 누적이 있으면 더 좋아진다.
- 상승 상태가 몇 시간째 이어졌는지
- 최근 20회 중 상태 전이 빈도
- 상태 안정도 / 잦은 흔들림 여부

### 2-6. 사용자용 장기 히스토리 payload 부재
현재 payload는 mostly current view 중심이다.
아래 같은 서비스용 데이터셋이 없다.
- 최근 1주/1개월 시장 브리핑 변화 타임라인
- 지표 추세 차트용 정리된 API
- 자산 강도 순위 히스토리

---

## 3. 추가 개발하면 좋은 서비스 후보

아래 서비스들은 현재 QuantMarket의 역할과 잘 맞고, 사용자가 시장과 자산을 해석하는 데 실질적으로 도움이 된다.

### A. 시장 브리핑 타임라인
가장 우선순위가 높은 서비스다.

제공 정보:
- 최근 1주 / 1개월 시장상태 변화
- 상태점수 추이
- trend / breadth / risk / defensive_flow 변화
- 주요 전환 시점과 당시 브리핑 문장

사용자 가치:
- 지금 시장이 좋아졌는지 나빠졌는지보다, `어떻게 변해 왔는지`를 이해하기 쉬워진다.
- 주간 모델 기준안과 함께 읽을 때 설득력이 높아진다.

필요 데이터:
- 기존 `market_component_scores`, `market_state_history`
- 추가로 `market_briefing_timeline_payload` 또는 전용 API

### B. 자산군 상대강도 브리핑
멀티애셋 서비스 정체성과 가장 잘 맞는다.

제공 정보:
- 최근 1주 / 1개월 기준 자산군 상대강도
- 주식 / 채권 / 달러 / 금 / 인버스 등 비교
- 강한 자산군 / 약한 자산군 / 중립 자산군

사용자 가치:
- 시장을 단순 상승/하락이 아니라 `어떤 자산이 주도하는지`로 읽을 수 있다.
- REDBOT이 멀티애셋 퀀트모델이라는 점이 자연스럽게 드러난다.

필요 데이터:
- 기존 `bond_20d_ret`, `gold_20d_ret`, `inverse_20d_ret`, `usdkrw_20d_ret`
- 추가로 자산군별 표준화 score 테이블 필요

### C. 시장 내부체력 브리핑
현재 breadth 데이터를 더 잘 쓰는 서비스다.

제공 정보:
- 20일선/60일선 위 종목 비율 추이
- 상승/하락 종목 비율 추이
- 신고가/신저가 확산
- 대형주 중심 상승인지, 시장 전반 확산인지

사용자 가치:
- 지수만 보고 느끼기 어려운 시장 내부 체력을 직관적으로 이해할 수 있다.
- `상승인데 왜 체감이 약한가` 같은 질문에 답하기 좋다.

필요 데이터:
- 기존 breadth feature 시계열
- 추가로 breadth regime 분류 테이블 있으면 좋음

### D. 변동성/리스크 체온계
현재 risk score를 서비스화한 버전이다.

제공 정보:
- 최근 변동성 추이
- drawdown 추이
- 경계/보통/안정 구간 히스토리
- 최근 위험 신호가 확대되는지 축소되는지

사용자 가치:
- 현재 시장이 상승이어도 `편안한 상승인지 불안한 상승인지`를 이해하기 쉬워진다.

필요 데이터:
- 기존 `realized_vol_20d`, `drawdown_5d`, `drawdown_20d`
- 추가로 위험 레짐 라벨 누적 필요

### E. 상태 전이 브리핑
퀀트 모델 서비스다운 차별화 포인트가 될 수 있다.

제공 정보:
- 최근 상태 전이 흐름
- 중립 -> 상승, 상승 -> 하락 같은 변화 패턴
- 현재 상태의 지속 시간
- 상태 안정도 / 흔들림 정도

사용자 가치:
- 현재 상태 한 점보다 `상태의 방향성`과 `전이의 질`을 이해하게 해 준다.

필요 데이터:
- 기존 `market_state_history`
- 추가로 전이 요약 집계 테이블 필요

### F. 모델 해석 백그라운드 카드
시장 브리핑과 모델 기준안을 연결하는 핵심 모듈이다.

제공 정보:
- 이번 주 모델 기준안과 함께 봐야 할 시장 배경 3가지
- 어떤 자산군 배경이 강했는지
- 어떤 위험 요인이 남아 있는지

사용자 가치:
- 시장 브리핑과 모델 기준안이 따로 노는 문제를 줄인다.
- 서비스 정체성이 명확해진다.

필요 데이터:
- 현재 payload + 자산군 상대강도 + 상태 전이 요약

### G. 주간/월간 브리핑 아카이브
운영 시간이 쌓일수록 가치가 커지는 서비스다.

제공 정보:
- 주간 브리핑 요약 히스토리
- 월간 핵심 전환 포인트
- 당시 AI 브리핑 / 상태 / 지표 요약

사용자 가치:
- 사용자가 브리핑 신뢰도를 체감하게 된다.
- 운영 히스토리가 서비스 자산이 된다.

필요 데이터:
- payload archive + AI note archive + market context archive

---

## 4. 추가로 꼭 저장해야 할 데이터

### 4-1. DB에 추가해야 할 핵심 테이블

#### `market_context_history`
용도:
- 뉴스/리스크 맥락의 시점별 저장

권장 컬럼:
- `market`
- `asof`
- `fetched_at`
- `headline_type` (`general` / `risk`)
- `headline_text`
- `source_url`
- `keyword_tags`
- `created_at`

#### `market_ai_brief_history`
용도:
- ChatGPT / Gemini 생성 결과를 정식 이력으로 저장

권장 컬럼:
- `market`
- `asof`
- `provider`
- `model_name`
- `theme_label`
- `viewpoint_key`
- `summary_lines_json`
- `source`
- `input_hash`
- `created_at`

비고:
- 현재 `market_analysis_ai_notes`를 확장하거나 대체 가능

#### `market_publish_history`
용도:
- handoff publish / remote publish 운영 이력 저장

권장 컬럼:
- `market`
- `asof`
- `run_id`
- `target` (`local` / `gcs_current` / `gcs_history`)
- `status`
- `base_url`
- `object_count`
- `etag_summary`
- `latency_ms`
- `created_at`

#### `market_asset_relative_strength_hourly`
용도:
- 자산군별 상대강도 표준화 시계열 저장

권장 컬럼:
- `market`
- `asof`
- `asset_group`
- `ret_5d`
- `ret_20d`
- `ret_60d`
- `zscore`
- `rank`
- `strength_label`
- `created_at`

#### `market_state_transition_stats`
용도:
- 상태 지속 시간 / 전이 빈도 / 안정도 저장

권장 컬럼:
- `market`
- `asof`
- `current_state`
- `prev_state`
- `duration_hours`
- `transition_count_5d`
- `transition_count_20d`
- `stability_score`
- `created_at`

### 4-2. 기존 테이블에 추가하면 좋은 컬럼

#### `market_features_hourly`
추가 후보:
- `oil_20d_ret`
- `vix_like_proxy`
- `foreign_flow_proxy`
- `turnover_ratio`
- `sector_leadership_score`
- `large_small_relative_strength`

#### `market_component_scores`
추가 후보:
- `trend_regime_label`
- `breadth_regime_label`
- `risk_regime_label`
- `defensive_regime_label`
- `total_score_band`

#### `market_state_history`
추가 후보:
- `duration_hours`
- `state_stability_score`
- `state_transition_code`

### 4-3. 파일 기반 latest만 두면 안 되는 데이터
아래는 반드시 DB 또는 archive 파일로 남기는 쪽이 좋다.
- market context
- AI 브리핑 결과
- publish 결과
- QuantService에 실제 전달된 payload snapshot

이유:
- 나중에 “그 시점에 무슨 문구가 나갔는가”를 복원할 수 있어야 한다.
- 운영 이슈, 잘못된 표현, 품질 개선을 추적할 수 있다.

---

## 5. 개발 방안

## 5-1. 단기 (P1.5)
목표:
- 현재 시스템을 크게 흔들지 않고 누적관리 기반을 만든다.

작업:
1. `market_context_history` 추가
2. `market_ai_brief_history` 추가
3. `market_publish_history` 추가
4. 현재 `latest` 리포트를 DB에도 함께 적재
5. 최근 1주 상태 타임라인 payload 추가

완료 후 가능한 서비스:
- 최근 시장 브리핑 변화 타임라인
- 최근 1주 상태 변화 차트
- AI 브리핑 아카이브

## 5-2. 중기 (P2)
목표:
- 멀티애셋 퀀트모델 서비스다운 차별화 기능 강화

작업:
1. `market_asset_relative_strength_hourly` 추가
2. 자산군 강도 rank 계산기 추가
3. 상태 전이 집계 로직 추가
4. 주간/월간 브리핑 아카이브 payload 추가
5. QuantService에 자산군 비교/상태전이 카드 제공

완료 후 가능한 서비스:
- 자산군 상대강도 브리핑
- 상태 전이 브리핑
- 모델 해석 백그라운드 카드

## 5-3. 장기 (P3)
목표:
- 운영 데이터가 쌓일수록 더 좋아지는 시스템으로 전환

작업:
1. 브리핑 품질 평가용 회고 테이블 추가
2. 상태/브리핑/자산군 변화와 실제 모델 변경내역 연결
3. 주간 리포트 자동 생성
4. US 시장 확장 시 KR/US 비교 브리핑 추가

완료 후 가능한 서비스:
- KR/US 비교 브리핑
- 모델 변화 배경 회고 리포트
- 장기 아카이브 기반 인사이트 서비스

---

## 6. 우선순위 제안

가장 먼저 개발할 서비스 3개를 고르면 아래가 좋다.

### 1순위: 시장 브리핑 타임라인
이유:
- 현재 있는 데이터로 가장 빨리 만들 수 있다.
- 사용자 이해도 개선 효과가 크다.

### 2순위: 자산군 상대강도 브리핑
이유:
- REDBOT이 퀀트모델 서비스라는 점을 가장 잘 보여 준다.
- 멀티애셋 정체성을 강화한다.

### 3순위: 모델 해석 백그라운드 카드
이유:
- 시장 브리핑과 모델 기준안을 연결하는 역할이 크다.
- 사용자 입장에서 서비스 흐름이 훨씬 자연스러워진다.

---

## 7. 결론

현재 QuantMarket은 `현재 시점의 시장 브리핑 생산`에는 충분한 구조를 갖췄다.
하지만 `풍성한 시장/자산 해석 서비스`로 가려면 아래 3가지가 추가로 필요하다.

1. 시장 컨텍스트 / AI 브리핑 / publish 결과의 정식 이력 저장
2. 자산군 강도 / 상태 전이 / 브리핑 타임라인 같은 파생 시계열 테이블
3. QuantService가 그대로 쓸 수 있는 장기 히스토리 payload

즉 다음 단계의 핵심은
- 새로운 현재값을 더 만드는 것
보다
- 현재 생성되는 데이터를 `누적, 구조화, 회고 가능`하게 만드는 것
에 있다.
