from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from scope_repro.physical import build_environment, simulate_trial


def build_raw_rows(config: dict, seed_rows: Iterable[dict[str, int]], experiments: list[str] | None = None) -> list[dict]:
    selected = _expand_selected_experiments(set(experiments)) if experiments else None
    rows: list[dict] = []
    requested = _requested_metrics(config)
    experiment_ids = sorted(requested.keys())
    if selected is not None:
        experiment_ids = [experiment_id for experiment_id in experiment_ids if experiment_id in selected]

    for seed_row in seed_rows:
        trial_id = int(seed_row["trial_id"])
        for experiment_id in experiment_ids:
            environment = build_environment(config, seed_row, experiment_id)
            for algorithm in config.get("algorithms", ["SCOPE", "MC3", "CAERM", "Dist-Greedy"]):
                result = simulate_trial(config, seed_row, experiment_id, algorithm, environment)
                metric_values = result.metric_values(environment, config)
                for metric in requested[experiment_id]:
                    if metric not in metric_values:
                        continue
                    rows.append(
                        {
                            "trial_id": trial_id,
                            "experiment": experiment_id,
                            "table_metric": _table_metric_name(config, experiment_id, metric),
                            "setting": _metric_setting(config, experiment_id, metric),
                            "metric": metric,
                            "algorithm": algorithm,
                            "value": f"{metric_values[metric]:.12g}",
                            "experiment_id": experiment_id,
                            "scenario": _scenario_for_experiment(experiment_id),
                            "environment_id": f"{experiment_id}-trial-{trial_id}",
                            "master_seed": seed_row["master_seed"],
                            "deployment_seed": seed_row["deployment_seed"],
                            "energy_seed": seed_row["energy_seed"],
                            "demand_seed": seed_row["demand_seed"],
                            "mobility_seed": seed_row["mobility_seed"],
                            "efficiency_seed": seed_row["efficiency_seed"],
                            "scenario_seed": seed_row["scenario_seed"],
                            "algorithm_seed": seed_row["algorithm_seed"],
                        }
                    )
    _append_derived_delta_rows(rows, config)
    if selected is not None:
        rows = [row for row in rows if row["experiment"] in selected or row["experiment"] == "fig19_mobility_energy_delta"]
    return rows


def _requested_metrics(config: dict) -> dict[str, list[str]]:
    requested: dict[str, set[str]] = defaultdict(set)
    for spec in config.get("table_vii_metrics", []):
        source = spec["source"]
        requested[source["experiment"]].add(source["metric"])
    for spec in config.get("table_viii_tests", []):
        source = spec["source"]
        if source["metric"] == "Delta_Rout":
            requested["fig19_mobility_energy_M0"].add("Rout_M3")
            requested["fig19_mobility_energy_M3"].add("Rout_M3")
        elif source["metric"] == "Delta_Rcov":
            requested["fig19_mobility_energy_M0"].add("Rcov_M3")
            requested["fig19_mobility_energy_M3"].add("Rcov_M3")
        else:
            requested[source["experiment"]].add(source["metric"])
    for figure in config.get("figures", []):
        requested[figure.get("source_experiment", "fig09_default")].add("Cavg")
    if not requested:
        requested["fig09_default"].update({"Cavg", "eta_travel", "Davg", "Lavg"})
    return {experiment: sorted(metrics) for experiment, metrics in requested.items()}


def _append_derived_delta_rows(rows: list[dict], config: dict) -> None:
    requested_metrics = {test.get("source", {}).get("metric") for test in config.get("table_viii_tests", [])}
    derivations = []
    if "Delta_Rout" in requested_metrics:
        derivations.append(("Rout_M3", "Delta_Rout", "M0-M3 paired mobility-energy outage stress", -1.0, 1.0))
    if "Delta_Rcov" in requested_metrics:
        derivations.append(("Rcov_M3", "Delta_Rcov", "M0-M3 paired coverage-retention degradation", 1.0, -1.0))
    if not derivations:
        return

    by_key: dict[tuple[int, str, str, str], dict] = {}
    for row in rows:
        if row["experiment"] not in {"fig19_mobility_energy_M0", "fig19_mobility_energy_M3"}:
            continue
        by_key[(int(row["trial_id"]), row["algorithm"], row["experiment"], row["metric"])] = row

    algorithms = config.get("algorithms", ["SCOPE", "MC3", "CAERM", "Dist-Greedy"])
    trial_ids = sorted({key[0] for key in by_key})
    for source_metric, derived_metric, setting, m0_factor, m3_factor in derivations:
        for trial_id in trial_ids:
            for algorithm in algorithms:
                m0 = by_key.get((trial_id, algorithm, "fig19_mobility_energy_M0", source_metric))
                m3 = by_key.get((trial_id, algorithm, "fig19_mobility_energy_M3", source_metric))
                if not m0 or not m3:
                    continue
                delta_row = dict(m3)
                value = m0_factor * float(m0["value"]) + m3_factor * float(m3["value"])
                delta_row.update(
                    {
                        "experiment": "fig19_mobility_energy_delta",
                        "table_metric": derived_metric,
                        "setting": setting,
                        "metric": derived_metric,
                        "value": f"{value:.12g}",
                        "experiment_id": "fig19_mobility_energy_delta",
                        "scenario": "M0-M3",
                        "environment_id": f"fig19_mobility_energy_delta-trial-{trial_id}",
                    }
                )
                rows.append(delta_row)


def _expand_selected_experiments(selected: set[str]) -> set[str]:
    expanded = set(selected)
    if "fig19_mobility_energy_delta" in expanded:
        expanded.update({"fig19_mobility_energy_M0", "fig19_mobility_energy_M3"})
    return expanded


def _table_metric_name(config: dict, experiment_id: str, metric: str) -> str:
    for spec in config.get("table_vii_metrics", []):
        source = spec["source"]
        if source["experiment"] == experiment_id and source["metric"] == metric:
            return spec["metric"]
    return metric


def _metric_setting(config: dict, experiment_id: str, metric: str) -> str:
    for spec in config.get("table_vii_metrics", []):
        source = spec["source"]
        if source["experiment"] == experiment_id and source["metric"] == metric:
            return spec.get("setting", experiment_id)
    return experiment_id


def _scenario_for_experiment(experiment_id: str) -> str:
    if experiment_id == "fig17_obstacle_robustness":
        return "S3"
    if experiment_id == "fig18_burst":
        return "Burst"
    if experiment_id in {"fig19_mobility_energy", "fig19_mobility_energy_M3"}:
        return "M3"
    if experiment_id == "fig19_mobility_energy_M0":
        return "M0"
    if experiment_id == "fig19_mobility_energy_delta":
        return "M0-M3"
    if experiment_id == "fig20_relearning":
        return "B1"
    return "S0"
