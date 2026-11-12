from __future__ import annotations

from itertools import product
import math

from .config import InverterSpec


def operating_point(s: InverterSpec, vdc_v: float, speed_rpm: float,
                    torque_nm: float, junction_c: float = 100.0) -> dict:
    if not all(math.isfinite(v) for v in (vdc_v, speed_rpm, torque_nm, junction_c)) or vdc_v <= 0:
        raise ValueError("Invalid inverter operating point")
    omega = speed_rpm * 2 * math.pi / 60
    torque_limit = min(s.maximum_torque_nm, s.rated_power_w / abs(omega)) if omega else s.maximum_torque_nm
    derate = min(1.0, max(0.0, (s.shutdown_c - junction_c) / (s.shutdown_c - s.derate_start_c)))
    applied = min(torque_limit * derate, max(-torque_limit * derate, torque_nm))
    iq = applied / (1.5 * s.pole_pairs * s.flux_wb)
    phase_rms = abs(iq) / math.sqrt(2)
    omega_e = s.pole_pairs * omega
    vd = -omega_e * s.phase_inductance_h * iq
    vq = s.phase_resistance_ohm * iq + omega_e * s.flux_wb
    phase_peak_voltage = math.hypot(vd, vq)
    voltage_limit = vdc_v / math.sqrt(3) * 0.95
    motor_copper = 3 * phase_rms**2 * s.phase_resistance_ohm
    motor_core = 150.0 * (abs(speed_rpm) / 4000)**1.5 if speed_rpm else 0.0
    conduction = 3 * phase_rms**2 * s.switch_rds_ohm
    switching = 6 * s.switching_energy_j * s.switching_hz * (
        abs(iq) * 2 / math.pi / s.energy_reference_current_a
    ) * vdc_v / s.energy_reference_voltage_v
    inverter_loss = conduction + switching
    mechanical_power = applied * omega
    dc_power = mechanical_power + motor_copper + motor_core + inverter_loss
    dc_current = dc_power / vdc_v
    estimated_tj = s.coolant_c + inverter_loss / 6 * s.theta_junction_k_w
    if mechanical_power > 0:
        efficiency = mechanical_power / dc_power
        mode = "motoring"
    elif mechanical_power < 0:
        efficiency = max(0.0, -dc_power / -mechanical_power)
        mode = "regeneration" if dc_power < 0 else "braking_without_net_recovery"
    else:
        efficiency = None
        mode = "standstill" if speed_rpm == 0 else "coast"
    violations = []
    if not s.minimum_bus_v <= vdc_v <= s.maximum_bus_v:
        violations.append("DC_BUS_RANGE")
    if abs(speed_rpm) > s.maximum_speed_rpm:
        violations.append("OVERSPEED")
    if junction_c >= s.shutdown_c or estimated_tj >= s.shutdown_c:
        violations.append("OVERTEMPERATURE")
    if phase_rms > s.phase_rms_limit_a:
        violations.append("PHASE_CURRENT")
    if abs(dc_current) > s.dc_current_limit_a:
        violations.append("DC_CURRENT")
    if phase_peak_voltage > voltage_limit:
        violations.append("VOLTAGE_LIMIT_ID_ZERO")
    return {
        "vdc_v": vdc_v, "speed_rpm": speed_rpm, "requested_torque_nm": torque_nm,
        "applied_torque_nm": applied, "junction_input_c": junction_c,
        "derate_factor": derate, "mode": mode, "phase_rms_a": phase_rms,
        "required_phase_peak_v": phase_peak_voltage, "available_phase_peak_v": voltage_limit,
        "mechanical_power_w": mechanical_power, "motor_copper_loss_w": motor_copper,
        "motor_core_loss_w": motor_core, "inverter_conduction_w": conduction,
        "inverter_switching_w": switching, "inverter_loss_w": inverter_loss,
        "dc_power_w": dc_power, "dc_current_a": dc_current,
        "efficiency": efficiency, "estimated_junction_c": estimated_tj,
        "status": "PASS" if not violations else "FAIL", "violations": "|".join(violations),
    }


def sweep(s: InverterSpec) -> list[dict]:
    return [operating_point(s, *point) for point in product(
        (600.0, 800.0, 850.0), (0.0, 1000.0, 4000.0, 8000.0, 12000.0),
        (-250.0, 0.0, 150.0, 360.0), (25.0, 125.0, 150.0, 170.0)
    )]
