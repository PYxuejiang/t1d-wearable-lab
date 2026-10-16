# Frozen implementation decisions

Protocol configuration: `configs/protocol.yaml`.

- Module 1 uses observed CGM anchors, a 60-minute history and a 30-minute target. Targets must be observed within 2.5 minutes of the nominal future time. No future observations enter features.
- Incident event prediction is evaluated separately from numeric forecasting and current-state detection.
- Module 2 uses trailing non-CGM physiological features with reference CGM labels. Sensor comparisons use common observations and also report end-to-end availability.
- An event is an observed low run spanning at least 15 elapsed minutes with no normal observation or gap exceeding 1.5 nominal sampling intervals. Left-censored starts are not confirmed incident events. Sparse observations do not establish continuous physiological exposure.
- Alarm processes use rising edges, 30-minute cooldown after reset, and chronological one-to-one event matching. Forecast hits must precede the reference onset by at most 30 minutes; detection hits occur within the observed event.
- BrisT1D repeated identical channel timestamps collapse. Conflicting numeric values at a channel timestamp are excluded with counts, not silently averaged. Event sums represent recorded intake/dose, not proof of unrecorded events being absent.
- PhysioCGM EGV rows alone are reference measurements. `Low`/`High` are censored threshold labels, not exact glucose values. Invalid or unknown encodings stop the adapter.
- E4 epoch timestamps are UTC. A training-only heart-rate comparison checks alignment to the chest sensor; glucose labels are never used to optimize clock offset. Treating CGM and chest naive timestamps as the same wall clock remains an explicit source assumption, tested in sensitivity analyses.
- Subject-independent LOSO and chronological 60/20/20 evaluation are distinct. Full input, target and event-confirmation support is purged at split boundaries. All imputation, scaling, calibration and threshold selection are restricted to training/validation data.
- Numerical errors are averaged equally across subjects. Event recurrence and correlated windows do not increase the number of independent participants.
- Internal targets (5% error improvement; 80% event recall at <=1 false alarm/person-day and >=80% availability) are research goals, not medical device standards. Effect can fail while the evaluation and reproducibility pass.

Source data are excluded from Git. Published acceptance records contain aggregate counts and limitations only. Predictions, waveforms and source archives stay in ignored local directories; any demo excerpts require separate explicit selection and provenance.
