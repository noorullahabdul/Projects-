from __future__ import annotations

import cmath
from itertools import product
import math

from .config import OBCSpec


def tank(s: OBCSpec, frequency_hz: float, output_v: float, power_w: float) -> dict:
    if not all(math.isfinite(v) and v > 0 for v in (frequency_hz, output_v, power_w)):
        raise ValueError("Positive finite LLC frequency, voltage, and power required")
    omega = 2 * math.pi * frequency_hz
    rac = 8 / math.pi**2 * s.turns_ratio**2 * output_v**2 / power_w
    zm = complex(0, omega * s.magnetizing_l_h)
    parallel = zm * rac / (zm + rac)
    series = complex(0, omega * s.resonant_l_h - 1 / (omega * s.resonant_c_f))
    zin = series + parallel
    gain = abs(parallel / zin)
    fundamental_rms = 2 * math.sqrt(2) / math.pi * s.dc_bus_v
    return {"gain": gain, "input_impedance_real": zin.real, "input_impedance_imag": zin.imag,
            "tank_rms_a": fundamental_rms / abs(zin), "rac_ohm": rac}


def solve_frequency(s: OBCSpec, output_v: float, power_w: float) -> float:
    target = output_v * s.turns_ratio / s.dc_bus_v  # full-bridge primary drive
    points = [s.minimum_hz + (s.maximum_hz - s.minimum_hz) * i / 256 for i in range(257)]
    errors = [tank(s, f, output_v, power_w)["gain"] - target for f in points]
    roots = []
    for a, b, fa, fb in zip(points, points[1:], errors, errors[1:]):
        if fa == 0:
            roots.append(a)
        if fa * fb < 0:
            for _ in range(45):
                mid = (a + b) / 2
                fm = tank(s, mid, output_v, power_w)["gain"] - target
                if fa * fm <= 0:
                    b = mid
                else:
                    a, fa = mid, fm
            roots.append((a + b) / 2)
    if errors[-1] == 0:
        roots.append(points[-1])
    if roots:
        inductive = [f for f in roots if tank(s, f, output_v, power_w)["input_impedance_imag"] > 0]
        return max(inductive or roots)
    return min(points, key=lambda f: abs(tank(s, f, output_v, power_w)["gain"] - target))


def operating_point(s: OBCSpec, line_ll_v: float, output_v: float, power_w: float) -> dict:
    if not all(math.isfinite(v) and v > 0 for v in (line_ll_v, output_v, power_w)):
        raise ValueError("Positive finite OBC operating inputs required")
    frequency = solve_frequency(s, output_v, power_w)
    network = tank(s, frequency, output_v, power_w)
    predicted_v = network["gain"] * s.dc_bus_v / s.turns_ratio
    error = abs(predicted_v / output_v - 1)
    iout = power_w / output_v
    # Input-current/loss fixed-point iteration; no empirical efficiency curve.
    input_power = power_w
    for _ in range(30):
        iac = input_power / (math.sqrt(3) * line_ll_v * s.power_factor)
        losses = (
            3 * iac**2 * s.pfc_resistance_ohm
            + network["tank_rms_a"]**2 * s.primary_resistance_ohm
            + iout**2 * s.secondary_resistance_ohm
            + s.fixed_loss_w
            + s.switching_loss_reference_w * frequency / 120_000 * power_w / s.rated_power_w
        )
        updated = power_w + losses
        if not math.isfinite(updated) or updated > power_w * 10:
            raise ValueError("Loss/current iteration diverged")
        if abs(updated - input_power) < 1e-8:
            input_power = updated
            break
        input_power = updated
    iac = input_power / (math.sqrt(3) * line_ll_v * s.power_factor)
    efficiency = power_w / input_power
    violations = []
    if power_w > s.rated_power_w:
        violations.append("RATED_POWER")
    if error > 0.02:
        violations.append("LLC_GAIN_UNREACHABLE")
    if network["input_impedance_imag"] <= 0:
        violations.append("CAPACITIVE_INPUT_REGION")
    if math.sqrt(2) * line_ll_v >= s.dc_bus_v:
        violations.append("PFC_BOOST_HEADROOM")
    if iac > s.line_current_limit_a:
        violations.append("LINE_CURRENT")
    if efficiency < s.minimum_efficiency:
        violations.append("EFFICIENCY")
    return {
        "line_ll_v": line_ll_v, "output_v": output_v, "power_w": power_w,
        "frequency_hz": frequency, "predicted_output_v": predicted_v,
        "gain_error_fraction": error, "iac_rms_a": iac, "iout_a": iout,
        "loss_w": input_power - power_w, "efficiency": efficiency,
        **network, "status": "PASS" if not violations else "FAIL",
        "violations": "|".join(violations), "zvs_evidence": "NOT_EVALUATED",
    }


def sweep(s: OBCSpec) -> list[dict]:
    return [operating_point(s, *point) for point in product(
        (360.0, 400.0, 440.0), (500.0, 650.0, 800.0), (3000.0, 15000.0, 30000.0)
    )]
