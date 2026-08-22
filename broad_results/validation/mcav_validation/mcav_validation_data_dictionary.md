# Manual Crossing-Actuation Validation Data Dictionary

This folder normalizes the Manual Crossing-Actuation Validation (MCAV) workbook for independent validation of pedestrian-volume inference from push-button actuation. The source workbook is:

`Pedestrian Actuators Validation Project/Manual Crossing-Actuation Validation/11_Intersections_Data.xlsx`

The normalizer is:

`scripts/normalize_mcav_validation.py`

Run it from the repository root with a Python environment that includes `openpyxl`:

`python3 broad_results/validation/mcav_validation/scripts/normalize_mcav_validation.py`

## Main Outputs

- `mcav_cycle_level_validation.csv`: one row per observed non-walk interval/cycle.
- `mcav_case_model_validation.csv`: one row per observed intersection/direction case.
- `mcav_model_comparison_summary.csv`: aggregate performance of candidate estimators.
- `mcav_model_stability_summary.csv`: aggregate-ratio, leave-one-out, and bootstrap stability for the pooled censored-Poisson and two cycle plug-in models.
- `mcav_model_leave_one_out.csv`: leave-one-case-out ratios.
- `mcav_model_plot_data.json`: compact data for visualization.
- `mcav_compliance_scenario_by_case.csv`: case-level universal signal- and actuator-compliance counterfactuals and alpha decomposition.
- `mcav_compliance_scenario_summary.csv`: pooled and unweighted-case scenario summaries.

## Cycle-Level Fields

- `case`: workbook case name, including direction suffix where the source sheet contains two observed directions.
- `source_sheet`, `comparison_row`, `source_total_row`: workbook traceability.
- `data_start_row`, `data_end_row`: raw second-by-second block used for the case.
- `cycle_number`: sequential non-walk interval within the case.
- `nonwalk_start_*`: first FDW/SDW row and row-order second for the interval.
- `walk_start_*`: first following W row, if observed.
- `next_nonwalk_start_*`: first row/second of the next non-walk interval, if observed.
- `first_push_*`: first actuator-count row/second inside the non-walk interval, if observed.
- `first_push_wait_seconds`: row-order seconds from FDW/SDW start to first observed push.
- `effective_wait_seconds`: `max(first_push_wait_seconds, 0.5)` for rate calculation; blank for no-push cycles.
- `nonwalk_exposure_seconds`: FDW/SDW start to following W, or to next interval/end if no W is observed.
- `full_cycle_exposure_seconds`: FDW/SDW start to the next FDW/SDW start, or to the observation end.
- `observed_ped_arrivals_cycle`: observed pedestrian arrivals assigned to the cycle.
- `observed_ped_arrivals_nonwalk`: observed pedestrian arrivals during the non-walk part only.
- `actuator_count_raw_cycle`: raw actuator-coded entries in the cycle.
- `legal_*`, `illegal_*`, `pushbutton_no_walk_cycle`: observed behavioural count components.
- `cycle_plugin_predicted_nonwalk_only`: `nonwalk_exposure_seconds / effective_wait_seconds` for first-push cycles, otherwise 0.
- `cycle_plugin_predicted_full_cycle`: `full_cycle_exposure_seconds / effective_wait_seconds` for first-push cycles, otherwise 0.
- `poisson_censored_implied_count_all_time`: case-level implied count from the pooled first-push Poisson model with no-push cycles contributing right-censored full observed exposure. This is the model matched to the SCATS network estimator.

## Model Interpretation

The cycle plug-in model follows the first-arrival interpretation: if the first observed push is `t` seconds after FDW/SDW starts, then the local Poisson arrival-rate estimate is `1/t` arrivals per second. Expected arrivals over an exposure window `E` are `E/t`. This includes expected later arrivals after the first push. It remains a diagnostic because the network estimator pools uncensored latencies and censored exposure within movement-hours. The paper calibrates that pooled estimator with the matched pooled MCAV result, not with the lower-error cycle plug-in result.

## Compliance-Scenario Fields

- `full_compliance_delay_seconds`: sum, over every observed restrictive-phase arrival with a following Walk, of people arriving in a one-second row multiplied by seconds remaining to that Walk.
- `delay_uncovered_restrictive_arrivals`: arrivals in truncated observation-end intervals without a following Walk; four of 1,492 restrictive-phase arrivals are uncovered.
- `full_actuation_implied_count`: count from the same pooled censored-Poisson estimator after replacing the recorded first push with the first observed pedestrian arrival in each closed interval.
- `count_alpha_full_actuation`: observed pedestrians divided by `full_actuation_implied_count`. This need not equal one because batching, temporal heterogeneity, observation boundaries, and model form remain after non-actuation is removed.
- `missing_actuation_multiplier`: counterfactual full-actuation implied count divided by the implied count from recorded actuation.
- `batch_factor_people_per_occupied_second`: observed people divided by one-second rows containing at least one arrival. It is a resolution-dependent batching diagnostic, not a directly observed group-size parameter.
- `remaining_timing_model_factor`: occupied arrival seconds divided by the full-actuation implied count.
- `delay_alpha_observed_actuation`: observed 100%-signal-compliance delay divided by the unexpanded actuation-conditioned delay from the SCATS formula using recorded first pushes.
- `delay_alpha_full_actuation`: the same delay ratio after first pushes are moved to first observed pedestrian arrivals.
