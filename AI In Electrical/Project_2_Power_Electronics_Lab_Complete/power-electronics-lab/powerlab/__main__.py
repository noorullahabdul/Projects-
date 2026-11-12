from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import json
from pathlib import Path
import sys

from . import buck, inverter, obc
from .config import BuckSpec, InverterSpec, OBCSpec, load_spec
from .reports import report, save_json
from .spice import export_buck
from .waveforms import analyze, digest, read_waveform, write_csv


def demo(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    spec = BuckSpec()
    waveform = buck.transient(spec)
    write_csv(out / "buck_nominal.csv", waveform)
    result = analyze(waveform, spec)
    fault_results = []
    for fault in ("sensor_bias", "duty_drop"):
        rows = buck.transient(spec, fault)
        write_csv(out / f"buck_{fault}.csv", rows)
        outcome = analyze(rows, spec)
        fault_results.append({"fault": fault, "observed": outcome["verdict"],
                              "fault_detected": outcome["verdict"] == "FAIL",
                              "failed_checks": [x["requirement"] for x in outcome["checks"] if x["status"] == "FAIL"]})
    buck_rows, inv_rows, obc_rows = buck.sweep(spec), inverter.sweep(InverterSpec()), obc.sweep(OBCSpec())
    for filename, rows in (("buck_sweep.csv", buck_rows), ("inverter_map.csv", inv_rows), ("obc_map.csv", obc_rows)):
        write_csv(out / filename, rows)
    summary = {
        "source": "synthetic analytical models", "buck_spec": asdict(spec),
        "inverter_spec": asdict(InverterSpec()), "obc_spec": asdict(OBCSpec()),
        "buck_transient": result, "buck_nominal_point": buck.operating_point(spec),
        "fault_injections": fault_results, "input_sha256": digest(out / "buck_nominal.csv"),
        "screening": {name: {"cases": len(rows), "pass": sum(r["status"] == "PASS" for r in rows),
                              "fail": sum(r["status"] == "FAIL" for r in rows)}
                      for name, rows in (("buck", buck_rows), ("inverter", inv_rows), ("obc", obc_rows))},
        "software_demo_verified": result["verdict"] == "PASS" and all(r["fault_detected"] for r in fault_results),
    }
    save_json(out / "summary.json", summary)
    report(out / "report.html", summary, waveform, buck_rows, inv_rows, obc_rows)
    export_buck(spec, out / "buck_ideal_switches.cir")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Power converter, LLC and inverter validation workbench")
    commands = parser.add_subparsers(dest="command", required=True)
    demo_parser = commands.add_parser("demo")
    demo_parser.add_argument("--out", type=Path, default=Path("outputs/demo"))
    for name in ("buck-point", "buck-sweep", "simulate", "analyze", "export-spice", "inverter-map", "obc-map"):
        p = commands.add_parser(name)
        p.add_argument("--spec", type=Path)
        if name in {"buck-sweep", "inverter-map", "obc-map"}:
            p.add_argument("--csv", type=Path, default=Path("outputs") / (name + ".csv"))
        elif name == "simulate":
            p.add_argument("--fault", choices=("none", "sensor_bias", "duty_drop"), default="none")
            p.add_argument("--csv", type=Path, default=Path("outputs/buck.csv"))
        elif name == "analyze":
            p.add_argument("csv", type=Path)
            p.add_argument("--step-time", type=float, default=0.020)
            p.add_argument("--out", type=Path, default=Path("outputs/waveform-summary.json"))
        elif name == "export-spice":
            p.add_argument("--out", type=Path, default=Path("outputs/buck.cir"))
    config = commands.add_parser("default-config")
    config.add_argument("kind", choices=("buck", "inverter", "obc"))
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            result = demo(args.out)
            print(json.dumps({"software_demo_verified": result["software_demo_verified"],
                              "screening": result["screening"], "report": str(args.out / "report.html")}, indent=2))
            return 0 if result["software_demo_verified"] else 1
        if args.command == "default-config":
            cls = {"buck": BuckSpec, "inverter": InverterSpec, "obc": OBCSpec}[args.kind]
            print(json.dumps(asdict(cls()), indent=2))
            return 0
        cls = InverterSpec if args.command == "inverter-map" else OBCSpec if args.command == "obc-map" else BuckSpec
        spec = load_spec(cls, args.spec) if args.spec else cls()
        if args.command == "buck-point":
            result = buck.operating_point(spec)
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command in {"buck-sweep", "inverter-map", "obc-map"}:
            rows = {"buck-sweep": buck.sweep, "inverter-map": inverter.sweep, "obc-map": obc.sweep}[args.command](spec)
            write_csv(args.csv, rows)
            print(json.dumps({"cases": len(rows), "failures": sum(r["status"] == "FAIL" for r in rows), "csv": str(args.csv)}))
            return 1 if any(r["status"] == "FAIL" for r in rows) else 0
        if args.command == "simulate":
            write_csv(args.csv, buck.transient(spec, args.fault))
            print(args.csv)
        elif args.command == "analyze":
            result = analyze(read_waveform(args.csv), spec, args.step_time)
            result["input_sha256"] = digest(args.csv)
            save_json(args.out, result)
            print(json.dumps(result, indent=2))
            return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}[result["verdict"]]
        elif args.command == "export-spice":
            export_buck(spec, args.out)
            print(args.out)
    except (ValueError, OSError, TypeError, csv.Error, json.JSONDecodeError) as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
