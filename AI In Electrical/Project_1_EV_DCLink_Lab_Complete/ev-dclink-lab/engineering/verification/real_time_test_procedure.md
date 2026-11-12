# 800 V DC Link Real Time Verification Procedure

## Purpose

This procedure defines MIL, HIL and prototype integration tests for the precharge, contactor, sensing and discharge subsystem. Testing on energized HV hardware may be performed only in an approved HV laboratory by trained personnel using a reviewed risk assessment, interlocked enclosure, remote operation and emergency isolation.

## Entry criteria

- Requirements, schematics, software build, calibration set and test-item serial number are baselined.
- DFMEA actions affecting personnel safety are closed or formally accepted.
- HV laboratory risk assessment, lockout tagout, emergency response and discharge verification are approved.
- Instrument calibration is current and measurement uncertainty is recorded.
- Current-limited source or battery simulator limits are independently verified before connecting the DUT.
- Contactor outputs default de-energized during controller reset and cable disconnection.

## Instrumentation and logging

- Isolated differential voltage probes rated above maximum transient voltage.
- HV current transducer or current probe with adequate peak and bandwidth rating.
- Four-channel or higher isolated oscilloscope with single-shot segmented capture.
- CAN or Ethernet logger synchronized to oscilloscope time within 1 ms.
- Temperature measurement on resistor bank, contactors, discharge element and capacitor terminals.
- HIL fault-injection interface for HVIL, isolation status, auxiliary contacts, voltage channels and controller reset.
- Minimum logged channels: Vpack, Vdc, Ipre, positive and negative contactor commands, precharge command, auxiliary contacts, discharge command, torque enable, state, DTC, controller supply and temperatures.

## Test execution sequence

1. Identify the test case, software/calibration version, operator, equipment IDs and environmental condition.
2. Confirm the DC link is below 60 V with an independent meter before access or reconfiguration.
3. Configure source voltage and current limit with DUT disconnected.
4. Connect the DUT inside the interlocked enclosure; perform continuity, insulation and polarity checks.
5. Arm synchronized waveform and bus logging before wake command.
6. Execute one nominal sequence at reduced energy, then the required corner or fault condition.
7. Verify safe-state outputs immediately after each fault or shutdown.
8. Confirm discharge below 60 V using both DUT sensing and an independent instrument.
9. Save raw waveform, decoded communication log, parameter file, photographs and operator observations.
10. Classify PASS, FAIL, BLOCKED or INVALID. Never rerun over a failure without preserving the original evidence.

## Worst case scenario matrix

| Scenario | Controlled condition | Measurements | Acceptance |
|---|---|---|---|
| WC-01 Maximum inrush | 850 V, cold minimum Rpre, minimum source resistance, minimum C | Ipre peak, dI/dt, contact bounce | Ipre <=10 A; no weld or fuse operation |
| WC-02 Slowest precharge | Maximum Rpre hot, 1.10 mF, high source resistance, adverse sensor errors, 5 ms latency | Vdc/Vpack and command time | Actual ratio >=90 percent and command <=350 ms |
| WC-03 Maximum resistor pulse | 850 V, maximum capacitance, repeated key cycles at minimum soak interval | Energy, pulse power and resistor temperature | Within supplier SOA and temperature limit |
| WC-04 Maximum discharge time | 850 V, 1.10 mF, maximum hot Rdis | Vdc decay and time to 60 V | <=5 s design target; <30 s requirement |
| WC-05 Maximum discharge heating | 850 V, minimum Rdis, repeated shutdown | Initial power and temperature | Within switch/resistor SOA |
| WC-06 Sensor adverse tolerance | Opposing pack and link errors at limits | Actual and measured ratio | No closure below 90 percent actual ratio |
| WC-07 Contactor low coil voltage | Minimum LV supply and hot coil | Pickup time, chatter and aux feedback | Reliable pickup or controlled abort; no torque enable |
| WC-08 Contactor high coil voltage | Maximum LV supply and cold coil | Coil current and driver temperature | Within driver/coil limits |
| WC-09 Controller brownout | Supply ramp/drop during each active state | Commands, reset, state and recovery | Outputs de-energize safely; no automatic torque enable |
| WC-10 EMC disturbance | Applicable transient while in PRECHARGE and RUN | Commands, DTC and recovery | No unsafe contactor or torque command |

## Fault injection scenarios

| Scenario | Injection | Required response |
|---|---|---|
| FI-01 | Precharge branch open | Timeout, latched DTC and safe outputs |
| FI-02 | Precharge branch short or current-estimator excess | Abort within 20 ms after criterion; main closure inhibited |
| FI-03 | Positive contactor fails open | Auxiliary timeout and no torque enable |
| FI-04 | Positive contactor welded | Command/aux/voltage disagreement detected; discharge strategy applied |
| FI-05 | Negative contactor fails or welds | Correct DTC and safe isolation strategy |
| FI-06 | HVIL opens in each energized state | Torque inhibit and contactor opening within allocated FTTI |
| FI-07 | Isolation status invalid/stale | Activation inhibited or controlled shutdown |
| FI-08 | Vpack or Vdc bias, stuck, open or short | Range/correlation/rate diagnostic; unsafe closure inhibited |
| FI-09 | Active discharge open | Decay diagnostic and service warning |
| FI-10 | Auxiliary contact chatter | Debounce; sequence abort if persistent; no output oscillation |
| FI-11 | CAN command loss | Torque inhibit and deterministic communication-timeout response |
| FI-12 | Controller reset during RUN | Hardware-default safe outputs and controlled recovery requiring new authorization |

## Integration scenarios

| Scenario | Interfaces involved | Verification focus |
|---|---|---|
| INT-01 Vehicle wake to ready | VCU, BMS, insulation monitor, contactor controller, inverter | Message order, validity, timeout, state progression and torque authorization |
| INT-02 OBC connected | OBC, BMS, VCU and DC link | Mutual HV ownership, precharge source selection and no conflicting contactor commands |
| INT-03 Traction inverter start | DC link, inverter, resolver/control and VCU | Bus-ready handshake, torque inhibit until RUN and DC-bus stability |
| INT-04 Regenerative overvoltage | Inverter, BMS and DC link | Overvoltage request handling, contactor strategy and safe torque reduction |
| INT-05 Crash shutdown | Restraint/crash signal, VCU, inverter and contactors | Immediate torque inhibit, HV isolation, discharge and event logging |
| INT-06 Service disconnect/HVIL | HV connector loop, BMS, VCU and inverter | FTTI, arc-prevention sequence and restart interlock |
| INT-07 Sleep and parked discharge | VCU, contactor controller and low-voltage power management | Quiescent current, false wake prevention and touch-safe decay |
| INT-08 Communication dropout | CAN/Ethernet gateways and all HV nodes | Timeout ownership, stale-data rejection and recovery without unintended energization |

## Pass fail and evidence rules

- A prepared model or test script is not a PASS result.
- Every result must link to requirement ID, test ID, configuration, raw evidence and reviewer.
- Failed first-run evidence must be retained with the problem report and corrective-action link.
- Integration PASS requires synchronized network and physical measurements; a CAN log alone is insufficient.
- Gate closure requires independent review and signed deviation records for every open item.
