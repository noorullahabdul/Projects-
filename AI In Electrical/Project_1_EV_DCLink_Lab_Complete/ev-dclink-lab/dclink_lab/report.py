from __future__ import annotations

from html import escape
import json
from pathlib import Path


CSS = """
:root{font-family:system-ui,sans-serif;color:#172a3a;background:#eef2f6}
body{max-width:1120px;margin:0 auto;padding:36px 24px 70px}h1{font-size:36px;margin:12px 0}
h2{margin-top:36px;font-size:23px}.eyebrow{color:#076b76;font-weight:750;letter-spacing:.14em;font-size:12px}
.subtitle{color:#486071;line-height:1.6;max-width:830px}.panel{background:#fff;border:1px solid #d7e0e7;border-radius:14px;padding:24px;margin:20px 0;overflow:auto}
.badge{display:inline-block;border-radius:6px;padding:4px 9px;font-size:12px;font-weight:750;background:#e6edf3}
.PASS{background:#d8f3e6;color:#116640}.FAIL{background:#ffe1df;color:#a02225}.INCOMPLETE{background:#fff0ca;color:#805d00}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:11px 12px;border-bottom:1px solid #e3eaf0;vertical-align:top}
th{background:#f5f8fa;color:#3e5769;font-size:12px}code,pre{font-family:ui-monospace,monospace}pre{font-size:12px;white-space:pre-wrap}
svg{width:100%;height:auto}a{color:#006d79}.footnote{font-size:12px;color:#536a7a}
"""


def table(rows: list[dict]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    columns = list(rows[0])

    def cell(value):
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.6g}"
        text = escape(str(value))
        return f'<span class="badge {text}">{text}</span>' if value in ("PASS", "FAIL", "INCOMPLETE") else text

    return "<table><thead><tr>" + "".join(f"<th>{escape(k.replace('_', ' '))}</th>" for k in columns) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join(f"<td>{cell(row.get(k))}</td>" for k in columns) + "</tr>" for row in rows
    ) + "</tbody></table>"


def voltage_svg(rows: list[dict]) -> str:
    if not rows:
        return ""
    width, height = 980, 300
    left, top, plot_w, plot_h = 60, 25, 890, 220
    t0, t1 = rows[0]["time_s"], rows[-1]["time_s"]
    vmax = max(max(row["vdc_v"], row["vpack_v"]) for row in rows) * 1.08
    sampled = rows[::max(1, len(rows) // 900)]
    if sampled[-1] is not rows[-1]:
        sampled.append(rows[-1])
    points = " ".join(f'{left + (r["time_s"]-t0)/(t1-t0 or 1)*plot_w:.2f},{top+plot_h-r["vdc_v"]/vmax*plot_h:.2f}' for r in sampled)
    grid = ""
    for i in range(5):
        y = top + plot_h - i * plot_h / 4
        grid += f'<line x1="{left}" x2="{left+plot_w}" y1="{y}" y2="{y}" stroke="#dde6ed"/><text x="48" y="{y+4}" text-anchor="end" font-size="11" fill="#536a7a">{vmax*i/4:.0f}</text>'
    for i in range(7):
        x = left + i * plot_w / 6
        grid += f'<text x="{x}" y="268" text-anchor="middle" font-size="11" fill="#536a7a">{t0+(t1-t0)*i/6:.1f}</text>'
    return f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="DC-link voltage versus time"><text x="15" y="15" font-size="11">V</text>{grid}<polyline points="{points}" fill="none" stroke="#087f8c" stroke-width="2.5"/><text x="500" y="294" text-anchor="middle" font-size="12">Time (s) — DC-link voltage</text></svg>'


def write_report(path: str | Path, title: str, result: dict, rows: list[dict] | None = None,
                 faults: list[dict] | None = None, corners: list[dict] | None = None) -> None:
    sections = '<div class="panel">' + table(result.get("checks", [])) + "</div>"
    if rows:
        sections = '<div class="panel"><h2>Nominal transient</h2>' + voltage_svg(rows) + "</div>" + sections
    if faults is not None:
        sections += "<h2>Injected faults — observed controller diagnostics</h2><div class=\"panel\">" + table(faults) + "</div>"
    if corners is not None:
        failed = [row for row in corners if not row["pass"]]
        sections += f"<h2>Design corners</h2><p>{len(corners)-len(failed)} / {len(corners)} meet all analytical limits. Full data: corners.csv.</p>"
        if failed:
            sections += '<div class="panel"><h3>Failing corners (first 12)</h3>' + table(failed[:12]) + "</div>"
    body = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{CSS}</style><body>
<div class="eyebrow">EV DC-LINK LAB / ENGINEERING EVIDENCE</div><h1>{escape(title)}</h1>
<p class="subtitle">800 V precharge, contactor sequencing, isolated discharge and telemetry verification.
Demo traces are synthetic analytical simulations. Imported traces retain their input hash in the run database.
Historical documents under engineering are references; this report contains the current computed checks.</p>
<p><span class="badge {escape(result['verdict'])}">{escape(result['verdict'])}</span> nominal / imported operating cycle</p>
{sections}<div class="panel"><h2>Machine-readable result</h2><pre>{escape(json.dumps(result, indent=2))}</pre></div>
<p class="footnote">Software verification and first-order modelling only. LTspice and MATLAB files require their own local simulation and correlation.</p>
</body></html>"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(body, encoding="utf-8")
