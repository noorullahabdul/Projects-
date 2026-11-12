#!/usr/bin/env python3
"""Static integrity checks for EV-DCL-LTS-005.

This validator does not replace an LTspice run. It checks package structure,
include resolution, controlled-model rules and expected implementation tokens.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REQUIRED = [
    "DCLINK_PHYSICAL_MODELS.lib",
    "DCLINK_PHYSICAL_PLANT.inc",
    "DCLINK_PHYSICAL_NOMINAL.cir",
    "DCLINK_PHYSICAL_CORNERS.cir",
    "DCLINK_PHYSICAL_FAULTS.cir",
    "DCLINK_PHYSICAL_OVERVIEW.asc",
    "README.md",
    "DESIGN_BASIS.md",
    "MODEL_REPLACEMENT_GUIDE.md",
    "SOURCE_REFERENCES.md",
    "component_parameter_map.csv",
    "acceptance_matrix.csv",
    "run_all_ltspice.bat",
    "parse_ltspice_log.py",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
if missing:
    fail("missing required files: " + ", ".join(missing))

model_text = (ROOT / "DCLINK_PHYSICAL_MODELS.lib").read_text(encoding="utf-8")
plant_text = (ROOT / "DCLINK_PHYSICAL_PLANT.inc").read_text(encoding="utf-8")
nominal_text = (ROOT / "DCLINK_PHYSICAL_NOMINAL.cir").read_text(encoding="utf-8")
controlled_text = "\n".join([model_text, plant_text, nominal_text])
controlled_netlist = "\n".join(
    line for line in controlled_text.splitlines() if not line.lstrip().startswith("*")
)

if re.search(r"(?im)^\s*B\w+\s", controlled_netlist):
    fail("behavioral B source found in nominal controlled model")
if re.search(r"(?i)R\s*=\s*if\s*\(", controlled_netlist):
    fail("time/command-controlled R=if contact found")

required_tokens = [
    ".subckt EV200_COIL_CONTACTOR",
    ".subckt PRECHARGE_COIL_CONTACTOR",
    ".subckt COIL_LOW_SIDE_DRIVER",
    ".subckt DISCRETE_COMPARATOR",
    ".subckt ACTIVE_DISCHARGE",
    "RCOIL",
    "LCOIL",
    "VCOIL_SENSE",
    "HFORCE",
    "CARM",
    "SMAIN",
    "MDRV",
    "DNEG_FLY",
    "DPOS_FLY",
    "DPRE_FLY",
    "QPKILL",
    "MTIMEOUT",
    "XVCMP",
]
for token in required_tokens:
    if token.lower() not in controlled_text.lower():
        fail(f"expected physical-model token missing: {token}")

for deck_name in [
    "DCLINK_PHYSICAL_NOMINAL.cir",
    "DCLINK_PHYSICAL_CORNERS.cir",
    "DCLINK_PHYSICAL_FAULTS.cir",
]:
    deck = (ROOT / deck_name).read_text(encoding="utf-8")
    if ".include DCLINK_PHYSICAL_PLANT.inc" not in deck:
        fail(f"{deck_name} does not include the controlled plant")
    if not re.search(r"(?im)^\.tran\s", deck):
        fail(f"{deck_name} has no transient analysis")
    if not re.search(r"(?im)^\.end\s*$", deck):
        fail(f"{deck_name} has no terminal .end")

print("PASS: package structure and controlled-model rules")
print("PASS: no behavioral B source in models, plant or nominal deck")
print("PASS: no command-driven R=if contact in controlled model")
print("PASS: coil, driver, armature, auxiliary, comparator and discharge blocks present")
print("\nSHA-256 manifest")
for name in REQUIRED:
    data = (ROOT / name).read_bytes()
    print(f"{hashlib.sha256(data).hexdigest()}  {name}")

print("\nNOTE: run LTspice locally; static validation is not simulation evidence.")

