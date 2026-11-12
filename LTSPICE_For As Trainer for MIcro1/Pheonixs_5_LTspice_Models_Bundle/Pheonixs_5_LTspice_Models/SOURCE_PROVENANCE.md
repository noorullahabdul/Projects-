# Source provenance

Input: `Pheonixs.zip`, uploaded by the user, available locally as a 351,869,480-byte
archive. SHA-256:

`153d3aa778305071463f649579295347e93a59849ce0e503b2da8c460c2ecda0`

It contains 72 files including 17 ASC schematics, saved logs/RAW data, pictures,
an LTspice installer, caches and a nested Infineon model archive. Five schematics
were selected. The uploaded archive itself was not altered.

`source_files.json` identifies each byte-identical retained original ASC/log/RAW
file by archive path, packaged path and SHA-256. Current working files have the
common name `Model.asc`; changes are recorded in `changes.json` and folder READMEs.
Screenshots and AI-generated artwork were not treated as simulation evidence.

Declared symbols and subcircuits were recovered by data extraction from the
user-supplied `LTspice64 (4).msi`, then its `disk1.cab` and `lib.zip`. The installer
was not executed or installed. Only selected model support files were packaged;
the installer/executable and complete library were excluded. Protected IC
subcircuits were copied as opaque files and were not decrypted.

Some IC symbols originally used a `SpiceModel filename.sub` / `Value2 partname`
combination. Their local working symbols now use the explicit `ModelFile`
attribute with the same part Value and pin order. Standard diode/MOS definitions
were selected unchanged from the installer component libraries. The source
library hashes and each packaged dependency are recorded in
`vendor_reference/dependencies.json`. Vendor rights remain unchanged, and the
original supplied licence is retained in `vendor_reference/License.txt`.

The native `.plt` preset syntax was grounded in plot files from the installer's
`examples.zip`. Fresh GUI import was not tested. The generic ADC `.cir` is
exported from the prepared ASC's pin/wire connectivity, with no proprietary
IC model substitution. Its ngspice transient step is made positive for that
simulator's syntax; the component topology and quantization expression are shared.

The supplied LTspice logs retain their original June 2026 dates and Windows
paths as historical data. They are not fresh test logs. The current processing
date is 2026-11-11. No previous commit history, personal ownership or client
publication permission was inferred from filenames or paths.

Primary references consulted:

- [Analog Devices LTspice Quickstart and command-line reference](https://analogdevicesinc.github.io/ltspice-reference/ai_ref/LTSPICE-QUICKSTART.html)
- [Analog Devices SPICE netlist syntax reference](https://analogdevicesinc.github.io/ltspice-reference/ai_ref/SPICE-SYNTAX-REFERENCE.html)

The first reference grounds the open/run and `-netlist`/`-b` workflow; the second
grounds netlist text, node and multiplier conventions. Circuit-specific facts
come from the actual uploaded schematics, recovered symbols and saved data.
