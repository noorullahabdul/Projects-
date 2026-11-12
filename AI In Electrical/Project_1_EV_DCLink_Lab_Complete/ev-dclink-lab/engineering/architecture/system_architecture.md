# 800 V DC-Link System Architecture

## Scope

The subsystem connects a 600-850 V battery pack to an inverter DC-link. It controls precharge, main positive/negative contactors, active/passive discharge, HV interlock supervision, isolation plausibility, voltage sensing and safe shutdown.

## Electrical path

Battery positive -> fuse -> main positive contactor -> DC-link positive. A parallel precharge branch contains the precharge contactor and resistor. Battery negative connects through the main negative contactor. The DC-link includes 1,000 uF effective capacitance, local film capacitance, voltage sensing and a controlled discharge path.

## Controller states

| State | Entry condition | Outputs | Exit criteria |
|---|---|---|---|
| OFF | Key off or reset | All contactors open | Valid wake request |
| SELF_TEST | Wake request | Sensor plausibility and driver tests | HVIL closed, isolation valid, voltages plausible |
| NEG_CLOSE | Checks passed | Negative contactor close command | Auxiliary contact confirms closure |
| PRECHARGE | Negative closed | Precharge contactor closed | DC-link >= 90% pack and dV/dt plausible |
| MAIN_CLOSE | Precharge complete | Positive main close command | Auxiliary contact confirms closure |
| RUN | Main contacts confirmed | Precharge open; torque enable permitted | Shutdown request or fault |
| DISCHARGE | Main contacts open | Active discharge enabled | DC-link < 60 V |
| SAFE | Discharge complete | All HV outputs off | New validated wake request |
| FAULT | Critical diagnostic | Torque inhibit; controlled isolation | Service/reset policy satisfied |

## Timing budget

- Sensor plausibility: 20 ms
- Negative contactor confirmation: 50 ms maximum
- Precharge: 0.35 s maximum
- Main positive confirmation: 50 ms maximum
- Precharge release after main confirmation: 20 ms
- DC-link discharge to <60 V: 30 s maximum

## Safety constraints

- Never close the positive main contactor without confirmed negative-contactor closure.
- Never permit torque before both main contacts are confirmed and precharge is open.
- A voltage-ratio decision must be supported by dV/dt plausibility to reduce sensor-bias risk.
- A welded contactor shall be diagnosed by auxiliary-contact and voltage-decay disagreement.
- A critical HVIL or isolation fault commands torque inhibit and controlled HV isolation.

