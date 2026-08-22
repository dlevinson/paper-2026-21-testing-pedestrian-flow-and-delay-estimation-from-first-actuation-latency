#!/usr/bin/env python3
"""Estimator-matched video validation using reconstructed first actuations.

The public video export is one row per pedestrian, so a completely empty signal
cycle has no row.  The full set of no-actuation service opportunities is
nevertheless identifiable as *exposure* when the one-hour observation window
and the signal service period are known.  This set includes cycles containing
pedestrians who do not actuate as well as cycles containing no pedestrians.
For each reconstructable approach-session, the censored first-event likelihood
is therefore

    lambda_hat = K / (sum(Y_k) + (M - K) * T_R),

where K is the number of cycles with an eligible actuation, Y is the first
actuation latency (actuation is placed at pedestrian arrival), M is the number
of service opportunities in the hour, and T_R is the restrictive-period
duration.  The M-K cycles contribute right-censored exposure without requiring
invented pedestrian rows.

This is the same estimator family used for MCAV.  It is an independent peer
validation under two explicit reconstruction assumptions: press at arrival and
recovered signal geometry.  Its factors are not pooled with MCAV.

Run estimate_video_alpha.py first; this script consumes its auditable
first-actuation-cycle reconstruction and the archived pedestrian-level source.
"""

from __future__ import annotations

import csv
import hashlib
import math
import statistics
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
VALIDATION_DIR = HERE.parent
SOURCE = VALIDATION_DIR / "source" / "REGRESSION_SINGLE_HARD_COMPLIANCE.csv"
CYCLES = VALIDATION_DIR / "video_cycle_plugin_reconstruction_cycles.csv"
CASE_OUT = VALIDATION_DIR / "video_pooled_censored_cases.csv"
SUMMARY_OUT = VALIDATION_DIR / "video_pooled_censored_summary.csv"

EXPECTED_SHA256 = "7281d4e7215cc1c71c2372a19a2c02a84a1b7108c8c59fc02516f42228c9cee7"
SESSION_SECONDS = 3_600.0
RESTRICTIVE = {"1", "2"}
SELECTED_DISTANCES = {"4": {9.9, 12.8}, "5": {15.1, 15.9}}
SITE_NAMES = {
    "4": "Campbell St / Riley St",
    "5": "William Henry St / Harris St",
}


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def number(value: str | None) -> float | None:
    try:
        result = float(value) if value not in (None, "") else None
    except ValueError:
        return None
    return result if result is not None and math.isfinite(result) else None


def discrete_quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("quantile of empty sample")
    return ordered[min(len(ordered) - 1, int(probability * len(ordered)))]


def service_period(rows: list[dict]) -> float:
    """Recover the controller service period from wrap-around wait identities."""

    gaps = []
    for row in rows:
        arrival_offset = number(row.get("time_bw_arrival_and_FR_hard"))
        start_offset = number(row.get("time_bw_start_and_FR_hard"))
        wait = number(row.get("wait_time_s"))
        if None in (arrival_offset, start_offset, wait):
            continue
        gap = wait - (start_offset - arrival_offset)
        if gap > 20.0:
            gaps.append(gap)
    if len(gaps) < 5:
        raise ValueError("insufficient service-period identities")
    median = statistics.median(gaps)
    first_band = [gap for gap in gaps if gap < 1.5 * median]
    return statistics.median(first_band)


def restrictive_duration(rows: list[dict], probability: float = 0.10) -> float:
    """Low-tail Walk starts estimate the red-to-Walk boundary on the phase clock."""

    starts = [
        value
        for row in rows
        if row.get("signal_at_start") == "0"
        and row.get("signal_at_arrival") in RESTRICTIVE
        and (value := number(row.get("time_bw_start_and_FR_hard"))) is not None
    ]
    if not starts:
        raise ValueError("no compliant Walk starts for restrictive-duration estimate")
    return discrete_quantile(starts, probability)


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: f"{value:.9f}" if isinstance(value, float) else value
                    for key, value in row.items()
                }
            )


def correlation(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    cross = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    sum_x2 = sum((x - mean_x) ** 2 for x in xs)
    sum_y2 = sum((y - mean_y) ** 2 for y in ys)
    slope = cross / sum_x2
    intercept = mean_y - slope * mean_x
    corr = cross / math.sqrt(sum_x2 * sum_y2)
    return corr, intercept, slope


def main() -> None:
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Unexpected source SHA-256: {digest}")
    if not CYCLES.exists():
        raise RuntimeError(
            "Run estimate_video_alpha.py first to reconstruct first-actuation cycles"
        )

    pedestrians = read_csv(SOURCE)
    reconstructed = read_csv(CYCLES)
    sessions = sorted({row["Session"] for row in pedestrians})
    session_period = {
        session: service_period([row for row in pedestrians if row["Session"] == session])
        for session in sessions
    }

    source_groups: dict[tuple[str, float], list[dict]] = defaultdict(list)
    for row in pedestrians:
        distance = number(row.get("leg_distance"))
        if distance is None:
            continue
        session = row["Session"]
        if session[0] in SELECTED_DISTANCES and any(
            abs(distance - selected) < 0.01
            for selected in SELECTED_DISTANCES[session[0]]
        ):
            source_groups[(session, round(distance, 2))].append(row)

    cycle_groups: dict[tuple[str, float], list[dict]] = defaultdict(list)
    for row in reconstructed:
        cycle_groups[
            (row["source_session_code"], round(float(row["leg_distance"]), 2))
        ].append(row)

    cases = []
    for key in sorted(source_groups, key=lambda item: (item[0], item[1])):
        session, distance = key
        rows = source_groups[key]
        cycle_rows = cycle_groups.get(key, [])
        if not cycle_rows:
            raise RuntimeError(f"No reconstructed actuation cycles for {key}")

        period = session_period[session]
        red = min(restrictive_duration(rows), period - 6.0)
        opportunities = round(SESSION_SECONDS / period)
        first_actuations = len(cycle_rows)
        if first_actuations > opportunities:
            raise RuntimeError(f"More actuated cycles than service opportunities for {key}")
        first_latencies = [float(row["first_actuation_latency_seconds"]) for row in cycle_rows]
        latency_sum = sum(first_latencies)
        empty_cycles = opportunities - first_actuations
        risk = latency_sum + empty_cycles * red
        rate = first_actuations / risk
        implied = rate * SESSION_SECONDS
        observed = len(rows)
        alpha = observed / implied

        restrictive_rows = [row for row in rows if row.get("signal_at_arrival") in RESTRICTIVE]
        observed_waits = [
            red - offset
            for row in restrictive_rows
            if (offset := number(row.get("time_bw_arrival_and_FR_hard"))) is not None
            and offset <= red
        ]
        mean_wait = statistics.fmean(observed_waits) if observed_waits else 0.0
        compliant_delay = sum(observed_waits) + mean_wait * (
            len(restrictive_rows) - len(observed_waits)
        )
        model_delay = sum(
            (red - latency) + rate * (red - latency) ** 2 / 2.0
            for latency in first_latencies
            if latency <= red
        )

        # Geometry sensitivity: integer opportunity bounds and the 5th/20th
        # percentiles of compliant Walk starts.  These are reconstruction
        # bounds, not sampling confidence intervals.
        implied_sensitivity = []
        for opportunity_count in {
            math.floor(SESSION_SECONDS / period),
            round(SESSION_SECONDS / period),
            math.ceil(SESSION_SECONDS / period),
        }:
            for probability in (0.05, 0.10, 0.20):
                red_s = min(restrictive_duration(rows, probability), period - 6.0)
                empty_s = max(opportunity_count - first_actuations, 0)
                risk_s = latency_sum + empty_s * red_s
                implied_sensitivity.append(first_actuations / risk_s * SESSION_SECONDS)

        cases.append(
            {
                "source_session_code": session,
                "site_name": SITE_NAMES[session[0]],
                "observation_time": "08:00-09:00" if session.endswith("AM") else "12:00-13:00",
                "leg_distance": distance,
                "observed_pedestrians": observed,
                "service_period_s": period,
                "restrictive_duration_s": red,
                "service_opportunities": opportunities,
                "first_actuation_cycles": first_actuations,
                "inferred_no_actuation_cycles": empty_cycles,
                "sum_first_actuation_latency_s": latency_sum,
                "censored_risk_exposure_s": risk,
                "pooled_rate_per_hour": implied,
                "pooled_censored_implied_count": implied,
                "count_alpha": alpha,
                "count_alpha_geometry_low": observed / max(implied_sensitivity),
                "count_alpha_geometry_high": observed / min(implied_sensitivity),
                "red_share": red / period,
                "full_compliance_delay_s": compliant_delay,
                "pooled_model_delay_s": model_delay,
                "delay_alpha": compliant_delay / model_delay,
                "press_at_arrival_assumption": "yes",
                "empty_cycles_observed_as_censored_exposure": "yes",
            }
        )

    for index, case in enumerate(cases):
        training_alpha = statistics.fmean(
            other["count_alpha"] for j, other in enumerate(cases) if j != index
        )
        prediction = training_alpha * case["pooled_censored_implied_count"]
        case["leave_one_case_out_alpha"] = training_alpha
        case["leave_one_case_out_prediction"] = prediction
        case["leave_one_case_out_absolute_percentage_error"] = abs(
            prediction - case["observed_pedestrians"]
        ) / case["observed_pedestrians"]

    total_observed = sum(row["observed_pedestrians"] for row in cases)
    total_implied = sum(row["pooled_censored_implied_count"] for row in cases)
    total_compliant_delay = sum(row["full_compliance_delay_s"] for row in cases)
    total_model_delay = sum(row["pooled_model_delay_s"] for row in cases)
    total_implied_geometry_high = sum(
        row["observed_pedestrians"] / row["count_alpha_geometry_low"]
        for row in cases
    )
    total_implied_geometry_low = sum(
        row["observed_pedestrians"] / row["count_alpha_geometry_high"]
        for row in cases
    )
    corr, intercept, slope = correlation(
        [row["red_share"] for row in cases], [row["count_alpha"] for row in cases]
    )
    summaries = [
        {"metric": "approach_session_cases", "value": len(cases)},
        {"metric": "observed_pedestrians", "value": total_observed},
        {"metric": "first_actuation_cycles", "value": sum(row["first_actuation_cycles"] for row in cases)},
        {"metric": "inferred_no_actuation_cycles", "value": sum(row["inferred_no_actuation_cycles"] for row in cases)},
        {"metric": "pooled_censored_implied_count", "value": total_implied},
        {"metric": "count_alpha_ratio_of_sums", "value": total_observed / total_implied},
        {"metric": "count_alpha_geometry_ratio_of_sums_low", "value": total_observed / total_implied_geometry_high},
        {"metric": "count_alpha_geometry_ratio_of_sums_high", "value": total_observed / total_implied_geometry_low},
        {"metric": "count_alpha_mean_case", "value": statistics.fmean(row["count_alpha"] for row in cases)},
        {"metric": "count_alpha_geometry_mean_case_low", "value": statistics.fmean(row["count_alpha_geometry_low"] for row in cases)},
        {"metric": "count_alpha_geometry_mean_case_high", "value": statistics.fmean(row["count_alpha_geometry_high"] for row in cases)},
        {"metric": "count_alpha_min_case", "value": min(row["count_alpha"] for row in cases)},
        {"metric": "count_alpha_max_case", "value": max(row["count_alpha"] for row in cases)},
        {"metric": "leave_one_case_out_predicted_pedestrians", "value": sum(row["leave_one_case_out_prediction"] for row in cases)},
        {"metric": "leave_one_case_out_mape", "value": statistics.fmean(row["leave_one_case_out_absolute_percentage_error"] for row in cases)},
        {"metric": "full_compliance_delay_hours", "value": total_compliant_delay / 3600.0},
        {"metric": "pooled_model_delay_hours", "value": total_model_delay / 3600.0},
        {"metric": "delay_alpha_ratio_of_sums", "value": total_compliant_delay / total_model_delay},
        {"metric": "delay_alpha_mean_case", "value": statistics.fmean(row["delay_alpha"] for row in cases)},
        {"metric": "count_alpha_red_share_correlation", "value": corr},
        {"metric": "count_alpha_red_share_regression_intercept", "value": intercept},
        {"metric": "count_alpha_red_share_regression_slope", "value": slope},
    ]

    write_csv(CASE_OUT, cases)
    write_csv(SUMMARY_OUT, summaries)

    print("Video pooled-censored peer validation")
    print(f"  cases: {len(cases)}; observed pedestrians: {total_observed}")
    print(
        f"  alpha_N mean {statistics.fmean(row['count_alpha'] for row in cases):.3f}; "
        f"ratio of sums {total_observed / total_implied:.3f}"
    )
    print(
        f"  LOO predicted {sum(row['leave_one_case_out_prediction'] for row in cases):.1f}; "
        f"MAPE {statistics.fmean(row['leave_one_case_out_absolute_percentage_error'] for row in cases):.1%}"
    )
    print(
        f"  alpha_D mean {statistics.fmean(row['delay_alpha'] for row in cases):.3f}; "
        f"ratio of sums {total_compliant_delay / total_model_delay:.3f}"
    )
    print(f"  alpha_N/red-share correlation: {corr:.3f}")
    print(f"Wrote {CASE_OUT}")
    print(f"Wrote {SUMMARY_OUT}")


if __name__ == "__main__":
    main()
