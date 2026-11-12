from __future__ import annotations

from dataclasses import replace
from itertools import product
import math

from .config import BuckSpec


def operating_point(s: BuckSpec) -> dict:
    current = s.power_w / s.vout_v
    denominator = s.vin_v - current * (s.high_rds_ohm - s.low_rds_ohm)
    if denominator <= 0:
        raise ValueError("No finite duty solution for the specified conduction resistances")
    duty = (s.vout_v + current * (s.inductor_dcr_ohm + s.low_rds_ohm)) / denominator
    if not 0 < duty < 1:
        raise ValueError("Duty solution is outside (0, 1)")
    # CCM first-order ripple; the exact DC conduction drop is included in duty.
    ripple_a = (s.vin_v - s.vout_v - current * (s.inductor_dcr_ohm + s.high_rds_ohm)) * duty / (s.inductance_h * s.switching_hz)
    rms2 = current * current + ripple_a * ripple_a / 12
    high_conduction = rms2 * s.high_rds_ohm * duty
    low_conduction = rms2 * s.low_rds_ohm * (1 - duty)
    inductor_loss = rms2 * s.inductor_dcr_ohm
    switching_loss = 0.5 * s.vin_v * current * (s.rise_s + s.fall_s) * s.switching_hz
    deadtime_loss = 2 * s.diode_v * current * s.deadtime_s * s.switching_hz
    gate_loss = 2 * s.gate_charge_c * s.gate_drive_v * s.switching_hz
    capacitor_loss = ripple_a * ripple_a / 12 * s.capacitor_esr_ohm
    losses = {"high_conduction_w": high_conduction, "low_conduction_w": low_conduction,
              "inductor_w": inductor_loss, "switching_w": switching_loss,
              "deadtime_w": deadtime_loss, "gate_w": gate_loss,
              "capacitor_w": capacitor_loss, "core_w": s.core_loss_w}
    total = sum(losses.values())
    high_tj = s.ambient_c + (high_conduction + switching_loss + gate_loss / 2) * s.theta_junction_k_w
    low_tj = s.ambient_c + (low_conduction + deadtime_loss + gate_loss / 2) * s.theta_junction_k_w
    output_ripple = abs(ripple_a) * (s.capacitor_esr_ohm + 1 / (8 * s.switching_hz * s.capacitance_f))
    peak = current + ripple_a / 2
    violations = []
    if duty > 0.95:
        violations.append("DUTY_HEADROOM")
    if peak > s.peak_current_limit_a:
        violations.append("PEAK_CURRENT")
    if output_ripple > s.ripple_fraction * s.vout_v:
        violations.append("OUTPUT_RIPPLE")
    if max(high_tj, low_tj) > s.junction_limit_c:
        violations.append("JUNCTION_TEMPERATURE")
    if current <= ripple_a / 2:
        violations.append("CCM_ASSUMPTION_INVALID")
    return {"vin_v": s.vin_v, "vout_v": s.vout_v, "power_w": s.power_w,
            "duty": duty, "output_current_a": current, "ripple_current_pp_a": ripple_a,
            "peak_current_a": peak, "output_ripple_pp_v": output_ripple,
            "total_loss_w": total, "efficiency": s.power_w / (s.power_w + total),
            "high_junction_c": high_tj, "low_junction_c": low_tj,
            **losses, "status": "PASS" if not violations else "FAIL", "violations": "|".join(violations)}


def sweep(s: BuckSpec) -> list[dict]:
    return [operating_point(replace(s, vin_v=vin, power_w=power, switching_hz=fsw, ambient_c=ambient))
            for vin, power, fsw, ambient in product(
                (36.0, 48.0, 60.0), (250.0, 500.0, 1000.0),
                (80_000.0, 100_000.0, 150_000.0), (25.0, 55.0, 85.0))]


def transient(s: BuckSpec, fault: str = "none", duration_s: float = 0.080,
              dt: float = 10e-6, step_s: float = 0.020) -> list[dict]:
    """Averaged CCM LC model with PI control, ESR, and RK4 integration."""
    if fault not in {"none", "sensor_bias", "duty_drop"}:
        raise ValueError("Unknown transient fault")
    if not math.isfinite(dt) or not 0 < dt <= min(50e-6, math.sqrt(s.inductance_h * s.capacitance_f) / 20):
        raise ValueError("dt is too large for the LC time constant")
    if not math.isfinite(duration_s) or not 0 < step_s < duration_s or duration_s / dt > 2_000_000:
        raise ValueError("Invalid or excessive simulation duration")
    initial = operating_point(replace(s, power_w=s.power_w * 0.5))
    state = [initial["output_current_a"], s.vout_v, initial["duty"] - s.vout_v / s.vin_v]
    rows = []

    def derivative(y, time_s, load_r):
        il, vc, integral = y
        vo = (vc + s.capacitor_esr_ohm * il) / (1 + s.capacitor_esr_ohm / load_r)
        measurement = vo + (0.8 if fault == "sensor_bias" and time_s >= step_s else 0.0)
        error = s.vout_v - measurement
        unconstrained = s.vout_v / s.vin_v + s.proportional_gain * error + integral
        duty = min(0.95, max(0.0, unconstrained))
        if fault == "duty_drop" and time_s >= step_s:
            duty = initial["duty"] * 0.70
        resistance = s.inductor_dcr_ohm + duty * s.high_rds_ohm + (1 - duty) * s.low_rds_ohm
        dil = (duty * s.vin_v - vo - resistance * il) / s.inductance_h
        dvc = (il - vo / load_r) / s.capacitance_f
        antiwindup = unconstrained > 0.95 and error > 0 or unconstrained < 0 and error < 0
        dint = 0.0 if antiwindup else s.integral_gain * error
        return [dil, dvc, dint], vo, duty

    for index in range(int(math.ceil(duration_s / dt)) + 1):
        t = index * dt
        # Freeze each integration interval's load; a sampled load step occurs
        # at the first sample at or after step_s.
        load_power = s.power_w * (0.5 if t < step_s - 1e-12 else 1.0)
        resistance = s.vout_v * s.vout_v / load_power
        k1, vo, duty = derivative(state, t, resistance)
        rows.append({"time_s": round(t, 12), "vin_v": s.vin_v, "vout_v": vo,
                     "inductor_a": state[0], "load_a": vo / resistance, "duty": duty})
        def advance(k, factor):
            return [v + factor * dt * delta for v, delta in zip(state, k)]
        k2 = derivative(advance(k1, 0.5), t + dt / 2, resistance)[0]
        k3 = derivative(advance(k2, 0.5), t + dt / 2, resistance)[0]
        k4 = derivative(advance(k3, 1), t + dt, resistance)[0]
        state = [v + dt * (a + 2*b + 2*c + e) / 6 for v, a, b, c, e in zip(state, k1, k2, k3, k4)]
        if not all(math.isfinite(value) and abs(value) < 1e8 for value in state):
            raise ValueError("Model diverged; review component values and controller gains")
    return rows
