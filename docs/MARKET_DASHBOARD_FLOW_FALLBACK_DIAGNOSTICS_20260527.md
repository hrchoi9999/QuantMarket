# Market Dashboard Flow Fallback Diagnostics 2026-05-27

- generated_at: 2026-05-27 19:55 KST
- revised_at: 2026-05-27 20:42 KST
- handoff_asof: 2026-05-27
- scope: remaining `low_confidence_fallback` rows in `index_forecast_signal_current`
- fallback_count: 5/12
- note: `low_confidence_ratio` was corrected to be calculated per candidate group, not as a global rule-level average.

## Current Fallback Rows

| Market | Horizon | Pred | Confidence | Floor | Gap | Top2 Margin | Hist LowConf | Hist Percentile | Sharpe | Rule | Model | Label |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| KOSPI | 10d | sideways | 0.366 | 0.450 | 0.084 | 0.028 | 0.983 | 0.464 | 1.026 | defensive_100_30_0 | extra_trees | existing |
| KOSPI200 | 10d | down | 0.338 | 0.450 | 0.112 | 0.004 | 0.984 | 0.019 | 1.058 | moderate_80_40_0 | extra_trees | vol_adjusted_q2020 |
| KOSDAQ | 5d | up | 0.411 | 0.550 | 0.139 | 0.021 | 0.886 | 0.295 | 0.056 | moderate_80_40_0 | ensemble_mean_all | vol_adjusted_wide_q2020 |
| KOSPI | 5d | down | 0.347 | 0.450 | 0.103 | 0.010 | 0.980 | 0.070 | 0.913 | moderate_80_40_0 | extra_trees | vol_adjusted_wide_q2020 |
| KOSPI200 | 5d | sideways | 0.349 | 0.500 | 0.151 | 0.001 | 0.997 | 0.095 | 1.048 | defensive_100_30_0 | extra_trees | vol_adjusted_wide_q2020 |

Definitions:
- Gap: `confidence_floor - current confidence`.
- Top2 Margin: difference between the largest and second-largest class probabilities.
- Hist LowConf: historical ratio below the selected confidence floor.
- Hist Percentile: current confidence percentile within the selected model history.

## Cause Summary

| Segment | Cause | Interpretation |
|---|---|---|
| KOSDAQ 5d | weak model plus high floor | Sharpe is only 0.056 and historical low-confidence ratio is 0.656. This is not just a floor issue; the 5d KOSDAQ signal itself is weak. |
| KOSPI 5d | flat probability distribution | Top2 margin is 0.010 and current confidence is in the 7th percentile. The model has no clear near-term direction. |
| KOSPI200 5d | almost tied probabilities | Top2 margin is 0.001 and current confidence is in the 9.5th percentile. This is the clearest ambiguity case. |
| KOSPI 10d | normal-but-below-floor confidence | Current confidence is near the historical median, but the chosen rule has a high 0.45 floor and 98%+ historical low-confidence ratio. |
| KOSPI200 10d | rare low-confidence event | Current confidence is in the 1.9th percentile with a 0.004 top2 margin. The model is unusually uncertain today. |

## Lower-Fallback Alternatives

Lowering fallback is possible, but most alternatives trade away too much Sharpe.

| Segment | Best lower-fallback alternative | LowConf | Sharpe | Sharpe loss vs selected | Comment |
|---|---|---:|---:|---:|---|
| KOSDAQ 5d | floor 0.00/0.30 variants | 0.000 | -0.313 | -0.370 | Not acceptable. It removes fallback by accepting a negative Sharpe rule. |
| KOSPI 10d | moderate_80_40_0 floor 0.00/0.30 | 0.000 | 0.349 | -0.676 | Not acceptable. Current defensive rule is materially better. |
| KOSPI 5d | moderate_80_40_0 floor 0.00/0.30 | 0.000 | 0.620 | -0.293 | Possible only if fallback avoidance is prioritized over Sharpe. |
| KOSPI200 10d | moderate_80_40_0 floor 0.00/0.30 | 0.000 | 0.799 | -0.259 | Sharpe sacrifice is meaningful. |
| KOSPI200 5d | moderate_80_40_0 floor 0.00/0.30 | 0.000 | 0.954 | -0.093 | Most reasonable candidate for next tuning. |

## Conclusion

The remaining fallback rows are not mainly caused by today's one-off model failure. They are concentrated in low-margin probability regimes where the selected tree or ensemble models often do not exceed the configured floor:

- 5d signals have very small probability margins.
- KOSDAQ 5d is structurally weak and should not be forced into higher exposure.
- KOSPI/KOSPI200 5d require probability calibration testing or a separate short-horizon confidence policy.
- KOSPI200 5d is the only segment where reducing fallback may be worth testing immediately because the Sharpe loss is relatively small.

## Next Action

Run a focused probability calibration test for 5d KOSPI and KOSPI200 first. Keep KOSDAQ 5d defensive until the underlying model improves.
