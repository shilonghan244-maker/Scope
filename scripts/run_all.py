from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scope_repro.config import load_config
from scope_repro.io import write_csv
from scope_repro.pipeline import build_raw_rows
from scope_repro.utils.rng import generate_seed_rows, load_seed_rows, save_seed_rows


RAW_COLUMNS = [
    "trial_id",
    "experiment",
    "table_metric",
    "setting",
    "metric",
    "algorithm",
    "value",
    "experiment_id",
    "scenario",
    "environment_id",
    "master_seed",
    "deployment_seed",
    "energy_seed",
    "demand_seed",
    "mobility_seed",
    "efficiency_seed",
    "scenario_seed",
    "algorithm_seed",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SCOPE reproducibility simulation pipeline.")
    parser.add_argument("--config", default="configs/paper_default.yaml")
    parser.add_argument("--seeds", default="seeds/monte_carlo_50_trials.csv")
    parser.add_argument("--out", default="results/raw")
    parser.add_argument("--trials", type=int, default=None, help="Optional smoke-test override for the number of trials.")
    parser.add_argument("--only", nargs="*", default=None, help="Optional experiment ids to run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(ROOT / args.config)
    seed_path = ROOT / args.seeds
    if seed_path.exists():
        seed_rows = load_seed_rows(seed_path)
    else:
        seed_rows = generate_seed_rows(trials=int(config["simulation"]["runs"]))
        save_seed_rows(seed_rows, seed_path)
    if args.trials is not None:
        seed_rows = seed_rows[: args.trials]

    raw_rows = build_raw_rows(config, seed_rows, experiments=args.only)
    out_dir = ROOT / args.out
    write_csv(out_dir / "trial_metrics.csv", raw_rows, RAW_COLUMNS)
    print(f"Wrote {len(raw_rows)} raw rows to {out_dir / 'trial_metrics.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
