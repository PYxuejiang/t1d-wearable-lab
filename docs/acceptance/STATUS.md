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
| S5 interactive showcase and publication checks | Local display/exports passed; screen recording pending | `S5.json`, desktop/390px screenshots, result contracts and error/empty-state checks |

## Improvement experiments

| Stage | Evaluation | Effect |
|---|---|---|
| V2.1 personalized static/temporal features and dense thresholds | 63 groups independently verified | Event target failed |
| V2.2 added device physiology summaries | 63 groups independently verified | Event target failed |
| COHORT_SW1 new smartwatch cohort, unseen-subject tests | 33 groups independently verified | AUC/AP benefit inconclusive |
| COHORT_SW_PERSONAL1 personalized source-row holdout | 33 groups independently verified; exact chronological time unavailable | AP gain exploratory positive; AUC and alarm target remain unresolved |

Advance only after recording the current stage's engineering/evaluation checks. Predictive-effect targets may fail or be inconclusive; report that separately rather than changing the test protocol.



| Additional stage | Evaluation | Effect |
|---|---|---|
| CONTEXT_V1_ABORTED | Original120-row-purge attempt quarantined by support audit | No efficacy claim |
| CONTEXT_V1_1 |132 groups independently verified; source-row limits retained | Context AP gain inconclusive; calibration improves raw Brier but not stable versus simple prior |
| ECG_CAPTURE_PILOT1 |48 groups independently verified on four fixed expert-annotated ECG records | Both methods pass internal capture gate; no glucose/PPG/alarm effect claim |
