# 30 kW OBC — PFC and LLC Converter

## Objective

Develop a reproducible, reduced-order design study for a three-phase 30 kW onboard charger. The study checks front-end current, DC-link current, LLC resonant-tank sizing, estimated ZVS margin, output ripple, device stress, and efficiency over a defined operating envelope.

## My role

Power-architecture definition, first-pass component sizing, operating-envelope definition, automated sweep development, limit checking, and technical documentation.

## Baseline assumptions

- AC input: 360–440 V line-to-line, three phase
- Output: 500–800 V DC
- Rated output: 30 kW
- PFC efficiency assumption: 98%
- LLC nominal efficiency assumption: 97.5%
- LLC switching frequency: 80–160 kHz; nominal 120 kHz
- Resonant inductance: 25 µH; resonant capacitance: 70 nF
- Output ripple target: ≤ 2% of output voltage

## Automation sequence

1. Generate combinations of AC voltage, battery voltage, output power, switching frequency, dead time, and resonant-component tolerance.
2. Calculate AC RMS current, DC output current, resonant frequency, normalized frequency, estimated efficiency and ripple.
3. Apply deterministic pass/fail limits for current, frequency range, ripple, efficiency, and ZVS proxy margin.
4. Export all operating points and a compact summary to `results/`.

## Deliverables

- `docs/requirements.md` — requirements and verification matrix
- `simulation/obc_llc_reduced.cir` — generic SPICE starter circuit
- `automation/run_obc_sweep.py` — automated corner sweep
- `results/` — generated CSV evidence

## Status

Independent analytical/simulation portfolio model. Not fabricated or production released.

