* automotive_input_protection_core.inc
* Common protected-input circuit used by all four simulation cases.
*
.include "./automotive_protection_models.lib"

* Input-current sensor; positive current flows from VBAT toward the load.
V_IIN VBAT VBAT_IN 0

* Fuse/contact resistance.
RFUSE VBAT_IN VIN_RAW 50m

* TVS-current sensor and bidirectional TVS.
* Positive I(V_ITVS) means current absorbed from VIN_RAW into the TVS.
V_ITVS VIN_RAW TVS_TOP 0
XTVS TVS_TOP 0 TVS_BIDIR_24V

* L-C-L input filter with explicit inductor DCR.
R_L1 VIN_RAW L1_INT 20m
L1 L1_INT VIN_FILT 10u

CIN VIN_FILT 0 2.2u

R_L2 VIN_FILT L2_INT 20m
L2 L2_INT VIN_PROT 10u

* High-side reverse-polarity MOSFET.
* Correct port order: D G S.
XQ1 VIN_PROT GATE VOUT_PROT PMOS_REV_60V

* Gate network:
* RSG references the gate to the PMOS source.
* RGND turns Q1 on only when the source rises positive.
* During reverse battery, both source and gate remain near 0 V, so Q1 stays off.
RSG VOUT_PROT GATE 1Meg
RGND GATE 0 100k

* Gate-source zener: anode at gate, cathode at source.
DZGS GATE VOUT_PROT ZENER12V

* Protected-output capacitors with explicit ESR.
R_BULK VOUT_PROT CBULK_INT 80m
CBULK CBULK_INT 0 100u

R_COUT VOUT_PROT COUT_INT 30m
COUT COUT_INT 0 10u

* Protected load.
RLOAD VOUT_PROT 0 12

* Weak leakage aids convergence.
RLEAK_OUT VOUT_PROT 0 10Meg
