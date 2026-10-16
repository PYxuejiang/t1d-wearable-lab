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
