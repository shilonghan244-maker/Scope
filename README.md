# SCOPE WRSN Reproducibility Package

This repository contains the simulation code, random-seed lists, configuration
files, trial-level logs, and table-generation scripts used for the paper:

**SCOPE: A Hierarchical Event-Triggered Framework for Spatio-Temporal Coverage
Maximization in WRSNs with Zeno-Free Scheduling Guarantees**

The package regenerates the raw Monte Carlo statistics and Tables VI-VIII from
the released trial records and configuration files. Optional simplified
diagnostic figures can also be generated for trend inspection. The diagnostic
figures are not advertised as pixel-level reproductions of all manuscript
figures.

## Contents

| Material | Location | Purpose |
| --- | --- | --- |
| Simulation code | `src/scope_repro/`, `experiments/` | Physical WRSN model, policy rules, metrics, and experiment entry points. |
| Seed list | `seeds/monte_carlo_50_trials.csv` | The 50 paired Monte Carlo trials used by the paper experiments. |
| Configuration | `configs/paper_default.yaml` | Paper experiment parameters, scenario settings, metric definitions, and baseline settings. |
| Scripts | `scripts/` | Simulation execution, table generation, diagnostic plotting, and manuscript-number export. |
| Public outputs | `results/raw/`, `results/tables/`, `results/manuscript_numbers.md` | Trial-level logs and generated table artifacts. |

## Generated Artifacts

The public workflow generates:

- `results/raw/trial_metrics.csv`, one direct simulator `value` per metric,
  trial, experiment, and algorithm;
- `results/tables/table_vi_communication_overhead.csv/.tex`;
- `results/tables/table_vii_statistics.csv/.tex`, computed as mean, sample
  standard deviation, and 95% confidence interval over the paired trial records;
- `results/tables/table_viii_paired_tests.csv/.tex`, computed from paired
  SCOPE-baseline differences using the Wilcoxon signed-rank test, Holm
  correction, and paired effect size `dz`;
- `results/manuscript_numbers.md`, a Markdown export of the generated table
  values.

Optional simplified diagnostic figures can be written to
`results/diagnostic_figures/`.

## Metric Notes

- Table VII reports **Average coverage-quality ratio (Cavg)** for the Fig. 9
  coverage trend.
- The Table VII latency statistic uses the scheduling-visible
  request-reporting/acceptance time after warm-start initialization.
- Travel-normalized efficiency uses meter-equivalent path distance from the
  simulator.
- Utility-normalized efficiency uses a common coverage-quality normalized PSM
  marginal utility and one global unit scale for every algorithm and trial.
- Fig. 18/19 coverage-critical outage metrics use partial low-energy severity
  below the request threshold `Eth`.
- Table VI is compact scheduling-control payload accounting. It excludes
  sensing-data traffic, MAC/PHY headers, retransmissions,
  encryption/authentication fields, and hardware-specific protocol overhead.
- The computation-time values come from the same reference computational-cost
  model used for Fig. 16.

## Environment

Python 3.10 or newer is recommended.

```powershell
cd scope-wrsn-repro
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

The core simulation uses the Python standard library. The packages in
`requirements.txt` support plotting and extension work.

## Recommended Workflow

Run the 50 paired Monte Carlo workflow:

```powershell
python scripts\run_all_parallel.py --config configs\paper_default.yaml --seeds seeds\monte_carlo_50_trials.csv --out results\raw --max-workers 4
python scripts\make_tables.py --config configs\paper_default.yaml --input results\raw --output results\tables
python scripts\export_manuscript_numbers.py --tables results\tables --out results\manuscript_numbers.md
```

Regenerate tables from existing raw logs:

```powershell
python scripts\run_reproduce_tables.py --config configs\paper_default.yaml --raw results\raw --tables results\tables
```

Optional executability check:

```powershell
python scripts\run_all.py --config configs\paper_default.yaml --seeds seeds\monte_carlo_50_trials.csv --trials 3 --out results\smoke_raw
python scripts\make_tables.py --config configs\paper_default.yaml --input results\smoke_raw --output results\smoke_tables
```

Smoke outputs are for local executability checks only and are not
manuscript-scale Monte Carlo results.

## Seed Protocol

The experiments use paired common randomness. For a fixed `trial_id`, SCOPE,
MC3, CAERM, and Dist-Greedy share the same deployment, initial energy, demand,
mobility, charging-efficiency, and scenario seeds. Only the scheduling policy
differs.

## Configuration Boundary

Parameters explicitly stated in the manuscript tables are kept under
`paper_fixed_parameters`: network size, charger count, energy thresholds,
charging power, battery capacity, charger speed, PSM constants, time slot, and
SCOPE control-period settings.

Implementation-level settings used by the simulator are provided in
`implementation_parameters`. These include load variation, scenario details,
policy weights, finite grouping radius, and queue/service ordering details.

Generated table values are always computed from `results/raw/trial_metrics.csv`.
The table scripts do not rewrite raw values, p-values, confidence intervals,
effect sizes, or interpretations.

## Traceability

```text
configs/paper_default.yaml + seeds/monte_carlo_50_trials.csv
  -> scripts/run_all.py or scripts/run_all_parallel.py
  -> results/raw/trial_metrics.csv
  -> scripts/make_tables.py
  -> results/tables/
  -> scripts/export_manuscript_numbers.py
  -> results/manuscript_numbers.md
```

Each statistic is traceable to a trial-level record, a seed row, and the paper
configuration file.

## Guardrails

- Do not edit generated tables manually.
- Do not compare algorithms from different random deployments.
- Do not interpret smoke runs as manuscript-scale results.
