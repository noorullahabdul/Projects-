"""Run an installed LTspice on a copy of a selected model, preserving sources.

No LTspice executable is shipped in this bundle. Exit code alone is never
treated as proof of a completed simulation or an electrical acceptance pass.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from inspect_models import ROOT,read_text,validate
from raw_evidence import inspect


def locate(explicit):
    if explicit:
        p=Path(explicit).expanduser()
        if p.is_file():return p.resolve()
        raise ValueError("--ltspice does not identify an existing executable")
    candidates=[]
    for name in ("LTspice.exe","XVIIx64.exe"):
        match=shutil.which(name)
        if match:candidates.append(Path(match))
    for env,tail in (("LOCALAPPDATA","Programs/ADI/LTspice/LTspice.exe"),
                     ("ProgramFiles","ADI/LTspice/LTspice.exe")):
        if os.environ.get(env):candidates.append(Path(os.environ[env])/tail)
    for p in candidates:
        if p.is_file():return p.resolve()
    raise ValueError("LTspice is not installed here. Open Model.asc on your LTspice computer or supply --ltspice.")


def check_log(text):
    bad=re.search(r"(?im)^\s*(?:ERROR\b|Fatal\b|Time step too small|Unknown subcircuit|Unknown parameter)|Simulation stopped by user|Measurement .+ FAIL",text)
    if bad:raise RuntimeError("Native run did not complete cleanly: "+bad.group(0))
    if "Total elapsed time:" not in text:raise RuntimeError("Native completion marker missing")


def main(argv=None):
    parser=argparse.ArgumentParser(description="Run one of the five bundled schematics in installed Windows LTspice")
    parser.add_argument("--model",choices=("01","02","03","04","05","all"),default="01")
    parser.add_argument("--list",action="store_true")
    parser.add_argument("--ltspice")
    parser.add_argument("--out",type=Path,default=ROOT/"output/ltspice")
    parser.add_argument("--timeout",type=int,default=600)
    args=parser.parse_args(argv)
    folders=sorted(p for p in (ROOT/"models").iterdir() if (p/"Model.asc").is_file())
    if args.list:
        for p in folders:print(p.name)
        return 0
    try:
        executable=locate(args.ltspice)
        if args.timeout<1:raise ValueError("Timeout must be positive")
        selected=folders if args.model=="all" else [p for p in folders if p.name.startswith(args.model+"_")]
        records=[]
        for source in selected:
            static=validate(source)
            if static["static_status"]!="PASS":raise ValueError("Resolve static issues before native execution")
            target=(args.out/source.name).resolve();target.mkdir(parents=True,exist_ok=True)
            if target==source.resolve() or target.is_relative_to(source.resolve()):
                raise ValueError("Run output must be outside the source model folder")
            for file in source.iterdir():
                if file.is_file() and file.suffix.lower() in (".asc",".asy",".sub",".lib",".plt"):
                    shutil.copyfile(file,target/file.name)
            for name in ("Model.net","Model.log","Model.raw"):(target/name).unlink(missing_ok=True)
            commands=[[str(executable),"-netlist",str(target/"Model.asc")],
                      [str(executable),"-b",str(target/"Model.net")]]
            for command in commands:
                run=subprocess.run(command,cwd=target,capture_output=True,text=True,errors="replace",timeout=args.timeout)
                if run.returncode:raise RuntimeError(f"LTspice exited {run.returncode}: {run.stderr[:200]}")
                if "-netlist" in command and not (target/"Model.net").is_file():
                    raise RuntimeError("LTspice did not produce the netlist")
            log=read_text(target/"Model.log");check_log(log)
            raw=target/"Model.raw"
            summary,_=inspect(raw.read_bytes())
            expected={"01":.0015,"02":.001,"03":.01,"04":.005,"05":.012}[source.name[:2]]
            if abs(summary["last_time_s"]-expected)>max(1e-9,expected*1e-6):
                raise RuntimeError("Native waveform did not reach the configured stop time")
            record={"model":source.name,"native_simulation":"COMPLETED",
                    "electrical_acceptance":"NOT_CONFIGURED","measured_hardware":False,
                    "commands":commands,"raw":summary,
                    "schematic_sha256":hashlib.sha256((target/"Model.asc").read_bytes()).hexdigest()}
            (target/"run.json").write_text(json.dumps(record,indent=2)+"\n");records.append(record)
            print(source.name,"native simulation completed; electrical acceptance remains separate")
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
        print("LTspice workflow:",exc)
        return 2


if __name__=="__main__":raise SystemExit(main())
