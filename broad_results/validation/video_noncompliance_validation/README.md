# Video-coded pedestrian peer validation

This folder applies the MCAV pooled-censored first-actuation method to the
video-coded data associated with *Pedestrian Non-Compliance at Signalised
Intersections in Sydney*. The video results are an independent peer test under
a different observation protocol and are not pooled with MCAV.

## Primary source and observation model

The primary analysis now uses the author-supplied upstream package dated
2026-07-20. For each of six site-period sessions it contains:

- a pedestrian table with physical leg, arrival time, crossing-start time, and
  binary actuator use;
- four directional `G`/`FR`/`R` signal timelines; and
- the processed single-stage master table used to verify realised waiting.

The 18 retained input files are under
`source/choy_final_data_20260720/`. Their SHA-256 hashes are checked by the
analysis and written to `video_upstream_source_manifest.csv`.

The upstream signal timelines resolve the two limitations of the earlier
public-table reconstruction. They identify every restrictive service
opportunity, including 855 cycles with no eligible actuation, and they identify
the physical leg directly, including Redfern/Pitt. Arrival and flashing-red
times are no longer recovered from shifted processed fields. One observation
assumption remains: `Accuator` records whether a pedestrian pressed, not the
press timestamp, so an actuator-positive pedestrian is assumed to press at
their recorded arrival.

Each analysis case is one session by one physical leg. The common session
window begins at zero and ends at the final timestamp in the simultaneous
directional signal streams. These recorded windows range from 3,421 to 3,803
seconds and cover every mapped pedestrian. One of the 2,004 source pedestrians
has no physical leg and is excluded, leaving 2,003 in 24 cases.

For each flashing-don't-walk onset, the earliest restrictive-phase actuator
user is the first event. A cycle with no such user contributes its complete
restrictive duration as right-censored exposure:

```
lambda = first-actuation cycles / total first-event or censoring exposure
base = lambda * recorded session duration
alpha_N = observed pedestrians / base
```

Only the first eligible actuation in a cycle enters the likelihood. Later
pedestrians and later actuator users remain in the observed person count but do
not create additional first events.

## Primary results

The 24 leg-sessions contain 2,003 mapped pedestrians and 1,462 restrictive
service opportunities: 607 with a first eligible actuation and 855 without one.
The unexpanded base is 937.323 events. Case count factors have mean 2.203,
range 1.422--3.213, and ratio of totals 2.137. Leave-one-leg-session-out
predictions total 2,067.4 pedestrians with 22.36% MAPE. Applying the MCAV mean
factor 2.202 predicts 2,064.4 pedestrians, 3.07% above the video count.

The exact signal replay classifies 372 arrivals on Walk, 367 during flashing
red, 1,262 during red, and two before the first known state. These totals
reproduce the processed public table. Of 799 actuator users, 758 arrive during
a restrictive indication and are eligible under the stated observation model.
The separate complete-event behavioural ratio is therefore 2,001 / 758 =
2.640; it is a diagnostic, not the first-actuation estimator.

Replaying every restrictive arrival to the exact next Walk gives 12.934 hours
of signal-only delay under 100% compliance. The first-actuation model supplies
6.626 unexpanded hours. Case delay factors have mean 2.233, range
1.156--3.751, and ratio of totals 1.952. Recorded realised restrictive waiting
is 8.522 hours; 666 crossings begin under a restrictive indication and avoid an
estimated 5.029 hours relative to the compliance scenario. Adding the measured
5.499-second median post-Walk start-up lag gives 15.422 hours.

## Reproduction and output status

Run from the project root:

```sh
python3 broad_results/validation/video_noncompliance_validation/scripts/estimate_video_upstream_peer.py
```

Primary outputs:

- `video_upstream_peer_cases.csv`
- `video_upstream_peer_cycles.csv`
- `video_upstream_peer_arrivals.csv`
- `video_upstream_peer_sessions.csv`
- `video_upstream_peer_summary.csv`
- `video_upstream_source_manifest.csv`

`estimate_video_alpha.py`, `estimate_video_pooled_censored.py`, and files named
`video_pooled_censored_*`, `video_cycle_plugin_reconstruction_*`, or
`video_delay_direct_summary.csv` are retained only as an audit trail of the
superseded public-table reconstruction. They are not manuscript inputs.
