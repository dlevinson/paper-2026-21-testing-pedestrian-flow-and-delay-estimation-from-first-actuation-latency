# Manual Crossing-Actuation Validation Model Comparison Note

Source outputs:

- `mcav_cycle_level_validation.csv`
- `mcav_case_model_validation.csv`
- `mcav_model_comparison_summary.csv`
- `mcav_model_stability_summary.csv`

The Manual Crossing-Actuation Validation (MCAV) dataset contains 14 observed intersection/direction cases and 492 observed non-walk intervals/cycles. Across those cases the field observations recorded:

| Quantity | Value |
|---|---:|
| Observed pedestrian arrivals | 1,744 |
| Workbook actuator events | 513 |
| Observed pedestrians per actuator event | 3.40 |
| Legal pedestrians with push button | 479 |
| Legal pedestrians without push button | 1,188 |
| Illegal pedestrians with push button | 20 |
| Illegal pedestrians without push button | 43 |
| Pushed button but did not walk | 14 |

Button actuation is therefore not a pedestrian count in these observations. Treating actuator events as pedestrians captures only 29.4% of observed arrivals.

## Aggregate Model Comparison

| Model | Implied pedestrians | Implied / actual | Actual / implied | Case MARE |
|---|---:|---:|---:|---:|
| Diagnostic recorded actuator events, not a person-volume estimator | 513.0 | 0.294 | 3.40 | 68.1% |
| Workbook mean-wait formula | 1,183.5 | 0.679 | 1.47 | 38.5% |
| Pooled first-push Poisson, uncensored only | 1,004.7 | 0.576 | 1.74 | 40.1% |
| Pooled first-push Poisson, censored all observed time | 805.6 | 0.462 | 2.16 | 51.9% |
| Pooled first-push Poisson, censored non-walk only | 745.2 | 0.427 | 2.34 | 55.3% |
| Cycle plug-in, non-walk exposure only | 1,067.7 | 0.612 | 1.63 | 37.0% |
| Cycle plug-in, full observed cycle exposure | 1,164.1 | 0.667 | 1.50 | 31.5% |

The full-cycle plug-in model has the lowest case-level error among these simple forms. It uses the first push in each cycle to estimate a local arrival rate, then applies that rate to observed cycle exposure. It is a diagnostic rather than the paper's network calibration model. The SCATS network estimator pools first-actuation latencies and censored exposure, so its matched MCAV calibration is the pooled censored-Poisson estimate: a multiplier of 2.165.

## Stability

| Model | Aggregate ratio | Leave-one-out range | Bootstrap 95% ratio interval | Multiplier interval |
|---|---:|---:|---:|---:|
| Pooled first-push Poisson, censored all observed time | 0.462 | 0.444 to 0.478 | 0.411 to 0.524 | 1.91 to 2.43 |
| Cycle plug-in, non-walk exposure only | 0.612 | 0.592 to 0.622 | 0.568 to 0.670 | 1.49 to 1.76 |
| Cycle plug-in, full observed cycle exposure | 0.667 | 0.647 to 0.677 | 0.623 to 0.726 | 1.38 to 1.60 |

The aggregate ratio is not driven by a single case: deleting any one case leaves the full-cycle ratio between 0.647 and 0.677. The bootstrap interval is wider because there are only 14 heterogeneous cases.

## Interpretation for the Paper

The MCAV observations validate the method as a useful signal, not as a finished count. Raw push totals are retained only as a diagnostic showing that actuation counts are not pedestrian counts. The current network application uses the matched pooled censored-Poisson multiplier of 2.165, with substantial uncertainty and a need for broader validation. The cycle plug-in multiplier of about 1.5 applies only if that cycle estimator is itself used.
