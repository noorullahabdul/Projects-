"""Strict ngspice execution and evidence handling; never trust exit code alone."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import subprocess


class SpiceError(RuntimeError):
    pass


NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
MEASURE = re.compile(rf"^([a-zA-Z]\w*)\s*=\s*({NUMBER})(?:\s|$)", re.MULTILINE)
ERROR = re.compile(
    r"(?im)^\s*(?:error\b|fatal\b|doanalyses:|.*timestep too small|"
    r".*simulation\(s\) aborted|.*simulation interrupted|.*run simulation.*aborted)"
)


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_engine(explicit: str | None = None) -> str:
    candidate = explicit or os.environ.get("NGSPICE_EXE")
    if candidate:
        found = shutil.which(candidate)
        if found:
            return str(Path(found).resolve())
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path.resolve())
        raise SpiceError("NGSPICE_EXE / --ngspice does not identify an executable")
    for name in ("ngspice", "ngspice_con"):
        found = shutil.which(name)
        if found:
            return str(Path(found).resolve())
    raise SpiceError("Install ngspice, add it to PATH, or supply --ngspice / set NGSPICE_EXE")


def validate_log(log: str, required_measures: tuple[str, ...]) -> dict[str, float]:
    match = ERROR.search(log)
    if match:
        raise SpiceError("ngspice reported an error: " + match.group(0).strip()[:180])
    measures = {}
    for match in MEASURE.finditer(log):
        name, value = match.groups()
        if name in measures:
            raise SpiceError(f"Repeated measurement {name}; expected one simulation")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise SpiceError(f"Non-finite measurement {name}")
        measures[name] = numeric
    missing = set(required_measures) - set(measures)
    if missing:
        raise SpiceError("Required measurements missing: " + ", ".join(sorted(missing)))
    if not re.search(r"No\. of Data Rows\s*:\s*[1-9]\d*", log):
        raise SpiceError("No completed transient dataset reported")
    return measures


def read_wrdata(path: str | Path, required: tuple[str, ...], stop_s: float) -> list[dict]:
    with Path(path).open(encoding="utf-8") as stream:
        header = stream.readline().split()
        if not header or len(set(header)) != len(header) or header[0] != "time":
            raise SpiceError("Missing/duplicated wrdata header; use wr_singlescale and wr_vecnames")
        if set(required) - set(header):
            raise SpiceError("Required waveform vectors missing")
        rows = []
        last = -math.inf
        for line_no, line in enumerate(stream, 2):
            if not line.strip():
                continue
            tokens = line.split()
            if len(tokens) != len(header):
                raise SpiceError(f"Wrong wrdata column count on line {line_no}")
            try:
                values = [float(value) for value in tokens]
            except ValueError as error:
                raise SpiceError(f"Invalid number on wrdata line {line_no}") from error
            if not all(math.isfinite(value) for value in values):
                raise SpiceError(f"Non-finite wrdata on line {line_no}")
            row = dict(zip(header, values))
            if row["time"] < 0 or row["time"] <= last:
                raise SpiceError("wrdata time must be nonnegative and strictly increasing")
            last = row["time"]
            rows.append(row)
            if len(rows) > 2_000_000:
                raise SpiceError("Waveform exceeds two million samples")
    if len(rows) < 3 or abs(rows[0]["time"]) > 1e-9 or abs(rows[-1]["time"] - stop_s) > max(1e-9, stop_s * 1e-8):
        raise SpiceError("Waveform does not span the requested transient")
    return rows


def run_engine(deck: str, out: Path, executable: str, required: tuple[str, ...],
               vectors: tuple[str, ...], stop_s: float) -> tuple[list[dict], dict]:
    out.mkdir(parents=True, exist_ok=True)
    # Fresh outputs are essential: ngspice can exit zero after a failed control command.
    for filename in ("waveform.dat", "ngspice.log", "run.json", "telemetry.csv"):
        (out / filename).unlink(missing_ok=True)
    circuit = out / "circuit.cir"
    circuit.write_text(deck, encoding="utf-8")
    try:
        version = subprocess.run([executable, "--version"], capture_output=True, text=True,
                                 errors="replace", timeout=10, check=False)
        if version.returncode:
            raise SpiceError("Could not read ngspice version")
        executed = subprocess.run(
            [executable, "-n", "-b", "-o", "ngspice.log", "circuit.cir"],
            cwd=out, capture_output=True, text=True, errors="replace", timeout=120, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SpiceError(f"ngspice could not complete: {error}") from error
    (out / "console.txt").write_text(executed.stdout + executed.stderr, encoding="utf-8")
    if executed.returncode:
        raise SpiceError(f"ngspice exited {executed.returncode}; see {out / 'ngspice.log'}")
    log_path = out / "ngspice.log"
    if not log_path.is_file():
        raise SpiceError("ngspice produced no run log")
    log = log_path.read_text(encoding="utf-8", errors="replace")
    measures = validate_log(log, required)
    rows = read_wrdata(out / "waveform.dat", vectors, stop_s)
    metadata = {
        "dataset_type": "SIMULATED_NGSPICE_EXECUTED",
        "measured_hardware": False,
        "engine_version": (version.stdout + version.stderr).strip(),
        "engine_executable_sha256": sha256(executable),
        "command": ["ngspice", "-n", "-b", "-o", "ngspice.log", "circuit.cir"],
        "executed_utc": datetime.now(timezone.utc).isoformat(),
        "exit_code": executed.returncode, "samples": len(rows),
        "stop_time_s": rows[-1]["time"], "requested_stop_s": stop_s,
        "measurements": measures, "netlist_sha256": sha256(circuit),
        "log_sha256": sha256(log_path), "waveform_sha256": sha256(out / "waveform.dat"),
        "warnings": [line.strip() for line in log.splitlines() if line.lower().lstrip().startswith("warning")],
    }
    return rows, metadata
