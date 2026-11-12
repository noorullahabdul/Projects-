# Component-Level LTspice Model — 800 V DC Link

Model ID: **EV-DCL-LTS-005**  
Revision: **A**  
Evidence status: **prepared model; local LTspice execution and review required**

## What changed from the earlier model

This replacement removes the command-driven `R=if(...)` contactors and the
behavioral command sources from the nominal power/control path.

- Main and precharge contactors contain explicit **R-L coils**.
- Each coil is energized by a **60 V VDMOS low-side driver**, gate resistor,
  pulldown and Vgs clamp.
- Coil flyback paths are explicit.
- Contact pickup and dropout depend on **simulated coil current**, armature
  delay and hysteresis.
- Main and auxiliary contacts are separate switching elements.
- The 93% close threshold uses independent high-voltage resistor dividers and
  a **transistor-level differential comparator**.
- Precharge delay and approximately 350 ms timeout use physical RC networks.
- The positive-main auxiliary contact actively removes the precharge command.
- Active discharge uses a floating 15 V drive rail, optocoupler proxy,
  1200 V VDMOS and 1 kOhm resistor.
- Fault switches are confined to the fault-injection deck.

## Start here

1. Keep all files together in one local folder with a short path.
2. Open `DCLINK_PHYSICAL_NOMINAL.cir` in LTspice XVII or LTspice 24.x.
3. Select **Simulate > Run**.
4. Plot:
   - `V(HVP_BUS)` and `V(DCPLUS,DCMINUS)`
   - `I(RPRE_PATH)`
   - `V(NEG_MECH)`, `V(PRE_MECH)`, `V(POS_MECH)`
   - `V(PRE_GATE)`, `V(POS_GATE)` and `V(DIS_GATE,DCMINUS)`
   - `V(NEG_AUX)`, `V(POS_AUX)` and `V(RUN_OK)`
   - `I(RNEG_COIL_FAULT)`, `I(RPRE_COIL_FAULT)` and
     `I(RPOS_COIL_FAULT)`
5. Open **View > SPICE Error Log** and record every `.meas` result.
6. Run the corner deck, then the fault deck.

Windows users can run all three decks with `run_all_ltspice.bat`. Set
`LTSPICE_EXE` inside that file if LTspice is installed somewhere else.

## Files

| File | Purpose |
|---|---|
| `DCLINK_PHYSICAL_NOMINAL.cir` | Nominal 6 s transient and measurements |
| `DCLINK_PHYSICAL_CORNERS.cir` | Twelve targeted electrical, temperature and sensing corners |
| `DCLINK_PHYSICAL_FAULTS.cir` | Ten nominal/fault cases |
| `DCLINK_PHYSICAL_PLANT.inc` | Complete plant, drivers, sensing and controller interconnect |
| `DCLINK_PHYSICAL_MODELS.lib` | Contactors, semiconductors, comparator and discharge subcircuits |
| `DCLINK_PHYSICAL_OVERVIEW.asc` | Graphical LTspice architecture/run wrapper |
| `DESIGN_BASIS.md` | Calculations, assumptions and replacement rules |
| `component_parameter_map.csv` | Parameter provenance and confidence |
| `acceptance_matrix.csv` | Objective limits and expected fault response |
| `MODEL_REPLACEMENT_GUIDE.md` | How to replace proxy devices with supplier models |
| `validate_physical_package.py` | Static completeness and anti-behavioral-model checks |
| `parse_ltspice_log.py` | Converts stepped `.meas` output to CSV |

## Nominal expectation before correlation

- Initial precharge current: approximately **8.69 A** at 800 V.
- Ideal electrical time to 93% after precharge contact closure:
  approximately **244.7 ms**.
- Positive main contact closure: expected around **0.28–0.31 s**, including
  coil and armature delay.
- Precharge-resistor deposited energy: approximately **320 J** at 800 V and
  1 mF, excluding losses elsewhere.
- Active-discharge time from 800 V to 60 V: approximately **2.59 s** after
  the delayed discharge command.

These are analytical expectations, not claimed LTspice results. The package
contains no fabricated `.raw` file or fabricated pass report.

## Important engineering boundary

SPICE cannot represent a moving electromechanical contact without some
electrical/mechanical boundary element. The `S` primitive is used only for
that boundary. It is **not driven by the controller**; it is driven by the
coil-current/armature state. Coil resistance, inductance, pickup threshold,
dropout threshold, armature delay and contact resistance remain proxy values
until measured or replaced by supplier-correlated data.

The model is suitable for design exploration, timing allocation and portfolio
evidence. It is not a released automotive design, contactor qualification,
ASIL work product, vehicle-energization authority or production validation.

