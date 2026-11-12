from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .design import Design, corner_sweep
from .report import write_report
from .simulation import FAULTS, simulate
from .storage import history, record_run, save_json
from .telemetry import analyze, file_digest, read_csv, write_csv


def demo(design: Design, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    nominal = simulate(design)
    write_csv(out / "nominal.csv", nominal)
    result = analyze(nominal, design)
    fault_results = []
    for name, expected in FAULTS.items():
        if name == "none":
            continue
        rows = simulate(design, name)
        write_csv(out / "faults" / f"{name}.csv", rows)
        observed = next((row["fault"] for row in rows if row["fault"]), "")
        connected_discharge = any(row["discharge_cmd"] and (row["pos_aux"] or row["neg_aux"] or row["pre_aux"]) for row in rows)
        unexpected_torque = name != "discharge_open" and any(row["torque_enable"] for row in rows)
        passed = observed == expected and not connected_discharge and not unexpected_torque
        fault_results.append({"fault": name, "expected": expected, "observed": observed, "status": "PASS" if passed else "FAIL"})
    corners = corner_sweep(design)
    write_csv(out / "corners.csv", corners)
    result["fault_tests"] = fault_results
    result["corner_count"] = len(corners)
    result["corner_failures"] = sum(not row["pass"] for row in corners)
    result["source"] = "deterministic synthetic analytical plant"
    result["design"] = asdict(design)
    result["experiment_verified"] = result["verdict"] == "PASS" and all(row["status"] == "PASS" for row in fault_results)
    save_json(out / "summary.json", result)
    write_report(out / "report.html", "DC-link validation experiment", result, nominal, fault_results, corners)
    record_run(out / "runs.sqlite3", "demo", design, result, file_digest(out / "nominal.csv"))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="DC-link simulation and CSV diagnostics")
    parser.add_argument("--design", type=Path, help="Design JSON; defaults are 800 V / 92 ohm / 1 mF")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("demo", "sweep"):
        child = commands.add_parser(command)
        child.add_argument("--out", type=Path, default=Path("outputs") / command)
    simulation = commands.add_parser("simulate")
    simulation.add_argument("--fault", choices=list(FAULTS), default="none")
    simulation.add_argument("--csv", type=Path, default=Path("outputs/trace.csv"))
    simulation.add_argument("--duration", type=float, default=6.0)
    simulation.add_argument("--dt", type=float, default=0.002)
    analysis = commands.add_parser("analyze")
    analysis.add_argument("csv", type=Path)
    analysis.add_argument("--out", type=Path, default=Path("outputs/analysis"))
    log = commands.add_parser("history")
    log.add_argument("database", type=Path)
    commands.add_parser("default-design")
    args = parser.parse_args(argv)
    try:
        d = Design.load(args.design) if args.design else Design()
        if args.command == "default-design":
            print(json.dumps(asdict(d), indent=2))
        elif args.command == "demo":
            result = demo(d, args.out)
            print(json.dumps({"nominal": result["verdict"], "fault_tests": len(result["fault_tests"]),
                              "experiment_verified": result["experiment_verified"],
                              "design_corner_failures": result["corner_failures"],
                              "report": str(args.out / "report.html")}, indent=2))
            return 0 if result["experiment_verified"] else 1
        elif args.command == "simulate":
            write_csv(args.csv, simulate(d, args.fault, args.duration, args.dt))
            print(args.csv)
        elif args.command == "sweep":
            rows = corner_sweep(d)
            write_csv(args.out / "corners.csv", rows)
            failed = sum(not row["pass"] for row in rows)
            result = {"cases": len(rows), "failed": failed}
            save_json(args.out / "summary.json", result)
            print(json.dumps(result))
            return 1 if failed else 0
        elif args.command == "analyze":
            rows = read_csv(args.csv)
            result = analyze(rows, d)
            result["input_sha256"] = file_digest(args.csv)
            result["source"] = str(args.csv.name)
            save_json(args.out / "summary.json", result)
            write_report(args.out / "report.html", "Imported DC-link telemetry", result, rows)
            record_run(args.out / "runs.sqlite3", "analyze", d, result, result["input_sha256"])
            print(json.dumps(result, indent=2))
            return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}[result["verdict"]]
        elif args.command == "history":
            print(json.dumps(history(args.database), indent=2))
    except (ValueError, OSError, TypeError, csv.Error, json.JSONDecodeError) as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
