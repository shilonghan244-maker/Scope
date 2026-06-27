#!/usr/bin/env bash
set -euo pipefail
python scripts/run_all.py --config configs/paper_default.yaml --seeds seeds/monte_carlo_50_trials.csv
python scripts/make_tables.py --config configs/paper_default.yaml --input results/raw --output results/tables
python scripts/plot_all.py --input results/raw --output results/diagnostic_figures
python scripts/export_manuscript_numbers.py --tables results/tables --out results/manuscript_numbers.md
