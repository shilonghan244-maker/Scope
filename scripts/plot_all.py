from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scope_repro.config import load_config
from scope_repro.plotting import write_all_figures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate simplified data-backed diagnostic figures for the SCOPE reproducibility package.")
    parser.add_argument("--config", default="configs/paper_default.yaml")
    parser.add_argument("--input", default="results/raw")
    parser.add_argument("--output", default="results/diagnostic_figures")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(ROOT / args.config)
    written = write_all_figures(ROOT / args.input / "trial_metrics.csv", ROOT / args.output, config)
    print(f"Wrote {len(written)} figure files to {ROOT / args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
