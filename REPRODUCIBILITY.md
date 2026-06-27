# Reproducibility Notes

This document describes how the repository regenerates trial-level Monte Carlo
statistics and statistical tables from the released seed list and configuration
file.

## Provided Materials

| Review item | Repository location | Contents |
| --- | --- | --- |
| Code | `src/scope_repro/`, `experiments/` | Physical WRSN simulation, policy rules, metrics, statistics helpers, and experiment entry points. |
| Seeds | `seeds/monte_carlo_50_trials.csv` | The 50 paired Monte Carlo seed rows used by the paper experiments. |
| Configuration | `configs/paper_default.yaml` | Paper experiment parameters, scenario settings, metric definitions, and baseline settings. |
| Scripts | `scripts/run_all.py`, `scripts/run_all_parallel.py`, `scripts/make_tables.py`, `scripts/export_manuscript_numbers.py` | Simulation, table generation, diagnostic plotting, and manuscript table export. |

## Monte Carlo Protocol

The final statistics use 50 paired Monte Carlo trials. For a fixed `trial_id`,
all algorithms share the same environment realization:

- sensor deployment seed;
- initial energy seed;
- demand/load perturbation seed;
- mobility seed;
- charging-efficiency seed;
- scenario seed.

The algorithms differ in scheduling policy only. This paired common-randomness
protocol supports paired SCOPE-baseline tests and reduces Monte Carlo variance.

`configs/paper_default.yaml` is the paper experiment configuration used by the
public workflow.

## Physical Simulation Model

The workflow advances a physical WRSN state over the configured time horizon:

- sensors are deployed according to the selected scenario;
- each sensor has an initial energy state, stochastic load, PSM contribution,
  and low-energy request state;
- energy decreases at `simulation.time_slot_s = 1 s`;
- mobile chargers move at the configured speed, consume movement energy, keep a
  battery reserve, and deliver wireless charging energy with scenario-dependent
  efficiency;
- `scope.phase_iii.tau_ctrl_s = 50 s` remains a control-period parameter, not
  the physical integration step;
- request latency is measured at service start using the configured
  accepted-assignment origin plus the control-cycle offset;
- SCOPE, MC3, CAERM, and Dist-Greedy use the same physical rules and differ
  only in target selection, assignment, grouping, and reorganization policy.

## Metrics And Tables

`scripts/run_all.py` and `scripts/run_all_parallel.py` write
`results/raw/trial_metrics.csv`. Each row contains one direct simulator
`value`.

`scripts/make_tables.py` computes:

- Table VII: mean, sample standard deviation, and 95% confidence interval over
  paired trial records;
- Table VIII: paired differences, Wilcoxon signed-rank p-values, Holm-adjusted
  p-values, and paired effect size `dz` for representative key comparisons;
- Table VI: communication-overhead accounting from public configuration values.

The generated table files are produced from raw trial records by the table
script and are not edited by a later reporting layer. When a Table VIII row
uses a best-baseline selector, the generated table shows the resolved concrete
algorithm name rather than a generic best-baseline label.

Metric definitions used by the public tables are fixed in the configuration
before the 50 paired Monte Carlo run:

- `Cavg` is exported as **Average coverage-quality ratio (Cavg)**.
- `Davg` is the Fig. 9/Table VII dead-node exposure ratio.
- `eta_travel` is computed from delivered charging energy divided by
  meter-equivalent path distance.
- `eta_util` uses normalized PSM marginal utility with one global
  coverage-quality exponent and unit scale.
- Fig. 18/19 coverage-critical outage metrics use partial low-energy severity
  below `Eth`, the low-energy request threshold.
- Table VI is compact scheduling-control payload accounting.
- Computation-time values use the reference computational-cost model for
  Fig. 16.

## Commands

Final run:

```powershell
python scripts\run_all_parallel.py --config configs\paper_default.yaml --seeds seeds\monte_carlo_50_trials.csv --out results\raw --max-workers 4
python scripts\make_tables.py --config configs\paper_default.yaml --input results\raw --output results\tables
python scripts\export_manuscript_numbers.py --tables results\tables --out results\manuscript_numbers.md
```

Table-only reproduction from existing raw logs:

```powershell
python scripts\run_reproduce_tables.py --config configs\paper_default.yaml --raw results\raw --tables results\tables
```

Optional local diagnostics:

```powershell
python scripts\plot_all.py --input results\raw --output results\diagnostic_figures
```

Diagnostic figures are simplified, data-backed QA figures. They are not claimed
as full manuscript figure artwork.

## Baselines

The baselines run on the same physical charging model as SCOPE.

- MC3 follows the supplied MC3 paper at the simulator level: nearest/current
  mobile-charger assignment with lightweight workload balancing.
- CAERM follows the supplied CAERM paper at the simulator level: coverage-aware
  energy replenishment with static charger-region adaptation for the
  multi-charger setting.
- Dist-Greedy is the nearest currently requested sensor heuristic.

Physical constants such as charging power, speed, battery capacity, energy
thresholds, request threshold, PSM formula, and common service target are shared
across all algorithms.

Route and queueing differences are represented through implementation-level
strategy parameters such as static region use, nearest-only target selection,
route continuation, return-to-depot behavior, cooperative grouping, and
reorganization delay. These parameters are part of the paper experiment
configuration and are not table-level adjustments.

SCOPE grouping parameters are coalition candidate bounds only. A grouped
request still consumes service time, delivered energy, movement energy, and
charger battery budget.

## Public Results Tree

Before release, retain only:

- `results/raw/`
- `results/tables/`
- optionally `results/manuscript_numbers.md`

Remove smoke outputs, worker directories, caches, temporary profiles, and old
figure folders.
