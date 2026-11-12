from __future__ import annotations

import csv
import hashlib
import math
from pathlib import Path

from .config import BuckSpec


COLUMNS = ("time_s", "vin_v", "vout_v", "inductor_a", "load_a", "duty")


def write_csv(path: str | Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("No rows to write")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_waveform(path: str | Path) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("Missing or duplicate CSV header")
        missing = set(COLUMNS) - set(reader.fieldnames)
        if missing:
            raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
        rows = []
        previous = -math.inf
        for line, raw in enumerate(reader, 2):
            try:
                if None in raw:
                    raise ValueError("extra column")
                row = {name: float(raw[name]) for name in COLUMNS}
                if not all(math.isfinite(v) for v in row.values()):
                    raise ValueError("non-finite number")
                if row["time_s"] < 0 or row["time_s"] <= previous:
                    raise ValueError("timestamps must be nonnegative and strictly increasing")
                if row["vin_v"] <= 0 or row["vout_v"] < 0 or row["load_a"] < 0 or not 0 <= row["duty"] <= 1:
                    raise ValueError("invalid voltage, load, or duty")
            except (ValueError, TypeError) as error:
                raise ValueError(f"Invalid waveform line {line}: {error}") from error
            previous = row["time_s"]
            rows.append(row)
            if len(rows) > 2_000_000:
                raise ValueError("Waveform exceeds two million samples")
    if len(rows) < 3:
        raise ValueError("At least three samples are required")
    return rows


def time_average(rows: list[dict], key: str) -> float:
    duration = rows[-1]["time_s"] - rows[0]["time_s"]
    if duration <= 0:
        raise ValueError("Average requires a positive duration")
    return sum((a[key] + b[key]) / 2 * (b["time_s"] - a["time_s"])
               for a, b in zip(rows, rows[1:])) / duration


def analyze(rows: list[dict], s: BuckSpec, step_s: float = 0.020) -> dict:
    if not math.isfinite(step_s) or step_s < 0 or len(rows) < 3:
        raise ValueError("Invalid step time or waveform")
    checks = []

    def check(requirement, status, observed, limit):
        checks.append({"requirement": requirement, "status": status, "observed": observed, "limit": limit})

    duration = rows[-1]["time_s"] - rows[0]["time_s"]
    max_gap = max(b["time_s"] - a["time_s"] for a, b in zip(rows, rows[1:]))
    covered = rows[0]["time_s"] <= step_s - 0.002 and rows[-1]["time_s"] >= step_s + 0.020
    check("BUCK-001 sampling and coverage", "PASS" if covered and max_gap <= 50e-6 + 1e-12 else "INCOMPLETE",
          {"duration_s": duration, "maximum_gap_s": max_gap}, "2 ms pre-step; 20 ms post-step; gap <=50 us")
    plateau = [row for row in rows if row["time_s"] >= max(step_s, rows[-1]["time_s"] - 0.010)]
    if len(plateau) < 2:
        plateau = rows
    average = time_average(plateau, "vout_v")
    error = abs(average / s.vout_v - 1)
    check("BUCK-002 steady regulation", "PASS" if error <= s.regulation_fraction else "FAIL",
          average, f"{s.vout_v} V +/- {s.regulation_fraction*100:g}%")
    # Average power at each sample, rather than multiplying two independent averages.
    power_rows = [{**r, "power_w": r["vout_v"] * r["load_a"]} for r in plateau]
    load_power = time_average(power_rows, "power_w")
    check("BUCK-003 rated load observed", "PASS" if abs(load_power / s.power_w - 1) <= 0.05 else "FAIL",
          load_power, f"{s.power_w} W +/-5% in final plateau")
    low, high = min(r["vout_v"] for r in rows), max(r["vout_v"] for r in rows)
    check("BUCK-004 transient voltage envelope",
          "PASS" if 0.90 * s.vout_v <= low and high <= 1.10 * s.vout_v else "FAIL",
          {"minimum_v": low, "maximum_v": high}, "within +/-10% during load step")
    peak = max(abs(row["inductor_a"]) for row in rows)
    check("BUCK-005 current peak", "PASS" if peak <= s.peak_current_limit_a else "FAIL",
          peak, f"<= {s.peak_current_limit_a} A")
    post = [row for row in rows if row["time_s"] >= step_s]
    outside = [i for i, row in enumerate(post) if abs(row["vout_v"] / s.vout_v - 1) > s.regulation_fraction]
    recovery = None
    if post:
        index = outside[-1] + 1 if outside else 0
        if index < len(post) and post[-1]["time_s"] - post[index]["time_s"] >= 0.005:
            recovery = post[index]["time_s"] - step_s
    check("BUCK-006 settling", "PASS" if recovery is not None and recovery <= 0.020 else "FAIL" if covered else "INCOMPLETE",
          recovery, "2% band within 20 ms, held >=5 ms")
    check("BUCK-007 input observed", "PASS" if all(abs(row["vin_v"] / s.vin_v - 1) <= 0.05 for row in rows) else "FAIL",
          time_average(rows, "vin_v"), f"{s.vin_v} V +/-5%")
    statuses = {row["status"] for row in checks}
    verdict = "FAIL" if "FAIL" in statuses else "INCOMPLETE" if "INCOMPLETE" in statuses else "PASS"
    return {"verdict": verdict, "checks": checks, "samples": len(rows),
            "steady_low_frequency_pp_v": max(r["vout_v"] for r in plateau) - min(r["vout_v"] for r in plateau),
            "waveform_model": "averaged CCM; switching ripple is estimated separately"}


def digest(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
