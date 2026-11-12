from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

FORMAT = "hv-powerup/1"
DIGITAL = ("pre_cmd", "pre_aux", "pos_cmd", "pos_aux", "neg_cmd", "neg_aux", "crash")
COLUMNS = (
    "t_ms", "pack_v", "link_v", "pack_a", "pre_cmd", "pre_aux",
    "pos_cmd", "pos_aux", "neg_cmd", "neg_aux", "iso_kohm", "crash",
)
LIMITS = (
    "ready_ratio", "max_precharge_ms", "aux_delay_ms", "weld_dwell_ms",
    "bounce_interval_ms", "open_check_ms", "open_min_rise_ratio",
    "short_tau_factor", "isolation_min_kohm", "residual_abs_v",
    "residual_ratio", "safe_close_ratio", "sensor_bias_abs_v",
    "sensor_bias_ratio", "sensor_bias_dwell_ms",
)


class FatalInputError(ValueError):
    pass


class CaseInputError(ValueError):
    pass


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise CaseInputError(f"{label} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CaseInputError(f"{label} must be a finite number") from exc
    if not math.isfinite(number):
        raise CaseInputError(f"{label} must be a finite number")
    return number


def load_index(path: str | Path) -> tuple[Path, list[Any]]:
    index_path = Path(path).resolve()
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FatalInputError(f"cannot read index: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("cases"), list):
        raise FatalInputError(f"index must use format {FORMAT!r} and contain a cases array")
    return index_path, data["cases"]


def validate_case(raw: Any, position: int, base: Path) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CaseInputError("case must be an object")
    case_id = raw.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        case_id = f"invalid_case_{position:04d}"
        raise CaseInputError(f"case_id is missing; assigned {case_id}")
    capture = raw.get("capture")
    if not isinstance(capture, str) or not capture:
        raise CaseInputError("capture must be a non-empty string")
    cap = finite_number(raw.get("capacitance_uf"), "capacitance_uf")
    resistance = finite_number(raw.get("precharge_ohm"), "precharge_ohm")
    if cap <= 0 or resistance <= 0:
        raise CaseInputError("capacitance_uf and precharge_ohm must be positive")
    limits_raw = raw.get("limits")
    if not isinstance(limits_raw, dict):
        raise CaseInputError("limits must be an object")
    limits: dict[str, float] = {}
    for key in LIMITS:
        value = finite_number(limits_raw.get(key), f"limits.{key}")
        if key == "open_min_rise_ratio":
            if value < 0:
                raise CaseInputError(f"limits.{key} must be non-negative")
        elif value <= 0:
            raise CaseInputError(f"limits.{key} must be positive")
        limits[key] = value
    if not 0 <= limits["open_min_rise_ratio"] < 1:
        raise CaseInputError("limits.open_min_rise_ratio must be in [0, 1)")
    for key in (
        "ready_ratio",
        "short_tau_factor",
        "residual_ratio",
        "safe_close_ratio",
        "sensor_bias_ratio",
    ):
        if not 0 < limits[key] < 1:
            raise CaseInputError(f"limits.{key} must be between 0 and 1")
    session_id = raw.get("session_id")
    attempt = raw.get("attempt")
    has_session = "session_id" in raw
    has_attempt = "attempt" in raw
    if has_session != has_attempt:
        raise CaseInputError("session_id and attempt must be provided together")
    if has_session:
        if not isinstance(session_id, str) or not session_id.strip():
            raise CaseInputError("session_id must be a non-empty string")
        if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
            raise CaseInputError("attempt must be a positive integer")
        session = {"session_id": session_id, "attempt": attempt}
    else:
        session = None

    return {
        "case_id": case_id,
        "capture": (base / capture).resolve() if not Path(capture).is_absolute() else Path(capture).resolve(),
        "capacitance_uf": cap,
        "precharge_ohm": resistance,
        "limits": limits,
        "session": session,
    }


def load_capture(path: str | Path) -> list[dict[str, float | int]]:
    capture_path = Path(path)
    try:
        handle = capture_path.open("r", encoding="utf-8", newline="")
    except OSError as exc:
        raise CaseInputError(f"cannot read capture: {exc}") from exc
    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or set(reader.fieldnames) != set(COLUMNS):
            raise CaseInputError("capture has the wrong columns")
        by_time: dict[float, dict[str, float | int]] = {}
        for line_number, raw in enumerate(reader, start=2):
            row: dict[str, float | int] = {}
            for key in COLUMNS:
                value = finite_number(raw.get(key), f"line {line_number} {key}")
                if key in DIGITAL:
                    if value not in (0.0, 1.0):
                        raise CaseInputError(f"line {line_number} {key} must be 0 or 1")
                    row[key] = int(value)
                else:
                    row[key] = value
            by_time[float(row["t_ms"])] = row
    rows = [by_time[key] for key in sorted(by_time)]
    if len(rows) < 3:
        raise CaseInputError("capture must contain at least three unique times")
    return rows
