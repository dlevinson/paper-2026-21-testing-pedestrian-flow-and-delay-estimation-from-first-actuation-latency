# MCAV Cycle-Level First-Actuation Plug-In Model

Source:

- `mcav_cycle_first_actuation_plugin_model.csv`

This note tests the intuitive first-arrival interpretation:

`lambda_i = 1 / t_i`

where `t_i` is the time from FDW/non-walk start to the first observed button push in cycle `i`.

For example, if the first actuation occurs 15 seconds after FDW begins, the plug-in arrival-rate estimate is:

`lambda = 1 / 15 seconds = 4 pedestrians per minute`

The expected number of pedestrians in an exposure window of length `E_i` is then:

`N_i = E_i / t_i`

This includes expected later arrivals after the first actuation, because Poisson increments after the first arrival are independent.

## Aggregate Results

Across 14 direction cases:

| Quantity | Count | Share of actual |
|---|---:|---:|
| Actual observed pedestrians | 1,744.0 | 1.000 |
| Cycle plug-in, non-walk exposure only | 1,067.7 | 0.612 |
| Cycle plug-in, full observed cycle exposure | 1,164.1 | 0.667 |

Corresponding calibration multipliers:

| Model | Actual / implied |
|---|---:|
| Cycle plug-in, non-walk exposure only | 1.63 |
| Cycle plug-in, full observed cycle exposure | 1.50 |

Mean absolute relative error:

| Model | MARE |
|---|---:|
| Cycle plug-in, non-walk exposure only | 37.0% |
| Cycle plug-in, full observed cycle exposure | 31.5% |

## Interpretation

The cycle-level first-actuation model is closer to the user's intended interpretation than the pooled censored model. It still undercounts actual pedestrians, but less severely. The remaining gap is expected because the first actuation is a first observed push-button event, not necessarily the first pedestrian arrival, and many observed pedestrians do not press the button.

The MCAV workbook also records violations and non-button behaviour:

- legal pedestrians with push button: 479;
- legal pedestrians without push button: 1,188;
- illegal pedestrians with push button: 20;
- illegal pedestrians without push button: 43;
- pedestrians who pushed but did not walk: 14.

Thus the workbook records 63 illegal crossings out of 1,744 observed pedestrian arrivals, or about 3.6%. If the 14 push-but-did-not-walk observations are excluded from crossings, the illegal share is 63 / 1,730 = 3.6%.
