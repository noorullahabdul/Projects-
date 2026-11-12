# LTspice Run Guide - Gate 3 Rev B

## Correct evidence status

The delivered `.cir` files are prepared simulation inputs. They are not counted as passing evidence until they are executed in a recorded LTspice version and the `.log`, `.raw`, measurements and screenshots are archived and reviewed.

## Files

- `dclink_gate2_parasitic.cir`: 81 nominal/corner transient combinations with source, harness, contactor and capacitor parasitics.
- `dclink_gate3_faults.cir`: nominal plus precharge-open, precharge-short, welded-positive, discharge-open, high-ESR and high-source-impedance conditions.

## Acceptance review

- `I_PRE_PEAK <= 10 A`
- `V_RATIO_MAIN >= 0.90`
- Precharge threshold reached within `350 ms`
- Active discharge reaches `60 V` within the 5 s design target
- No undefined `.meas` result may be treated as PASS
- Review resistor peak power and absorbed energy against the selected supplier pulse SOA

## Recommended model

Open `dclink_gate2_parasitic.cir` directly in LTspice and select **Run**. The file is a complete SPICE netlist and does not require a custom symbol library.

The model includes:

- 600/800/850 V pack stepping
- 900/1,000/1,100 uF capacitance stepping
- 90/100/110 ohm precharge-resistance stepping
- Source resistance and bus inductance
- Capacitor ESR and ESL
- Precharge-contact bounce
- Main-contactor sequencing
- 1 kohm active-discharge branch
- Measurements for peak precharge current, voltage ratio, discharge time and resistor energy

## Expected plots

Plot `V(dc)`, `I(Rpre)` and `I(Ractive)`. Review the SPICE error log for `.meas` results.

## Local validation checklist

1. Confirm all 27 parameter combinations converge.
2. Confirm peak precharge current remains below 10 A.
3. Confirm `V(dc)/VPACK` exceeds 0.90 before main closure.
4. Confirm active discharge reduces `V(dc)` below 60 V within 5 s.
5. Replace generic switches with shortlisted supplier models and rerun.
6. Add measured busbar inductance, capacitor ESR/ESL and contactor resistance after prototype characterization.

An `.asc` file is not required to execute this netlist. If a graphical schematic is desired, create a new schematic in LTspice, place the equivalent elements, and retain this `.cir` file as the regression reference.

