"""Command-line workflow for buck-converter waveform validation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .metrics import CSV_FIELDS, analyze_case
from .raw import read_ascii_raw


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate ngspice buck-converter traces")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--requirements", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def _invalid_row(case: dict[str, str], message: str) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id", ""),
        "case_type": (case.get("case_type") or "").strip().lower(),
        "status": "invalid",
        "case_pass": False,
        "fsw_hz": None,
        "vout_avg_v": None,
        "ripple_v_pp": None,
        "settling_time_s": None,
        "min_vout_v": None,
        "max_vout_v": None,
        "recovery_time_s": None,
        "peak_inductor_current_a": None,
        "errors": message,
        "checks": {},
    }


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.12g}"
    return value


def run(manifest_path: Path, requirements_path: Path, output_dir: Path) -> None:
    requirements = json.loads(requirements_path.read_text(encoding="utf-8"))
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        cases = list(csv.DictReader(handle))
    if not cases:
        raise ValueError("manifest contains no cases")

    rows: list[dict[str, Any]] = []
    for case in cases:
        raw_text = (case.get("raw_path") or "").strip()
        raw_path = Path(raw_text)
        if not raw_path.is_absolute():
            raw_path = manifest_path.parent / raw_path
        try:
            plot = read_ascii_raw(raw_path)
            row = analyze_case(plot, case, requirements)
        except Exception as exc:  # one bad trace must not suppress the remaining report
            row = _invalid_row(case, str(exc))
        rows.append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "measurements.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in CSV_FIELDS})

    valid = sum(row["status"] == "ok" for row in rows)
    passed = sum(bool(row["case_pass"]) for row in rows)
    report = {
        "schema_version": 1,
        "overall_pass": passed == len(rows),
        "summary": {
            "total_cases": len(rows),
            "valid_cases": valid,
            "passed_cases": passed,
        },
        "cases": rows,
    }
    (output_dir / "validation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = build_parser().parse_args()
    run(Path(args.manifest), Path(args.requirements), Path(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
