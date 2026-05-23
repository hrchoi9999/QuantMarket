# QuantMarket Target/Validation Mart 분리 회신

- 작성일: 2026-05-13
- 대상: Quant 모델 쓰레드

## 완료

시장전망용 target mart와 검증 mart를 분리 생성했습니다.

## 산출물

- DB: `D:\QuantMarket\data\db\market_context.db`
- target table: `market_forecast_target_daily`
- validation table: `market_forecast_validation_daily`
- target CSV: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_forecast_target_daily_current.csv`
- validation CSV: `D:\QuantMarket\service_platform\ai_training\market_context\current\market_forecast_validation_daily_current.csv`
- manifest: `D:\QuantMarket\service_platform\ai_training\market_context\current\manifest.json`

## Row count

- `market_forecast_target_daily`: 23,460 rows, 2015-08-24 ~ 2026-05-12
- `market_forecast_validation_daily`: 20,601 rows, 2017-01-02 ~ 2026-05-12
- duplicate key: 0

## Join key

- `asof_date + market_scope + forecast_horizon`

## 주요 컬럼

`market_forecast_target_daily`
- `target_forward_return`
- `target_direction_label`
- `target_available_flag`
- `target_horizon_trading_days`
- `target_start_close`
- `target_end_asof_date`
- `target_end_close`

`market_forecast_validation_daily`
- forecast columns
- calibrated forecast columns
- target columns
- `baseline_direction_hit_flag`
- `baseline_forecast_error`
- `ai_direction_hit_flag`
- `ai_forecast_error`

## 사용 기준

- 학습 target은 `market_forecast_target_daily`를 사용
- 예측값과 실제값 비교는 `market_forecast_validation_daily`를 사용
- `target_available_flag=0`인 최신 row는 아직 미래 수익률이 확정되지 않은 row입니다.
