"""Buck-converter waveform metrics."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from math import isfinite
from statistics import median
from typing import Any, Iterable

from .raw import RawPlot


CSV_FIELDS = (
    "case_id", "case_type", "status", "case_pass", "fsw_hz", "vout_avg_v",
    "ripple_v_pp", "settling_time_s", "min_vout_v", "max_vout_v",
    "recovery_time_s", "peak_inductor_current_a", "errors",
)


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a quantile from no samples")
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = int(position)
    fraction = position - lower
    if lower + 1 >= len(ordered):
        return ordered[-1]
    return ordered[lower] * (1.0 - fraction) + ordered[lower + 1] * fraction


def _interp(times: list[float], values: list[float], x: float) -> float:
    if x < times[0] or x > times[-1]:
        raise ValueError("requested interval lies outside waveform")
    j = bisect_left(times, x)
    if j < len(times) and times[j] == x:
        return values[j]
    if j == 0 or j >= len(times):
        raise ValueError("cannot interpolate waveform boundary")
    t0, t1 = times[j - 1], times[j]
    y0, y1 = values[j - 1], values[j]
    return y0 + (y1 - y0) * ((x - t0) / (t1 - t0))


def _segment(times: list[float], values: list[float], start: float, end: float) -> tuple[list[float], list[float]]:
    if not start < end:
        raise ValueError("analysis interval is empty")
    if start < times[0] or end > times[-1]:
        raise ValueError("analysis interval lies outside waveform")
    left = bisect_right(times, start)
    right = bisect_left(times, end)
    xs = [start] + times[left:right] + [end]
    ys = [_interp(times, values, start)] + values[left:right] + [_interp(times, values, end)]
    return xs, ys


def _time_mean(times: list[float], values: list[float], start: float, end: float) -> float:
    xs, ys = _segment(times, values, start, end)
    area = sum((xs[i + 1] - xs[i]) * (ys[i + 1] + ys[i]) * 0.5 for i in range(len(xs) - 1))
    return area / (end - start)


def _interval_minmax(times: list[float], values: list[float], start: float, end: float) -> tuple[float, float]:
    _, ys = _segment(times, values, start, end)
    return min(ys), max(ys)


def _rising_edges(times: list[float], gate: list[float], start: float, end: float) -> list[float]:
    xs, ys = _segment(times, gate, start, end)
    low = _quantile(ys, 0.05)
    high = _quantile(ys, 0.95)
    if high - low <= max(1e-9, abs(high) * 1e-6):
        raise ValueError("gate waveform has no usable logic swing")
    threshold = (low + high) * 0.5
    edges: list[float] = []
    for i in range(1, len(xs)):
        if ys[i - 1] < threshold <= ys[i] and ys[i] != ys[i - 1]:
            fraction = (threshold - ys[i - 1]) / (ys[i] - ys[i - 1])
            edges.append(xs[i - 1] + fraction * (xs[i] - xs[i - 1]))
    return edges


def _last_outside_then_settled(
    times: list[float], values: list[float], start: float, end: float,
    target: float, band_fraction: float,
) -> float:
    xs, ys = _segment(times, values, start, end)
    lower, upper = target * (1.0 - band_fraction), target * (1.0 + band_fraction)
    last_outside = -1
    for i, value in enumerate(ys):
        if not (lower <= value <= upper):
            last_outside = i
    if last_outside == len(ys) - 1:
        raise ValueError("waveform never settles")
    return xs[last_outside + 1]


def _recovery_time(
    times: list[float], values: list[float], event: float, end: float,
    target: float, band_fraction: float, hold_time: float,
) -> float:
    xs, ys = _segment(times, values, event, end)
    lower, upper = target * (1.0 - band_fraction), target * (1.0 + band_fraction)
    for i, candidate in enumerate(xs):
        hold_end = candidate + hold_time
        if hold_end > end:
            break
        j = bisect_right(xs, hold_end)
        window = ys[i:j]
        window.append(_interp(times, values, hold_end))
        if window and min(window) >= lower and max(window) <= upper:
            return candidate - event
    raise ValueError("waveform does not recover for the required hold time")


def _float(case: dict[str, str], key: str, required: bool = True) -> float | None:
    text = (case.get(key) or "").strip()
    if not text:
        if required:
            raise ValueError(f"manifest field {key} is required")
        return None
    value = float(text)
    if not isfinite(value):
        raise ValueError(f"manifest field {key} is non-finite")
    return value


def _normalized_signals(plot: RawPlot, case: dict[str, str]) -> dict[str, list[float]]:
    lookup = {name.casefold(): index for index, name in enumerate(plot.variables)}
    requested = {
        "time": case["time_var"],
        "vout": case["vout_var"],
        "gate": case["gate_var"],
        "inductor": case["inductor_current_var"],
        "load": case["load_current_var"],
    }
    indices: dict[str, int] = {}
    for role, name in requested.items():
        try:
            indices[role] = lookup[name.casefold()]
        except KeyError as exc:
            raise ValueError(f"required signal {name!r} is missing") from exc

    latest: dict[float, tuple[float, ...]] = {}
    for row in plot.rows:
        latest[row[indices["time"]]] = row
    ordered = sorted(latest.items())
    if len(ordered) < 3:
        raise ValueError("waveform has fewer than three unique timestamps")
    times = [item[0] for item in ordered]
    if any(times[i] >= times[i + 1] for i in range(len(times) - 1)):
        raise ValueError("timestamps cannot be normalized")
    return {
        role: [row[index] for _, row in ordered]
        for role, index in indices.items()
    }


def analyze_case(plot: RawPlot, case: dict[str, str], requirements: dict[str, Any]) -> dict[str, Any]:
    """Analyze one manifest case and return one output row."""
    signals = _normalized_signals(plot, case)
    times = signals["time"]
    start = _float(case, "analysis_start_s")
    end = _float(case, "analysis_end_s")
    assert start is not None and end is not None
    edges = _rising_edges(times, signals["gate"], start, end)
    if len(edges) < 2:
        raise ValueError("fewer than two gate rising edges in analysis interval")
    periods = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
    period = median(periods)
    if period <= 0:
        raise ValueError("invalid switching period")
    fsw = 1.0 / period

    steady_cycles = int(requirements["steady_cycles"])
    if len(edges) < steady_cycles + 1:
        raise ValueError("not enough complete cycles for steady-state metrics")
    steady_start, steady_end = edges[-(steady_cycles + 1)], edges[-1]
    vout_avg = _time_mean(times, signals["vout"], steady_start, steady_end)
    steady_min, steady_max = _interval_minmax(times, signals["vout"], steady_start, steady_end)
    peak_current = max(abs(value) for value in _segment(times, signals["inductor"], start, end)[1])

    result: dict[str, Any] = {
        "case_id": case["case_id"],
        "case_type": case["case_type"].strip().lower(),
        "status": "ok",
        "fsw_hz": fsw,
        "vout_avg_v": vout_avg,
        "ripple_v_pp": steady_max - steady_min,
        "settling_time_s": None,
        "min_vout_v": None,
        "max_vout_v": None,
        "recovery_time_s": None,
        "peak_inductor_current_a": peak_current,
        "errors": "",
    }

    if result["case_type"] == "startup":
        settling_abs = _last_outside_then_settled(
            times, signals["vout"], start, steady_start, vout_avg,
            float(requirements["startup_settling_time_s"]["band_fraction"]),
        )
        result["settling_time_s"] = settling_abs - start
    elif result["case_type"] == "step":
        event = _float(case, "event_time_s")
        assert event is not None
        observation_end = min(end, event + int(requirements["post_step_observation_cycles"]) * period)
        minimum, maximum = _interval_minmax(times, signals["vout"], event, observation_end)
        result["min_vout_v"] = minimum
        result["max_vout_v"] = maximum
        result["recovery_time_s"] = _recovery_time(
            times, signals["vout"], event, end, vout_avg,
            float(requirements["step_recovery_time_s"]["band_fraction"]),
            int(requirements["step_recovery_time_s"]["hold_periods"]) * period,
        )
    else:
        raise ValueError(f"unsupported case_type {result['case_type']!r}")

    checks = evaluate_case(result, requirements)
    result["checks"] = checks
    result["case_pass"] = all(checks.values())
    return result


def evaluate_case(metrics: dict[str, Any], requirements: dict[str, Any]) -> dict[str, bool]:
    """Evaluate one metric row against the supplied requirements."""
    checks = {
        "switching_frequency": requirements["switching_frequency_hz"]["min"] <= metrics["fsw_hz"] <= requirements["switching_frequency_hz"]["max"],
        "steady_state_vout": requirements["steady_state_vout_v"]["min"] <= metrics["vout_avg_v"] <= requirements["steady_state_vout_v"]["max"],
        "steady_state_ripple": metrics["ripple_v_pp"] <= requirements["steady_state_ripple_v_pp"]["max"],
        "peak_inductor_current": metrics["peak_inductor_current_a"] <= requirements["peak_inductor_current_a"]["max"],
    }
    if metrics["case_type"] == "startup":
        checks["startup_settling"] = metrics["settling_time_s"] <= requirements["startup_settling_time_s"]["max"]
    elif metrics["case_type"] == "step":
        checks.update({
            "step_min_vout": metrics["min_vout_v"] >= requirements["step_min_vout_v"]["min"],
            "step_max_vout": metrics["max_vout_v"] <= requirements["step_max_vout_v"]["max"],
            "step_recovery": metrics["recovery_time_s"] <= requirements["step_recovery_time_s"]["max"],
        })
    return checks
