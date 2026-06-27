from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_experiment(experiment_id: str) -> int:
    root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        str(root / "scripts" / "run_all.py"),
        "--config",
        "configs/paper_default.yaml",
        "--seeds",
        "seeds/monte_carlo_50_trials.csv",
        "--only",
        experiment_id,
    ]
    return subprocess.call(cmd, cwd=root)
