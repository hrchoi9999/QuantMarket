# Market Dashboard Flow Probability Calibration 2026-05-27

- generated_at: 2026-05-27 20:42 KST
- scope: KOSPI 5d, KOSPI200 5d
- label_policy: vol_adjusted_wide_q2020
- model_tested: extra_trees raw vs extra_trees calibrated sigmoid
- cost_bps: 5

## Classification Result

| Market | Model | Decision | BalAcc | MacroF1 | AvgConf | MedianConf | AvgTop2Margin | LowConf |
|---|---|---|---:|---:|---:|---:|---:|---:|
| KOSPI | extra_trees_raw | argmax | 0.364 | 0.346 | 0.382 | 0.377 | 0.050 | 0.980 |
| KOSPI | extra_trees_calibrated_sigmoid | argmax | 0.302 | 0.224 | 0.421 | 0.419 | 0.103 | 0.832 |
| KOSPI200 | extra_trees_raw | threshold | 0.353 | 0.309 | 0.382 | 0.376 | 0.050 | 0.997 |
| KOSPI200 | extra_trees_calibrated_sigmoid | threshold | 0.332 | 0.246 | 0.425 | 0.418 | 0.108 | 0.967 |

## Backtest Result

| Market | Model | CumRet | Sharpe | B&H Sharpe | MaxDD | AvgExposure | Turnover | LowConf |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| KOSPI | extra_trees_raw | 0.442 | 0.913 | 0.889 | -0.126 | 0.405 | 0.007 | 0.980 |
| KOSPI | extra_trees_calibrated_sigmoid | 0.196 | 0.478 | 0.889 | -0.153 | 0.333 | 0.048 | 0.832 |
| KOSPI200 | extra_trees_raw | 0.420 | 1.048 | 1.011 | -0.094 | 0.302 | 0.002 | 0.997 |
| KOSPI200 | extra_trees_calibrated_sigmoid | 0.363 | 1.003 | 1.011 | -0.094 | 0.290 | 0.012 | 0.967 |

## Conclusion

Sigmoid calibration raises average confidence and top-two margin, so it reduces low-confidence frequency slightly. However, it worsens directional quality and backtest performance:

- KOSPI 5d Sharpe falls from 0.913 to 0.478.
- KOSPI200 5d Sharpe falls from 1.048 to 1.003.
- Macro F1 deteriorates in both markets.
- Turnover rises, especially in KOSPI.

Do not apply calibrated extra_trees to production handoff yet. The problem is not only under-confident probabilities; calibration changes the signal distribution and weakens performance.

## Next Action

Use a separate short-horizon confidence policy instead of probability calibration as the next improvement path. Test lower effective floors or confidence bands only for KOSPI/KOSPI200 5d while preserving the raw extra_trees probabilities.
