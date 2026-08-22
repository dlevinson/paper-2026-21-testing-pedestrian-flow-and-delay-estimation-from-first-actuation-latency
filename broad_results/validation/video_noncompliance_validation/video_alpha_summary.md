# Video-coded actuator-use alpha summary

> **Status:** the count tables below are behavioural diagnostics. The phase-geometry delay block is a superseded wrap-around sensitivity, not the paper's 100%-compliance estimate. The paper uses the direct signal-only calculation in `video_latency_replay/scripts/decompose_video_errors.py` and the pooled-censored peer factors in `estimate_video_pooled_censored.py`.

An actuator-positive pedestrian is assumed to press at arrival. The primary denominator retains uses whose recorded arrival signal is flashing or solid red. The resulting values are complete-event behavioural expansions and are not estimator-matched first-actuation-latency factors. Three rows with missing arrival indication are excluded from the primary numerator.

Source codes such as `3AM` mean site 3 in the morning, not 03:00. The source paper identifies the observation windows as 08:00-09:00 and 12:00-13:00. The `prev_start_time` field is a video-relative previous crossing-start time and is not a wall-clock arrival timestamp.

| Site and observation time | Pedestrians | Restrictive arrivals | Eligible actuator users | Combined alpha |
|---|---:|---:|---:|---:|
| Redfern St / Pitt St, 08:00-09:00 | 442 | 358 | 151 | 2.927 |
| Redfern St / Pitt St, 12:00-13:00 | 354 | 279 | 105 | 3.362 |
| Campbell St / Riley St, 08:00-09:00 | 317 | 258 | 130 | 2.438 |
| Campbell St / Riley St, 12:00-13:00 | 366 | 292 | 133 | 2.737 |
| William Henry St / Harris St, 08:00-09:00 | 288 | 240 | 128 | 2.250 |
| William Henry St / Harris St, 12:00-13:00 | 237 | 202 | 111 | 2.135 |

The six session factors range from 2.135 to 3.362, with unweighted mean 2.642, median 2.588, and ratio-of-sums 2.640. Including actuator use recorded for green arrivals gives mean 2.507; restricting the analysis to single-stage pedestrians gives mean 2.537.

## Decomposition and compliance scenario

The aggregate combined factor decomposes exactly as

`2.640 = 1.228 x 2.149`,

where the first term accounts for known pedestrians arriving during Walk, and the second for restrictive-phase arrivals not recorded as actuator users. With universal actuator participation, the restrictive-population count factor is 1.000 and the all-arrival factor is therefore only this closed-period coverage term, 1.228.

For the superseded phase-geometry sensitivity, every restrictive-phase arrival is assigned the phase-geometry wait to the next estimated Walk onset. Walk onsets are the lower tails of compliant crossing-start clusters on each session/leg-distance phase clock. This gives 16.062 pedestrian-hours, or 28.90 seconds per pedestrian with known arrival indication. Cluster-gap and reference-cycle alternatives span 15.147-17.620 hours. Restrictive arrivals without a usable phase value receive the median reconstructed delay for their session/leg-distance group. Eligible actuator users account for 6.846 hours, giving a delay-weighted behavioural factor of 2.346. Under universal actuator participation this delay factor is 1.000.

The deposited phase variables are informative but imperfect. The source notebook's one-letter leg search maps east and west phase clocks to south, and at Redfern/Pitt one distance value represents more than one leg. The reported range therefore expresses phase-reconstruction sensitivity; it is not a sampling confidence interval.

## Group diagnostic

| Group code | Pedestrians | Restrictive arrivals | Eligible users | Actuation rate | Non-actuation factor |
|---|---:|---:|---:|---:|---:|
| Individual | 1540 | 1255 | 646 | 0.515 | 1.943 |
| Pair | 362 | 293 | 89 | 0.304 | 3.292 |
| Group of 3+ | 102 | 81 | 23 | 0.284 | 3.522 |

These group rows describe person-level actuator coding. They do not identify unique physical presses or group-arrival events, so they cannot by themselves supply a group-size multiplier for the first-actuation model.

## Cycle plug-in reconstruction sensitivity

The same cycle-level question used in MCAV can be reconstructed for eight approach-sessions at sites 4 and 5. For each actuator cycle, the base is `E_i / max(y_i, 0.5)`, where `y_i` is the reconstructed time from FDW onset to the first actuator user. The public export omits the next-FDW table, so `E_i` is inferred from observed FDW-onset gaps. The point estimate rounds the number of cycles in a long gap; floor and ceiling alternatives define the reported reconstruction range. Site 3 cannot be reconstructed because one exported distance combines two physical legs.

| Approach-session | Observed | Base (range) | Alpha | LOO predicted | Absolute percentage error |
|---|---:|---:|---:|---:|---:|
| Campbell St / Riley St, 08:00-09:00, distance 9.9 m | 94 | 92.8 (69.9-97.9) | 1.013 | 75.0 | 20.2% |
| Campbell St / Riley St, 08:00-09:00, distance 12.8 m | 76 | 113.3 (85.9-129.5) | 0.670 | 97.2 | 27.9% |
| Campbell St / Riley St, 12:00-13:00, distance 9.9 m | 76 | 91.2 (68.3-95.9) | 0.833 | 76.1 | 0.2% |
| Campbell St / Riley St, 12:00-13:00, distance 12.8 m | 96 | 73.6 (57.9-79.3) | 1.305 | 56.4 | 41.2% |
| William Henry St / Harris St, 08:00-09:00, distance 15.1 m | 41 | 71.5 (63.2-83.1) | 0.574 | 62.3 | 51.9% |
| William Henry St / Harris St, 08:00-09:00, distance 15.9 m | 122 | 328.6 (292.2-378.5) | 0.371 | 295.9 | 142.5% |
| William Henry St / Harris St, 12:00-13:00, distance 15.1 m | 26 | 35.9 (27.0-42.3) | 0.724 | 30.5 | 17.4% |
| William Henry St / Harris St, 12:00-13:00, distance 15.9 m | 105 | 88.7 (58.7-89.6) | 1.184 | 69.6 | 33.7% |

Across these partial cases, the observed count is 636, the uncalibrated base is 895.7 (723.1-996.1), and the ratio-of-sums alpha is 0.710 (0.638-0.879). The eight case alphas have mean 0.834, range 0.371-1.305. Leave-one-case-out calibration predicts 763.1 pedestrians with 41.9% MAPE. The weak and unstable result is evidence that the deposited timestamps do not support an exact second validation; it is not pooled with MCAV.
