* =============================================================================
* Parameterized 800 V DC-link plant and real-time controller interconnect
* Include this file only after the calling deck defines the top-level params.
* =============================================================================
.include DCLINK_PHYSICAL_MODELS.lib

* ----- HV battery and harness ----------------------------------------------
VBAT BATP 0 {VPACK}
RBAT BATP BAT_R {RBAT}
LBAT BAT_R BAT_L {LBAT}
RHAR BAT_L HVP {RHAR}
LHAR HVP HVP_INT {LHAR}
RHV_BUS HVP_INT HVP_BUS 1u

* ----- LV controller supplies and external vehicle commands ----------------
V12 V12 0 {VCOIL}
V5 V5 0 {VLOGIC}
* Key-on is an external ECU input. The internal controller creates precharge
* delay, timeout, threshold closure and auxiliary-contact interlocking.
VWAKE WAKE 0 PWL(0 0 1.999m 0 2m 5 999.9m 5 1s 0 6s 0)
* Discharge is delayed 50 ms after key-off so both mechanical mains have time
* to release before the resistor is applied across the isolated DC link.
VDIS_REQ DIS_REQ 0 PWL(0 0 1.0499s 0 1.05s 5 6s 5)

* ----- Main negative contactor and coil driver ------------------------------
RNEG_COIL_FAULT V12 NEG_CP {RNEG_COIL_FAULT}
XKNEG 0 DCMINUS NEG_CP NEG_D V5 NEG_AUX NEG_MECH EV200_COIL_CONTACTOR
+ params: RCOIL={RCOIL_MAIN} LCOIL={LCOIL_MAIN}
XDRV_NEG NEG_D WAKE 0 COIL_LOW_SIDE_DRIVER
DNEG_FLY NEG_D NEG_CP DFLY
RNEG_AUX_PD NEG_AUX 0 10k

* ----- Positive main contactor and coil driver ------------------------------
RPOS_PATH_FAULT HVP_BUS POS_HVIN {RPOS_PATH_FAULT}
RPOS_COIL_FAULT V12 POS_CP {RPOS_COIL_FAULT}
XKPOS POS_HVIN DCPLUS POS_CP POS_D V5 POS_AUX POS_MECH EV200_COIL_CONTACTOR
+ params: RCOIL={RCOIL_MAIN} LCOIL={LCOIL_MAIN}
XDRV_POS POS_D POS_GATE 0 COIL_LOW_SIDE_DRIVER
DPOS_FLY POS_D POS_CP DFLY
RPOS_AUX_PD POS_AUX 0 10k

* A physical auxiliary contact removes the precharge-coil command after the
* positive main contact has mechanically closed.
RPKILL_BASE POS_AUX PKILL_B 10k
RPKILL_PD PKILL_B 0 100k
QPKILL PRE_GATE PKILL_B 0 QNPN

* ----- Precharge contactor, pulse resistor and coil driver ------------------
RPRE_COIL_FAULT V12 PRE_CP {RPRE_COIL_FAULT}
XKPRE HVP_BUS PRE_CONT_OUT PRE_CP PRE_D V5 PRE_AUX PRE_MECH PRECHARGE_COIL_CONTACTOR
+ params: RCOIL={RCOIL_PRE} LCOIL={LCOIL_PRE}
XDRV_PRE PRE_D PRE_GATE 0 COIL_LOW_SIDE_DRIVER
DPRE_FLY PRE_D PRE_CP DFLY
RPRE_AUX_PD PRE_AUX 0 10k
RPRE_PATH PRE_CONT_OUT PRE_RIN {RPRE_EFFECTIVE}
LPRE_PATH PRE_RIN DCPLUS {LPRE}

* ----- Static test fault injectors -----------------------------------------
VWELD_CTRL WELD_CTRL 0 {5*F_POS_WELD}
SPOS_WELD HVP_BUS DCPLUS WELD_CTRL 0 FAULT_CONTACT
VPREW_CTRL PREW_CTRL 0 {5*F_PRE_WELD}
SPRE_WELD HVP_BUS PRE_CONT_OUT PREW_CTRL 0 FAULT_CONTACT

* ----- DC-link bank ---------------------------------------------------------
LESL DCPLUS CAP_ESR {CESL}
RESR CAP_ESR CAP_NODE {CESR}
CDC CAP_NODE DCMINUS {CDC} ic=0
RLEAK DCPLUS DCMINUS {RLEAK}

* ----- Physical voltage sensing --------------------------------------------
* 800 V -> 3.881 V nominal using 8 MOhm / 39 kOhm divider.
RP1 HVP_BUS PK1 2Meg
RP2 PK1 PK2 2Meg
RP3 PK2 PK3 2Meg
RP4 PK3 PACK_SNS 2Meg
RPL PACK_SNS 0 {39k*(1+EPACK)}
CPL PACK_SNS 0 10n

RD1 DCPLUS DK1 2Meg
RD2 DK1 DK2 2Meg
RD3 DK2 DK3 2Meg
RD4 DK3 VDC_SNS 2Meg
RDL VDC_SNS DCMINUS {39k*(1+ELINK)}
CDL VDC_SNS DCMINUS 10n

* Independent 93 percent pack-reference divider. 4 x 2.151 MOhm with 39 kOhm
* creates approximately 0.93 times the transfer ratio of the DC-link channel.
RT1 HVP_BUS PT1 {2.151Meg/(1+EPACK)}
RT2 PT1 PT2 {2.151Meg/(1+EPACK)}
RT3 PT2 PT3 {2.151Meg/(1+EPACK)}
RT4 PT3 VPACK93_REF {2.151Meg/(1+EPACK)}
RTL VPACK93_REF 0 39k
CTL VPACK93_REF 0 10n

* ----- Real-time analog precharge controller -------------------------------
* Precharge pickup delay: the driver gate rises only after the WAKE RC reaches
* the MOSFET threshold. The auxiliary contact and timeout MOSFET can both
* force the gate low.
RPRE_DELAY WAKE PRE_GATE 180k
CPRE_DELAY PRE_GATE 0 100n ic=0
RPRE_GATE_PD PRE_GATE 0 1Meg

* Hardware precharge timeout: approximately 350 ms at a 2.5 V MOS threshold.
RTIME WAKE TIME_NODE 510k
CTIME TIME_NODE 0 1u ic=0
DTIME_RESET TIME_NODE WAKE DLOGIC
MTIMEOUT PRE_GATE TIME_NODE 0 0 NLOGIC

* Transistor-level comparator closes the positive contactor after the sensed
* DC link exceeds the 93 percent pack reference.
XVCMP VDC_SNS VPACK93_REF RATIO_OK V5 0 DISCRETE_COMPARATOR
RHYST RATIO_OK VDC_SNS 20Meg
RPOS_DELAY RATIO_OK POS_GATE 10k
CPOS_DELAY POS_GATE 0 330n ic=0
RPOS_GATE_PD POS_GATE 0 100k

* Wake-low hardware clamp makes the positive coil fail-safe on key-off.
RWAKE_N V5 WAKE_N 10k
QWAKE_INV WAKE_N WAKE 0 QNPN
RPOS_SHUT_B WAKE_N POS_SHUT_B 10k
RPOS_SHUT_PD POS_SHUT_B 0 100k
QPOS_SHUT POS_GATE POS_SHUT_B 0 QNPN

* Hardware RUN permission is high only when wake, both main auxiliary contacts
* and the voltage-ratio comparator are high. Diodes implement a wired AND;
* this node is an observable permission signal, not a production torque path.
RRUN_PULL V5 RUN_OK 10k
DRUN_WAKE RUN_OK WAKE DLOGIC
DRUN_NEG RUN_OK NEG_AUX DLOGIC
DRUN_POS RUN_OK POS_AUX DLOGIC
DRUN_RATIO RUN_OK RATIO_OK DLOGIC

* ----- Active discharge ----------------------------------------------------
RDIS_FAULT DCPLUS DIS_PLUS {RDIS_PATH_FAULT}
XDIS DIS_PLUS DCMINUS DIS_REQ 0 DIS_GATE ACTIVE_DISCHARGE params: RDIS={RDIS}

* ----- Simulation-reference conductances ----------------------------------
* These do not represent chassis bonding; they keep intentionally isolated
* nodes numerically referenced before the contactors close.
RDM_REF DCMINUS 0 1G
RDC_REF DCPLUS 0 1T

