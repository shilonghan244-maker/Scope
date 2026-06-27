from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate manuscript Tables VI-VIII from existing SCOPE trial-level raw logs."
    )
    parser.add_argument("--config", default="configs/paper_default.yaml")
    parser.add_argument("--seeds", default="seeds/monte_carlo_50_trials.csv")
    parser.add_argument("--raw-output", "--raw", default="results/raw")
    parser.add_argument("--tables-output", "--tables", default="results/tables")
    parser.add_argument("--manuscript-out", default="results/manuscript_numbers.md")
    parser.add_argument("--trials", type=int, default=None, help="Optional smoke-test trial count.")
    parser.add_argument(
        "--run-simulation",
        action="store_true",
        help="Regenerate raw logs before tables. By default the script reuses existing results/raw logs.",
    )
    parser.add_argument("--skip-simulation", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--skip-export", action="store_true", help="Skip manuscript-number Markdown export.")
    return parser.parse_args()


def _run(command: list[str]) -> None:
    print(" ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    args = parse_args()
    python = sys.executable

    if args.run_simulation and args.skip_simulation:
        raise SystemExit("--run-simulation and --skip-simulation cannot be used together.")

    if args.run_simulation:
        run_all = [
            python,
            "scripts/run_all.py",
            "--config",
            args.config,
            "--seeds",
            args.seeds,
            "--out",
            args.raw_output,
        ]
        if args.trials is not None:
            run_all.extend(["--trials", str(args.trials)])
        _run(run_all)

    _run(
        [
            python,
            "scripts/make_tables.py",
            "--config",
            args.config,
            "--input",
            args.raw_output,
            "--output",
            args.tables_output,
        ]
    )

    if not args.skip_export:
        _run(
            [
                python,
                "scripts/export_manuscript_numbers.py",
                "--tables",
                args.tables_output,
                "--out",
                args.manuscript_out,
            ]
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
