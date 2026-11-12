# Superseded Behavioral LTspice Model for the 800 V DC Link

> **Do not use this folder for the component-level portfolio release.** It is
> retained only for comparison and regression. Use `../ltspice_physical/`,
> which contains coil-driven contactors, MOSFET drivers, physical sensing and
> a transistor-level controller. No Gate 3 claim should be based on this
> superseded folder.

## Delivered model files

- `DCLINK_CR004_SYSTEM.asc` - editable graphical system schematic with automatic threshold-based main-contactor command.
- `DCLINK_CR004_NOMINAL.cir` - nominal closed-loop simulation deck.
- `DCLINK_CR004_CORNERS.cir` - 324-run deterministic corner sweep.
- `DCLINK_CR004_FAULTS.cir` - nominal plus nine electrical and sensing fault configurations.
- `DCLINK_CR004_MANUAL_DEBUG.asc` - manual command-source worksheet for debugging.
- `run_all_ltspice.bat` - Windows batch execution helper.
- `parse_ltspice_log.py` - extracts `.meas` rows into CSV.
- `acceptance_matrix.csv` - objective pass/fail criteria.

## Modelled functions

- 600 to 850 V floating battery source
- positive and negative main contactors
- 92 ohm +/-3 percent low-TCR precharge bank
- pack/harness resistance and inductance
- 0.9 to 1.1 mF DC-link bank with ESR and ESL
- pack and DC-link sensor gain error
- automatic closure at 93 percent measured ratio
- active and passive discharge
- open, short, welded, fails-open, sensor-bias and high-ESR faults
- objective `.meas` statements for current, timing, ratio, energy and discharge

## First run

1. Extract the package to a local folder with a short path.
2. Open `DCLINK_CR004_SYSTEM.asc` in LTspice.
3. Select **Simulate > Run**.
4. Plot `V(HVP)`, `V(DCPLUS)`, `I(RPRE)`, `V(PRE_CMD)`, `V(POS_CMD)` and `V(DIS_CMD)`.
5. Open **View > SPICE Error Log** and review every `.meas` result.
6. Run the nominal `.cir` deck before the corner and fault campaigns.

## Expected nominal behaviour

- Negative main contactor closes at 2 ms.
- Precharge begins at 12 ms.
- Positive main command asserts when measured Vdc reaches 93 percent of measured pack voltage.
- Precharge path opens when the positive command asserts.
- Both main paths open at 1 s.
- Active discharge starts at 1.002 s.
- Initial precharge current must remain below 10 A.
- Actual voltage ratio at main closure must remain at least 90 percent.
- Main closure must occur within 350 ms from wake for the controlled corner allocation.
- DC link must fall below 60 V within 5 s after the discharge command.

## Corner campaign

`DCLINK_CR004_CORNERS.cir` executes 972 combinations:

- pack voltage: 600, 800 and 850 V
- capacitance: 0.9, 1.0 and 1.1 mF
- precharge resistance: 89.24, 92 and 94.76 ohm at 25 C
- temperature: -40, 25 and 105 C
- pack sensor error: -1.5 and +1.5 percent
- DC-link sensor error: -1.5 and +1.5 percent
- total pack and harness resistance: 25, 47 and 150 milliohm

The simulation log may be large. Parse it using:

`python parse_ltspice_log.py DCLINK_CR004_CORNERS.log corner_results.csv`

## Fault campaign

| Fault value | Condition |
|---:|---|
| 0 | Nominal |
| 1 | Precharge open |
| 2 | Precharge short |
| 3 | Positive main welded |
| 4 | Active discharge open |
| 5 | Positive main fails open |
| 6 | Negative main fails open |
| 7 | DC-link sensor +15 percent bias |
| 8 | DC-link sensor -15 percent bias |
| 9 | Capacitor ESR increased to 80 milliohm |

Some `.meas` statements are expected to be undefined for faults that intentionally prevent a transition. An undefined result must be reviewed against the expected fault response and must not be automatically marked PASS.

## Important limitations

- Contactors use behavioral on/off resistance. Coil pickup, economizer, stochastic bounce, arc energy and wear require supplier models or bench correlation.
- The resistor bank uses electrical pulse energy; thermal impedance and case temperature require the selected supplier data.
- The capacitor bank is a lumped equivalent. Distributed busbar and inverter parasitics require measured correlation.
- Prepared model files are not executed evidence until LTspice version, logs, raw files, screenshots and hashes are archived and reviewed.
