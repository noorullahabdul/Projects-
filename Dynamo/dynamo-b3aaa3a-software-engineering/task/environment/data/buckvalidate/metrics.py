"""Waveform metrics for closed-loop buck-converter validation.

The public task intentionally leaves this implementation incomplete.
"""

from __future__ import annotations

from typing import Any

from .raw import RawPlot


def analyze_case(plot: RawPlot, case: dict[str, str], requirements: dict[str, Any]) -> dict[str, Any]:
    """Analyze one manifest case and return one output row."""
    raise NotImplementedError("implement converter metrics")


def evaluate_case(metrics: dict[str, Any], requirements: dict[str, Any]) -> dict[str, bool]:
    """Evaluate one metric row against the supplied requirements."""
    raise NotImplementedError("implement requirement evaluation")
