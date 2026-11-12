# Primary technical references

Checked 10 November 2026. The implementation and derivations are original;
these references establish the underlying conventions, not the chosen
demonstration component values.

1. Texas Instruments, Basic Calculation of a Buck Converter's Power Stage,
   SLVA477. CCM sizing and ripple relations:
   https://www.ti.com/lit/an/slva477/slva477.pdf
2. Texas Instruments, Hong Huang, Designing an LLC Resonant Half-Bridge
   Power Converter, SLUP263. FHA equivalent network and reflected load:
   https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/196/3225.slup263.pdf
3. MathWorks, PMSM documentation. dq voltage/torque conventions and surface
   permanent-magnet machine assumptions:
   https://www.mathworks.com/help/simscape-electrical/ref/pmsm.html

The code's LLC primary uses full-bridge excitation. The TI paper's half-bridge
excitation factor is not copied into that full-bridge gain conversion.
No manufacturer datasheet is asserted to validate the default switch,
motor, magnetics, thermal, or switching-energy values.
