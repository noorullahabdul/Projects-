SPWM SIC V4 - ROBUST SWITCH-MODEL BUNDLE
=========================================

RUN ORDER
  1. SPWM_V4_CONTROL_TEST.sch
  2. SPWM_SIC_V4_RUN_FIRST.sch
  3. SPWM_SIC_V4_FULL_60ms.sch

SIMULATOR
  ngspice

WHAT CHANGED
  - Removed all six nonlinear behavioural power-current sources.
  - Replaced each phase leg with standard SPICE S switches.
  - Added explicit 1200 V body-diode models.
  - Added 100 pF switch capacitances and DC leakage paths.
  - Added 50 mOhm DC-link capacitor ESR.
  - Changed neutral return from 100 MOhm to 1 MOhm.
  - Power nodes are connected with physical wires.
  - Labels are attached to non-zero wire segments.
  - High-side switching is controlled by PWM logic, not by an algebraic
    floating-gate feedback loop.

EXPECTED FIRST TEST
  SPWM_V4_CONTROL_TEST.sch should produce:
    REF_A / REF_B / REF_C: 50 Hz, 120 degrees apart
    CARRIER: 40 kHz triangular
    PWM outputs: approximately 0 V and 5 V

THEN RUN
  SPWM_SIC_V4_RUN_FIRST.sch for 5 ms.

NOTE
  This is a robust functional SiC inverter model. It is not a detailed
  manufacturer electrothermal macro-model.
