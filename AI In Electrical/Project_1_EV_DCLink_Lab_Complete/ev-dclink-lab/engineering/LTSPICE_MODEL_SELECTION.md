# LTspice Model Selection

## Controlled portfolio model

Use `ltspice_physical/DCLINK_PHYSICAL_NOMINAL.cir` and its companion corner and
fault decks. This is model **EV-DCL-LTS-005 Rev A**.

It contains R-L contactor coils, MOSFET low-side drivers, coil-current-driven
main/auxiliary contacts, hardware RC sequencing, transistor-level voltage-ratio
comparison, physical sensing dividers and a VDMOS active-discharge path.

## Superseded model

`ltspice_complete/` is retained only as an archival behavioral baseline. It
uses direct command-to-resistance contact abstractions and is not the selected
component-level deliverable.

