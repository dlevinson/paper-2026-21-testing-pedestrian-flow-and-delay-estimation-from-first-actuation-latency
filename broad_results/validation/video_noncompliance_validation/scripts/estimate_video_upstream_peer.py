#!/usr/bin/env python3
"""Run the estimator-matched peer analysis on the upstream video files.

The upstream package supplies a pedestrian table and four complete signal-state
streams for each video session.  It therefore supplies the same two count-side
inputs used by MCAV: restrictive-cycle exposure, including cycles with no
actuation, and the first eligible actuation in each cycle.  The actuator field
is binary rather than timestamped, so an actuator-positive pedestrian is
assumed to press at their recorded arrival time.

Only Python's standard library is required.  Outputs are written beside this
validation folder and are intentionally separate from the older reconstruction
based on the processed public table.
"""

from __future__ import annotations

import csv
import hashlib
import math
import statistics
from collections import defaultdict
from pathlib import Path


VALIDATION_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = VALIDATION_DIR / "source" / "choy_final_data_20260720"
SESSIONS = ("3AM", "3PM", "4AM", "4PM", "5AM", "5PM")
LEGS = ("north leg", "east leg", "south leg", "west leg")
DIRECTION_BY_LEG = {
    "north leg": "N",
    "east leg": "E",
    "south leg": "S",
    "west leg": "W",
}
SITE_BY_NUMBER = {
    "3": "Redfern Street/Pitt Street",
    "4": "Campbell Street/Riley Street",
    "5": "William Henry Street/Harris Street",
}
PERIOD_BY_CODE = {"AM": "08:00--09:00", "PM": "12:00--13:00"}
MCAV_COUNT_ALPHA_MEAN = 2.202456678
STARTUP_LAG_S = 5.499

# These hashes identify the author-supplied upstream files used in the paper.
EXPECTED_SHA256 = {
    "3AM/3AM PED.csv": "05d047ee391160fb94cccb955479123ac0dcb70170c2b513455a3a38f16e439e",
    "3AM/3AM SIGNAL.csv": "cb2250d05ae4c8f6976837a310e2bdcc4a9975c4e8805421e0d3dbd97b053fca",
    "3AM/3AM_MASTER_SINGLE_STAGE.csv": "61f8ff5f24c293a702018963b2974118ecf066dd57c26e40ef81095822369b9b",
    "3PM/3PM PED.csv": "fcb0fb0fda32e5030fdd182f4d8a1847a2d3d79aae8aa3ee1f4eafd1f273d5b9",
    "3PM/3PM SIGNAL.csv": "161fff7fb894522b28744db678f65101955a70a1995076329464c4d528b133d9",
    "3PM/3PM_MASTER_SINGLE_STAGE.csv": "8723f5cdfc08c9d2682dcec31bbefadd5d210306489c4904f2dae3d6a591cb21",
    "4AM/4AM PED.csv": "8d9f77eb17c602742ca0451c005fe27bd64e129de31397cddac0ff4a687d0f4f",
    "4AM/4AM SIGNAL.csv": "76848c59aca6bb52da08f4e52326f6460a8b4d01c62ab9efb920571ec0f9832c",
    "4AM/4AM_MASTER_SINGLE_STAGE.csv": "c091e36722710e5e7727692b7e7ddd01df0049d3fb096f7140bfa63adfaa3401",
    "4PM/4PM PED.csv": "c72a3f5ce0ca26b844e385c5be4c6662867bd1893198cc545f70fdfcdc9ac320",
    "4PM/4PM SIGNAL.csv": "7946c81b182cc5d7c205448e8bca35ebe19b355c1939f45f5446f2ebb75dcfd3",
    "4PM/4PM_MASTER_SINGLE_STAGE.csv": "ee893ec0b38c009f3c5751a2fee945c1a10e29046d4f69b793eb57bbe6002fb1",
    "5AM/5AM PED.csv": "75dc55168f963bedb45b2025cbfd8a9a6097afaca7a4d99e0d7e6fe46e18429f",
    "5AM/5AM SIGNAL.csv": "4355864ee78f50eb0b7c3fd571882fbf274b0db3b8cced54e47d02bd69c3f811",
    "5AM/5AM_MASTER_SINGLE_STAGE.csv": "aedea00279a5e85e72d14dd9f97fb51a0f55c6e1c6a6f20f04d1e10f9f898104",
    "5PM/5PM PED.csv": "938b52e2041561e12085ff2830da6a6f13a5163e64298c69b0bacb3d77ba4934",
    "5PM/5PM SIGNAL.csv": "9a29fbb060b5d070d8c3e9177ea512dabac480a3264003d9163e977e865f69f7",
    "5PM/5PM_MASTER_SINGLE_STAGE.csv": "f23f483f5b5e4cd81744a645e9aab0addc6da5ccddc679ca054e5bb739bb79fd",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: format_value(row.get(key, "")) for key in fields})


def format_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.9f}"
    return value


def seconds(value: str | None) -> float | None:
    if not value or value == "-":
        return None
    parts = value.split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, second_value = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(second_value)
    except ValueError:
        return None


def number(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "", "-") else None
    except ValueError:
        return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def state_at(events: list[tuple[float, str]], time_s: float) -> str | None:
    state = None
    for event_time, event_state in events:
        if event_time > time_s:
            break
        state = event_state
    return state


def next_state_time(
    events: list[tuple[float, str]], time_s: float, target: str
) -> float | None:
    for event_time, event_state in events:
        if event_time > time_s and event_state == target:
            return event_time
    return None


def state_duration(
    events: list[tuple[float, str]], session_end_s: float, targets: set[str]
) -> float:
    total = 0.0
    for index, (start, state) in enumerate(events):
        if start >= session_end_s:
            break
        end = events[index + 1][0] if index + 1 < len(events) else session_end_s
        if state in targets:
            total += max(0.0, min(end, session_end_s) - start)
    return total


def correlation(xs: list[float], ys: list[float]) -> float:
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = math.sqrt(
        sum((x - mean_x) ** 2 for x in xs)
        * sum((y - mean_y) ** 2 for y in ys)
    )
    return numerator / denominator if denominator else math.nan


def source_manifest() -> list[dict]:
    rows = []
    for relative, expected in EXPECTED_SHA256.items():
        path = SOURCE_DIR / relative
        actual = sha256(path)
        if actual != expected:
            raise ValueError(f"SHA-256 mismatch for {relative}: {actual} != {expected}")
        rows.append(
            {
                "relative_path": relative,
                "bytes": path.stat().st_size,
                "sha256": actual,
                "verified": 1,
            }
        )
    return rows


def main() -> None:
    manifest_rows = source_manifest()
    case_rows: list[dict] = []
    cycle_rows: list[dict] = []
    arrival_rows: list[dict] = []
    session_rows: list[dict] = []
    raw_pedestrian_rows = 0
    missing_leg_rows = 0

    for session in SESSIONS:
        session_dir = SOURCE_DIR / session
        pedestrians = read_csv(session_dir / f"{session} PED.csv")
        signal_rows = read_csv(session_dir / f"{session} SIGNAL.csv")
        master_rows = read_csv(session_dir / f"{session}_MASTER_SINGLE_STAGE.csv")
        master_by_id = {row.get("ID", ""): row for row in master_rows}
        raw_pedestrian_rows += len(pedestrians)
        missing_leg_rows += sum(
            row.get("Leg", "").strip().lower() not in LEGS for row in pedestrians
        )

        events_by_leg: dict[str, list[tuple[float, str]]] = {}
        for leg, direction in DIRECTION_BY_LEG.items():
            events = []
            for row in signal_rows:
                event_time = seconds(row.get(f"{direction}.time"))
                event_state = row.get(f"{direction}.signal", "").strip()
                if event_time is not None and event_state:
                    events.append((event_time, event_state))
            events.sort()
            events_by_leg[leg] = events

        # The directional streams are simultaneous but have unequal numbers of
        # transitions.  Their latest timestamp is the conservative common end
        # of the recorded signal window and covers every mapped pedestrian.
        session_end_s = max(
            event_time
            for events in events_by_leg.values()
            for event_time, _ in events
        )

        for leg in LEGS:
            events = events_by_leg[leg]
            people = [
                row
                for row in pedestrians
                if row.get("Leg", "").strip().lower() == leg
                and (arrival := seconds(row.get("Arrival Time"))) is not None
                and arrival <= session_end_s
            ]
            actuator_users = [
                row for row in people if number(row.get("Accuator")) == 1.0
            ]

            cycles: list[dict] = []
            for onset_s, indication in events:
                if indication != "FR" or onset_s >= session_end_s:
                    continue
                following_walk_s = next_state_time(events, onset_s, "G")
                censor_end_s = min(following_walk_s or session_end_s, session_end_s)
                if censor_end_s <= onset_s:
                    continue
                eligible_times = []
                for person in actuator_users:
                    arrival_s = seconds(person.get("Arrival Time"))
                    if (
                        arrival_s is not None
                        and onset_s <= arrival_s < censor_end_s
                        and state_at(events, arrival_s) in {"FR", "R"}
                    ):
                        eligible_times.append(arrival_s)
                observed_arrival_times = []
                for person in people:
                    arrival_s = seconds(person.get("Arrival Time"))
                    if (
                        arrival_s is not None
                        and onset_s <= arrival_s < censor_end_s
                        and state_at(events, arrival_s) in {"FR", "R"}
                    ):
                        observed_arrival_times.append(arrival_s)
                first_s = min(eligible_times) if eligible_times else None
                risk_s = first_s - onset_s if first_s is not None else censor_end_s - onset_s
                first_arrival_s = (
                    min(observed_arrival_times) if observed_arrival_times else None
                )
                full_actuation_risk_s = (
                    first_arrival_s - onset_s
                    if first_arrival_s is not None
                    else censor_end_s - onset_s
                )
                cycle = {
                    "case_id": f"{session}_{DIRECTION_BY_LEG[leg]}",
                    "session": session,
                    "leg": leg,
                    "fdw_onset_s": onset_s,
                    "censor_end_s": censor_end_s,
                    "following_walk_s": following_walk_s,
                    "restrictive_duration_s": censor_end_s - onset_s,
                    "first_actuation_s": first_s,
                    "first_actuation_latency_s": (
                        first_s - onset_s if first_s is not None else None
                    ),
                    "risk_exposure_s": risk_s,
                    "first_actuation_cycle": int(first_s is not None),
                    "right_censored_cycle": int(first_s is None),
                    "eligible_actuator_users_in_cycle": len(eligible_times),
                    "first_observed_arrival_s": first_arrival_s,
                    "first_observed_arrival_latency_s": (
                        first_arrival_s - onset_s
                        if first_arrival_s is not None
                        else None
                    ),
                    "full_actuation_risk_exposure_s": full_actuation_risk_s,
                    "first_observed_arrival_cycle": int(first_arrival_s is not None),
                    "right_censored_no_arrival_cycle": int(
                        first_arrival_s is None
                    ),
                }
                cycles.append(cycle)
                cycle_rows.append(cycle)

            first_actuation_cycles = sum(
                cycle["first_actuation_cycle"] for cycle in cycles
            )
            risk_exposure_s = sum(cycle["risk_exposure_s"] for cycle in cycles)
            rate_per_s = (
                first_actuation_cycles / risk_exposure_s if risk_exposure_s else math.nan
            )
            base_count = rate_per_s * session_end_s
            full_actuation_first_arrival_cycles = sum(
                cycle["first_observed_arrival_cycle"] for cycle in cycles
            )
            full_actuation_risk_exposure_s = sum(
                cycle["full_actuation_risk_exposure_s"] for cycle in cycles
            )
            full_actuation_rate_per_s = (
                full_actuation_first_arrival_cycles
                / full_actuation_risk_exposure_s
                if full_actuation_risk_exposure_s
                else math.nan
            )
            full_actuation_base_count = (
                full_actuation_rate_per_s * session_end_s
            )
            occupied_arrival_seconds = len(
                {
                    math.floor(arrival_s)
                    for person in people
                    if (arrival_s := seconds(person.get("Arrival Time"))) is not None
                }
            )

            compliant_delay_s = 0.0
            model_delay_s = 0.0
            delay_covered_arrivals = 0
            signal_unknown_arrivals = 0
            eligible_actuator_users = 0
            realised_restrictive_delay_s = 0.0
            noncompliers = 0
            noncompliance_saving_s = 0.0

            for person in people:
                arrival_s = seconds(person.get("Arrival Time"))
                assert arrival_s is not None
                arrival_state = state_at(events, arrival_s)
                actuator_user = number(person.get("Accuator")) == 1.0
                eligible_user = actuator_user and arrival_state in {"FR", "R"}
                eligible_actuator_users += int(eligible_user)
                next_walk_s = (
                    next_state_time(events, arrival_s, "G")
                    if arrival_state in {"FR", "R"}
                    else None
                )
                person_compliant_delay_s = (
                    next_walk_s - arrival_s if next_walk_s is not None else 0.0
                )
                if arrival_state in {"FR", "R"} and next_walk_s is not None:
                    compliant_delay_s += person_compliant_delay_s
                    delay_covered_arrivals += 1
                elif arrival_state is None:
                    signal_unknown_arrivals += 1

                master = master_by_id.get(person.get("ID", ""), {})
                realised_wait_s = number(master.get("wait_time_s"))
                start_s = seconds(person.get("Start Crossing Time"))
                start_state = state_at(events, start_s) if start_s is not None else None
                is_noncomplier = (
                    arrival_state in {"FR", "R"}
                    and start_state in {"FR", "R"}
                    and next_walk_s is not None
                    and realised_wait_s is not None
                )
                saving_s = None
                if arrival_state in {"FR", "R"} and realised_wait_s is not None:
                    realised_restrictive_delay_s += realised_wait_s
                if is_noncomplier:
                    noncompliers += 1
                    saving_s = person_compliant_delay_s - realised_wait_s
                    noncompliance_saving_s += saving_s

                arrival_rows.append(
                    {
                        "case_id": f"{session}_{DIRECTION_BY_LEG[leg]}",
                        "session": session,
                        "site": SITE_BY_NUMBER[session[0]],
                        "period": PERIOD_BY_CODE[session[1:]],
                        "pedestrian_id": person.get("ID", ""),
                        "leg": leg,
                        "arrival_s": arrival_s,
                        "start_crossing_s": start_s,
                        "signal_at_arrival_exact": arrival_state,
                        "signal_at_start_exact": start_state,
                        "actuator_user": int(actuator_user),
                        "eligible_actuator_user": int(eligible_user),
                        "next_walk_s": next_walk_s,
                        "compliant_signal_delay_s": person_compliant_delay_s,
                        "processed_realised_wait_s": realised_wait_s,
                        "noncomplier_exact": int(is_noncomplier),
                        "noncompliance_saving_s": saving_s,
                    }
                )

            for cycle in cycles:
                first_s = cycle["first_actuation_s"]
                following_walk_s = cycle["following_walk_s"]
                if first_s is None or following_walk_s is None:
                    continue
                remaining_s = following_walk_s - first_s
                model_delay_s += remaining_s + rate_per_s * remaining_s**2 / 2.0

            restrictive_state_s = state_duration(
                events, session_end_s, {"FR", "R"}
            )
            case_rows.append(
                {
                    "case_id": f"{session}_{DIRECTION_BY_LEG[leg]}",
                    "source_session_code": session,
                    "session": session,
                    "site": SITE_BY_NUMBER[session[0]],
                    "period": PERIOD_BY_CODE[session[1:]],
                    "leg": leg,
                    "session_duration_s": session_end_s,
                    "observed_pedestrians": len(people),
                    "actuator_users": len(actuator_users),
                    "eligible_actuator_users": eligible_actuator_users,
                    "service_opportunities": len(cycles),
                    "first_actuation_cycles": first_actuation_cycles,
                    "no_actuation_cycles": len(cycles) - first_actuation_cycles,
                    "risk_exposure_s": risk_exposure_s,
                    "rate_per_s": rate_per_s,
                    "base_count": base_count,
                    "count_alpha": len(people) / base_count,
                    "full_actuation_first_arrival_cycles": (
                        full_actuation_first_arrival_cycles
                    ),
                    "full_actuation_risk_exposure_s": (
                        full_actuation_risk_exposure_s
                    ),
                    "full_actuation_rate_per_s": full_actuation_rate_per_s,
                    "full_actuation_base_count": full_actuation_base_count,
                    "missing_actuation_multiplier": (
                        full_actuation_base_count / base_count
                    ),
                    "occupied_arrival_seconds": occupied_arrival_seconds,
                    "people_per_occupied_second": (
                        len(people) / occupied_arrival_seconds
                    ),
                    "remaining_timing_model_factor": (
                        occupied_arrival_seconds / full_actuation_base_count
                    ),
                    "decomposition_product_check": (
                        (full_actuation_base_count / base_count)
                        * (len(people) / occupied_arrival_seconds)
                        * (occupied_arrival_seconds / full_actuation_base_count)
                    ),
                    "restrictive_state_s": restrictive_state_s,
                    "red_share": restrictive_state_s / session_end_s,
                    "compliant_signal_delay_s": compliant_delay_s,
                    "model_delay_s": model_delay_s,
                    "delay_alpha": compliant_delay_s / model_delay_s,
                    "realised_delay_alpha": (
                        realised_restrictive_delay_s / model_delay_s
                        if model_delay_s
                        else math.nan
                    ),
                    "delay_covered_arrivals": delay_covered_arrivals,
                    "signal_unknown_arrivals": signal_unknown_arrivals,
                    "realised_restrictive_delay_s": realised_restrictive_delay_s,
                    "noncompliers": noncompliers,
                    "noncompliance_saving_s": noncompliance_saving_s,
                }
            )

        session_cases = [row for row in case_rows if row["session"] == session]
        session_rows.append(
            {
                "session": session,
                "site": SITE_BY_NUMBER[session[0]],
                "period": PERIOD_BY_CODE[session[1:]],
                "session_duration_s": session_end_s,
                "observed_pedestrians": sum(
                    row["observed_pedestrians"] for row in session_cases
                ),
                "service_opportunities": sum(
                    row["service_opportunities"] for row in session_cases
                ),
                "first_actuation_cycles": sum(
                    row["first_actuation_cycles"] for row in session_cases
                ),
                "no_actuation_cycles": sum(
                    row["no_actuation_cycles"] for row in session_cases
                ),
                "base_count": sum(row["base_count"] for row in session_cases),
                "full_actuation_base_count": sum(
                    row["full_actuation_base_count"] for row in session_cases
                ),
                "occupied_arrival_seconds": sum(
                    row["occupied_arrival_seconds"] for row in session_cases
                ),
                "count_alpha_ratio_of_sums": sum(
                    row["observed_pedestrians"] for row in session_cases
                )
                / sum(row["base_count"] for row in session_cases),
                "count_alpha_mean_leg": statistics.fmean(
                    row["count_alpha"] for row in session_cases
                ),
                "compliant_signal_delay_s": sum(
                    row["compliant_signal_delay_s"] for row in session_cases
                ),
                "model_delay_s": sum(
                    row["model_delay_s"] for row in session_cases
                ),
                "delay_alpha_ratio_of_sums": sum(
                    row["compliant_signal_delay_s"] for row in session_cases
                )
                / sum(row["model_delay_s"] for row in session_cases),
                "delay_alpha_mean_leg": statistics.fmean(
                    row["delay_alpha"] for row in session_cases
                ),
                "realised_delay_alpha_ratio_of_sums": (
                    sum(
                        row["realised_restrictive_delay_s"]
                        for row in session_cases
                    )
                    / sum(row["model_delay_s"] for row in session_cases)
                ),
                "realised_delay_alpha_mean_leg": statistics.fmean(
                    row["realised_delay_alpha"] for row in session_cases
                ),
            }
        )

    count_alphas = [row["count_alpha"] for row in case_rows]
    delay_alphas = [row["delay_alpha"] for row in case_rows]
    realised_delay_alphas = [row["realised_delay_alpha"] for row in case_rows]
    total_observed = sum(row["observed_pedestrians"] for row in case_rows)
    total_base = sum(row["base_count"] for row in case_rows)
    total_full_actuation_base = sum(
        row["full_actuation_base_count"] for row in case_rows
    )
    total_occupied_arrival_seconds = sum(
        row["occupied_arrival_seconds"] for row in case_rows
    )
    total_compliant_delay_s = sum(
        row["compliant_signal_delay_s"] for row in case_rows
    )
    total_model_delay_s = sum(row["model_delay_s"] for row in case_rows)
    restrictive_arrivals = sum(
        row["delay_covered_arrivals"] for row in case_rows
    )
    known_arrivals = sum(
        row["signal_at_arrival_exact"] is not None for row in arrival_rows
    )
    eligible_actuator_users = sum(
        row["eligible_actuator_user"] for row in arrival_rows
    )
    arrival_state_counts = {
        state: sum(row["signal_at_arrival_exact"] == state for row in arrival_rows)
        for state in ("G", "FR", "R")
    }
    actuator_state_counts = {
        state: sum(
            row["actuator_user"] and row["signal_at_arrival_exact"] == state
            for row in arrival_rows
        )
        for state in ("G", "FR", "R")
    }

    loo_predictions = []
    for index, row in enumerate(case_rows):
        training_mean = statistics.fmean(
            other["count_alpha"]
            for other_index, other in enumerate(case_rows)
            if other_index != index
        )
        prediction = training_mean * row["base_count"]
        loo_predictions.append((prediction, row["observed_pedestrians"]))

    red_shares = [row["red_share"] for row in case_rows]
    summary_values = {
        "source_version": "choy_final_data_20260720",
        "press_time_assumption": "actuator-positive pedestrian presses at recorded arrival",
        "case_definition": "session by physical crossing leg",
        "raw_pedestrian_rows": raw_pedestrian_rows,
        "mapped_pedestrian_rows": total_observed,
        "missing_leg_rows": missing_leg_rows,
        "known_signal_at_arrival_rows": known_arrivals,
        "signal_unknown_arrival_rows": total_observed - known_arrivals,
        "walk_arrivals": arrival_state_counts["G"],
        "flashing_red_arrivals": arrival_state_counts["FR"],
        "red_arrivals": arrival_state_counts["R"],
        "restrictive_arrivals": restrictive_arrivals,
        "actuator_users_all_states": sum(
            row["actuator_user"] for row in arrival_rows
        ),
        "actuator_users_on_walk": actuator_state_counts["G"],
        "actuator_users_on_flashing_red": actuator_state_counts["FR"],
        "actuator_users_on_red": actuator_state_counts["R"],
        "eligible_actuator_users": eligible_actuator_users,
        "behavioural_alpha_known_all_over_eligible": known_arrivals
        / eligible_actuator_users,
        "cases": len(case_rows),
        "observed_pedestrians": total_observed,
        "service_opportunities": sum(
            row["service_opportunities"] for row in case_rows
        ),
        "first_actuation_cycles": sum(
            row["first_actuation_cycles"] for row in case_rows
        ),
        "no_actuation_cycles": sum(
            row["no_actuation_cycles"] for row in case_rows
        ),
        "base_count": total_base,
        "full_actuation_first_arrival_cycles": sum(
            row["full_actuation_first_arrival_cycles"] for row in case_rows
        ),
        "full_actuation_risk_exposure_s": sum(
            row["full_actuation_risk_exposure_s"] for row in case_rows
        ),
        "full_actuation_base_count": total_full_actuation_base,
        "occupied_arrival_seconds": total_occupied_arrival_seconds,
        "missing_actuation_multiplier_ratio_of_sums": (
            total_full_actuation_base / total_base
        ),
        "people_per_occupied_second_ratio_of_sums": (
            total_observed / total_occupied_arrival_seconds
        ),
        "remaining_timing_model_factor_ratio_of_sums": (
            total_occupied_arrival_seconds / total_full_actuation_base
        ),
        "decomposition_product_check": (
            (total_full_actuation_base / total_base)
            * (total_observed / total_occupied_arrival_seconds)
            * (total_occupied_arrival_seconds / total_full_actuation_base)
        ),
        "count_alpha_mean_case": statistics.fmean(count_alphas),
        "count_alpha_median_case": statistics.median(count_alphas),
        "count_alpha_min_case": min(count_alphas),
        "count_alpha_max_case": max(count_alphas),
        "count_alpha_ratio_of_sums": total_observed / total_base,
        "count_alpha_red_share_correlation": correlation(red_shares, count_alphas),
        "loo_predicted_pedestrians": sum(value[0] for value in loo_predictions),
        "loo_mape": statistics.fmean(
            abs(predicted - observed) / observed
            for predicted, observed in loo_predictions
        ),
        "mcav_mean_predicted_pedestrians": MCAV_COUNT_ALPHA_MEAN * total_base,
        "mcav_mean_prediction_error_fraction": (
            MCAV_COUNT_ALPHA_MEAN * total_base / total_observed - 1.0
        ),
        "compliant_signal_delay_s": total_compliant_delay_s,
        "compliant_signal_delay_h": total_compliant_delay_s / 3600.0,
        "model_delay_s": total_model_delay_s,
        "model_delay_h": total_model_delay_s / 3600.0,
        "delay_alpha_mean_case": statistics.fmean(delay_alphas),
        "delay_alpha_median_case": statistics.median(delay_alphas),
        "delay_alpha_min_case": min(delay_alphas),
        "delay_alpha_max_case": max(delay_alphas),
        "delay_alpha_ratio_of_sums": total_compliant_delay_s / total_model_delay_s,
        "realised_delay_alpha_mean_case": statistics.fmean(realised_delay_alphas),
        "realised_delay_alpha_median_case": statistics.median(
            realised_delay_alphas
        ),
        "realised_delay_alpha_min_case": min(realised_delay_alphas),
        "realised_delay_alpha_max_case": max(realised_delay_alphas),
        "realised_delay_alpha_ratio_of_sums": (
            sum(row["realised_restrictive_delay_s"] for row in case_rows)
            / total_model_delay_s
        ),
        "realised_restrictive_delay_s": sum(
            row["realised_restrictive_delay_s"] for row in case_rows
        ),
        "realised_restrictive_delay_h": sum(
            row["realised_restrictive_delay_s"] for row in case_rows
        )
        / 3600.0,
        "noncompliers_exact": sum(row["noncompliers"] for row in case_rows),
        "noncompliance_saving_s": sum(
            row["noncompliance_saving_s"] for row in case_rows
        ),
        "noncompliance_saving_h": sum(
            row["noncompliance_saving_s"] for row in case_rows
        )
        / 3600.0,
        "startup_lag_s": STARTUP_LAG_S,
        "compliant_delay_plus_startup_h": (
            total_compliant_delay_s + STARTUP_LAG_S * restrictive_arrivals
        )
        / 3600.0,
    }
    summary_rows = [
        {"metric": key, "value": format_value(value)}
        for key, value in summary_values.items()
    ]

    # Reconcile the upstream replay to the published processed table and the
    # exact cycle census before any manuscript-facing outputs are written.
    expected_counts = {
        "raw_pedestrian_rows": 2004,
        "mapped_pedestrian_rows": 2003,
        "missing_leg_rows": 1,
        "known_signal_at_arrival_rows": 2001,
        "signal_unknown_arrival_rows": 2,
        "walk_arrivals": 372,
        "flashing_red_arrivals": 367,
        "red_arrivals": 1262,
        "restrictive_arrivals": 1629,
        "actuator_users_all_states": 799,
        "eligible_actuator_users": 758,
        "cases": 24,
        "service_opportunities": 1462,
        "first_actuation_cycles": 607,
        "no_actuation_cycles": 855,
        "full_actuation_first_arrival_cycles": 842,
        "occupied_arrival_seconds": 1701,
    }
    for metric, expected in expected_counts.items():
        actual = summary_values[metric]
        if actual != expected:
            raise ValueError(f"Reconciliation failed for {metric}: {actual} != {expected}")

    write_csv(VALIDATION_DIR / "video_upstream_source_manifest.csv", manifest_rows)
    write_csv(VALIDATION_DIR / "video_upstream_peer_cases.csv", case_rows)
    write_csv(VALIDATION_DIR / "video_upstream_peer_cycles.csv", cycle_rows)
    write_csv(VALIDATION_DIR / "video_upstream_peer_arrivals.csv", arrival_rows)
    write_csv(VALIDATION_DIR / "video_upstream_peer_sessions.csv", session_rows)
    write_csv(VALIDATION_DIR / "video_upstream_peer_summary.csv", summary_rows)

    print("Video upstream peer analysis complete")
    for key in (
        "cases",
        "observed_pedestrians",
        "service_opportunities",
        "first_actuation_cycles",
        "no_actuation_cycles",
        "base_count",
        "full_actuation_base_count",
        "occupied_arrival_seconds",
        "missing_actuation_multiplier_ratio_of_sums",
        "people_per_occupied_second_ratio_of_sums",
        "remaining_timing_model_factor_ratio_of_sums",
        "decomposition_product_check",
        "count_alpha_mean_case",
        "count_alpha_ratio_of_sums",
        "loo_predicted_pedestrians",
        "loo_mape",
        "mcav_mean_predicted_pedestrians",
        "mcav_mean_prediction_error_fraction",
        "compliant_signal_delay_h",
        "model_delay_h",
        "delay_alpha_mean_case",
        "delay_alpha_ratio_of_sums",
        "realised_restrictive_delay_h",
        "noncompliers_exact",
        "noncompliance_saving_h",
        "compliant_delay_plus_startup_h",
    ):
        print(f"{key}: {summary_values[key]}")


if __name__ == "__main__":
    main()
