# Traction Inverter and E-Axle Controller

## Objective

Create a reduced-order 150 kW traction-inverter/e-axle study covering the torque-speed envelope, electrical current, modulation utilization, inverter loss, mechanical output, regenerative operation, derating, and protection sequencing.

## My role

System architecture, operating-envelope definition, control/protection requirements, analytical plant model, automated sweep, fault injection, and evidence reporting.

## Baseline assumptions

- DC bus: 600–850 V; nominal 800 V
- Peak mechanical output: 150 kW
- Base speed: 4,000 rpm; maximum speed: 12,000 rpm
- Peak torque: 360 N·m
- Switching frequency: 10 kHz
- Motor efficiency: operating-point approximation
- Inverter efficiency target: ≥96% at medium/high load

## Automation sequence

1. Sweep DC voltage, speed, torque command, temperature, and dead time.
2. Apply torque-speed envelope and temperature-based derating.
3. Calculate mechanical power, estimated DC current, modulation proxy, loss, and efficiency.
4. Check overcurrent, overspeed, overtemperature, bus limits, and dead-time bounds.
5. Inject sensor, phase-loss, and protection faults; confirm torque inhibition or controlled derating.

## Status

Independent model-based portfolio study. It is not a fabricated or production-released e-axle.

