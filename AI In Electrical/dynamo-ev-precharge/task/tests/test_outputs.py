from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import pytest

APP = Path("/app")
CLI = [sys.executable, "-m", "powerup.cli"]
CSV_COLUMNS = [
    "t_ms", "pack_v", "link_v", "pack_a", "pre_cmd", "pre_aux",
    "pos_cmd", "pos_aux", "neg_cmd", "neg_aux", "iso_kohm", "crash",
]
DIGITAL_CHANNELS = [
    "pre_cmd", "pre_aux", "pos_cmd", "pos_aux", "neg_cmd", "neg_aux", "crash",
]
PRECEDENCE = [
    "WELDED_CONTACTOR", "UNSAFE_CLOSE", "LOW_ISOLATION",
    "REPEATED_PRECHARGE_FAILURE", "BYPASS_OR_SHORT", "OPEN_PRECHARGE",
    "PRECHARGE_TIMEOUT", "SENSOR_BIAS", "RESIDUAL_LINK", "CONTACT_BOUNCE",
    "AUX_TIMEOUT", "OK",
]
CASE_KEYS = ["case_id", "input_state", "verdict", "flags", "metrics", "evidence", "messages"]
METRIC_KEYS = [
    "precharge_start_ms", "ready_at_ms", "ready_delay_ms", "ready_link_v",
    "final_link_ratio", "peak_abs_pack_a", "max_link_slew_v_per_ms", "tau_ms",
    "aux_delay_ms", "aux_edges",
]
TIME_PATTERN = re.compile(r"^-?\d+\.\d{6}$")


class IntegerStream:
    """Small deterministic stream; callers must supply an explicit suite/test seed."""

    def __init__(self, state: int):
        self.state = state & 0x7FFFFFFF
        if self.state == 0:
            self.state = 1

    def take(self, low: int, high: int) -> int:
        self.state = (1664525 * self.state + 1013904223) & 0x7FFFFFFF
        return low + self.state % (high - low + 1)


@dataclass(frozen=True)
class Electrical:
    pack_v: float
    resistance_ohm: float
    capacitance_uf: float


class HiddenCases:
    def __init__(self, root: Path, seed: int):
        self.root = root
        self.stream = IntegerStream(seed)
        self.limits = {
            "ready_ratio": 0.90,
            "max_precharge_ms": 1000.0,
            "aux_delay_ms": 80.0,
            "weld_dwell_ms": 100.0,
            "bounce_interval_ms": 15.0,
            "open_check_ms": 250.0,
            "open_min_rise_ratio": 0.03,
            "short_tau_factor": 0.35,
            "isolation_min_kohm": 500.0,
            "residual_abs_v": 60.0,
            "residual_ratio": 0.10,
            "safe_close_ratio": 0.85,
            "sensor_bias_abs_v": 15.0,
            "sensor_bias_ratio": 0.03,
            "sensor_bias_dwell_ms": 100.0,
        }
        self.electrical = {
            "ok": Electrical(800.0, 30.0, 1000.0),
            "open": Electrical(920.0, 200.0, 5000.0),
            "timeout": Electrical(760.0, 200.0, 5000.0),
            "short": Electrical(880.0, 100.0, 3000.0),
            "weld": Electrical(640.0, 60.0, 1000.0),
            "unsafe": Electrical(820.0, 100.0, 2000.0),
            "unsafe_ratio": Electrical(815.0, 35.0, 1000.0),
            "unsafe_isolation": Electrical(825.0, 35.0, 1000.0),
            "unsafe_preready": Electrical(818.0, 35.0, 1000.0),
            "unsafe_crash": Electrical(822.0, 35.0, 1000.0),
            "isolation": Electrical(700.0, 80.0, 1000.0),
            "sensor": Electrical(790.0, 35.0, 1000.0),
            "residual": Electrical(900.0, 25.0, 2000.0),
            "bounce": Electrical(600.0, 50.0, 1000.0),
            "aux_timeout": Electrical(840.0, 40.0, 2000.0),
            "stale_aux": Electrical(810.0, 40.0, 1000.0),
            "boundary": Electrical(860.0, 100.0, 2000.0),
            "bad_input": Electrical(720.0, 20.0, 500.0),
            "weld_low": Electrical(910.0, 75.0, 1200.0),
            "unsafe_aux": Electrical(830.0, 120.0, 2000.0),
            "open_aux": Electrical(680.0, 150.0, 4000.0),
            "residual_bounce": Electrical(870.0, 45.0, 1800.0),
            "dense": Electrical(805.0, 32.0, 1100.0),
        }

    def case_id(self, label: str) -> str:
        # Opaque deterministic IDs prevent the hidden identifier from leaking
        # the intended diagnostic class to the submitted implementation.
        del label
        return f"{self.stream.take(0, 0xFFFFFF):06x}{self.stream.take(0, 0xFFFFFF):06x}"

    def case(self, label: str, capture: str, **updates):
        e = self.electrical[label]
        item = {
            "case_id": self.case_id(label),
            "capture": capture,
            "capacitance_uf": e.capacitance_uf,
            "precharge_ohm": e.resistance_ohm,
            "limits": dict(self.limits),
        }
        if label == "timeout":
            item["limits"]["max_precharge_ms"] = 700.0
        if label == "boundary":
            item["limits"]["max_precharge_ms"] = 300.0
        item.update(updates)
        return item

    @staticmethod
    def irregular_times(end: float, extras: set[float]) -> list[float]:
        steps = [7.0, 13.0, 11.0, 17.0, 9.0]
        values = [0.0]
        index = 0
        while values[-1] < end:
            values.append(min(end, values[-1] + steps[index % len(steps)]))
            index += 1
        return sorted(set(values) | {float(x) for x in extras if 0.0 <= x <= end})

    def rows(self, label: str, *, dense: bool = False) -> list[dict[str, float | int]]:
        e = self.electrical[label]
        limits = dict(self.limits)
        if label == "timeout":
            limits["max_precharge_ms"] = 700.0
        if label == "boundary":
            limits["max_precharge_ms"] = 300.0

        start = 50.0
        initial_link = 8.0
        expected_tau = e.resistance_ohm * e.capacitance_uf / 1000.0
        actual_tau = expected_tau
        if label == "short":
            actual_tau = 0.20 * expected_tau

        ready_continuous = start - actual_tau * math.log(
            e.pack_v * (1.0 - limits["ready_ratio"]) / (e.pack_v - initial_link)
        )
        main_cmd_at = max(start + 100.0, ready_continuous + 25.0)
        pos_aux_at = main_cmd_at + 10.0
        neg_aux_at = main_cmd_at + 15.0
        pre_aux_at = start + 20.0

        no_mains = {"open", "timeout", "isolation", "bounce", "aux_timeout", "open_aux"}
        if label in no_mains:
            main_cmd_at = pos_aux_at = neg_aux_at = math.inf
        if label in {"weld", "weld_low"}:
            main_cmd_at = math.inf
            pos_aux_at = 0.0
            neg_aux_at = math.inf
        if label in {"unsafe", "unsafe_aux", "unsafe_preready"}:
            main_cmd_at = pos_aux_at = neg_aux_at = start + 40.0
        if label in {"aux_timeout", "unsafe_aux"}:
            pre_aux_at = start + 120.0
        if label == "open_aux":
            pre_aux_at = start + 150.0
        if label == "boundary":
            pre_aux_at = 130.0
            main_cmd_at, pos_aux_at, neg_aux_at = 370.0, 380.0, 385.0

        deadline = start + limits["max_precharge_ms"]
        end = max(
            deadline + 180.0,
            (neg_aux_at if math.isfinite(neg_aux_at) else 0.0) + limits["sensor_bias_dwell_ms"] + 160.0,
            start + limits["open_check_ms"] + 120.0,
        )
        extras = {
            start, pre_aux_at, main_cmd_at, pos_aux_at, neg_aux_at,
            deadline, start + limits["open_check_ms"],
            25.0, 70.0, 80.0, 90.0, 130.0, 145.0, 160.0,
        }
        if dense:
            times = [i * 0.25 for i in range(int(end / 0.25) + 1)]
        else:
            times = self.irregular_times(end, extras)

        rows: list[dict[str, float | int]] = []
        for t in times:
            pre_cmd = int(t >= start)
            pre_aux = int(t >= pre_aux_at)
            pos_cmd = int(t >= main_cmd_at)
            neg_cmd = int(t >= main_cmd_at)
            pos_aux = int(t >= pos_aux_at)
            neg_aux = int(t >= neg_aux_at)
            iso = 1000.0
            crash = 0

            if label in {"open", "open_aux"}:
                link = initial_link
            elif label == "boundary":
                if t < start:
                    link = initial_link
                elif t <= deadline:
                    fraction = (t - start) / (deadline - start)
                    link = initial_link + fraction * (limits["ready_ratio"] * e.pack_v - initial_link)
                else:
                    link = e.pack_v
            else:
                link = (
                    initial_link
                    if t < start
                    else e.pack_v - (e.pack_v - initial_link) * math.exp(-(t - start) / actual_tau)
                )

            if label in {"residual", "residual_bounce"} and t < start:
                link = max(limits["residual_abs_v"] + 25.0, 0.22 * e.pack_v)
            if label in {"isolation", "weld_low"} and t >= start + 20.0:
                iso = 250.0
            if label == "stale_aux":
                pre_aux = int(t < 25.0 or t >= 70.0)
            if label in {"bounce", "residual_bounce"}:
                if 70.0 <= t < 80.0:
                    pre_aux = 1
                elif 80.0 <= t < 90.0:
                    pre_aux = 0
                elif t >= 90.0:
                    pre_aux = 1
            if label == "boundary":
                if 130.0 <= t < 145.0:
                    pre_aux = 1
                elif 145.0 <= t < 160.0:
                    pre_aux = 0
                elif t >= 160.0:
                    pre_aux = 1

            # Closing both mains equalizes the link in normal cases. A
            # dedicated sensor case retains a realistic biased measurement.
            if pos_aux and neg_aux:
                if label == "sensor":
                    link = e.pack_v - 55.0
                elif label == "unsafe_ratio":
                    # Keep the closure edge itself safe, then introduce a
                    # post-readiness voltage collapse on the next sample.
                    link = 0.80 * e.pack_v if t > neg_aux_at else e.pack_v
                elif label == "unsafe_preready":
                    # Isolate the pre-readiness UNSAFE_CLOSE branch: the first
                    # row with both mains active is safe for the close-ratio
                    # threshold but still below the readiness threshold.
                    link = (
                        0.5 * (limits["safe_close_ratio"] + limits["ready_ratio"])
                        * e.pack_v
                        if t <= neg_aux_at
                        else e.pack_v
                    )
                elif label not in {"unsafe", "unsafe_aux"}:
                    link = e.pack_v

            # This case reaches readiness first, then closes both mains with
            # isolation below the floor. It isolates the isolation branch of
            # UNSAFE_CLOSE from the pre-ready and crash branches.
            if label == "unsafe_isolation" and t > neg_aux_at:
                iso = 250.0

            if label == "unsafe":
                crash = int(t >= start + 40.0)
            if label == "unsafe_crash":
                crash = int(t >= neg_aux_at)
            if label == "bad_input" and t == times[min(3, len(times) - 1)]:
                pre_aux = 2

            pack_current = 0.0
            if pre_cmd and not (pos_aux and neg_aux):
                pack_current = (e.pack_v - float(link)) / e.resistance_ohm
            rows.append({
                "t_ms": float(t),
                "pack_v": e.pack_v,
                "link_v": float(link),
                "pack_a": float(pack_current),
                "pre_cmd": pre_cmd,
                "pre_aux": pre_aux,
                "pos_cmd": pos_cmd,
                "pos_aux": pos_aux,
                "neg_cmd": neg_cmd,
                "neg_aux": neg_aux,
                "iso_kohm": iso,
                "crash": crash,
            })
        return rows

    def write_capture(self, filename: str, rows, duplicate: bool = False) -> Path:
        path = self.root / filename
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
            writer.writeheader()
            for index, row in enumerate(rows):
                if duplicate and index == 5:
                    stale = dict(row)
                    stale["pre_aux"] = 1 - int(row["pre_aux"])
                    writer.writerow(stale)
                writer.writerow(row)
        return path

    def write_index(self, cases, filename: str = "index.json") -> Path:
        path = self.root / filename
        path.write_text(
            json.dumps({"format": "hv-powerup/1", "cases": cases}, indent=2) + "\n",
            encoding="utf-8",
        )
        return path


def invoke(index: Path, out: Path, timeout: float = 30.0):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(APP)
    return subprocess.run(
        CLI + ["--index", str(index), "--out", str(out)],
        cwd=APP,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_output_file(out: Path, name: str) -> Path:
    """Reject symlinked output directories/files before reading graded artifacts."""
    assert out.exists() and out.is_dir(), f"missing output directory: {out}"
    assert not out.is_symlink(), f"symlinked output directory is not allowed: {out}"
    resolved_out = out.resolve(strict=True)
    path = out / name
    assert path.exists() and path.is_file(), f"missing output file: {path}"
    assert not path.is_symlink(), f"symlinked output file is not allowed: {path}"
    resolved_path = path.resolve(strict=True)
    assert resolved_path.parent == resolved_out, f"output escaped expected directory: {path}"
    return path


def read_report(out: Path):
    raw = _safe_output_file(out, "report.json").read_text(encoding="utf-8")
    assert raw.endswith("\n")
    # The task contract requires deterministic UTF-8 JSON with two-space
    # indentation. Check the raw bytes before json.loads() normalizes away
    # whitespace so an indent=4/compact serializer cannot pass unnoticed.
    assert re.search(r'(?m)^  "format":', raw)
    assert re.search(r'(?m)^  "cases":', raw)
    assert re.search(r'(?m)^  "aggregate":', raw)
    assert "\t" not in raw
    return json.loads(raw), raw


def read_events(out: Path):
    path = _safe_output_file(out, "events.csv")
    raw = path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ["case_id", "time_ms", "event", "channel", "value", "detail"]
        rows = list(reader)
    assert all(TIME_PATTERN.fullmatch(row["time_ms"]) for row in rows)
    return rows, raw


def digital_edges(rows, channel):
    previous = 0
    result = []
    for row in rows:
        current = int(row[channel])
        if current != previous:
            result.append((float(row["t_ms"]), "rise" if current else "fall", str(current)))
        previous = current
    return result


def first_rise(rows, channel, earliest=-math.inf):
    for time_value, kind, _ in digital_edges(rows, channel):
        if kind == "rise" and time_value >= earliest:
            return time_value
    return None


def crossing_time(rows, start, function):
    points = [row for row in rows if float(row["t_ms"]) >= start]
    if not points:
        return None
    previous = points[0]
    previous_value = float(function(previous))
    if previous_value >= 0:
        return float(previous["t_ms"])
    for current in points[1:]:
        value = float(function(current))
        if previous_value < 0 <= value:
            t0, t1 = float(previous["t_ms"]), float(current["t_ms"])
            return t0 + (-previous_value) * (t1 - t0) / (value - previous_value)
        previous, previous_value = current, value
    return None


def expected_ready(rows, ratio):
    start = first_rise(rows, "pre_cmd")
    if start is None:
        return None
    return crossing_time(
        rows,
        start,
        lambda row: float(row["link_v"]) - ratio * float(row["pack_v"]),
    )


def interpolate_value(rows, at_ms, key):
    """Independently linearly interpolate one analog value within the capture."""
    if at_ms < float(rows[0]["t_ms"]) or at_ms > float(rows[-1]["t_ms"]):
        raise AssertionError("interpolation requested outside capture")
    for row in rows:
        if float(row["t_ms"]) == at_ms:
            return float(row[key])
    for left, right in zip(rows, rows[1:]):
        t0, t1 = float(left["t_ms"]), float(right["t_ms"])
        if t0 < at_ms < t1:
            fraction = (at_ms - t0) / (t1 - t0)
            return float(left[key]) + fraction * (float(right[key]) - float(left[key]))
    return float(rows[-1][key])


def expected_tau(rows):
    """Independently derive the 63.21205588% RC crossing delay."""
    start = first_rise(rows, "pre_cmd")
    if start is None:
        return None
    pack_start = interpolate_value(rows, start, "pack_v")
    link_start = interpolate_value(rows, start, "link_v")
    target = link_start + 0.6321205588 * (pack_start - link_start)
    at_ms = crossing_time(rows, start, lambda row: float(row["link_v"]) - target)
    return None if at_ms is None else at_ms - start


def expected_window_metrics(rows, limits):
    """Independently derive current peak and positive link slew in the metric window."""
    start = first_rise(rows, "pre_cmd")
    if start is None:
        return None, None
    ready = expected_ready(rows, limits["ready_ratio"])
    end = min(
        float(rows[-1]["t_ms"]),
        start + float(limits["max_precharge_ms"]),
        ready if ready is not None else math.inf,
    )
    currents = [
        abs(interpolate_value(rows, start, "pack_a")),
        abs(interpolate_value(rows, end, "pack_a")),
    ]
    for row in rows:
        at_ms = float(row["t_ms"])
        if start <= at_ms <= end:
            currents.append(abs(float(row["pack_a"])))

    positive_slopes = []
    for left, right in zip(rows, rows[1:]):
        t0, t1 = float(left["t_ms"]), float(right["t_ms"])
        if t1 <= start or t0 >= end:
            continue
        slope = (float(right["link_v"]) - float(left["link_v"])) / (t1 - t0)
        if slope > 0:
            positive_slopes.append(slope)
    return max(currents), max(positive_slopes, default=0.0)


def expected_auxiliary_metrics(rows):
    """Independently derive all neg/pos/pre delays and auxiliary edge counts."""
    pairs = {
        "neg": ("neg_cmd", "neg_aux"),
        "pos": ("pos_cmd", "pos_aux"),
        "pre": ("pre_cmd", "pre_aux"),
    }
    delays = {}
    counts = {}
    for name, (command, auxiliary) in pairs.items():
        command_at = first_rise(rows, command)
        auxiliary_at = None if command_at is None else first_rise(rows, auxiliary, command_at)
        delays[name] = (
            None if command_at is None or auxiliary_at is None else auxiliary_at - command_at
        )
        counts[name] = len(digital_edges(rows, auxiliary))
    return delays, counts


def assert_optional_number(actual, expected, *, abs_tol=None, rel_tol=None):
    """Compare nullable numeric metrics without accepting scalar substitutes for null."""
    if expected is None:
        assert actual is None
    else:
        assert actual is not None
        assert actual == pytest.approx(expected, abs=abs_tol, rel=rel_tol)


def assert_report_schema(report):
    assert isinstance(report, dict)
    assert list(report) == ["format", "cases", "aggregate"]
    assert report["format"] == "hv-powerup-report/1"
    assert list(report["aggregate"]) == ["case_count", "ok_count", "fault_count", "verdict_histogram"]
    for key in ("case_count", "ok_count", "fault_count"):
        assert type(report["aggregate"][key]) is int
        assert report["aggregate"][key] >= 0
    assert isinstance(report["aggregate"]["verdict_histogram"], dict)
    assert all(type(value) is int and value >= 0 for value in report["aggregate"]["verdict_histogram"].values())
    assert list(report["aggregate"]["verdict_histogram"]) == sorted(report["aggregate"]["verdict_histogram"])
    assert [case["case_id"] for case in report["cases"]] == sorted(case["case_id"] for case in report["cases"])
    for case in report["cases"]:
        assert list(case) == CASE_KEYS
        assert isinstance(case["case_id"], str) and case["case_id"]
        assert case["input_state"] in {"valid", "invalid"}
        assert isinstance(case["verdict"], str) and case["verdict"] in PRECEDENCE + ["BAD_INPUT"]
        assert isinstance(case["flags"], list) and all(isinstance(value, str) for value in case["flags"])
        assert isinstance(case["messages"], list) and all(isinstance(value, str) for value in case["messages"])
        assert isinstance(case["metrics"], dict)
        assert list(case["metrics"]) == METRIC_KEYS
        for key in METRIC_KEYS[:-2]:
            value = case["metrics"][key]
            assert value is None or (isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value))
        assert isinstance(case["metrics"]["aux_delay_ms"], dict)
        assert isinstance(case["metrics"]["aux_edges"], dict)
        assert list(case["metrics"]["aux_delay_ms"]) == ["neg", "pos", "pre"]
        assert list(case["metrics"]["aux_edges"]) == ["neg", "pos", "pre"]
        assert all(
            value is None or (isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value))
            for value in case["metrics"]["aux_delay_ms"].values()
        )
        assert all(type(value) is int and value >= 0 for value in case["metrics"]["aux_edges"].values())
        assert isinstance(case["evidence"], list) and case["evidence"]
        assert all(list(item) == ["code", "time_ms", "detail"] for item in case["evidence"])
        for item in case["evidence"]:
            assert isinstance(item["code"], str) and item["code"] in PRECEDENCE + ["BAD_INPUT"]
            assert item["time_ms"] is None or (isinstance(item["time_ms"], (int, float)) and not isinstance(item["time_ms"], bool) and math.isfinite(item["time_ms"]))
            assert isinstance(item["detail"], str) and item["detail"]
        assert case["evidence"][0]["code"] == case["verdict"]
        assert case["flags"] == sorted(case["flags"], key=PRECEDENCE.index)
        assert [item["code"] for item in case["evidence"]] == [
            case["verdict"], *case["flags"]
        ]
        assert case["messages"] == sorted(case["messages"])

    expected_histogram = dict(sorted(Counter(
        case["verdict"] for case in report["cases"]
    ).items()))
    assert report["aggregate"]["verdict_histogram"] == expected_histogram
    assert sum(report["aggregate"]["verdict_histogram"].values()) == report["aggregate"]["case_count"]


def assert_event_ledger(case_id, source_rows, limits, case_report, event_rows):
    actual = [row for row in event_rows if row["case_id"] == case_id]
    if case_report["input_state"] == "invalid":
        assert len(actual) == 1
        row = actual[0]
        assert row["time_ms"] == "0.000000"
        assert row["event"] == "verdict"
        assert row["channel"] == "system"
        assert row["value"] == "BAD_INPUT"
        assert row["detail"] == case_report["evidence"][0]["detail"]
        return

    expected_transitions = []
    for channel in DIGITAL_CHANNELS:
        for event_time, event, value in digital_edges(source_rows, channel):
            expected_transitions.append((round(event_time, 6), event, channel, value))
    transition_rows = [row for row in actual if row["event"] in {"rise", "fall"}]
    observed_transitions = [
        (float(row["time_ms"]), row["event"], row["channel"], row["value"])
        for row in transition_rows
    ]
    assert sorted(observed_transitions) == sorted(expected_transitions)
    assert all(row["detail"] == "digital transition" for row in transition_rows)

    verdict_rows = [row for row in actual if row["event"] == "verdict"]
    assert len(verdict_rows) == 1
    assert verdict_rows[0]["channel"] == "system"
    assert verdict_rows[0]["value"] == case_report["verdict"]
    assert verdict_rows[0]["detail"] == case_report["evidence"][0]["detail"]
    assert float(verdict_rows[0]["time_ms"]) == pytest.approx(
        case_report["evidence"][0]["time_ms"] or 0.0, abs=1e-6
    )

    ready_rows = [row for row in actual if row["event"] == "ready"]
    ready = expected_ready(source_rows, limits["ready_ratio"])
    if ready is None:
        assert ready_rows == []
    else:
        assert len(ready_rows) == 1
        assert ready_rows[0]["channel"] == "link_v"
        assert float(ready_rows[0]["time_ms"]) == pytest.approx(ready, abs=5.0)
        assert float(ready_rows[0]["value"]) == pytest.approx(
            limits["ready_ratio"] * source_rows[0]["pack_v"], abs=1.0
        )
        assert ready_rows[0]["detail"] == "readiness threshold crossed"

    assert len(actual) == len(expected_transitions) + len(ready_rows) + 1
    keys = [
        (row["case_id"], float(row["time_ms"]), row["event"], row["channel"], row["value"])
        for row in actual
    ]
    assert keys == sorted(keys)


@pytest.fixture()
def hidden(tmp_path, request):
    """Provide an isolated hidden generator with a distinct deterministic seed per test.

    The seed is derived from the hidden pytest node id rather than one suite-global
    constant, so case IDs / filenames cannot be reused as a fixed cross-test lookup
    table. Acceptance expectations are still deterministic for each generated input.
    """
    digest = hashlib.sha256(
        f"hv-powerup-hidden-v3::{request.node.nodeid}".encode("utf-8")
    ).digest()
    seed = int.from_bytes(digest[:8], "big") & 0x7FFFFFFF
    return HiddenCases(tmp_path, seed)


def build_fault_matrix(hidden):
    """Create the complete single-fault matrix and its independent expectations."""
    expected = {
        "ok": "OK",
        "open": "OPEN_PRECHARGE",
        "timeout": "PRECHARGE_TIMEOUT",
        "short": "BYPASS_OR_SHORT",
        "weld": "WELDED_CONTACTOR",
        "unsafe": "UNSAFE_CLOSE",
        "unsafe_ratio": "UNSAFE_CLOSE",
        "unsafe_isolation": "UNSAFE_CLOSE",
        "isolation": "LOW_ISOLATION",
        "sensor": "SENSOR_BIAS",
        "residual": "RESIDUAL_LINK",
        "bounce": "CONTACT_BOUNCE",
        "aux_timeout": "AUX_TIMEOUT",
        "stale_aux": "OK",
        "bad_input": "BAD_INPUT",
    }
    cases = []
    rows_by_id = {}
    limits_by_id = {}
    verdict_by_id = {}
    label_by_id = {}
    electrical_values = []
    for label, verdict in expected.items():
        filename = f"capture-{hidden.stream.take(100000, 999999)}.csv"
        rows = hidden.rows(label)
        hidden.write_capture(filename, rows)
        case = hidden.case(label, filename)
        cases.append(case)
        rows_by_id[case["case_id"]] = rows
        limits_by_id[case["case_id"]] = case["limits"]
        verdict_by_id[case["case_id"]] = verdict
        label_by_id[case["case_id"]] = label
        electrical_values.append(
            (hidden.electrical[label].pack_v, case["capacitance_uf"], case["precharge_ohm"])
        )
    return cases, rows_by_id, limits_by_id, verdict_by_id, label_by_id, electrical_values


def run_fault_matrix(hidden, tmp_path, suffix):
    """Run the CLI once for a generated single-fault matrix and return parsed artifacts."""
    cases, rows_by_id, limits_by_id, verdict_by_id, label_by_id, electrical_values = build_fault_matrix(hidden)
    index = hidden.write_index(cases, f"matrix-{suffix}.json")
    out = tmp_path / f"matrix-{suffix}-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    return (
        cases,
        rows_by_id,
        limits_by_id,
        verdict_by_id,
        label_by_id,
        electrical_values,
        result,
        report,
        events,
        out,
    )


def run_boundary_case(hidden, tmp_path, suffix):
    """Run the exact-boundary capture with a stale duplicate row inserted first."""
    rows = hidden.rows("boundary")
    filename = f"boundary-{suffix}.csv"
    hidden.write_capture(filename, rows, duplicate=True)
    case = hidden.case("boundary", filename)
    index = hidden.write_index([case], f"boundary-{suffix}-index.json")
    out = tmp_path / f"boundary-{suffix}-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    return rows, case, report["cases"][0], events


def test_single_fault_verdict_matrix_and_parameter_span(hidden, tmp_path):
    """Verify every disclosed primary verdict across the full hidden V/R/C ranges."""
    (
        _cases,
        _rows_by_id,
        _limits_by_id,
        verdict_by_id,
        label_by_id,
        electrical_values,
        _result,
        report,
        _events,
        _out,
    ) = run_fault_matrix(hidden, tmp_path, "verdicts")

    assert min(v[0] for v in electrical_values) == 600.0
    assert max(v[0] for v in electrical_values) == 920.0
    assert min(v[1] for v in electrical_values) == 500.0
    assert max(v[1] for v in electrical_values) == 5000.0
    assert min(v[2] for v in electrical_values) == 20.0
    assert max(v[2] for v in electrical_values) == 200.0
    assert {case["case_id"]: case["verdict"] for case in report["cases"]} == verdict_by_id

    expected_flags = {
        "weld": ["AUX_TIMEOUT"],
        "unsafe": ["SENSOR_BIAS"],
        "unsafe_ratio": ["SENSOR_BIAS"],
        "unsafe_isolation": ["LOW_ISOLATION"],
    }
    for case in report["cases"]:
        label = label_by_id[case["case_id"]]
        assert case["flags"] == expected_flags.get(label, [])


def test_unsafe_close_ratio_and_isolation_subconditions(hidden, tmp_path):
    """Require UNSAFE_CLOSE when only safe-ratio or isolation-at-close is violated."""
    cases = []
    rows_by_id = {}
    labels = ("unsafe_ratio", "unsafe_isolation")
    for label in labels:
        filename = f"{label}-{hidden.stream.take(100000, 999999)}.csv"
        rows = hidden.rows(label)
        hidden.write_capture(filename, rows)
        case = hidden.case(label, filename)
        cases.append(case)
        rows_by_id[case["case_id"]] = (label, rows, case["limits"])

    index = hidden.write_index(cases, "unsafe-subconditions-index.json")
    out = tmp_path / "unsafe-subconditions-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    verdicts = {item["case_id"]: item["verdict"] for item in report["cases"]}

    for case in cases:
        case_id = case["case_id"]
        label, rows, limits = rows_by_id[case_id]
        ready = expected_ready(rows, limits["ready_ratio"])
        assert ready is not None
        trigger_row = next(
            row
            for row in rows
            if int(row["pos_aux"]) == 1
            and int(row["neg_aux"]) == 1
            and (
                (
                    label == "unsafe_ratio"
                    and float(row["link_v"]) / float(row["pack_v"])
                    < limits["safe_close_ratio"]
                )
                or (
                    label == "unsafe_isolation"
                    and float(row["iso_kohm"]) < limits["isolation_min_kohm"]
                )
            )
        )
        assert float(trigger_row["t_ms"]) >= ready
        assert int(trigger_row["crash"]) == 0
        ratio = float(trigger_row["link_v"]) / float(trigger_row["pack_v"])

        if label == "unsafe_ratio":
            assert ratio < limits["safe_close_ratio"]
            assert float(trigger_row["iso_kohm"]) >= limits["isolation_min_kohm"]
        else:
            assert ratio >= limits["safe_close_ratio"]
            assert float(trigger_row["iso_kohm"]) < limits["isolation_min_kohm"]

        assert verdicts[case_id] == "UNSAFE_CLOSE"
        expected_flags = {
            "unsafe_ratio": ["SENSOR_BIAS"],
            "unsafe_isolation": ["LOW_ISOLATION"],
        }
        item = next(entry for entry in report["cases"] if entry["case_id"] == case_id)
        assert item["flags"] == expected_flags[label]


def test_unsafe_close_preready_and_crash_subconditions(hidden, tmp_path):
    """Isolate the pre-ready and crash-only UNSAFE_CLOSE OR branches."""
    cases = []
    rows_by_id = {}
    for label in ("unsafe_preready", "unsafe_crash"):
        filename = f"{label}-{hidden.stream.take(100000, 999999)}.csv"
        rows = hidden.rows(label)
        hidden.write_capture(filename, rows)
        case = hidden.case(label, filename)
        cases.append(case)
        rows_by_id[case["case_id"]] = (label, rows, case["limits"])

    index = hidden.write_index(cases, "unsafe-independent-or-index.json")
    out = tmp_path / "unsafe-independent-or-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    verdicts = {item["case_id"]: item["verdict"] for item in report["cases"]}

    for case in cases:
        case_id = case["case_id"]
        label, rows, limits = rows_by_id[case_id]
        ready = expected_ready(rows, limits["ready_ratio"])
        assert ready is not None

        if label == "unsafe_preready":
            trigger = next(
                row
                for row in rows
                if int(row["pos_aux"]) == 1
                and int(row["neg_aux"]) == 1
                and float(row["t_ms"]) < ready
            )
            ratio = float(trigger["link_v"]) / float(trigger["pack_v"])
            assert ratio >= limits["safe_close_ratio"]
            assert ratio < limits["ready_ratio"]
            assert float(trigger["iso_kohm"]) >= limits["isolation_min_kohm"]
            assert int(trigger["crash"]) == 0
        else:
            trigger = next(
                row
                for row in rows
                if int(row["pos_aux"]) == 1
                and int(row["neg_aux"]) == 1
                and int(row["crash"]) == 1
            )
            ratio = float(trigger["link_v"]) / float(trigger["pack_v"])
            assert float(trigger["t_ms"]) >= ready
            assert ratio >= limits["ready_ratio"]
            assert ratio >= limits["safe_close_ratio"]
            assert float(trigger["iso_kohm"]) >= limits["isolation_min_kohm"]

        assert verdicts[case_id] == "UNSAFE_CLOSE"
        item = next(entry for entry in report["cases"] if entry["case_id"] == case_id)
        assert item["flags"] == []


def test_all_valid_metrics_are_independently_recomputed(hidden, tmp_path):
    """Value-check every disclosed metric across all valid hidden fault cases."""
    (
        _cases,
        rows_by_id,
        limits_by_id,
        _verdict_by_id,
        _label_by_id,
        _electrical_values,
        _result,
        report,
        _events,
        _out,
    ) = run_fault_matrix(hidden, tmp_path, "all-metrics")

    nonzero_peak_seen = False
    nonzero_slew_seen = False
    for item in report["cases"]:
        if item["input_state"] != "valid":
            continue
        case_id = item["case_id"]
        rows = rows_by_id[case_id]
        limits = limits_by_id[case_id]
        metrics = item["metrics"]

        start = first_rise(rows, "pre_cmd")
        ready = expected_ready(rows, limits["ready_ratio"])
        ready_delay = None if start is None or ready is None else ready - start
        ready_link = None if ready is None else interpolate_value(rows, ready, "link_v")
        final_pack = float(rows[-1]["pack_v"])
        final_ratio = None if final_pack == 0 else float(rows[-1]["link_v"]) / final_pack
        tau = expected_tau(rows)
        peak, slew = expected_window_metrics(rows, limits)
        delays, counts = expected_auxiliary_metrics(rows)

        assert_optional_number(metrics["precharge_start_ms"], start, abs_tol=5.0)
        assert_optional_number(metrics["ready_at_ms"], ready, abs_tol=5.0)
        assert_optional_number(metrics["ready_delay_ms"], ready_delay, abs_tol=5.0)
        assert_optional_number(metrics["ready_link_v"], ready_link, abs_tol=1.0)
        assert_optional_number(metrics["final_link_ratio"], final_ratio, abs_tol=0.002)
        assert_optional_number(metrics["tau_ms"], tau, rel_tol=0.05)
        assert_optional_number(metrics["peak_abs_pack_a"], peak, abs_tol=0.5)
        slew_tolerance = None if slew is None else max(0.05, abs(slew) * 0.03)
        assert_optional_number(
            metrics["max_link_slew_v_per_ms"], slew, abs_tol=slew_tolerance
        )

        for name in ("neg", "pos", "pre"):
            assert_optional_number(metrics["aux_delay_ms"][name], delays[name], abs_tol=5.0)
            assert metrics["aux_edges"][name] == counts[name]

        if start is not None and ready is not None:
            assert metrics["ready_delay_ms"] == pytest.approx(
                metrics["ready_at_ms"] - metrics["precharge_start_ms"], abs=1e-6
            )
        nonzero_peak_seen |= peak is not None and peak > 1.0
        nonzero_slew_seen |= slew is not None and slew > 0.1

    assert nonzero_peak_seen
    assert nonzero_slew_seen


def test_report_schema_auxiliary_order_and_event_ledger(hidden, tmp_path):
    """Verify canonical JSON order and the complete transition/ready/verdict CSV ledger."""
    (
        _cases,
        rows_by_id,
        limits_by_id,
        _verdict_by_id,
        _label_by_id,
        _electrical_values,
        _result,
        report,
        events,
        _out,
    ) = run_fault_matrix(hidden, tmp_path, "ledger")

    assert_report_schema(report)
    for case_report in report["cases"]:
        assert_event_ledger(
            case_report["case_id"],
            rows_by_id[case_report["case_id"]],
            limits_by_id[case_report["case_id"]],
            case_report,
            events,
        )


def test_stale_auxiliary_edge_is_ignored_for_delay(hidden, tmp_path):
    """Require auxiliary delay to use the first rise at or after command assertion."""
    filename = "stale-aux.csv"
    rows = hidden.rows("stale_aux")
    hidden.write_capture(filename, rows)
    case = hidden.case("stale_aux", filename)
    index = hidden.write_index([case], "stale-index.json")
    out = tmp_path / "stale-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    item = report["cases"][0]
    assert item["verdict"] == "OK"
    assert item["metrics"]["aux_delay_ms"]["pre"] == 20.0


def test_aggregate_counts_and_exact_stdout(hidden, tmp_path):
    """Verify aggregate totals and the exact successful CLI summary line."""
    (
        _cases,
        _rows_by_id,
        _limits_by_id,
        verdict_by_id,
        _label_by_id,
        _electrical_values,
        result,
        report,
        _events,
        out,
    ) = run_fault_matrix(hidden, tmp_path, "aggregate")

    count = len(verdict_by_id)
    ok_count = sum(verdict == "OK" for verdict in verdict_by_id.values())
    fault_count = count - ok_count  # BAD_INPUT is explicitly a fault in instruction.md.
    assert report["aggregate"]["case_count"] == count
    assert report["aggregate"]["ok_count"] == ok_count
    assert report["aggregate"]["fault_count"] == fault_count
    expected_histogram = dict(sorted(Counter(verdict_by_id.values()).items()))
    assert report["aggregate"]["verdict_histogram"] == expected_histogram
    assert sum(report["aggregate"]["verdict_histogram"].values()) == count
    assert result.stdout == (
        f"cases={count} ok={ok_count} faults={fault_count} out={out.resolve()}\n"
    )


def test_simultaneous_fault_precedence_and_flags(hidden, tmp_path):
    """Verify primary verdict precedence and ordered flags for combined faults."""
    expected = {
        "weld_low": ("WELDED_CONTACTOR", ["LOW_ISOLATION", "AUX_TIMEOUT"]),
        "unsafe_aux": ("UNSAFE_CLOSE", ["SENSOR_BIAS", "AUX_TIMEOUT"]),
        "open_aux": ("OPEN_PRECHARGE", ["AUX_TIMEOUT"]),
        "residual_bounce": ("RESIDUAL_LINK", ["CONTACT_BOUNCE"]),
    }
    cases = []
    expected_by_id = {}
    for label in expected:
        filename = f"capture-{hidden.stream.take(100000,999999)}.csv"
        hidden.write_capture(filename, hidden.rows(label))
        case = hidden.case(label, filename)
        cases.append(case)
        expected_by_id[case["case_id"]] = expected[label]
    index = hidden.write_index(cases, "combined.json")
    out = tmp_path / "combined-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    for item in report["cases"]:
        verdict, required_flags = expected_by_id[item["case_id"]]
        assert item["verdict"] == verdict
        assert item["flags"] == required_flags
        assert item["flags"] == sorted(item["flags"], key=PRECEDENCE.index)
        assert [entry["code"] for entry in item["evidence"]] == [
            verdict, *required_flags
        ]




def test_residual_link_requires_both_thresholds_across_varied_limits(hidden, tmp_path):
    """Require RESIDUAL_LINK to satisfy both strict operands, including equalities."""
    # Each scenario varies the per-case thresholds while keeping all unrelated
    # diagnostics clear. The one-sided/equality controls make either a dropped
    # AND operand or a >= substitution observably wrong on valid input.
    scenarios = (
        # name, residual_abs_v, residual_ratio, pre-command link_v, verdict
        ("abs-only-a", 58.0, 0.125, 78.0, "OK"),
        ("abs-only-b", 62.0, 0.130, 82.0, "OK"),
        ("ratio-only-a", 105.0, 0.090, 90.0, "OK"),
        ("ratio-only-b", 112.0, 0.095, 88.0, "OK"),
        ("abs-equality", 72.0, 0.080, 72.0, "OK"),
        ("ratio-equality", 50.0, 0.100, 80.0, "OK"),
        ("both-true-a", 60.0, 0.100, 95.0, "RESIDUAL_LINK"),
        ("both-true-b", 70.0, 0.105, 92.0, "RESIDUAL_LINK"),
    )

    cases = []
    expected_by_id = {}
    witness_by_id = {}
    for name, abs_limit, ratio_limit, pre_link, expected in scenarios:
        rows = hidden.rows("ok")
        for row in rows:
            if float(row["t_ms"]) < 50.0:
                row["link_v"] = pre_link

        filename = f"residual-and-{hidden.stream.take(100000, 999999)}.csv"
        hidden.write_capture(filename, rows)
        case = hidden.case("ok", filename)
        case["limits"]["residual_abs_v"] = abs_limit
        case["limits"]["residual_ratio"] = ratio_limit
        cases.append(case)
        expected_by_id[case["case_id"]] = expected
        witness_by_id[case["case_id"]] = (name, rows, abs_limit, ratio_limit, pre_link)

    index = hidden.write_index(cases, "residual-and-varied-index.json")
    out = tmp_path / "residual-and-varied-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)

    assert len(report["cases"]) == len(scenarios)
    for item in report["cases"]:
        case_id = item["case_id"]
        name, rows, abs_limit, ratio_limit, pre_link = witness_by_id[case_id]
        pack = float(rows[0]["pack_v"])
        abs_true = pre_link > abs_limit
        ratio_true = pre_link > ratio_limit * pack

        # Prove the hidden family actually exercises both one-sided states,
        # both strict-equality boundaries, and positive controls.
        if name.startswith("abs-only"):
            assert abs_true and not ratio_true
        elif name.startswith("ratio-only"):
            assert ratio_true and not abs_true
        elif name == "abs-equality":
            assert pre_link == abs_limit and ratio_true
        elif name == "ratio-equality":
            assert abs_true and pre_link == ratio_limit * pack
        else:
            assert abs_true and ratio_true

        assert item["verdict"] == expected_by_id[case_id]
        if expected_by_id[case_id] == "OK":
            assert "RESIDUAL_LINK" not in item["flags"]
        else:
            assert item["flags"] == []


def test_contact_bounce_precedes_aux_timeout_when_both_fire(hidden, tmp_path):
    """Require CONTACT_BOUNCE to outrank AUX_TIMEOUT in the same valid capture."""
    cases = []
    rows_by_id = {}

    # Two distinct held-out waveforms prevent the precedence check from relying
    # on one exact timestamp pattern. Both keep all higher-priority faults clear.
    patterns = (
        (134.0, 145.0, 160.0),
        (145.0, 160.0, 162.0),
    )
    for index, (first_rise_at, fall_at, second_rise_at) in enumerate(patterns):
        rows = hidden.rows("bounce")
        for row in rows:
            t_ms = float(row["t_ms"])
            row["pre_aux"] = int(
                first_rise_at <= t_ms < fall_at or t_ms >= second_rise_at
            )

        filename = f"bounce-timeout-{index}-{hidden.stream.take(100000, 999999)}.csv"
        hidden.write_capture(filename, rows)
        case = hidden.case("bounce", filename)
        cases.append(case)
        rows_by_id[case["case_id"]] = (rows, case["limits"])

    index_path = hidden.write_index(cases, "bounce-timeout-precedence-index.json")
    out = tmp_path / "bounce-timeout-precedence-out"
    result = invoke(index_path, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)

    for item in report["cases"]:
        rows, limits = rows_by_id[item["case_id"]]
        pre_cmd_at = first_rise(rows, "pre_cmd")
        pre_aux_at = first_rise(rows, "pre_aux", pre_cmd_at)
        pre_aux_edges = digital_edges(rows, "pre_aux")

        assert pre_cmd_at is not None and pre_aux_at is not None
        assert pre_aux_at - pre_cmd_at > limits["aux_delay_ms"]
        assert any(
            current[0] - previous[0] < limits["bounce_interval_ms"]
            for previous, current in zip(pre_aux_edges, pre_aux_edges[1:])
        )
        assert item["verdict"] == "CONTACT_BOUNCE"
        assert item["flags"] == ["AUX_TIMEOUT"]
        assert [evidence["code"] for evidence in item["evidence"]] == [
            "CONTACT_BOUNCE", "AUX_TIMEOUT"
        ]


def test_nondefault_limits_override_boundary_precedence(hidden, tmp_path):
    """Require per-case limit overrides to control bounce and aux-timeout decisions."""
    rows = hidden.rows("boundary")
    filename = "override-boundary.csv"
    hidden.write_capture(filename, rows)

    case = hidden.case("boundary", filename)
    # The same waveform is non-faulting at the default equalities:
    # pre aux delay == 80 ms and adjacent pre_aux edges == 15 ms.
    # Tighten only the case-local limits so both rules now fire.
    case["limits"]["aux_delay_ms"] = 79.0
    case["limits"]["bounce_interval_ms"] = 16.0

    index = hidden.write_index([case], "override-boundary-index.json")
    out = tmp_path / "override-boundary-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr

    report, _ = read_report(out)
    item = report["cases"][0]

    assert item["metrics"]["aux_delay_ms"]["pre"] == pytest.approx(80.0, abs=5.0)
    assert item["metrics"]["aux_edges"]["pre"] == 3
    assert item["verdict"] == "CONTACT_BOUNCE"
    assert item["flags"] == ["AUX_TIMEOUT"]
    assert [entry["code"] for entry in item["evidence"]] == [
        "CONTACT_BOUNCE", "AUX_TIMEOUT"
    ]



def make_sparse_sensor_bias_span(
    hidden, *, dwell_ms: float, start_offset_ms: float, duration_delta_ms: float
):
    """Build one isolated SENSOR_BIAS span with explicit retained-row boundaries."""
    rows = hidden.rows("sensor")
    mains_begin = next(
        float(row["t_ms"])
        for row in rows
        if int(row["pos_aux"]) == 1 and int(row["neg_aux"]) == 1
    )
    bias_start = mains_begin + float(start_offset_ms)
    bias_end = bias_start + float(dwell_ms) + float(duration_delta_ms)
    if bias_end <= bias_start:
        raise AssertionError("sensor-bias test span must have positive duration")

    def row_copy_at(at_ms: float, *, biased: bool):
        template = max(
            (row for row in rows if float(row["t_ms"]) <= at_ms),
            key=lambda row: float(row["t_ms"]),
        )
        cloned = dict(template)
        cloned["t_ms"] = float(at_ms)
        cloned["link_v"] = (
            float(cloned["pack_v"]) - 55.0 if biased else float(cloned["pack_v"])
        )
        cloned["pack_a"] = 0.0
        return cloned

    sparse_rows = []
    # Remove late interior samples so the >dwell case has no retained true row
    # at or beyond the dwell-expiry time; the first false row closes the span.
    sparse_after = bias_start + 0.60 * float(dwell_ms)
    for row in rows:
        t_ms = float(row["t_ms"])
        if t_ms == bias_start or t_ms == bias_end:
            continue
        if sparse_after < t_ms < bias_end:
            continue
        updated = dict(row)
        if int(updated["pos_aux"]) == 1 and int(updated["neg_aux"]) == 1:
            if bias_start <= t_ms < bias_end:
                updated["link_v"] = float(updated["pack_v"]) - 55.0
            else:
                updated["link_v"] = float(updated["pack_v"])
            updated["pack_a"] = 0.0
        sparse_rows.append(updated)

    sparse_rows.append(row_copy_at(bias_start, biased=True))
    sparse_rows.append(row_copy_at(bias_end, biased=False))
    sparse_rows.sort(key=lambda row: float(row["t_ms"]))
    return sparse_rows, bias_start, bias_end


def test_welded_contactor_evidence_time_family(hidden, tmp_path):
    """Pin WELDED_CONTACTOR threshold-expiry evidence across starts, limits, and channels."""
    scenarios = (
        ("pos_aux", 31.0, 65.0),
        ("neg_aux", 77.0, 110.0),
        ("pos_aux", 121.0, 155.0),
        ("neg_aux", 171.0, 85.0),
    )
    cases = []
    expected = {}

    for aux_channel, weld_begin, dwell_ms in scenarios:
        rows = hidden.rows("weld")
        other_aux = "neg_aux" if aux_channel == "pos_aux" else "pos_aux"
        for row in rows:
            t_ms = float(row["t_ms"])
            row["pos_cmd"] = 0
            row["neg_cmd"] = 0
            row[other_aux] = 0
            row[aux_channel] = int(t_ms >= weld_begin)

        assert any(float(row["t_ms"]) == weld_begin for row in rows)
        filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
        hidden.write_capture(filename, rows)
        case = hidden.case("weld", filename)
        case["limits"]["weld_dwell_ms"] = dwell_ms
        cases.append(case)
        expected[case["case_id"]] = weld_begin + dwell_ms

    index = hidden.write_index(cases, "weld-evidence-time-family.json")
    out = tmp_path / "weld-evidence-time-family-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)

    by_id = {item["case_id"]: item for item in report["cases"]}
    assert set(by_id) == set(expected)
    for case_id, evidence_time in expected.items():
        item = by_id[case_id]
        assert item["verdict"] == "WELDED_CONTACTOR"
        assert item["evidence"][0]["code"] == "WELDED_CONTACTOR"
        assert item["evidence"][0]["time_ms"] == pytest.approx(evidence_time, abs=1e-6)
        verdict_rows = [
            row for row in events
            if row["case_id"] == case_id and row["event"] == "verdict"
        ]
        assert len(verdict_rows) == 1
        assert verdict_rows[0]["value"] == "WELDED_CONTACTOR"
        assert float(verdict_rows[0]["time_ms"]) == pytest.approx(evidence_time, abs=1e-6)


def test_welded_contactor_strict_dwell_boundary_family(hidden, tmp_path):
    """Weld dwell is strict >; exact equality is accepted on both main channels."""
    cases = []
    expected = {}

    # Exercise below/equal/above the configured dwell on both positive and
    # negative main auxiliaries.  Keep AUX_TIMEOUT looser than each observed
    # mismatch span so WELDED_CONTACTOR is the only possible fault.
    for channel in ("pos_aux", "neg_aux"):
        for delta_ms, should_fault in ((-4.0, False), (0.0, False), (4.0, True)):
            weld_begin = float(hidden.stream.take(30, 90))
            dwell_ms = float(hidden.stream.take(70, 135))
            weld_end = weld_begin + dwell_ms + delta_ms
            midpoint = weld_begin + 0.5 * (weld_end - weld_begin)
            times = [0.0, weld_begin, midpoint, weld_end, weld_end + 45.0]

            rows = []
            for t_ms in times:
                row = {
                    "t_ms": t_ms,
                    "pack_v": 800.0,
                    "link_v": 0.0,
                    "pack_a": 0.0,
                    "pre_cmd": 0,
                    "pre_aux": 0,
                    "pos_cmd": 0,
                    "pos_aux": 0,
                    "neg_cmd": 0,
                    "neg_aux": 0,
                    "iso_kohm": 1000.0,
                    "crash": 0,
                }
                if weld_begin <= t_ms < weld_end:
                    row[channel] = 1
                rows.append(row)

            filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
            hidden.write_capture(filename, rows)
            case = hidden.case("ok", filename)
            case["limits"]["weld_dwell_ms"] = dwell_ms
            case["limits"]["aux_delay_ms"] = (weld_end - weld_begin) + 50.0
            cases.append(case)
            expected[case["case_id"]] = (should_fault, weld_begin + dwell_ms, rows, case["limits"])

    index = hidden.write_index(cases, "weld-strict-dwell-boundary.json")
    out = tmp_path / "weld-strict-dwell-boundary-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    by_id = {item["case_id"]: item for item in report["cases"]}

    assert set(by_id) == set(expected)
    for case_id, (should_fault, evidence_time, rows, limits) in expected.items():
        item = by_id[case_id]
        if should_fault:
            assert item["verdict"] == "WELDED_CONTACTOR"
            assert item["evidence"][0]["code"] == "WELDED_CONTACTOR"
            assert item["evidence"][0]["time_ms"] == pytest.approx(evidence_time, abs=1e-6)
        else:
            assert item["verdict"] == "OK"
            assert "WELDED_CONTACTOR" not in [entry["code"] for entry in item["evidence"]]
        assert_event_ledger(case_id, rows, limits, item, events)


def test_sensor_bias_strict_dwell_boundary_family(hidden, tmp_path):
    """Exercise below/equal/above dwell at multiple limits and shifted span starts."""
    cases = []
    expected = {}
    scenarios = (
        (75.0, 23.0),
        (100.0, 41.0),
        (135.0, 58.0),
    )
    for dwell_ms, start_offset_ms in scenarios:
        for delta_ms, should_fault in ((-5.0, False), (0.0, False), (5.0, True)):
            rows, bias_start, bias_end = make_sparse_sensor_bias_span(
                hidden,
                dwell_ms=dwell_ms,
                start_offset_ms=start_offset_ms,
                duration_delta_ms=delta_ms,
            )
            filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
            hidden.write_capture(filename, rows)
            case = hidden.case("sensor", filename)
            case["limits"]["sensor_bias_dwell_ms"] = dwell_ms
            cases.append(case)
            expected[case["case_id"]] = {
                "fault": should_fault,
                "evidence_time": bias_start + dwell_ms,
                "span_duration": bias_end - bias_start,
                "dwell": dwell_ms,
            }

    index = hidden.write_index(cases, "sensor-bias-boundary-family.json")
    out = tmp_path / "sensor-bias-boundary-family-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    by_id = {item["case_id"]: item for item in report["cases"]}

    assert set(by_id) == set(expected)
    for case_id, expectation in expected.items():
        item = by_id[case_id]
        codes = [entry["code"] for entry in item["evidence"]]
        if expectation["fault"]:
            assert expectation["span_duration"] > expectation["dwell"]
            assert item["verdict"] == "SENSOR_BIAS"
            assert item["flags"] == []
            assert codes == ["SENSOR_BIAS"]
            assert item["evidence"][0]["time_ms"] == pytest.approx(
                expectation["evidence_time"], abs=1e-6
            )
        else:
            assert expectation["span_duration"] <= expectation["dwell"]
            assert "SENSOR_BIAS" not in codes
            assert item["verdict"] == "OK"


def test_sparse_sensor_bias_span_is_detected_on_closing_sample(hidden, tmp_path):
    """Detect a >dwell sensor-bias span even when no sample lands after the dwell."""
    rows = hidden.rows("sensor")
    limits = dict(hidden.limits)

    mains_begin = next(
        float(row["t_ms"])
        for row in rows
        if int(row["pos_aux"]) == 1 and int(row["neg_aux"]) == 1
    )
    dwell = float(limits["sensor_bias_dwell_ms"])
    bias_end = mains_begin + dwell + 5.0

    # Keep the bias active from mains_begin, then remove every interior sample
    # near the dwell boundary. The first non-biased sample closes the span at
    # bias_end. Correct span-based logic sees duration=dwell+5 ms; a common
    # row-only timer that checks only while the condition is active misses it.
    sparse_rows = []
    for row in rows:
        t_ms = float(row["t_ms"])
        if mains_begin + 70.0 < t_ms < bias_end:
            continue
        updated = dict(row)
        if t_ms >= bias_end:
            updated["link_v"] = float(updated["pack_v"])
            updated["pack_a"] = 0.0
        sparse_rows.append(updated)

    # Ensure the false sample that terminates the active span exists exactly
    # at bias_end, without adding an active sample beyond the dwell threshold.
    if not any(float(row["t_ms"]) == bias_end for row in sparse_rows):
        before = max(
            (row for row in sparse_rows if float(row["t_ms"]) < bias_end),
            key=lambda row: float(row["t_ms"]),
        )
        end_row = dict(before)
        end_row["t_ms"] = bias_end
        end_row["link_v"] = float(end_row["pack_v"])
        end_row["pack_a"] = 0.0
        sparse_rows.append(end_row)
        sparse_rows.sort(key=lambda row: float(row["t_ms"]))

    active_samples = [
        float(row["t_ms"])
        for row in sparse_rows
        if mains_begin <= float(row["t_ms"]) < bias_end
        and int(row["pos_aux"]) == 1
        and int(row["neg_aux"]) == 1
        and abs(float(row["pack_v"]) - float(row["link_v"]))
        > max(
            limits["sensor_bias_abs_v"],
            limits["sensor_bias_ratio"] * abs(float(row["pack_v"])),
        )
    ]
    assert active_samples
    assert max(active_samples) < mains_begin + dwell
    assert bias_end - mains_begin > dwell

    filename = "sparse-sensor-bias.csv"
    hidden.write_capture(filename, sparse_rows)
    case = hidden.case("sensor", filename)
    index = hidden.write_index([case], "sparse-sensor-bias-index.json")
    out = tmp_path / "sparse-sensor-bias-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr

    report, _ = read_report(out)
    item = report["cases"][0]
    assert item["verdict"] == "SENSOR_BIAS"
    assert item["flags"] == []
    assert [entry["code"] for entry in item["evidence"]] == ["SENSOR_BIAS"]
    assert item["evidence"][0]["time_ms"] == pytest.approx(
        mains_begin + dwell, abs=5.0
    )



def test_session_streak_uses_attempt_order_and_full_evidence(hidden, tmp_path):
    """Require session ordering by attempt and count source faults that are only flags."""
    session_id = "8f3a91c2"

    rows_a = hidden.rows("open")
    rows_b = hidden.rows("timeout")
    rows_c = hidden.rows("open")
    start_c = first_rise(rows_c, "pre_cmd")
    assert start_c is not None
    for row in rows_c:
        if float(row["t_ms"]) >= start_c:
            row["iso_kohm"] = 250.0

    captures = []
    for filename, rows in (
        ("c91d2e.csv", rows_a),
        ("0ab47f.csv", rows_b),
        ("7d31aa.csv", rows_c),
    ):
        hidden.write_capture(filename, rows)
        captures.append(filename)

    # Deliberately make lexical case_id order disagree with attempt order and
    # shuffle the index itself. A correct implementation must use attempt.
    attempt1 = hidden.case(
        "open", captures[0], case_id="f3a1c900", session_id=session_id, attempt=1
    )
    attempt2 = hidden.case(
        "timeout", captures[1], case_id="0b7e2d11", session_id=session_id, attempt=2
    )
    attempt3 = hidden.case(
        "open", captures[2], case_id="7ac044de", session_id=session_id, attempt=3
    )
    index = hidden.write_index([attempt3, attempt1, attempt2], "seq-a.json")
    out = tmp_path / "seq-a-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr

    report, _ = read_report(out)
    events, _ = read_events(out)
    by_id = {item["case_id"]: item for item in report["cases"]}

    assert by_id[attempt1["case_id"]]["verdict"] == "OPEN_PRECHARGE"
    assert by_id[attempt2["case_id"]]["verdict"] == "PRECHARGE_TIMEOUT"

    third = by_id[attempt3["case_id"]]
    # Capture-local evidence is LOW_ISOLATION + OPEN_PRECHARGE. The session
    # rule must inspect all local evidence, count OPEN_PRECHARGE even though it
    # is a flag, and insert the session code at its global precedence position.
    assert third["verdict"] == "LOW_ISOLATION"
    assert third["flags"] == ["REPEATED_PRECHARGE_FAILURE", "OPEN_PRECHARGE"]
    assert [entry["code"] for entry in third["evidence"]] == [
        "LOW_ISOLATION", "REPEATED_PRECHARGE_FAILURE", "OPEN_PRECHARGE"
    ]
    source_time = next(
        entry["time_ms"] for entry in third["evidence"] if entry["code"] == "OPEN_PRECHARGE"
    )
    repeated_entry = next(
        entry
        for entry in third["evidence"]
        if entry["code"] == "REPEATED_PRECHARGE_FAILURE"
    )
    repeated_time = repeated_entry["time_ms"]
    assert repeated_time == source_time
    assert repeated_entry["detail"] == (
        "three or more consecutive precharge-path failures in the same session"
    )

    # Flags do not get separate CSV rows; the one verdict row stays aligned
    # with the final primary evidence (LOW_ISOLATION here).
    verdict_rows = [
        row for row in events
        if row["case_id"] == attempt3["case_id"] and row["event"] == "verdict"
    ]
    assert len(verdict_rows) == 1
    assert verdict_rows[0]["value"] == "LOW_ISOLATION"
    assert float(verdict_rows[0]["time_ms"]) == pytest.approx(
        third["evidence"][0]["time_ms"], abs=1e-6
    )



def test_session_invalid_case_is_omitted_without_resetting_streak(hidden, tmp_path):
    """An invalid session case neither increments nor resets the valid-case failure streak."""
    session_id = "7e41b920"
    plan = (
        ("open", "c1000001", 1),
        ("bad_input", "a2000002", 2),
        ("timeout", "e3000003", 3),
        ("open", "b4000004", 4),
    )
    cases = []
    for label, case_id, attempt in plan:
        filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
        hidden.write_capture(filename, hidden.rows(label))
        cases.append(
            hidden.case(
                label,
                filename,
                case_id=case_id,
                session_id=session_id,
                attempt=attempt,
            )
        )

    # Shuffle the physical index so session order must still come from attempt.
    index = hidden.write_index([cases[2], cases[1], cases[3], cases[0]], "seq-invalid-gap.json")
    out = tmp_path / "seq-invalid-gap-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    by_id = {item["case_id"]: item for item in report["cases"]}

    assert by_id[cases[0]["case_id"]]["verdict"] == "OPEN_PRECHARGE"
    assert by_id[cases[1]["case_id"]]["input_state"] == "invalid"
    assert by_id[cases[1]["case_id"]]["verdict"] == "BAD_INPUT"
    assert by_id[cases[2]["case_id"]]["verdict"] == "PRECHARGE_TIMEOUT"

    third_valid_failure = by_id[cases[3]["case_id"]]
    assert third_valid_failure["verdict"] == "REPEATED_PRECHARGE_FAILURE"
    assert third_valid_failure["flags"] == ["OPEN_PRECHARGE"]
    assert [entry["code"] for entry in third_valid_failure["evidence"]] == [
        "REPEATED_PRECHARGE_FAILURE", "OPEN_PRECHARGE"
    ]


def test_session_success_resets_streak_and_later_third_failure_becomes_primary(hidden, tmp_path):
    """Require deterministic duplicate-attempt ordering, reset, and third+ failure behavior."""
    session_id = "2c701fa8"
    plan = (
        # Same attempt number: case_id ordering must place OPEN before OK, so
        # the OK case resets the first failure before the later streak starts.
        ("open", "10000001", 1),
        ("ok", "f0000002", 1),
        ("timeout", "d33000b3", 2),
        ("open", "244000c4", 3),
        ("timeout", "a55000d5", 4),
        ("open", "366000e6", 5),
    )
    cases = []
    for label, case_id, attempt in plan:
        filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
        hidden.write_capture(filename, hidden.rows(label))
        cases.append(
            hidden.case(
                label,
                filename,
                case_id=case_id,
                session_id=session_id,
                attempt=attempt,
            )
        )

    # Reverse input order so neither original index order nor final report
    # case_id order can accidentally implement the session sequence.
    index = hidden.write_index(list(reversed(cases)), "seq-reset.json")
    out = tmp_path / "seq-reset-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    by_id = {item["case_id"]: item for item in report["cases"]}

    assert by_id[cases[0]["case_id"]]["verdict"] == "OPEN_PRECHARGE"
    assert by_id[cases[1]["case_id"]]["verdict"] == "OK"
    assert "REPEATED_PRECHARGE_FAILURE" not in [
        entry["code"] for entry in by_id[cases[3]["case_id"]]["evidence"]
    ]

    fifth = by_id[cases[4]["case_id"]]
    assert fifth["verdict"] == "REPEATED_PRECHARGE_FAILURE"
    assert fifth["flags"] == ["PRECHARGE_TIMEOUT"]
    assert [entry["code"] for entry in fifth["evidence"]] == [
        "REPEATED_PRECHARGE_FAILURE", "PRECHARGE_TIMEOUT"
    ]
    assert fifth["evidence"][0]["time_ms"] == fifth["evidence"][1]["time_ms"]

    sixth = by_id[cases[5]["case_id"]]
    assert sixth["verdict"] == "REPEATED_PRECHARGE_FAILURE"
    assert sixth["flags"] == ["OPEN_PRECHARGE"]
    assert [entry["code"] for entry in sixth["evidence"]] == [
        "REPEATED_PRECHARGE_FAILURE", "OPEN_PRECHARGE"
    ]

    for case, expected in (
        (cases[4], "REPEATED_PRECHARGE_FAILURE"),
        (cases[5], "REPEATED_PRECHARGE_FAILURE"),
    ):
        verdict_rows = [
            row for row in events
            if row["case_id"] == case["case_id"] and row["event"] == "verdict"
        ]
        assert len(verdict_rows) == 1
        assert verdict_rows[0]["value"] == expected
        assert float(verdict_rows[0]["time_ms"]) == pytest.approx(
            by_id[case["case_id"]]["evidence"][0]["time_ms"], abs=1e-6
        )


def test_partial_or_invalid_session_metadata_is_case_local_bad_input(hidden, tmp_path):
    """Require session_id/attempt to be paired and attempt to be a positive JSON integer."""
    rows = hidden.rows("ok")
    names = ("a001.csv", "b002.csv", "c003.csv", "d004.csv")
    for name in names:
        hidden.write_capture(name, rows)

    cases = [
        hidden.case("ok", names[0], case_id="01aa02bb", session_id="s1"),
        hidden.case("ok", names[1], case_id="03cc04dd", attempt=1),
        hidden.case("ok", names[2], case_id="05ee06ff", session_id="s2", attempt=1.0),
        hidden.case("ok", names[3], case_id="07110822", session_id="s3", attempt=True),
    ]
    index = hidden.write_index(cases, "seq-invalid.json")
    out = tmp_path / "seq-invalid-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)

    assert all(item["input_state"] == "invalid" for item in report["cases"])
    assert all(item["verdict"] == "BAD_INPUT" for item in report["cases"])
    assert report["aggregate"]["fault_count"] == 4
    assert report["aggregate"]["ok_count"] == 0
    assert report["aggregate"]["verdict_histogram"] == {"BAD_INPUT": 4}
    assert len(events) == 4
    assert all(row["event"] == "verdict" and row["value"] == "BAD_INPUT" for row in events)



def test_aux_timeout_covers_both_mismatch_directions_with_varied_limits(hidden, tmp_path):
    """Require AUX_TIMEOUT for both cmd=1/aux=0 and cmd=0/aux=1 dwell spans.

    Limits, filenames, case IDs, and the chosen closing/release rows vary with this
    test's hidden seed. This prevents a fixed lookup table from reproducing the
    expected verdict/evidence bytes while also closing the asymmetric AUX_TIMEOUT
    acceptance gap.
    """
    cases = []
    rows_by_id = {}
    expected_evidence_time = {}

    # Two forward-lag cases and two reverse-lag cases.  All limits are comfortably
    # away from the normal 20 ms precharge auxiliary delay and all mismatch spans
    # exceed the selected threshold by at least 15 ms.
    directions = ("forward", "forward", "reverse", "reverse")
    for index, direction in enumerate(directions):
        rows = [dict(row) for row in hidden.rows("ok")]
        delay = float(hidden.stream.take(58, 94))

        if direction == "forward":
            start = next(float(row["t_ms"]) for row in rows if int(row["pre_cmd"]) == 1)
            candidates = [
                float(row["t_ms"])
                for row in rows
                if start + delay + 15.0 <= float(row["t_ms"]) <= start + delay + 55.0
            ]
            assert candidates
            aux_on = candidates[hidden.stream.take(0, len(candidates) - 1)]
            for row in rows:
                row["pre_aux"] = int(float(row["t_ms"]) >= aux_on)
            begin = start
            end = aux_on
        else:
            # Preserve the normal rising response, then command OPEN while the
            # auxiliary remains closed.  AUX_TIMEOUT is defined by inequality, so
            # this reverse mismatch must be treated identically to forward lag.
            candidates = [
                float(row["t_ms"])
                for row in rows
                if 470.0 <= float(row["t_ms"]) <= 620.0
            ]
            assert candidates
            release_at = candidates[hidden.stream.take(0, len(candidates) - 1)]
            for row in rows:
                if float(row["t_ms"]) >= release_at:
                    row["pre_cmd"] = 0
            begin = release_at
            end = float(rows[-1]["t_ms"])

        assert end - begin > delay

        filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
        hidden.write_capture(filename, rows)
        case = hidden.case("ok", filename)
        case["limits"]["aux_delay_ms"] = delay
        cases.append(case)
        rows_by_id[case["case_id"]] = rows
        expected_evidence_time[case["case_id"]] = begin + delay

    index_path = hidden.write_index(cases, "aux-symmetric-hidden.json")
    out = tmp_path / "aux-symmetric-hidden-out"
    result = invoke(index_path, out)
    assert result.returncode == 0, result.stderr

    report, _ = read_report(out)
    events, _ = read_events(out)
    assert_report_schema(report)

    by_id = {item["case_id"]: item for item in report["cases"]}
    assert set(by_id) == {case["case_id"] for case in cases}

    for case in cases:
        case_id = case["case_id"]
        item = by_id[case_id]
        assert item["input_state"] == "valid"
        assert item["verdict"] == "AUX_TIMEOUT"
        assert item["flags"] == []
        assert [entry["code"] for entry in item["evidence"]] == ["AUX_TIMEOUT"]
        assert item["evidence"][0]["time_ms"] == pytest.approx(
            expected_evidence_time[case_id], abs=1e-6
        )

        verdict_rows = [
            row
            for row in events
            if row["case_id"] == case_id and row["event"] == "verdict"
        ]
        assert len(verdict_rows) == 1
        assert verdict_rows[0]["value"] == "AUX_TIMEOUT"
        assert float(verdict_rows[0]["time_ms"]) == pytest.approx(
            expected_evidence_time[case_id], abs=1e-6
        )

        # The complete transition ledger must also match the dynamically generated
        # capture, preventing a generic "unknown case => AUX_TIMEOUT" shortcut.
        assert_event_ledger(
            case_id,
            rows_by_id[case_id],
            case["limits"],
            item,
            events,
        )



def test_valid_capture_without_precharge_rise_still_evaluates_nonstart_rules(hidden, tmp_path):
    """A readable capture with no pre_cmd rise stays valid; start-dependent metrics are null."""
    cases = []
    expected = {}

    # Case 1: no commands/auxiliaries at all, but residual link is above BOTH
    # configured residual thresholds before any command.
    pack_v = float(hidden.stream.take(720, 910))
    residual_abs = float(hidden.stream.take(45, 75))
    residual_ratio = hidden.stream.take(9, 17) / 100.0
    link_v = max(residual_abs + 25.0, residual_ratio * pack_v + 25.0)
    times = [0.0, 37.0, 91.0, 173.0]
    residual_rows = [
        {
            "t_ms": t, "pack_v": pack_v, "link_v": link_v, "pack_a": 0.0,
            "pre_cmd": 0, "pre_aux": 0, "pos_cmd": 0, "pos_aux": 0,
            "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0,
        }
        for t in times
    ]
    residual_name = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(residual_name, residual_rows)
    residual_case = hidden.case("ok", residual_name)
    residual_case["limits"]["residual_abs_v"] = residual_abs
    residual_case["limits"]["residual_ratio"] = residual_ratio
    cases.append(residual_case)
    expected[residual_case["case_id"]] = ("RESIDUAL_LINK", residual_rows, residual_case["limits"])

    # Case 2: no precharge rise, but one main auxiliary remains closed with its
    # own command open longer than weld_dwell_ms. AUX timeout is intentionally
    # looser so the case isolates WELDED_CONTACTOR.
    weld_begin = float(hidden.stream.take(25, 45))
    weld_dwell = float(hidden.stream.take(70, 90))
    weld_end = weld_begin + weld_dwell + float(hidden.stream.take(18, 35))
    end = weld_end + 35.0
    weld_times = [0.0, weld_begin, weld_end, end]
    weld_rows = []
    for t in weld_times:
        weld_rows.append({
            "t_ms": t, "pack_v": pack_v, "link_v": 8.0, "pack_a": 0.0,
            "pre_cmd": 0, "pre_aux": 0, "pos_cmd": 0,
            "pos_aux": int(weld_begin <= t < weld_end),
            "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0,
        })
    weld_name = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(weld_name, weld_rows)
    weld_case = hidden.case("ok", weld_name)
    weld_case["limits"]["weld_dwell_ms"] = weld_dwell
    weld_case["limits"]["aux_delay_ms"] = (weld_end - weld_begin) + 50.0
    cases.append(weld_case)
    expected[weld_case["case_id"]] = ("WELDED_CONTACTOR", weld_rows, weld_case["limits"])

    index_path = hidden.write_index(cases, "no-precharge-rise-hidden.json")
    out = tmp_path / "no-precharge-rise-hidden-out"
    result = invoke(index_path, out)
    assert result.returncode == 0, result.stderr

    report, _ = read_report(out)
    events, _ = read_events(out)
    assert_report_schema(report)
    by_id = {item["case_id"]: item for item in report["cases"]}

    for case_id, (verdict, source_rows, limits) in expected.items():
        item = by_id[case_id]
        assert item["input_state"] == "valid"
        assert item["verdict"] == verdict
        assert item["metrics"]["precharge_start_ms"] is None
        assert item["metrics"]["ready_at_ms"] is None
        assert item["metrics"]["ready_delay_ms"] is None
        assert item["metrics"]["ready_link_v"] is None
        assert item["metrics"]["peak_abs_pack_a"] is None
        assert item["metrics"]["max_link_slew_v_per_ms"] is None
        assert item["metrics"]["tau_ms"] is None
        assert_event_ledger(case_id, source_rows, limits, item, events)


def test_metric_window_excludes_prestart_disturbances_and_interpolates_end_current(hidden, tmp_path):
    """Peak/slew window begins at precharge rise and includes interpolated analog endpoints."""
    pack_v = float(hidden.stream.take(760, 880))
    pre_spike_a = float(hidden.stream.take(75, 105))
    end_spike_a = float(hidden.stream.take(28, 42))

    rows = [
        {
            "t_ms": 0.0, "pack_v": pack_v, "link_v": 0.0, "pack_a": 0.0,
            "pre_cmd": 0, "pre_aux": 0, "pos_cmd": 0, "pos_aux": 0,
            "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0,
        },
        {
            "t_ms": 20.0, "pack_v": pack_v, "link_v": 0.50 * pack_v, "pack_a": pre_spike_a,
            "pre_cmd": 0, "pre_aux": 0, "pos_cmd": 0, "pos_aux": 0,
            "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0,
        },
        {
            "t_ms": 40.0, "pack_v": pack_v, "link_v": 8.0, "pack_a": 0.0,
            "pre_cmd": 0, "pre_aux": 0, "pos_cmd": 0, "pos_aux": 0,
            "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0,
        },
        {
            "t_ms": 50.0, "pack_v": pack_v, "link_v": 8.0, "pack_a": 4.0,
            "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
            "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0,
        },
        {
            "t_ms": 100.0, "pack_v": pack_v, "link_v": 0.50 * pack_v, "pack_a": 6.0,
            "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
            "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0,
        },
        {
            "t_ms": 150.0, "pack_v": pack_v, "link_v": 0.95 * pack_v, "pack_a": end_spike_a,
            "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
            "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0,
        },
        {
            "t_ms": 300.0, "pack_v": pack_v, "link_v": 0.99 * pack_v, "pack_a": 0.0,
            "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
            "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0,
        },
    ]

    filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(filename, rows)
    case = hidden.case("ok", filename)
    # Keep the deliberate pre-start voltage excursion from becoming RESIDUAL_LINK.
    case["limits"]["residual_abs_v"] = 0.70 * pack_v
    case["limits"]["residual_ratio"] = 0.70
    case["limits"]["max_precharge_ms"] = 500.0

    expected_peak, expected_slew = expected_window_metrics(rows, case["limits"])
    assert expected_peak < pre_spike_a
    assert expected_peak > 6.0  # proves the interpolated ready-boundary current matters

    index_path = hidden.write_index([case], "metric-window-hidden.json")
    out = tmp_path / "metric-window-hidden-out"
    result = invoke(index_path, out)
    assert result.returncode == 0, result.stderr

    report, _ = read_report(out)
    events, _ = read_events(out)
    assert_report_schema(report)
    item = report["cases"][0]
    assert item["input_state"] == "valid"
    assert item["verdict"] == "OK"
    assert item["metrics"]["peak_abs_pack_a"] == pytest.approx(expected_peak, abs=0.5)
    assert item["metrics"]["max_link_slew_v_per_ms"] == pytest.approx(
        expected_slew, rel=0.03, abs=0.05
    )
    assert item["metrics"]["peak_abs_pack_a"] < pre_spike_a
    assert_event_ledger(case["case_id"], rows, case["limits"], item, events)


def test_weld_dwell_is_independent_per_main_channel_and_cannot_be_pooled(hidden, tmp_path):
    """Alternating positive/negative weld-like spans must not combine into one dwell."""
    cases = []

    for first_aux, second_aux in (("pos_aux", "neg_aux"), ("neg_aux", "pos_aux")):
        span = float(hidden.stream.take(48, 62))
        weld_dwell = span + float(hidden.stream.take(18, 28))
        start = 180.0
        rows = []
        times = [0.0, span, 2.0 * span, start, start + 50.0, start + 100.0, start + 150.0, 500.0]
        pack_v = float(hidden.stream.take(760, 860))

        for t in times:
            pre_on = t >= start
            first_state = int(0.0 <= t < span)
            second_state = int(span <= t < 2.0 * span)
            if t < start:
                link_v = 8.0
            elif t <= start + 100.0:
                fraction = (t - start) / 100.0
                link_v = 8.0 + fraction * (0.95 * pack_v - 8.0)
            else:
                link_v = 0.99 * pack_v

            row = {
                "t_ms": t, "pack_v": pack_v, "link_v": link_v, "pack_a": 0.0,
                "pre_cmd": int(pre_on), "pre_aux": int(pre_on),
                "pos_cmd": 0, "pos_aux": 0, "neg_cmd": 0, "neg_aux": 0,
                "iso_kohm": 1000.0, "crash": 0,
            }
            row[first_aux] = first_state
            row[second_aux] = second_state
            rows.append(row)

        filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
        hidden.write_capture(filename, rows)
        case = hidden.case("ok", filename)
        case["limits"]["weld_dwell_ms"] = weld_dwell
        case["limits"]["aux_delay_ms"] = weld_dwell + 40.0
        case["limits"]["max_precharge_ms"] = 500.0
        cases.append((case, rows))

    index_path = hidden.write_index([case for case, _ in cases], "weld-channel-handoff-hidden.json")
    out = tmp_path / "weld-channel-handoff-hidden-out"
    result = invoke(index_path, out)
    assert result.returncode == 0, result.stderr

    report, _ = read_report(out)
    events, _ = read_events(out)
    assert_report_schema(report)
    by_id = {item["case_id"]: item for item in report["cases"]}

    for case, rows in cases:
        item = by_id[case["case_id"]]
        assert item["input_state"] == "valid"
        assert item["verdict"] == "OK"
        assert "WELDED_CONTACTOR" not in [entry["code"] for entry in item["evidence"]]
        assert_event_ledger(case["case_id"], rows, case["limits"], item, events)


def test_exact_threshold_equalities_are_accepted(hidden, tmp_path):
    """Verify equality semantics for readiness, timeout, bounce, and auxiliary delay."""
    _rows, _case, item, _events = run_boundary_case(hidden, tmp_path, "equalities")
    assert item["verdict"] == "OK"
    assert "PRECHARGE_TIMEOUT" not in item["flags"]
    assert "CONTACT_BOUNCE" not in item["flags"]
    assert "AUX_TIMEOUT" not in item["flags"]
    assert item["metrics"]["precharge_start_ms"] == 50.0
    assert item["metrics"]["aux_delay_ms"]["pre"] == 80.0
    assert item["metrics"]["aux_edges"]["pre"] == 3


def test_duplicate_last_row_and_metric_tolerances(hidden, tmp_path):
    """Verify last-duplicate semantics and disclosed interpolation/RC tolerances."""
    rows, case, item, events = run_boundary_case(hidden, tmp_path, "metrics")
    ready = expected_ready(rows, case["limits"]["ready_ratio"])
    assert ready == pytest.approx(350.0, abs=5.0)
    assert item["metrics"]["ready_at_ms"] == pytest.approx(ready, abs=5.0)
    assert item["metrics"]["ready_delay_ms"] == pytest.approx(300.0, abs=5.0)
    assert item["metrics"]["ready_link_v"] == pytest.approx(
        case["limits"]["ready_ratio"] * hidden.electrical["boundary"].pack_v, abs=1.0
    )
    assert item["metrics"]["tau_ms"] == pytest.approx(
        (0.6321205588 / case["limits"]["ready_ratio"]) * 300.0,
        rel=0.05,
    )
    assert item["metrics"]["final_link_ratio"] == pytest.approx(1.0, abs=0.002)
    assert_event_ledger(case["case_id"], rows, case["limits"], item, events)


def test_deterministic_bytes_and_input_immutability(hidden, tmp_path):
    """Verify repeated runs are byte-identical and never change index/capture inputs."""
    good_path = hidden.write_capture("good.csv", hidden.rows("ok"))
    bad_path = hidden.write_capture("bad.csv", hidden.rows("bad_input"))
    good_case = hidden.case("ok", "good.csv")
    bad_case = hidden.case("bad_input", "bad.csv")
    index = hidden.write_index([good_case, bad_case], "integrity.json")
    before = {path: digest(path) for path in (index, good_path, bad_path)}

    out_a, out_b = tmp_path / "run-a", tmp_path / "run-b"
    first = invoke(index, out_a)
    second = invoke(index, out_b)
    assert first.returncode == second.returncode == 0
    assert (out_a / "report.json").read_bytes() == (out_b / "report.json").read_bytes()
    assert (out_a / "events.csv").read_bytes() == (out_b / "events.csv").read_bytes()
    assert before == {path: digest(path) for path in before}


def test_invalid_case_is_isolated_and_canonical(hidden, tmp_path):
    """Verify one malformed capture becomes BAD_INPUT without aborting valid peers."""
    good_rows = hidden.rows("ok")
    bad_rows = hidden.rows("bad_input")
    hidden.write_capture("good-local.csv", good_rows)
    hidden.write_capture("bad-local.csv", bad_rows)
    good_case = hidden.case("ok", "good-local.csv")
    bad_case = hidden.case("bad_input", "bad-local.csv")
    index = hidden.write_index([good_case, bad_case], "local-failure.json")
    out = tmp_path / "local-failure-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)

    states = {case["case_id"]: case["input_state"] for case in report["cases"]}
    assert states[good_case["case_id"]] == "valid"
    assert states[bad_case["case_id"]] == "invalid"
    bad = next(case for case in report["cases"] if case["case_id"] == bad_case["case_id"])
    assert bad["verdict"] == "BAD_INPUT"
    assert bad["flags"] == []
    assert all(
        value is None
        for key, value in bad["metrics"].items()
        if key not in ("aux_delay_ms", "aux_edges")
    )
    assert bad["metrics"]["aux_delay_ms"] == {"neg": None, "pos": None, "pre": None}
    assert bad["metrics"]["aux_edges"] == {"neg": 0, "pos": 0, "pre": 0}
    assert_event_ledger(bad_case["case_id"], bad_rows, bad_case["limits"], bad, events)


def test_fatal_index_and_output_errors_return_nonzero(hidden, tmp_path):
    """Verify top-level index and unwritable-output failures are fatal and artifact-free."""
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"format":"wrong","cases":[]}', encoding="utf-8")
    failed = invoke(malformed, tmp_path / "malformed-out")
    assert failed.returncode != 0
    assert not (tmp_path / "malformed-out" / "report.json").exists()

    hidden.write_capture("fatal-base.csv", hidden.rows("dense", dense=True))
    case = hidden.case("dense", "fatal-base.csv")
    index = hidden.write_index([case], "fatal-index.json")
    occupied = tmp_path / "occupied"
    occupied.write_text("not a directory", encoding="utf-8")
    output_error = invoke(index, occupied)
    assert output_error.returncode != 0


def test_dense_capture_runtime_and_immutability(hidden, tmp_path):
    """Verify dense irregular telemetry completes within budget without input mutation."""
    rows = hidden.rows("dense", dense=True)
    capture = hidden.write_capture("dense.csv", rows)
    case = hidden.case("dense", "dense.csv")
    index = hidden.write_index([case], "dense-index.json")
    before = {index: digest(index), capture: digest(capture)}
    out = tmp_path / "dense-out"
    started = time.monotonic()
    result = invoke(index, out, timeout=18.0)
    elapsed = time.monotonic() - started
    assert result.returncode == 0, result.stderr
    assert elapsed < 18.0
    assert before == {path: digest(path) for path in before}
    report, _ = read_report(out)
    assert report["cases"][0]["verdict"] == "OK"


def test_interleaved_sessions_keep_failure_streaks_strictly_isolated(hidden, tmp_path):
    """Interleaved sessions and standalone cases must never share precharge-failure state."""
    session_a = f"sa-{hidden.stream.take(0, 0xFFFFFF):06x}"
    session_b = f"sb-{hidden.stream.take(0, 0xFFFFFF):06x}"

    def make_case(label, *, session_id=None, attempt=None):
        filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
        rows = hidden.rows(label)
        hidden.write_capture(filename, rows)
        updates = {}
        if session_id is not None:
            updates.update(session_id=session_id, attempt=attempt)
        return hidden.case(label, filename, **updates)

    # Session B has only two consecutive source failures and therefore must
    # never receive REPEATED_PRECHARGE_FAILURE.
    b1 = make_case("open", session_id=session_b, attempt=1)
    b2 = make_case("timeout", session_id=session_b, attempt=2)

    # Session A has exactly three consecutive source failures.  Only its third
    # ordered attempt is eligible for the session-level code.
    a1 = make_case("open", session_id=session_a, attempt=1)
    a2 = make_case("timeout", session_id=session_a, attempt=2)
    a3 = make_case("open", session_id=session_a, attempt=3)

    # A standalone source failure is intentionally placed between participating
    # cases.  It is omitted from session processing and cannot increment/reset
    # either session's streak.
    standalone = make_case("open")

    # Deliberately interleave and reverse attempt order physically.  Correct
    # behavior requires grouping by exact session_id before applying each
    # session's (attempt, case_id, original-position) order.
    index_path = hidden.write_index(
        [b2, a3, standalone, a1, b1, a2],
        "interleaved-session-isolation.json",
    )
    out = tmp_path / "interleaved-session-isolation-out"
    result = invoke(index_path, out)
    assert result.returncode == 0, result.stderr

    report, _ = read_report(out)
    events, _ = read_events(out)
    assert_report_schema(report)
    by_id = {item["case_id"]: item for item in report["cases"]}

    assert by_id[a1["case_id"]]["verdict"] == "OPEN_PRECHARGE"
    assert by_id[a2["case_id"]]["verdict"] == "PRECHARGE_TIMEOUT"
    assert by_id[a3["case_id"]]["verdict"] == "REPEATED_PRECHARGE_FAILURE"
    assert by_id[a3["case_id"]]["flags"] == ["OPEN_PRECHARGE"]
    assert [entry["code"] for entry in by_id[a3["case_id"]]["evidence"]] == [
        "REPEATED_PRECHARGE_FAILURE", "OPEN_PRECHARGE"
    ]

    for case, expected_verdict in (
        (b1, "OPEN_PRECHARGE"),
        (b2, "PRECHARGE_TIMEOUT"),
        (standalone, "OPEN_PRECHARGE"),
    ):
        item = by_id[case["case_id"]]
        assert item["verdict"] == expected_verdict
        assert "REPEATED_PRECHARGE_FAILURE" not in [
            entry["code"] for entry in item["evidence"]
        ]

    # The session promotion changes A3's primary verdict, so its one verdict
    # ledger row must be back-patched; no flag gets a separate verdict row.
    verdict_rows = [
        row for row in events
        if row["case_id"] == a3["case_id"] and row["event"] == "verdict"
    ]
    assert len(verdict_rows) == 1
    assert verdict_rows[0]["value"] == "REPEATED_PRECHARGE_FAILURE"
    assert float(verdict_rows[0]["time_ms"]) == pytest.approx(
        by_id[a3["case_id"]]["evidence"][0]["time_ms"], abs=1e-6
    )


def test_readiness_and_tau_crossings_are_never_extrapolated_beyond_capture(hidden, tmp_path):
    """Missing in-capture crossings stay null even when the final slope tempts extrapolation."""
    pack_v = float(hidden.stream.take(780, 860))
    start = 50.0
    aux_on = 70.0
    deadline = 450.0
    times = [0.0, start, aux_on, 300.0, deadline, 550.0, 600.0]

    # Both captures remain below readiness through the final retained row.
    # The first also remains below the 63.212% tau target.  The second crosses
    # the tau target inside the capture but still never reaches readiness.
    profiles = (
        ("no-tau-no-ready", [8.0, 8.0, 40.0, 180.0, 330.0, 430.0, 480.0], False),
        (
            "tau-but-no-ready",
            [8.0, 8.0, 60.0, 0.70 * pack_v, 0.77 * pack_v, 0.82 * pack_v, 0.84 * pack_v],
            True,
        ),
    )

    cases = []
    source_rows = {}
    expected_tau_by_id = {}
    for _name, link_values, tau_should_exist in profiles:
        rows = []
        for t_ms, link_v in zip(times, link_values):
            rows.append({
                "t_ms": t_ms,
                "pack_v": pack_v,
                "link_v": float(link_v),
                "pack_a": 0.0,
                "pre_cmd": int(t_ms >= start),
                "pre_aux": int(t_ms >= aux_on),
                "pos_cmd": 0,
                "pos_aux": 0,
                "neg_cmd": 0,
                "neg_aux": 0,
                "iso_kohm": 1000.0,
                "crash": 0,
            })

        filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
        hidden.write_capture(filename, rows)
        case = hidden.case("ok", filename)
        case["limits"]["max_precharge_ms"] = deadline - start
        cases.append(case)
        source_rows[case["case_id"]] = rows

        expected_tau_value = expected_tau(rows)
        assert (expected_tau_value is not None) is tau_should_exist
        expected_tau_by_id[case["case_id"]] = expected_tau_value
        assert expected_ready(rows, case["limits"]["ready_ratio"]) is None

        # Prove OPEN_PRECHARGE is not the reason for the timeout: by the
        # open-check instant the observed ratio has increased well beyond the
        # configured minimum rise, while still remaining below readiness.
        open_check_at = start + case["limits"]["open_check_ms"]
        open_row = next(row for row in rows if float(row["t_ms"]) == open_check_at)
        start_row = next(row for row in rows if float(row["t_ms"]) == start)
        ratio_rise = (
            float(open_row["link_v"]) / float(open_row["pack_v"])
            - float(start_row["link_v"]) / float(start_row["pack_v"])
        )
        assert ratio_rise > case["limits"]["open_min_rise_ratio"]
        assert float(rows[-1]["link_v"]) < case["limits"]["ready_ratio"] * pack_v

    index_path = hidden.write_index(cases, "no-extrapolation-crossings.json")
    out = tmp_path / "no-extrapolation-crossings-out"
    result = invoke(index_path, out)
    assert result.returncode == 0, result.stderr

    report, _ = read_report(out)
    events, _ = read_events(out)
    assert_report_schema(report)
    by_id = {item["case_id"]: item for item in report["cases"]}

    for case in cases:
        case_id = case["case_id"]
        item = by_id[case_id]
        rows = source_rows[case_id]
        assert item["input_state"] == "valid"
        assert item["verdict"] == "PRECHARGE_TIMEOUT"
        assert item["flags"] == []
        assert item["metrics"]["ready_at_ms"] is None
        assert item["metrics"]["ready_delay_ms"] is None
        assert item["metrics"]["ready_link_v"] is None

        expected_tau_value = expected_tau_by_id[case_id]
        if expected_tau_value is None:
            assert item["metrics"]["tau_ms"] is None
        else:
            assert item["metrics"]["tau_ms"] == pytest.approx(
                expected_tau_value, rel=0.05
            )

        assert item["evidence"][0]["code"] == "PRECHARGE_TIMEOUT"
        assert item["evidence"][0]["time_ms"] == pytest.approx(deadline, abs=5.0)
        assert not any(
            row["case_id"] == case_id and row["event"] == "ready"
            for row in events
        )
        assert_event_ledger(case_id, rows, case["limits"], item, events)


def test_bypass_or_short_tau_and_ready_delay_paths_are_independently_observable(hidden, tmp_path):
    """Both normative BYPASS_OR_SHORT alternatives must work independently."""
    cases = []
    expectations = {}

    # A: tau crosses implausibly early, but readiness is deliberately delayed far
    # beyond the short-ready threshold.  Removing the tau alternative must fail.
    pack = 800.0
    rows_tau = [
        {"t_ms": 0.0, "pack_v": pack, "link_v": 8.0, "pack_a": 0.0,
         "pre_cmd": 0, "pre_aux": 0, "pos_cmd": 0, "pos_aux": 0,
         "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0},
        {"t_ms": 50.0, "pack_v": pack, "link_v": 8.0, "pack_a": 4.0,
         "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
         "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0},
        {"t_ms": 80.0, "pack_v": pack, "link_v": 560.0, "pack_a": 3.0,
         "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
         "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0},
        {"t_ms": 300.0, "pack_v": pack, "link_v": 650.0, "pack_a": 2.0,
         "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
         "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0},
        {"t_ms": 700.0, "pack_v": pack, "link_v": 730.0, "pack_a": 0.5,
         "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
         "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0},
        {"t_ms": 1200.0, "pack_v": pack, "link_v": 790.0, "pack_a": 0.0,
         "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
         "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0},
    ]
    name_tau = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(name_tau, rows_tau)
    case_tau = hidden.case("ok", name_tau)
    case_tau["precharge_ohm"] = 100.0
    case_tau["capacitance_uf"] = 3000.0
    case_tau["limits"]["max_precharge_ms"] = 1000.0
    case_tau["limits"]["open_min_rise_ratio"] = 0.01
    tau_measured = round(expected_tau(rows_tau), 6)
    tau_expected_rc = case_tau["precharge_ohm"] * case_tau["capacitance_uf"] / 1000.0
    case_tau["limits"]["short_tau_factor"] = tau_measured / tau_expected_rc
    cases.append(case_tau)
    expectations[case_tau["case_id"]] = "tau_only"

    # B: readiness occurs exactly at the short-ready equality while the static
    # tau target (derived from pack/link at start) is never reached in-capture.
    # This pins the documented '<=' boundary for the ready-delay alternative.
    ready_ratio_eq = 1.0 - math.exp(-1.0)
    rows_ready = [
        {"t_ms": 0.0, "pack_v": 800.0, "link_v": 8.0, "pack_a": 0.0,
         "pre_cmd": 0, "pre_aux": 0, "pos_cmd": 0, "pos_aux": 0,
         "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0},
        {"t_ms": 50.0, "pack_v": 800.0, "link_v": 8.0, "pack_a": 3.0,
         "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
         "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0},
        {"t_ms": 110.0, "pack_v": 400.0, "link_v": ready_ratio_eq * 400.0, "pack_a": 2.0,
         "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
         "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0},
        {"t_ms": 300.0, "pack_v": 400.0, "link_v": 300.0, "pack_a": 0.5,
         "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
         "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0},
        {"t_ms": 900.0, "pack_v": 400.0, "link_v": 350.0, "pack_a": 0.0,
         "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 0, "pos_aux": 0,
         "neg_cmd": 0, "neg_aux": 0, "iso_kohm": 1000.0, "crash": 0},
    ]
    name_ready = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(name_ready, rows_ready)
    case_ready = hidden.case("ok", name_ready)
    case_ready["precharge_ohm"] = 100.0
    case_ready["capacitance_uf"] = 3000.0
    case_ready["limits"]["ready_ratio"] = ready_ratio_eq
    case_ready["limits"]["short_tau_factor"] = 0.20
    case_ready["limits"]["max_precharge_ms"] = 1000.0
    case_ready["limits"]["open_min_rise_ratio"] = 0.01
    cases.append(case_ready)
    expectations[case_ready["case_id"]] = "ready_only"

    index_path = hidden.write_index(cases, "bypass-independent-alternatives.json")
    out = tmp_path / "bypass-independent-alternatives-out"
    result = invoke(index_path, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    by_id = {item["case_id"]: item for item in report["cases"]}

    tau_item = by_id[case_tau["case_id"]]
    assert tau_item["verdict"] == "BYPASS_OR_SHORT"
    assert tau_item["metrics"]["tau_ms"] is not None
    expected_tau_rc = case_tau["precharge_ohm"] * case_tau["capacitance_uf"] / 1000.0
    assert tau_item["metrics"]["tau_ms"] == pytest.approx(case_tau["limits"]["short_tau_factor"] * expected_tau_rc, abs=1e-6)
    expected_ready_ms = -math.log(1.0 - case_tau["limits"]["ready_ratio"]) * expected_tau_rc
    assert tau_item["metrics"]["ready_delay_ms"] is not None
    assert tau_item["metrics"]["ready_delay_ms"] > case_tau["limits"]["short_tau_factor"] * expected_ready_ms
    assert_event_ledger(case_tau["case_id"], rows_tau, case_tau["limits"], tau_item, events)

    ready_item = by_id[case_ready["case_id"]]
    assert ready_item["verdict"] == "BYPASS_OR_SHORT"
    assert ready_item["metrics"]["tau_ms"] is None
    assert ready_item["metrics"]["ready_delay_ms"] is not None
    expected_tau_rc = case_ready["precharge_ohm"] * case_ready["capacitance_uf"] / 1000.0
    expected_ready_ms = -math.log(1.0 - case_ready["limits"]["ready_ratio"]) * expected_tau_rc
    assert ready_item["metrics"]["ready_delay_ms"] == pytest.approx(case_ready["limits"]["short_tau_factor"] * expected_ready_ms, abs=1e-6)
    # Generic ledger helper assumes a constant pack voltage when checking the
    # ready-row value.  This waveform intentionally varies pack_v to isolate
    # the ready-delay alternative, so validate the relevant event fields directly.
    ready_rows = [row for row in events if row["case_id"] == case_ready["case_id"] and row["event"] == "ready"]
    assert len(ready_rows) == 1
    assert float(ready_rows[0]["time_ms"]) == pytest.approx(ready_item["metrics"]["ready_at_ms"], abs=5.0)
    assert float(ready_rows[0]["value"]) == pytest.approx(ready_item["metrics"]["ready_link_v"], abs=1.0)


def test_open_precharge_requires_pre_aux_closed_at_probe(hidden, tmp_path):
    """A flat link with pre_aux still open is timeout, not OPEN_PRECHARGE."""
    pack = float(hidden.stream.take(730, 890))
    rows = []
    for t in (0.0, 50.0, 150.0, 300.0, 700.0, 1200.0):
        rows.append({
            "t_ms": t, "pack_v": pack, "link_v": 8.0, "pack_a": 0.0,
            "pre_cmd": int(t >= 50.0), "pre_aux": 0,
            "pos_cmd": 0, "pos_aux": 0, "neg_cmd": 0, "neg_aux": 0,
            "iso_kohm": 1000.0, "crash": 0,
        })
    filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(filename, rows)
    case = hidden.case("ok", filename)
    case["limits"]["open_check_ms"] = 250.0
    case["limits"]["max_precharge_ms"] = 650.0
    case["limits"]["aux_delay_ms"] = 1000.0  # isolate OPEN vs TIMEOUT
    index_path = hidden.write_index([case], "open-requires-aux.json")
    out = tmp_path / "open-requires-aux-out"
    result = invoke(index_path, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    item = report["cases"][0]
    assert item["input_state"] == "valid"
    assert item["verdict"] == "PRECHARGE_TIMEOUT"
    assert "OPEN_PRECHARGE" not in [entry["code"] for entry in item["evidence"]]
    assert_event_ledger(case["case_id"], rows, case["limits"], item, events)



def _simple_row(t, *, pack=800.0, link=8.0, iso=1000.0, crash=0, **digital):
    row = {
        "t_ms": float(t), "pack_v": float(pack), "link_v": float(link), "pack_a": 0.0,
        "pre_cmd": 0, "pre_aux": 0, "pos_cmd": 0, "pos_aux": 0,
        "neg_cmd": 0, "neg_aux": 0, "iso_kohm": float(iso), "crash": int(crash),
    }
    row.update({key: int(value) for key, value in digital.items()})
    return row


def test_low_isolation_all_hv_activity_channels_and_strict_boundary(hidden, tmp_path):
    """LOW_ISOLATION must use strict '<' and accept activity from every HV cmd/aux channel."""
    cases = []
    expectations = {}
    channels = ("pre_cmd", "pre_aux", "pos_cmd", "pos_aux", "neg_cmd", "neg_aux")
    for channel in channels:
        rows = [
            _simple_row(0.0),
            _simple_row(20.0, iso=499.0, **{channel: 1}),
            _simple_row(40.0),
        ]
        filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
        hidden.write_capture(filename, rows)
        case = hidden.case("ok", filename)
        case["limits"]["isolation_min_kohm"] = 500.0
        case["limits"]["weld_dwell_ms"] = 1000.0
        case["limits"]["aux_delay_ms"] = 1000.0
        case["limits"]["max_precharge_ms"] = 1000.0
        cases.append(case)
        expectations[case["case_id"]] = (True, rows, case["limits"])

    # Equality is explicitly non-faulting because LOW_ISOLATION uses '<'.
    rows_eq = [
        _simple_row(0.0),
        _simple_row(20.0, iso=500.0, pos_cmd=1),
        _simple_row(40.0),
    ]
    filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(filename, rows_eq)
    case_eq = hidden.case("ok", filename)
    case_eq["limits"]["isolation_min_kohm"] = 500.0
    case_eq["limits"]["aux_delay_ms"] = 1000.0
    case_eq["limits"]["max_precharge_ms"] = 1000.0
    cases.append(case_eq)
    expectations[case_eq["case_id"]] = (False, rows_eq, case_eq["limits"])

    index = hidden.write_index(cases, "low-isolation-activity-family.json")
    out = tmp_path / "low-isolation-activity-family-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    by_id = {item["case_id"]: item for item in report["cases"]}
    for case_id, (should_fault, rows, limits) in expectations.items():
        item = by_id[case_id]
        codes = [entry["code"] for entry in item["evidence"]]
        if should_fault:
            assert "LOW_ISOLATION" in codes
        else:
            assert "LOW_ISOLATION" not in codes
        assert_event_ledger(case_id, rows, limits, item, events)


def test_unsafe_close_requires_both_mains_and_strict_postready_boundaries(hidden, tmp_path):
    """UNSAFE_CLOSE requires both mains and strict ratio/isolation comparisons after readiness."""
    pack = 800.0
    cases = []
    expected_no_unsafe = {}

    # One-main-only controls: even crash=1 cannot trigger UNSAFE_CLOSE.
    for side in ("pos", "neg"):
        cmd, aux = f"{side}_cmd", f"{side}_aux"
        rows = [
            _simple_row(0.0, pack=pack, link=pack, crash=0),
            _simple_row(20.0, pack=pack, link=pack, crash=1, **{cmd: 1, aux: 1}),
            _simple_row(40.0, pack=pack, link=pack, crash=0, **{cmd: 1, aux: 1}),
        ]
        filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
        hidden.write_capture(filename, rows)
        case = hidden.case("ok", filename)
        case["limits"]["aux_delay_ms"] = 1000.0
        case["limits"]["weld_dwell_ms"] = 1000.0
        cases.append(case)
        expected_no_unsafe[case["case_id"]] = (rows, case["limits"])

    # Reach readiness first; then close both mains exactly at BOTH strict boundaries.
    rows_boundary = [
        _simple_row(0.0, pack=pack, link=8.0),
        _simple_row(50.0, pack=pack, link=8.0, pre_cmd=1, pre_aux=1),
        _simple_row(150.0, pack=pack, link=0.95 * pack, pre_cmd=1, pre_aux=1),
        _simple_row(
            250.0, pack=pack, link=0.85 * pack, iso=500.0,
            pre_cmd=1, pre_aux=1, pos_cmd=1, pos_aux=1, neg_cmd=1, neg_aux=1,
        ),
        _simple_row(
            300.0, pack=pack, link=pack, iso=500.0,
            pre_cmd=1, pre_aux=1, pos_cmd=1, pos_aux=1, neg_cmd=1, neg_aux=1,
        ),
    ]
    filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(filename, rows_boundary)
    case_boundary = hidden.case("ok", filename)
    case_boundary["limits"]["safe_close_ratio"] = 0.85
    case_boundary["limits"]["isolation_min_kohm"] = 500.0
    case_boundary["limits"]["sensor_bias_dwell_ms"] = 1000.0
    case_boundary["limits"]["aux_delay_ms"] = 1000.0
    cases.append(case_boundary)
    expected_no_unsafe[case_boundary["case_id"]] = (rows_boundary, case_boundary["limits"])

    # Both mains close exactly on the readiness crossing. Readiness equality
    # has already occurred at that retained row, so the pre-readiness branch
    # must use time < ready, not time <= ready.
    rows_ready_equal = [
        _simple_row(0.0, pack=pack, link=8.0),
        _simple_row(50.0, pack=pack, link=8.0, pre_cmd=1, pre_aux=1),
        _simple_row(150.0, pack=pack, link=0.90 * pack, pre_cmd=1, pre_aux=1,
                    pos_cmd=1, pos_aux=1, neg_cmd=1, neg_aux=1),
        _simple_row(250.0, pack=pack, link=pack, pre_cmd=1, pre_aux=1,
                    pos_cmd=1, pos_aux=1, neg_cmd=1, neg_aux=1),
    ]
    filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(filename, rows_ready_equal)
    case_ready_equal = hidden.case("ok", filename)
    case_ready_equal["limits"]["sensor_bias_dwell_ms"] = 1000.0
    case_ready_equal["limits"]["aux_delay_ms"] = 1000.0
    cases.append(case_ready_equal)
    expected_no_unsafe[case_ready_equal["case_id"]] = (rows_ready_equal, case_ready_equal["limits"])

    index = hidden.write_index(cases, "unsafe-negative-boundaries.json")
    out = tmp_path / "unsafe-negative-boundaries-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    by_id = {item["case_id"]: item for item in report["cases"]}
    for case_id, (rows, limits) in expected_no_unsafe.items():
        item = by_id[case_id]
        assert "UNSAFE_CLOSE" not in [entry["code"] for entry in item["evidence"]]
        assert_event_ledger(case_id, rows, limits, item, events)


def test_open_precharge_equality_initial_ratio_and_probe_range_operands(hidden, tmp_path):
    """Pin OPEN_PRECHARGE <= equality plus initial-ratio and in-capture probe guards."""
    pack = 800.0
    cases = []
    expected = {}

    # Equality on rise operand must trigger OPEN_PRECHARGE.
    rows_eq = [
        _simple_row(0.0, pack=pack, link=8.0),
        _simple_row(50.0, pack=pack, link=8.0, pre_cmd=1, pre_aux=1),
        _simple_row(300.0, pack=pack, link=32.0, pre_cmd=1, pre_aux=1),
        _simple_row(800.0, pack=pack, link=32.0, pre_cmd=1, pre_aux=1),
    ]
    filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(filename, rows_eq)
    case_eq = hidden.case("ok", filename)
    case_eq["limits"]["open_check_ms"] = 250.0
    case_eq["limits"]["open_min_rise_ratio"] = 0.03
    case_eq["limits"]["max_precharge_ms"] = 600.0
    case_eq["limits"]["aux_delay_ms"] = 1000.0
    cases.append(case_eq)
    expected[case_eq["case_id"]] = ("OPEN", rows_eq, case_eq["limits"])

    # Initial ratio is already above readiness at the precharge command edge.
    rows_initial = [
        _simple_row(0.0, pack=pack, link=8.0),
        _simple_row(50.0, pack=pack, link=0.90 * pack, pre_cmd=1, pre_aux=1),
        _simple_row(300.0, pack=pack, link=0.90 * pack, pre_cmd=1, pre_aux=1),
        _simple_row(700.0, pack=pack, link=0.90 * pack, pre_cmd=1, pre_aux=1),
    ]
    filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(filename, rows_initial)
    case_initial = hidden.case("ok", filename)
    case_initial["limits"]["open_check_ms"] = 250.0
    case_initial["limits"]["open_min_rise_ratio"] = 0.03
    case_initial["limits"]["aux_delay_ms"] = 1000.0
    cases.append(case_initial)
    expected[case_initial["case_id"]] = ("NO_OPEN_READY_AT_START", rows_initial, case_initial["limits"])

    # Probe lies beyond the final retained row; OPEN_PRECHARGE must not extrapolate.
    rows_range = [
        _simple_row(0.0, pack=pack, link=8.0),
        _simple_row(50.0, pack=pack, link=8.0, pre_cmd=1, pre_aux=1),
        _simple_row(250.0, pack=pack, link=8.0, pre_cmd=1, pre_aux=1),
        _simple_row(400.0, pack=pack, link=8.0, pre_cmd=1, pre_aux=1),
    ]
    filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(filename, rows_range)
    case_range = hidden.case("ok", filename)
    case_range["limits"]["open_check_ms"] = 500.0
    case_range["limits"]["max_precharge_ms"] = 300.0
    case_range["limits"]["aux_delay_ms"] = 1000.0
    cases.append(case_range)
    expected[case_range["case_id"]] = ("NO_OPEN", rows_range, case_range["limits"])

    index = hidden.write_index(cases, "open-operand-closure.json")
    out = tmp_path / "open-operand-closure-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    by_id = {item["case_id"]: item for item in report["cases"]}
    for case_id, (mode, rows, limits) in expected.items():
        item = by_id[case_id]
        codes = [entry["code"] for entry in item["evidence"]]
        if mode == "OPEN":
            assert item["verdict"] == "OPEN_PRECHARGE"
            assert item["evidence"][0]["time_ms"] == pytest.approx(300.0, abs=1e-6)
        else:
            assert "OPEN_PRECHARGE" not in codes
        if mode == "NO_OPEN_READY_AT_START":
            ready_rows = [
                row for row in events
                if row["case_id"] == case_id and row["event"] == "ready"
            ]
            assert len(ready_rows) == 1
            assert float(ready_rows[0]["time_ms"]) == pytest.approx(50.0, abs=1e-6)
            assert float(ready_rows[0]["value"]) == pytest.approx(0.90 * pack, abs=1.0)
        else:
            assert_event_ledger(case_id, rows, limits, item, events)


def test_sensor_bias_threshold_maximum_strictness_and_activation_guards(hidden, tmp_path):
    """SENSOR_BIAS must honor max(abs,ratio), strict analog threshold, both mains, and readiness."""
    pack = 800.0
    cases = []
    expected_sensor = {}

    def add_case(rows, *, abs_v, ratio, dwell=80.0, expect=False):
        filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
        hidden.write_capture(filename, rows)
        case = hidden.case("ok", filename)
        case["limits"]["sensor_bias_abs_v"] = abs_v
        case["limits"]["sensor_bias_ratio"] = ratio
        case["limits"]["sensor_bias_dwell_ms"] = dwell
        case["limits"]["aux_delay_ms"] = 1000.0
        case["limits"]["weld_dwell_ms"] = 1000.0
        cases.append(case)
        expected_sensor[case["case_id"]] = (expect, rows, case["limits"])

    # Common ready-then-both-mains timeline, with sustained post-ready delta.
    def biased_rows(delta, *, both=True):
        d = {
            "pre_cmd": 1, "pre_aux": 1, "pos_cmd": 1, "pos_aux": 1,
            "neg_cmd": 1, "neg_aux": 1 if both else 0,
        }
        return [
            _simple_row(0.0, pack=pack, link=8.0),
            _simple_row(50.0, pack=pack, link=8.0, pre_cmd=1, pre_aux=1),
            _simple_row(150.0, pack=pack, link=0.95 * pack, pre_cmd=1, pre_aux=1),
            _simple_row(220.0, pack=pack, link=pack - delta, **d),
            _simple_row(320.0, pack=pack, link=pack - delta, **d),
            _simple_row(360.0, pack=pack, link=pack, **d),
        ]

    # abs threshold dominates; delta is above ratio-only but below abs => no fault.
    add_case(biased_rows(30.0), abs_v=40.0, ratio=0.02, expect=False)
    # ratio threshold dominates; delta is above abs-only but below ratio => no fault.
    add_case(biased_rows(40.0), abs_v=10.0, ratio=0.08, expect=False)
    # Exact equality to max threshold remains non-faulting even for > dwell.
    add_case(biased_rows(40.0), abs_v=40.0, ratio=0.02, expect=False)
    # Above the max threshold is a positive control.
    add_case(biased_rows(55.0), abs_v=40.0, ratio=0.02, expect=True)
    # Only one main auxiliary closed: never SENSOR_BIAS.
    add_case(biased_rows(55.0, both=False), abs_v=40.0, ratio=0.02, expect=False)

    # Both mains are closed with large disagreement only BEFORE readiness; it
    # correctly causes UNSAFE_CLOSE, but SENSOR_BIAS must not be added as a flag.
    rows_preready = [
        _simple_row(0.0, pack=pack, link=8.0),
        _simple_row(50.0, pack=pack, link=8.0, pre_cmd=1, pre_aux=1),
        _simple_row(70.0, pack=pack, link=100.0, pre_cmd=1, pre_aux=1,
                    pos_cmd=1, pos_aux=1, neg_cmd=1, neg_aux=1),
        _simple_row(170.0, pack=pack, link=300.0, pre_cmd=1, pre_aux=1,
                    pos_cmd=1, pos_aux=1, neg_cmd=1, neg_aux=1),
        _simple_row(250.0, pack=pack, link=0.95 * pack, pre_cmd=1, pre_aux=1,
                    pos_cmd=1, pos_aux=1, neg_cmd=1, neg_aux=1),
        _simple_row(350.0, pack=pack, link=pack, pre_cmd=1, pre_aux=1,
                    pos_cmd=1, pos_aux=1, neg_cmd=1, neg_aux=1),
    ]
    add_case(rows_preready, abs_v=40.0, ratio=0.02, dwell=80.0, expect=False)

    index = hidden.write_index(cases, "sensor-operand-closure.json")
    out = tmp_path / "sensor-operand-closure-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    by_id = {item["case_id"]: item for item in report["cases"]}
    for case_id, (should_fault, rows, limits) in expected_sensor.items():
        item = by_id[case_id]
        codes = [entry["code"] for entry in item["evidence"]]
        if should_fault:
            assert "SENSOR_BIAS" in codes
        else:
            assert "SENSOR_BIAS" not in codes
        assert_event_ledger(case_id, rows, limits, item, events)


def test_contact_bounce_never_pools_different_aux_channels(hidden, tmp_path):
    """Close-in-time transitions on different auxiliaries are not CONTACT_BOUNCE."""
    rows = [
        _simple_row(0.0),
        _simple_row(20.0, pos_cmd=1, pos_aux=1),
        _simple_row(25.0, pos_cmd=1, pos_aux=1, neg_cmd=1, neg_aux=1),
        _simple_row(80.0, pos_cmd=1, pos_aux=1, neg_cmd=1, neg_aux=1),
    ]
    filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(filename, rows)
    case = hidden.case("ok", filename)
    case["limits"]["bounce_interval_ms"] = 10.0
    case["limits"]["sensor_bias_dwell_ms"] = 1000.0
    index = hidden.write_index([case], "bounce-cross-channel.json")
    out = tmp_path / "bounce-cross-channel-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    item = report["cases"][0]
    assert "CONTACT_BOUNCE" not in [entry["code"] for entry in item["evidence"]]
    assert_event_ledger(case["case_id"], rows, case["limits"], item, events)


def test_aux_timeout_applies_to_pos_and_neg_channels_in_both_directions(hidden, tmp_path):
    """AUX_TIMEOUT symmetry must include pos/neg, not only the precharge pair."""
    cases = []
    expected = {}
    for side in ("pos", "neg"):
        cmd, aux = f"{side}_cmd", f"{side}_aux"
        for direction in ("forward", "reverse"):
            if direction == "forward":
                rows = [
                    _simple_row(0.0),
                    _simple_row(20.0, **{cmd: 1, aux: 0}),
                    _simple_row(100.0, **{cmd: 1, aux: 0}),
                    _simple_row(120.0, **{cmd: 1, aux: 1}),
                ]
            else:
                rows = [
                    _simple_row(0.0),
                    _simple_row(20.0, **{cmd: 1, aux: 1}),
                    _simple_row(40.0, **{cmd: 0, aux: 1}),
                    _simple_row(120.0, **{cmd: 0, aux: 1}),
                    _simple_row(140.0, **{cmd: 0, aux: 0}),
                ]
            filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
            hidden.write_capture(filename, rows)
            case = hidden.case("ok", filename)
            case["limits"]["aux_delay_ms"] = 60.0
            case["limits"]["weld_dwell_ms"] = 200.0
            case["limits"]["sensor_bias_dwell_ms"] = 1000.0
            cases.append(case)
            expected[case["case_id"]] = (rows, case["limits"])

    index = hidden.write_index(cases, "aux-main-channel-symmetry.json")
    out = tmp_path / "aux-main-channel-symmetry-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    by_id = {item["case_id"]: item for item in report["cases"]}
    for case_id, (rows, limits) in expected.items():
        item = by_id[case_id]
        assert item["verdict"] == "AUX_TIMEOUT"
        assert [entry["code"] for entry in item["evidence"]] == ["AUX_TIMEOUT"]
        assert_event_ledger(case_id, rows, limits, item, events)


def test_residual_link_requires_precommand_and_both_mains_open_guards(hidden, tmp_path):
    """High link voltage is residual only before any command and with both mains open."""
    pack = 800.0
    rows_after_command = [
        _simple_row(0.0, pack=pack, link=8.0),
        _simple_row(20.0, pack=pack, link=100.0, pos_cmd=1),
        _simple_row(40.0, pack=pack, link=120.0, pos_cmd=1),
    ]
    rows_main_closed = [
        _simple_row(0.0, pack=pack, link=100.0, pos_aux=1),
        _simple_row(20.0, pack=pack, link=100.0, pos_aux=1),
        _simple_row(40.0, pack=pack, link=100.0, pos_aux=1),
    ]
    cases = []
    expected = {}
    for rows in (rows_after_command, rows_main_closed):
        filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
        hidden.write_capture(filename, rows)
        case = hidden.case("ok", filename)
        case["limits"]["residual_abs_v"] = 60.0
        case["limits"]["residual_ratio"] = 0.10
        case["limits"]["aux_delay_ms"] = 1000.0
        case["limits"]["weld_dwell_ms"] = 1000.0
        cases.append(case)
        expected[case["case_id"]] = (rows, case["limits"])
    index = hidden.write_index(cases, "residual-guards.json")
    out = tmp_path / "residual-guards-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    by_id = {item["case_id"]: item for item in report["cases"]}
    for case_id, (rows, limits) in expected.items():
        item = by_id[case_id]
        assert "RESIDUAL_LINK" not in [entry["code"] for entry in item["evidence"]]
        assert_event_ledger(case_id, rows, limits, item, events)


def test_input_validation_family_for_unique_rows_finite_values_and_limit_domains(hidden, tmp_path):
    """Explicit input-domain requirements must remain case-local BAD_INPUT."""
    cases = []

    # Two unique timestamps only.
    rows_two = [_simple_row(0.0), _simple_row(10.0)]
    hidden.write_capture("two-unique.csv", rows_two)
    cases.append(hidden.case("ok", "two-unique.csv"))

    # Non-finite analog capture value.
    rows_nan = [_simple_row(0.0), _simple_row(10.0), _simple_row(20.0)]
    hidden.write_capture("nan.csv", rows_nan)
    nan_path = hidden.root / "nan.csv"
    raw = nan_path.read_text(encoding="utf-8").replace("1000.0,0\n", "nan,0\n", 1)
    nan_path.write_text(raw, encoding="utf-8")
    cases.append(hidden.case("ok", "nan.csv"))

    # Wrong capture columns.
    bad_columns = hidden.root / "bad-columns.csv"
    with bad_columns.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS[:-1], lineterminator="\n")
        writer.writeheader()
        for row in [_simple_row(0.0), _simple_row(10.0), _simple_row(20.0)]:
            writer.writerow({key: row[key] for key in CSV_COLUMNS[:-1]})
    cases.append(hidden.case("ok", "bad-columns.csv"))

    # Invalid limit domains and attempt integer semantics.
    valid_name = "validation-base.csv"
    hidden.write_capture(valid_name, [_simple_row(0.0), _simple_row(10.0), _simple_row(20.0)])
    for key, value in (
        ("ready_ratio", 1.0),
        ("short_tau_factor", 0.0),
        ("residual_ratio", 1.0),
        ("safe_close_ratio", 0.0),
        ("sensor_bias_ratio", 1.0),
        ("open_min_rise_ratio", -0.01),
        ("open_min_rise_ratio", 1.0),
        ("sensor_bias_dwell_ms", 0.0),
        ("bounce_interval_ms", 0.0),
    ):
        case = hidden.case("ok", valid_name)
        case["limits"][key] = value
        cases.append(case)
    cap_zero = hidden.case("ok", valid_name)
    cap_zero["capacitance_uf"] = 0.0
    cases.append(cap_zero)
    resistance_zero = hidden.case("ok", valid_name)
    resistance_zero["precharge_ohm"] = 0.0
    cases.append(resistance_zero)
    cap_bool = hidden.case("ok", valid_name)
    cap_bool["capacitance_uf"] = True
    cases.append(cap_bool)
    cases.append(hidden.case("ok", valid_name, session_id="S", attempt=True))
    cases.append(hidden.case("ok", valid_name, session_id="S", attempt=1.5))

    index = hidden.write_index(cases, "invalid-domain-family.json")
    out = tmp_path / "invalid-domain-family-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    assert len(report["cases"]) == len(cases)
    assert all(item["input_state"] == "invalid" for item in report["cases"])
    assert all(item["verdict"] == "BAD_INPUT" for item in report["cases"])
    for item in report["cases"]:
        assert item["flags"] == []
        assert item["metrics"] == {
            "precharge_start_ms": None, "ready_at_ms": None, "ready_delay_ms": None,
            "ready_link_v": None, "final_link_ratio": None, "peak_abs_pack_a": None,
            "max_link_slew_v_per_ms": None, "tau_ms": None,
            "aux_delay_ms": {"neg": None, "pos": None, "pre": None},
            "aux_edges": {"neg": 0, "pos": 0, "pre": 0},
        }
        assert_event_ledger(item["case_id"], [], hidden.limits, item, events)


def test_missing_case_id_uses_position_fallback_and_is_case_local_bad_input(hidden, tmp_path):
    """A missing ID must serialize as invalid_case_<NNNN> without aborting valid peers."""
    rows = hidden.rows("ok")
    hidden.write_capture("missing-id.csv", rows)
    hidden.write_capture("valid-peer.csv", rows)
    missing = hidden.case("ok", "missing-id.csv")
    missing.pop("case_id")
    peer = hidden.case("ok", "valid-peer.csv")
    index = hidden.write_index([missing, peer], "missing-id-index.json")
    out = tmp_path / "missing-id-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    by_id = {item["case_id"]: item for item in report["cases"]}
    assert "invalid_case_0001" in by_id
    bad = by_id["invalid_case_0001"]
    assert bad["input_state"] == "invalid"
    assert bad["verdict"] == "BAD_INPUT"
    assert peer["case_id"] in by_id and by_id[peer["case_id"]]["input_state"] == "valid"
    assert_event_ledger("invalid_case_0001", [], hidden.limits, bad, events)


def test_capture_rows_are_sorted_before_edges_metrics_and_rules(hidden, tmp_path):
    """Physical CSV order must not alter retained time order or derived results."""
    rows = hidden.rows("ok")
    unsorted_rows = rows[::2] + rows[1::2]
    assert [float(r["t_ms"]) for r in unsorted_rows] != sorted(float(r["t_ms"]) for r in unsorted_rows)
    filename = f"{hidden.stream.take(0, 0xFFFFFF):06x}.csv"
    hidden.write_capture(filename, unsorted_rows)
    case = hidden.case("ok", filename)
    index = hidden.write_index([case], "unsorted-capture-index.json")
    out = tmp_path / "unsorted-capture-out"
    result = invoke(index, out)
    assert result.returncode == 0, result.stderr
    report, _ = read_report(out)
    events, _ = read_events(out)
    item = report["cases"][0]
    sorted_rows = sorted(rows, key=lambda row: float(row["t_ms"]))
    assert item["verdict"] == "OK"
    delays, counts = expected_auxiliary_metrics(sorted_rows)
    for key in ("neg", "pos", "pre"):
        assert_optional_number(item["metrics"]["aux_delay_ms"][key], delays[key], abs_tol=5.0)
        assert item["metrics"]["aux_edges"][key] == counts[key]
    assert_event_ledger(case["case_id"], sorted_rows, case["limits"], item, events)
