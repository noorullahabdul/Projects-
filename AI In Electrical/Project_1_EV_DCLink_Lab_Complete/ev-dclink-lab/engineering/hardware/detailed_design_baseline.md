# 800 V DC-Link Detailed Design Baseline

## Frozen design inputs

| Parameter | Minimum | Nominal | Maximum |
|---|---:|---:|---:|
| Pack voltage | 600 V | 800 V | 850 V |
| Effective DC-link capacitance | 900 uF | 1,000 uF | 1,100 uF |
| Precharge resistance | 90.25 ohm | 95 ohm | 99.75 ohm |
| Active discharge resistance | 900 ohm | 1,000 ohm | 1,100 ohm |
| Passive monitor/bleeder resistance | 90 kohm | 100 kohm | 110 kohm |
| Traction power used for interface rating | - | 150 kW | - |

## Precharge network

At the worst current corner, 850 V and 90.25 ohm produce 9.42 A, meeting the 10 A requirement. Gate 3 changed the nominal selection to 95 ohm +/-5% because the earlier 110 ohm upper allocation did not retain enough timing margin with the sensor-error-compensated 93% command threshold.

The capacitor stores 397 J at the maximum 850 V and 1,100 uF corner. The resistor bank shall therefore be rated by pulse-energy SOA, not only average wattage. Its initial instantaneous power reaches approximately 8.01 kW at 850 V and 90.25 ohm. The sourcing specification requires at least 500 J single-pulse capability at the defined starting temperature and three consecutive precharge attempts with an approved cooldown model.

## Active discharge redesign

The earlier 10 kohm concept could miss the 30 s touch-safe requirement at tolerance. Gate 2 uses a switched 1 kohm nominal active-discharge branch plus a 100 kohm monitoring/bleeder branch.

- Maximum active-discharge time from 850 V to 60 V at 1,100 ohm and 1,100 uF: 3.21 s.
- Maximum initial active-discharge power at 850 V and 900 ohm: 803 W.
- Maximum energy to absorb: 397 J.
- The switch and resistor bank require voltage grading, pulse SOA, temperature sensing or a validated thermal model, and open-circuit diagnostics.
- The passive 100 kohm path is not credited for the 5 s safety goal; it provides a diagnostic/backup decay path only.

## Main current path

At 150 kW, ideal DC current is 250 A at 600 V and 176 A at 850 V. Allowing overload, ripple, coolant/ambient variation and ageing, Gate 2 defines a preliminary continuous-current requirement of 300 A and a short-duration requirement of 450 A for 10 s. Final values must be aligned with the motor/inverter peak-power profile.

Each main contactor requires:

- 1,000 VDC minimum working rating, subject to system transient specification.
- 300 A continuous carry at the validated thermal condition.
- 450 A for 10 s minimum overload capability.
- Bidirectional make/break capability appropriate to battery and inverter faults.
- Auxiliary contact feedback, coil suppression and driver current diagnostics.
- Published electrical/endurance life for the specified load profile.

## DC-link capacitor interface

The inverter-owned capacitor bank shall demonstrate:

- 1,000 uF nominal effective capacitance after tolerance, voltage, temperature and ageing effects.
- Voltage rating and transient margin consistent with the 850 V pack and overshoot specification.
- Ripple-current capability derived from inverter modulation and motor operating points.
- ESR/ESL and busbar inductance included in switching-overshoot verification.
- Discharge, venting and failure-mode integration with the enclosure safety concept.

## Voltage sensing

Two independent safety-relevant observations are required: pack voltage and DC-link voltage. The design uses separated divider networks and isolated/qualified acquisition paths. Software evaluates range, cross-ratio, stuck, rate-of-change and command/response plausibility. A single biased DC-link channel shall not be sufficient to authorize main-contactor closure.

Preliminary measurement requirements:

- Input range: 0–1,000 VDC.
- Total error: <=1.5% over voltage, temperature and lifetime.
- Update period: <=1 ms during precharge.
- Isolation and creepage/clearance: allocated by the product insulation-coordination plan.
- Diagnostic coverage: open, short, stuck, offset and excessive noise.

## Gate 2 limitations

This baseline establishes design requirements and calculations. Final part numbers, PCB creepage/clearance, busbar geometry, fuse coordination, enclosure, thermal correlation and supplier PPAP remain open until mechanical, environmental and sourcing inputs are frozen.

