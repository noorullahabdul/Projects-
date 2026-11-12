# Requirements and Verification Matrix

| ID | Requirement | Verification |
|---|---|---|
| DCL-001 | Prevent main contactor closure until HVIL and insulation checks pass | State-machine tests |
| DCL-002 | Limit nominal initial inrush current to ≤10 A | Calculation/transient |
| DCL-003 | Reach ≥90% pack voltage within 0.35 s | Parameter sweep |
| DCL-004 | Open precharge path after main contactor confirmation | State-machine test |
| DCL-005 | Detect precharge-open and timeout faults | Fault injection |
| DCL-006 | Detect welded main contactor during shutdown | Fault injection |
| DCL-007 | Reduce DC-link below 60 V within 30 s | Discharge calculation |
| DCL-008 | Evaluate pack voltage, R and C tolerance corners | Automated sweep |

