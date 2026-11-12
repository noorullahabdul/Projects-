# 800 V DC Link Design Calculations and Assumptions

## Scope and controlled status

This calculation record supports the CR-004 verification candidate. It is not a production release. Analytical results have been executed; LTspice, MATLAB, Simulink, Simscape, HIL and prototype evidence require local execution and approval.

## Electrical operating envelope

| Parameter | Minimum | Nominal | Maximum | Basis |
|---|---:|---:|---:|---|
| Battery voltage | 600 V | 800 V | 850 V | Vehicle HV operating range |
| Effective DC-link capacitance | 0.90 mF | 1.00 mF | 1.10 mF | Tolerance, bias, ageing and temperature allocation |
| Precharge resistor at 25 C | 89.24 ohm | 92 ohm | 94.76 ohm | 92 ohm +/-3 percent candidate |
| Resistor TCR | - | 100 ppm/C | 100 ppm/C | Low-TCR pulse resistor-bank target |
| Source plus harness resistance | 25 mohm | 47 mohm | 150 mohm | Pack, busbar, fuse and harness allocation |
| Contactor path resistance | - | 0.85 mohm | - | Model-equivalent conduction path |
| Voltage channel error | -1.5 percent | 0 | +1.5 percent | Independent pack and DC-link channels |
| Command-processing latency | 0 ms | 2.5 ms | 5 ms | Software, filtering and task timing budget |
| Active discharge resistance | 900 ohm | 1 kohm | 1.1 kohm | Tolerance and temperature envelope |

## Precharge equations

For a first-order RC approximation:

`Vdc(t) = Vpack x (1 - exp(-t/(Rtotal x Cdc)))`

`Ipre(0) = Vpack / Rtotal`

`t = latency - Rtotal x Cdc x ln(1 - Vdc/Vpack)`

`Ecap = 0.5 x Cdc x Vpack^2`

`Presistor(0) = Ipre(0)^2 x Rpre`

With opposing sensor errors, actual voltage ratio at a measured 93 percent threshold is:

`actual ratio = 0.93 x (1 + pack-channel error) / (1 + link-channel error)`

## Key worst-case results

- Highest inrush: 850 V, minimum cold resistance and minimum source resistance. Analytical maximum is 9.584 A against the 10 A limit.
- Slowest precharge: maximum hot resistance, 1.10 mF, high source resistance, worst high actual closure ratio and 5 ms latency. Analytical maximum is 339.424 ms against 350 ms.
- Lowest actual closure ratio: pack channel -1.5 percent and DC-link channel +1.5 percent. Result is 90.251 percent against 90 percent.
- Maximum stored energy: `0.5 x 1.10 mF x 850^2 = 397.4 J`.
- Nominal resistor initial pulse at 850 V and 92 ohm is approximately 7.85 kW. Supplier pulse-energy and transient thermal impedance must be verified; continuous-power rating alone is not sufficient.

## Active discharge

`Vdc(t) = V0 x exp(-t/(Rdis x Cdc))`

`t60 = Rdis x Cdc x ln(V0/60)`

Worst analytical corner uses 850 V, 1.10 mF, 1.10 kohm and high-temperature resistance correction. Result is 3.336 s against the 5 s portfolio design target and 30 s system requirement.

Initial discharge power at 850 V and 900 ohm is 803 W. The selected implementation must be verified against pulse power, junction temperature, resistor surface temperature, repetition rate and fault-on duration.

## Contactor assumptions

- Main and precharge contactors are represented by generic controlled switches with milliohm conduction resistance.
- Coil pickup, dropout, economizer behavior, stochastic bounce, contact erosion and arc energy are not supplier-qualified in the model.
- Auxiliary feedback is assumed independently sensed and debounced.
- Positive and negative contactors require independent weld and open-load diagnostics.

## Sensing assumptions

- Pack and DC-link channels are independently isolated or independently plausible.
- Total channel accuracy allocation is +/-1.5 percent over voltage, temperature, ageing and ADC reference tolerance.
- Range, correlation, rate-of-change, stuck and command-response diagnostics are required.
- Common-cause reference and isolation failures require safety analysis beyond this calculation.

## Thermal and insulation assumptions

- Ambient range is -40 C to 105 C for component-corner analysis; actual enclosure air and coolant conditions must be defined at vehicle level.
- Creepage, clearance, dielectric withstand and partial-discharge requirements depend on pollution degree, material group, altitude and working-voltage waveform.
- The portfolio model does not constitute IEC 60664, ISO 6469 or OEM insulation approval.

## Decision

CR-004 is analytically feasible with limited margin. It can proceed to LTspice/MATLAB execution and prototype planning, but it cannot be approved until pulse-resistor SOA, contactor behavior, sensing accuracy, thermal performance and integration tests are correlated with physical evidence.
