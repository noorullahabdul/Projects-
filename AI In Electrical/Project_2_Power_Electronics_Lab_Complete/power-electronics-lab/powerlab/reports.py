from __future__ import annotations

from html import escape
import json
from pathlib import Path


def save_json(path: str | Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def table(rows: list[dict], limit: int = 25) -> str:
    if not rows:
        return "<p>No data.</p>"
    columns = list(rows[0])
    def cell(value):
        if isinstance(value, float):
            return f"{value:.6g}"
        if value is None:
            return "—"
        return escape(str(value))
    return "<div class=\"scroll\"><table><thead><tr>" + "".join("<th>" + escape(key.replace("_", " ")) + "</th>" for key in columns) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join("<td>" + cell(row.get(key)) + "</td>" for key in columns) + "</tr>" for row in rows[:limit]
    ) + "</tbody></table></div>"


def plot(rows: list[dict]) -> str:
    if len(rows) < 2:
        return ""
    sampled = rows[::max(1, len(rows)//1000)]
    if sampled[-1] is not rows[-1]:
        sampled.append(rows[-1])
    t0, t1 = rows[0]["time_s"], rows[-1]["time_s"]
    vmin, vmax = min(row["vout_v"] for row in rows) - 0.2, max(row["vout_v"] for row in rows) + 0.2
    points = " ".join(f'{65+(r["time_s"]-t0)/(t1-t0)*880:.2f},{240-(r["vout_v"]-vmin)/(vmax-vmin)*210:.2f}' for r in sampled)
    labels = "".join(f'<text x="53" y="{244-i*52.5}" text-anchor="end" font-size="11">{vmin+(vmax-vmin)*i/4:.2f}</text><line x1="65" x2="945" y1="{240-i*52.5}" y2="{240-i*52.5}" stroke="#e2e8ef"/>' for i in range(5))
    labels += "".join(f'<text x="{65+i*146.667}" y="265" text-anchor="middle" font-size="11">{(t0+(t1-t0)*i/6)*1000:.0f}</text>' for i in range(7))
    return f'<svg role="img" aria-label="Buck output voltage load-step waveform" viewBox="0 0 980 300">{labels}<polyline points="{points}" fill="none" stroke="#007e87" stroke-width="2.3"/><text x="20" y="18" font-size="12">V</text><text x="500" y="294" text-anchor="middle" font-size="12">Time (ms) — output voltage, averaged plant</text></svg>'


def report(path: str | Path, summary: dict, waveform: list[dict], buck_rows: list[dict],
           inverter_rows: list[dict], obc_rows: list[dict]) -> None:
    sections = '<section><h2>Buck load-step response</h2>' + plot(waveform) + table(summary["buck_transient"]["checks"]) + "</section>"
    sections += "<section><h2>Loss and thermal screening — buck</h2><p>Full sweep in buck_sweep.csv.</p>" + table(buck_rows, 12) + "</section>"
    sections += "<section><h2>150 kW traction inverter</h2><p>Signed DC power distinguishes motoring and regeneration. Infeasible voltage points are flagged; field weakening is not simulated.</p>" + table(inverter_rows, 12) + "</section>"
    sections += "<section><h2>Three-phase PFC / full-bridge LLC</h2><p>LLC frequency is solved using an FHA impedance network. Inductive input impedance does not establish ZVS; ZVS evidence remains NOT_EVALUATED.</p>" + table(obc_rows, 12) + "</section>"
    body = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Power Electronics Lab — computed report</title><style>
body{{font-family:system-ui,sans-serif;background:#edf2f6;color:#182c3d;max-width:1180px;margin:auto;padding:36px 24px}}
h1{{font-size:38px;margin:12px 0}}h2{{font-size:23px}}p{{line-height:1.6;color:#435d70}}.eyebrow{{letter-spacing:.12em;font-size:12px;font-weight:750;color:#007e87}}
section{{background:white;padding:24px;margin:24px 0;border:1px solid #d9e2e9;border-radius:14px}}.scroll{{overflow:auto}}
table{{border-collapse:collapse;font-size:12px;min-width:100%}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #e1e9ef;white-space:nowrap}}th{{background:#f5f8fa}}
svg{{width:100%;height:auto}}pre{{white-space:pre-wrap;font-size:12px}}a{{color:#00717b}}
</style><body><div class="eyebrow">POWER ELECTRONICS LAB / REPRODUCIBLE ANALYSIS</div><h1>Converter &amp; inverter validation</h1>
<p>48 V → 12 V / 1 kW buck · 30 kW OBC · 150 kW traction inverter. These are synthetic model results with explicit parameter assumptions, not laboratory measurements.</p>
{sections}<section><h2>Run summary</h2><pre>{escape(json.dumps(summary,indent=2))}</pre></section></body></html>"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(body, encoding="utf-8")
