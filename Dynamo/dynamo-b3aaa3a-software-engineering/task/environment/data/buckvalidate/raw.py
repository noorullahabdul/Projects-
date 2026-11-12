"""Parser for ngspice ASCII raw files.

The public task intentionally leaves this implementation incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RawPlot:
    title: str
    plotname: str
    variables: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]


def read_ascii_raw(path: str | Path) -> RawPlot:
    """Return the last transient plot in an ngspice ASCII raw file."""
    raise NotImplementedError("implement ngspice ASCII raw parsing")
