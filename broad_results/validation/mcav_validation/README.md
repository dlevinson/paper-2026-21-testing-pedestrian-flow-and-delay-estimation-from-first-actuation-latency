# Manual Crossing-Actuation Validation (MCAV)

This folder contains the normalized analysis of the Manual Crossing-Actuation
Validation (MCAV) dataset. It is independent field-validation evidence for
pedestrian-volume inference from first push-button actuation.

## Source

- Workbook: `Pedestrian Actuators Validation Project/Manual Crossing-Actuation Validation/11_Intersections_Data.xlsx`
- Observation period: around midday in August 2022; exact dates and clock times
  are unavailable.
- Coverage: 11 intersections, 14 crossing-direction cases, 50,635 retained
  seconds (14.07 hours), and 1,744 observed pedestrian arrivals.

The workbook records signal phase, pedestrian arrivals, actuator pushes,
compliant and non-compliant crossings, and presses not followed by a crossing.
The formula-driven `Comparison ` sheet is a partial summary; the analysis uses
the underlying second-by-second sheets. Initial rows labelled `W (Invalid)`
precede the first usable cycle anchors and are excluded. Some unused workbook
summaries double the raw actuator column; first-push detection uses presence
only and is unaffected.

## Reproduction

Run from the project root:

```sh
python3 broad_results/validation/mcav_validation/scripts/normalize_mcav_validation.py
```

Primary outputs:

- `mcav_cycle_level_validation.csv`
- `mcav_case_model_validation.csv`
- `mcav_model_comparison_summary.csv`
- `mcav_model_stability_summary.csv`
- `mcav_model_leave_one_out.csv`
- `mcav_model_plot_data.json`
- `mcav_compliance_scenario_by_case.csv`
- `mcav_compliance_scenario_summary.csv`
- `mcav_validation_data_dictionary.md`
- `mcav_model_comparison_note.md`

Earlier diagnostic outputs are also retained with the `mcav_` prefix.

## Principal results

- 14 direction cases and 492 observed restrictive intervals/cycles, 422 with a
  first observed push.
- 1,744 observed pedestrians and 513 manually coded actuator events.
- The pooled censored-Poisson estimator implies 805.6 unexpanded events.
- Count alpha is 2.202 as the unweighted case mean and 2.165 as the
  ratio-of-sums diagnostic.
- The 100%-signal-compliance replay gives 16.606 pedestrian-hours of delay.
- Delay alpha is 2.176 as the unweighted case mean and 2.133 as the
  ratio-of-sums diagnostic.

The network analysis uses the unweighted count and delay means. Ratio-of-sums,
cycle plug-in, raw-actuation, and universal-actuation results remain diagnostics
and are not substituted across estimator definitions.

## Provenance limits

The exact August dates, observation start/end clock times, and corresponding
controller logs are unavailable. These do not prevent validation of the
first-actuation estimator because the workbook directly observes pedestrian
arrivals, button behaviour, and signal state in the same field intervals.
