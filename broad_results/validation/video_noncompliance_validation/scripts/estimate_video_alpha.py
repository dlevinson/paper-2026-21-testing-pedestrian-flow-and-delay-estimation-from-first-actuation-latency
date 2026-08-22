#!/usr/bin/env python3
"""Estimate video-coded actuator-use expansion and compliance-delay factors.

The public pedestrian-noncompliance table records whether each pedestrian used
an actuator but not the physical press timestamp.  Following the stated
measurement assumption, an observed actuator use is placed at pedestrian
arrival.  A use is eligible for the comparison when the recorded arrival
signal is flashing red or solid red, matching the closed interval in which the
first-actuation model samples demand.

These factors are complete-event behavioural expansions, not reconstructed
first-actuation-latency factors.  For the full-compliance delay scenario, Walk
onsets are estimated from clusters of compliant crossing starts on the
deposited cycle-relative signal clock.  This replaces the earlier behavioural
k-nearest-neighbour imputation with a signal-geometry calculation.
"""

from __future__ import annotations

import csv
import hashlib
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
VALIDATION_DIR = ROOT / "broad_results" / "validation" / "video_noncompliance_validation"
SOURCE_IN = VALIDATION_DIR / "source" / "REGRESSION_SINGLE_HARD_COMPLIANCE.csv"
CASE_OUT = VALIDATION_DIR / "video_alpha_case_distribution.csv"
SUMMARY_OUT = VALIDATION_DIR / "video_alpha_summary.csv"
NOTE_OUT = VALIDATION_DIR / "video_alpha_summary.md"
COMPLIANCE_CASE_OUT = VALIDATION_DIR / "video_compliance_scenario_by_session.csv"
COMPLIANCE_SUMMARY_OUT = VALIDATION_DIR / "video_compliance_scenario_summary.csv"
GROUP_OUT = VALIDATION_DIR / "video_group_actuation_decomposition.csv"
PHASE_OUT = VALIDATION_DIR / "video_phase_geometry.csv"
FIRST_ACTUATION_CASE_OUT = VALIDATION_DIR / "video_cycle_plugin_reconstruction_cases.csv"
FIRST_ACTUATION_CYCLE_OUT = VALIDATION_DIR / "video_cycle_plugin_reconstruction_cycles.csv"
FIRST_ACTUATION_SUMMARY_OUT = (
    VALIDATION_DIR / "video_cycle_plugin_reconstruction_summary.csv"
)

EXPECTED_SHA256 = "7281d4e7215cc1c71c2372a19a2c02a84a1b7108c8c59fc02516f42228c9cee7"
EXPECTED_ROWS = 2_004
EXPECTED_ACTUATOR_USERS = 799
EXPECTED_ELIGIBLE_ACTUATOR_USERS = 758
RESTRICTIVE_SIGNALS = {1, 2}  # 1=flashing red, 2=solid red in the public file
SITE_NAMES = {
    "3": "Redfern St / Pitt St",
    "4": "Campbell St / Riley St",
    "5": "William Henry St / Harris St",
}
PERIOD_TIMES = {"AM": "08:00-09:00", "PM": "12:00-13:00"}
GROUP_NAMES = {0: "Individual", 1: "Pair", 2: "Group of 3+"}
PHASE_CLUSTER_GAP_SECONDS = 15.0
PHASE_CLUSTER_GAP_SENSITIVITIES = (10.0, 25.0)
PHASE_CLUSTER_MINIMUM_SHARE = 0.04
PHASE_CLUSTER_ONSET_QUANTILE = 0.05
NOMINAL_SESSION_SECONDS = 3_600.0
FDW_ONSET_CLUSTER_TOLERANCE_SECONDS = 1.0

# The public export omits the physical leg.  At sites 4 and 5, leg distance is
# unique and the stored previous-pedestrian fields therefore recover the
# within-leg row sequence exactly.  The source notebook's one-letter phase
# lookup maps east and west to the south clock; these two distances per site are
# the clocks that retain the required FR -> R -> Walk order in both sessions.
# Site 3 is excluded because each distance combines two physical legs.
AUDITABLE_FIRST_ACTUATION_DISTANCES = {
    "4": {9.90, 12.80},
    "5": {15.10, 15.90},
}
MINIMUM_SIGNAL_ORDER_SCORE = 0.80


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            formatted = {}
            for field in fields:
                value = row.get(field, "")
                formatted[field] = f"{value:.9f}" if isinstance(value, float) else value
            writer.writerow(formatted)


def numeric(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def linear_quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def session_key(session: str) -> tuple[int, int]:
    return int(session[0]), 0 if session.endswith("AM") else 1


def is_actuator_user(row: dict) -> bool:
    return numeric(row.get("Accuator")) == 1


def arrival_signal(row: dict) -> int | None:
    value = numeric(row.get("signal_at_arrival"))
    return int(value) if value is not None else None


def is_single_stage(row: dict) -> bool:
    return numeric(row.get("two_stage_crossing")) == 0


def eligible_actuator_user(row: dict) -> bool:
    return is_actuator_user(row) and arrival_signal(row) in RESTRICTIVE_SIGNALS


def case_row(session: str, rows: list[dict]) -> dict:
    all_users = sum(is_actuator_user(row) for row in rows)
    eligible_users = sum(eligible_actuator_user(row) for row in rows)
    green_users = sum(
        is_actuator_user(row) and arrival_signal(row) == 0 for row in rows
    )
    missing_signal_users = sum(
        is_actuator_user(row) and arrival_signal(row) is None for row in rows
    )
    single_rows = [row for row in rows if is_single_stage(row)]
    single_users = sum(is_actuator_user(row) for row in single_rows)
    single_eligible_users = sum(eligible_actuator_user(row) for row in single_rows)
    observed = len(rows)
    single_observed = len(single_rows)
    restrictive_arrivals = sum(
        arrival_signal(row) in RESTRICTIVE_SIGNALS for row in rows
    )
    walk_arrivals = sum(arrival_signal(row) == 0 for row in rows)
    missing_arrival_signal = sum(arrival_signal(row) is None for row in rows)
    known_signal_pedestrians = observed - missing_arrival_signal
    period_code = session[1:]
    return {
        "case": session,
        "site_code": session[0],
        "site_name": SITE_NAMES[session[0]],
        "period_code": period_code,
        "observation_time": PERIOD_TIMES[period_code],
        "case_label": f"{SITE_NAMES[session[0]]}, {PERIOD_TIMES[period_code]}",
        "observed_pedestrians": observed,
        "known_arrival_signal_pedestrians": known_signal_pedestrians,
        "restrictive_arrivals": restrictive_arrivals,
        "walk_arrivals": walk_arrivals,
        "missing_arrival_signal": missing_arrival_signal,
        "actuator_users_all": all_users,
        "eligible_actuator_users": eligible_users,
        "green_arrival_actuator_users": green_users,
        "missing_arrival_signal_actuator_users": missing_signal_users,
        "alpha_video": known_signal_pedestrians / eligible_users,
        "alpha_video_including_missing_signal": observed / eligible_users,
        "alpha_walk_exposure_full_actuation": known_signal_pedestrians / restrictive_arrivals,
        "nonactuation_factor_restrictive": restrictive_arrivals / eligible_users,
        "alpha_all_actuator_users": observed / all_users,
        "single_stage_pedestrians": single_observed,
        "single_stage_actuator_users_all": single_users,
        "single_stage_eligible_actuator_users": single_eligible_users,
        "alpha_video_single_stage": single_observed / single_eligible_users,
    }


def start_signal(row: dict) -> int | None:
    value = numeric(row.get("signal_at_start"))
    return int(value) if value is not None else None


def is_restrictive_arrival(row: dict) -> bool:
    return arrival_signal(row) in RESTRICTIVE_SIGNALS


def recorded_wait(row: dict) -> float | None:
    return numeric(row.get("wait_time_s"))


def phase_elapsed_at_arrival(row: dict) -> float | None:
    return numeric(row.get("time_bw_arrival_and_FR_hard"))


def phase_elapsed_at_start(row: dict) -> float | None:
    return numeric(row.get("time_bw_start_and_FR_hard"))


def leg_distance(row: dict) -> float | None:
    return numeric(row.get("leg_distance"))


def phase_group_key(row: dict) -> tuple[str, float | None]:
    return row["Session"], leg_distance(row)


def phase_geometry(
    rows: list[dict], cluster_gap_seconds: float, cycle_method: str
) -> dict[tuple[str, float | None], dict]:
    """Estimate Walk-onset modes on each deposited phase clock.

    The source notebook measures event times from the most recent flashing-red
    onset.  Restrictive arrivals that subsequently start on Walk therefore
    reveal Walk-onset clusters.  The lower tail of each retained cluster is an
    onset estimate; the reference-clock span supplies wrap-around geometry.

    The source notebook maps east and west phase clocks to south because it
    searches for single direction letters inside the leg label.  Consequently
    this is a phase-cluster estimate, not a claim that the original transition
    table has been recovered exactly.
    """

    grouped: dict[tuple[str, float | None], list[dict]] = defaultdict(list)
    by_session: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[phase_group_key(row)].append(row)
        by_session[row["Session"]].append(row)

    session_cycle: dict[str, float] = {}
    if cycle_method == "session_max":
        for session, session_rows in by_session.items():
            elapsed = [
                value
                for row in session_rows
                for value in (
                    phase_elapsed_at_arrival(row),
                    phase_elapsed_at_start(row),
                )
                if value is not None
            ]
            session_cycle[session] = math.ceil((max(elapsed) + 0.01) / 5.0) * 5.0

    models = {}
    for key, group_rows in grouped.items():
        compliant_starts = sorted(
            phase_elapsed_at_start(row)
            for row in group_rows
            if is_restrictive_arrival(row)
            and start_signal(row) == 0
            and phase_elapsed_at_start(row) is not None
        )
        elapsed = [
            value
            for row in group_rows
            for value in (phase_elapsed_at_arrival(row), phase_elapsed_at_start(row))
            if value is not None
        ]
        if not compliant_starts or not elapsed:
            models[key] = {
                "walk_onsets": [],
                "cycle_span_seconds": None,
                "compliant_start_count": len(compliant_starts),
                "retained_cluster_count": 0,
            }
            continue
        clusters = [[compliant_starts[0]]]
        for value in compliant_starts[1:]:
            if value - clusters[-1][-1] > cluster_gap_seconds:
                clusters.append([value])
            else:
                clusters[-1].append(value)
        minimum_cluster = max(
            2, math.ceil(len(compliant_starts) * PHASE_CLUSTER_MINIMUM_SHARE)
        )
        retained = [cluster for cluster in clusters if len(cluster) >= minimum_cluster]
        onsets = [
            linear_quantile(cluster, PHASE_CLUSTER_ONSET_QUANTILE)
            for cluster in retained
        ]
        if cycle_method == "session_max":
            cycle_span = session_cycle[key[0]]
        elif cycle_method == "group_robust":
            cycle_span = math.ceil((linear_quantile(elapsed, 0.995) + 1.0) / 5.0) * 5.0
        else:
            raise ValueError(f"Unknown cycle method: {cycle_method}")
        models[key] = {
            "walk_onsets": onsets,
            "cycle_span_seconds": cycle_span,
            "compliant_start_count": len(compliant_starts),
            "retained_cluster_count": len(retained),
        }
    return models


def compliance_delays(
    rows: list[dict], cluster_gap_seconds: float, cycle_method: str
) -> tuple[dict[int, float], dict[int, str], dict]:
    models = phase_geometry(rows, cluster_gap_seconds, cycle_method)
    delays: dict[int, float] = {}
    methods: dict[int, str] = {}
    resolved_by_group: dict[tuple[str, float | None], list[float]] = defaultdict(list)

    for row in rows:
        if arrival_signal(row) is None:
            methods[id(row)] = "excluded_missing_arrival_signal"
            continue
        if not is_restrictive_arrival(row):
            delays[id(row)] = 0.0
            methods[id(row)] = "arrival_on_walk"
            continue
        elapsed = phase_elapsed_at_arrival(row)
        model = models[phase_group_key(row)]
        onsets = model["walk_onsets"]
        cycle_span = model["cycle_span_seconds"]
        if elapsed is None or not onsets or cycle_span is None:
            methods[id(row)] = "aggregate_fallback_pending"
            continue
        candidates = [onset - elapsed for onset in onsets if onset >= elapsed]
        candidates.append(onsets[0] + cycle_span - elapsed)
        feasible = [value for value in candidates if value >= 0]
        if not feasible:
            methods[id(row)] = "aggregate_fallback_pending"
            continue
        delay = min(feasible)
        delays[id(row)] = delay
        methods[id(row)] = "phase_geometry"
        resolved_by_group[phase_group_key(row)].append(delay)

    resolved_by_session: dict[str, list[float]] = defaultdict(list)
    for (session, _), values in resolved_by_group.items():
        resolved_by_session[session].extend(values)
    all_resolved = [value for values in resolved_by_group.values() for value in values]
    for row in rows:
        if methods.get(id(row)) != "aggregate_fallback_pending":
            continue
        group_values = resolved_by_group.get(phase_group_key(row), [])
        session_values = resolved_by_session.get(row["Session"], [])
        donor_values = group_values or session_values or all_resolved
        if not donor_values:
            raise RuntimeError(f"No phase-delay fallback for {row['Session']}")
        delays[id(row)] = statistics.median(donor_values)
        methods[id(row)] = "session_leg_median_fallback" if group_values else "session_median_fallback"
    return delays, methods, models


def compliance_case_row(
    session: str,
    rows: list[dict],
    point_delays: dict[int, float],
    point_methods: dict[int, str],
    sensitivity_delays: dict[int, dict[int, float]],
) -> dict:
    observed = len(rows)
    restrictive = sum(is_restrictive_arrival(row) for row in rows)
    walk = sum(arrival_signal(row) == 0 for row in rows)
    missing_arrival_signal = sum(arrival_signal(row) is None for row in rows)
    known_signal_pedestrians = observed - missing_arrival_signal
    eligible_users = sum(eligible_actuator_user(row) for row in rows)
    fallback_arrivals = sum(
        point_methods.get(id(row), "").endswith("fallback") for row in rows
    )
    full_delay = sum(point_delays.get(id(row), 0.0) for row in rows)
    eligible_delay = sum(
        point_delays[id(row)] for row in rows if eligible_actuator_user(row)
    )
    observed_restrictive_wait = sum(
        recorded_wait(row) or 0.0 for row in rows if is_restrictive_arrival(row)
    )
    sensitivity_totals = [
        sum(delay_map.get(id(row), 0.0) for row in rows)
        for delay_map in sensitivity_delays.values()
    ]
    period_code = session[1:]
    return {
        "source_session_code": session,
        "site_code": session[0],
        "site_name": SITE_NAMES[session[0]],
        "period_code": period_code,
        "observation_time": PERIOD_TIMES[period_code],
        "case_label": f"{SITE_NAMES[session[0]]}, {PERIOD_TIMES[period_code]}",
        "observed_pedestrians": observed,
        "known_arrival_signal_pedestrians": known_signal_pedestrians,
        "restrictive_arrivals": restrictive,
        "walk_arrivals": walk,
        "missing_arrival_signal": missing_arrival_signal,
        "eligible_actuator_users": eligible_users,
        "count_alpha_observed_combined": known_signal_pedestrians / eligible_users,
        "count_alpha_observed_combined_including_missing_signal": observed / eligible_users,
        "count_alpha_walk_exposure_full_actuation": known_signal_pedestrians / restrictive,
        "nonactuation_factor_restrictive": restrictive / eligible_users,
        "decomposition_product_check": (known_signal_pedestrians / restrictive)
        * (restrictive / eligible_users),
        "observed_realised_wait_restrictive_seconds": observed_restrictive_wait,
        "full_signal_compliance_delay_seconds": full_delay,
        "full_signal_compliance_delay_sensitivity_min": min(sensitivity_totals),
        "full_signal_compliance_delay_sensitivity_max": max(sensitivity_totals),
        "average_full_signal_compliance_delay_all_pedestrians_seconds": (
            full_delay / known_signal_pedestrians
        ),
        "average_full_signal_compliance_delay_restrictive_seconds": (
            full_delay / restrictive
        ),
        "eligible_actuator_user_compliance_delay_seconds": eligible_delay,
        "delay_alpha_observed_actuation": full_delay / eligible_delay,
        "delay_alpha_full_actuation": 1.0,
        "phase_geometry_arrivals": sum(
            point_methods.get(id(row)) == "phase_geometry" for row in rows
        ),
        "aggregate_fallback_restrictive_arrivals": fallback_arrivals,
    }


def group_decomposition_rows(rows: list[dict]) -> list[dict]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        group_value = numeric(row.get("Group"))
        grouped[int(group_value) if group_value is not None else -1].append(row)
    output = []
    for group_code in sorted(grouped):
        group_rows = grouped[group_code]
        restrictive = sum(is_restrictive_arrival(row) for row in group_rows)
        eligible = sum(eligible_actuator_user(row) for row in group_rows)
        output.append(
            {
                "group_code": group_code,
                "group_label": GROUP_NAMES.get(group_code, "Missing"),
                "pedestrians": len(group_rows),
                "pedestrian_share": len(group_rows) / len(rows),
                "restrictive_arrivals": restrictive,
                "eligible_actuator_users": eligible,
                "actuation_rate_among_restrictive_arrivals": eligible / restrictive,
                "nonactuation_factor_restrictive": restrictive / eligible,
                "combined_people_per_eligible_actuator_user": len(group_rows) / eligible,
            }
        )
    return output


def clock_seconds(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.strptime(value, "%H:%M:%S")
    except ValueError:
        return None
    return float(parsed.hour * 3600 + parsed.minute * 60 + parsed.second)


def signal_order_score(rows: list[dict]) -> float:
    """Best FR -> R -> Walk classification accuracy on the phase clock."""

    observations = sorted(
        (
            phase_elapsed_at_arrival(row),
            arrival_signal(row),
        )
        for row in rows
        if phase_elapsed_at_arrival(row) is not None
        and arrival_signal(row) is not None
    )
    labels = [label for _, label in observations]
    count = len(labels)
    if count == 0:
        return 0.0
    prefix = {label: [0] * (count + 1) for label in (0, 1, 2)}
    for index, value in enumerate(labels, start=1):
        for label in prefix:
            prefix[label][index] = prefix[label][index - 1] + (value == label)
    best = 0
    for first_end in range(count + 1):
        first_correct = prefix[1][first_end]
        for second_end in range(first_end, count + 1):
            correct = (
                first_correct
                + prefix[2][second_end]
                - prefix[2][first_end]
                + prefix[0][count]
                - prefix[0][second_end]
            )
            best = max(best, correct)
    return best / count


def first_actuation_latency_analysis(
    rows: list[dict], point_delays: dict[int, float]
) -> tuple[list[dict], list[dict], list[dict]]:
    """Reconstruct the cycle plug-in estimator where the export permits it.

    Actuation is placed at pedestrian arrival.  In the deposited file, each
    row's own crossing-start time was dropped but the next row on the same leg
    retains it as ``prev_start_time``.  Where distance uniquely identifies a
    leg, shifting that field backward therefore recovers the current start;
    arrival follows by subtracting ``wait_time_s``.  The source phase elapsed
    value identifies the FDW onset and the earliest actuator user within each
    onset cluster.

    The public export does not retain the next-FDW transition table.  Exposure
    therefore has to be reconstructed from gaps between distinct observed FDW
    onsets.  A robust short-gap median supplies the typical cycle.  Long gaps
    are divided by the rounded number of cycles for the point estimate, and by
    the ceiling/floor counts for a reconstruction range.  These outputs are a
    sensitivity analysis, not a second exact validation.
    """

    grouped: dict[tuple[str, float], list[dict]] = defaultdict(list)
    for row in rows:
        distance = leg_distance(row)
        if distance is not None:
            grouped[(row["Session"], round(distance, 2))].append(row)

    cases: list[dict] = []
    cycles: list[dict] = []
    for (session, distance), group_rows in sorted(
        grouped.items(), key=lambda item: (session_key(item[0][0]), item[0][1])
    ):
        selected = AUDITABLE_FIRST_ACTUATION_DISTANCES.get(session[0], set())
        if distance not in selected:
            continue

        order_score = signal_order_score(group_rows)
        if order_score < MINIMUM_SIGNAL_ORDER_SCORE:
            raise RuntimeError(
                f"Phase clock failed signal-order audit for {session}, {distance}: "
                f"{order_score:.3f}"
            )

        shift_checks = 0
        shift_matches = 0
        reconstructed_all = []
        for index, row in enumerate(group_rows[:-1]):
            next_row = group_rows[index + 1]
            current_compliance = numeric(row.get("hard_compliance"))
            next_previous_compliance = numeric(next_row.get("prev_hard_compliance"))
            if current_compliance is not None and next_previous_compliance is not None:
                shift_checks += 1
                shift_matches += current_compliance == next_previous_compliance

            start_seconds = clock_seconds(next_row.get("prev_start_time"))
            wait_seconds = recorded_wait(row)
            elapsed_seconds = phase_elapsed_at_arrival(row)
            if (
                start_seconds is None
                or wait_seconds is None
                or elapsed_seconds is None
            ):
                continue
            arrival_seconds = start_seconds - wait_seconds
            reconstructed_all.append(
                {
                    "row": row,
                    "arrival_seconds": arrival_seconds,
                    "fdw_onset_seconds": arrival_seconds - elapsed_seconds,
                    "latency_seconds": elapsed_seconds,
                    "eligible_actuator_user": eligible_actuator_user(row),
                }
            )

        shift_match_rate = shift_matches / shift_checks if shift_checks else 0.0
        if shift_match_rate != 1.0:
            raise RuntimeError(
                f"Previous-row timestamp reconstruction failed for {session}, "
                f"{distance}: {shift_match_rate:.3f}"
            )

        reconstructed_all.sort(key=lambda item: item["fdw_onset_seconds"])
        onset_clusters: list[list[dict]] = []
        for item in reconstructed_all:
            if (
                not onset_clusters
                or item["fdw_onset_seconds"]
                - onset_clusters[-1][-1]["fdw_onset_seconds"]
                > FDW_ONSET_CLUSTER_TOLERANCE_SECONDS
            ):
                onset_clusters.append([item])
            else:
                onset_clusters[-1].append(item)

        cluster_onsets = [
            statistics.fmean(item["fdw_onset_seconds"] for item in cluster)
            for cluster in onset_clusters
        ]
        onset_gaps = [
            later - earlier
            for earlier, later in zip(cluster_onsets, cluster_onsets[1:])
            if later - earlier >= 20.0
        ]
        if not onset_gaps:
            raise RuntimeError(f"No usable FDW gaps for {session}, {distance}")
        ordered_gaps = sorted(onset_gaps)
        short_half = ordered_gaps[: max(1, math.ceil(len(ordered_gaps) / 2))]
        typical_cycle = statistics.median(short_half)

        def exposure(gap: float, divisor_method: str) -> tuple[float, int]:
            ratio = max(gap / typical_cycle, 1.0)
            if divisor_method == "floor":
                divisor = max(1, math.floor(ratio + 1e-9))
            elif divisor_method == "ceil":
                divisor = max(1, math.ceil(ratio - 1e-9))
            else:
                divisor = max(1, math.floor(ratio + 0.5))
            return gap / divisor, divisor

        actuator_clusters = []
        for cluster_index, cluster in enumerate(onset_clusters):
            actuator_items = [
                item for item in cluster if item["eligible_actuator_user"]
            ]
            if actuator_items:
                actuator_clusters.append(
                    (
                        cluster_index,
                        cluster,
                        min(actuator_items, key=lambda item: item["latency_seconds"]),
                    )
                )

        first_items = [item for _, _, item in actuator_clusters]
        latency_sum = sum(max(item["latency_seconds"], 0.5) for item in first_items)
        if not first_items or latency_sum <= 0:
            raise RuntimeError(f"No usable first actuations for {session}, {distance}")
        observed = len(group_rows)
        observed_compliance_delay = sum(
            point_delays.get(id(row), 0.0) for row in group_rows
        )
        base_count = 0.0
        base_count_low = 0.0
        base_count_high = 0.0
        unexpanded_delay = 0.0
        for output_cycle_index, (cluster_index, cluster, first) in enumerate(
            actuator_clusters, start=1
        ):
            if cluster_index + 1 < len(cluster_onsets):
                gap = cluster_onsets[cluster_index + 1] - cluster_onsets[cluster_index]
            else:
                gap = typical_cycle
            exposure_point, cycles_point = exposure(gap, "round")
            exposure_low, cycles_ceil = exposure(gap, "ceil")
            exposure_high, cycles_floor = exposure(gap, "floor")
            latency = max(first["latency_seconds"], 0.5)
            rate_per_second = 1.0 / latency
            count_point = exposure_point * rate_per_second
            count_low = exposure_low * rate_per_second
            count_high = exposure_high * rate_per_second
            base_count += count_point
            base_count_low += min(count_low, count_high)
            base_count_high += max(count_low, count_high)
            remaining_wait = point_delays.get(id(first["row"]), 0.0)
            contribution = remaining_wait + rate_per_second * remaining_wait**2 / 2
            unexpanded_delay += contribution
            cycles.append(
                {
                    "source_session_code": session,
                    "site_code": session[0],
                    "site_name": SITE_NAMES[session[0]],
                    "period_code": session[1:],
                    "observation_time": PERIOD_TIMES[session[1:]],
                    "leg_distance": distance,
                    "cycle_index": output_cycle_index,
                    "reconstructed_fdw_onset_seconds": statistics.fmean(
                        item["fdw_onset_seconds"] for item in cluster
                    ),
                    "pedestrians_reconstructed_in_cycle": len(cluster),
                    "eligible_actuator_users_in_cycle": sum(
                        item["eligible_actuator_user"] for item in cluster
                    ),
                    "first_actuation_latency_seconds": first["latency_seconds"],
                    "effective_first_actuation_latency_seconds": latency,
                    "first_actuation_arrival_seconds": first["arrival_seconds"],
                    "next_observed_fdw_gap_seconds": gap,
                    "typical_cycle_seconds": typical_cycle,
                    "cycles_in_gap_point_round": cycles_point,
                    "cycles_in_gap_low_exposure_ceil": cycles_ceil,
                    "cycles_in_gap_high_exposure_floor": cycles_floor,
                    "cycle_exposure_point_seconds": exposure_point,
                    "cycle_exposure_low_seconds": min(exposure_low, exposure_high),
                    "cycle_exposure_high_seconds": max(exposure_low, exposure_high),
                    "cycle_plugin_implied_count": count_point,
                    "cycle_plugin_implied_count_low": min(count_low, count_high),
                    "cycle_plugin_implied_count_high": max(count_low, count_high),
                    "first_actuation_to_walk_seconds": remaining_wait,
                    "unexpanded_delay_contribution_seconds": contribution,
                }
            )

        alpha_delay = (
            observed_compliance_delay / unexpanded_delay
            if unexpanded_delay > 0
            else math.nan
        )
        cases.append(
            {
                "source_session_code": session,
                "site_code": session[0],
                "site_name": SITE_NAMES[session[0]],
                "period_code": session[1:],
                "observation_time": PERIOD_TIMES[session[1:]],
                "leg_distance": distance,
                "case_label": (
                    f"{SITE_NAMES[session[0]]}, {PERIOD_TIMES[session[1:]]}, "
                    f"distance {distance:g} m"
                ),
                "nominal_observation_seconds": NOMINAL_SESSION_SECONDS,
                "observed_pedestrians": observed,
                "reconstructed_timestamp_pedestrians": len(reconstructed_all),
                "eligible_actuator_users_reconstructed": sum(
                    item["eligible_actuator_user"] for item in reconstructed_all
                ),
                "first_actuation_cycles": len(first_items),
                "distinct_observed_fdw_onsets": len(onset_clusters),
                "typical_cycle_seconds": typical_cycle,
                "sum_first_actuation_latency_seconds": latency_sum,
                "mean_first_actuation_latency_seconds": latency_sum
                / len(first_items),
                "cycle_plugin_implied_count": base_count,
                "cycle_plugin_implied_count_low": base_count_low,
                "cycle_plugin_implied_count_high": base_count_high,
                "count_alpha_cycle_plugin": observed / base_count,
                "count_alpha_cycle_plugin_if_high_base": observed / base_count_high,
                "count_alpha_cycle_plugin_if_low_base": observed / base_count_low,
                "full_compliance_delay_seconds": observed_compliance_delay,
                "cycle_plugin_delay_unexpanded_seconds": unexpanded_delay,
                "delay_alpha_cycle_plugin": alpha_delay,
                "signal_order_score": order_score,
                "previous_row_shift_match_rate": shift_match_rate,
                "unreconstructed_terminal_rows": 1,
                "status": "partial reconstruction sensitivity; not exact validation",
            }
        )

    count_alphas = [row["count_alpha_cycle_plugin"] for row in cases]
    delay_alphas = [row["delay_alpha_cycle_plugin"] for row in cases]
    for index, row in enumerate(cases):
        loo_alpha = statistics.fmean(
            value for other, value in enumerate(count_alphas) if other != index
        )
        predicted = row["cycle_plugin_implied_count"] * loo_alpha
        row["leave_one_case_out_count_alpha"] = loo_alpha
        row["leave_one_case_out_predicted_pedestrians"] = predicted
        row["leave_one_case_out_absolute_percentage_error"] = abs(
            predicted / row["observed_pedestrians"] - 1
        )

    total_observed = sum(row["observed_pedestrians"] for row in cases)
    total_base = sum(row["cycle_plugin_implied_count"] for row in cases)
    total_base_low = sum(row["cycle_plugin_implied_count_low"] for row in cases)
    total_base_high = sum(row["cycle_plugin_implied_count_high"] for row in cases)
    total_observed_delay = sum(row["full_compliance_delay_seconds"] for row in cases)
    total_base_delay = sum(
        row["cycle_plugin_delay_unexpanded_seconds"] for row in cases
    )
    metrics = {
        "case_count": len(cases),
        "observed_pedestrians": total_observed,
        "eligible_actuator_users_reconstructed": sum(
            row["eligible_actuator_users_reconstructed"] for row in cases
        ),
        "first_actuation_cycles": sum(row["first_actuation_cycles"] for row in cases),
        "sum_first_actuation_latency_seconds": sum(
            row["sum_first_actuation_latency_seconds"] for row in cases
        ),
        "cycle_plugin_implied_count": total_base,
        "cycle_plugin_implied_count_low": total_base_low,
        "cycle_plugin_implied_count_high": total_base_high,
        "count_alpha_cycle_plugin_ratio_of_sums": total_observed / total_base,
        "count_alpha_cycle_plugin_ratio_of_sums_min": total_observed
        / total_base_high,
        "count_alpha_cycle_plugin_ratio_of_sums_max": total_observed
        / total_base_low,
        "count_alpha_cycle_plugin_mean_case": statistics.fmean(count_alphas),
        "count_alpha_cycle_plugin_median_case": statistics.median(count_alphas),
        "count_alpha_cycle_plugin_sd_case": statistics.stdev(count_alphas),
        "count_alpha_cycle_plugin_min_case": min(count_alphas),
        "count_alpha_cycle_plugin_p025_case": linear_quantile(
            count_alphas, 0.025
        ),
        "count_alpha_cycle_plugin_p25_case": linear_quantile(count_alphas, 0.25),
        "count_alpha_cycle_plugin_p75_case": linear_quantile(count_alphas, 0.75),
        "count_alpha_cycle_plugin_p975_case": linear_quantile(
            count_alphas, 0.975
        ),
        "count_alpha_cycle_plugin_max_case": max(count_alphas),
        "leave_one_case_out_predicted_pedestrians": sum(
            row["leave_one_case_out_predicted_pedestrians"] for row in cases
        ),
        "leave_one_case_out_count_mape": statistics.fmean(
            row["leave_one_case_out_absolute_percentage_error"] for row in cases
        ),
        "full_compliance_delay_seconds": total_observed_delay,
        "cycle_plugin_delay_unexpanded_seconds": total_base_delay,
        "delay_alpha_cycle_plugin_ratio_of_sums": total_observed_delay
        / total_base_delay,
        "delay_alpha_cycle_plugin_mean_case": statistics.fmean(delay_alphas),
        "delay_alpha_cycle_plugin_median_case": statistics.median(delay_alphas),
        "delay_alpha_cycle_plugin_sd_case": statistics.stdev(delay_alphas),
        "delay_alpha_cycle_plugin_min_case": min(delay_alphas),
        "delay_alpha_cycle_plugin_max_case": max(delay_alphas),
        "reconstruction_status": "partial sensitivity; missing exact next-FDW table",
    }
    return cases, cycles, [
        {"metric": metric, "value": value} for metric, value in metrics.items()
    ]


def summary_rows(cases: list[dict]) -> list[dict]:
    alphas = [row["alpha_video"] for row in cases]
    alpha_all = [row["alpha_all_actuator_users"] for row in cases]
    alpha_single = [row["alpha_video_single_stage"] for row in cases]
    total_pedestrians = sum(row["observed_pedestrians"] for row in cases)
    total_known_signal = sum(
        row["known_arrival_signal_pedestrians"] for row in cases
    )
    total_restrictive = sum(row["restrictive_arrivals"] for row in cases)
    total_walk = sum(row["walk_arrivals"] for row in cases)
    total_missing_arrival_signal = sum(
        row["missing_arrival_signal"] for row in cases
    )
    total_eligible = sum(row["eligible_actuator_users"] for row in cases)
    total_users = sum(row["actuator_users_all"] for row in cases)
    total_single = sum(row["single_stage_pedestrians"] for row in cases)
    total_single_eligible = sum(
        row["single_stage_eligible_actuator_users"] for row in cases
    )
    metrics = {
        "case_count": len(cases),
        "observed_pedestrians": total_pedestrians,
        "restrictive_arrivals": total_restrictive,
        "walk_arrivals": total_walk,
        "missing_arrival_signal": total_missing_arrival_signal,
        "actuator_users_all": total_users,
        "eligible_actuator_users": total_eligible,
        "eligible_actuator_share": total_eligible / total_pedestrians,
        "alpha_video_mean": statistics.fmean(alphas),
        "alpha_video_median": statistics.median(alphas),
        "alpha_video_sd": statistics.stdev(alphas),
        "alpha_video_min": min(alphas),
        "alpha_video_p025": linear_quantile(alphas, 0.025),
        "alpha_video_p25": linear_quantile(alphas, 0.25),
        "alpha_video_p75": linear_quantile(alphas, 0.75),
        "alpha_video_p975": linear_quantile(alphas, 0.975),
        "alpha_video_max": max(alphas),
        "known_arrival_signal_pedestrians": total_known_signal,
        "alpha_video_ratio_of_sums": total_known_signal / total_eligible,
        "alpha_video_including_missing_signal_ratio_of_sums": total_pedestrians
        / total_eligible,
        "count_alpha_walk_exposure_full_actuation_ratio_of_sums": (
            total_known_signal / total_restrictive
        ),
        "nonactuation_factor_restrictive_ratio_of_sums": (
            total_restrictive / total_eligible
        ),
        "alpha_all_users_mean": statistics.fmean(alpha_all),
        "alpha_all_users_ratio_of_sums": total_pedestrians / total_users,
        "alpha_single_stage_mean": statistics.fmean(alpha_single),
        "alpha_single_stage_ratio_of_sums": total_single / total_single_eligible,
    }
    return [{"metric": key, "value": value} for key, value in metrics.items()]


def compliance_summary_rows(cases: list[dict], sensitivity_totals: list[float]) -> list[dict]:
    observed = sum(row["observed_pedestrians"] for row in cases)
    known_signal = sum(row["known_arrival_signal_pedestrians"] for row in cases)
    restrictive = sum(row["restrictive_arrivals"] for row in cases)
    eligible = sum(row["eligible_actuator_users"] for row in cases)
    observed_wait = sum(
        row["observed_realised_wait_restrictive_seconds"] for row in cases
    )
    full_delay = sum(row["full_signal_compliance_delay_seconds"] for row in cases)
    eligible_delay = sum(
        row["eligible_actuator_user_compliance_delay_seconds"] for row in cases
    )
    metrics = {
        "session_count": len(cases),
        "observed_pedestrians": observed,
        "known_arrival_signal_pedestrians": known_signal,
        "restrictive_arrivals": restrictive,
        "walk_arrivals": sum(row["walk_arrivals"] for row in cases),
        "missing_arrival_signal": sum(
            row["missing_arrival_signal"] for row in cases
        ),
        "eligible_actuator_users": eligible,
        "count_alpha_observed_combined_ratio_of_sums": known_signal / eligible,
        "count_alpha_observed_combined_including_missing_signal_ratio_of_sums": observed
        / eligible,
        "count_alpha_observed_combined_mean_session": statistics.fmean(
            row["count_alpha_observed_combined"] for row in cases
        ),
        "count_alpha_walk_exposure_full_actuation_ratio_of_sums": (
            known_signal / restrictive
        ),
        "count_alpha_walk_exposure_full_actuation_mean_session": statistics.fmean(
            row["count_alpha_walk_exposure_full_actuation"] for row in cases
        ),
        "nonactuation_factor_restrictive_ratio_of_sums": restrictive / eligible,
        "nonactuation_factor_restrictive_mean_session": statistics.fmean(
            row["nonactuation_factor_restrictive"] for row in cases
        ),
        "decomposition_product_check": (known_signal / restrictive)
        * (restrictive / eligible),
        "observed_realised_wait_restrictive_seconds": observed_wait,
        "observed_realised_wait_restrictive_hours": observed_wait / 3600,
        "full_signal_compliance_delay_seconds": full_delay,
        "full_signal_compliance_delay_hours": full_delay / 3600,
        "full_signal_compliance_delay_sensitivity_min_seconds": min(
            sensitivity_totals
        ),
        "full_signal_compliance_delay_sensitivity_max_seconds": max(
            sensitivity_totals
        ),
        "full_signal_compliance_delay_increment_hours": (
            full_delay - observed_wait
        )
        / 3600,
        "full_signal_compliance_to_observed_wait_ratio": full_delay / observed_wait,
        "average_full_signal_compliance_delay_all_pedestrians_seconds": (
            full_delay / known_signal
        ),
        "average_full_signal_compliance_delay_restrictive_seconds": (
            full_delay / restrictive
        ),
        "eligible_actuator_user_compliance_delay_seconds": eligible_delay,
        "delay_alpha_observed_actuation_ratio_of_sums": full_delay / eligible_delay,
        "delay_alpha_observed_actuation_mean_session": statistics.fmean(
            row["delay_alpha_observed_actuation"] for row in cases
        ),
        "delay_alpha_full_actuation": 1.0,
        "phase_geometry_arrivals": sum(
            row["phase_geometry_arrivals"] for row in cases
        ),
        "aggregate_fallback_restrictive_arrivals": sum(
            row["aggregate_fallback_restrictive_arrivals"] for row in cases
        ),
    }
    return [{"metric": key, "value": value} for key, value in metrics.items()]


def write_note(
    cases: list[dict],
    summaries: list[dict],
    compliance_cases: list[dict],
    compliance_summaries: list[dict],
    group_rows: list[dict],
) -> None:
    metric = {row["metric"]: row["value"] for row in summaries}
    compliance = {row["metric"]: row["value"] for row in compliance_summaries}
    with NOTE_OUT.open("w", encoding="utf-8") as handle:
        handle.write("# Video-coded actuator-use alpha summary\n\n")
        handle.write(
            "> **Status:** the count tables below are behavioural diagnostics. The "
            "phase-geometry delay block is a superseded wrap-around sensitivity, not the "
            "paper's 100%-compliance estimate. The paper uses the direct signal-only "
            "calculation in `video_latency_replay/scripts/decompose_video_errors.py` and "
            "the pooled-censored peer factors in `estimate_video_pooled_censored.py`.\n\n"
        )
        handle.write(
            "An actuator-positive pedestrian is assumed to press at arrival. "
            "The primary denominator retains uses whose recorded arrival signal is "
            "flashing or solid red. The resulting values are complete-event behavioural "
            "expansions and are not estimator-matched first-actuation-latency factors. "
            "Three rows with missing arrival indication are excluded from the primary "
            "numerator.\n\n"
        )
        handle.write(
            "Source codes such as `3AM` mean site 3 in the morning, not 03:00. "
            "The source paper identifies the observation windows as 08:00-09:00 "
            "and 12:00-13:00. The `prev_start_time` field is a video-relative "
            "previous crossing-start time and is not a wall-clock arrival timestamp.\n\n"
        )
        handle.write(
            "| Site and observation time | Pedestrians | Restrictive arrivals | "
            "Eligible actuator users | Combined alpha |\n"
        )
        handle.write("|---|---:|---:|---:|---:|\n")
        for row in cases:
            handle.write(
                f"| {row['case_label']} | {row['observed_pedestrians']} | "
                f"{row['restrictive_arrivals']} | "
                f"{row['eligible_actuator_users']} | {row['alpha_video']:.3f} |\n"
            )
        handle.write("\n")
        handle.write(
            f"The six session factors range from {metric['alpha_video_min']:.3f} to "
            f"{metric['alpha_video_max']:.3f}, with unweighted mean "
            f"{metric['alpha_video_mean']:.3f}, median {metric['alpha_video_median']:.3f}, "
            f"and ratio-of-sums {metric['alpha_video_ratio_of_sums']:.3f}. "
            f"Including actuator use recorded for green arrivals gives mean "
            f"{metric['alpha_all_users_mean']:.3f}; restricting the analysis to "
            f"single-stage pedestrians gives mean {metric['alpha_single_stage_mean']:.3f}.\n"
        )
        handle.write("\n## Decomposition and compliance scenario\n\n")
        handle.write(
            "The aggregate combined factor decomposes exactly as\n\n"
            f"`{compliance['count_alpha_observed_combined_ratio_of_sums']:.3f} = "
            f"{compliance['count_alpha_walk_exposure_full_actuation_ratio_of_sums']:.3f} "
            f"x {compliance['nonactuation_factor_restrictive_ratio_of_sums']:.3f}`,\n\n"
            "where the first term accounts for known pedestrians arriving during Walk, and "
            "the second for restrictive-phase arrivals not recorded as actuator users. "
            "With universal actuator participation, the restrictive-population count "
            "factor is 1.000 and the all-arrival factor is therefore only this closed-period "
            "coverage term, "
            f"{compliance['count_alpha_walk_exposure_full_actuation_ratio_of_sums']:.3f}.\n\n"
        )
        handle.write(
            "For the superseded phase-geometry sensitivity, every restrictive-phase arrival is "
            "assigned the phase-geometry wait to the next estimated Walk onset. Walk "
            "onsets are the lower tails of compliant crossing-start clusters on each "
            "session/leg-distance phase clock. This gives "
            f"{compliance['full_signal_compliance_delay_hours']:.3f} pedestrian-hours, "
            f"or {compliance['average_full_signal_compliance_delay_all_pedestrians_seconds']:.2f} "
            "seconds per pedestrian with known arrival indication. Cluster-gap and "
            "reference-cycle alternatives span "
            f"{compliance['full_signal_compliance_delay_sensitivity_min_seconds']/3600:.3f}-"
            f"{compliance['full_signal_compliance_delay_sensitivity_max_seconds']/3600:.3f} "
            "hours. Restrictive arrivals without a usable phase value receive the median "
            "reconstructed delay for their session/leg-distance group. Eligible actuator "
            "users account for "
            f"{compliance['eligible_actuator_user_compliance_delay_seconds']/3600:.3f} hours, "
            "giving a delay-weighted behavioural factor of "
            f"{compliance['delay_alpha_observed_actuation_ratio_of_sums']:.3f}. Under "
            "universal actuator participation this delay factor is 1.000.\n\n"
        )
        handle.write(
            "The deposited phase variables are informative but imperfect. The source "
            "notebook's one-letter leg search maps east and west phase clocks to south, "
            "and at Redfern/Pitt one distance value represents more than one leg. The "
            "reported range therefore expresses phase-reconstruction sensitivity; it is "
            "not a sampling confidence interval.\n\n"
        )
        handle.write("## Group diagnostic\n\n")
        handle.write(
            "| Group code | Pedestrians | Restrictive arrivals | Eligible users | "
            "Actuation rate | Non-actuation factor |\n"
        )
        handle.write("|---|---:|---:|---:|---:|---:|\n")
        for row in group_rows:
            handle.write(
                f"| {row['group_label']} | {row['pedestrians']} | "
                f"{row['restrictive_arrivals']} | {row['eligible_actuator_users']} | "
                f"{row['actuation_rate_among_restrictive_arrivals']:.3f} | "
                f"{row['nonactuation_factor_restrictive']:.3f} |\n"
            )
        handle.write(
            "\nThese group rows describe person-level actuator coding. They do not identify "
            "unique physical presses or group-arrival events, so they cannot by themselves "
            "supply a group-size multiplier for the first-actuation model.\n"
        )


def append_cycle_plugin_note(
    reconstruction_cases: list[dict], reconstruction_summaries: list[dict]
) -> None:
    metric = {row["metric"]: row["value"] for row in reconstruction_summaries}
    with NOTE_OUT.open("a", encoding="utf-8") as handle:
        handle.write("\n## Cycle plug-in reconstruction sensitivity\n\n")
        handle.write(
            "The same cycle-level question used in MCAV can be reconstructed for eight "
            "approach-sessions at sites 4 and 5. For each actuator cycle, the base is "
            "`E_i / max(y_i, 0.5)`, where `y_i` is the reconstructed time from FDW onset "
            "to the first actuator user. The public export omits the next-FDW table, so "
            "`E_i` is inferred from observed FDW-onset gaps. The point estimate rounds "
            "the number of cycles in a long gap; floor and ceiling alternatives define "
            "the reported reconstruction range. Site 3 cannot be reconstructed because "
            "one exported distance combines two physical legs.\n\n"
        )
        handle.write(
            "| Approach-session | Observed | Base (range) | Alpha | LOO predicted | "
            "Absolute percentage error |\n"
        )
        handle.write("|---|---:|---:|---:|---:|---:|\n")
        for row in reconstruction_cases:
            handle.write(
                f"| {row['case_label']} | {row['observed_pedestrians']} | "
                f"{row['cycle_plugin_implied_count']:.1f} "
                f"({row['cycle_plugin_implied_count_low']:.1f}-"
                f"{row['cycle_plugin_implied_count_high']:.1f}) | "
                f"{row['count_alpha_cycle_plugin']:.3f} | "
                f"{row['leave_one_case_out_predicted_pedestrians']:.1f} | "
                f"{100*row['leave_one_case_out_absolute_percentage_error']:.1f}% |\n"
            )
        handle.write(
            "\nAcross these partial cases, the observed count is "
            f"{metric['observed_pedestrians']:.0f}, the uncalibrated base is "
            f"{metric['cycle_plugin_implied_count']:.1f} "
            f"({metric['cycle_plugin_implied_count_low']:.1f}-"
            f"{metric['cycle_plugin_implied_count_high']:.1f}), and the ratio-of-sums "
            f"alpha is {metric['count_alpha_cycle_plugin_ratio_of_sums']:.3f} "
            f"({metric['count_alpha_cycle_plugin_ratio_of_sums_min']:.3f}-"
            f"{metric['count_alpha_cycle_plugin_ratio_of_sums_max']:.3f}). The eight "
            f"case alphas have mean {metric['count_alpha_cycle_plugin_mean_case']:.3f}, "
            f"range {metric['count_alpha_cycle_plugin_min_case']:.3f}-"
            f"{metric['count_alpha_cycle_plugin_max_case']:.3f}. Leave-one-case-out "
            f"calibration predicts {metric['leave_one_case_out_predicted_pedestrians']:.1f} "
            f"pedestrians with {100*metric['leave_one_case_out_count_mape']:.1f}% MAPE. "
            "The weak and unstable result is evidence that the deposited timestamps do "
            "not support an exact second validation; it is not pooled with MCAV.\n"
        )


def main() -> None:
    digest = hashlib.sha256(SOURCE_IN.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Unexpected source SHA-256: {digest}")

    rows = read_csv(SOURCE_IN)
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["Session"]].append(row)
    cases = [case_row(session, groups[session]) for session in sorted(groups, key=session_key)]
    point_delays, point_methods, phase_models = compliance_delays(
        rows, PHASE_CLUSTER_GAP_SECONDS, "group_robust"
    )
    sensitivity_specs = [
        (PHASE_CLUSTER_GAP_SENSITIVITIES[0], "group_robust"),
        (PHASE_CLUSTER_GAP_SENSITIVITIES[1], "group_robust"),
        (PHASE_CLUSTER_GAP_SECONDS, "session_max"),
    ]
    sensitivity_delays = {
        index: compliance_delays(rows, gap, cycle_method)[0]
        for index, (gap, cycle_method) in enumerate(sensitivity_specs)
    }
    compliance_cases = [
        compliance_case_row(
            session,
            groups[session],
            point_delays,
            point_methods,
            sensitivity_delays,
        )
        for session in sorted(groups, key=session_key)
    ]
    sensitivity_totals = [
        sum(delay_map.get(id(row), 0.0) for row in rows)
        for delay_map in sensitivity_delays.values()
    ]
    group_rows = group_decomposition_rows(rows)

    all_users = sum(row["actuator_users_all"] for row in cases)
    eligible_users = sum(row["eligible_actuator_users"] for row in cases)
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_ROWS} rows, found {len(rows)}")
    if all_users != EXPECTED_ACTUATOR_USERS:
        raise RuntimeError(
            f"Expected {EXPECTED_ACTUATOR_USERS} actuator users, found {all_users}"
        )
    if eligible_users != EXPECTED_ELIGIBLE_ACTUATOR_USERS:
        raise RuntimeError(
            f"Expected {EXPECTED_ELIGIBLE_ACTUATOR_USERS} eligible users, found {eligible_users}"
        )

    summaries = summary_rows(cases)
    compliance_summaries = compliance_summary_rows(compliance_cases, sensitivity_totals)
    reconstruction_cases, reconstruction_cycles, reconstruction_summaries = (
        first_actuation_latency_analysis(rows, point_delays)
    )
    phase_rows = []
    for (session, leg), model in sorted(
        phase_models.items(), key=lambda item: (session_key(item[0][0]), item[0][1] or -1)
    ):
        phase_rows.append(
            {
                "source_session_code": session,
                "leg_distance": "" if leg is None else leg,
                "compliant_start_count": model["compliant_start_count"],
                "retained_cluster_count": model["retained_cluster_count"],
                "walk_onsets_seconds": ";".join(
                    f"{value:.3f}" for value in model["walk_onsets"]
                ),
                "reference_cycle_span_seconds": model["cycle_span_seconds"] or "",
                "cluster_gap_seconds": PHASE_CLUSTER_GAP_SECONDS,
                "cycle_method": "group_robust_q995",
            }
        )
    write_csv(CASE_OUT, cases, list(cases[0].keys()))
    write_csv(SUMMARY_OUT, summaries, ["metric", "value"])
    write_csv(
        COMPLIANCE_CASE_OUT,
        compliance_cases,
        list(compliance_cases[0].keys()),
    )
    write_csv(
        COMPLIANCE_SUMMARY_OUT,
        compliance_summaries,
        ["metric", "value"],
    )
    write_csv(GROUP_OUT, group_rows, list(group_rows[0].keys()))
    write_csv(PHASE_OUT, phase_rows, list(phase_rows[0].keys()))
    write_note(cases, summaries, compliance_cases, compliance_summaries, group_rows)
    write_csv(
        FIRST_ACTUATION_CASE_OUT,
        reconstruction_cases,
        list(reconstruction_cases[0].keys()),
    )
    write_csv(
        FIRST_ACTUATION_CYCLE_OUT,
        reconstruction_cycles,
        list(reconstruction_cycles[0].keys()),
    )
    write_csv(
        FIRST_ACTUATION_SUMMARY_OUT,
        reconstruction_summaries,
        ["metric", "value"],
    )
    append_cycle_plugin_note(reconstruction_cases, reconstruction_summaries)

    print(f"Source rows: {len(rows)}")
    print(f"Eligible actuator users: {eligible_users}")
    print(
        "Video alpha mean: "
        f"{statistics.fmean(row['alpha_video'] for row in cases):.3f}"
    )
    print(f"Wrote {CASE_OUT}")
    print(f"Wrote {SUMMARY_OUT}")
    print(f"Wrote {COMPLIANCE_CASE_OUT}")
    print(f"Wrote {COMPLIANCE_SUMMARY_OUT}")
    print(f"Wrote {GROUP_OUT}")
    print(f"Wrote {PHASE_OUT}")
    print(f"Wrote {FIRST_ACTUATION_CASE_OUT}")
    print(f"Wrote {FIRST_ACTUATION_CYCLE_OUT}")
    print(f"Wrote {FIRST_ACTUATION_SUMMARY_OUT}")
    print(f"Wrote {NOTE_OUT}")


if __name__ == "__main__":
    main()
