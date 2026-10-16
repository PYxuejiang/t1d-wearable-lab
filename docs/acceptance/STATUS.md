# Stage acceptance

| Stage | Status | Evidence |
|---|---|---|
| S0 frozen protocol, repository and evaluation primitives | Passed | `configs/protocol.yaml`, 11 boundary tests; `S0.json` |
| S1a BrisT1D acquisition and cohort audit | Passed | 20 verified source files, channel-specific duplicate handling; `S1a.json` |
| S1b PhysioCGM acquisition and clock audit | Passed for a restricted cohort | All 10 verified; 7 included, 3 clock quarantined; `S1b.json` |
| S2a module 1 numeric forecasting and information ablation | Passed engineering/evaluation; wearable effect failed/inconclusive | `S2a.json`, independent recomputation of 5,080,095 test predictions |
| S2b module 1 incident-event prediction | Passed engineering/evaluation; effect failed | `S2b.json`, 80 independently reconstructed test groups |
| S3 module 2 physiological signal and sensor comparison | Passed engineering/evaluation; effect failed | `S3.json`, 140 independently reconstructed evaluation groups |
| S4 uncertainty, calibration and independent evaluation | Passed reporting; exploratory scope | `S4.json`, subject bootstrap, calibration, clock and dropout stress tests |
| S5 interactive showcase and publication checks | Pending | Actual result exports, UI checks |

Advance only after recording the current stage's engineering/evaluation checks. Predictive-effect targets may fail or be inconclusive; report that separately rather than changing the test protocol.

