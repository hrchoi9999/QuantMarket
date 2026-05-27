# Market Dashboard Flow Re-evaluation 2026-05-27

- generated_at: 2026-05-27 19:20 KST
- dataset_asof: 2026-05-27
- flow_feature_max_date: 2026-05-27
- scopes: KOSPI, KOSDAQ, KOSPI200
- horizons: 5d, 10d, 20d, 60d
- models: logistic, random_forest, extra_trees
- label_policies: existing, q2020, vol_adjusted_q2020, vol_adjusted_wide_q2020
- cost_bps: 5

The full five-model run exceeded the 15 minute execution limit. This run uses the core models that dominated the previous best set and keeps the investable-only scope policy.

## Best Rule Tuning Results

| Market | Horizon | Candidate | Decision | Label | Model | Rule | Floor | Sharpe | B&H Sharpe | CumRet | B&H CumRet |
|---|---:|---|---|---|---|---|---:|---:|---:|---:|---:|
| KOSDAQ | 5d | argmax_best | argmax | vol_adjusted_wide_q2020 | ensemble_mean_all | moderate_80_40_0 | 0.55 | 0.056 | 0.002 | 0.028 | 0.003 |
| KOSPI | 5d | argmax_best | argmax | vol_adjusted_wide_q2020 | extra_trees | cash_heavy_70_20_0 | 0.50 | 0.922 | 0.889 | 0.198 | 1.246 |
| KOSPI200 | 5d | threshold_best | threshold | vol_adjusted_wide_q2020 | extra_trees | defensive_100_30_0 | 0.50 | 1.048 | 1.011 | 0.420 | 1.620 |
| KOSDAQ | 10d | argmax_best | argmax | existing | logistic | up_only_100_0_0 | 0.00 | 0.276 | 0.076 | 0.169 | 0.091 |
| KOSPI | 10d | selected | threshold | existing | extra_trees | defensive_100_30_0 | 0.45 | 1.026 | 0.965 | 0.412 | 1.361 |
| KOSPI200 | 10d | argmax_best | argmax | vol_adjusted_q2020 | extra_trees | baseline_100_50_0 | 0.50 | 1.086 | 1.080 | 0.711 | 1.738 |
| KOSDAQ | 20d | argmax_best | argmax | vol_adjusted_wide_q2020 | random_forest | moderate_80_40_0 | 0.50 | 0.115 | 0.137 | 0.066 | 0.167 |
| KOSPI | 20d | argmax_best | argmax | vol_adjusted_wide_q2020 | logistic | cash_heavy_70_20_0 | 0.00 | 0.536 | 0.875 | 0.252 | 1.166 |
| KOSPI200 | 20d | argmax_best | argmax | q2020 | ensemble_mean_all | up_only_100_0_0 | 0.00 | 1.216 | 0.972 | 0.896 | 1.458 |
| KOSDAQ | 60d | argmax_best | argmax | q2020 | logistic | up_only_100_0_0 | 0.50 | 0.242 | 0.144 | 0.156 | 0.152 |
| KOSPI | 60d | selected | threshold | vol_adjusted_q2020 | ensemble_mean_all | baseline_100_50_0 | 0.45 | 1.637 | 1.026 | 0.957 | 1.110 |
| KOSPI200 | 60d | selected | threshold | existing | ensemble_mean_all | baseline_100_50_0 | 0.00 | 1.628 | 1.141 | 1.222 | 1.388 |

## Horizon Average

| Horizon | Sharpe | B&H Sharpe | CumRet | B&H CumRet |
|---:|---:|---:|---:|---:|
| 5d | 0.675 | 0.634 | 0.215 | 0.956 |
| 10d | 0.796 | 0.707 | 0.430 | 1.063 |
| 20d | 0.622 | 0.661 | 0.405 | 0.930 |
| 60d | 1.169 | 0.770 | 0.778 | 0.883 |

## Interpretation

- 60d is the strongest horizon after latest flow refresh.
- 5d and 10d retain positive Sharpe lift but return capture remains low because selected rules are defensive.
- 20d is mixed. KOSPI200 improves, but KOSPI and KOSDAQ remain weaker than buy-and-hold by Sharpe.
- KOSDAQ remains the weakest market across horizons.
