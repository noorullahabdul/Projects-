# Meaningful next development tasks

1. Add oscilloscope CSV mappings and unit conversion with immutable input hashes.
2. Add controller sampling/PWM delay and compare time-step-independent stability.
3. Fit temperature-dependent switch resistance and switching-energy tables
   from public supplier data, retaining source/model revision per component.
4. Add id/iq field weakening with current-circle and voltage-ellipse constraints.
   Preserve signed motoring/regeneration power accounting.
5. Add LLC ZVS commutation-charge checks using explicit Coss/Qoss and deadtime.
   Keep unavailable evidence as NOT_EVALUATED.
6. Add measured efficiency-map import and residual/error plots instead of
   calibrating the tool against its own generated data.

Suggested terminal-assistant task:

    Add a configurable PWM/ADC delay to the averaged buck simulation.
    Explain the model and numerical risks first. Keep the current no-delay
    behavior reproducible, add meaningful convergence and delayed-loop
    regressions, run the suite, and summarize the change and limitations.

Keep actual terminal commands, failing cases, review decisions and commits.
Do not treat a passing test suite as hardware validation or invent a long
repository development history.
