# MCAV Model Stability

Source:

- `mcav_cycle_first_actuation_plugin_model.csv`
- `mcav_cycle_model_stability_summary.csv`
- `mcav_cycle_model_leave_one_out.csv`

This checks how stable the aggregate implied/actual ratios are for the cycle-level first-actuation plug-in model.

## Aggregate Ratios

Across 14 direction cases:

| Model | Implied / actual ratio | Calibration multiplier |
|---|---:|---:|
| Pooled censored Poisson, all observed exposure | 0.462 | 2.16 |
| Non-walk exposure only | 0.612 | 1.63 |
| Full observed cycle exposure | 0.667 | 1.50 |

## Leave-One-Out Stability

Removing one case at a time gives:

| Model | Leave-one-out range |
|---|---:|
| Pooled censored Poisson | 0.444 to 0.478 |
| Non-walk exposure only | 0.592 to 0.622 |
| Full observed cycle exposure | 0.647 to 0.677 |

This indicates that the aggregate ratios are not driven by a single case.

## Bootstrap Stability

A case-level bootstrap with replacement gives approximate 95% intervals:

| Model | Bootstrap 95% interval |
|---|---:|
| Pooled censored Poisson | 0.411 to 0.524 |
| Non-walk exposure only | 0.568 to 0.669 |
| Full observed cycle exposure | 0.623 to 0.726 |

The bootstrap intervals are wider because there are only 14 direction cases and the cases are heterogeneous. The aggregate ratios are directionally stable, but the precise multiplier should be treated as provisional until more validation cases are added.

## Interpretation

The full-cycle model ratio of 0.667 performs better case-by-case than the pooled model, but it is a different estimator. The SCATS network application uses pooled censored exposure, so its matched calibration multiplier is 2.165, with a bootstrap interval from 1.907 to 2.434. A multiplier near 1.5 applies only to the full-cycle plug-in specification.
