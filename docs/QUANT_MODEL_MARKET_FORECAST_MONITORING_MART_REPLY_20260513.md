# QuantMarket 예측 성능 모니터링 Mart 회신

- 작성일: 2026-05-13
- 대상: Quant 모델 쓰레드

## 완료

예측 성능 모니터링 mart를 추가했습니다.

## 산출물

- DB: `D:\QuantMarket\data\db\market_context.db`
- DB table: `market_forecast_monitoring_daily`
- CSV: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_forecast_monitoring_daily_current.csv`
- report: `D:\QuantMarket\reports\market_forecast_monitoring\market_forecast_monitoring_latest.md`
- manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`

## Row count

- rows: 20,523
- date range: 2017-01-02 ~ 2026-05-11
- duplicate key: 0

## Join key

- `asof_date + market_scope + forecast_horizon`

## 주요 지표

- `baseline_corr_20d/60d/120d`
- `ai_corr_20d/60d/120d`
- `baseline_hit_rate_20d/60d/120d`
- `ai_hit_rate_20d/60d/120d`
- `baseline_mae_20d/60d/120d`
- `ai_mae_20d/60d/120d`
- `ai_minus_baseline_corr_*`
- `ai_minus_baseline_hit_rate_*`
- `ai_minus_baseline_mae_*`
- `monitoring_quality_label`

## 최신 60일 기준 요약

- ALL 20d: strong, ai_corr_60d 0.3022, ai_hit_rate_60d 0.7000
- KOSDAQ 20d: usable, ai_corr_60d 0.1773, ai_hit_rate_60d 0.7000
- 1d 예측축은 대체로 weak
- 5d 예측축은 watch 중심

## 사용 기준

- 모델 고도화 전후 성능 비교는 `ai_minus_baseline_*` 컬럼 사용
- 운영 모니터링은 `monitoring_quality_label`과 60d rolling 지표 우선 확인
- `insufficient_history`는 rolling window 부족 구간입니다.
