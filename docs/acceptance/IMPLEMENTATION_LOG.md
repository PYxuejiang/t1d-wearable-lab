# Implementation log

## S0

Created the MIT-licensed independent implementation and frozen configuration. Eleven initial evaluation-boundary tests passed before model work; additional adapter and signal tests are added as source formats are audited. Public repository created only after local stage acceptance. Git author uses the account's GitHub noreply address.

## S1a

Downloaded and audited all 20 public BrisT1D processed device CSVs. The long-table layout, mixed 5/15-minute reference cadence and conflicting same-channel timestamps are explicitly handled. Source records remain ignored by Git. No numeric encodings failed the adapter.

## S1b

PhysioCGM raw ZIPs are processed directly: a single ~810 MB archive expands to over 11 GB. E4 native UTC timestamps are checked against chest HR using only the initial 60% of sensor time, without glucose labels. CGM/chest wall-clock equivalence remains a declared source assumption. Header-only E4 sessions are excluded rather than interpreted as zero signals. Censored `Low`/`High` values are labels/bounds, not numeric glucose measurements.

## S2a

All 20 subjects completed temporal and LOSO numeric comparisons with fixed model settings. The verification script adds the required simple-baseline selection using only validation errors; no trained model, hyperparameter or test prediction is changed. Both simple baselines are retained. Independent arithmetic agrees within 6.7e-16 mmol/L. Sensor information does not meet the predefined 5% gain target: LOSO is negative and temporal gain is inconclusive. These negative effects are retained; engineering/evaluation passage permits the next research stage under the handbook.

## Publication boundary

Only source code, protocol, aggregate acceptance records and selected aggregate display artifacts are public. Raw source files, participant-level predictions, waveforms and local manifests are not committed. A running pipeline does not imply a stage has passed.
