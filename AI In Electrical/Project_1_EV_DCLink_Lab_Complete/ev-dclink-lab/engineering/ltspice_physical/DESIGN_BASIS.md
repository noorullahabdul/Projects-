# Design Basis and Calculations

## 1. Controlled scope

The model covers a 600–850 V traction-battery interface with negative main,
positive main, precharge, DC-link capacitor bank, voltage sensing, contactor
coil drivers, threshold controller and active/passive discharge.

The verification candidate uses 800 V nominal, 1.0 mF DC-link capacitance and
a 92 ohm precharge resistance. Requirements allocated to this model are:

| ID | Requirement | LTspice evidence |
|---|---|---|
| DCL-SYS-001 | Operate from 600 to 850 V | Corner deck |
| DCL-SYS-003 | Peak precharge current below 10 A | `I_PRE_PEAK` |
| DCL-SYS-004 | Main closure within 350 ms from wake | `T_MAIN_CONTACT` |
| DCL-SYS-005 | Main closure at actual ratio of at least 0.90 | `V_RATIO_CLOSE` |
| DCL-SYS-006 | Diagnose/no-close response to open paths | Fault deck |
| DCL-SYS-007 | Identify welded contact behavior | Fault deck waveforms |
| DCL-SYS-008 | Discharge below 60 V within 5 s | `T_TO_60`, `VDC_5S` |

## 2. Precharge resistor

At the instant the precharge contact closes, the capacitor voltage is zero.
Ignoring the milliohm wiring contribution:

`I0 = VPACK / RPRE`

Nominal: `800 / 92 = 8.70 A`. With the modelled 47 mOhm source/harness
resistance, the expected value is approximately **8.69 A**.

The targeted maximum-inrush corner uses 850 V, 89.24 ohm and 0.9 mF:
`850 / (89.24 + 0.047) = 9.52 A`, retaining analytical margin to 10 A.

Initial resistor power is `P0 = V^2/R = 6.96 kW` nominal. The resistor-bank
selection must therefore use pulse energy and transient thermal impedance,
not continuous wattage alone.

## 3. Charging time and energy

For the first-order approximation:

`VDC(t)/VPACK = 1 - exp(-t/(RPRE*CDC))`

At 93%, `t93 = -RPRE*CDC*ln(0.07)`.

| Condition | R | C | Electrical t93 |
|---|---:|---:|---:|
| Nominal | 92 ohm | 1.0 mF | 244.7 ms |
| Max-inrush corner | 89.24 ohm | 0.9 mF | 213.6 ms |
| Slow-charge corner | 94.76 ohm | 1.1 mF | 277.2 ms |

Controller, coil and armature delays are added by the transient model. The
stored capacitor energy is `0.5*C*V^2`, or **320 J** at 800 V and 1 mF.

## 4. Physical sensing threshold

The pack and DC-link channels use four 2 MOhm resistors and one 39 kOhm
resistor. Their nominal transfer ratio is:

`39k / (8M + 39k) = 0.00485135`

This produces **3.881 V at 800 V**. A separate pack-reference chain uses four
2.151 MOhm resistors and 39 kOhm. Its ratio divided by the DC channel ratio is
**0.93012**, providing the physical 93% threshold without a behavioral voltage
equation. Ten-nanofarad capacitors represent input filtering.

## 5. Contactor dynamics

The main-contactor proxy has a 12 ohm, 80 mH winding at 25 degC. The
precharge-contactor proxy has a 24 ohm, 60 mH winding. Copper resistance uses
`R(T) = R25*(1 + 0.00393*(T-25))` in the corner deck.

The H source converts winding current into an armature-force proxy. An R-C
state network supplies delay, and the contact switch supplies pickup/dropout
hysteresis. This keeps the switch dependent on coil current rather than a
digital command. Default thresholds were selected so the engineering proxy
can pick up at 9 V and hot-winding resistance; these values require bench or
supplier correlation before design release.

## 6. Discharge

With 1 kOhm and 1 mF, `tau = 1.0 s`. The ideal time from 800 V to 60 V is:

`t = R*C*ln(800/60) = 2.590 s`

The discharge command starts 50 ms after key-off, allowing the coil-driven
main contacts to release before the resistor is applied. Hardware must verify
auxiliary-contact status before enabling discharge.

## 7. Assumptions requiring replacement or correlation

- Coil R/L, armature delay, pickup/dropout current and contact bounce.
- Main/precharge contact resistance versus current, temperature and life.
- Contactor economizer strategy over the full 9–36 V supply range.
- MOSFET switching, avalanche and thermal behavior using nominated parts.
- Resistor-bank pulse-energy/thermal model.
- Capacitor-bank distributed ESL/ESR and temperature dependence.
- Isolation-amplifier gain, offset, diagnostic behavior and common-mode
  transient immunity.
- Arc behavior, contact erosion and welded-contact physics.

No model value above should be interpreted as supplier qualification data.

