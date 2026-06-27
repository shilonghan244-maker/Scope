from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run trial-level SCOPE simulations in parallel and merge raw logs.")
    parser.add_argument("--config", default="configs/paper_default.yaml")
    parser.add_argument("--seeds", default="seeds/monte_carlo_50_trials.csv")
    parser.add_argument("--out", default="results/raw")
    parser.add_argument("--work-dir", default="results/raw_parallel_work")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--trials", type=int, default=None, help="Optional first-N trial limit for smoke runs.")
    parser.add_argument("--only", nargs="*", default=None, help="Optional experiment ids passed through to run_all.py.")
    parser.add_argument("--keep-work", action="store_true", help="Keep per-trial worker outputs after merging.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    seed_rows = _read_seed_rows(ROOT / args.seeds)
    if args.trials is not None:
        seed_rows = seed_rows[: args.trials]
    if not seed_rows:
        raise SystemExit("No seed rows selected.")

    work_dir = ROOT / args.work_dir
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    worker_count = max(1, min(int(args.max_workers), len(seed_rows)))
    futures = []
    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        for row in seed_rows:
            futures.append(executor.submit(_run_one_trial, row, args.config, args.only, str(work_dir)))
        trial_dirs = []
        for future in as_completed(futures):
            trial_dir = future.result()
            print(f"finished {trial_dir}")
            trial_dirs.append(Path(trial_dir))

    _merge_trial_outputs(sorted(trial_dirs), ROOT / args.out / "trial_metrics.csv")
    if not args.keep_work:
        shutil.rmtree(work_dir)
    print(f"Wrote merged raw rows to {ROOT / args.out / 'trial_metrics.csv'}")
    return 0


def _read_seed_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _run_one_trial(row: dict[str, str], config: str, only: list[str] | None, work_dir_text: str) -> str:
    work_dir = Path(work_dir_text)
    trial_id = int(row["trial_id"])
    trial_dir = work_dir / f"trial_{trial_id:03d}"
    trial_dir.mkdir(parents=True, exist_ok=True)
    seed_file = trial_dir / "seed.csv"
    with seed_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    command = [
        sys.executable,
        "scripts/run_all.py",
        "--config",
        config,
        "--seeds",
        str(seed_file.relative_to(ROOT)),
        "--out",
        str(trial_dir.relative_to(ROOT)),
    ]
    if only:
        command.extend(["--only", *only])
    subprocess.run(command, cwd=ROOT, check=True)
    return str(trial_dir)


def _merge_trial_outputs(trial_dirs: list[Path], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] | None = None
    rows: list[dict[str, str]] = []
    for trial_dir in trial_dirs:
        raw_file = trial_dir / "trial_metrics.csv"
        with raw_file.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if fieldnames is None:
                fieldnames = list(reader.fieldnames or [])
            rows.extend(reader)
    if fieldnames is None:
        raise ValueError("No trial outputs were produced.")
    rows.sort(key=lambda row: (int(row["trial_id"]), row["experiment"], row["metric"], row["algorithm"]))
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
