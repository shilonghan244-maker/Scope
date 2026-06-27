# Manuscript Table Mapping

This file maps repository outputs to manuscript Tables VI-VIII.

The public configuration is `configs/paper_default.yaml`. Tables VI-VIII are
generated from the released configuration and trial-level records.

## Table Mapping

| Manuscript artifact | Generated file | Source data | Command |
| --- | --- | --- | --- |
| Table VI, communication overhead | `results/tables/table_vi_communication_overhead.csv` and `.tex` | `configs/paper_default.yaml` | `python scripts/make_tables.py --config configs/paper_default.yaml --input results/raw --output results/tables` |
| Table VII, summary statistics | `results/tables/table_vii_statistics.csv` and `.tex` | `results/raw/trial_metrics.csv` | same as above |
| Table VIII, paired tests | `results/tables/table_viii_paired_tests.csv` and `.tex` | `results/raw/trial_metrics.csv` | same as above |
| Manuscript update aid | `results/manuscript_numbers.md` | generated table CSVs | `python scripts/export_manuscript_numbers.py --tables results/tables --out results/manuscript_numbers.md` |

Table VII is computed directly from raw trial records. Table VIII is a
representative paired statistical-test summary for key comparisons. It is
computed from paired trial differences, Wilcoxon signed-rank tests, Holm
correction, and paired `dz` for the specified representative comparison in each
row. Best-baseline rows are resolved against the generated raw means and display
the specific algorithm selected for the comparison.

Table VII uses the released statistical metric names generated from the raw
simulator metrics. In particular, `Cavg` is reported as **Average
coverage-quality ratio (Cavg)**.

## Figure Mapping

The package can generate simplified diagnostic figures:

```powershell
python scripts\plot_all.py --input results\raw --output results\diagnostic_figures
```

These figures are intended for local trend inspection. They are not advertised
as full reproduction of every manuscript figure unless separate figure scripts
are added for the final manuscript artwork.

## Baseline Source Mapping

| Baseline | Source supplied by author | Local simulator mapping |
| --- | --- | --- |
| CAERM | Supplied CAERM paper | Coverage benefit per added travel distance; static charger-region adaptation. |
| MC3 | Supplied MC3 paper | Nearest/current mobile-charger assignment with workload balancing. |
| Dist-Greedy | Basic greedy method | Nearest currently requested sensor. |

## Release Consistency Rule

Before public release, run the final workflow and update the manuscript tables
from `results/manuscript_numbers.md` if the generated values differ from an
older draft. Do not manually edit generated CSV files.
