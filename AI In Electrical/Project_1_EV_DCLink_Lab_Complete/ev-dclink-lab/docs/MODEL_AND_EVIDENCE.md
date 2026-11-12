# Model, assumptions, and evidence

## Electrical model

Charging uses Vdc = Vpack × (1 − exp(−t/RC)).
Time to ratio a is −RC × ln(1 − a).
Capacitor stored energy is 0.5 × C × V².
Discharge to Vsafe uses Rdis × C × ln(Vinitial/Vsafe).

The synthetic plant integrates each constant-topology RC interval with its
exact exponential update. A 2 ms default supervisor step and explicit
12 ms pickup / 8 ms release model contactor timing. This is not a switching
or electromechanical contact-bounce simulation.

The contactor supervisor requires negative-main feedback before precharge,
the close threshold before requesting positive-main closure, and both
main auxiliary contacts before torque enable. Shutdown interrupts startup
as well as run. Faults latch. Discharge is blocked whenever any contactor
auxiliary remains closed. Loss of main feedback or DC-link voltage disables
torque in the same supervisory step.

Two synthetic link-voltage channels support disagreement diagnostics.
Their agreement cannot rule out a common-cause bias. The simulator has no
isolation-resistance physics, arc model, crash system, or vehicle controller.

## Corner calculation

The measured ratio is actual_ratio × (1 + link_error)/(1 + pack_error).
Consequently actual_ratio at a command threshold is
command_ratio × (1 + pack_error)/(1 + link_error).

Enumerated combinations:

- Pack: 600, 800, 850 V.
- Precharge resistor: −3%, nominal, +3%.
- Capacitance: −10%, nominal, +10%.
- Pack and link sensor errors independently: −1.5%, +1.5%.
- Discharge resistor: conservative +10%.
- Startup overhead: 30 ms allocation, added to electrical charging time.

There are 108 combinations. The deterministic sweep uses a single sensing
ratio with the stated independent gain budget. The supervisor demonstration
also uses a second link channel; these are two separately identified
experiments, not the same qualification campaign.

## Current observed results

- Nominal cycle: all seven waveform checks pass.
- Ten injected faults: expected diagnostics observed, no torque in blocked
  startup faults, and no discharge commanded while auxiliary feedback is closed.
- Baseline sweep: 102 passes, six timing failures.
- Analytical 88 ohm allocation: 108 passes in this simplified sweep.

These are model results produced by the bundled commands. Tests establish
software behavior, not physical component reliability or ASIL compliance.

## Recovered native models

engineering/ltspice_physical includes coil/driver/contact proxy subcircuits,
separate nominal/corner/fault decks, a graphical .asc wrapper, parameter
provenance and replacement notes. engineering/ltspice_complete and
engineering/simulation preserve other recovered model variants.
engineering/simulink contains generation/analysis .m scripts.

The native models were recovered, not executed here. Use their own README
and parameter maps. Run the static package validators before local tool
execution. Historical report verdicts in recovered_sources are unverified
history and are not imported into current reports.
