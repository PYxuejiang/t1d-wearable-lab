# T1D Wearable Lab

Two reproducible research modules on public type 1 diabetes cohorts:

1. **CGM + wearable collaboration:** 30-minute glucose forecasting and separately evaluated incident hypoglycemia prediction using BrisT1D-Open.
2. **Sensor evaluation:** current hypoglycemia detection, signal quality, and paired sensor ablations using PhysioCGM.

This repository is a retrospective research project. Protocol compliance, predictive effect, and presentation readiness are separate acceptance decisions. Negative results are retained. No original participant records or credentials are published here.

## Status

Implementation is underway. See [stage acceptance](docs/acceptance/STATUS.md). Numeric module-1 comparisons have passed independent metric recomputation; event and sensor results are separate stages.

The initial **20-subject LOSO** numeric comparison finds CGM-only MAE 1.0261 mmol/L versus 1.1710 for the validation-selected simple baseline. Adding wearable summaries to the context model did **not** improve this held-out comparison (1.0290 versus 1.0252 mmol/L). Temporal results differ and are reported separately. These are retrospective fixed-model results, not medical efficacy or a general impossibility claim. See [S2a evidence](docs/acceptance/S2a.json).

## Setup

```powershell
python -m pip install -e .
python -m pytest -q
python scripts/download_data.py --dataset brist1d
python scripts/download_data.py --dataset physiocgm
python scripts/audit_data.py --dataset brist1d
python scripts/run_module1.py --build-only
python scripts/run_module1.py --protocol both
python scripts/verify_module1.py
python scripts/extract_signals.py --watch
```

Download commands save data locally under ignored `data/`, verify source checksums where available, and write a local manifest. PhysioCGM is processed directly from per-subject raw ZIP archives to avoid duplicating the full corpus on disk. Dataset access, source availability, and terms remain those of the original repositories.

## Sources and licenses

- [BrisT1D-Open](https://data.bris.ac.uk/data/dataset/33z5jc8fa6tob21ptrugzqog08): processed device data, CC BY 4.0. [Schema](https://data.bris.ac.uk/datasets/33z5jc8fa6tob21ptrugzqog08/README.txt).
- [PhysioCGM](https://doi.org/10.6084/m9.figshare.28136294): raw physiological data and CGM, CC0. [Data descriptor](https://doi.org/10.1038/s41597-025-06090-6).
- Own implementation: MIT. Public availability of an author's repository does not grant an unspecified code license; this project does not copy the original PhysioCGM implementation.

Published cohort sizes are not treated as counts of eligible test subjects. Each input file and exclusion is audited. CGM is a reference measurement, not a clinical venous-glucose gold standard. Detection is not advance warning; sparse sampling limits event timing precision.

