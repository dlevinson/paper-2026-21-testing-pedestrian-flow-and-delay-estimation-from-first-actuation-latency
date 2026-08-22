# MCAV First-Actuation Poisson Model

Source:

- `mcav_poisson_first_actuation_model.csv`
- `mcav_comparison_summary.csv`

This analysis treats the Manual Crossing-Actuation Validation field workbook as method-validation data. It compares observed pedestrian counts against counts implied by first pedestrian actuation per cycle under a Poisson-arrival assumption.

## Model

For each complete observed non-walk interval:

- `t_i` is the time from the start of FDW/non-walk to the first observed pedestrian button push;
- `c_j` is the non-walk duration for a cycle with no observed push, treated as right-censored exposure;
- `n` is the number of cycles with an observed first push.

The censored exponential/Poisson rate estimate is:

`lambda = n / (sum(t_i) + sum(c_j))`

The implied pedestrian count over the observed period is:

`N_hat = lambda * observed_seconds`

For comparison, the output also reports:

- an observed-first-push-only model, `lambda = n / sum(t_i)`, which ignores no-push censored cycles;
- the workbook's own saved first-push summary model.

## Aggregate Results

Across 14 direction cases:

| Quantity | Count | Share of actual |
|---|---:|---:|
| Actual observed pedestrians | 1,744.0 | 1.000 |
| Observed-first-push-only Poisson implied count | 1,004.7 | 0.576 |
| Censored first-push Poisson implied count | 805.6 | 0.462 |
| Workbook saved first-push model count | 1,183.5 | 0.679 |

The corresponding calibration multipliers, actual divided by model-implied count, are:

| Model | Calibration multiplier |
|---|---:|
| Observed-first-push-only Poisson | 1.74 |
| Censored first-push Poisson | 2.17 |
| Workbook saved first-push model | 1.47 |

Mean absolute relative error by case:

| Model | Mean absolute relative error |
|---|---:|
| Observed-first-push-only Poisson | 40.1% |
| Censored first-push Poisson | 51.9% |
| Workbook saved first-push model | 38.5% |

## Interpretation

The first-actuation signal is informative but not a pedestrian count. The model undercounts observed pedestrians unless a calibration factor is applied. This is expected because:

- one first push can represent multiple pedestrians;
- many pedestrians in the field observations crossed without pushing;
- later arrivals in the same cycle are unobserved by a first-actuation-only model;
- cycles with no push provide censored evidence of lower arrival rates, reducing the censored Poisson estimate.

The censored model is statistically cleaner for first-actuation event data, but in these field observations it is lower than the actual pedestrian counts. That does not invalidate the method; it shows the need for an empirical calibration layer from first-actuation arrivals to all pedestrians. Because this specification matches the pooled SCATS estimator, its multiplier of 2.165 is used in the network application.

The extracted model uses row order as the observation clock because the hand-coded workbook is one row per second and contains minor raw `Time (s)` anomalies in the cells. This avoids letting isolated time-entry typos distort cycle exposure.
