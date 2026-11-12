"""Extract LTspice stepped .meas results into a rectangular CSV.

Usage: python parse_ltspice_log.py input.log output.csv
The parser preserves undefined/error strings for engineering adjudication.
"""
from pathlib import Path
import csv, re, sys

if len(sys.argv) != 3:
    raise SystemExit('Usage: python parse_ltspice_log.py input.log output.csv')
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
text = src.read_text(errors='replace').splitlines()
step_re = re.compile(r'^\.step\s+(.*)$', re.I)
meas_re = re.compile(r'^([A-Za-z][\w]*)\s*[:=]\s*([^\s]+)', re.I)
rows=[]; current={}; active=False
for line in text:
    line=line.strip()
    sm=step_re.match(line)
    if sm:
        if current: rows.append(current)
        current={'step':sm.group(1)}; active=True; continue
    mm=meas_re.match(line)
    if mm and (active or mm.group(1).upper().startswith(('I_','V_','T_','E_','P_'))):
        current[mm.group(1)]=mm.group(2)
if current: rows.append(current)
if not rows:
    raise SystemExit('No stepped or measured results found in the log.')
fields=[]
for row in rows:
    for key in row:
        if key not in fields: fields.append(key)
with dst.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
print(f'Wrote {len(rows)} result rows to {dst}')
