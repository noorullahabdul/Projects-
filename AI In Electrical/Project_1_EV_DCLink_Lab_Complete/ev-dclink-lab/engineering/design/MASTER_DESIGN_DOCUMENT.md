---
title: 800 V DC Link Engineering Design and Verification
subtitle: Complete calculation schematic traceability and prototype validation package
author: Noorullah Abdul Khadar
date: 14 October 2026
toc: true
toc-depth: 3
---

# Document control and engineering decision

| Field | Controlled value |
|---|---|
| Document ID | EV-DCL-DD-001 |
| Revision | C |
| Gate status | Conditional and open |
| Verification candidate | CR-004 |
| Executed evidence | Python analytical campaign |
| Prepared evidence | LTspice MATLAB Simulink and Simscape inputs |
| Future evidence | HIL prototype EMC insulation and thermal correlation |

This document closes the documentation gaps identified in the earlier package. It records the design basis, equations, assumptions, requirement allocation, architecture links, DFMEA links, objective test procedures and prototype-resource needs. CR-004 is analytically feasible, but Gate 3 remains open until tool execution and physical correlation are reviewed.

## Revision history

| Revision | Date | Change | Status |
|---|---|---|---|
| A | 13 October 2026 | Initial model-verification presentation | Superseded |
| B | 14 October 2026 | Corrected scope and evidence status | Superseded |
| C | 14 October 2026 | Added calculations traceability procedures facilities and complete schematic | Current |

## Approval status

| Role | Name | Decision |
|---|---|---|
| Design owner | Noorullah Abdul Khadar | Prepared |
| Independent reviewer | To be assigned | Open |
| Verification lead | To be assigned | Open |
| Release authority | To be assigned | Open |

# Requirements analysis

The subsystem shall operate from 600 V to 850 V, limit precharge current to 10 A, reach at least 90 percent of pack voltage within 350 ms, inhibit torque until valid main-contactor closure, diagnose precharge and sensing faults, and discharge below 60 V. The controlled RA-to-validation matrix is delivered as `requirements/RA_to_validation_traceability.csv`.

## Requirement allocation summary

| Need | System allocation | Hardware or control allocation | Verification |
|---|---|---|---|
| Operate across pack range | DCL-SYS-001 | HV component derating | Analysis LTspice bench |
| Limit inrush | DCL-SYS-003 | Pulse resistor and precharge path | Calculation LTspice bench |
| Meet charge time | DCL-SYS-004 | R C sensing and latency budgets | Corners LTspice MIL HIL |
| Prevent unsafe torque | DCL-SYS-002 and 005 | State machine and auxiliary feedback | MIL SIL HIL |
| Diagnose faults | DCL-SYS-006 007 009 010 011 | Current voltage HVIL isolation and auxiliaries | Fault injection HIL bench |
| Touch-safe discharge | DCL-SYS-008 | Active and passive discharge | Analysis LTspice bench |
| Reproducible evidence | DCL-SYS-012 | Configuration and evidence management | Process audit |

# Architecture and controlled sequence

The battery feeds the positive and negative HV rails through independent main contactors. A precharge contactor and pulse resistor form a parallel path around the positive main contactor. The DC-link model contains effective capacitance, ESR, ESL and leakage. An actively switched resistor discharges the bus after shutdown. Pack and DC-link voltage channels, contactor auxiliaries, HVIL and isolation status feed the supervisory controller.

| State | Required conditions | Commands | Exit criterion |
|---|---|---|---|
| OFF | No wake | All contactors open | Valid wake |
| SELF TEST | HVIL and isolation valid | No HV commands | Inputs plausible |
| NEG CLOSE | Negative close allowed | Negative on | Auxiliary confirmed |
| PRECHARGE | Negative confirmed | Precharge on | Ratio and timing valid |
| MAIN CLOSE | Closure threshold reached | Positive on | Positive auxiliary confirmed |
| RUN | Both mains confirmed and precharge open | Torque enable permitted | Shutdown or fault |
| DISCHARGE | Mains commanded open | Active discharge on | Vdc below 60 V |
| SAFE OR FAULT | Fault or shutdown complete | Torque inhibited | Authorized recovery |

Torque enable is legal only in RUN. A reset or loss of control power de-energizes outputs by hardware default. HVIL or invalid isolation prevents activation and forces the allocated safe response.

# Analytical verification summary

| Campaign | Pass result | Key worst case |
|---|---:|---|
| Deterministic CR-004 corners | 6561 of 6561 | 339.424 ms maximum command time |
| Seeded Monte Carlo | 50000 of 50000 | 9.584 A maximum initial current |
| Active discharge corners | 81 of 81 | 3.336 s maximum to 60 V |

These calculations support feasibility only. They do not close the LTspice, MATLAB, Simulink, Simscape, HIL or prototype validation rows.

# DFMEA and validation coverage

The controlled DFMEA contains 18 failure modes covering the precharge resistor, DC-link capacitor, both main contactors, sensing, discharge, HVIL, isolation status and controller reset. The DVP and test catalogue contain 20 cases across analysis, LTspice, MIL, HIL, bench and process audit. Detailed records are delivered in `gate3/oem_documents`.

## Principal risk controls

- Use a 92 ohm plus or minus 3 percent low-TCR pulse resistor bank as the CR-004 verification candidate.
- Verify pulse energy and transient thermal impedance against supplier SOA.
- Use independent voltage-channel plausibility, rate and command-response diagnostics.
- Diagnose open, short, chatter and welded-contactor conditions using command, auxiliary and voltage behavior.
- Maintain hardware-default safe outputs during reset and brownout.
- Require synchronized physical and network evidence for integration approval.

# Complete schematic and model files

The editable LTspice file `simulation/800V_DCLink_CR004_Complete.asc` contains the battery source, source and harness parasitics, positive and negative main contactors, precharge contactor, resistor bank, DC-link ESR ESL and capacitance, passive leakage, active discharge, control sources and objective measurements. Companion netlists provide 81 corner combinations and seven fault configurations.

The MATLAB campaign evaluates deterministic, Monte Carlo and discharge corners. The Simulink builder defines supervisory logic. The Simscape builder defines the physical plant. These are prepared inputs and require local execution, tool-version recording, checksums and evidence review.

# Evidence and gate closure

| Closure item | Required evidence | Status |
|---|---|---|
| LTspice corner and fault runs | Log raw waveforms parsed measurements screenshots and checksum | Open |
| MATLAB campaign | CSV MAT PNG diary release host and hashes | Open |
| Simulink logic | SLX Model Advisor MIL report and coverage | Open |
| Simscape plant | SLX solver log waveforms and parameter manifest | Open |
| DFMEA actions | Cross-functional signed action record | Open |
| HIL timing | Timestamped raw and reviewed report | Future gate |
| Prototype correlation | Calibrated electrical thermal and contactor evidence | Future gate |
| Independent approval | Signed gate decision and deviations | Open |

The package is complete for portfolio design review and local model execution. It is not authorization for production hardware, vehicle energization, supplier nomination, safety release or SOP.
