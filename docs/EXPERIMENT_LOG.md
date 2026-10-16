# Experiment handoff log

## 2026-10-16 / v1 complete; v2 requested

- User requires continued improvement until a measurable, reproducible positive effect is found. This is a research objective, not permission to manufacture results or alter denominators.
- Heartbeat `t1d`: active, every two hours in this thread. Previous creation failed on usage review; latest creation succeeded.
- v1: M1 numeric independent verification passed, CGM MAE improved vs simple baseline; wearable increment failed/inconclusive. M1 event fused LOSO recall 47.5%, 0.53 unmatched alarms/person-day. M2 all five configurations failed event detection target; 7 included people, 146 LOSO events, 31 temporal test events.
- Source: all 20 Bris CSV and 10 PhysioCGM ZIP verified locally. Do not re-download. Features already extracted for 7 clock-approved people. No processes required to finish extraction.
- Local project path: `D:/健康系列/可穿戴设备/t1d-wearable-lab`; public repo `PYxuejiang/t1d-wearable-lab`.
- CI failure diagnosed: pandas 3 uses microsecond default datetime resolution whereas code assumed `.asi8` is nanoseconds. Explicit nanosecond conversions and mixed-resolution regression test added. Existing computed metrics used pandas 2.3/ns and are unaffected; verify in CI before claiming portable pass.
- Showcase, aggregate JSON, PNG/SVG cards, Chinese validation report and metrics documents exist. Final publication commit and S5 acceptance are still being completed. Local server last owned session was 51420 on 127.0.0.1:5173; check before starting another. Browser download-event wait once hung; use finite timeouts and static PNG href download instead.
- Next: freeze v2.1 protocol, implement causal temporal features and personalized learner comparison; dense validation-only threshold search. Save all candidates; do not touch the v1 evidence.

## 2026-10-17 / completed improvement batch

- GitHub head `ab4b30e` passed both Python tests and frontend build. Fixed a second portability issue: CRLF/LF text hashes now canonicalized. New code/results since that commit still need final push and CI confirmation.
- v2.1: 4 learner families × 4 feature sets, per-person validation AP selection; dense validation score quantiles, causal smoothing spans1/3, budgets1/2/4. Independent evaluator verified63 groups. Still failed; primary static model1/30 event hits; temporal0/30. Source lag matches intentionally exact in this version, which can leave many lag features NA for jittered timestamps.
- v2.2: added 36 source device physiology/quality summaries per anchor, bounded65min support (E4 HR minute-bin end can add1min); tolerant past lags10/25/50min. Independent evaluator verified63 groups. Static primary2/30 hits; temporal0/30; no stable event benefit beyond time baseline. Source HRV internal horizon remains unverified. Do not re-run these completed cohorts just to hunt a higher test score.
- New public data: all11 CC BY4.0 CSVs from Zenodo15309060 downloaded/checksummed in ignored `data/raw/smartwatch_hypo`. Unified downloader supports `--dataset smartwatch_hypo`; no download needed on this machine. CSVs contain processed wearable features, CGM, source labels, hour sin/cos, diaries; no full timestamp/day identifiers. Author code reviewed, not copied (no license found).
- `smartwatch_replication_v1`: true unseen-subject LOSO, only other participants train/validate. 33 groups independently verified to1.2e-16. Wearable+time macroAUC0.535/AP0.0627; paired AUC/AP improvements crosszero. Still inconclusive. No alarm/day or future-time claims.
- `smartwatch_personalized_v1`: first60% source rows train, next20%validate, last20%test;120-row purge each boundary. All11 retained;8 positive-test subjects give AUC/AP,3 single-class NA. Wearable+time AP0.1887 vs clock0.0980; paired AP gain0.09068 [0.00242,0.18449], unadjusted exploratory interval. AUC0.6131; AUC gain interval crosseszero; low point sensitivity. This is an early positive ranking effect, not a clinically useful alarm or verified prospective test. Hour-grid agreement audit≥.99 subgroup does not prove complete chronological timestamps.
- Aggregate ledger/report/card: `docs/IMPROVEMENT_REPORT.zh-CN.md`, `showcase/public/demo/improvement_data.json`, `showcase/public/cards/improvement.png`. Improvement page added. Desktop/390px, evidence drawer/Esc, no console error verified; screenshot in `docs/figures/improvement-showcase.jpg` and narrow version. v1's result artifact remains separate.
- All experimental processes for these four batches finished. Do not poll obsolete sessions or re-download raw data. Local preview session51420 should be stopped at teardown; check actual server before starting another.

### Next useful steps for the two-hour continuation

1. Complete final push/CI if not already recorded below; inspect current Git before mutation.
2. Design the next protocol before scoring: compare a contextual arm using source past meal/IOB records against wearable/time alone, keepingCGM excluded. Clearly label added manual-input burden; do not call it a pure sensor improvement. Inspect source timing and missingness first. Preserve the existing AP positive effect without claiming confirmed generalization.
3. PhysioCGM: prioritize verifying CGM/chest clock semantics, beat morphology and artifact handling. Adding coarse device summaries did not solve detection. Consult original research/open code licenses before adopting a reference implementation. No optimizing clock offsets against glucose outcomes.
4. Explore better alarm state persistence and calibration using training/validation only under a newID. Keep false alarms/day and whole-event missingness; no budget or denominator changes to force success.
5. Obtain a new independent timestamped dataset or original timestamp provenance for confirmation if available. Published source-row tests cannot support continuous-time alarm efficacy. Keep current heartbeat active until robust results or an explicit user stop; notify meaningful new evidence only.


## Publication closeout / 2026-10-17

- S5 local site, card exports, error/empty states, drawer and390px layout accepted; three-minute live recording remains explicitly pending (operation script provided). No medical alarm approval implied.
- Latest local suite:30 tests passed; previous GitHub headab4b30e passed Python + showcase build. Final improvement publication commit/CI checked at the end of this turn.
- Four improvement batches are complete and independently verified (63+63+33+33 groups). Positive AP effect remains exploratory; overall detection efficacy is not complete. No training process needs polling.
- Unified smartwatch downloader validated against all11 already downloaded files. Do not re-download here.
- Main manual updated toversion1.3 and current results; report/site/card contracts preserved. Keep heartbeat `t1d` active and continue the listed research steps.
