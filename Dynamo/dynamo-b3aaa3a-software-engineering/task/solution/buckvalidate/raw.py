"""Robust reader for real-valued ngspice ASCII raw files."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import re


@dataclass(frozen=True)
class RawPlot:
    title: str
    plotname: str
    variables: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]


_FIELD = re.compile(r"^\s*([^:]+):\s*(.*?)\s*$")
_INT = re.compile(r"^[+-]?\d+$")


def _next_nonblank(lines: list[str], pos: int) -> tuple[int, str]:
    while pos < len(lines) and not lines[pos].strip():
        pos += 1
    if pos >= len(lines):
        raise ValueError("unexpected end of raw file")
    return pos, lines[pos]


def _parse_plot(lines: list[str], start: int) -> tuple[RawPlot, int]:
    headers: dict[str, str] = {}
    pos = start
    while pos < len(lines):
        text = lines[pos].strip()
        if text.lower() == "variables:":
            pos += 1
            break
        match = _FIELD.match(lines[pos])
        if match:
            headers[match.group(1).strip().lower()] = match.group(2).strip()
        pos += 1
    else:
        raise ValueError("plot is missing Variables section")

    try:
        nvars = int(headers["no. variables"])
        npoints = int(headers["no. points"])
    except (KeyError, ValueError) as exc:
        raise ValueError("invalid variable or point count") from exc
    if nvars <= 0 or npoints < 0:
        raise ValueError("invalid variable or point count")
    flags = headers.get("flags", "").lower().split()
    if "complex" in flags or "real" not in flags:
        raise ValueError("only real-valued plots are supported")

    variables: list[str] = []
    for expected in range(nvars):
        pos, line = _next_nonblank(lines, pos)
        parts = line.split()
        if len(parts) < 3 or not _INT.match(parts[0]) or int(parts[0]) != expected:
            raise ValueError("invalid Variables section")
        variables.append(parts[1])
        pos += 1

    pos, line = _next_nonblank(lines, pos)
    if line.strip().lower() != "values:":
        raise ValueError("plot is missing Values section")
    pos += 1

    rows: list[tuple[float, ...]] = []
    for expected_point in range(npoints):
        pos, line = _next_nonblank(lines, pos)
        parts = line.split()
        if len(parts) < 2 or not _INT.match(parts[0]) or int(parts[0]) != expected_point:
            raise ValueError(f"invalid point index at record {expected_point}")
        number_tokens = parts[1:]
        pos += 1
        while len(number_tokens) < nvars:
            pos, continuation = _next_nonblank(lines, pos)
            number_tokens.extend(continuation.split())
            pos += 1
        if len(number_tokens) != nvars:
            raise ValueError(f"wrong value count at record {expected_point}")
        try:
            values = tuple(float(token) for token in number_tokens)
        except ValueError as exc:
            raise ValueError(f"non-numeric value at record {expected_point}") from exc
        if not all(isfinite(value) for value in values):
            raise ValueError(f"non-finite value at record {expected_point}")
        rows.append(values)

    return RawPlot(
        title=headers.get("title", ""),
        plotname=headers.get("plotname", ""),
        variables=tuple(variables),
        rows=tuple(rows),
    ), pos


def read_ascii_raw(path: str | Path) -> RawPlot:
    """Return the last real transient plot in *path*."""
    source = Path(path)
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("raw file is not UTF-8 text") from exc

    plots: list[RawPlot] = []
    pos = 0
    while pos < len(lines):
        while pos < len(lines) and not lines[pos].lstrip().lower().startswith("title:"):
            pos += 1
        if pos >= len(lines):
            break
        plot, pos = _parse_plot(lines, pos)
        plots.append(plot)

    transient = [plot for plot in plots if "transient analysis" in plot.plotname.lower()]
    if not transient:
        raise ValueError("no transient plot found")
    return transient[-1]
