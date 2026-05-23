# QuantMarket 시장전망 AI V1.1 설계안

- 작성일: 2026-05-14
- 목적: AI v1 실패 원인을 반영해, production 승격 가능성이 높은 시장전망 AI v1.1 구조를 설계한다.

## 1. 현재 상태

AI v1은 다음 산출을 완료했다.

- 모델 artifact 생성
- 최신 9개 scope/horizon 예측 생성
- validation report 생성
- promotion gate 적용

하지만 성능 기준을 통과하지 못해 `research_only`로 유지했다.

핵심 판단:
- v1은 feature가 너무 넓고, 모델이 최근 검증 구간에서 안정적인 신호를 만들지 못했다.
- 기존 `walk-forward ridge calibration`이 v1보다 안정적이었다.
- 따라서 v1.1은 더 복잡한 모델이 아니라 더 좁은 feature, 더 엄격한 walk-forward, 더 명확한 승격 기준이 필요하다.

## 2. V1 실패 원인

### 2.1 Feature 과다

v1은 167개 feature를 사용했다.

문제:
- 수급 feature처럼 과거 구간 coverage가 낮은 feature가 많다.
- categorical/label feature가 많아 tree 모델이 최근 구간에서 불안정해질 수 있다.
- 모델이 시장 신호보다 결측/구간 특성을 학습했을 가능성이 있다.

### 2.2 검증 방식 불일치

기존 ridge calibration은 walk-forward 검증에서 비교적 안정적이었다.

v1은 chronological 80/20 split으로 검증했다.

문제:
- 최근 20% 구간이 특정 시장 국면에 치우치면 전체 모델 품질보다 특정 국면 성능만 강하게 반영된다.
- 실제 운영 방식은 매일 과거 데이터로 재학습/예측하는 walk-forward에 가깝다.

### 2.3 Target 단순성

v1 target은 `target_forward_return` 중심이었다.

문제:
- 단순 수익률은 상승/하락 방향성은 보지만, 위험 대비 매력도는 반영하지 못한다.
- 시장전망에서는 최대낙폭, downside risk, excess return이 중요하다.

## 3. V1.1 핵심 방향

V1.1은 아래 원칙으로 설계한다.

1. 좁은 feature set
2. horizon별 분리 모델
3. walk-forward validation
4. baseline 대비 개선 검증
5. production 승격 gate 명확화

## 4. Feature Set 설계

### 4.1 Core Feature Set

우선 167개 feature 중 약 35~50개만 사용한다.

우선 포함:
- `market_forecast_score`
- `calibrated_forecast_score`
- `calibration_confidence_score`
- `market_state_score`
- `trend_score`
- `breadth_score`
- `risk_score`
- `risk_on_score`
- `risk_off_score`
- `expected_volatility_score`
- `drawdown_risk_score`
- `upside_participation_score`
- `global_risk_on_score`
- `external_macro_pressure_score`
- `external_asset_risk_on_score`
- `korea_proxy_momentum_score`
- `us_equity_momentum_score`
- `credit_proxy_score`
- `safe_haven_pressure_score`
- `market_state_score_delta_5d`
- `market_state_score_delta_20d`
- `market_forecast_score_delta_5d`
- `market_forecast_score_delta_20d`
- `market_forecast_score_acceleration_5d`
- `transition_count_20d`
- `regime_stability_score`
- `overall_feature_coverage_ratio`
- source별 `*_coverage_ratio`

우선 제외:
- raw level 계열 중 중복성이 큰 항목
- coverage가 낮은 flow raw feature
- generated_at/source path/policy text
- target 관련 컬럼
- 과도한 categorical label

### 4.2 Feature Selection 방식

1차는 수동 curated set을 사용한다.

2차는 아래 지표로 자동 선별한다.
- rolling IC
- missing rate
- regime별 성능 안정성
- feature redundancy correlation

## 5. Target 설계

V1.1 기본 target:
- `target_forward_return`

보조 target:
- `target_excess_return_vs_cash`
- `target_forward_max_drawdown`
- `target_downside_risk_flag`

V1.1에서는 우선 회귀 target을 유지하되, 별도 risk-adjusted score를 만든다.

예:

```text
risk_adjusted_target
= target_forward_return
  + 0.3 * target_excess_return_vs_cash
  + 0.5 * target_forward_max_drawdown
```

설명:
- `target_forward_max_drawdown`은 보통 음수이므로, 낙폭이 클수록 target이 낮아진다.
- 단순 상승률보다 위험을 반영한 예측 학습이 가능하다.

## 6. 모델 구조

### 6.1 기본 모델

V1.1 기본 모델은 아래 2개를 비교한다.

1. Ridge / ElasticNet
- 장점: 안정적, 과적합 적음, 해석 쉬움

2. HistGradientBoostingRegressor
- 장점: 비선형 관계 포착 가능
- 단점: 최근 구간 과적합 가능

최종 production 후보는 둘 중 성능이 좋은 하나가 아니라, 아래 기준으로 고른다.

- 20d 안정성 우선
- regime별 성능 붕괴 여부
- baseline 대비 개선 여부
- 최근 rolling performance

### 6.2 Ensemble 정책

V1.1에서는 무조건 ensemble하지 않는다.

조건부 ensemble:
- Ridge가 안정적이고 HGB가 일부 국면에서만 강하면 weighted ensemble 검토
- HGB가 불안정하면 Ridge only 채택

## 7. Validation 설계

V1.1은 walk-forward 검증을 기본으로 한다.

검증 방식:
- 최소 학습기간: 756 trading days
- refit 주기: 20 trading days
- test: 다음 1개 row 또는 다음 20개 row
- scope/horizon별 독립 평가

평가 지표:
- prediction corr
- rank corr
- directional hit rate
- MAE
- downside hit rate
- top/bottom quintile spread
- baseline 대비 개선폭

## 8. Promotion Gate

Production 후보 승격 기준:

필수:
- `ALL 20d` prediction corr >= 0.15
- `KOSPI 20d` 또는 `KOSDAQ 20d` 중 하나 이상 corr >= 0.12
- 20d directional hit rate >= 0.55
- baseline 대비 20d corr 개선
- 최근 60d monitoring이 `weak`가 아니어야 함

차단:
- 1d 성능이 약한 것은 production 차단 사유가 아님
- 단, 20d가 약하면 production 차단
- 특정 regime에서 hit rate 45% 미만이면 warning

## 9. 산출물 설계

V1.1 생성 파일:

- `market_forecast_ai_v1_1_predictions_current.csv`
- `market_forecast_ai_v1_1_validation_latest.csv`
- `market_forecast_ai_v1_1_metrics_latest.csv`
- `market_forecast_ai_v1_1_feature_importance_latest.csv`
- `market_forecast_ai_v1_1_report_latest.md`

DB table:
- `market_forecast_ai_v1_1_predictions`
- `market_forecast_ai_v1_1_validation`
- `market_forecast_ai_v1_1_feature_importance`

Model artifact:
- `D:\QuantMarket\models\market_forecast_ai_v1_1\`

## 10. 개발 단계

### Step 1. Curated feature set 생성

- `market_model_ready_feature_columns_current.json`에서 v1.1 feature set 생성
- coverage 낮은 feature 제외

### Step 2. risk-adjusted target 생성

- 기존 target mart에서 파생 target 생성
- 기존 target은 유지

### Step 3. walk-forward trainer 구현

- Ridge / ElasticNet / HGB 후보 비교
- scope/horizon별 평가

### Step 4. promotion gate 구현

- 기준 통과 여부 자동 판단
- `promote_candidate` 또는 `research_only`

### Step 5. 최신 예측 산출

- 통과 여부와 관계없이 latest prediction은 생성
- 단, production handoff에는 승격 전 미반영

## 11. 권장 진행

다음 작업은 바로 구현 단계로 넘어간다.

우선 구현 순서:

1. v1.1 curated feature set 생성
2. v1.1 walk-forward trainer 구현
3. v1.1 validation report 생성
4. v1.1 promotion gate 적용

최종 목표:

`AI v1.1이 기존 ridge calibration보다 명확히 나을 때만 production 후보로 승격한다.`
