from __future__ import annotations

import csv
import json
import math
import os
import random
import subprocess
import sys
from contextlib import contextmanager
from bisect import bisect_left, bisect_right
from pathlib import Path
from statistics import median

import pytest


CSV_FIELDS = [
    "case_id", "case_type", "status", "case_pass", "fsw_hz", "vout_avg_v",
    "ripple_v_pp", "settling_time_s", "min_vout_v", "max_vout_v",
    "recovery_time_s", "peak_inductor_current_a", "errors",
]


def _run_cli(manifest: Path, requirements: Path, output: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "/app"
    return subprocess.run(
        [
            sys.executable, "-m", "buckvalidate.cli",
            "--manifest", str(manifest),
            "--requirements", str(requirements),
            "--output-dir", str(output),
        ],
        cwd="/app",
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )


def _write_plot(handle, title, plotname, variables, rows, layout="mixed") -> None:
    handle.write(f"Title: {title}\n")
    handle.write("Date: hidden verifier\n")
    handle.write(f"Plotname: {plotname}\n")
    handle.write("Flags: real forward\n")
    handle.write(f"No. Variables: {len(variables)}\n")
    handle.write(f"No. Points: {len(rows)}\n")
    handle.write("Variables:\n")
    for index, (name, kind) in enumerate(variables):
        handle.write(f"  {index}  {name}  {kind}\n")
    handle.write("Values:\n")
    for index, row in enumerate(rows):
        if layout == "same" or (layout == "mixed" and index % 4 == 0):
            handle.write(str(index) + " " + " ".join(f"{value:.14e}" for value in row) + "\n")
        else:
            handle.write(f"{index} {row[0]:.14e}\n")
            for value in row[1:]:
                handle.write(f"  {value:.14e}\n")
        if index and index % 353 == 0:
            handle.write("\n")


def _irregular_times(end: float, dt: float, seed: int, duplicate_every: int = 0) -> list[float]:
    rng = random.Random(seed)
    values: list[float] = []
    t = 0.0
    index = 0
    while t <= end:
        values.append(t)
        index += 1
        if duplicate_every and index % duplicate_every == 0:
            values.append(t)
        t += dt * (1.0 + rng.uniform(-0.18, 0.18))
    return values


def _tri(phase: float) -> float:
    x = phase % 1.0
    return 4.0 * x - 1.0 if x < 0.5 else 3.0 - 4.0 * x


def _make_startup(
    path: Path,
    fsw: float = 187_500.0,
    *,
    seed: int = 9917,
    duplicate_every: int = 577,
) -> tuple[list[float], dict[str, list[float]]]:
    period = 1.0 / fsw
    times = _irregular_times(0.0118, 0.72e-6, seed, duplicate_every=duplicate_every)
    signals = {"time": [], "vout": [], "gate": [], "il": [], "load": []}
    rows = []
    for index, t in enumerate(times):
        phase = (t / period) % 1.0
        gate = 12.0 if phase < 0.39 else 8.0
        vout = 12.02 * (1.0 - math.exp(-t / 0.00145)) + 0.055 * _tri(phase)
        load = 5.0
        il = load + 0.52 * _tri(phase + 0.14)
        # The later duplicate intentionally supersedes the earlier record.
        if index and t == times[index - 1]:
            vout += 0.002
        signals["time"].append(t)
        signals["vout"].append(vout)
        signals["gate"].append(gate)
        signals["il"].append(il)
        signals["load"].append(load)
        rows.append((gate, t, il, vout, load))
    variables = [
        ("V(GATE_HIDDEN)", "voltage"),
        ("TIME", "time"),
        ("I(L_HIDDEN)", "current"),
        ("V(OUT_HIDDEN)", "voltage"),
        ("I(LOAD_HIDDEN)", "current"),
    ]
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        _write_plot(handle, "decoy", "Operating Point", [("v(dummy)", "voltage")], [(0.0,)], "same")
        handle.write("\n")
        _write_plot(handle, "hidden startup", "Transient Analysis", variables, rows, "mixed")
    return times, signals


def _make_step(
    path: Path,
    fsw: float = 215_000.0,
    event: float = 0.0045,
    *,
    seed: int = 4421,
    duplicate_every: int = 619,
) -> tuple[list[float], dict[str, list[float]]]:
    period = 1.0 / fsw
    times = _irregular_times(0.0108, 0.62e-6, seed, duplicate_every=duplicate_every)
    signals = {"time": [], "vout": [], "gate": [], "il": [], "load": []}
    rows = []
    for index, t in enumerate(times):
        phase = (t / period) % 1.0
        gate = 9.0 if phase < 0.46 else 4.0
        load = 3.0 if t < event else 9.0
        dynamic = 0.0
        if t >= event:
            dt = t - event
            dynamic = -0.88 * math.exp(-dt / 0.00034) + 0.13 * math.exp(-((dt - 0.0014) / 0.00035) ** 2)
        vout = 11.98 + dynamic + 0.045 * _tri(phase)
        il = load + 0.64 * _tri(phase + 0.21)
        if index and t == times[index - 1]:
            gate += 0.01
        signals["time"].append(t)
        signals["vout"].append(vout)
        signals["gate"].append(gate)
        signals["il"].append(il)
        signals["load"].append(load)
        rows.append((t, load, vout, gate, il))
    variables = [
        ("time", "time"),
        ("i(load_x)", "current"),
        ("v(out_x)", "voltage"),
        ("v(gate_x)", "voltage"),
        ("i(lx)", "current"),
    ]
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        # A valid but irrelevant transient plot verifies that the final transient is selected.
        _write_plot(handle, "old run", "Transient Analysis", variables, [(0, 0, 1, 0, 0), (1e-6, 0, 1, 0, 0)], "same")
        handle.write("\n")
        _write_plot(handle, "hidden step", "transient analysis", variables, rows, "mixed")
    return times, signals


def _dedupe(times: list[float], signals: dict[str, list[float]]) -> tuple[list[float], dict[str, list[float]]]:
    last: dict[float, int] = {}
    for index, t in enumerate(times):
        last[t] = index
    ordered = sorted(last)
    return ordered, {name: [values[last[t]] for t in ordered] for name, values in signals.items() if name != "time"}


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(position)
    frac = position - low
    return ordered[low] if low + 1 == len(ordered) else ordered[low] * (1 - frac) + ordered[low + 1] * frac


def _interp(times: list[float], values: list[float], x: float) -> float:
    pos = bisect_left(times, x)
    if pos < len(times) and times[pos] == x:
        return values[pos]
    t0, t1 = times[pos - 1], times[pos]
    y0, y1 = values[pos - 1], values[pos]
    return y0 + (y1 - y0) * (x - t0) / (t1 - t0)


def _segment(times: list[float], values: list[float], start: float, end: float) -> tuple[list[float], list[float]]:
    left, right = bisect_right(times, start), bisect_left(times, end)
    return [start] + times[left:right] + [end], [_interp(times, values, start)] + values[left:right] + [_interp(times, values, end)]


def _mean(times: list[float], values: list[float], start: float, end: float) -> float:
    xs, ys = _segment(times, values, start, end)
    return sum((xs[i + 1] - xs[i]) * (ys[i + 1] + ys[i]) / 2 for i in range(len(xs) - 1)) / (end - start)


def _reference_metrics(times0: list[float], signals0: dict[str, list[float]], case_type: str, start: float, end: float, event: float | None, req: dict) -> dict[str, float]:
    times, signals = _dedupe(times0, signals0)
    xs, gate = _segment(times, signals["gate"], start, end)
    threshold = (_quantile(gate, 0.05) + _quantile(gate, 0.95)) / 2
    edges = []
    for i in range(1, len(xs)):
        if gate[i - 1] < threshold <= gate[i]:
            fraction = (threshold - gate[i - 1]) / (gate[i] - gate[i - 1])
            edges.append(xs[i - 1] + fraction * (xs[i] - xs[i - 1]))
    period = median([edges[i + 1] - edges[i] for i in range(len(edges) - 1)])
    steady_start, steady_end = edges[-(req["steady_cycles"] + 1)], edges[-1]
    vavg = _mean(times, signals["vout"], steady_start, steady_end)
    _, steady_v = _segment(times, signals["vout"], steady_start, steady_end)
    _, il = _segment(times, signals["il"], start, end)
    result = {
        "fsw_hz": 1 / period,
        "vout_avg_v": vavg,
        "ripple_v_pp": max(steady_v) - min(steady_v),
        "peak_inductor_current_a": max(abs(v) for v in il),
    }
    if case_type == "startup":
        _, vals = _segment(times, signals["vout"], start, steady_start)
        tx, _ = _segment(times, signals["vout"], start, steady_start)
        band = req["startup_settling_time_s"]["band_fraction"]
        low, high = vavg * (1 - band), vavg * (1 + band)
        last_bad = max((i for i, value in enumerate(vals) if not low <= value <= high), default=-1)
        result["settling_time_s"] = tx[last_bad + 1] - start
    else:
        assert event is not None
        obs_end = min(end, event + req["post_step_observation_cycles"] * period)
        _, vals = _segment(times, signals["vout"], event, obs_end)
        result["min_vout_v"], result["max_vout_v"] = min(vals), max(vals)
        band = req["step_recovery_time_s"]["band_fraction"]
        hold = req["step_recovery_time_s"]["hold_periods"] * period
        low, high = vavg * (1 - band), vavg * (1 + band)
        tx, vals = _segment(times, signals["vout"], event, end)
        recovery = None
        for i, candidate in enumerate(tx):
            if candidate + hold > end:
                break
            j = bisect_right(tx, candidate + hold)
            window = vals[i:j] + [_interp(times, signals["vout"], candidate + hold)]
            if min(window) >= low and max(window) <= high:
                recovery = candidate - event
                break
        assert recovery is not None
        result["recovery_time_s"] = recovery
    return result


def _read_outputs(output: Path) -> tuple[list[dict[str, str]], dict]:
    with (output / "measurements.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == CSV_FIELDS
        rows = list(reader)
    report = json.loads((output / "validation_report.json").read_text(encoding="utf-8"))
    return rows, report


def _requirements() -> dict:
    return json.loads(Path("/app/data/requirements.json").read_text(encoding="utf-8"))


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "case_id", "raw_path", "case_type", "analysis_start_s", "analysis_end_s", "event_time_s",
        "time_var", "vout_var", "gate_var", "inductor_current_var", "load_current_var",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)



NUMERIC_FIELDS = CSV_FIELDS[4:-1]
COMMON_CHECKS = {
    "switching_frequency",
    "steady_state_vout",
    "steady_state_ripple",
    "peak_inductor_current",
}
CHECK_RULES = {
    "switching_frequency": ("fsw_hz", "switching_frequency_hz"),
    "steady_state_vout": ("vout_avg_v", "steady_state_vout_v"),
    "steady_state_ripple": ("ripple_v_pp", "steady_state_ripple_v_pp"),
    "peak_inductor_current": ("peak_inductor_current_a", "peak_inductor_current_a"),
    "startup_settling": ("settling_time_s", "startup_settling_time_s"),
    "step_min_vout": ("min_vout_v", "step_min_vout_v"),
    "step_max_vout": ("max_vout_v", "step_max_vout_v"),
    "step_recovery": ("recovery_time_s", "step_recovery_time_s"),
}


def _check_keys(case_type: str) -> set[str]:
    if case_type == "startup":
        return COMMON_CHECKS | {"startup_settling"}
    if case_type == "step":
        return COMMON_CHECKS | {"step_min_vout", "step_max_vout", "step_recovery"}
    raise AssertionError(f"unexpected case type: {case_type}")


def _rule_pass(value: float, rule: dict) -> bool:
    return (
        ("min" not in rule or value >= float(rule["min"]))
        and ("max" not in rule or value <= float(rule["max"]))
    )


def _expected_checks(metrics: dict[str, float], case_type: str, req: dict) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for check in sorted(_check_keys(case_type)):
        metric_name, requirement_name = CHECK_RULES[check]
        result[check] = _rule_pass(float(metrics[metric_name]), req[requirement_name])
    return result


def _json_number_matches(csv_value: str, json_value) -> bool:
    if csv_value == "":
        return json_value is None
    return isinstance(json_value, (int, float)) and not isinstance(json_value, bool) and math.isclose(
        float(csv_value), float(json_value), rel_tol=1e-7, abs_tol=1e-10
    )


def _assert_artifact_integrity(rows: list[dict[str, str]], report: dict, req: dict) -> None:
    assert set(report) == {"schema_version", "overall_pass", "summary", "cases"}
    assert report["schema_version"] == 1
    assert set(report["summary"]) == {"total_cases", "valid_cases", "passed_cases"}
    assert isinstance(report["cases"], list)
    assert len(report["cases"]) == len(rows)

    valid_count = 0
    passed_count = 0
    json_cases = report["cases"]
    assert [case["case_id"] for case in json_cases] == [row["case_id"] for row in rows]

    for row, case in zip(rows, json_cases):
        assert set(case) == set(CSV_FIELDS) | {"checks"}
        assert case["case_id"] == row["case_id"]
        assert case["case_type"] == row["case_type"]
        assert case["status"] == row["status"]
        assert case["errors"] == row["errors"]
        assert row["case_pass"] in {"true", "false"}
        csv_pass = row["case_pass"] == "true"
        assert case["case_pass"] is csv_pass

        for field in NUMERIC_FIELDS:
            assert _json_number_matches(row[field], case[field]), (
                field, row[field], case[field]
            )

        if row["status"] == "invalid":
            assert csv_pass is False
            assert case["checks"] == {}
            assert row["errors"].strip()
            assert all(row[field] == "" for field in NUMERIC_FIELDS)
            continue

        assert row["status"] == "ok"
        valid_count += 1
        metrics = {field: float(row[field]) for field in NUMERIC_FIELDS if row[field] != ""}
        expected = _expected_checks(metrics, row["case_type"], req)
        assert set(case["checks"]) == _check_keys(row["case_type"])
        assert all(type(value) is bool for value in case["checks"].values())
        assert case["checks"] == expected
        assert csv_pass is all(expected.values())
        passed_count += int(csv_pass)

    assert report["summary"] == {
        "total_cases": len(rows),
        "valid_cases": valid_count,
        "passed_cases": passed_count,
    }
    assert report["overall_pass"] is (len(rows) > 0 and passed_count == len(rows))


def _assert_metrics_close(row: dict[str, str], expected: dict[str, float], case_type: str) -> None:
    assert float(row["fsw_hz"]) == pytest.approx(expected["fsw_hz"], rel=0.01)
    assert float(row["vout_avg_v"]) == pytest.approx(expected["vout_avg_v"], abs=0.02)
    assert float(row["ripple_v_pp"]) == pytest.approx(expected["ripple_v_pp"], abs=0.02)
    assert float(row["peak_inductor_current_a"]) == pytest.approx(
        expected["peak_inductor_current_a"], abs=0.05
    )
    if case_type == "startup":
        assert float(row["settling_time_s"]) == pytest.approx(
            expected["settling_time_s"], abs=0.0002
        )
        assert row["min_vout_v"] == row["max_vout_v"] == row["recovery_time_s"] == ""
    else:
        assert float(row["min_vout_v"]) == pytest.approx(expected["min_vout_v"], abs=0.02)
        assert float(row["max_vout_v"]) == pytest.approx(expected["max_vout_v"], abs=0.02)
        assert float(row["recovery_time_s"]) == pytest.approx(
            expected["recovery_time_s"], abs=0.0002
        )
        assert row["settling_time_s"] == ""


def _header_value(lines: list[str], key: str) -> str:
    prefix = key.lower() + ":"
    for line in lines:
        if line.lower().startswith(prefix):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"missing raw header {key!r}")


def _parse_final_transient(path: Path) -> tuple[list[float], dict[str, list[float]]]:
    """Independent, verifier-side parser for the documented ASCII raw subset."""
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    starts = [i for i, line in enumerate(lines) if line.lower().startswith("title:")]
    assert starts, f"no plots in {path}"
    starts.append(len(lines))
    plots: list[tuple[str, list[str], list[list[float]]]] = []

    for start, stop in zip(starts, starts[1:]):
        block = lines[start:stop]
        plotname = _header_value(block, "Plotname")
        nvars = int(_header_value(block, "No. Variables"))
        npoints = int(_header_value(block, "No. Points"))
        variables_i = next(i for i, line in enumerate(block) if line.strip().lower() == "variables:")
        values_i = next(i for i, line in enumerate(block) if line.strip().lower() == "values:")

        names: list[str] = []
        for line in block[variables_i + 1:values_i]:
            if not line.strip():
                continue
            parts = line.split()
            assert len(parts) >= 3
            names.append(parts[1])
        assert len(names) == nvars

        rows: list[list[float]] = []
        i = values_i + 1
        expected_index = 0
        while expected_index < npoints:
            while i < len(block) and not block[i].strip():
                i += 1
            assert i < len(block), f"truncated Values section in {path}"
            parts = block[i].split()
            i += 1
            assert int(parts[0]) == expected_index
            values = [float(token) for token in parts[1:]]
            while len(values) < nvars:
                while i < len(block) and not block[i].strip():
                    i += 1
                assert i < len(block), f"truncated point {expected_index} in {path}"
                values.extend(float(token) for token in block[i].split())
                i += 1
            assert len(values) == nvars
            rows.append(values)
            expected_index += 1
        plots.append((plotname, names, rows))

    transient = [plot for plot in plots if "transient" in plot[0].lower()]
    assert transient, f"no transient plot in {path}"
    _, names, rows = transient[-1]
    columns = {
        name.lower(): [row[index] for row in rows]
        for index, name in enumerate(names)
    }
    time_name = next(
        (name.lower() for name in names if name.lower() == "time"),
        None,
    )
    assert time_name is not None
    return columns[time_name], columns


def _reference_from_manifest_row(
    manifest: Path,
    row: dict[str, str],
    req: dict,
) -> dict[str, float]:
    raw_path = Path(row["raw_path"])
    if not raw_path.is_absolute():
        raw_path = manifest.parent / raw_path
    times, columns = _parse_final_transient(raw_path)

    def signal(column: str) -> list[float]:
        key = row[column].lower()
        assert key in columns, f"missing {key} in independent reference parser"
        return columns[key]

    # Access load_current_var as well so every manifest-declared signal is verified.
    signal("load_current_var")
    signals = {
        "time": times,
        "vout": signal("vout_var"),
        "gate": signal("gate_var"),
        "il": signal("inductor_current_var"),
        "load": signal("load_current_var"),
    }
    start = float(row["analysis_start_s"])
    end = float(row["analysis_end_s"])
    event = float(row["event_time_s"]) if row["event_time_s"].strip() else None
    return _reference_metrics(times, signals, row["case_type"], start, end, event, req)


@contextmanager
def _temporary_bytes(path: Path, data: bytes):
    existed = path.exists()
    previous = path.read_bytes() if existed else None
    path.write_bytes(data)
    try:
        yield
    finally:
        if existed:
            assert previous is not None
            path.write_bytes(previous)
        else:
            path.unlink(missing_ok=True)


def test_public_outputs_match_independent_raw_calculation() -> None:
    """Public artifacts must match an independent calculation from every supplied raw file."""
    output = Path("/app/output")
    assert (output / "measurements.csv").is_file()
    assert (output / "validation_report.json").is_file()
    rows, report = _read_outputs(output)
    manifest = Path("/app/data/cases.csv")
    req = _requirements()
    with manifest.open(newline="", encoding="utf-8") as handle:
        manifest_rows = list(csv.DictReader(handle))
    assert [row["case_id"] for row in rows] == [row["case_id"] for row in manifest_rows]
    by_id = {row["case_id"]: row for row in rows}
    for manifest_row in manifest_rows:
        expected = _reference_from_manifest_row(manifest, manifest_row, req)
        actual = by_id[manifest_row["case_id"]]
        assert actual["status"] == "ok"
        _assert_metrics_close(actual, expected, manifest_row["case_type"])
    _assert_artifact_integrity(rows, report, req)


def test_hidden_waveforms_match_randomized_independent_reference(tmp_path: Path) -> None:
    """Fresh hidden traces with unpredictable identities and frequencies must match independent metrics."""
    seed = 0xB6C7A1D5
    rng = random.Random(seed)
    startup_fsw = rng.uniform(184_000.0, 198_000.0)
    step_fsw = rng.uniform(204_000.0, 218_000.0)
    event = rng.uniform(0.0042, 0.0048)
    token = f"{seed:08x}"

    startup = tmp_path / f"startup_{token}.raw"
    step = tmp_path / f"step_{token}.raw"
    start_times, start_signals = _make_startup(
        startup, startup_fsw, seed=seed ^ 0x13579BDF, duplicate_every=541
    )
    step_times, step_signals = _make_step(
        step, step_fsw, event, seed=seed ^ 0x2468ACE0, duplicate_every=607
    )
    start_id = f"startup_{token}"
    step_id = f"step_{token}"
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [
        {
            "case_id": start_id, "raw_path": startup.name, "case_type": "startup",
            "analysis_start_s": "0.000000", "analysis_end_s": "0.011700", "event_time_s": "",
            "time_var": "time", "vout_var": "v(out_hidden)", "gate_var": "v(gate_hidden)",
            "inductor_current_var": "i(l_hidden)", "load_current_var": "i(load_hidden)",
        },
        {
            "case_id": step_id, "raw_path": step.name, "case_type": "step",
            "analysis_start_s": "0.002000", "analysis_end_s": "0.010700",
            "event_time_s": f"{event:.12g}",
            "time_var": "TIME", "vout_var": "V(OUT_X)", "gate_var": "V(GATE_X)",
            "inductor_current_var": "I(LX)", "load_current_var": "I(LOAD_X)",
        },
    ])
    req_path = tmp_path / "requirements.json"
    req = _requirements()
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, f"seed={seed}\n{result.stderr}"
    rows, report = _read_outputs(output)
    by_id = {row["case_id"]: row for row in rows}
    assert set(by_id) == {start_id, step_id}
    assert all(row["status"] == "ok" for row in rows)

    expected_start = _reference_metrics(
        start_times, start_signals, "startup", 0.0, 0.0117, None, req
    )
    expected_step = _reference_metrics(
        step_times, step_signals, "step", 0.002, 0.0107, event, req
    )
    _assert_metrics_close(by_id[start_id], expected_start, "startup")
    _assert_metrics_close(by_id[step_id], expected_step, "step")
    _assert_artifact_integrity(rows, report, req)


def test_malformed_trace_is_isolated_while_valid_case_continues(tmp_path: Path) -> None:
    """A malformed raw record must yield one invalid row while a valid case continues."""
    valid = tmp_path / "valid.raw"
    valid_times, valid_signals = _make_startup(valid)
    malformed = tmp_path / "bad.raw"
    malformed.write_text(
        "Title: bad\nPlotname: Transient Analysis\nFlags: real\nNo. Variables: 2\nNo. Points: 1\n"
        "Variables:\n0 time time\n1 v(out) voltage\nValues:\n0 0.0\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [
        {
            "case_id": "broken_case", "raw_path": malformed.name, "case_type": "startup",
            "analysis_start_s": "0", "analysis_end_s": "0.001", "event_time_s": "",
            "time_var": "time", "vout_var": "v(out)", "gate_var": "v(gate)",
            "inductor_current_var": "i(l)", "load_current_var": "i(load)",
        },
        {
            "case_id": "survivor_case", "raw_path": valid.name, "case_type": "startup",
            "analysis_start_s": "0", "analysis_end_s": "0.0117", "event_time_s": "",
            "time_var": "time", "vout_var": "v(out_hidden)", "gate_var": "v(gate_hidden)",
            "inductor_current_var": "i(l_hidden)", "load_current_var": "i(load_hidden)",
        },
    ])
    req = _requirements()
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert rows[0]["status"] == "invalid"
    assert rows[1]["status"] == "ok"
    expected = _reference_metrics(valid_times, valid_signals, "startup", 0, 0.0117, None, req)
    _assert_metrics_close(rows[1], expected, "startup")
    _assert_artifact_integrity(rows, report, req)



def test_inconsistent_point_index_rejects_otherwise_valid_trace(tmp_path: Path) -> None:
    """A valid waveform with one non-sequential Values index must be rejected."""
    raw = tmp_path / "bad_point_index.raw"
    _make_startup(raw, seed=0x51A7E, duplicate_every=0)

    lines = raw.read_text(encoding="utf-8").splitlines()
    values_markers = [index for index, line in enumerate(lines) if line.strip().lower() == "values:"]
    assert values_markers
    final_values = values_markers[-1]
    record_lines = [
        index
        for index in range(final_values + 1, len(lines))
        if lines[index] and lines[index][0].isdigit()
    ]
    assert len(record_lines) > 600
    target_line = record_lines[500]
    parts = lines[target_line].split(maxsplit=1)
    assert int(parts[0]) == 500
    lines[target_line] = f"507 {parts[1]}"
    raw.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "bad_point_index",
        "raw_path": raw.name,
        "case_type": "startup",
        "analysis_start_s": "0",
        "analysis_end_s": "0.0117",
        "event_time_s": "",
        "time_var": "time",
        "vout_var": "v(out_hidden)",
        "gate_var": "v(gate_hidden)",
        "inductor_current_var": "i(l_hidden)",
        "load_current_var": "i(load_hidden)",
    }])
    req = _requirements()
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert len(rows) == 1
    assert rows[0]["status"] == "invalid"
    assert rows[0]["errors"].strip()
    _assert_artifact_integrity(rows, report, req)

def test_missing_required_signal_marks_only_that_case_invalid(tmp_path: Path) -> None:
    """A missing manifest-declared signal must invalidate that case without crashing the CLI."""
    raw = tmp_path / "missing_signal.raw"
    _make_startup(raw)
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "missing_load", "raw_path": raw.name, "case_type": "startup",
        "analysis_start_s": "0", "analysis_end_s": "0.0117", "event_time_s": "",
        "time_var": "time", "vout_var": "v(out_hidden)", "gate_var": "v(gate_hidden)",
        "inductor_current_var": "i(l_hidden)", "load_current_var": "i(not_present)",
    }])
    req = _requirements()
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert rows[0]["status"] == "invalid"
    _assert_artifact_integrity(rows, report, req)


def test_duplicate_timestamp_keeps_final_record(tmp_path: Path) -> None:
    """An earlier duplicate outlier must be discarded; the final timestamp record controls ripple."""
    raw = tmp_path / "duplicate.raw"
    fsw = 200_000.0
    period = 1.0 / fsw
    times = [i * 0.5e-6 for i in range(401)]
    variables = [
        ("time", "time"), ("v(out)", "voltage"), ("v(g)", "voltage"),
        ("i(l)", "current"), ("i(load)", "current"),
    ]
    raw_rows = []
    signals = {"time": [], "vout": [], "gate": [], "il": [], "load": []}
    for t in times:
        phase = (t / period) % 1.0
        row = (
            t,
            12.0 + 0.04 * _tri(phase),
            7.0 if phase < 0.4 else 3.0,
            4.0 + 0.4 * _tri(phase),
            4.0,
        )
        raw_rows.append(row)
        for name, value in zip(("time", "vout", "gate", "il", "load"), row):
            signals[name].append(value)
    insert_at = len(raw_rows) - 35
    normal = raw_rows[insert_at]
    raw_rows.insert(insert_at, (normal[0], 20.0, normal[2], normal[3], normal[4]))
    for name, value in zip(
        ("time", "vout", "gate", "il", "load"),
        (normal[0], 20.0, normal[2], normal[3], normal[4]),
    ):
        signals[name].insert(insert_at, value)
    with raw.open("w", encoding="utf-8", newline="\n") as handle:
        _write_plot(handle, "duplicate test", "Transient Analysis", variables, raw_rows, "mixed")

    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "duplicate_final_wins", "raw_path": raw.name, "case_type": "startup",
        "analysis_start_s": "0", "analysis_end_s": "0.000199", "event_time_s": "",
        "time_var": "time", "vout_var": "v(out)", "gate_var": "v(g)",
        "inductor_current_var": "i(l)", "load_current_var": "i(load)",
    }])
    req = _requirements()
    req["startup_settling_time_s"]["max"] = 1.0
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    # Build the exact original order expected by _dedupe after insertion.
    ordered_times = times.copy()
    ordered_times.insert(insert_at, normal[0])
    expected = _reference_metrics(ordered_times, signals, "startup", 0, 0.000199, None, req)
    _assert_metrics_close(rows[0], expected, "startup")
    assert float(rows[0]["ripple_v_pp"]) < 0.12
    _assert_artifact_integrity(rows, report, req)


def test_changed_requirements_change_exact_checks_and_overall_result(tmp_path: Path) -> None:
    """Pass/fail and every check key must be derived from the provided requirements."""
    raw = tmp_path / "nominal.raw"
    times, signals = _make_startup(raw)
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "strict_ripple_case", "raw_path": raw.name, "case_type": "startup",
        "analysis_start_s": "0", "analysis_end_s": "0.0117", "event_time_s": "",
        "time_var": "time", "vout_var": "v(out_hidden)", "gate_var": "v(gate_hidden)",
        "inductor_current_var": "i(l_hidden)", "load_current_var": "i(load_hidden)",
    }])
    req = _requirements()
    req["steady_state_ripple_v_pp"]["max"] = 0.01
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    expected_metrics = _reference_metrics(times, signals, "startup", 0, 0.0117, None, req)
    _assert_metrics_close(rows[0], expected_metrics, "startup")
    _assert_artifact_integrity(rows, report, req)
    checks = report["cases"][0]["checks"]
    assert checks["steady_state_ripple"] is False
    assert rows[0]["case_pass"] == "false"
    assert report["overall_pass"] is False


def test_exact_alternate_input_paths_are_supported(tmp_path: Path) -> None:
    """The documented /app/cases.csv and /app/requirements.json paths must work unchanged."""
    token = "a17c9e42"
    raw = Path("/app") / f"alternate_{token}.raw"
    manifest = Path("/app/cases.csv")
    requirements = Path("/app/requirements.json")
    times, signals = _make_startup(raw, seed=int(token, 16))
    manifest_text = (
        "case_id,raw_path,case_type,analysis_start_s,analysis_end_s,event_time_s,"
        "time_var,vout_var,gate_var,inductor_current_var,load_current_var\n"
        f"alternate_{token},{raw.name},startup,0,0.0117,,time,v(out_hidden),"
        "v(gate_hidden),i(l_hidden),i(load_hidden)\n"
    ).encode()
    req = _requirements()
    output = tmp_path / "out"
    try:
        with _temporary_bytes(manifest, manifest_text), _temporary_bytes(
            requirements, json.dumps(req).encode()
        ):
            result = _run_cli(manifest, requirements, output)
            assert result.returncode == 0, result.stderr
            rows, report = _read_outputs(output)
            expected = _reference_metrics(times, signals, "startup", 0, 0.0117, None, req)
            _assert_metrics_close(rows[0], expected, "startup")
            _assert_artifact_integrity(rows, report, req)
    finally:
        raw.unlink(missing_ok=True)
def _gate_edges_for_test(
    times: list[float],
    gate: list[float],
    start: float,
    end: float,
) -> list[float]:
    """Verifier-side edge calculation used only to place adversarial events."""
    xs, ys = _segment(times, gate, start, end)
    threshold = (_quantile(ys, 0.05) + _quantile(ys, 0.95)) / 2
    edges: list[float] = []
    for index in range(1, len(xs)):
        if ys[index - 1] < threshold <= ys[index]:
            fraction = (threshold - ys[index - 1]) / (ys[index] - ys[index - 1])
            edges.append(xs[index - 1] + fraction * (xs[index] - xs[index - 1]))
    return edges


def _write_named_transient(
    path: Path,
    title: str,
    times: list[float],
    vout: list[float],
    gate: list[float],
    il: list[float],
    load: list[float],
) -> None:
    variables = [
        ("time", "time"),
        ("v(out_adv)", "voltage"),
        ("v(gate_adv)", "voltage"),
        ("i(l_adv)", "current"),
        ("i(load_adv)", "current"),
    ]
    rows = list(zip(times, vout, gate, il, load))
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        _write_plot(handle, title, "Transient Analysis", variables, rows, "mixed")


def test_startup_that_never_settles_is_invalid(tmp_path: Path) -> None:
    """A final excursion at the steady-window boundary leaves no valid startup settling point."""
    req = _requirements()
    fsw = 192_000.0
    period = 1.0 / fsw
    dt = period / 12.0
    end = 0.0042
    # Include at least one sample at or beyond the requested analysis end so
    # boundary interpolation is always defined despite floating-point rounding.
    times = [index * dt for index in range(math.ceil(end / dt) + 1)]
    gate = [8.0 if (t / period) % 1.0 < 0.40 else 3.0 for t in times]
    edges = _gate_edges_for_test(times, gate, 0.0, end)
    assert len(edges) > req["steady_cycles"] + 2
    steady_start = edges[-(req["steady_cycles"] + 1)]

    vout = [12.0 + 0.025 * _tri(t / period) for t in times]
    boundary_index = bisect_left(times, steady_start)
    assert 0 < boundary_index < len(times)
    vout[boundary_index - 1] = 14.0
    vout[boundary_index] = 14.0
    il = [4.0 + 0.35 * _tri(t / period + 0.17) for t in times]
    load = [4.0 for _ in times]

    raw = tmp_path / "never_settles.raw"
    _write_named_transient(raw, "startup never settles", times, vout, gate, il, load)
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "startup_never_settles",
        "raw_path": raw.name,
        "case_type": "startup",
        "analysis_start_s": "0",
        "analysis_end_s": f"{end:.12g}",
        "event_time_s": "",
        "time_var": "time",
        "vout_var": "v(out_adv)",
        "gate_var": "v(gate_adv)",
        "inductor_current_var": "i(l_adv)",
        "load_current_var": "i(load_adv)",
    }])
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert len(rows) == 1
    assert rows[0]["status"] == "invalid"
    assert rows[0]["errors"].strip()
    _assert_artifact_integrity(rows, report, req)


def test_step_that_never_recovers_is_invalid(tmp_path: Path) -> None:
    """Persistent out-of-band alternation prevents any complete recovery hold interval."""
    req = _requirements()
    fsw = 208_000.0
    period = 1.0 / fsw
    dt = period / 16.0
    end = 0.0064
    times = [index * dt for index in range(int(end / dt) + 1)]
    event_index = int(0.0016 / dt)
    event = times[event_index]
    gate = [9.0 if (t / period) % 1.0 < 0.45 else 4.0 for t in times]
    band = float(req["step_recovery_time_s"]["band_fraction"])
    amplitude = 12.0 * band * 1.6 + 0.06
    vout: list[float] = []
    for index, t in enumerate(times):
        if t < event:
            vout.append(12.0 + 0.02 * _tri(t / period))
        else:
            vout.append(12.0 + (amplitude if index % 2 == 0 else -amplitude))
    il = [3.0 if t < event else 8.0 for t in times]
    load = [3.0 if t < event else 8.0 for t in times]

    raw = tmp_path / "never_recovers.raw"
    _write_named_transient(raw, "step never recovers", times, vout, gate, il, load)
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "step_never_recovers",
        "raw_path": raw.name,
        "case_type": "step",
        "analysis_start_s": "0",
        "analysis_end_s": f"{end:.12g}",
        "event_time_s": f"{event:.14e}",
        "time_var": "time",
        "vout_var": "v(out_adv)",
        "gate_var": "v(gate_adv)",
        "inductor_current_var": "i(l_adv)",
        "load_current_var": "i(load_adv)",
    }])
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert len(rows) == 1
    assert rows[0]["status"] == "invalid"
    assert rows[0]["errors"].strip()
    _assert_artifact_integrity(rows, report, req)


def test_exact_sample_boundaries_match_reference(tmp_path: Path) -> None:
    """Exact sample-aligned analysis and event boundaries obey the same closed-interval rules."""
    req = _requirements()
    fsw = 205_000.0
    period = 1.0 / fsw
    dt = period / 14.0
    times = [index * dt for index in range(12_001)]
    start_index = 700
    event_index = 3_100
    end_index = 11_500
    start = times[start_index]
    event = times[event_index]
    end = times[end_index]

    gate = [10.0 if (t / period) % 1.0 < 0.43 else 4.0 for t in times]
    vout: list[float] = []
    il: list[float] = []
    load: list[float] = []
    for t in times:
        phase = (t / period) % 1.0
        if t < event:
            dynamic = 0.0
            current = 3.5
        else:
            elapsed = t - event
            dynamic = -0.72 * math.exp(-elapsed / 0.00030)
            current = 7.5
        vout.append(12.01 + dynamic + 0.035 * _tri(phase))
        il.append(current + 0.42 * _tri(phase + 0.23))
        load.append(current)

    raw = tmp_path / "exact_boundaries.raw"
    _write_named_transient(raw, "exact sample boundaries", times, vout, gate, il, load)
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "exact_boundary_step",
        "raw_path": raw.name,
        "case_type": "step",
        "analysis_start_s": f"{start:.14e}",
        "analysis_end_s": f"{end:.14e}",
        "event_time_s": f"{event:.14e}",
        "time_var": "time",
        "vout_var": "v(out_adv)",
        "gate_var": "v(gate_adv)",
        "inductor_current_var": "i(l_adv)",
        "load_current_var": "i(load_adv)",
    }])
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert rows[0]["status"] == "ok"
    signals = {"time": times, "vout": vout, "gate": gate, "il": il, "load": load}
    expected = _reference_metrics(times, signals, "step", start, end, event, req)
    _assert_metrics_close(rows[0], expected, "step")
    _assert_artifact_integrity(rows, report, req)


def _write_regular_gate_case(
    path: Path,
    times: list[float],
    gate: list[float],
    vout: list[float],
    il: list[float],
    load: list[float],
    *,
    title: str,
) -> None:
    _write_named_transient(path, title, times, vout, gate, il, load)


def _wide_requirements(*, steady_cycles: int = 4) -> dict:
    req = _requirements()
    req["switching_frequency_hz"] = {"min": 1_000.0, "max": 1_000_000.0}
    req["steady_state_vout_v"] = {"min": 1.0, "max": 30.0}
    req["steady_state_ripple_v_pp"] = {"max": 10.0}
    req["startup_settling_time_s"] = {"max": 1.0, "band_fraction": 1.0}
    req["step_min_vout_v"] = {"min": 0.0}
    req["step_max_vout_v"] = {"max": 30.0}
    req["step_recovery_time_s"] = {"max": 1.0, "band_fraction": 1.0, "hold_periods": 2}
    req["peak_inductor_current_a"] = {"max": 100.0}
    req["steady_cycles"] = steady_cycles
    req["post_step_observation_cycles"] = 4
    return req


def test_edge_count_requirement_depends_on_steady_cycles_not_fixed_twelve(tmp_path: Path) -> None:
    """A valid short capture needs only enough rises for frequency and the configured steady window."""
    period = 10e-6
    dt = 0.25e-6
    end = 69e-6
    times = [i * dt for i in range(math.ceil(end / dt) + 2)]
    rises = [5e-6 + i * period for i in range(7)]  # deliberately fewer than twelve
    gate = [10.0 if any(rise <= t < rise + 3e-6 for rise in rises) else 0.0 for t in times]
    vout = [12.0 for _ in times]
    il = [4.0 for _ in times]
    load = [4.0 for _ in times]
    raw = tmp_path / "short_valid.raw"
    _write_regular_gate_case(raw, times, gate, vout, il, load, title="short valid capture")

    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "short_valid", "raw_path": raw.name, "case_type": "startup",
        "analysis_start_s": "0", "analysis_end_s": f"{end:.12g}", "event_time_s": "",
        "time_var": "time", "vout_var": "v(out_adv)", "gate_var": "v(gate_adv)",
        "inductor_current_var": "i(l_adv)", "load_current_var": "i(load_adv)",
    }])
    req = _wide_requirements(steady_cycles=4)
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert rows[0]["status"] == "ok"
    expected = _reference_metrics(
        times, {"time": times, "vout": vout, "gate": gate, "il": il, "load": load},
        "startup", 0.0, end, None, req,
    )
    _assert_metrics_close(rows[0], expected, "startup")
    _assert_artifact_integrity(rows, report, req)


def test_gate_threshold_uses_documented_fifth_and_ninety_fifth_percentiles(tmp_path: Path) -> None:
    """Two skewed-duty cases independently make the 5th and 95th percentile operands decisive."""
    period = 10e-6
    dt = period / 100
    cycles = 24
    end = cycles * period - dt
    times = [i * dt for i in range(cycles * 100)]

    # 8% low, 92% high. Alternating 8 V / 12 V high levels make q05 decisive:
    # q05=0 gives a 6 V midpoint and every cycle rises; q10=8 would suppress 8 V cycles.
    gate_q05 = []
    for t in times:
        cycle = int(t / period)
        phase = (t / period) % 1.0
        high = 8.0 if cycle % 2 == 0 else 12.0
        gate_q05.append(0.0 if phase < 0.08 else high)

    # 92% low, 8% high. q95 is high while q90 is zero, so the 95th percentile is decisive.
    gate_q95 = [10.0 if (t / period) % 1.0 >= 0.92 else 0.0 for t in times]
    vout = [12.0 for _ in times]
    il = [4.0 for _ in times]
    load = [4.0 for _ in times]

    raw05 = tmp_path / "q05.raw"
    raw95 = tmp_path / "q95.raw"
    _write_regular_gate_case(raw05, times, gate_q05, vout, il, load, title="q05 decisive")
    _write_regular_gate_case(raw95, times, gate_q95, vout, il, load, title="q95 decisive")
    manifest = tmp_path / "cases.csv"
    rows_in = []
    for cid, raw in (("q05_decisive", raw05), ("q95_decisive", raw95)):
        rows_in.append({
            "case_id": cid, "raw_path": raw.name, "case_type": "startup",
            "analysis_start_s": "0", "analysis_end_s": f"{end:.12g}", "event_time_s": "",
            "time_var": "time", "vout_var": "v(out_adv)", "gate_var": "v(gate_adv)",
            "inductor_current_var": "i(l_adv)", "load_current_var": "i(load_adv)",
        })
    _write_manifest(manifest, rows_in)
    req = _wide_requirements(steady_cycles=4)
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert [row["status"] for row in rows] == ["ok", "ok"]
    for row, gate in zip(rows, (gate_q05, gate_q95)):
        expected = _reference_metrics(
            times, {"time": times, "vout": vout, "gate": gate, "il": il, "load": load},
            "startup", 0.0, end, None, req,
        )
        _assert_metrics_close(row, expected, "startup")
        assert float(row["fsw_hz"]) == pytest.approx(100_000.0, rel=0.01)
    _assert_artifact_integrity(rows, report, req)


def test_switching_frequency_uses_median_of_all_consecutive_edge_intervals(tmp_path: Path) -> None:
    """One long switching interval must not turn the required median-period estimate into a mean."""
    dt = 0.25e-6
    intervals = [5e-6, 5e-6, 5e-6, 10e-6, 5e-6, 5e-6, 5e-6, 5e-6, 5e-6, 5e-6, 5e-6, 5e-6]
    rises = [3e-6]
    for interval in intervals:
        rises.append(rises[-1] + interval)
    end = rises[-1] + 3e-6
    times = [i * dt for i in range(math.ceil(end / dt) + 2)]
    gate = [10.0 if any(rise <= t < rise + 2e-6 for rise in rises) else 0.0 for t in times]
    vout = [12.0 for _ in times]
    il = [4.0 for _ in times]
    load = [4.0 for _ in times]
    raw = tmp_path / "median_period.raw"
    _write_regular_gate_case(raw, times, gate, vout, il, load, title="median period")
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "median_period", "raw_path": raw.name, "case_type": "startup",
        "analysis_start_s": "0", "analysis_end_s": f"{end:.12g}", "event_time_s": "",
        "time_var": "time", "vout_var": "v(out_adv)", "gate_var": "v(gate_adv)",
        "inductor_current_var": "i(l_adv)", "load_current_var": "i(load_adv)",
    }])
    req = _wide_requirements(steady_cycles=4)
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert rows[0]["status"] == "ok"
    assert float(rows[0]["fsw_hz"]) == pytest.approx(200_000.0, rel=0.01)
    expected = _reference_metrics(
        times, {"time": times, "vout": vout, "gate": gate, "il": il, "load": load},
        "startup", 0.0, end, None, req,
    )
    _assert_metrics_close(rows[0], expected, "startup")
    _assert_artifact_integrity(rows, report, req)


def test_steady_state_window_is_exactly_the_final_configured_complete_cycles(tmp_path: Path) -> None:
    """The earliest of the final configured cycles is intentionally different and must be included."""
    period = 5e-6
    dt = 0.25e-6
    rises = [2e-6 + i * period for i in range(11)]
    end = rises[-1] + 2e-6
    times = [i * dt for i in range(math.ceil(end / dt) + 2)]
    gate = [10.0 if any(rise <= t < rise + 2e-6 for rise in rises) else 0.0 for t in times]

    # With steady_cycles=4 the exact window is [rises[-5], rises[-1]].
    # Its first cycle is 10 V and its final three cycles are 12 V.
    vout = []
    for t in times:
        if rises[-5] <= t < rises[-4]:
            vout.append(10.0)
        else:
            vout.append(12.0)
    il = [4.0 for _ in times]
    load = [4.0 for _ in times]
    raw = tmp_path / "steady_window.raw"
    _write_regular_gate_case(raw, times, gate, vout, il, load, title="steady window")
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "steady_window", "raw_path": raw.name, "case_type": "startup",
        "analysis_start_s": "0", "analysis_end_s": f"{end:.12g}", "event_time_s": "",
        "time_var": "time", "vout_var": "v(out_adv)", "gate_var": "v(gate_adv)",
        "inductor_current_var": "i(l_adv)", "load_current_var": "i(load_adv)",
    }])
    req = _wide_requirements(steady_cycles=4)
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    expected = _reference_metrics(
        times, {"time": times, "vout": vout, "gate": gate, "il": il, "load": load},
        "startup", 0.0, end, None, req,
    )
    _assert_metrics_close(rows[0], expected, "startup")
    assert float(rows[0]["vout_avg_v"]) < 11.8
    assert float(rows[0]["ripple_v_pp"]) > 1.5
    _assert_artifact_integrity(rows, report, req)


def test_zero_band_zero_time_absolute_peak_and_inclusive_requirement_equalities(tmp_path: Path) -> None:
    """Exact equality is inside every band/limit, event is a recovery candidate, and peak uses abs()."""
    period = 1.0 / 131_072.0  # binary-exact period => exact 131072 Hz equality boundary
    dt = period / 16.0
    end = 24 * period
    times = [i * dt for i in range(24 * 16 + 1)]
    gate = [10.0 if 3 <= (i % 16) < 9 else 0.0 for i, _ in enumerate(times)]
    vout = [12.0 for _ in times]
    il = [-5.0 for _ in times]
    load = [5.0 for _ in times]
    raw = tmp_path / "exact_equalities.raw"
    _write_regular_gate_case(raw, times, gate, vout, il, load, title="exact equalities")
    event = 8 * period
    manifest = tmp_path / "cases.csv"
    base = {
        "raw_path": raw.name,
        "analysis_start_s": "0", "analysis_end_s": f"{end:.12g}",
        "time_var": "time", "vout_var": "v(out_adv)", "gate_var": "v(gate_adv)",
        "inductor_current_var": "i(l_adv)", "load_current_var": "i(load_adv)",
    }
    _write_manifest(manifest, [
        {**base, "case_id": "exact_startup", "case_type": "startup", "event_time_s": ""},
        {**base, "case_id": "exact_step", "case_type": "step", "event_time_s": f"{event:.12g}"},
    ])
    req = _wide_requirements(steady_cycles=4)
    req["switching_frequency_hz"] = {"min": 131_072.0, "max": 131_073.0}
    req["steady_state_vout_v"] = {"min": 12.0, "max": 12.0}
    req["steady_state_ripple_v_pp"] = {"max": 0.0}
    req["startup_settling_time_s"] = {"max": 0.0, "band_fraction": 0.0}
    req["step_min_vout_v"] = {"min": 12.0}
    req["step_max_vout_v"] = {"max": 12.0}
    req["step_recovery_time_s"] = {"max": 0.0, "band_fraction": 0.0, "hold_periods": 2}
    req["peak_inductor_current_a"] = {"max": 5.0}
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert [row["status"] for row in rows] == ["ok", "ok"]
    assert all(row["case_pass"] == "true" for row in rows)
    assert float(rows[0]["settling_time_s"]) == pytest.approx(0.0, abs=1e-12)
    assert float(rows[1]["recovery_time_s"]) == pytest.approx(0.0, abs=1e-12)
    assert all(float(row["peak_inductor_current_a"]) == pytest.approx(5.0, abs=1e-12) for row in rows)
    assert report["overall_pass"] is True
    _assert_artifact_integrity(rows, report, req)


def test_cli_preserves_manifest_requirements_and_raw_inputs_byte_for_byte(tmp_path: Path) -> None:
    """All input files are read-only task inputs and must remain byte-identical after execution."""
    raw = tmp_path / "preserve.raw"
    _make_startup(raw, seed=0xABCD, duplicate_every=0)
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "preserve", "raw_path": raw.name, "case_type": "startup",
        "analysis_start_s": "0", "analysis_end_s": "0.0117", "event_time_s": "",
        "time_var": "time", "vout_var": "v(out_hidden)", "gate_var": "v(gate_hidden)",
        "inductor_current_var": "i(l_hidden)", "load_current_var": "i(load_hidden)",
    }])
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(_requirements(), indent=2) + "\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in (raw, manifest, req_path)}
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    assert all(path.read_bytes() == data for path, data in before.items())


def test_vout_average_is_trapezoidal_time_weighted_not_sample_weighted(tmp_path: Path) -> None:
    """Irregular sampling deliberately over-represents the high half-cycle in sample count."""
    period = 10e-6
    end = 140e-6
    times: list[float] = []
    t = 0.0
    while t <= end + 1e-15:
        times.append(t)
        phase = (t / period) % 1.0
        t += 1.0e-6 if phase < 0.5 else 0.1e-6
    if times[-1] < end:
        times.append(end)
    gate = [10.0 if 0.18 <= (t / period) % 1.0 < 0.42 else 0.0 for t in times]
    vout = [10.0 if (t / period) % 1.0 < 0.5 else 14.0 for t in times]
    il = [4.0 for _ in times]
    load = [4.0 for _ in times]
    raw = tmp_path / "time_weighted.raw"
    _write_regular_gate_case(raw, times, gate, vout, il, load, title="time weighted average")
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "time_weighted", "raw_path": raw.name, "case_type": "startup",
        "analysis_start_s": "0", "analysis_end_s": f"{end:.12g}", "event_time_s": "",
        "time_var": "time", "vout_var": "v(out_adv)", "gate_var": "v(gate_adv)",
        "inductor_current_var": "i(l_adv)", "load_current_var": "i(load_adv)",
    }])
    req = _wide_requirements(steady_cycles=4)
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    expected = _reference_metrics(
        times, {"time": times, "vout": vout, "gate": gate, "il": il, "load": load},
        "startup", 0.0, end, None, req,
    )
    _assert_metrics_close(rows[0], expected, "startup")
    assert 11.7 < float(rows[0]["vout_avg_v"]) < 12.3
    _assert_artifact_integrity(rows, report, req)


def test_peak_current_ignores_out_of_window_spikes_but_uses_closed_interval(tmp_path: Path) -> None:
    """Large current spikes outside analysis_start/end must not contaminate the reported peak."""
    period = 10e-6
    dt = 0.5e-6
    raw_end = 200e-6
    times = [i * dt for i in range(math.ceil(raw_end / dt) + 1)]
    start_index, end_index = 40, 340
    start, end = times[start_index], times[end_index]
    gate = [10.0 if 0.2 <= (t / period) % 1.0 < 0.6 else 0.0 for t in times]
    vout = [12.0 for _ in times]
    il = [-50.0 if i < start_index or i > end_index else -5.0 for i, _ in enumerate(times)]
    load = [5.0 for _ in times]
    raw = tmp_path / "peak_window.raw"
    _write_regular_gate_case(raw, times, gate, vout, il, load, title="peak current window")
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "peak_window", "raw_path": raw.name, "case_type": "startup",
        "analysis_start_s": f"{start:.17g}", "analysis_end_s": f"{end:.17g}", "event_time_s": "",
        "time_var": "time", "vout_var": "v(out_adv)", "gate_var": "v(gate_adv)",
        "inductor_current_var": "i(l_adv)", "load_current_var": "i(load_adv)",
    }])
    req = _wide_requirements(steady_cycles=4)
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert float(rows[0]["peak_inductor_current_a"]) == pytest.approx(5.0, abs=1e-12)
    _assert_artifact_integrity(rows, report, req)


def test_step_minmax_stops_at_configured_post_step_observation_window(tmp_path: Path) -> None:
    """A large later disturbance is outside the post-step min/max observation interval."""
    period = 10e-6
    dt = 0.5e-6
    end = 250e-6
    event = 50e-6
    times = [i * dt for i in range(math.ceil(end / dt) + 1)]
    gate = [10.0 if 0.2 <= (t / period) % 1.0 < 0.6 else 0.0 for t in times]
    vout = [12.0 for _ in times]
    # Observation ends after four periods (~90 us); disturb only much later.
    for i, t in enumerate(times):
        if 135e-6 <= t <= 145e-6:
            vout[i] = 17.0 if i % 2 == 0 else 7.0
    il = [5.0 for _ in times]
    load = [5.0 for _ in times]
    raw = tmp_path / "step_observation.raw"
    _write_regular_gate_case(raw, times, gate, vout, il, load, title="step observation window")
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "step_observation", "raw_path": raw.name, "case_type": "step",
        "analysis_start_s": "0", "analysis_end_s": f"{end:.12g}", "event_time_s": f"{event:.12g}",
        "time_var": "time", "vout_var": "v(out_adv)", "gate_var": "v(gate_adv)",
        "inductor_current_var": "i(l_adv)", "load_current_var": "i(load_adv)",
    }])
    req = _wide_requirements(steady_cycles=4)
    req["post_step_observation_cycles"] = 4
    req["step_recovery_time_s"]["band_fraction"] = 1.0
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert float(rows[0]["min_vout_v"]) == pytest.approx(12.0, abs=1e-12)
    assert float(rows[0]["max_vout_v"]) == pytest.approx(12.0, abs=1e-12)
    _assert_artifact_integrity(rows, report, req)


def test_recovery_requires_the_full_hold_interval_not_a_single_in_band_sample(tmp_path: Path) -> None:
    """A brief in-band blip is not recovery; the final steady segment is shorter than hold_periods."""
    period = 10e-6
    dt = 0.5e-6
    rises = [2e-6 + i * period for i in range(20)]
    end = rises[-1] + 1e-6
    times = [i * dt for i in range(math.ceil(end / dt) + 2)]
    gate = [10.0 if any(rise <= t < rise + 4e-6 for rise in rises) else 0.0 for t in times]
    event = 20e-6
    steady_start = rises[-5]
    vout = []
    for t in times:
        if t < event:
            vout.append(12.0)
        elif abs(t - 50e-6) < dt / 4:
            vout.append(12.0)  # isolated in-band blip
        elif t >= steady_start:
            vout.append(12.0)  # only four final periods: shorter than required five-period hold
        else:
            vout.append(10.0)
    il = [5.0 for _ in times]
    load = [5.0 for _ in times]
    raw = tmp_path / "hold_required.raw"
    _write_regular_gate_case(raw, times, gate, vout, il, load, title="hold required")
    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "hold_required", "raw_path": raw.name, "case_type": "step",
        "analysis_start_s": "0", "analysis_end_s": f"{end:.17g}", "event_time_s": f"{event:.17g}",
        "time_var": "time", "vout_var": "v(out_adv)", "gate_var": "v(gate_adv)",
        "inductor_current_var": "i(l_adv)", "load_current_var": "i(load_adv)",
    }])
    req = _wide_requirements(steady_cycles=4)
    req["step_recovery_time_s"] = {"max": 1.0, "band_fraction": 0.02, "hold_periods": 5}
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert rows[0]["status"] == "invalid"
    assert rows[0]["errors"].strip()
    _assert_artifact_integrity(rows, report, req)


def test_rising_edge_interpolation_and_strict_left_threshold_are_decisive(tmp_path: Path) -> None:
    """Coarse asymmetric sampling requires interpolation, and a threshold plateau must not double-count."""
    period = 20e-6
    cycles = 14

    def sampled_case(*, plateau_threshold: bool) -> tuple[list[float], list[float]]:
        points: dict[float, float] = {}
        for cycle in range(cycles):
            base = cycle * period
            if plateau_threshold:
                # Make the documented q05/q95 values exactly 0/10, hence the
                # threshold exactly 5.  The 5->10 segment must NOT create a
                # second edge: the left side of the predicate is strictly <.
                # If it is mutated to <=, every cycle gains a duplicate-time
                # rising edge and the all-period median is no longer 20 us.
                local = [
                    (0e-6, 0.0), (1e-6, 0.0), (2e-6, 0.0), (3e-6, 0.0),
                    (4e-6, 0.0), (5e-6, 5.0), (6e-6, 10.0), (7e-6, 10.0),
                    (8e-6, 10.0), (9e-6, 10.0), (10e-6, 10.0),
                    (12e-6, 0.0), (14e-6, 0.0), (16e-6, 0.0), (18e-6, 0.0),
                ]
            else:
                width = (cycle % 4 + 1) * 1e-6
                local = [
                    (0e-6, 0.0), (5e-6 - width, 0.0), (5e-6 + width, 10.0),
                    (10e-6, 10.0), (12e-6, 0.0), (18e-6, 0.0),
                ]
            for offset, value in local:
                points[base + offset] = value
        points[cycles * period] = 0.0
        times = sorted(points)
        return times, [points[t] for t in times]

    cases = []
    raw_specs = []
    for cid, plateau in (("interpolated_edges", False), ("strict_left_edge", True)):
        times, gate = sampled_case(plateau_threshold=plateau)
        vout = [12.0 for _ in times]
        il = [4.0 for _ in times]
        load = [4.0 for _ in times]
        raw = tmp_path / f"{cid}.raw"
        _write_regular_gate_case(raw, times, gate, vout, il, load, title=cid)
        # Use an interior retained sample as the interval end.  RAW values are
        # serialized in scientific notation, so this avoids asking the parser
        # to extrapolate by a sub-ULP amount created only by text round-tripping.
        analysis_end = times[-2]
        cases.append({
            "case_id": cid, "raw_path": raw.name, "case_type": "startup",
            "analysis_start_s": "0", "analysis_end_s": f"{analysis_end:.14e}", "event_time_s": "",
            "time_var": "time", "vout_var": "v(out_adv)", "gate_var": "v(gate_adv)",
            "inductor_current_var": "i(l_adv)", "load_current_var": "i(load_adv)",
        })
        raw_specs.append((times, gate, vout, il, load, analysis_end))

    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, cases)
    req = _wide_requirements(steady_cycles=4)
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert [row["status"] for row in rows] == ["ok", "ok"]
    for row, (times, gate, vout, il, load, analysis_end) in zip(rows, raw_specs):
        expected = _reference_metrics(
            times, {"time": times, "vout": vout, "gate": gate, "il": il, "load": load},
            "startup", 0.0, analysis_end, None, req,
        )
        _assert_metrics_close(row, expected, "startup")
        assert float(row["fsw_hz"]) == pytest.approx(50_000.0, rel=0.01)
    _assert_artifact_integrity(rows, report, req)


def test_transient_name_contains_match_later_nontransient_and_nonfinite_unused_signal(tmp_path: Path) -> None:
    """Select the last matching transient even with suffix text; non-finite values anywhere invalidate a plot."""
    period = 10e-6
    dt = 0.5e-6
    end = 180e-6
    times = [i * dt for i in range(math.ceil(end / dt) + 1)]
    vout = [12.0 for _ in times]
    gate = [10.0 if 0.2 <= (t / period) % 1.0 < 0.6 else 0.0 for t in times]
    il = [4.0 for _ in times]
    load = [4.0 for _ in times]
    variables = [
        ("time", "time"), ("v(out)", "voltage"), ("v(gate)", "voltage"),
        ("i(l)", "current"), ("i(load)", "current"),
    ]
    rows = list(zip(times, vout, gate, il, load))

    valid_raw = tmp_path / "contains_transient.raw"
    with valid_raw.open("w", encoding="utf-8", newline="\n") as handle:
        _write_plot(handle, "selected", "Transient Analysis - postprocessed", variables, rows, "mixed")
        handle.write("\n")
        _write_plot(handle, "later decoy", "Operating Point", [("v(dummy)", "voltage")], [(0.0,)], "same")

    invalid_raw = tmp_path / "nonfinite_unused.raw"
    bad_rows = list(rows)
    bad = list(bad_rows[len(bad_rows) // 2])
    bad[-1] = float("nan")  # load signal is required but not otherwise used by metrics
    bad_rows[len(bad_rows) // 2] = tuple(bad)
    with invalid_raw.open("w", encoding="utf-8", newline="\n") as handle:
        _write_plot(handle, "nonfinite", "Transient Analysis", variables, bad_rows, "mixed")

    manifest = tmp_path / "cases.csv"
    common = {
        "case_type": "startup", "analysis_start_s": "0", "analysis_end_s": f"{end:.12g}",
        "event_time_s": "", "time_var": "time", "vout_var": "v(out)", "gate_var": "v(gate)",
        "inductor_current_var": "i(l)", "load_current_var": "i(load)",
    }
    _write_manifest(manifest, [
        {**common, "case_id": "contains_transient", "raw_path": valid_raw.name},
        {**common, "case_id": "nonfinite_unused", "raw_path": invalid_raw.name},
    ])
    req = _wide_requirements(steady_cycles=4)
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    out_rows, report = _read_outputs(output)
    assert out_rows[0]["status"] == "ok"
    assert out_rows[1]["status"] == "invalid"
    expected = _reference_metrics(
        times, {"time": times, "vout": vout, "gate": gate, "il": il, "load": load},
        "startup", 0.0, end, None, req,
    )
    _assert_metrics_close(out_rows[0], expected, "startup")
    _assert_artifact_integrity(out_rows, report, req)


def test_unsorted_timestamp_records_are_sorted_before_analysis(tmp_path: Path) -> None:
    """Raw point indices stay sequential while the time column is deliberately out of chronological order."""
    period = 10e-6
    dt = 0.5e-6
    base_times = [i * dt for i in range(361)]
    base = []
    for t in base_times:
        phase = (t / period) % 1.0
        base.append((t, 12.0 + 0.03 * _tri(phase), 10.0 if 0.2 <= phase < 0.6 else 0.0, 4.0, 4.0))
    order = list(range(len(base)))
    rng = random.Random(0x5A17)
    rng.shuffle(order)
    shuffled = [base[i] for i in order]
    raw = tmp_path / "unsorted_times.raw"
    variables = [
        ("time", "time"), ("v(out)", "voltage"), ("v(gate)", "voltage"),
        ("i(l)", "current"), ("i(load)", "current"),
    ]
    with raw.open("w", encoding="utf-8", newline="\n") as handle:
        _write_plot(handle, "unsorted time values", "Transient Analysis", variables, shuffled, "mixed")

    manifest = tmp_path / "cases.csv"
    _write_manifest(manifest, [{
        "case_id": "unsorted_times", "raw_path": raw.name, "case_type": "startup",
        "analysis_start_s": "0", "analysis_end_s": f"{base_times[-1]:.12g}", "event_time_s": "",
        "time_var": "time", "vout_var": "v(out)", "gate_var": "v(gate)",
        "inductor_current_var": "i(l)", "load_current_var": "i(load)",
    }])
    req = _wide_requirements(steady_cycles=4)
    req_path = tmp_path / "requirements.json"
    req_path.write_text(json.dumps(req), encoding="utf-8")
    output = tmp_path / "out"
    result = _run_cli(manifest, req_path, output)
    assert result.returncode == 0, result.stderr
    rows, report = _read_outputs(output)
    assert rows[0]["status"] == "ok"
    shuffled_times = [row[0] for row in shuffled]
    shuffled_signals = {
        "time": shuffled_times,
        "vout": [row[1] for row in shuffled],
        "gate": [row[2] for row in shuffled],
        "il": [row[3] for row in shuffled],
        "load": [row[4] for row in shuffled],
    }
    expected = _reference_metrics(shuffled_times, shuffled_signals, "startup", 0.0, base_times[-1], None, req)
    _assert_metrics_close(rows[0], expected, "startup")
    _assert_artifact_integrity(rows, report, req)
