# Insulation, Layout and EMC Rules

1. Creepage and clearance values are not frozen without pollution degree, material group, altitude, working voltage category and applicable product standard. The PCB and mechanical drawings shall reference the approved insulation-coordination calculation.
2. HV and SELV domains shall have explicit keep-out zones, isolation barriers and controlled return paths. No copper, test point or mounting feature may compromise the barrier.
3. High dV/dt switching nodes shall be physically separated from voltage-sense, HVIL and communication circuits. Use differential routing, RC input filtering and shield/return planning where justified.
4. Precharge and discharge current loops shall be short and physically separated from measurement references. Kelvin sensing is required across pulse resistors when current inference is used.
5. Contactor coils require local suppression selected against release-time requirements. Driver ground bounce shall not corrupt safety inputs.
6. DC-link busbar inductance shall be included in inverter switching-overshoot analysis. The contactor assembly shall be reviewed for magnetic force, hot-spot and fault-current withstand.
7. HV measurement dividers require series voltage grading, spacing between elements and open/short diagnostic analysis. Do not rely on a single high-value resistor.
8. Test points on HV nodes shall be guarded and mechanically protected; production test access shall use rated fixtures and interlocks.

