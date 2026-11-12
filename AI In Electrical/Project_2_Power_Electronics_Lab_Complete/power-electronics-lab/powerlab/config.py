from __future__ import annotations

from dataclasses import dataclass, fields
import json
import math
from pathlib import Path
from typing import TypeVar


T = TypeVar("T")


def finite_parameters(instance) -> None:
    for field in fields(instance):
        value = getattr(instance, field.name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{field.name} must be a finite number")


def load_spec(spec_type: type[T], path: str | Path) -> T:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object")
    unknown = set(data) - {field.name for field in fields(spec_type)}
    if unknown:
        raise ValueError("Unknown configuration fields: " + ", ".join(sorted(unknown)))
    return spec_type(**data)


@dataclass(frozen=True)
class BuckSpec:
    vin_v: float = 48.0
    vout_v: float = 12.0
    power_w: float = 1000.0
    switching_hz: float = 100_000.0
    inductance_h: float = 40e-6
    capacitance_f: float = 2.2e-3
    capacitor_esr_ohm: float = 0.012
    inductor_dcr_ohm: float = 0.001
    high_rds_ohm: float = 0.001
    low_rds_ohm: float = 0.001
    rise_s: float = 20e-9
    fall_s: float = 20e-9
    deadtime_s: float = 100e-9
    diode_v: float = 0.8
    gate_charge_c: float = 100e-9
    gate_drive_v: float = 12.0
    core_loss_w: float = 2.0
    ambient_c: float = 55.0
    theta_junction_k_w: float = 2.0
    junction_limit_c: float = 150.0
    peak_current_limit_a: float = 110.0
    regulation_fraction: float = 0.02
    ripple_fraction: float = 0.01
    proportional_gain: float = 0.30
    integral_gain: float = 8.0

    def __post_init__(self):
        finite_parameters(self)
        exempt = {"ambient_c", "core_loss_w", "rise_s", "fall_s", "deadtime_s",
                  "capacitor_esr_ohm", "inductor_dcr_ohm", "high_rds_ohm", "low_rds_ohm"}
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name not in exempt and value <= 0:
                raise ValueError(f"{field.name} must be positive")
            if field.name in exempt - {"ambient_c"} and value < 0:
                raise ValueError(f"{field.name} must be nonnegative")
        if not 0 < self.vout_v < self.vin_v:
            raise ValueError("Buck requires 0 < Vout < Vin")
        if not 0 < self.regulation_fraction < 0.5 or not 0 < self.ripple_fraction < 0.5:
            raise ValueError("Invalid output tolerances")
        if self.deadtime_s * self.switching_hz >= 0.10:
            raise ValueError("Dead time must be below 10% of switching period")
        if self.ambient_c >= self.junction_limit_c:
            raise ValueError("Ambient must be below junction limit")


@dataclass(frozen=True)
class InverterSpec:
    rated_power_w: float = 150_000.0
    maximum_torque_nm: float = 360.0
    maximum_speed_rpm: float = 12_000.0
    pole_pairs: int = 4
    flux_wb: float = 0.16
    phase_resistance_ohm: float = 0.010
    phase_inductance_h: float = 0.00018
    switch_rds_ohm: float = 0.0016
    switching_hz: float = 10_000.0
    switching_energy_j: float = 0.0025
    energy_reference_current_a: float = 400.0
    energy_reference_voltage_v: float = 800.0
    phase_rms_limit_a: float = 300.0
    dc_current_limit_a: float = 300.0
    coolant_c: float = 65.0
    theta_junction_k_w: float = 0.25
    derate_start_c: float = 125.0
    shutdown_c: float = 170.0
    minimum_bus_v: float = 600.0
    maximum_bus_v: float = 850.0

    def __post_init__(self):
        finite_parameters(self)
        for field in fields(self):
            if field.name not in {"coolant_c", "derate_start_c", "shutdown_c"} and getattr(self, field.name) <= 0:
                raise ValueError(f"{field.name} must be positive")
        if self.pole_pairs != int(self.pole_pairs):
            raise ValueError("pole_pairs must be an integer")
        if not self.coolant_c < self.derate_start_c < self.shutdown_c:
            raise ValueError("Require coolant < derate start < shutdown")
        if self.minimum_bus_v >= self.maximum_bus_v:
            raise ValueError("Invalid DC bus range")


@dataclass(frozen=True)
class OBCSpec:
    rated_power_w: float = 30_000.0
    dc_bus_v: float = 800.0
    turns_ratio: float = 1.0
    resonant_l_h: float = 25e-6
    resonant_c_f: float = 70e-9
    magnetizing_l_h: float = 125e-6
    minimum_hz: float = 80_000.0
    maximum_hz: float = 160_000.0
    power_factor: float = 0.99
    line_current_limit_a: float = 52.0
    pfc_resistance_ohm: float = 0.015
    primary_resistance_ohm: float = 0.015
    secondary_resistance_ohm: float = 0.020
    fixed_loss_w: float = 50.0
    switching_loss_reference_w: float = 200.0
    minimum_efficiency: float = 0.94

    def __post_init__(self):
        finite_parameters(self)
        if any(getattr(self, field.name) <= 0 for field in fields(self)):
            raise ValueError("All OBC parameters must be positive")
        if self.minimum_hz >= self.maximum_hz or not 0 < self.power_factor <= 1 or not 0 < self.minimum_efficiency < 1:
            raise ValueError("Invalid OBC operating limits")
