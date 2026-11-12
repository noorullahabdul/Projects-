# 12-bit sample-and-hold / quantizer model

Open **Model.asc** in LTspice, press Run, and load **Model.plt**. Keep all files in this model folder together.

## Selected source

`SRS_!.asc` from the uploaded Pheonixs.zip. The original is retained unchanged under `source/`.

## Working-copy notes

- Behavioral acquisition and quantization model; no SAR register, comparator bit trial, or real ADC device is modeled.
- Separated the clock from SH_OUT and joined the switch output to the hold capacitor.
- Changed hold capacitor to 100p and leakage load to 1T; codes are clipped to 0..4095.
- The original .four result is not a valid ENOB result; it is retained only in source evidence.

This is a behavioral sample/hold and ideal 12-bit quantizer, not a transistor-level SAR converter. S1 now joins VIN to SH_OUT while CLK drives only its control. C1=100p and R2=1T provide fast ideal acquisition and low hold leakage. Explicit min/max clipping gives codes 0..4095. The corrected generic circuit was executed in ngspice; native LTspice execution is still pending. The original RAW/THD log is separate historical failure evidence.

## Plot expressions

- `V(VIN)`
- `V(SH_OUT)`
- `V(DGTL_OUT)`
- `V(CLK)`

## Status

Local declared dependencies and stated structural checks pass. Fresh native LTspice execution and plot import were not performed here. These are circuit simulations/models, not bench measurements or production qualification.
