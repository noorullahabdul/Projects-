# Pheonixs — five selected LTspice models

Five engineering models selected from your uploaded **Pheonixs.zip**, prepared
as separate LTspice folders with graphical schematics, plot presets, local
symbols, required declared model files, source evidence and run instructions.
Working copies are separate from the originals.

| Model | Engineering focus | Selected source |
|---|---|---|
| 01 — LT8584 | Active cell-to-stack balancing | `BMS/LT8584.asc` |
| 02 — LTC3300-1 | Six-cell bidirectional balancing | `BMS/3300-1.asc` |
| 03 — LT8304 | 48 V isolated flyback with two secondaries | `Draft1.asc` |
| 04 — LTC7851 | Four-phase 12 V VRM, 10 A → 100 A load step | `vrm_transient_core.asc` |
| 05 — ADC sampling | 100 kS/s sample-and-hold with 12-bit behavioral quantization | `SRS_!.asc` |

The selection favors relevant circuits, recoverable dependencies and manageable
repairs. The SiC draft requires a larger power/thermal/control wiring review;
the interrupted combined data-center design and duplicate copies were not
selected. The ADC is an acquisition/quantizer model, not a transistor-level SAR
ADC or an implemented successive-approximation state machine.

## Open and run in LTspice

1. Extract the whole ZIP to a folder such as `C:\Projects\Pheonixs_5_Models`.
2. Use your installed LTspice. The supplied historical logs identify LTspice
   26.0.2 for Windows. The original installer stays in your source upload.
3. Double-click `OPEN_MODELS.bat` and select 1–5, or open the chosen
   `models/.../Model.asc` directly in LTspice.
4. Press **Run**. Load the matching `Model.plt` or probe the nodes in
   `trace_list.txt`. Autorange if your result exceeds a preset axis.
5. Open that model's `README.md` for the source changes and specific observations.

Do not copy only the `.asc`: its local `.asy`, `.sub` and `.lib` files are part
of the model. These local assets avoid the original machine-specific symbol
paths. Encrypted/protected IC subcircuits remain byte-for-byte vendor files;
their contents were not decrypted or translated to other simulators.

LTspice product/download page: [Analog Devices](https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html).

## What changed

- All five use local symbol names and packaged declared dependencies. Original
  `.asc` files remain unchanged in each `source/` folder.
- The VRM's extra `Iload Vout 0` directive was removed. The existing connected
  `I1` supplies the intended load step on `OUT`. The ambiguous `X15` capacitor
  notation became an explicit 1500 uF bank. Measurements exclude startup, and
  only relevant traces are saved to reduce waveform size.
- The ADC clock was separated from `SH_OUT`, and the switch output was joined
  to the hold capacitor. The hold capacitor is 100 pF, the ideal leakage load
  is 1 TΩ, and an explicit min/max expression clips codes to 0–4095. The old
  continuous-waveform `.four` measurement was removed from the working copy.
- Output labels were added to the flyback and cell terminals to make probing
  meaningful. Balancer transient maximum steps were made explicit.

`changes.json` and each folder's README record the details. New plot settings
follow the format of plot files recovered from the uploaded installer; their
LTspice GUI import has not been checked in this environment.

## Verification status

| Model | Checks completed here | Fresh native LTspice run |
|---|---|---|
| LT8584 | Local dependencies; historical RAW/log inspection | Pending |
| LTC3300-1 | Local dependencies; six-cell source and symbol inspection | Pending |
| LT8304 | Local dependencies; historical RAW/log inspection; output labels | Pending |
| LTC7851 | Local dependencies; connected load and four-phase output checks | Pending |
| ADC | Local dependencies; repaired switch/clock/hold connectivity; executed ngspice experiment | Pending |

The ADC experiment passes its code-range, quantization-consistency, signal-span
and hold-change checks. Its coherent, uniformly strobed **ideal-model** result
is about **73.93 dB SINAD / 11.99 derived ENOB**. These are simulated results,
not measured ADC performance or evidence of a physical SAR implementation.

Historical flyback data reaches **100 ms**, while the selected source and
working schematic request **10 ms**. It is kept as historical evidence and
does not establish the current revision's performance. The old VRM log includes
a floating-node error and a failed recovery measurement; it is not a pass report.

See `VALIDATION.md`, `validation/static_checks.json` and the ADC run's actual log,
measurement JSON, uniformly sampled table and strobed samples. No circuit here
is claimed to have passed production, safety, EMC or hardware qualification.

## Terminal workflows

Only Python 3.10+ is needed for local checks; no Python packages are required.

```console
python tools/inspect_models.py
python tools/test_helpers.py
python tools/run_ltspice.py --list
python tools/run_ltspice.py --model 01 --ltspice "C:\Program Files\ADI\LTspice\LTspice.exe"
```

The LTspice runner copies the chosen folder into `output/ltspice/`, creates a
native netlist with `-netlist`, runs it with `-b`, and checks the log and waveform
stop time. `--model all` runs sequentially. Simulation completion is distinct
from electrical acceptance; no arbitrary acceptance limits are silently added.
This native runner was supplied but not executed here because LTspice/Wine are
not installed in this environment.

The generic ADC can also run with an installed ngspice:

```console
python tools/run_adc_ngspice.py --ngspice "C:\path\to\ngspice_con.exe" --out output/adc_ngspice
```

Its netlist is exported from the working ASC connectivity. Only the positive
transient output step changes for ngspice syntax. Proprietary LTspice IC models
in folders 01–04 require their intended simulator.

## Source and ownership

Prepared on **2026-11-11** from the uploaded archive. `SOURCE_PROVENANCE.md`
records the archive identity, selection and source hashes. `vendor_reference/`
retains the supplied licence and dependency provenance. Vendor models are not
represented as your original code. No GitHub repository was published, and no
prior development history or ownership verification was fabricated.
