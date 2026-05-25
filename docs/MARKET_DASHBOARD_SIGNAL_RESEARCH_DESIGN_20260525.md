# Market Dashboard Signal Research Design

## 목적

시장 브리핑 현황판의 3축 점수와 주가지수 방향성의 관계를 production Mart와 분리해 검증한다.
효용성이 확인되기 전까지 Quant/QuantService에는 연구 산출물로만 제공한다.

## 입력

- Source DB: `D:\QuantMarket\data\db\market_analysis.db`
- 3축 신호: `market_analysis_payload.today_bridge.market_state_composite.composite_chart.series`
  - `financial_environment`
  - `medium_term_model_outlook`
  - `short_term_market_condition`
- 실제 지수: `market_index_daily`
  - KOSPI: `1001`
  - KOSDAQ: `2001`
  - KOSPI200: `1028`

## 별도 산출 구조

- Research DB: `D:\QuantMarket\data\db\market_dashboard_signal_research.db`
- Current output: `D:\QuantMarket\service_platform\research\market_dashboard_signal\current`
- Report: `D:\QuantMarket\reports\market_dashboard_signal_research`
- Production `service_platform\ai_training\market_context\current`와 `quant_model_handoff`는 수정하지 않는다.

## 라벨 정책

방향성 라벨은 학습 내부용 5단계로 둔다.

- `strong_down`
- `mild_down`
- `sideways`
- `mild_up`
- `strong_up`

각 `market_scope`와 `forecast_horizon`별 미래 수익률의 20/40/60/80% 분위수로 나눈다.
서비스 표시나 다른 쓰레드 제공 시에는 필요하면 `하락/횡보/상승` 3단계로 압축한다.

## 예측 기간과 범위

- Horizons: `5d`, `10d`, `20d`, `60d`
- Scopes: `ALL`, `KOSPI`, `KOSDAQ`, `KOSPI200`
- `ALL`은 KOSPI/KOSDAQ 미래 수익률의 동일가중 평균이다.

## 검증

1. 3축 원점수, 변화율, 이동평균, 교차항을 feature로 만든다.
2. 기존 `market_features_hourly`와 `market_component_scores`를 확장 feature로 결합한다.
3. `market_investor_flow_daily`와 `kiwoom_stock_investor_flow_daily`를 수급 feature Mart로 결합한다.
4. 미래 지수 수익률과 feature 상관을 산출한다.
5. 3축 bucket 조합별 평균 수익률, 양의 수익률 비율, -5% 손실 비율을 산출한다.
6. `sklearn` 기준 Logistic Regression baseline으로 5단계 방향 라벨 예측력을 점검한다.
7. 5단계 라벨을 `down / sideways / up` 3-class로 압축해 별도 성능을 평가한다.
8. horizon별 연도 단위 walk-forward 성능표를 생성한다.

## 기본 성능표

앞으로 연구 결과 보고 시 아래 horizon을 한 표에 같이 표시한다.

| 범위 | 5d | 10d | 20d | 60d |
|---|---:|---:|---:|---:|
| ALL | label/probability | label/probability | label/probability | label/probability |
| KOSPI | label/probability | label/probability | label/probability | label/probability |
| KOSDAQ | label/probability | label/probability | label/probability | label/probability |
| KOSPI200 | label/probability | label/probability | label/probability | label/probability |

성능 평가는 `dashboard_axis_horizon_scorecard_current.csv`를 기준으로 holdout과 walk-forward를 같이 본다.

## 실행

```powershell
D:\Quant\venv64\Scripts\python.exe D:\QuantMarket\build_market_dashboard_signal_research.py
```

## 통과 기준 초안

- 단순 majority baseline 대비 `balanced_accuracy` 또는 `macro_f1` 개선
- 20d 기준 조합별 기대수익률/손실률에 일관된 순위성 확인
- 최소 1년 이상 out-of-sample 구간에서 과도한 붕괴 없음

이 기준을 만족하면 다른 쓰레드에는 `dashboard_axis_signal_latest.json`와 current CSV를 읽기 전용 인터페이스로 공개한다.

## v2 산출물

- `dashboard_axis_model_metrics_3class_current.csv`
- `dashboard_axis_walk_forward_metrics_current.csv`
- `dashboard_axis_horizon_scorecard_current.csv`
- `dashboard_axis_signal_latest.json#model_predictions_3class`
- `dashboard_axis_flow_feature_daily_current.csv`
