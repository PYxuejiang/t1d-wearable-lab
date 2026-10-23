"""Public aggregate-only research figures; no raw records or predictions."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'showcase/public/cards'


def card(name, title, subtitle, labels, values, baseline, metric, notes):
    fig, ax = plt.subplots(figsize=(10, 5.4), facecolor='#f6f5ef')
    ax.set_facecolor('#f6f5ef')
    fig.subplots_adjust(left=.27, right=.88, top=.70, bottom=.28)
    bars = ax.barh(labels, values, color=['#758482', '#276c61', '#619a8b', '#b08695'][:len(values)], height=.48)
    ax.invert_yaxis()
    ax.set_xlim(0, 1 if metric == 'Out-of-fold ROC AUC' else max(values + [baseline]) * 1.24)
    ax.axvline(baseline, color='#9b7356', linestyle='--', linewidth=1.3)
    ax.set_xlabel(metric, color='#526764')
    ax.tick_params(length=0, labelsize=10, colors='#1d373b')
    for spine in ax.spines.values():
        spine.set_visible(False)
    for bar, value in zip(bars, values):
        ax.text(value + ax.get_xlim()[1] * .018, bar.get_y() + bar.get_height()/2,
                f'{value:.3f}', va='center', color='#1d373b', fontsize=11)
    fig.text(.07, .92, 'T1D / LAB   •   REPRODUCIBLE RESEARCH', fontsize=9, color='#758482')
    fig.text(.07, .84, title, fontsize=20, weight='bold', color='#1d373b')
    fig.text(.07, .77, subtitle, fontsize=10, color='#526764')
    fig.text(.07, .13, notes, fontsize=9, color='#526764', linespacing=1.7)
    DEST.mkdir(parents=True, exist_ok=True)
    fig.savefig(DEST / f'{name}.svg')
    fig.savefig(DEST / f'{name}.png', dpi=150)
    plt.close(fig)


def main():
    report = json.loads((ROOT / 'docs/acceptance/PULSE_TEMPORAL_FIT2.json').read_text())
    checked = json.loads((ROOT / 'docs/acceptance/PULSE_TEMPORAL_FIT2_VERIFY.json').read_text())
    if checked['status'] != 'passed' or not report['test_opened'] is False:
        raise ValueError('Verified validation-only result required')
    kinds = ['head', 'full', 'lora', 'linear']
    best = [max([r for r in report['candidates'] if r['kind'] == kind],
                key=lambda r: (r['selected']['AP'], -r['selected']['Brier'])) for kind in kinds]
    card('ppg-lora-validation', 'Real PPG representations. Measured trade-offs.',
         f"4 training participants / 1 validation participant / {report['validation_windows']:,} validation windows",
         ['Head on frozen backbone', 'Full temporal tuning', 'Q/V LoRA', 'Linear embedding head'],
         [r['selected']['AP'] for r in best], report['validation_prevalence'], 'Validation average precision',
         'Dashed line: validation prevalence. All 18 candidates retained; selection uses this validation set.\n'
         'No test score, clinical alarm claim, paired background effect or independent generalization estimate.')
    studies = [json.loads((ROOT / f'docs/acceptance/{name}.json').read_text()) for name in
               ['ANTIBODY_ARRAY1', 'ANTIBODY_ANNOTATED1', 'ANTIBODY_PNA1']]
    card('antibody-independent-baseline', 'An independent antibody branch.',
         '149 arrays / conservative title-family grouping / nested cross-validation',
         ['All 774 features', '757 annotated features', '17 pNA features'],
         [r['oof']['roc_auc'] for r in studies], .5, 'Out-of-fold ROC AUC',
         'Donor identity and batch effects remain unresolved. pNA-only discrimination is a confounding warning.\n'
         'Different endpoint: T1D vs control arrays. Not wearable hypoglycemia detection or personal risk.')
    print('Exported two aggregate-only cards as PNG and SVG.')


if __name__ == '__main__':
    main()
