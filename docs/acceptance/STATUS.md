# Stage acceptance

| Stage | Status | Evidence |
|---|---|---|
| S0 frozen protocol, repository and evaluation primitives | Passed | `configs/protocol.yaml`, 11 boundary tests; `S0.json` |
| S1a BrisT1D acquisition and cohort audit | Passed | 20 verified source files, channel-specific duplicate handling; `S1a.json` |
| S1b PhysioCGM acquisition and clock audit | In progress | Per-subject raw ZIPs, source clock and censored-label audit |
| S2 module 1 forecasting and information ablation | Pending | Frozen held-out predictions |
| S3 module 2 physiological signal and sensor comparison | Pending | Source ZIP audit and held-out predictions |
| S4 uncertainty, calibration and independent evaluation | Pending | Subject-level reports and acceptance JSON |
| S5 interactive showcase and publication checks | Pending | Actual result exports, UI checks |

Advance only after recording the current stage's engineering/evaluation checks. Predictive-effect targets may fail or be inconclusive; report that separately rather than changing the test protocol.

