from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

SEED_FIELDS = [
    "trial_id",
    "master_seed",
    "deployment_seed",
    "energy_seed",
    "demand_seed",
    "mobility_seed",
    "efficiency_seed",
    "scenario_seed",
    "algorithm_seed",
]


def generate_seed_rows(trials: int = 50, base_seed: int = 2026062300) -> list[dict[str, int]]:
    """Generate separated deterministic seed streams for paired trials."""
    rows: list[dict[str, int]] = []
    for trial_id in range(trials):
        master = base_seed + trial_id * 100
        rows.append(
            {
                "trial_id": trial_id,
                "master_seed": master,
                "deployment_seed": master + 1,
                "energy_seed": master + 2,
                "demand_seed": master + 3,
                "mobility_seed": master + 4,
                "efficiency_seed": master + 5,
                "scenario_seed": master + 6,
                "algorithm_seed": master + 7,
            }
        )
    return rows


def save_seed_rows(rows: Iterable[dict[str, int]], path: str | Path) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SEED_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: int(row[field]) for field in SEED_FIELDS})


def load_seed_rows(path: str | Path) -> list[dict[str, int]]:
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append({field: int(row[field]) for field in SEED_FIELDS})
    return rows
