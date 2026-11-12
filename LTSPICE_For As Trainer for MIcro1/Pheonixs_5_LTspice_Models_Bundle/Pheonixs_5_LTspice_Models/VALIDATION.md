# Validation and limits

## Completed here

- Five working ASC files and five corresponding plot presets prepared.
- All declared symbol references resolve to files beside their schematic.
- All declared model/include files are present; protected vendor binaries are retained unchanged.
- Five local inspections pass across **133 schematic components**.
- VRM: connected `I1` is between `OUT` and ground; all four inductors join the
  output net; no disconnected `Iload` directive remains; capacitor bank is explicit.
- ADC: clock and hold nets are distinct; switch signal and control pins are
  correctly assigned; hold capacitor and quantizer output reference ground.
- Five focused support-script tests pass, including mirrored pin geometry,
  deliberate clock-short detection, extended RAW alias columns and rejection
  of a user-stopped log even when it contains an elapsed-time line.
- Original selected source files and two retained historical RAW files match
  the uploaded bytes. RAW record sizes/counts and monotone times were checked.
- The corrected behavioral ADC was executed in **ngspice 44.2**. Its four stated
  behavioral checks pass. See `validation/adc_ngspice/result.json`.

The ADC's measured-from-simulation quantization residual is approximately
0.00019–0.99971 LSB. The maximum held-node change over the checked 2 us hold
intervals is about 0.1013 uV. Code span is 0–4095. A coherent 1000-point
rectangular DFT of uniformly strobed held codes, at 100 kS/s and 9.9 kHz input,
gives about 73.93 dB SINAD and 11.99 derived ENOB. DC is excluded. These are
ideal behavioral-model metrics and have no hardware correlation.

## Historical evidence is separate

The LT8584 historical RAW has 1,648 points and ends at 1.5 ms, matching its
source stop time. The flyback historical RAW has 263,104 points and ends at
100 ms, which differs from the selected source's present 10 ms command. That
mismatch is explicitly retained. Original log completion does not prove the
current source revision or the prepared working copy was run.

The original ADC RAW has 1,001,355 points over 1 ms. Its full file was omitted
from this focused bundle; the source archive still contains it. A decimated
preview, metadata and full-file hash are included. The original clock/sample
short and extreme `.four` results are not used to claim ENOB. Decimated
historical previews must not be used for spectral or switching-peak acceptance.

## Not completed here

Fresh native LTspice execution, native GUI import of the plot presets, GUI
schematic rendering, electrical acceptance of the protected IC models, board
measurements, EMC/safety qualification and GitHub publication were not performed.
The package provides working copies and reproducible checks; it does not claim
that the four protected IC circuits have newly passed electrical simulations.

Local dependency checks can identify declared files, not inspect internal
dependencies of encrypted vendor subcircuits. A native LTspice rerun is the
remaining way to establish that the chosen installation resolves and executes them.
