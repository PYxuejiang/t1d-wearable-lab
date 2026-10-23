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
| V3_MECHANISM1 |336 test groups, nested parameter selection and63 selected validation configurations independently checked | ECG failover coverage72.8%→82.8%; primary0/30 hits; detection target failed |
| SOURCE_TIME1 |34,218 source feature labels and ten fixed processed probes checked; three unique E4 waveform matches | Source consistency supported; physical CGM/chest clocks still unresolved, no offset changes |
| V4_LATE_FUSION1 |392 groups,30 inner candidates,28 selected validation points and out-of-fit stack refit independently checked | Stack AP0.0755→0.0969 exploratory gain; primary0/30, PPG comparator3/30; event target failed |

| V5_PPG_MORPH1 |42 groups,9 inner candidates,6 validation selections independently verified; old coarse scores reproduced| Morphology1/30 versus coarse3/30; same72.8% coverage; no AP or alarm gain; effect FAILED |

Interactive product homepage has a separate engineering acceptance report: [WATCH_EXPERIENCE](../WATCH_EXPERIENCE.zh-CN.md). Visual completion does not change scientific effect status.

PPG_DALIA_AUDIT1: two published MAT checksums and29activity records audited; scoring not started, source indexing/delay and licensing differences retained. See [source audit](../PPG_DALIA_AUDIT.zh-CN.md). No efficacy pass.

PPG_CAPTURE1: 607windows/464metricgroups, calibration and5SQIcandidates verified; engineering passed. HeldoutF1 gain not supported, shared reference alignment remains limited, clinical effect not evaluated. [Report](../PPG_CAPTURE_REPORT.zh-CN.md).

LORA_ENGINEERING1 (2026-10-23): synthetic pretraining and Q/V adapter fitting, frozen-weight invariance, hash-bound checkpoint roundtrip, missingness/consent/subject/time boundaries verified. 78 Python and18 Agent tests pass; frontend build passes. Real-cohort disease performance, paired protein fusion and QLoRA are **not evaluated/implemented**. See [implementation report](../TRANSFORMER_LORA.zh-CN.md) and [aggregate acceptance](LORA_ENGINEERING1.json). Original Harness and clinical evidence remain in place.
