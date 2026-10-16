# T1D Wearable Lab

Two reproducible research modules on public type 1 diabetes cohorts:

1. **CGM + wearable collaboration:** 30-minute glucose forecasting and separately evaluated incident hypoglycemia prediction using BrisT1D-Open.
2. **Sensor evaluation:** current hypoglycemia detection, signal quality, and paired sensor ablations using PhysioCGM.

This repository is a retrospective research project. Protocol compliance, predictive effect, and presentation readiness are separate acceptance decisions. Negative results are retained. No original participant records or credentials are published here.

## Status

Both initial research pipelines have run on real public data and passed independent evaluation checks. See [stage acceptance](docs/acceptance/STATUS.md), the [Chinese validation report](docs/VALIDATION_REPORT.zh-CN.md), [metric definitions](docs/METRICS.zh-CN.md), and the [new improvement plan](docs/IMPROVEMENT_PLAN.zh-CN.md). Passing engineering checks does **not** mean the alarm targets passed.

The initial **20-subject LOSO** numeric comparison finds CGM-only MAE 1.0261 mmol/L versus 1.1710 for the validation-selected simple baseline. Adding wearable summaries to the context model did **not** improve this held-out comparison (1.0290 versus 1.0252 mmol/L). Temporal results differ and are reported separately. These are retrospective fixed-model results, not medical efficacy or a general impossibility claim. See [S2a evidence](docs/acceptance/S2a.json).

The separate incident-risk model reaches 47.5% subject-equal event recall at 0.53 unmatched alarms/person-day in LOSO, below the internal recall target. In the physiological module, 7/10 source clocks were eligible; the original five sensor configurations fail the event target, including zero event recall at their validation-selected test operating points. These negative results are retained while v2 explores personalized models, temporal features, and denser validation-only alarm selection. Reusing the already viewed cohort is explicitly exploratory.

![Research showcase](docs/figures/showcase-overview.jpg)

## Try the local showcase

Node 22 is recommended. The checked-in aggregate evidence and PNG/SVG cards work without patient-data downloads:

```powershell
cd showcase
npm ci
npm run dev
```

Open the printed local URL. The interface offers protocol comparisons, five sensor configurations, evidence drawers, PNG cards and aggregate JSON export. Optional real participant replays/waveforms are generated locally after analysis and excluded from Git. See the [three-minute demo script](docs/DEMO.zh-CN.md). Public site deployment and personal-device migration are outside the current scope.

## Setup

```powershell
python -m pip install -e ".[reports]" pytest
python -m pytest -q
python scripts/download_data.py --dataset brist1d
python scripts/download_data.py --dataset physiocgm
python scripts/audit_data.py --dataset brist1d
python scripts/run_module1.py --build-only
python scripts/run_module1.py --protocol both
python scripts/verify_module1.py
python scripts/extract_signals.py --watch
python scripts/run_incident.py
python scripts/verify_incident.py
python scripts/run_module2.py
python scripts/verify_module2.py
python scripts/robustness_report.py
python scripts/export_showcase.py
python scripts/export_signal_example.py
python scripts/export_cards.py
python scripts/final_report.py
```

The initial environment is pinned in `requirements-reproduce.txt`; the package also tests explicit datetime resolutions so pandas microsecond/nanosecond defaults cannot silently change time units. After a result changes, regenerate the aggregate JSON, cards and report together; display-contract tests enforce identical scientific values and a shared canonical run ID. Outputs and individual predictions remain local. Source file sizes/checksums are in [the source manifest](docs/source_manifest.json).

To run the separately versioned exploratory comparison, first read `configs/improvement_v2.json`, then run `python scripts/run_improvement.py`. Validation chooses candidates and alarm parameters; test predictions are not used to pick winners.

Download commands save data locally under ignored `data/`, verify source checksums where available, and write a local manifest. PhysioCGM is processed directly from per-subject raw ZIP archives to avoid duplicating the full corpus on disk. Dataset access, source availability, and terms remain those of the original repositories.

## Sources and licenses

- [BrisT1D-Open](https://data.bris.ac.uk/data/dataset/33z5jc8fa6tob21ptrugzqog08): processed device data, CC BY 4.0. [Schema](https://data.bris.ac.uk/datasets/33z5jc8fa6tob21ptrugzqog08/README.txt).
- [PhysioCGM](https://doi.org/10.6084/m9.figshare.28136294): raw physiological data and CGM, CC0. [Data descriptor](https://doi.org/10.1038/s41597-025-06090-6).
- Own implementation: MIT. Public availability of an author's repository does not grant an unspecified code license; this project does not copy the original PhysioCGM implementation.

Published cohort sizes are not treated as counts of eligible test subjects. Each input file and exclusion is audited. CGM is a reference measurement, not a clinical venous-glucose gold standard. Detection is not advance warning; sparse sampling limits event timing precision.

