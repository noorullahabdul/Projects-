# Models, conventions, and limitations

## Buck design and losses

Duty is solved from the DC volt-second balance including inductor DCR and
the two duty-weighted MOSFET resistances. CCM inductor ripple is estimated
from on-state voltage and switching period. Triangular ripple contributes
ΔI²/12 to mean-square current.

Losses include both switch conduction paths, inductor copper, hard-switching
overlap, two deadtime intervals, two gate charges, output-capacitor ESR, and
an explicitly allocated core loss. Junction temperatures use a lumped
thermal resistance. Reverse recovery, nonlinear capacitance, frequency-dependent
magnetics, layout parasitics and temperature-dependent Rds(on) are not modelled.
CCM-invalid points are flagged.

## Averaged buck transient

States are inductor current, ideal-capacitor voltage and PI integrator.
For a resistive load R:

    Vout = (Vcap + ESR × IL) / (1 + ESR/R)
    dIL/dt = (D × Vin − Vout − IL × Rseries(D)) / L
    dVcap/dt = (IL − Vout/R) / C
    D = clamp(Vtarget/Vin + Kp × error + integral, 0, 0.95)
    d(integral)/dt = Ki × error, except during outward saturation

Classical fourth-order Runge–Kutta integrates each interval. The default
10 us step is bounded relative to the LC time constant. The load changes at
20 ms from 50% to 100% of nominal power, represented as resistance at target
voltage. It is not a constant-power load model.

PI gains are demonstration values. The model omits PWM/ADC delay and does not
establish a physical compensation design. Numerical convergence is tested.
The separately generated native SPICE deck uses fixed PWM and ideal switches;
it is not the Python controller translated into SPICE.

## Traction inverter

The surface-PMSM convention uses peak dq currents, id = 0, equal d/q
inductance, electrical speed = pole pairs × mechanical speed:

    Torque = 1.5 × pole_pairs × flux × iq
    vd = −electrical_speed × L × iq
    vq = Rs × iq + electrical_speed × flux
    phase_RMS_current = abs(iq) / sqrt(2)

Required phase peak voltage is compared with 95% of Vdc/sqrt(3).
Points outside this range are flagged; no field-weakening result is fabricated.
Torque is clamped to the torque/power envelope and linearly derated between
the configured temperature thresholds.

    Pdc = Pmechanical + motor_copper + allocated_motor_core + inverter_losses

Positive Pdc means power drawn from the battery. Negative Pdc means net
regeneration. A braking command does not imply battery charging if losses
exceed mechanical recovery. Standstill efficiency is left undefined.

Switching loss scales six-device reference switching energy with mean
absolute sine current and bus voltage. The core-loss curve, reference energy,
electrical parameters and thermal resistance are explicit screening assumptions.
No current loop, FOC transients, DESAT, short-circuit withstand or gate-driver
timing validation is claimed.

## OBC PFC/LLC

The new OBC model uses a balanced three-phase PFC input and full-bridge LLC
drive. It is distinct from any half-bridge reference netlist.
Equivalent load Rac = 8 × n² × Rout / pi².
The complex tank model evaluates series Lr/Cr and parallel Lm/Rac. The
solver searches the configured frequency band for the required full-bridge
gain Vout × n / Vbus, preferring an inductive-input solution.

At Lr/Cr resonance, the series reactance cancels and tank gain is unity.
An unreachable gain is flagged. Input-current/loss iteration includes stated
conduction, fixed and allocated switching losses. It is an engineering
screening estimate, not an efficiency measurement.

Inductive input impedance is a necessary screening observation, not evidence
that MOSFET output capacitance commutates in the available deadtime. ZVS
therefore remains NOT_EVALUATED.

See SOURCES.md for primary technical references. The implementation is original;
source documents are linked, not redistributed.
