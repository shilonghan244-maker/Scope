from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scope_repro.io import read_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export regenerated Table VII and VIII numbers for manuscript updates.")
    parser.add_argument("--tables", default="results/tables")
    parser.add_argument("--out", default="results/manuscript_numbers.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tables_dir = ROOT / args.tables
    table_vii = read_csv(tables_dir / "table_vii_statistics.csv")
    table_viii = read_csv(tables_dir / "table_viii_paired_tests.csv")
    lines = [
        "# Regenerated Manuscript Numbers",
        "",
        "These values are exported from generated table CSV files. Update the manuscript from this file after rerunning the released seed pool and table-generation workflow.",
        "",
        "## Table VII",
        "",
        "| Metric | Setting | Algorithm | n | Mean | Std | 95% CI |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in table_vii:
        lines.append(
            f"| {row['metric']} | {row['setting']} | {row['algorithm']} | {row['n']} | "
            f"{row['mean']} | {row['std']} | [{row['ci_low']}, {row['ci_high']}] |"
        )
    lines.extend(
        [
            "",
            "## Table VIII",
            "",
            "Summary of paired statistical tests for representative key comparisons. Differences, confidence intervals, Holm-adjusted p-values, and paired effect sizes are computed from the released paired trial records.",
            "",
            "| Comparison | Metric | Baseline | Difference | 95% CI | Test | p_adj | dz | Unit | Interpretation |",
            "| --- | --- | --- | ---: | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in table_viii:
        lines.append(
            f"| {row['comparison']} | {row['metric']} | {row['baseline']} | {row['paired_difference']} | "
            f"[{row['ci_low']}, {row['ci_high']}] | {row['test']} | {row['p_adj']} | {row['dz']} | "
            f"{row['unit']} | {row['interpretation']} |"
        )
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote manuscript number export to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
