# Prototype Tools and Facilities Plan

## Safety and laboratory infrastructure

- Restricted HV laboratory with interlocked enclosure, emergency stop, remote energization and status beacon.
- Lockout tagout station, insulated barriers, rescue hook, Class C fire protection as approved locally and posted emergency procedure.
- HV-rated PPE selected by the laboratory risk assessment; trained and authorized operators only.
- Insulation mat, touch-safe connectors, keyed HVIL loop, fused source output and independently verified discharge path.
- Battery simulator or bidirectional HV DC source covering at least 0 to 900 V with programmable current limit and emergency isolation.
- Energy-limited commissioning mode using reduced capacitance or lower voltage before full-energy testing.

## Measurement equipment

| Equipment | Minimum capability | Use |
|---|---|---|
| Oscilloscope | 4 or more channels, isolated or approved differential setup, segmented memory | Precharge, bounce, shutdown and faults |
| Differential probes | Rated above 1 kV working voltage and expected transients | Vpack and Vdc |
| Current probe/transducer | At least 20 A peak for precharge with adequate bandwidth | Inrush and discharge current |
| Power analyzer | HV DC input and synchronized current channels | Energy and loss correlation |
| Precision DMM | CAT-rated for setup; independent safe-voltage confirmation | Static voltage and resistance |
| LCR meter/impedance analyzer | Capacitance, ESR and frequency sweep | DC-link bank characterization |
| Thermal camera and thermocouples | Calibrated over expected component temperatures | Resistor, contactor and discharge heating |
| Insulation resistance tester | Voltage appropriate to insulation plan | Pre-energization screening |
| Dielectric withstand tester | Per approved insulation test plan | Qualification only in controlled lab |
| CAN/Ethernet logger | Timestamp accuracy 1 ms or better | State and DTC correlation |
| HIL platform | Analog/digital fault insertion and deterministic real-time execution | Sensor, HVIL, isolation and auxiliary faults |

## Prototype hardware

- 900 V-rated contactors with auxiliary contacts and supplier coil-economizer requirements.
- Pulse-rated precharge resistor bank implementing the CR-004 92 ohm candidate with temperature measurement.
- DC-link capacitor fixture allowing 0.9, 1.0 and 1.1 mF configurations with controlled ESR/ESL.
- Active-discharge switch and pulse-rated resistor assembly with guarded thermal surfaces.
- Isolated voltage-sensing channels with calibration injection points.
- Current observation or validated dV/dt estimator for precharge-short detection.
- Controller board with safe-default gate/contact outputs, watchdog and independently fused low-voltage supply.
- Breakout and fault-insertion box for HVIL, contactor auxiliaries, isolation status and voltage-sensor substitution.

## Software and automation

- LTspice for electrical transient and fault decks.
- MATLAB/Simulink and Simscape for analytical, supervisory and physical models.
- Python for evidence processing, plotting, checksum generation and regression comparison.
- HIL automation using the selected platform API, CAN database and timestamped result capture.
- Configuration management for schematics, model files, calibration, software build, test procedure and raw evidence.

## Prototype maturity sequence

1. Offline schematic review, FMEA and component SOA confirmation.
2. Reduced-voltage and reduced-energy bench bring-up.
3. Full-voltage precharge with current-limited source and open inverter load.
4. Discharge and fault tests inside interlocked enclosure.
5. HIL closed-loop state and diagnostic testing.
6. OBC, inverter, BMS and VCU integration using controlled HV ownership.
7. Thermal, EMC and environmental verification on representative hardware.

## Procurement evidence required

- Supplier datasheets and revision-controlled part numbers.
- Contactor voltage, current, make/break, coil, economizer and auxiliary-contact ratings.
- Resistor pulse-energy curve, transient thermal impedance, insulation and repetition limits.
- Capacitor voltage derating, capacitance tolerance, ESR, ripple-current, temperature and life model.
- Isolation component certificates and creepage/clearance data.
- Calibration certificates for safety-critical measurement equipment.
