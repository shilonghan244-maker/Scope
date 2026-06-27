from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scope_repro.config import load_config
from scope_repro.io import read_csv, write_csv
from scope_repro.tables import (
    TABLE_VII_COLUMNS,
    TABLE_VIII_COLUMNS,
    build_table_vi_rows,
    build_table_vii_rows,
    build_table_viii_rows,
    rows_to_latex_table,
)

TABLE_VIII_CAPTION = "Summary of paired statistical tests for representative key comparisons."
TABLE_VIII_NOTE = (
    "Note: Table VIII summarizes paired statistical tests for representative key comparisons. "
    "Reported paired differences, confidence intervals, Holm-adjusted p-values, and paired "
    "effect sizes are computed from the released paired Monte Carlo trial records for the "
    "specified comparison in each row. The paired effect size \\(d_z\\) is interpreted jointly "
    "with the corrected p-value and confidence interval. When the confidence interval includes "
    "zero or the adjusted p-value is not below 0.05, the result is interpreted as comparable "
    "performance rather than as a statistically supported separation. pp denotes percentage "
    "points."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SCOPE paper tables from raw trial logs.")
    parser.add_argument("--config", default="configs/paper_default.yaml")
    parser.add_argument("--input", default="results/raw")
    parser.add_argument("--output", default="results/tables")
    return parser.parse_args()


def _write_tex(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    config = load_config(ROOT / args.config)
    raw_rows = read_csv(ROOT / args.input / "trial_metrics.csv")
    out = ROOT / args.output

    table_vi = build_table_vi_rows(config)
    table_vii = build_table_vii_rows(raw_rows, config)
    table_viii = build_table_viii_rows(raw_rows, config)

    write_csv(out / "table_vi_communication_overhead.csv", table_vi)
    write_csv(out / "table_vii_statistics.csv", table_vii, TABLE_VII_COLUMNS)
    write_csv(out / "table_viii_paired_tests.csv", table_viii, TABLE_VIII_COLUMNS)
    _write_tex(out / "table_vi_communication_overhead.tex", rows_to_latex_table(table_vi, list(table_vi[0].keys()), "Communication overhead."))
    _write_tex(out / "table_vii_statistics.tex", rows_to_latex_table(table_vii, TABLE_VII_COLUMNS, "Statistical summary."))
    _write_tex(out / "table_viii_paired_tests.tex", rows_to_latex_table(table_viii, TABLE_VIII_COLUMNS, TABLE_VIII_CAPTION, TABLE_VIII_NOTE))
    print(f"Wrote tables to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
