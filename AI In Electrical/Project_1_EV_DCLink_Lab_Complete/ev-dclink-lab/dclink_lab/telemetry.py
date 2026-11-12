from __future__ import annotations

import csv
import hashlib
import math
from pathlib import Path

from .design import Design


REQUIRED = (
    "time_s", "vpack_v", "vdc_v", "pre_current_a", "wake",
    "neg_aux", "pos_aux", "pre_aux", "discharge_cmd", "torque_enable",
)
BOOL_FIELDS = ("wake", "neg_aux", "pos_aux", "pre_aux", "discharge_cmd", "torque_enable")


def write_csv(path: str | Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty dataset")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: str | Path) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Missing or duplicated CSV header")
        missing = set(REQUIRED) - set(reader.fieldnames)
        if missing:
            raise ValueError("Missing CSV columns: " + ", ".join(sorted(missing)))
        rows = []
        last = -math.inf
        for line, raw in enumerate(reader, 2):
            if None in raw:
                raise ValueError(f"Unexpected extra column on line {line}")
            row = dict(raw)
            try:
                for name in REQUIRED:
                    row[name] = float(raw[name])
                    if not math.isfinite(row[name]):
                        raise ValueError("non-finite number")
                if any(row[name] not in (0, 1) for name in BOOL_FIELDS):
                    raise ValueError("boolean columns require 0 or 1")
                if row["time_s"] < 0 or row["time_s"] <= last:
                    raise ValueError("timestamps must be nonnegative and strictly increasing")
                if row["vpack_v"] <= 0 or row["vdc_v"] < 0:
                    raise ValueError("invalid voltage")
            except (ValueError, TypeError) as error:
                raise ValueError(f"Invalid CSV line {line}: {error}") from error
            last = row["time_s"]
            rows.append(row)
            if len(rows) > 2_000_000:
                raise ValueError("CSV exceeds two million rows")
    if len(rows) < 2:
        raise ValueError("At least two samples are required")
    return rows


def analyze(rows: list[dict], d: Design) -> dict:
    if len(rows) < 2:
        raise ValueError("At least two samples required")
    checks = []

    def check(key, status, observed, limit):
        checks.append({"requirement": key, "status": status, "observed": observed, "limit": limit})

    gaps = [b["time_s"] - a["time_s"] for a, b in zip(rows, rows[1:])]
    gap = max(gaps)
    check("DCL-001 sampling", "PASS" if gap <= 0.020 + 1e-12 else "INCOMPLETE", gap, "maximum gap 0.020 s")
    peak = max(abs(row["pre_current_a"]) for row in rows)
    check("DCL-002 precharge current", "PASS" if peak <= d.maximum_current_a else "FAIL", peak, f"<= {d.maximum_current_a} A")
    closures = [b for a, b in zip(rows, rows[1:]) if not a["pos_aux"] and b["pos_aux"]]
    ratios = [row["vdc_v"] / row["vpack_v"] for row in closures]
    check("DCL-003 close ratio", "PASS" if ratios and min(ratios) >= d.minimum_close_ratio else "FAIL" if ratios else "INCOMPLETE",
          min(ratios) if ratios else None, f">= {d.minimum_close_ratio}")
    wake = next((row["time_s"] for row in rows if row["wake"]), None)
    run = next((row["time_s"] for row in rows if row["torque_enable"]), None)
    startup = run - wake if run is not None and wake is not None else None
    check("DCL-004 startup", "PASS" if startup is not None and startup <= d.startup_limit_s else "FAIL" if wake is not None and rows[-1]["time_s"] - wake >= d.startup_limit_s else "INCOMPLETE",
          startup, f"<= {d.startup_limit_s} s from wake")
    unsafe = sum(bool(row["torque_enable"]) and (
        not row["neg_aux"] or not row["pos_aux"] or row["discharge_cmd"]
        or row["vdc_v"] / row["vpack_v"] < d.minimum_close_ratio
    ) for row in rows)
    check("DCL-005 torque interlock", "PASS" if unsafe == 0 else "FAIL", unsafe, "zero unsafe samples")
    connected_discharge = sum(bool(row["discharge_cmd"]) and bool(row["neg_aux"] or row["pos_aux"] or row["pre_aux"]) for row in rows)
    check("DCL-006 isolated discharge", "PASS" if connected_discharge == 0 else "FAIL", connected_discharge, "zero connected discharge samples")
    start = next((i for i, row in enumerate(rows) if row["discharge_cmd"]), None)
    safe_t = None
    if start is not None:
        # Linear crossing interpolation removes sample-period bias from the timing metric.
        for a, b in zip(rows[start:], rows[start + 1:]):
            if a["vdc_v"] >= d.safe_voltage_v > b["vdc_v"]:
                fraction = (a["vdc_v"] - d.safe_voltage_v) / (a["vdc_v"] - b["vdc_v"])
                safe_t = a["time_s"] + fraction * (b["time_s"] - a["time_s"]) - rows[start]["time_s"]
                break
    status = "PASS" if safe_t is not None and safe_t <= d.discharge_limit_s else "FAIL" if start is not None and rows[-1]["time_s"] - rows[start]["time_s"] >= d.discharge_limit_s else "INCOMPLETE"
    check("DCL-007 discharge", status, safe_t, f"< {d.safe_voltage_v} V within {d.discharge_limit_s} s")
    statuses = {item["status"] for item in checks}
    verdict = "FAIL" if "FAIL" in statuses else "INCOMPLETE" if "INCOMPLETE" in statuses else "PASS"
    return {"verdict": verdict, "checks": checks, "samples": len(rows),
            "duration_s": rows[-1]["time_s"] - rows[0]["time_s"],
            "diagnostics": sorted({row.get("fault", "") for row in rows} - {""})}


def file_digest(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
