# Supplier-Model Replacement Guide

The delivered netlists run without external libraries. For a correlation-grade
model, preserve the top-level net names and replace the proxies in this order.

## 1. Main contactors

Replace `EV200_COIL_CONTACTOR` only after obtaining coil current, economizer
behavior, pickup/dropout limits, operate/release distributions and contact
resistance from the selected part/supplier. The current reference is an
EV200-class SPST-NO contactor because the public TE product family covers
500 A, 12–900 VDC contacts and a 9–36 VDC coil. The delivered subcircuit is
not a TE model.

Keep the seven-pin interface:

`HV_IN HV_OUT COIL+ COIL- AUX_IN AUX_OUT MECH_STATE`

If no mechanical state pin exists in the supplier macro-model, expose an
auxiliary-contact voltage as the state used by measurements.

## 2. Coil drivers

`COIL_LOW_SIDE_DRIVER` uses a generic 60 V VDMOS. Replace it with the selected
automotive protected low-side-switch model and add its diagnostic interface.
Infineon TLE6220GP/FLEX-class devices are implementation references for relay
and solenoid drive; component suitability, current capability and lifecycle
must be confirmed for the final winding and architecture.

## 3. Comparator and sensing

Replace `DISCRETE_COMPARATOR` with the selected automotive comparator model.
Then add the real isolation amplifier or isolated ADC transfer function,
reference tolerance, input protection, leakage, diagnostic pull networks and
ADC quantization. Keep the independent pack and DC-link channels.

## 4. Active discharge

Replace `SIC1200_DISCHARGE` with a vendor 1200 V SiC MOSFET model. Replace the
optocoupler proxy with the isolated gate-driver model, including UVLO,
propagation delay, Miller clamp, desaturation/protection if applicable and
isolated-bias startup/shutdown.

## 5. Model correlation record

For every replacement, record:

- supplier and exact ordering code;
- model filename, revision, checksum and license;
- datasheet revision and operating limits;
- parameters changed and engineering justification;
- waveform comparison against a bench measurement;
- reviewer, date and open deviations.

