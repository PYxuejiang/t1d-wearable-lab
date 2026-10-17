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


Final verified publication: `b5b5e35` is pushed; GitHub Python tests and showcase build both passed. Local suite30 passed. Working tree was clean and tracked-data scan found no raw data, individual timelines, waveform excerpts or credentials. Owned preview server51420 stopped after QA. Heartbeat `t1d` remains active; all four experiment batches are complete, so the next run should start a new predeclared study rather than poll/re-run these finished commands.


## 2026-10-17 / contextual and calibration follow-up

- No existing completed experiment was re-run for model improvement. Audited source meal/IOB columns first: IOB is a unitless recorded injection-activity index, not insulin units. Subject13 lacks meal columns and has all-zero IOB; retained with explicit uncertainty.
- Original context120-row-purge attempt completed before the interrupt arrived; output quarantined BEFORE effect summarization/selection because nominal four-hour context plus15-minute label support exceeds241-row separation. No efficacy claim from that attempt. SeeCONTEXT_V1_ABORTED.
- Replacement `smartwatch_context_v1_1` uses150-row purge each boundary (301-row separation under nominal minute rows). Same full11 people,4 feature sets,3 learners chosen validation-only; raw/calibrated/training-prior test outputs. Missing timestamps remain a limitation; not true continuous-time evaluation.
- Completed and independently verified132 groups: source labels, same test rows, feature whitelist, candidate selection, validation-only thresholds, calibration refit and mapping, conservative row split. Max metric discrepancy1.2e-16; mapping discrepancy0.
- Primary combined-context AP0.1032 vs wearable+clock0.1561, paired difference−0.0529 interval[−0.1151,0.0104]; inconclusive, no supported positive contextual gain. Do not compare these means directly to old120-purge AP0.1887 because test ranges and training differ.
- Wearable+clock Brier raw0.1306 → calibrated0.0295; training-prevalence constant0.0278. Calibration fixes overconfident weighted scores but does not establish useful signal or beat the simple prior. Positive sigmoid maps cannot reverse rankings; clipped logits can create ties; nonpositive fits fall back to validation prevalence.7 sigmoid/4constant, including2 single-class validation subjects.
- Added protocol guard to reject insufficient four-hour context purge.35 local tests passed. Report/card/plot atdocs/CONTEXT_REPORT.zh-CN.md,showcase/public/cards/context-calibration.png,docs/figures/context-calibration.png. Updated historical personalized record's wording: early subject reference labels ARE used; scientific metrics unchanged. Both old AP positive effect and new negative experiments are retained.
- Current run `outputs/smartwatch_context_v1_1` is complete; do not re-run to hunt test scores. Next priority is source-clock evidence and signal morphology/SQI under a new predeclared design, not indefinite context/learner stacking. Three-minute live recording remains pending.

## 2026-10-17 / fixed ECG capture pilot

- Froze `configs/ecg_capture_pilot_v1.json` before download/scoring: MIT-BIH v1.0.0 records100/101/103/105, channel0, all complete nonoverlapping5min windows,2s common edges,150ms one-to-one tolerance. Includes all registered beat symbols, not onlyN. No glucose labels or tuning.24windows,118.4scored minutes,48method groups.
- All12hea/dat/atr files verified against officialSHA256SUMS.txt. Main-site100.dat transfer was slow and stopped without producing a file; completed from official documented publicS3 mirror. Raw files remain ignored indata/raw/mitdb_pilot. WFDB4.3.1 installed only inignored outputs/signal_runtime venv withsystemsite dependencies; original training environment unchanged.
- Both original energy peaks and defaultXQRS passed frozen pilot gate: perrecord sensitivity/PPV≥95%,24validHR windows,meanHRMAE≤3bpm. MacroF1 .996641/.997719;HRMAE .034676/.035289bpm. Modest capture difference, no HR improvement supported. Matched timing errors also independently verified; better peak location is not a demonstratedHRV improvement.
-48groups independently checked: rawsource annotations, fixed windows/edges, allrecord coverage, maximum-cardinality bipartite matching counts, separate binary-search chronological timing pairs, HR and gate arithmetic. No reuse of runner metric functions in verifier. Source/config/code hashes recorded.
- No replacement ofPhysioCGM features and no PPG/hypoglycemia/alarm efficacy claim. Two methods already capture well onthis convenience sample; do not blame weak glucose detection on this result or claim all48MIT-BIH records passed.
- Report/card/plot atdocs/ECG_CAPTURE_REPORT.zh-CN.md,showcase/public/cards/ecg-capture.png,docs/figures/ecg-capture-pilot.png. Context experiment remains a separate negative result. Improvement ledger includes allseven stages, preserving originalAP finding and failed event evidence.
-39local tests and showcase productionbuild passed. Context/calibration commit `e7f2187` pushed; GitHub tests/showcase both success. Pilot publication/CI completion recorded at final closeout below. Three-minute live recording remains pending.
- Signal section checked in desktop and375px viewport:48-group evidence drawer/Escape, report/card links, no console errors; mobile table scroll is local, no page overflow. Screenshotsdocs/figures/ecg-showcase.jpg andecg-showcase-mobile.jpg; sharePNG and plot visually inspected. Improvement run`improve-916205fa21ce`,capture card`ecg-1bfbd56876dc`,context card`context-60c99552ce78`. Originalv1 run`t1d-26c297decb6a`unchanged.

### Next continuation

1. InspectGit,latestCI and actualprocesses first. Completed context and pilot outputs must not be retrained/re-scored to hunt results. No long-running analysis remains.
2. Freeze a broader ECG/noise and RR/HRV quality study before scoring; four convenience records are insufficient for target-device accuracy. Separately audit PhysioCGM raw waveforms, clipping/artifacts, pairedcapture agreement and retainedcoverage. Agreement is not correctness without expertreference.
3. Investigate originalCGM/chest time provenance without choosing shifts by glucose scores. No clinically reliable event goal can pass while criticaltime semantics remain unsupported.
4. Only after signal/quality gates, version a new label-independent feature/SQI extraction and compare same-subject test opportunities with all failed baselines. Mark reuse ofseen T1D cohorts exploratory and keep missing-event/falsealarm denominators.
5. Keep heartbeat `t1d` ACTIVE every2h. Next notification only for meaningful evidence, failure or required action; no unchanged routine status. Do not upload source data, waveforms, individual predictions or credentials.
