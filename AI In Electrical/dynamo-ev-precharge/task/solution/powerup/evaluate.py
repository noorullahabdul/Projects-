from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable

from .io import CaseInputError, FatalInputError, load_capture, load_index, validate_case

PRECEDENCE = [
    "WELDED_CONTACTOR", "UNSAFE_CLOSE", "LOW_ISOLATION",
    "REPEATED_PRECHARGE_FAILURE", "BYPASS_OR_SHORT", "OPEN_PRECHARGE",
    "PRECHARGE_TIMEOUT", "SENSOR_BIAS", "RESIDUAL_LINK", "CONTACT_BOUNCE",
    "AUX_TIMEOUT", "OK",
]
PRECHARGE_FAILURE_CODES = {"BYPASS_OR_SHORT", "OPEN_PRECHARGE", "PRECHARGE_TIMEOUT"}
DIGITAL_CHANNELS = ("pre_cmd", "pre_aux", "pos_cmd", "pos_aux", "neg_cmd", "neg_aux", "crash")
AUX_PAIRS = (("pre", "pre_cmd", "pre_aux"), ("pos", "pos_cmd", "pos_aux"), ("neg", "neg_cmd", "neg_aux"))
METRIC_KEYS = (
    "precharge_start_ms", "ready_at_ms", "ready_delay_ms", "ready_link_v",
    "final_link_ratio", "peak_abs_pack_a", "max_link_slew_v_per_ms", "tau_ms",
    "aux_delay_ms", "aux_edges",
)


def rounded(value: float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def invalid_metrics() -> dict[str, Any]:
    return {
        "precharge_start_ms": None,
        "ready_at_ms": None,
        "ready_delay_ms": None,
        "ready_link_v": None,
        "final_link_ratio": None,
        "peak_abs_pack_a": None,
        "max_link_slew_v_per_ms": None,
        "tau_ms": None,
        "aux_delay_ms": {"neg": None, "pos": None, "pre": None},
        "aux_edges": {"neg": 0, "pos": 0, "pre": 0},
    }


def edges(rows: list[dict[str, Any]], channel: str) -> list[tuple[float, str, int]]:
    previous = 0
    out: list[tuple[float, str, int]] = []
    for row in rows:
        current = int(row[channel])
        if current != previous:
            out.append((float(row["t_ms"]), "rise" if current else "fall", current))
        previous = current
    return out


def first_rise(rows: list[dict[str, Any]], channel: str) -> float | None:
    for time, kind, _ in edges(rows, channel):
        if kind == "rise":
            return time
    return None


def first_rise_at_or_after(
    rows: list[dict[str, Any]], channel: str, earliest: float
) -> float | None:
    """Return the first channel rise at or after ``earliest``.

    A stale or bouncing auxiliary rise before its command must not be used as
    the command-to-feedback delay.
    """
    for time, kind, _ in edges(rows, channel):
        if kind == "rise" and time >= earliest:
            return time
    return None


def row_at_time(rows: list[dict[str, Any]], time: float) -> dict[str, Any]:
    for row in reversed(rows):
        if float(row["t_ms"]) <= time:
            return row
    return rows[0]


def interpolate(rows: list[dict[str, Any]], time: float, key: str) -> float:
    if time < float(rows[0]["t_ms"]) or time > float(rows[-1]["t_ms"]):
        raise ValueError("time is outside capture")
    for row in rows:
        if float(row["t_ms"]) == time:
            return float(row[key])
    for left, right in zip(rows, rows[1:]):
        t0, t1 = float(left["t_ms"]), float(right["t_ms"])
        if t0 < time < t1:
            fraction = (time - t0) / (t1 - t0)
            return float(left[key]) + fraction * (float(right[key]) - float(left[key]))
    return float(rows[-1][key])


def crossing(rows: list[dict[str, Any]], start: float, func) -> float | None:
    points = [row for row in rows if float(row["t_ms"]) >= start]
    if not points:
        return None
    first = points[0]
    v0 = float(func(first))
    if v0 >= 0:
        return float(first["t_ms"])
    previous = first
    previous_value = v0
    for current in points[1:]:
        value = float(func(current))
        if value >= 0 and previous_value < 0:
            t0, t1 = float(previous["t_ms"]), float(current["t_ms"])
            if value == previous_value:
                return t1
            fraction = -previous_value / (value - previous_value)
            return t0 + fraction * (t1 - t0)
        previous, previous_value = current, value
    return None


def unequal_spans(rows: list[dict[str, Any]], left: str, right: str) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    started: float | None = None
    for row in rows:
        time = float(row["t_ms"])
        mismatch = int(row[left]) != int(row[right])
        if mismatch and started is None:
            started = time
        elif not mismatch and started is not None:
            spans.append((started, time))
            started = None
    if started is not None:
        spans.append((started, float(rows[-1]["t_ms"])))
    return spans


def weld_spans(rows: list[dict[str, Any]], cmd: str, aux: str) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    started: float | None = None
    for row in rows:
        time = float(row["t_ms"])
        active = int(row[aux]) == 1 and int(row[cmd]) == 0
        if active and started is None:
            started = time
        elif not active and started is not None:
            spans.append((started, time))
            started = None
    if started is not None:
        spans.append((started, float(rows[-1]["t_ms"])))
    return spans


def condition_spans(rows: list[dict[str, Any]], predicate) -> list[tuple[float, float]]:
    """Return sampled time spans for which ``predicate(row)`` is true."""
    spans: list[tuple[float, float]] = []
    started: float | None = None
    for row in rows:
        time = float(row["t_ms"])
        active = bool(predicate(row))
        if active and started is None:
            started = time
        elif not active and started is not None:
            spans.append((started, time))
            started = None
    if started is not None:
        spans.append((started, float(rows[-1]["t_ms"])))
    return spans


def window_metrics(rows: list[dict[str, Any]], start: float, end: float) -> tuple[float, float]:
    currents = [abs(interpolate(rows, start, "pack_a")), abs(interpolate(rows, end, "pack_a"))]
    for row in rows:
        time = float(row["t_ms"])
        if start <= time <= end:
            currents.append(abs(float(row["pack_a"])))
    slopes: list[float] = []
    for left, right in zip(rows, rows[1:]):
        t0, t1 = float(left["t_ms"]), float(right["t_ms"])
        if t1 <= start or t0 >= end:
            continue
        slope = (float(right["link_v"]) - float(left["link_v"])) / (t1 - t0)
        if slope > 0:
            slopes.append(slope)
    return max(currents), max(slopes, default=0.0)


def build_metrics(rows: list[dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    limits = case["limits"]
    start = first_rise(rows, "pre_cmd")
    ready = None
    ready_link = None
    tau = None
    peak = None
    slew = None
    if start is not None:
        ready = crossing(rows, start, lambda row: float(row["link_v"]) - limits["ready_ratio"] * float(row["pack_v"]))
        if ready is not None:
            ready_link = interpolate(rows, ready, "link_v")
        start_pack = interpolate(rows, start, "pack_v")
        start_link = interpolate(rows, start, "link_v")
        target = start_link + 0.6321205588 * (start_pack - start_link)
        tau_cross = crossing(rows, start, lambda row: float(row["link_v"]) - target)
        if tau_cross is not None:
            tau = tau_cross - start
        window_end = min(float(rows[-1]["t_ms"]), start + limits["max_precharge_ms"], ready if ready is not None else math.inf)
        peak, slew = window_metrics(rows, start, window_end)
    delays: dict[str, float | None] = {}
    counts: dict[str, int] = {}
    for name, cmd, aux in AUX_PAIRS:
        cmd_time = first_rise(rows, cmd)
        aux_time = None if cmd_time is None else first_rise_at_or_after(rows, aux, cmd_time)
        delays[name] = None if cmd_time is None or aux_time is None else aux_time - cmd_time
        counts[name] = len(edges(rows, aux))
    final_pack = float(rows[-1]["pack_v"])
    final_ratio = None if final_pack == 0 else float(rows[-1]["link_v"]) / final_pack
    return {
        "precharge_start_ms": rounded(start),
        "ready_at_ms": rounded(ready),
        "ready_delay_ms": rounded(None if ready is None or start is None else ready - start),
        "ready_link_v": rounded(ready_link),
        "final_link_ratio": rounded(final_ratio),
        "peak_abs_pack_a": rounded(peak),
        "max_link_slew_v_per_ms": rounded(slew),
        "tau_ms": rounded(tau),
        "aux_delay_ms": {key: rounded(delays[key]) for key in sorted(delays)},
        "aux_edges": {key: counts[key] for key in sorted(counts)},
    }


def evaluate_rules(rows: list[dict[str, Any]], case: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    limits = case["limits"]
    found: dict[str, tuple[float | None, str]] = {}
    def add(code: str, time: float | None, detail: str) -> None:
        found.setdefault(code, (time, detail))

    for name, cmd, aux in (("positive", "pos_cmd", "pos_aux"), ("negative", "neg_cmd", "neg_aux")):
        for begin, end in weld_spans(rows, cmd, aux):
            if end - begin > limits["weld_dwell_ms"]:
                add("WELDED_CONTACTOR", begin + limits["weld_dwell_ms"], f"{name} auxiliary stayed closed without command")
                break

    ready = metrics["ready_at_ms"]
    for row in rows:
        time = float(row["t_ms"])
        pack = float(row["pack_v"])
        ratio = math.inf if pack == 0 else float(row["link_v"]) / pack
        mains_closed = int(row["pos_aux"]) == 1 and int(row["neg_aux"]) == 1
        if mains_closed and (ready is None or time < ready or ratio < limits["safe_close_ratio"] or float(row["iso_kohm"]) < limits["isolation_min_kohm"] or int(row["crash"]) == 1):
            add("UNSAFE_CLOSE", time, "both main auxiliaries closed before all safety conditions were satisfied")
            break

    for row in rows:
        active = any(int(row[key]) for key in ("pre_cmd", "pre_aux", "pos_cmd", "pos_aux", "neg_cmd", "neg_aux"))
        if active and float(row["iso_kohm"]) < limits["isolation_min_kohm"]:
            add("LOW_ISOLATION", float(row["t_ms"]), "isolation was below the configured floor while the HV path was active")
            break

    expected_tau = case["precharge_ohm"] * case["capacitance_uf"] / 1000.0
    expected_ready = -math.log(1.0 - limits["ready_ratio"]) * expected_tau
    if metrics["tau_ms"] is not None and metrics["tau_ms"] <= limits["short_tau_factor"] * expected_tau:
        add("BYPASS_OR_SHORT", metrics["precharge_start_ms"] + metrics["tau_ms"], "measured RC time constant was implausibly fast")
    elif metrics["ready_delay_ms"] is not None and metrics["ready_delay_ms"] <= limits["short_tau_factor"] * expected_ready:
        add("BYPASS_OR_SHORT", metrics["ready_at_ms"], "readiness was reached implausibly fast")

    start = metrics["precharge_start_ms"]
    if start is not None:
        probe = start + limits["open_check_ms"]
        if probe <= float(rows[-1]["t_ms"]):
            start_pack = interpolate(rows, start, "pack_v")
            start_link = interpolate(rows, start, "link_v")
            probe_pack = interpolate(rows, probe, "pack_v")
            probe_link = interpolate(rows, probe, "link_v")
            initial_ratio = math.inf if start_pack == 0 else start_link / start_pack
            probe_ratio = math.inf if probe_pack == 0 else probe_link / probe_pack
            pre_aux = int(row_at_time(rows, probe)["pre_aux"])
            if pre_aux == 1 and initial_ratio < limits["ready_ratio"] and probe_ratio - initial_ratio <= limits["open_min_rise_ratio"]:
                add("OPEN_PRECHARGE", probe, "link voltage did not rise enough during the open-path probe")
        deadline = start + limits["max_precharge_ms"]
        if "OPEN_PRECHARGE" not in found and (ready is None or ready > deadline):
            add("PRECHARGE_TIMEOUT", deadline, "readiness was not achieved by the deadline")

    # After readiness and both main contactors are confirmed closed, a
    # persistent pack/link disagreement indicates a biased voltage channel.
    if ready is not None:
        def sensor_bias_active(row: dict[str, Any]) -> bool:
            time = float(row["t_ms"])
            if time < ready or int(row["pos_aux"]) != 1 or int(row["neg_aux"]) != 1:
                return False
            pack = float(row["pack_v"])
            link = float(row["link_v"])
            threshold = max(
                limits["sensor_bias_abs_v"],
                limits["sensor_bias_ratio"] * abs(pack),
            )
            return abs(pack - link) > threshold

        for begin, end in condition_spans(rows, sensor_bias_active):
            if end - begin > limits["sensor_bias_dwell_ms"]:
                add(
                    "SENSOR_BIAS",
                    begin + limits["sensor_bias_dwell_ms"],
                    "pack and link voltage disagreed after both main contactors closed",
                )
                break

    first_command_times = [time for channel in ("pre_cmd", "pos_cmd", "neg_cmd") for time, kind, _ in edges(rows, channel) if kind == "rise"]
    first_command = min(first_command_times, default=math.inf)
    for row in rows:
        time = float(row["t_ms"])
        if time >= first_command:
            break
        if int(row["pos_aux"]) == 0 and int(row["neg_aux"]) == 0:
            pack = float(row["pack_v"])
            link = float(row["link_v"])
            if link > limits["residual_abs_v"] and link > limits["residual_ratio"] * pack:
                add("RESIDUAL_LINK", time, "DC-link voltage was excessive before any command")
                break

    for name, _, aux in AUX_PAIRS:
        times = [time for time, _, _ in edges(rows, aux)]
        for previous, current in zip(times, times[1:]):
            if current - previous < limits["bounce_interval_ms"]:
                add("CONTACT_BOUNCE", current, f"{name} auxiliary transitioned twice inside the bounce interval")
                break

    for name, cmd, aux in AUX_PAIRS:
        for begin, end in unequal_spans(rows, cmd, aux):
            if end - begin > limits["aux_delay_ms"]:
                add("AUX_TIMEOUT", begin + limits["aux_delay_ms"], f"{name} command and auxiliary disagreed too long")
                break

    if not found:
        add("OK", float(rows[-1]["t_ms"]), "power-up sequence satisfied all configured rules")
    return [
        {"code": code, "time_ms": rounded(found[code][0]), "detail": found[code][1]}
        for code in PRECEDENCE if code in found
    ]


def digital_events(case_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for channel in DIGITAL_CHANNELS:
        for time, kind, state in edges(rows, channel):
            out.append({"case_id": case_id, "time_ms": time, "event": kind, "channel": channel, "value": str(state), "detail": "digital transition"})
    return out


def inspect_case(
    raw: Any, position: int, base: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    fallback = f"invalid_case_{position:04d}"
    case_id = raw.get("case_id") if isinstance(raw, dict) and isinstance(raw.get("case_id"), str) and raw.get("case_id").strip() else fallback
    session: dict[str, Any] | None = None
    try:
        case = validate_case(raw, position, base)
        session = case["session"]
        rows = load_capture(case["capture"])
        metrics = build_metrics(rows, case)
        evidence = evaluate_rules(rows, case, metrics)
        verdict = evidence[0]["code"]
        flags = [item["code"] for item in evidence[1:]]
        events = digital_events(case_id, rows)
        if metrics["ready_at_ms"] is not None:
            events.append({"case_id": case_id, "time_ms": metrics["ready_at_ms"], "event": "ready", "channel": "link_v", "value": f"{metrics['ready_link_v']:.6f}", "detail": "readiness threshold crossed"})
        events.append({"case_id": case_id, "time_ms": evidence[0]["time_ms"] if evidence[0]["time_ms"] is not None else 0.0, "event": "verdict", "channel": "system", "value": verdict, "detail": evidence[0]["detail"]})
        result = {"case_id": case_id, "input_state": "valid", "verdict": verdict, "flags": flags, "metrics": metrics, "evidence": evidence, "messages": []}
        return result, events, session
    except CaseInputError as exc:
        evidence = [{"code": "BAD_INPUT", "time_ms": None, "detail": str(exc)}]
        result = {"case_id": case_id, "input_state": "invalid", "verdict": "BAD_INPUT", "flags": [], "metrics": invalid_metrics(), "evidence": evidence, "messages": []}
        event = {"case_id": case_id, "time_ms": 0.0, "event": "verdict", "channel": "system", "value": "BAD_INPUT", "detail": str(exc)}
        return result, [event], session


def apply_session_rules(
    records: list[tuple[int, dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]]
) -> None:
    """Apply cross-capture retry diagnostics after all local rules are known.

    Only valid cases with validated session metadata participate.  Session cases
    are ordered by (attempt, case_id, original index position).  A valid case
    without a precharge-path failure resets the consecutive-failure streak.
    """
    groups: dict[str, list[tuple[int, dict[str, Any], list[dict[str, Any]], dict[str, Any]]]] = {}
    for position, result, case_events, session in records:
        if result["input_state"] != "valid" or session is None:
            continue
        groups.setdefault(session["session_id"], []).append((position, result, case_events, session))

    for members in groups.values():
        members.sort(key=lambda item: (item[3]["attempt"], item[1]["case_id"], item[0]))
        streak = 0
        for _position, result, case_events, _session in members:
            source_entries = [
                entry for entry in result["evidence"]
                if entry["code"] in PRECHARGE_FAILURE_CODES
            ]
            if not source_entries:
                streak = 0
                continue
            streak += 1
            if streak < 3:
                continue

            times = [entry["time_ms"] for entry in source_entries if entry["time_ms"] is not None]
            event_time = min(times) if times else 0.0
            repeated = {
                "code": "REPEATED_PRECHARGE_FAILURE",
                "time_ms": rounded(event_time),
                "detail": "three or more consecutive precharge-path failures in the same session",
            }
            by_code = {entry["code"]: entry for entry in result["evidence"]}
            by_code[repeated["code"]] = repeated
            evidence = [by_code[code] for code in PRECEDENCE if code in by_code]
            result["evidence"] = evidence
            result["verdict"] = evidence[0]["code"]
            result["flags"] = [entry["code"] for entry in evidence[1:]]

            verdict_event = next(event for event in case_events if event["event"] == "verdict")
            verdict_event["time_ms"] = evidence[0]["time_ms"] if evidence[0]["time_ms"] is not None else 0.0
            verdict_event["value"] = result["verdict"]
            verdict_event["detail"] = evidence[0]["detail"]


def write_report(path: Path, cases: list[dict[str, Any]]) -> None:
    histogram: dict[str, int] = {}
    for case in cases:
        histogram[case["verdict"]] = histogram.get(case["verdict"], 0) + 1
    ok_count = histogram.get("OK", 0)
    report = {
        "format": "hv-powerup-report/1",
        "cases": cases,
        "aggregate": {
            "case_count": len(cases),
            "ok_count": ok_count,
            "fault_count": len(cases) - ok_count,
            "verdict_histogram": {key: histogram[key] for key in sorted(histogram)},
        },
    }
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_events(path: Path, events: list[dict[str, Any]]) -> None:
    events.sort(key=lambda item: (item["case_id"], float(item["time_ms"]), item["event"], item["channel"], item["value"]))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["case_id", "time_ms", "event", "channel", "value", "detail"])
        for item in events:
            writer.writerow([item["case_id"], f"{float(item['time_ms']):.6f}", item["event"], item["channel"], item["value"], item["detail"]])


def inspect_cases(index_path: str | Path, output_dir: str | Path) -> tuple[int, int, int, Path]:
    index, raw_cases = load_index(index_path)
    destination = Path(output_dir).resolve()
    try:
        destination.mkdir(parents=True, exist_ok=True)
        probe = destination / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise FatalInputError(f"cannot create or write output directory: {exc}") from exc
    records: list[tuple[int, dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]] = []
    for position, raw in enumerate(raw_cases, start=1):
        result, case_events, session = inspect_case(raw, position, index.parent)
        records.append((position, result, case_events, session))
    apply_session_rules(records)
    results = [record[1] for record in records]
    events = [event for record in records for event in record[2]]
    results.sort(key=lambda item: item["case_id"])
    write_report(destination / "report.json", results)
    write_events(destination / "events.csv", events)
    ok = sum(1 for item in results if item["verdict"] == "OK")
    return len(results), ok, len(results) - ok, destination
