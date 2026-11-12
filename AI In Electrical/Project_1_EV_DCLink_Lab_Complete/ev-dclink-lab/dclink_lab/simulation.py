from __future__ import annotations

from dataclasses import dataclass
import math

from .controller import Controller, Inputs
from .design import Design


FAULTS = {
    "none": "",
    "precharge_open": "STARTUP_TIMEOUT",
    "precharge_short": "PRE_OVERCURRENT",
    "negative_open": "NEG_TIMEOUT",
    "positive_open": "POS_TIMEOUT",
    "positive_weld": "CONTACTOR_CLOSED_AT_START",
    "precharge_weld": "CONTACTOR_CLOSED_AT_START",
    "sensor_bias": "SENSOR_DISAGREEMENT",
    "hvil_open": "HV_SAFETY_INPUT",
    "isolation_fault": "HV_SAFETY_INPUT",
    "discharge_open": "DISCHARGE_TIMEOUT",
}


@dataclass
class Relay:
    closed: bool = False
    timer: float = 0.0

    def step(self, command: bool, dt: float, fault: str = "") -> bool:
        if fault == "weld":
            self.closed = True
        elif fault == "open":
            self.closed = False
        elif command != self.closed:
            self.timer += dt
            if self.timer + 1e-12 >= (0.012 if command else 0.008):
                self.closed = command
                self.timer = 0
        else:
            self.timer = 0
        return self.closed


def simulate(d: Design, fault: str = "none", duration_s: float = 6.0, dt: float = 0.002) -> list[dict]:
    if fault not in FAULTS:
        raise ValueError(f"Unknown fault {fault}")
    if not math.isfinite(dt) or not 0 < dt <= 0.01:
        raise ValueError("Simulation dt must be in (0, 0.01]")
    if not math.isfinite(duration_s) or duration_s <= 0 or duration_s / dt > 2_000_000:
        raise ValueError("Invalid or excessive simulation duration")
    controller = Controller(d)
    neg, pos, pre = Relay(), Relay(), Relay()
    vdc = 0.0
    current = 0.0
    rows = []
    for index in range(int(math.ceil(duration_s / dt)) + 1):
        t = index * dt
        previous = controller.outputs
        neg.step(previous.neg_cmd, dt, "open" if fault == "negative_open" else "")
        pos.step(previous.pos_cmd, dt, "weld" if fault == "positive_weld" else "open" if fault == "positive_open" else "")
        pre.step(previous.pre_cmd, dt, "weld" if fault == "precharge_weld" else "")
        sensed = vdc * (1.15 if fault == "sensor_bias" and t >= 0.05 else 1.0)
        out = controller.step(Inputs(
            dt=dt, wake=t >= 0.020, shutdown=t >= 0.700,
            hvil=not (fault == "hvil_open" and t >= 0.15),
            isolation_ok=not (fault == "isolation_fault" and t >= 0.15),
            neg_aux=neg.closed, pos_aux=pos.closed, pre_aux=pre.closed,
            vpack=d.pack_v, vdc=sensed, vdc_secondary=vdc, pre_current_a=current,
        ))
        resistance = (1.0 if fault == "precharge_short" else d.precharge_ohm) + d.source_ohm
        current = (d.pack_v - vdc) / resistance if neg.closed and pre.closed and fault != "precharge_open" else 0.0
        rows.append({
            "time_s": round(t, 9), "vpack_v": d.pack_v, "vdc_v": vdc,
            "sensed_vdc_v": sensed, "pre_current_a": current,
            "wake": int(t >= 0.020), "shutdown": int(t >= 0.700),
            "neg_aux": int(neg.closed), "pos_aux": int(pos.closed),
            "pre_aux": int(pre.closed), "discharge_cmd": int(out.discharge_cmd),
            "torque_enable": int(out.torque_enable),
            "state": controller.state.value, "fault": out.fault,
        })
        if neg.closed and pos.closed:
            vdc = d.pack_v + (vdc - d.pack_v) * math.exp(-dt / (d.source_ohm * d.capacitance_f))
        elif neg.closed and pre.closed and fault != "precharge_open":
            vdc = d.pack_v + (vdc - d.pack_v) * math.exp(-dt / (resistance * d.capacitance_f))
        elif out.discharge_cmd and fault != "discharge_open":
            vdc *= math.exp(-dt / (d.discharge_ohm * d.capacitance_f))
    return rows
