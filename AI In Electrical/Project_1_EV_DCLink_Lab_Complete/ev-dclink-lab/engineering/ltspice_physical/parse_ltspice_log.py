#!/usr/bin/env python3
"""Extract stepped LTspice .meas results into a rectangular CSV file."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


STEP_RE = re.compile(r"^\.step\s+(.+)$", re.IGNORECASE)
MEAS_RE = re.compile(
    r"^([A-Za-z][A-Za-z0-9_]*)\s*:\s*([-+0-9.eE]+)(?:\s+FROM\s+.*)?$",
    re.IGNORECASE,
)


def parse(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: dict[str, str] = {"step": "unstepped"}
    for raw_line in path.read_text(errors="replace").splitlines():
        line = raw_line.strip()
        step_match = STEP_RE.match(line)
        if step_match:
            if len(current) > 1:
                rows.append(current)
            current = {"step": step_match.group(1)}
            continue
        measure_match = MEAS_RE.match(line)
        if measure_match:
            current[measure_match.group(1)] = measure_match.group(2)
    if len(current) > 1:
        rows.append(current)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()
    rows = parse(args.log)
    if not rows:
        raise SystemExit("No .meas results found in the supplied LTspice log")
    fields = ["step"] + sorted({key for row in rows for key in row if key != "step"})
    with args.csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} row(s) to {args.csv}")


if __name__ == "__main__":
    main()

