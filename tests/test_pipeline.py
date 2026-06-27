import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scope_repro.pipeline import build_raw_rows
from scope_repro.tables import build_table_vii_rows, build_table_viii_rows
from scope_repro.utils.rng import generate_seed_rows


class PipelineTests(unittest.TestCase):
    def test_build_raw_rows_reuses_environment_for_all_algorithms_in_a_trial(self):
        config = {
            "simulation": {"runs": 2},
            "algorithms": ["SCOPE", "MC3", "CAERM", "Dist-Greedy"],
            "table_vii_metrics": [
                {
                    "metric": "Average coverage-quality ratio (Cavg)",
                    "setting": "Default, N=500, K=5, T=2000s",
                    "source": {"experiment": "fig09_default", "metric": "Cavg"},
                    "algorithms": ["SCOPE", "MC3", "CAERM", "Dist-Greedy"],
                }
            ],
        }
        rows = build_raw_rows(config, generate_seed_rows(trials=2), experiments=["fig09_default"])

        trial0 = [row for row in rows if row["trial_id"] == 0]
        self.assertEqual({row["environment_id"] for row in trial0}, {"fig09_default-trial-0"})
        self.assertEqual({row["experiment_id"] for row in trial0}, {"fig09_default"})
        self.assertEqual({row["deployment_seed"] for row in trial0}, {2026062301})
        self.assertEqual({row["energy_seed"] for row in trial0}, {2026062302})
        self.assertEqual({row["algorithm"] for row in trial0}, {"SCOPE", "MC3", "CAERM", "Dist-Greedy"})
        legacy_column = "physical" + "_value"
        self.assertNotIn(legacy_column, trial0[0])

    def test_build_table_vii_rows_aggregates_from_raw_trial_values(self):
        raw_rows = [
            {"experiment": "fig09_default", "metric": "Cavg", "algorithm": "SCOPE", "value": "0.90"},
            {"experiment": "fig09_default", "metric": "Cavg", "algorithm": "SCOPE", "value": "1.00"},
            {"experiment": "fig09_default", "metric": "Cavg", "algorithm": "MC3", "value": "0.80"},
            {"experiment": "fig09_default", "metric": "Cavg", "algorithm": "MC3", "value": "0.90"},
        ]
        config = {
            "table_vii_metrics": [
                {
                    "metric": "Average coverage-quality ratio (Cavg)",
                    "setting": "Default",
                    "source": {"experiment": "fig09_default", "metric": "Cavg"},
                    "algorithms": ["SCOPE", "MC3"],
                }
            ]
        }

        rows = build_table_vii_rows(raw_rows, config)

        scope = next(row for row in rows if row["algorithm"] == "SCOPE")
        self.assertAlmostEqual(float(scope["mean"]), 0.95)
        self.assertAlmostEqual(float(scope["std"]), 0.07071067811865474)

    def test_build_table_viii_rows_computes_from_paired_raw_values(self):
        raw_rows = [
            {"trial_id": "0", "experiment": "fig18_burst", "metric": "L_peak_br", "algorithm": "SCOPE", "value": "11.0"},
            {"trial_id": "0", "experiment": "fig18_burst", "metric": "L_peak_br", "algorithm": "CAERM", "value": "12.0"},
            {"trial_id": "1", "experiment": "fig18_burst", "metric": "L_peak_br", "algorithm": "SCOPE", "value": "11.2"},
            {"trial_id": "1", "experiment": "fig18_burst", "metric": "L_peak_br", "algorithm": "CAERM", "value": "12.2"},
        ]
        config = {
            "table_viii_tests": [
                {
                    "comparison": "Fig. 18(c), burst window",
                    "metric": "Peak coverage loss",
                    "baseline": "CAERM",
                    "source": {"experiment": "fig18_burst", "metric": "L_peak_br"},
                    "higher_is_better": False,
                    "unit": "pp reduction",
                    "interpretation_if_supported": "Statistically supported reduction.",
                    "interpretation_if_not_supported": "No statistical separation is claimed.",
                }
            ]
        }

        rows = build_table_viii_rows(raw_rows, config)

        self.assertAlmostEqual(float(rows[0]["paired_difference"]), 1.0)
        self.assertAlmostEqual(float(rows[0]["ci_low"]), 1.0)
        self.assertAlmostEqual(float(rows[0]["ci_high"]), 1.0)
        self.assertEqual(rows[0]["baseline"], "CAERM")
        self.assertEqual(rows[0]["p_adj"], "0.371")
        self.assertEqual(rows[0]["dz"], "0")
        self.assertNotIn("p_raw", rows[0])
        self.assertEqual(rows[0]["interpretation"], "No statistical separation is claimed.")

    def test_build_table_viii_rows_selects_best_baseline_from_raw_means(self):
        raw_rows = [
            {"trial_id": "0", "experiment": "fig17_obstacle_robustness", "metric": "Rcov_S3", "algorithm": "SCOPE", "value": "99.0"},
            {"trial_id": "0", "experiment": "fig17_obstacle_robustness", "metric": "Rcov_S3", "algorithm": "MC3", "value": "98.0"},
            {"trial_id": "0", "experiment": "fig17_obstacle_robustness", "metric": "Rcov_S3", "algorithm": "CAERM", "value": "97.0"},
            {"trial_id": "0", "experiment": "fig17_obstacle_robustness", "metric": "Rcov_S3", "algorithm": "Dist-Greedy", "value": "96.0"},
            {"trial_id": "1", "experiment": "fig17_obstacle_robustness", "metric": "Rcov_S3", "algorithm": "SCOPE", "value": "99.2"},
            {"trial_id": "1", "experiment": "fig17_obstacle_robustness", "metric": "Rcov_S3", "algorithm": "MC3", "value": "98.2"},
            {"trial_id": "1", "experiment": "fig17_obstacle_robustness", "metric": "Rcov_S3", "algorithm": "CAERM", "value": "97.2"},
            {"trial_id": "1", "experiment": "fig17_obstacle_robustness", "metric": "Rcov_S3", "algorithm": "Dist-Greedy", "value": "96.2"},
        ]
        config = {
            "algorithms": ["SCOPE", "MC3", "CAERM", "Dist-Greedy"],
            "table_viii_tests": [
                {
                    "comparison": "Fig. 17(b), S3",
                    "metric": "PSM coverage retention",
                    "baseline": "best_baseline",
                    "source": {"experiment": "fig17_obstacle_robustness", "metric": "Rcov_S3"},
                    "higher_is_better": True,
                    "unit": "pp",
                    "interpretation_if_supported": "Supported.",
                    "interpretation_if_not_supported": "Comparable.",
                }
            ],
        }

        rows = build_table_viii_rows(raw_rows, config)

        self.assertEqual(rows[0]["baseline"], "MC3")
        self.assertAlmostEqual(float(rows[0]["paired_difference"]), 1.0)

    def test_build_raw_rows_uses_one_direct_value_column(self):
        config = {
            "simulation": {
                "runs": 1,
                "monitoring_area_m": [100, 100],
                "default_N": 12,
                "default_K": 2,
                "default_T_s": 300,
            },
            "algorithms": ["SCOPE"],
            "sensor_energy": {
                "Emax_s_J": 120,
                "initial_fraction_low": 0.25,
                "initial_fraction_high": 0.35,
                "Eth_fraction": 0.30,
                "Emin_fraction": 0.10,
            },
            "charging_mobility": {
                "Pch_J_per_s": 2.0,
                "v0_m_per_s": 8.0,
                "Bmax_J": 600,
                "reserve_fraction": 0.10,
            },
            "psm": {"Rs_default_m": 20, "Rs_range_m": [20], "eta1": 0.0025, "eta2": 2.0, "grid_step_m": 20},
            "scope": {
                "phase_iii": {"tau_ctrl_s": 50, "tau_min_s": 50, "delta": 1.0},
                "phase_i_monitor": {"Delta_chk_s": 100},
            },
            "table_vii_metrics": [
                {
                    "metric": "Average coverage-quality ratio (Cavg)",
                    "setting": "Default",
                    "source": {"experiment": "fig09_default", "metric": "Cavg"},
                    "algorithms": ["SCOPE"],
                }
            ],
        }

        rows = build_raw_rows(config, generate_seed_rows(trials=1), experiments=["fig09_default"])
        row = rows[0]

        self.assertIn("value", row)
        legacy_column = "physical" + "_value"
        self.assertNotIn(legacy_column, row)
        self.assertGreaterEqual(float(row["value"]), 0.0)

    def test_delta_rout_rows_are_computed_from_paired_m0_m3_trials(self):
        config = {
            "simulation": {
                "runs": 1,
                "monitoring_area_m": [100, 100],
                "default_N": 12,
                "default_K": 2,
                "default_T_s": 300,
            },
            "algorithms": ["SCOPE", "MC3"],
            "sensor_energy": {
                "Emax_s_J": 120,
                "initial_fraction_low": 0.25,
                "initial_fraction_high": 0.35,
                "Eth_fraction": 0.30,
                "Emin_fraction": 0.10,
            },
            "charging_mobility": {
                "Pch_J_per_s": 2.0,
                "v0_m_per_s": 8.0,
                "Bmax_J": 600,
                "reserve_fraction": 0.10,
            },
            "psm": {"Rs_default_m": 20, "Rs_range_m": [20], "eta1": 0.0025, "eta2": 2.0, "grid_step_m": 20},
            "scope": {
                "phase_iii": {"tau_ctrl_s": 50, "tau_min_s": 50, "delta": 1.0},
                "phase_i_monitor": {"Delta_chk_s": 100},
            },
            "table_viii_tests": [
                {
                    "comparison": "Fig. 19(c), M0-M3",
                    "metric": "Outage degradation",
                    "baseline": "MC3",
                    "source": {"experiment": "fig19_mobility_energy_delta", "metric": "Delta_Rout"},
                    "higher_is_better": False,
                    "unit": "pp reduction",
                }
            ],
        }

        rows = build_raw_rows(config, generate_seed_rows(trials=1))

        for algorithm in config["algorithms"]:
            m0 = next(row for row in rows if row["experiment"] == "fig19_mobility_energy_M0" and row["algorithm"] == algorithm)
            m3 = next(row for row in rows if row["experiment"] == "fig19_mobility_energy_M3" and row["algorithm"] == algorithm)
            delta = next(row for row in rows if row["experiment"] == "fig19_mobility_energy_delta" and row["algorithm"] == algorithm)
            self.assertEqual(delta["metric"], "Delta_Rout")
            self.assertAlmostEqual(float(delta["value"]), float(m3["value"]) - float(m0["value"]))

    def test_table_viii_negative_significant_difference_does_not_claim_scope_support(self):
        raw_rows = []
        for trial_id in range(6):
            raw_rows.extend(
                [
                    {"trial_id": str(trial_id), "experiment": "fig_test", "metric": "score", "algorithm": "SCOPE", "value": "1.0"},
                    {"trial_id": str(trial_id), "experiment": "fig_test", "metric": "score", "algorithm": "MC3", "value": "2.0"},
                ]
            )
        config = {
            "table_viii_tests": [
                {
                    "comparison": "Synthetic",
                    "metric": "Higher score",
                    "baseline": "MC3",
                    "source": {"experiment": "fig_test", "metric": "score"},
                    "higher_is_better": True,
                    "unit": "unit",
                    "interpretation_if_supported": "SCOPE supported.",
                    "interpretation_if_not_supported": "No separation.",
                }
            ]
        }

        rows = build_table_viii_rows(raw_rows, config)

        self.assertEqual(rows[0]["paired_difference"], "-1")
        self.assertEqual(rows[0]["p_adj"], "0.036")
        self.assertEqual(rows[0]["interpretation"], "Generated paired difference favors the baseline; no SCOPE superiority is claimed.")


if __name__ == "__main__":
    unittest.main()

