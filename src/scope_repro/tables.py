from __future__ import annotations

from collections import defaultdict

from scope_repro.reporting import format_table_value
from scope_repro.statistics import holm_adjust, mean_std_ci, paired_differences, paired_effect_size, wilcoxon_signed_rank_pvalue


TABLE_VII_COLUMNS = ["metric", "setting", "algorithm", "n", "mean", "std", "ci_low", "ci_high"]
TABLE_VIII_COLUMNS = [
    "comparison",
    "metric",
    "baseline",
    "paired_difference",
    "ci_low",
    "ci_high",
    "unit",
    "test",
    "p_adj",
    "dz",
    "interpretation",
]


def build_table_vii_rows(raw_rows: list[dict], config: dict) -> list[dict]:
    grouped: dict[tuple[str, str, str, str, str], list[float]] = defaultdict(list)
    source_to_metric: dict[tuple[str, str], tuple[str, str, list[str]]] = {}
    algorithms_by_metric: dict[str, list[str]] = {}
    for spec in config.get("table_vii_metrics", []):
        table_metric = spec["metric"]
        source = spec["source"]
        algorithms = spec.get("algorithms", config.get("algorithms", []))
        source_to_metric[(source["experiment"], source["metric"])] = (table_metric, spec["setting"], algorithms)
        algorithms_by_metric[table_metric] = algorithms

    for row in raw_rows:
        source_key = (row["experiment"], row["metric"])
        if source_key not in source_to_metric:
            continue
        table_metric, setting, _algorithms = source_to_metric[source_key]
        key = (table_metric, setting, row["experiment"], row["metric"], row["algorithm"])
        grouped[key].append(float(row["value"]))

    output: list[dict] = []
    for spec in config.get("table_vii_metrics", []):
        table_metric = spec["metric"]
        for algorithm in algorithms_by_metric[table_metric]:
            key = (table_metric, spec["setting"], spec["source"]["experiment"], spec["source"]["metric"], algorithm)
            values = grouped.get(key, [])
            if not values:
                continue
            summary = mean_std_ci(values)
            output.append(
                {
                    "metric": table_metric,
                    "setting": spec["setting"],
                    "algorithm": algorithm,
                    "n": int(summary["n"]),
                    "mean": f"{summary['mean']:.12g}",
                    "std": f"{summary['std']:.12g}",
                    "ci_low": f"{summary['ci_low']:.12g}",
                    "ci_high": f"{summary['ci_high']:.12g}",
                }
            )
    return output


def build_table_vi_rows(config: dict) -> list[dict]:
    return [dict(row) for row in config.get("table_vi_communication_overhead", [])]


def build_table_viii_rows(raw_rows: list[dict], config: dict) -> list[dict]:
    raw_index: dict[tuple[str, str, str], dict[int, float]] = defaultdict(dict)
    for row in raw_rows:
        raw_index[(row["experiment"], row["metric"], row["algorithm"])][int(row["trial_id"])] = float(row["value"])

    pending: list[dict] = []
    p_values: list[float] = []
    for test in config.get("table_viii_tests", []):
        source = test["source"]
        higher_is_better = bool(test.get("higher_is_better", True))
        baseline = _resolve_table_viii_baseline(raw_index, source, test, config, higher_is_better)
        scope_map = raw_index[(source["experiment"], source["metric"], "SCOPE")]
        baseline_map = raw_index[(source["experiment"], source["metric"], baseline)]
        common_trials = sorted(set(scope_map.keys()) & set(baseline_map.keys()))
        if not common_trials:
            continue
        scope_values = [scope_map[trial] for trial in common_trials]
        baseline_values = [baseline_map[trial] for trial in common_trials]
        diffs = paired_differences(scope_values, baseline_values, higher_is_better=higher_is_better)
        summary = mean_std_ci(diffs)
        p_value = wilcoxon_signed_rank_pvalue(diffs)
        p_values.append(p_value)
        baseline_label = test.get("baseline_label")
        if baseline_label is None:
            baseline_label = baseline
        pending.append(
            {
                "comparison": test["comparison"],
                "metric": test["metric"],
                "baseline": baseline,
                "baseline_label": baseline_label,
                "n": len(common_trials),
                "paired_difference": summary["mean"],
                "ci_low": summary["ci_low"],
                "ci_high": summary["ci_high"],
                "test": "Wilcoxon",
                "p_raw": p_value,
                "dz": paired_effect_size(scope_values, baseline_values, higher_is_better=higher_is_better),
                "unit": test.get("unit", ""),
                "interpretation_if_supported": test.get("interpretation_if_supported", ""),
                "interpretation_if_not_supported": test.get("interpretation_if_not_supported", ""),
                "interpretation_if_baseline_supported": test.get(
                    "interpretation_if_baseline_supported",
                    "Generated paired difference favors the baseline; no SCOPE superiority is claimed.",
                ),
            }
        )

    adjusted = holm_adjust(p_values)
    rows: list[dict] = []
    for row, p_adj in zip(pending, adjusted):
        ci_low = float(row["ci_low"])
        ci_high = float(row["ci_high"])
        supports_scope = p_adj < 0.05 and ci_low > 0.0 and ci_high > 0.0
        supports_baseline = p_adj < 0.05 and ci_low < 0.0 and ci_high < 0.0
        diff = float(row["paired_difference"])
        if supports_scope:
            interpretation = row["interpretation_if_supported"]
        elif supports_baseline:
            interpretation = row["interpretation_if_baseline_supported"]
        elif diff < 0.0:
            interpretation = (
                "The methods are statistically comparable; no directional advantage is claimed."
            )
        else:
            interpretation = row["interpretation_if_not_supported"]
        rows.append(
            {
                "comparison": row["comparison"],
                "metric": row["metric"],
                "baseline": format_table_value(row["baseline_label"]),
                "paired_difference": format_table_value(row["paired_difference"]),
                "ci_low": format_table_value(row["ci_low"]),
                "ci_high": format_table_value(row["ci_high"]),
                "test": row["test"],
                "p_adj": _format_p_value(p_adj),
                "dz": format_table_value(row["dz"]),
                "unit": row["unit"],
                "interpretation": interpretation,
            }
        )
    return rows


def _uses_best_baseline(test: dict) -> bool:
    return str(test.get("baseline", "")).lower().replace("-", "_").replace(" ", "_") in {
        "best_baseline",
        "best",
    }


def _resolve_table_viii_baseline(
    raw_index: dict[tuple[str, str, str], dict[int, float]],
    source: dict,
    test: dict,
    config: dict,
    higher_is_better: bool,
) -> str:
    if not _uses_best_baseline(test):
        return str(test["baseline"])
    experiment = source["experiment"]
    metric = source["metric"]
    candidates = [algorithm for algorithm in config.get("algorithms", []) if algorithm != "SCOPE"]
    scored: list[tuple[float, str]] = []
    for algorithm in candidates:
        values = list(raw_index.get((experiment, metric, algorithm), {}).values())
        if not values:
            continue
        mean_value = sum(values) / len(values)
        score = mean_value if higher_is_better else -mean_value
        scored.append((score, algorithm))
    if not scored:
        raise ValueError(f"No baseline rows available for {experiment}:{metric}.")
    scored.sort(reverse=True)
    return scored[0][1]


def _format_p_value(value: float) -> str:
    if value < 0.001:
        return "< 0.001"
    return f"{value:.3f}"


def rows_to_latex_table(rows: list[dict], columns: list[str], caption: str, note: str | None = None) -> str:
    lines = ["\\begin{table}[t]", "\\centering", f"\\caption{{{caption}}}", "\\begin{tabular}{" + "l" * len(columns) + "}", "\\hline"]
    lines.append(" & ".join(columns).replace("_", "\\_") + " \\\\")
    lines.append("\\hline")
    for row in rows:
        values = [str(row.get(column, "")).replace("_", "\\_") for column in columns]
        lines.append(" & ".join(values) + " \\\\")
    if note:
        lines.append("\\hline")
        lines.append(f"\\multicolumn{{{len(columns)}}}{{p{{0.98\\linewidth}}}}{{\\footnotesize {note}}} \\\\")
    lines.extend(["\\hline", "\\end{tabular}", "\\end{table}", ""])
    return "\n".join(lines)
