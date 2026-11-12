SPWM SIC V3 WORKING QUCS-S BUNDLE
=================================

RECOMMENDED ORDER
  1. SPWM_CONTROL_V3_TEST.sch
  2. SPWM_SIC_V3_WORKING_RUN_FIRST.sch
  3. SPWM_SIC_V3_FULL_60ms.sch

SIMULATOR
  ngspice

FIXES APPLIED
  1. Removed unsupported conditional functions.
  2. Uses smooth tanh() logic.
  3. Every B-voltage source has its own ground.
  4. No source ground wire crosses another source terminal.
  5. Every important node uses an explicit zero-length NAME label.
  6. DC_POS, DC_NEG, VPOLE_A/B/C and filter nodes are explicitly named.
  7. Behavioural SiC current-source polarity was corrected.
  8. Body-diode action uses a smooth positive-part expression.

OPEN
  First open SPWM_CONTROL_V3_TEST.sch and press F2.
  Then open SPWM_SIC_V3_WORKING_RUN_FIRST.sch and press F2.

EXPECTED CONTROL NETLIST
  BREF_A VREF_A 0 ...
  BREF_B VREF_B 0 ...
  BPWM_AH PWM_AH 0 ...
  BPWM_AL PWM_AL 0 ...
  BGH_A GH_A 0 ...

The generated netlist should not contain chained lines such as:
  BREF_A VREF_A VREF_B
  BPWM_AH PWM_AH PWM_AL

The note "No compatibility mode selected!" is informational.
