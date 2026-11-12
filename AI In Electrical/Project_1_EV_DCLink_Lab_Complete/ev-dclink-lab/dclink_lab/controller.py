from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from .design import Design


class State(str, Enum):
    OFF = "OFF"
    SELF_TEST = "SELF_TEST"
    NEG_CLOSE = "NEG_CLOSE"
    PRECHARGE = "PRECHARGE"
    MAIN_CLOSE = "MAIN_CLOSE"
    RUN = "RUN"
    OPENING = "OPENING"
    DISCHARGE = "DISCHARGE"
    SAFE = "SAFE"
    FAULT = "FAULT"


@dataclass(frozen=True)
class Inputs:
    dt: float = 0.001
    wake: bool = False
    shutdown: bool = False
    hvil: bool = True
    isolation_ok: bool = True
    neg_aux: bool = False
    pos_aux: bool = False
    pre_aux: bool = False
    vpack: float = 800.0
    vdc: float = 0.0
    vdc_secondary: float | None = None
    pre_current_a: float = 0.0


@dataclass(frozen=True)
class Outputs:
    neg_cmd: bool = False
    pos_cmd: bool = False
    pre_cmd: bool = False
    discharge_cmd: bool = False
    torque_enable: bool = False
    fault: str = ""


class Controller:
    """Educational supervisor; no hardware interface or automatic fault reset."""

    STARTUP_STATES = {
        State.SELF_TEST, State.NEG_CLOSE, State.PRECHARGE, State.MAIN_CLOSE
    }
    ENERGIZED_STATES = STARTUP_STATES | {State.RUN}

    def __init__(self, design: Design | None = None):
        self.design = design or Design()
        self.state = State.OFF
        self.elapsed = 0.0
        self.startup_elapsed = 0.0
        self.fault = ""
        self.outputs = Outputs()

    def transition(self, state: State) -> None:
        self.state = state
        self.elapsed = 0.0

    def fail(self, code: str) -> None:
        if not self.fault:
            self.fault = code
        if self.state is not State.FAULT:
            self.transition(State.FAULT)

    def step(self, x: Inputs) -> Outputs:
        if not math.isfinite(x.dt) or not 0 < x.dt <= 0.1:
            raise ValueError("dt must be finite and in (0, 0.1] seconds")
        self.elapsed += x.dt
        if self.state in self.STARTUP_STATES:
            self.startup_elapsed += x.dt
        d = self.design
        measurements = (x.vpack, x.vdc, x.pre_current_a)
        if x.vdc_secondary is not None:
            measurements += (x.vdc_secondary,)
        valid = all(math.isfinite(value) for value in measurements)
        valid = valid and x.vpack > 0 and x.vdc >= 0
        if x.vdc_secondary is not None:
            valid = valid and x.vdc_secondary >= 0
        if not valid:
            self.fail("INVALID_SENSOR")
        elif self.state in self.ENERGIZED_STATES:
            if not x.hvil or not x.isolation_ok:
                self.fail("HV_SAFETY_INPUT")
            elif not d.pack_min_v <= x.vpack <= d.pack_max_v:
                self.fail("PACK_RANGE")
            elif x.vdc_secondary is not None and abs(x.vdc - x.vdc_secondary) > max(5.0, 0.05 * x.vpack):
                self.fail("SENSOR_DISAGREEMENT")
            elif abs(x.pre_current_a) > d.maximum_current_a:
                self.fail("PRE_OVERCURRENT")
            elif x.shutdown:
                self.transition(State.OPENING)
            elif self.state in self.STARTUP_STATES and self.startup_elapsed > d.startup_limit_s + 1e-12:
                self.fail("STARTUP_TIMEOUT")

        if self.state is State.OFF and x.wake and valid:
            self.startup_elapsed = 0
            self.transition(State.SELF_TEST)
        elif self.state is State.SELF_TEST:
            if x.neg_aux or x.pos_aux or x.pre_aux:
                self.fail("CONTACTOR_CLOSED_AT_START")
            elif x.vdc >= d.safe_voltage_v:
                self.fail("LINK_NOT_DISCHARGED")
            else:
                self.transition(State.NEG_CLOSE)
        elif self.state is State.NEG_CLOSE:
            if x.pos_aux:
                self.fail("UNCOMMANDED_POSITIVE")
            elif x.neg_aux:
                self.transition(State.PRECHARGE)
            elif self.elapsed >= 0.050:
                self.fail("NEG_TIMEOUT")
        elif self.state is State.PRECHARGE:
            if not x.neg_aux:
                self.fail("NEG_FEEDBACK_LOST")
            elif x.pos_aux:
                self.fail("UNCOMMANDED_POSITIVE")
            else:
                lower_vdc = min(x.vdc, x.vdc_secondary) if x.vdc_secondary is not None else x.vdc
                if lower_vdc / x.vpack >= d.command_ratio:
                    self.transition(State.MAIN_CLOSE)
        elif self.state is State.MAIN_CLOSE:
            lower_vdc = min(x.vdc, x.vdc_secondary) if x.vdc_secondary is not None else x.vdc
            if not x.neg_aux:
                self.fail("NEG_FEEDBACK_LOST")
            elif lower_vdc / x.vpack < d.minimum_close_ratio:
                self.fail("CLOSE_VOLTAGE_LOST")
            elif x.pos_aux:
                self.transition(State.RUN)
            elif self.elapsed >= 0.050:
                self.fail("POS_TIMEOUT")
        elif self.state is State.RUN:
            if not x.neg_aux or not x.pos_aux:
                self.fail("MAIN_FEEDBACK_LOST")
            elif min(x.vdc, x.vdc_secondary if x.vdc_secondary is not None else x.vdc) / x.vpack < d.minimum_close_ratio:
                self.fail("RUN_LINK_UNDERVOLTAGE")
            elif x.pre_aux and self.elapsed > 0.050:
                self.fail("PRE_CONTACTOR_STUCK")
        elif self.state is State.OPENING:
            if not (x.neg_aux or x.pos_aux or x.pre_aux):
                self.transition(State.DISCHARGE)
            elif self.elapsed >= 0.050:
                self.fail("CONTACTOR_OPEN_TIMEOUT")
        elif self.state is State.DISCHARGE:
            if x.vdc < d.safe_voltage_v:
                self.transition(State.SAFE)
            elif self.elapsed >= d.discharge_limit_s:
                self.fail("DISCHARGE_TIMEOUT")

        s = self.state
        isolated = not (x.neg_aux or x.pos_aux or x.pre_aux)
        # A latched fault cannot start a resistor discharge into a connected pack.
        discharge = (s is State.DISCHARGE or s is State.FAULT) and valid and isolated and x.vdc >= d.safe_voltage_v
        self.outputs = Outputs(
            neg_cmd=s in {State.NEG_CLOSE, State.PRECHARGE, State.MAIN_CLOSE, State.RUN},
            pre_cmd=s in {State.PRECHARGE, State.MAIN_CLOSE},
            pos_cmd=s in {State.MAIN_CLOSE, State.RUN},
            discharge_cmd=discharge,
            torque_enable=s is State.RUN and x.neg_aux and x.pos_aux,
            fault=self.fault,
        )
        return self.outputs
