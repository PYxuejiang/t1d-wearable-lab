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

### Verified publication closeout

Code/result commit `f62e0e0` pushed to public origin; GitHub `tests` and `showcase` both completed successfully. Local suite39 passed. Tracked-file scan found no raw/private outputs. Owned browser tab8 and preview server49604 closed; no analysis/preview session remains to poll. The following journal-only commit records this verification. Heartbeat`t1d` confirmedACTIVE every2h. Main manual updated through§15.3. Next run begins a new frozen signal/quality protocol, not a repeat ofcompleted context or capture experiments.

## 2026-10-17 / user-directed method and parameter revision

- User explicitly requested careful metric improvement, added analysis and adjusted parameters. First audited existing train/validation only: wrist coverage constraint, sparse observable events and pointAP/event decision mismatch. Kept all observed labels/events and previously failed results.
- Froze `configs/mechanism_v3_1.json` before new test scoring. Six arms: clock, compactpersonal physiology, activity residuals, pooledresiduals, ECGfailover, and union-missingness+clock control. Ten fixed hyperparameters;240inner candidates saved. Fit normal baselines/activityRidge only with earlier training reference labels. Inference has noCGM input.
- Inner chronological75/25 inside outer training,60/15min full-support purge chooses hyperparameters. Outer validation chooses4alert policies,101quantile thresholds and1/2day budgets; personal and pooled calibration separate. All model/policy choices written to `selections_frozen_before_test.json` before test scoring. No further training or threshold changes after this run.
- Preserved v2.1 outer splits/events/opportunities. No peak extractor or rawwaveform change. Wrist availability unchanged. ECGfailover and maskcontrol use wrist OR complete/validECG, missingmodality values masked. Shared training uses equal person totals; every test person supplies early reference labels, so notLOSO or zero-label personalization.
-336test groups (7people×6arms×2calibration modes×2budgets×2views) independently verified. Also independently checked innerAPs/parameterchoice, allstored decisioncandidate ranks and63distinct selected validation configurations, source labels/timebounds, scoreavailability, current-event matching, alarms/falsealarms/delay/timecoverage. Maxmetricdifference1.11e-16. Verification first exposed only JSONnumpy-integer serialization, fixed without re-training or changing any result. Diagnostics extension also uses frozen scores only.
- Coverage improves from.728007 to.828446, paired+10.04pp exploratory95%[2.54,21.46]pp. Observable events25→27of30. This adds a chestsensor and changes training opportunity, so a strategy-level availability gain, not isolated hardware accuracy or wrist-only detection success.
- Predeclared primary pooledfailover/commonvalidation/budget1:0/30hits,.042234unmatched alerts/reference-person-day,macroAP.07353,AUC.58327. Model selected innerlogisticC1balanced; validation chose originaledge threshold.8325967. All30events retained; primaryeffectFAILED. Secondarybudget2:2/30hits,macrorecall17.1%,FA1.858/day; notsubstitute for budget1. Micro2/30=6.7%, never label17.1% as overallcountrecall.
- Primary miss audit:3noinput,26score neverabove threshold,1highscore but no event-timealert. Sole unmatched alert within30min BEFORE recordedonset remains a detectionfalsealert. Fixedpolicy perfect-point counterfactual23hits is descriptive, not an algorithm result or a universalmaximum. Sourceclock assumption unresolved; never choose timeoffsets against disease scores.
- End-to-end AP deltas between different input masks omitted; common-wrist AP deltas and same-union maskcontrol retained. All policies/modes/budgets and per-person metrics retained inV3_MECHANISM1, not only better outcomes. Previously viewed cohort, all exploratory/unadjusted.
- Reports `docs/METHOD_CHANGE_V3.zh-CN.md`, `docs/MECHANISM_REPORT.zh-CN.md`; acceptance `docs/acceptance/V3_MECHANISM1.json`; plot/card `docs/figures/mechanism-v3.png`, `showcase/public/cards/mechanism-v3.png`. Run`mechanism-59d894d8c717`,ledger`improve-b56995f64e8e`; v1 evidenceunchanged. Mainmanualversion1.4 updatedthrough§15.4.
-45local tests passed; productionbuild passed with existing largebundle warning. Desktop and375px panel/evidence drawer/Escape/links/no-console-errors checked. Currentviewport screenshotsonly: fullpagecapture unsupported inthis browser session; ordinaryscreenshots atdocs/figures/mechanism-showcase.jpg,mechanism-detail.jpg,mechanism-mobile.jpg; exportedcard andplot visually inspected. No raw patientrecords inpublishedassets.

### Next work after this completed batch

1. Do not rerunV3 to hunt scores. All analysis completed; no training to poll. CheckGit/CI and actualprocesses. Owned preview8353/browser tab9 are temporary and shouldclose at final teardown.
2. Highest priority: independently audit sourceCGM/chest/wrist temporal semantics, ideally match original and author-processed pairedsegments bysource times/values. Do not optimize clockshifts by glucoseclassification. Checkrecordunits, reference labels and censoring against descriptor.
3. Only after new alignment/information evidence, freeze an RR/morphology-quality or alternateendpoint study.26/30primarymisses belowthreshold means changing onlycooldown is insufficient; do not keepunbounded parametersearches onseen tests.
4. Keep positivecoveragegain andoldsmartwatchAPeffect with explicit limits, not clinicalclaims. Mainincident/detection goal stillunachieved. Heartbeat`t1d` ACTIVE every2h; notify meaningful changes only. No patient data/individualwaveforms/predictions/credentials uploads; no personalwatchmigration or messages to others.

### V3 verified publication closeout

Code/results commit`400ecc5` pushed; GitHub`tests`and`showcase`both completed successfully. Local45tests/build passed, trackedraw/private-file scan empty, workingtree clean before this journal-only follow-up. Firstpush hadtransientTLS handshake failure; ordinary retry succeeded without changing TLSverification. Ownedpreview8353 andbrowser tab9 closed. No activeanalysis session remains; completedV3outputs must not be rerun. Next step is source-time/label provenance audit under a new protocol. Heartbeat`t1d` remainsACTIVE.

## 2026-10-18 / source provenance and modality-expert follow-up

- User requested continued performance work with existing methods. Read pinned author PhysioCGM commit6940f1d587f8f68b131cf129d5a9f65237f61fcc and original paper plus2026HR/GSR preprint. No third-party code copied into repository. Author uses hostlocaltime forE4, naiveCGM/chest clocks, waveform modality experts and stratifiedfolds; cannot borrow its scores as chronologicaleventperformance.
- SOURCE_TIME1: fixed smallest numeric processedpickle per10subjects, independent oflabels. BoundedHTTP206ranges,ZIPmemberCRC/SHA256; fullprocessedZIPMD5 NOT verified. Restrictednumpy/pandastimestampunpickler, arbitraryglobalsrejected/tested. Originalfullrawarchives alreadyverified. All10probesCGMIndex/time/value match, firstchestsummary matches, ECGsamplesall≤CGM and within330s.3probes have unique16pointE4 matches, offsets−18000s agreeexistingc1s01/c1s05/c2s04 shifts;7probes lack usablewristsequence, no inference for them. All34,218existingfeatureanchors match sourceCGMvalues/labels. PhysicalCGM/chestzerooffset stillunverified. No shifting/quarantinechanges. Rawprobes/authorsource remain ignored outputs/source_audit_v1.
- V4_LATE_FUSION1 frozen before scores.7arms×2weightings×2budgets×2views×7subjects=392groups. Existingv2.1features/splits and60minhistory/15minreferencepurge unchanged.3modalityexperts, earlyfusion, meanfusion, fixedC0.1logisticstack, maskclockcontrol.30internalcandidate records; LR C.1/HGB7leaves/ExtraTreesdepth5. Equalperson/class weight; pointvscontiguouslowrun/negative6hblock weighting. Brief lows retained, notonlyconfirmed15minevents. Groups/weights trainingonly.
- Experts selected from earliertrain75/25 purgedholdoutAP. Stack fit onlyselected out-of-fitinnerpredictions; expertsrefitfulloutertrain. Hyperparameterselection andstackfit shareinnerholdout; refit may shift scoredistributions, explicitlimitation. Outer earlier validation selects4policies×101quantiles under1/2FA/daybudgets. Entireselectionfilewrittenbeforetestscores; runnerrejectsexistingoutput. No postresultretraining. Joblibphysicalcorewarning only, fellbacklogicalcores; trainingfinishedsuccessfully.
- Independentverification392groups,30innercandidateAP/ranks,28selectedvalidationoutcomes, labels/splits/inputends/availability, lowrunweights, fusioninputs andstackrefit. Maxmetricdifference1.11e-16,stackscore2.39e-15. Verifier additionally computes posthoc PPG/EDA samewristmask contrasts fromfrozenscores, explicitlydescriptive; no changes toselections. All30testevents retained.
- Prespecifiedprimary late_stack/run/b1/end_to_end:0/30,macroAP.0968515,AUC.532913,FA.126703/day,coverage.828446. FAILED. ComparedstackpointAP.0755107→.0968515,paired+.0213408 CI[.00409246,.0437051] unadjustedexploratory. Stackpoint had1/30hits, so APgain doesnotimprovealarms. APagainstearlyrun/maskclockrun intervals crosszero. Same3/26/1primarymissdecomposition remains.
- RegisteredPPGpointcomparator3/30,total10%,macro6.9388%,FA.717985/day,coverage.728007. Hitsonlyc2s02(1)andc2s05(2);5otherszero. SelectedlogisticC.1 andconfirm2 threshold.6818246 onvalidation. Notnewprimary, not80%recall/coveragepass. PosthocPPGpointAPgainvsmaskclockcommonwrist+.02554CI[−.01214,.07972], uncertain. Keepall14routes andbudget2 results; no cherry-picking.
- Artifacts: docs/METHOD_CHANGE_V4.zh-CN.md,docs/LATE_FUSION_REPORT.zh-CN.md,acceptance/SOURCE_TIME1.json andV4_LATE_FUSION1.json. Plot/card exported; fusion-3dd63bc863f8, ledgerimprove-25aa77a847ce; originalv1rununchanged. Mainmanualversion1.5 through§15.5.51localtests andproductionbuildpass; existinglargeJSbundlewarning remains.
- UI14rows,392groupevidencedrawer/Escape,1280pxdesktop and375pxresponsive(no documentoverflow),consoleerrors[] verified. Ordinaryscreenshots docs/figures/fusion-showcase.png andfusion-mobile.png; PNGcardviewed. Temporarybrowser2/tab2closed andviewportreset. Ownedpreview20339 shouldstop atcloseout.3minlive recordingstillpending. Heartbeatt1dconfirmedACTIVE every2h; no automationupdate needed.

### Next continuation after V4

1. Do not rerunV4/sourceprobes. Allanalysiscomplete; no modelprocess to poll. CheckGit/CI and actualprocesses.
2. Freeze nextrawPPGshortwindow morphology/RR/SQI study. Sourcealignmentconsistency nowdocumented butphysicalclockstillunresolved; no scoreoptimizedshifts. No expert reference means agreement only, notaccuracy.
3. Preserve7people,allmissinginputevents andonlytrain/validationselection. PPGsuccessin2people doesnotjustify dropping5failures. Avoid unboundedcoarsefeaturesearch; independentdata ornewqualityvalidatedfeatures needed.
4. KeepAPimprovement andnegativealarmevidence separate. Module1 CGM-assistedwork can be a separatelyversioned study, notclaim wrist-onlyachievement. Heartbeat remainsactive; meaningfulupdatesonly; rawdata/predictions/authorsource/credentials notuploaded.

### V4 verified publication closeout

Code/resultscommit`ad0102f` pushed; GitHub`tests`and`showcase`both completed success.51localtests passed; productionbuild passed. Ownedpreview20339 stopped, no5173listener; browser2/tab2closed andviewportreset. Trackeddata/privateoutputscanempty; workingtreecleanbeforethisjournal-onlycommit. No training orverification process remains. Mainmanualversion1.5 updated, heartbeat`t1d` stillACTIVE every2h. Next run begins the frozen newinformation/quality study rather than rerunningV4 or downloadingfinishedprobes.


## 2026-10-18 / V5 PPG morphology protocol frozen; extraction in progress

Latest human instruction restricts algorithm development to PPG short-window morphology, pulse intervals and signal quality. This overrides older suggestions to work in parallel on module1 or ECG/EDA fusion. No new endpoint or participant selection.

V5_PPG_MORPH1 uses ten causal30s windows inside trailing300s raw64HzBVP,31descriptors and missing indicators. PPI successive differences preserve adjacency across rejected intervals. Three arms coarse/quality_time/morphology; same old wrist mask; fixed v4pointweights and3learners; innerAP then outervalidation4policies and1/2FA budgets;6operating points freeze before test. Same7subjects/all30events. Synthetic tests pass but real beat accuracy unvalidated. Current extraction is sequential, completed subjectparquets have hashmanifests; do not duplicate a live process or overwrite completed outputs.

Goal review docs/GOAL_REVIEW.zh-CN.md distinguishes engineering, information gain, optional future assistance and clinical alarm. Old80/1/80 is self-set research aspiration, notclinicalstandard; fixed72.8%mask makescoveragegate impossible. Future proposed+10ppmacrorecall at≤1FA/day is a project screening proposal, notappliedretrospectively or claimedclinicalmeaning. PLOS2025event60.4%/first15min36.6%, nocturnal2025minuteleveloutcomes andDexcomCGMproduct scope reviewed. No claimV5performance before run/verification.

54localtests passed; productionbuildpassed(existinglargeJSbundlewarning). PPGdisplaycomponent waits for verifiedacceptance data, so no inventedresult shown. Extraction running via session89695, logoutputs/ppg_morphology_extraction_v5.log. Follow extraction→run_ppg_morphology.py→verify_ppg_morphology.py→export_ppg_morphology.py→export_improvement.py, then results/UIacceptance andpublication.


### V5 extraction checkpoint / same algorithm, independent subject workers

Protocol commit0a144db pushed before model scoring; GitHubtests/showcase bothpassed. First3subjects completed with matching manifests. To reduce wall time, own sequential PID26588 was verified and stopped only after c1s03 manifest/parquet hash passed; no completed files discarded. Remaining4subjects now run separately using new --subjects argument, exactsame featuremodule/hash. Partial nextsubject work can be recomputed; no competing writer remains. Controller session58981/logoutputs/ppg_morphology_parallel_controller.log. Pipeline session48182 waits for all7 complete manifests, then runs model→independentverify→exports, logsoutputs/ppg_morphology_pipeline_v5.log. The old session89695 termination is intentional, not an algorithm failure. Do not launch duplicate jobs. Mainmanualv1.6 has protocol/goalreview and explicitly pending results.


## 2026-10-18：V5已完成，交互展示与每小时接续

V5_PPG_MORPH1已完成提取、训练、独立复算与导出，**不要重跑旧控制器或流水线**。42组测试、9个内层候选、6个选中验证工作点全部核对。三路使用同一腕部掩码和全部7人、30次事件；粗特征分数与V4精确复现。

主形态方案1/30命中，前15分钟0/30，17次未匹配报警/18次总报警，误报0.717985次/参考人日，覆盖72.8007%。旧粗特征对照3/30、前15分钟2/30。形态AP0.0770，对照0.0992；配对差−0.0222，按人探索性95%区间[−0.0814,0.0185]。**工程与评价通过，信息增益和原检测目标失败**。5次无输入、22次低于阈值、2次报警状态未触发；不能隐藏这些漏检。新增形态尚无专家搏动准确性验证，源物理时钟仍未解决。

下一阶段仅限PPG：先审计有参考心搏标注的公开基准与许可，冻结跨记录、活动分层的峰值/PPI/质量验证；先确认提取是否可靠，再决定是否回到低血糖模型。候选PPG-DaLiA/PPG-beats不是新疾病标签，也不是低血糖外部验证。无新证据不扩大固定特征参数网格、不按测试改报警阈值。旧80%召回/1次误报/80%覆盖目标保留；其属于内部目标，固定72.8%掩码无法过覆盖门槛。分层研究目标见GOAL_REVIEW，任何新门槛必须前瞻冻结，不能追认本轮成功。

用户要求接续间隔改为每1小时；原t1d自动任务已更新为ACTIVE，每小时推进算法和交互展示。首页改为原创三维概念手表与五步感知流程；复杂指标和历史证据保留在#research。动画是合成示意，不代表PPG血糖测量、已验证心律/呼吸异常或真实医疗通知。公开资产为自写模型、汇总验收和截图，患者数据仍仅本地。三分钟现场录屏尚未完成。

Independent verifier recheck passed; run ppgmorph-12455c7357cf, aggregate ledger improve-32b0b8f73297. No extraction/training process remains. Native automation update succeeded for existing t1d, interval1h.


### V5 + watch experience publication closeout

Code/results/assets commit `d79ab3870a52ff34375f804c5f1ac79286f9f776` pushed to existing public main. GitHub `tests` and `showcase` both completed SUCCESS. Local56tests and final production build passed (large lazy JS bundle warning retained). Public staging scan contained no raw/private data paths. V5card and 1280×900/375×812 product views visually reviewed; evidence navigation style leak fixed, auto journey/reminder/color/scenario controls checked; browser console errors empty. Details and limitations in WATCH_EXPERIENCE.zh-CN.md. Owned Vite session35700 stopped with Ctrl-C; owned QA tab2 closed and viewport reset. No model rerun was started. Global psutil network enumeration was unavailable on this host; server-session termination was confirmed directly. Manual v1.7 updated outside repository. Existing hourly heartbeat is ACTIVE. Next continuation starts annotated PPG quality/beat benchmark audit, not completed V5 extraction or model jobs; recording still pending. This final journal-only change does not change tested implementation or results.


## 2026-10-19 / PPG_DALIA_AUDIT1 completed

No active PPG jobs; V5 remains complete. Downloaded only fixed sitting/walking MAT files from Zenodo12793711; published MD5+size verified, localSHA256 recorded. Sitting15records/2.5403h/9,263ECG R peaks; walking14records/2.6087h/15,458peaks, S6 absent in source.29records, no detector scoring. Integer increasingRpeaks andfinitePPG do not establish signalaccuracy. HRsummaryoffsetunknown; bothzero/onebasedboundsvalid, indexing andpulse/filterdelay mustbe explicitlyhandledbefore scoring. MATLABconverter preservesfirstactivityepisode, notalltime. UCI/ZenodoCCBY wording differsolderuniversityscientificnoncommercialtext; dataremainlocal, no commercialredistributionclaim. PPG-beatsalignmentGPL distinctfromdocumentationlicense, no copiedcode. Source report docs/PPG_DALIA_AUDIT.zh-CN.md and aggregate acceptance/PPG_DALIA_AUDIT1.json. Next: freeze beat-matching/lag protocol andindependentverifier onfixeddevelopmentS1–S5, evaluateheldoutS6–S15 onlyafterfreeze; no glucoseendpoint. FullV5andwatchcodecommitd79ab38CIalreadygreen. Hourlyautomationactive. No repeat downloadsneeded; audit script validatescachedfiles.


## 2026-10-19 / PPG_CAPTURE1 completed; no detector improvement

Frozen code/protocol32c7b1d pushed before scoring. Fixed V5 short-window peak rule versus original dual-moving-average adaptation ofElgendi2013; common causal0.5–5Hz filter,30s windows,27s cardiac-time cores. S1–S5development10records, S6–S15heldout19records (S6walking absent). Eachrecordfirst120s ECGreference selects shared0–0.6s lag; this is offline reference-assisted, not standalonewearable performance. FiveSQI candidates frozen before heldout; threshold0 selected, highergates faildevelopmentwalkingcoverage. No ECGinput to detector andno glucoseendpoint.

607windows and464metricgroups independently checked, including rawsourceRpeakwindows, calibratedlags, allSQIcandidates, one-to-one counts via dynamicprogramming, adjacentPPI and HR errors. Initialverifierexactfloatcomparison failed due5.55e-17 summation-orderdifference; tolerance corrected to1e-12, originalfailedlog retained, no method/prediction/selection changes. Do not rerun extraction; ignoredoutputs/ppg_capture_v1 complete.

HeldoutmacroF1 .4777299→.4758344, paired−.0018955 CI[−.0044216,.0007305]; no stablegain. HRMAE4.809→5.387bpm; matchedadjacentPPIcoverage30.31%→29.93%. The ~41msPPIerror is conditional, notfullreferenceaccuracy. Fixed200ms F1 .1568→.1475; unadjusted .1959→.1880.5/19heldoutrecords calibrate at upper0.6s bound, so F1 mixes detector errors with unresolvedrelative/filterdelay. Do not conclude wristPPGintrinsically48%accurate. Coretimecoverage88.0% is a different benchmark denominator, notPhysioCGM72.8% improvement. V5remains1/30failed. Fullreport docs/PPG_CAPTURE_REPORT.zh-CN.md, cardppgcap-aef624ada333; oldresearchpage linksadded, homepage remainsminimal.

Next onlyPPG: onfixeddevelopmentS1–S5 audit raw/filtered pulse timing and calibrated-lagboundary withknown syntheticdelay andpublishedE4timing. Freeze a newalignmentprotocol before further scoring. Existingheldout is nowseen; furthersamecohortchanges exploratory. No broadercoarsefeaturetuning or ECG/CGMdiseasefusion. Preserve allfailedmethods/SQIcoverage. Hourlyautomationactive; no activeanalysisjob expected after verification.


### PPG_CAPTURE1 发布前验收收尾

63项本地测试通过；最终网页生产构建通过，保留两个懒加载包超过500KB的警告。研究证据页新增报告和成果卡入口，桌面及375×812竖屏验证无横向溢出，浏览器错误日志为空；截图保存docs/figures/ppg-capture-links.png。早先自动审批检查因用量限制中断临时页清理，2026-10-19恢复后已重置视口并关闭自建tab4；未关闭用户tab1/tab3。自建Vite session55018已结束，实际进程检查未发现PPG训练/提取任务。本轮未重新提取或重训，下一轮沿用完成文件做开发集时间对齐核查。

发布前自动审批拒绝了包含逐记录指标的初版上传；未发送成功。修订导出边界：逐记录验收、开发集逐记录偏移及候选逐记录指标全部保留在忽略目录outputs/ppg_capture_v1/acceptance_local.json；公开仅群体/活动汇总、候选群体分数、区间、哈希与计数。修订未发布的本地提交后再上传，避免原逐记录文件进入远程提交历史；数值结论不变。独立复核再次通过，增加公开文件无逐记录字段的验收约束。


### 2026-10-19 用户网站验收修订

仅展示层：成果/差距/下一步文案，完整对照折叠；移除平板式长表带，三色GLB同步更新；内置image_gen生成工作/生活/睡眠场景并随状态切换。详情见WATCH_EXPERIENCE；图片与提示词一同版本化。算法、验收JSON及历史失败结论未改，不重跑实验。生产构建、桌面/手机布局和关键交互通过。预览为用户验收后台进程，勿按研究临时服务清理；只监听127.0.0.1:5173。下一算法仍是开发集PPG时间对齐审计。

用户进一步验收发现背景右沿遮挡文案：已扩大背景并加入右向透明渐变，watch-stage与caption建立独立层级，文字在上层；移动端背景约束于表体区域。1440桌面及375竖屏复核无横向溢出，手机文字起点比表体底部低28px。截图docs/figures/lifestyle-gradient-desktop.png。


## 2026-10-19 PPG_TIMING_DEV1完成

开发集S1–S5共10记录211窗，复用现有峰值，不改疾病模型；执行前协议557ea1b。首120秒校准范围由0–0.6诊断为±1.5秒，固定4–26秒评分核心、尾段冻结偏移。静坐F1 .4112→.5871，步行 .3818→.4760；5人配对差+.1350，探索性95%区间[.0114,.2729]。这是对齐敏感性，不是检测器改善。8/10校准在旧范围外；2/5步行有近似等分的远处偏移，存在整搏混淆。分块偏移变化中位80/90ms；合成滤波峰移随脉宽变化，真实未滤波/滤波峰配对不是时钟真值。独立验证20个校准选择、20组尾段计数，同参考分母。公开仅群体汇总，逐记录在ignored outputs。

下一步仍仅PPG：开发集整搏混淆、峰/上升沿与不同校准段稳定性，先冻结对齐协议再同队列探索验证；不回到低血糖模型、不按留出成绩挑时移、不删除歧义记录。完整报告PPG_TIMING_DEV_REPORT.zh-CN.md。已完成输出勿重复长任务。

本轮全套测试首次62过/1失败，原因是前次无表带设计仍被旧GLB测试要求StrapTop/StrapBottom/BandFinish；已同步为实际表体与传感器节点，保留GLB格式、完整性、哈希、材质和三角形检查。不是算法或数值失败。

修正资产验收后63项测试全部通过。评分核心时间覆盖静坐73.08%、步行70.73%（校准后原始时间为分母）。成果卡ppgtime-336a9d5b6e07与报告加入研究证据页；卡片只含群体汇总，已目视核对。

## 2026-10-19 GitHub Pages 上线

用户要求网站放到GitHub。提交2eaf669启用Actions发布与相对资源路径；Pages部署39194417360及CI39194417295均成功。公网地址 https://pyxuejiang.github.io/t1d-wearable-lab/ 。HTTP首页200，手表GLB、三场景图、两公开汇总及新成果卡200；两本地个体回放路径404。浏览器成功读取首页、结果汇总及导航，进一步交互截图调用超时，未声称完成线上视觉/交互复验。仅干净checkout构建发布，禁止上传本地dist（其中可能含ignored个体回放）。主站后续showcase更新自动部署，算法任务范围不变。


## 2026-10-19 PPG_STABILITY_DEV1完成

执行前协议/脚本9e118ce冻结。5名开发受试者10记录211窗，仅复用PPG峰缓存。0–60、60–120、0–120秒三校准方案固定用于相同尾段；未按尾段选方案。静坐F1 39.27/59.22/58.71%，步行39.37/49.18/47.60%；两一分钟校准偏移相差≤100ms分别2/5、4/5。按人尾段F1平均绝对差25.88个百分点，探索性95%区间[15.10,42.33]；是评分敏感性，不是算法增益。完整两分钟校准步行2/5有近似整搏周期竞争偏移，未触±1.5秒界不等于物理同步。评分时间覆盖静坐73.08%、步行70.73%，全部记录保留。

独立复核30次校准选择、30组尾段计数/PPI与群体汇总、按人区间通过；逐记录仅ignored outputs/ppg_stability_dev_v1，勿重复长任务。报告PPG_STABILITY_DEV_REPORT.zh-CN.md；成果卡ppgstable-255be8015c05。下一步仅开发集PPG峰/上升沿、校准平台和残差核查，先冻结协议；不再把靠近200ms的最大匹配数偏移视作唯一物理同步证据，不根据尾段挑规则。尚无新疾病事件、误报、及时性结果，V5及旧对照保持。

本轮完整pytest验收63 passed；新成果卡已目视核对。公开JSON只含群体/活动汇总与合成控制，不含逐记录偏移、波形或峰值数组。


### PPG直接人工标注入口已取得（2026-10-19）

在稳定性诊断后进一步核查作者公开pyPPG标注包，已下载v1 PPG-BP_annot.zip 7.17MB并核对官方MD5；Zenodo记录CC-BY-4.0。结构审计确认219唯一信号条目、两套各219汇总标注、1000Hz、2.1–4.2秒；不是连续腕部波形，不能原样套现有30秒检测器。只读结构验收通过，未评分。详情docs/PPG_BP_ANNOT_AUDIT.zh-CN.md与acceptance/PPG_BP_ANNOT_SOURCE1.json；数据留data/ppg_bp_annot，不重复下载。下一步优先审计采集部位、标注预处理、时间/索引、空标签和标注者一致性，冻结短片段定位协议，再做PPG-DaLiA开发集峰/上升沿核查。不得拼接短片段伪造长记录，不把专家边界内定位当连续检出，不将此类信号成绩当疾病效果。


## 2026-10-19 PPG_LABEL_AUDIT1完成

预先冻结a9ea490，219条两套标注1752字段独立复核；汇总与merged MAT完全一致。严格单pk解析仅34/219配对，原因主要为邻搏多峰，不能称其余全部缺标。事后数量诊断：自己的os内恰一pk，MG219/219、PC218/219；PC1条os/u数量异常，保留不删。on/off/u均218配对，MAE3.208/3.472/1.119ms，仅标签差不是算法误差。原论文说明高质量指端单搏、12Hz人工标注滤波、>10ms分歧讨论；最终两套差异不应说成未经协商的独立标注可靠性。作者代码以round(t*fs)索引且使用专家边界，不能把其条件定位当连续检出。包内少数峰备注提示不确定性，未据此删记录。

公开docs/PPG_LABEL_AUDIT_REPORT.zh-CN.md、acceptance/PPG_LABEL_AUDIT1.json、成果卡ppglabel-168ed26d5dcf；本地outputs/ppg_label_audit_v1完整，勿重跑主审计。后续先冻结专家边界内单搏条件定位协议（目标峰/上升沿，两套标签和全部219覆盖），再回PPG-DaLiA开发集；不以当前标签MAE宣称新算法、腕部或低血糖效果。事件召回、误报、及时性和疾病PPV均无新结果。网站仍GitHub Pages自动发布。


## 2026-10-19 PPG_FIDUCIAL1完成

执行前05388c7冻结；219条指端精选单搏按名称哈希分70开发/149评价。MG专家边界作为明确输入，不输入参考pk/u；开发MG两类MAE选择offline12。评价MG峰MAE：raw12.178、causal5 43.979、offline12 7.741ms；上升沿24.319、63.984、2.791ms。PC分别12.735/42.911/8.937与24.290/63.631/3.035ms。MG参考149/149、PC148/149；全部保留、输出率100%，不是连续覆盖。MG峰≤50ms由raw98.66%降至97.32%，不可只报均值。

相对未补偿causal5的MG配对平均MAE差−48.716ms，按条目探索性95%区间[−55.945,−43.460]。这混合频段、相位、短片段滤波初始化影响；causal5上升沿偏差+63.984ms，不能说全部是检测器改善。双向用未来样本、专家边界、指端精选单搏及已见标注资源，均限制推论。未产生新的腕部连续检出、PPI、SQI拒绝或疾病报警效能。

独立MAT解析/极值/导数复算657组预测、438参考映射、24指标组、6区间和开发选择通过；3个合成控制通过，共享SciPy滤波内核已披露。主结果在outputs/ppg_fiducial_v1，勿重跑。公开PPG_FIDUCIAL_REPORT.zh-CN.md、acceptance/PPG_FIDUCIAL1.json与定位成果卡，只含群体汇总；研究页更新，首页不堆数据。V5及全部旧失败不变。

下一步先冻结5/12Hz与因果/双向分解对照，延迟修正仅开发估计，评价只作已见资源探索；关注尾部，随后回PPG-DaLiA固定开发人群核查独立找搏和整搏歧义。不要将专家边界定位成功追认为腕部或低血糖达标，不根据已见评价扩大搜索。

本轮完整pytest 63 passed；生产构建通过（保留既有大分块提示）。成果卡ppgfid-28eb3194faf8已目视核对。公开仅群体定位误差/区间/计数/哈希；个体坐标与预测留在忽略目录。


## 2026-10-19 PPG_FILTER1完成

执行前26a033b冻结；前次因自动审批额度未能执行，本次审批恢复后首次计算。固定219条、70开发/149评价，7路全公开、不选胜者。两路因果pk/u全局偏差只取开发MG中位数；全部校正结果计分、不裁剪。MG评价causal5的u MAE63.984→2.107ms，说明很大部分为固定定位偏移；常数校正不改变PPI，不能称找搏能力改善。

双向12Hz相对5Hz的峰/u平均MAE差−3.767ms，探索性95%按条目区间[−4.631,−2.873]。因果两路校正后12Hz反而平均高1.043ms [0.508,1.609]，不支持直接将所有链路改12Hz；峰差区间跨零。12Hz校正后1/149出界保留；MG参考149/149、PC148/149，输出149/149不等于时间覆盖。滤波双向改变幅频及边缘状态，非纯相位消融。旧三路完全复现，原低血糖失败与指标不变。

独立MAT与极值重算1533组预测、4开发常数、56指标组、30区间通过；两个合成控制通过。报告PPG_FILTER_REPORT.zh-CN.md、群体acceptance/PPG_FILTER1.json与成果卡；本地outputs/ppg_filter_v1完成勿重跑。公开没有条目身份/坐标/个体预测。下一阶段回到PPG-DaLiA固定开发受试者，先冻结无人工边界的PPG峰/上升沿配对和整搏歧义诊断，不能把指端固定偏移直接移到腕部；不继续扩张指端参数网格、不切回疾病模型。

本轮pytest 63 passed；生产构建通过，保留既有分块大小提示。成果卡ppgfilter-e2d145a85568目视核对通过。


## 2026-10-19 PPG_UPSTROKE_DEV1完成

运行前c835357冻结。原5开发人、静坐/步行10记录211窗，复用7954峰，仅从PPG独立定位上升沿；不输入专家边界或指端固定偏移。243个非严格谷/u/峰次序候选保留。三校准方案全公开；首120秒静坐F1 58.71→70.16%、PPI覆盖46.00→60.49%，步行F1 47.60→43.76%、PPI覆盖27.54→25.02%。按人两活动平均，F1差+3.81pp [−2.18,10.21]、PPI覆盖+5.98pp [−1.65,14.32]，均跨零；不能说稳定总体改善。条件PPI MAE静坐35.94→25.65ms，步行44.53→48.35ms。

固定核心时间覆盖静坐73.08%、步行70.73%；上升沿首120秒静坐1/5校准触边、步行1/5整周期歧义。两个一分钟偏移稳定≤100ms记录静坐峰2/5、u3/5；步行峰4/5、u2/5。ECG仅参考辅助匹配，非物理同步或上升沿真值。候选数量固定、窗口含等待，不等于连续在线检测或新疾病结果。

独立MAT复算211窗7954定位、60次校准、60组尾段计数/PPI及2个按人区间通过；旧峰基线精确复现、所有参考分母一致。本地outputs/ppg_upstroke_dev_v1完成勿重跑。公开报告PPG_UPSTROKE_DEV_REPORT.zh-CN.md、acceptance/PPG_UPSTROKE_DEV1.json及成果卡仅聚合；更新研究页，首页不堆数据。V1–V5失败和临床指标不变。

下一步先冻结活动分层的候选形态/质量诊断，核查步行非严格次序、位移和漏/多搏来源；不按尾段删记录或扩大粗特征参数搜索。若尝试质量拒绝，同时报告全部参考分母、保留时间及被拒部分，不以拒绝换取虚高精度。

本轮pytest 63 passed；生产构建通过（保留既有大分块提示）。成果卡ppgupstroke-5b8710dacf7b目视核对通过。


## 2026-10-19 PPG_QUALITY_DEV1完成

执行前2c1b48c冻结，复用PPG_UPSTROKE_DEV1全部缓存与固定偏移，不重跑检测。5开发人10记录211窗7954候选；尾段固定核心171窗5119候选。固定三个错误风险分数全部报告：非严格次序AUC静坐0.5153/步行0.5072；校准段位移偏差0.7204/0.5085；1−旧SQI 0.7528/0.5580。按人两活动平均分别0.5113 [0.5021,0.5207]、0.6144 [0.5813,0.6382]、0.6554 [0.6196,0.6958]。标签为参考辅助未匹配，并非伪迹真值；5人已见开发探索，不能称疾病效果。

步行尾段次序异常仅覆盖91/1718=5.30%未匹配候选（逐记录宏平均5.75%），静坐17/539=3.15%。静坐1条无异常，其异常未匹配率按4条算且明确报告。位移IQR按记录宏平均静坐21.88ms/步行62.50ms。异常标记不能解释大部分错误，简单位移偏差和现有SQI在步行分辨力有限。全部候选保留，未选阈值、未翻转AUC、未拒绝数据；时间/PPI覆盖及疾病指标不变。

独立复算171窗5119候选、30个AUC、3个按人区间及4个合成AUC控制通过；旧上升沿逐记录计数精确复现。输出outputs/ppg_quality_dev_v1勿重跑；报告PPG_QUALITY_DEV_REPORT.zh-CN.md、汇总acceptance/PPG_QUALITY_DEV1.json和成果卡仅聚合，研究页更新。下一步先冻结校准段分位阈值的质量保留率/错误代价诊断，所有工作点、真实搏动损失、时间覆盖、原参考分母一起报；不得按尾段选阈值，不直接部署质量拒绝。V1–V5全部证据保持。

本轮pytest 63 passed；生产构建通过（既有大分块提示保留）。质量诊断卡ppgquality-447346d90c60目视验收通过。


## 2026-10-20 PPG_RETENTION_DEV1完成

前次自动审批额度限制未执行；本次恢复后d0fba77先冻结协议/脚本并首次计算。仅原5开发人10记录171尾窗，首120秒4窗SQI的q25/q50/q75阈值加baseline全报告；无尾段选择，参考搏/PPI分母始终完整。独立复算30阈值、171窗、40记录工作点、4按人区间及零输出控制通过，baseline精确复现。

预设q50按人平均：输出PPV+7.71pp [3.52,12.47]，全参考敏感度−23.58pp [−31.44,−13.76]，PPI覆盖−18.57pp [−26.26,−9.61]，核心时间覆盖−28.26pp [−35.28,−18.33]。步行PPV45.87→49.60%，敏感度42.35→26.31%，核心覆盖70.73→47.37%，PPI覆盖25.02→13.64%；条件MAE48.35→48.68ms。q50步行移除418原FP同时丢580原TP，静坐290/675。全部筛选点活动宏F1均下降；不启用现有SQI整窗拒绝、不扩大其阈值搜索。

本地outputs/ppg_retention_dev_v1完成勿重跑。报告PPG_RETENTION_DEV_REPORT.zh-CN.md、群体acceptance/PPG_RETENTION_DEV1.json及成果卡公开；网站研究页、手册已同步。原疾病指标和V1–V5不变。下一步先冻结候选级局部模板/相邻间期一致性定义，对照已有窗级SQI，校准/训练内定规则，全部尾段评估有效搏动保留与错误排序；先证明信号信息增益再考虑筛选，不切新融合/疾病终点。

本轮pytest 63 passed；生产构建通过（既有大分块提示保留），成果卡ppgretention-ebf1cc412660目视验收通过。


## 2026-10-20 PPG_LOCAL_DEV1完成

77ca846预先冻结候选级形态/间期风险，仅首120秒PPG构模板和间期中位数。5开发人211窗7954候选全保留，171尾窗5119候选沿用已复核标签。静坐模板/间期/SQI AUC 0.8204/0.7665/0.7528；步行0.5107/0.5631/0.5580。模板减SQI按人差+0.0101 [−0.0049,0.0290]，间期+0.0094 [−0.0653,0.0702]，均跨零。不能说总体改善，不启用筛选或扩展这组手工参数。

独立MAT/插值/相关性复算7954候选、5119尾候选30个AUC与5个区间通过，旧SQI精确复现；共享SciPy内核披露。静坐204、步行218单侧邻间期候选保留；无默认空形状触发。原F1/PPI/时间覆盖与疾病指标不变。输出outputs/ppg_local_dev_v1勿重跑；报告PPG_LOCAL_DEV_REPORT.zh-CN.md、聚合acceptance/PPG_LOCAL_DEV1.json、卡片与研究页已更新。

下一步优先人工质量标签入口审计，避免继续盲调同类手工特征。已查Segade作者仓库https://github.com/chengstark/Segade及2024预印本https://www.medrxiv.org/content/10.1101/2024.06.07.24308621v1.full：腕部逐点伪迹标签、DaLiA/WESAD/TROIKA来源；先核实代码/数据许可、下载可达性、标签语义、受试者映射与已见DaLiA重叠。尚未下载数据或借用代码，不能把整个资源当外部验证；不向作者发消息。先审计/冻结再训练，仍只研究PPG质量。7306段为论文描述，尚非本地核验计数。

本轮pytest 63 passed；生产构建通过（既有大分块提示保留）。候选形态卡ppglocal-b1f45aff9f03目视验收通过。


## 2026-10-20 SEGADE_SOURCE1完成：结构可达，训练准入未通过

固定作者commit f5b2ad6e180a1474bc47d6c5ec5d482edaed6797；Git完整树105blob、data恰8文件。HTTP Range读取8个NPY前缀，均206；只保存128字节头，无完整波形/标签下载。numpy独立核验4组shape与Git文件大小：DaLiA train3436/test869、WESAD2888、TROIKA113，合计7306段×1920。标签dtype为float64，实际0/1取值/重复/对齐尚未核验，不能把结构审计说成数据集验收。

GitHub license为空，树中无许可名称文件，README/两脚本无许可关键词；代码和新增标签复用许可未明确。data无逐行身份/时间sidecar，db2npy顶层只导出两数组；data_split用shuffle KFold对X行分折而非group。外层按人说明不等于内层按人，不直接宣称全论文泄漏。未训练、不执行第三方代码、不联系作者。初版审计器误计SQLite函数内np.save，已改AST仅核顶层，结构验收通过。

公开docs/SEGADE_SOURCE_AUDIT.zh-CN.md、acceptance/SEGADE_SOURCE1.json、fetch_segade_metadata.py和audit_segade_headers.py及卡片。缓存outputs/segade_source_audit_v1完成勿重复下载；头SHA和源码摘要记录，不能冒充全文件SHA。原算法、疾病指标/覆盖不变。

下一步优先审计BUT PPG 2.0官方CC BY4入口的质量标签表、受试者ID与10秒30Hz结构，作为有明确许可的方法校验备用；手机域不等于腕部运动验证，禁止拼10秒为伪30秒。再检查PhysioKit SQA-Phys是否真有可取得且许可明确的腕部训练标签。尚未下载上述两者波形/训练标签。不盲调同类手工参数，不因Segade缺口停整个项目或请求联系他人。

本轮三个审计/导出脚本语法编译通过，独立头结构核验通过；pytest 63 passed，生产构建通过（既有大分块提示保留）。成果卡segadesource-0cc64ff4e356目视验收通过。未运行第三方模型，未产生新的疾病性能结果。


## 2026-10-20 BUT_SOURCE1完成：明确许可与分组，先修导入边界

上一轮审批额度暂不可用，复制/下载未执行；本轮恢复后首次执行。BUT PPG2.0本地标签/采集表/PPG索引各3888条，50人，一一匹配，无标签/HR缺失或重复ID。好830、差3058，始终判差accuracy78.65%；49人双类、1人单类，每人4–108条。初版12人48条、扩展38人3840条；耳1962/指1926，12条复合活动2;3保留。CSV两种解析计数一致，9个元数据/头SHA与官方清单一致。主站清单慢，终止原下载并用官方S3镜像取得；无波形下载。初次csv未处理BOM已修正，源数据未更改。

固定四头抽查：旧版首尾均300信号/30Hz/1点，新版首尾3信号/30Hz/300点。不能直接取第一列或flatten冒充10秒序列；wfdb可选包当前未装，没有声称其读取验收通过。下一步先冻结跨版本波形适配协议，独立解码核对增益/基线、时间轴、RGB通道，之后冻结按人分组再评分；全部失败记录和覆盖要报。仅质量方法的手机域对照，不是腕部外部验证，不改疾病终点，不拼片段。PhysioKit README示例为指/耳，纠正此前“腕部标签”线索措辞，训练集仍待查。

本地outputs/but_source_v1缓存勿重下；公开脚本、BUT_SOURCE_AUDIT.zh-CN.md、BUT_SOURCE1.json及聚合卡。无新模型或疾病指标，V1–V5保持。训练准入待适配及分组协议，元数据验收已通过。

本轮三脚本语法编译通过，元数据9项官方哈希和双解析计数通过；pytest 63 passed，生产构建通过（既有大分块提示保留）。质量数据卡butsource-a6907a705521目视验收通过。


## 2026-10-20 BUT_ADAPTER1完成：原布局数值通过，legacy时间轴待定

96e0162先冻结四样本协议/自写读取器/7合成测试，再下载2.0.0官方S3的4条PPG波形。8个头/波形SHA通过；与隔离安装的WFDB4.3.1数字逐值一致、物理最大误差0，2400值全有限，缺失码0。旧版2条仍1×300，新版2条300×3；未reshape、未选通道、未读标签评分、未训练。新版共6个32767编码端点保留，不直接解释硬件削顶。

首次真实检查单位等同性失败：源a.u.被WFDB解析成a，核查其单位正则不接受点号。保留原始单位，把差异显式入JSON，未改源头/样本/容差；不能声称元数据完全一致。独立数值验收通过不等于legacy时间轴通过。outputs/but_adapter_v1/completed.json已完成勿重跑；outputs/adapter_tools为本地可选验证库，未改全局依赖。

公开BUT_ADAPTER_PROTOCOL.zh-CN.md、BUT_ADAPTER_REPORT.zh-CN.md、BUT_ADAPTER1.json、自写读取/测试/运行器与成果卡。下一步补旧版时间顺序的来源证据和全量导入覆盖；如48条legacy仍不能准入，明确列入失败分母，不能静默删除后称全库100%。之后冻结按人分组/通道再评分。V1–V5疾病指标及覆盖不变，手机指/耳不能替代腕部验证。


推进边界：旧版时间轴问题不应无限阻塞已知RGB布局的扩展版。下一轮先对扩展版3840条/38人做全量导入覆盖审计，同时保留初版48条/12人技术待定清单。若无法获得旧版时间顺序的可靠依据，可以在任何模型评分前预注册“扩展版固定子队列”，以明确的发布阶段/采集格式定义范围，并分别报3888条总库与3840条目标队列的覆盖；不得称50人全库验证、不得按质量标签或效果挑样本。此举只用于新的手机质量方法对照，不删改原T1D事件或V1–V5分母。

本轮70项pytest通过（含新增7项读取边界测试），网站生产构建通过（既有大分块提示保留），读取成果卡butadapter-8f6eacb2f02e目视验收通过。


## 2026-10-23 LORA_ENGINEERING1：新研究分支工程验收

用户授权可穿戴/背景 Transformer 微调与机制知识扩展，保留 Agent Harness，排除旧质谱路线。先快进同步远端 ae760e0，未覆盖另一工作目录。新增原创时序Transformer、Q/V LoRA、缺失与时间处理、年龄段背景token、训练分组/归一化和检查点绑定；加入离线真实数据预训练/微调入口。SPAID/STING摘要经现有knowledge/retrieve_evidence读取；Harness本体、加密、三工具与日报回退不变。自由文本仍留Harness，不伪造患者蛋白或疾病标签。

固定合成60步预训练＋80步微调：总21159参数，可训练1281；零初始化输出差0，底座冻结逐值不变，适配器有更新，保存恢复差0；重建训练损失0.7980→0.1333仅工程证据。通用入口另以合成NPZ测试两阶段各40epoch，验证内选模型且不读取测试数组。78项Python测试、18项Agent测试与生产构建/凭据边界通过，原大分块提示保留。首次临时目录权限与本地HTTP沙箱失败已定位；改工作区临时目录和获批回环测试复核，文献数量断言更新以容纳新知识条目。

公开仅代码/文档/聚合LORA_ENGINEERING1.json，权重和数组在outputs忽略目录。V1–V5临床指标不变；真实队列Transformer效果待审计后实验，未实现QLoRA。GSE45515为可下载非质谱抗体芯片线索，无可穿戴配对；RA+CRP研究需申请；PHD/iPOP公开包的蛋白联结尚未核验。具体协议、来源与复现见docs/TRANSFORMER_LORA.zh-CN.md。定时任务当前PAUSED，本次未恢复。

## 2026-10-23 PPG预训练与独立抗体：已执行更新

按用户确认方向新增真实Pulse-PPG编码器、T1D时序Transformer/LoRA对照、GSE45515独立抗体基线，并将有来源与局限的研究摘要接入原Harness检索；不融合不同患者的蛋白与传感器记录。

FIT2：4人训练14039窗、1人验证3719窗；18候选独立复核差0。修正299/301秒时钟抖动后，参考决策点覆盖39.55%→80.12%。验证AP：线性0.0955、全量0.0931、LoRA0.0781、病例比例0.0683。LoRA尚未超过简单头，参数不称全局最优；测试和事件报警未评估。FIT1全部保留。

抗体149张芯片按104保守命名组：AUC0.882/AP0.872，但患者身份、总说明标签冲突、pNA条目AUC0.735的混杂尚未解决；不能作个人风险或低血糖增益。BIG IDEAs16个背景ID与目录相符，只有Gender/HbA1c，没有逐人年龄；波形时钟/背景取得时间未验收，暂不准入训练。

完整文档：https://github.com/PYxuejiang/t1d-wearable-lab/blob/main/docs/MULTIMODAL_BRANCHES.zh-CN.md 。真实PPG表示、两轮全部候选和复核存本地outputs，不重复长任务。下一步训练人员内分组验证与背景数据审计；不扩大单个验证人参数搜索，不自动用Agent输出当标签。91项Python、19项Agent和生产构建通过，个人数据和权重不公开，定时仍PAUSED。

## 2026-10-23 跨版本时间单位回归修复

首轮远端CI的LoRA作业两项新测试失败：pandas保留秒/微秒时间精度时，直接astype(int64)并不是纳秒。现显式转为epoch纳秒再关联标签，增加s/us/ns三种精度回归测试，并对空对齐结果清晰报错。实际源Parquet为datetime64[ns]，重新审计仍为训练14039/405阳性、验证3719/254阳性及相同覆盖台账，模型结果不变；没有为通过CI重标标签、重训或修改指标。[复核](acceptance/PULSE_TIME_UNIT_REGRESSION.json)。Pages此前已部署成功，公开研究卡SHA与本地一致。远端CI修复后另行确认。

修复后本地完整Python测试95项通过（新增三种时间精度回归），Agent19项与构建结果保持。失败环境为pandas3.1.0；实际训练环境为pandas2.3，已确认缓存分组和标签未变。
