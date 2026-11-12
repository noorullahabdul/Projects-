# LTspice Schematic Package

## Primary editable schematic

Open `800V_DCLink_CR004_Complete.asc` in LTspice. The drawing contains:

- 600 to 850 V source representation
- battery and harness resistance and inductance
- positive and negative main contactors
- independent precharge contactor and 92 ohm resistor bank
- DC-link capacitor with ESR and ESL
- passive bleeder and active discharge path
- contactor command sources including precharge bounce
- objective transient measurements

## Companion netlists

- `dclink_gate2_parasitic.cir` is the controlled corner netlist.
- `dclink_gate3_faults.cir` is the electrical fault-injection netlist.

## Local verification required

The ASC file uses standard LTspice symbols and generic voltage-controlled switches. Open it locally, run a nominal transient, confirm all symbol pins and control labels, then archive the `.raw` and `.log` files. Supplier contactor, resistor thermal and isolation behavior must be correlated separately.
