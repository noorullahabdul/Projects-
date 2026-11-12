from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from itertools import product
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class Design:
    pack_v: float = 800.0
    pack_min_v: float = 600.0
    pack_max_v: float = 850.0
    capacitance_f: float = 0.001
    precharge_ohm: float = 92.0
    source_ohm: float = 0.047
    discharge_ohm: float = 1000.0
    command_ratio: float = 0.93
    minimum_close_ratio: float = 0.90
    maximum_current_a: float = 10.0
    startup_limit_s: float = 0.350
    contactor_delay_budget_s: float = 0.030
    safe_voltage_v: float = 60.0
    discharge_limit_s: float = 5.0
    resistor_tolerance: float = 0.03
    capacitor_tolerance: float = 0.10
    sensor_tolerance: float = 0.015

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{field.name} must be a finite number")
        positive = (
            "pack_v", "pack_min_v", "pack_max_v", "capacitance_f",
            "precharge_ohm", "source_ohm", "discharge_ohm",
            "maximum_current_a", "startup_limit_s", "safe_voltage_v",
            "discharge_limit_s",
        )
        if any(getattr(self, name) <= 0 for name in positive):
            raise ValueError("Electrical values and time limits must be positive")
        if not 0 < self.minimum_close_ratio <= self.command_ratio < 1:
            raise ValueError("Require 0 < minimum_close_ratio <= command_ratio < 1")
        if not self.safe_voltage_v < self.pack_min_v <= self.pack_v <= self.pack_max_v:
            raise ValueError("Invalid pack range or safe voltage")
        if not 0 <= self.contactor_delay_budget_s < self.startup_limit_s:
            raise ValueError("Contactor delay budget must fit inside startup limit")
        for name in ("resistor_tolerance", "capacitor_tolerance", "sensor_tolerance"):
            if not 0 <= getattr(self, name) < 0.5:
                raise ValueError(f"{name} must be in [0, 0.5)")

    @classmethod
    def load(cls, path: str | Path) -> "Design":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Design JSON must be an object")
        unknown = set(payload) - {field.name for field in fields(cls)}
        if unknown:
            raise ValueError("Unknown design fields: " + ", ".join(sorted(unknown)))
        return cls(**payload)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")


def charge_voltage(voltage: float, resistance: float, capacitance: float, time_s: float) -> float:
    if not all(math.isfinite(v) for v in (voltage, resistance, capacitance, time_s)) or voltage < 0 or resistance <= 0 or capacitance <= 0 or time_s < 0:
        raise ValueError("Invalid RC charging parameters")
    return -voltage * math.expm1(-time_s / (resistance * capacitance))


def charge_time(resistance: float, capacitance: float, ratio: float) -> float:
    if not all(math.isfinite(v) for v in (resistance, capacitance, ratio)) or resistance <= 0 or capacitance <= 0 or not 0 < ratio < 1:
        raise ValueError("Invalid RC charging parameters")
    return -resistance * capacitance * math.log1p(-ratio)


def discharge_time(voltage: float, safe_v: float, resistance: float, capacitance: float) -> float:
    if not all(math.isfinite(v) for v in (voltage, safe_v, resistance, capacitance)) or safe_v <= 0 or resistance <= 0 or capacitance <= 0 or voltage < 0:
        raise ValueError("Invalid RC discharge parameters")
    return 0.0 if voltage <= safe_v else resistance * capacitance * math.log(voltage / safe_v)


def corner_sweep(d: Design) -> list[dict]:
    """Enumerate component corners and independent pack/link gain errors."""
    rows = []
    for pack, rscale, cscale, pack_error, link_error in product(
        sorted({d.pack_min_v, d.pack_v, d.pack_max_v}),
        (1 - d.resistor_tolerance, 1, 1 + d.resistor_tolerance),
        (1 - d.capacitor_tolerance, 1, 1 + d.capacitor_tolerance),
        (-d.sensor_tolerance, d.sensor_tolerance),
        (-d.sensor_tolerance, d.sensor_tolerance),
    ):
        resistance = d.precharge_ohm * rscale
        capacitance = d.capacitance_f * cscale
        actual_ratio = d.command_ratio * (1 + pack_error) / (1 + link_error)
        reachable = actual_ratio < 1
        startup = (
            charge_time(resistance + d.source_ohm, capacitance, actual_ratio)
            + d.contactor_delay_budget_s if reachable else None
        )
        current = pack / (resistance + d.source_ohm)
        tdis = discharge_time(
            pack, d.safe_voltage_v, d.discharge_ohm * 1.10, capacitance
        )
        rows.append({
            "case": len(rows) + 1, "pack_v": pack, "resistance_ohm": resistance,
            "capacitance_f": capacitance, "pack_gain_error": pack_error,
            "link_gain_error": link_error, "actual_ratio": actual_ratio,
            "startup_s": startup, "initial_current_a": current,
            "stored_energy_j": 0.5 * capacitance * pack * pack,
            "discharge_s": tdis,
            "pass": bool(reachable and startup <= d.startup_limit_s
                         and actual_ratio >= d.minimum_close_ratio
                         and current <= d.maximum_current_a
                         and tdis <= d.discharge_limit_s),
        })
    return rows
