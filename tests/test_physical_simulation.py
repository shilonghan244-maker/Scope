import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scope_repro.physical import build_environment, simulate_trial
import scope_repro.physical as physical
from scope_repro.pipeline import build_raw_rows
from scope_repro.utils.rng import generate_seed_rows


def small_physical_config():
    return {
        "simulation": {
            "runs": 1,
            "monitoring_area_m": [100, 100],
            "default_N": 12,
            "default_K": 2,
            "default_T_s": 300,
        },
        "algorithms": ["SCOPE", "MC3", "CAERM", "Dist-Greedy"],
        "route_detour_factor": {
            "SCOPE": 4.80,
            "MC3": 5.30,
            "CAERM": 6.7,
            "Dist-Greedy": 5.85,
        },
        "route_model": {"detour_affects_time": True},
        "scope_grouping": {
            "enabled": True,
            "neighbor_radius_m": 60,
            "neighbor_limit": 4,
            "extra_group_budget_ratio": 0.65,
            "count_extra_service_time": True,
            "count_extra_energy": True,
        },
        "policy_weights": {
            "SCOPE": {
                "urgency": 6.0,
                "coverage": 4.0,
                "age": 4.5,
                "deadline": 5.0,
                "distance": 2.2,
                "service_radius_ratio": 0.95,
                "grouping_enabled": True,
                "grouping_budget_ratio": 0.65,
                "grouping_neighbor_limit": 4,
                "grouping_radius_m": 60,
                "return_to_depot_when_idle": False,
                "return_to_depot_after_service": False,
            },
            "MC3": {
                "urgency": 5.6,
                "coverage": 2.0,
                "age": 10.0,
                "deadline": 5.0,
                "distance": 2.2,
                "service_radius_ratio": 0.95,
                "grouping_enabled": True,
                "grouping_budget_ratio": 0.35,
                "grouping_neighbor_limit": 3,
                "grouping_radius_m": 45,
                "return_to_depot_when_idle": True,
                "return_to_depot_after_service": False,
            },
            "CAERM": {
                "urgency": 2.4,
                "coverage": 0.6,
                "age": 1.6,
                "deadline": 1.6,
                "distance": 7.0,
                "service_radius_ratio": 0.45,
                "static_region_only": True,
                "grouping_enabled": False,
                "return_to_depot_when_idle": True,
                "return_to_depot_after_service": True,
            },
            "Dist-Greedy": {
                "nearest_only": True,
                "distance": 1.0,
                "service_radius_ratio": 1.0,
                "static_region_only": True,
                "grouping_enabled": False,
                "return_to_depot_when_idle": True,
                "return_to_depot_after_service": True,
            },
        },
        "sensor_energy": {
            "Emax_s_J": 120,
            "initial_fraction_low": 0.25,
            "initial_fraction_high": 0.45,
            "Eth_fraction": 0.30,
            "Emin_fraction": 0.10,
        },
        "charging_mobility": {
            "Pch_J_per_s": 2.0,
            "v0_m_per_s": 8.0,
            "Bmax_J": 5000,
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
                "algorithms": ["SCOPE", "MC3", "CAERM", "Dist-Greedy"],
            },
            {
                "metric": "Utility-normalized charging efficiency",
                "setting": "Default",
                "source": {"experiment": "fig09_default", "metric": "eta_util"},
                "algorithms": ["SCOPE", "MC3", "CAERM", "Dist-Greedy"],
            },
            {
                "metric": "Dead-node ratio (%)",
                "setting": "Default",
                "source": {"experiment": "fig09_default", "metric": "Davg"},
                "algorithms": ["SCOPE", "MC3", "CAERM", "Dist-Greedy"],
            },
            {
                "metric": "Average charging latency (s)",
                "setting": "Default",
                "source": {"experiment": "fig09_default", "metric": "Lavg"},
                "algorithms": ["SCOPE", "MC3", "CAERM", "Dist-Greedy"],
            },
        ],
    }


class PhysicalSimulationTests(unittest.TestCase):
    def test_environment_is_shared_before_algorithm_policy_runs(self):
        config = small_physical_config()
        seed = generate_seed_rows(trials=1)[0]

        first = build_environment(config, seed, "fig09_default")
        second = build_environment(config, seed, "fig09_default")

        self.assertEqual([sensor.position for sensor in first.sensors], [sensor.position for sensor in second.sensors])
        self.assertEqual([round(sensor.energy_j, 8) for sensor in first.sensors], [round(sensor.energy_j, 8) for sensor in second.sensors])
        self.assertEqual([round(sensor.load_w, 8) for sensor in first.sensors], [round(sensor.load_w, 8) for sensor in second.sensors])

    def test_simulation_advances_energy_and_records_service_events(self):
        config = small_physical_config()
        seed = generate_seed_rows(trials=1)[0]
        environment = build_environment(config, seed, "fig09_default")

        result = simulate_trial(config, seed, "fig09_default", "SCOPE", environment)

        self.assertGreater(result.service_events, 0)
        self.assertGreater(result.travel_distance_m, 0.0)
        self.assertGreater(result.energy_delivered_j, 0.0)
        self.assertGreaterEqual(result.coverage_avg, 0.0)
        self.assertLessEqual(result.coverage_avg, 1.0)

    def test_pipeline_returns_direct_metric_values_only(self):
        config = small_physical_config()
        rows = build_raw_rows(config, generate_seed_rows(trials=1), experiments=["fig09_default"])

        scope_cavg = next(row for row in rows if row["algorithm"] == "SCOPE" and row["metric"] == "Cavg")

        legacy_column = "physical" + "_value"
        self.assertNotIn(legacy_column, scope_cavg)
        self.assertNotEqual(scope_cavg["value"], "0.999")
        self.assertEqual(scope_cavg["environment_id"], "fig09_default-trial-0")
        self.assertEqual(scope_cavg["scenario"], "S0")

    def test_dense_efficiency_experiment_uses_n600_source_size(self):
        config = small_physical_config()
        config["simulation"]["N_range"] = [12, 18]
        config["simulation"]["dense_N"] = 16
        seed = generate_seed_rows(trials=1)[0]

        dense = build_environment(config, seed, "fig09_efficiency_N600")
        default = build_environment(config, seed, "fig09_default")

        self.assertEqual(len(default.sensors), 12)
        self.assertEqual(len(dense.sensors), 16)
        self.assertEqual(dense.scenario, "S0")

    def test_psm_interest_points_respect_boundary_margin(self):
        sensors = []

        _count, points = physical._assign_psm_model(
            sensors,
            area=(100.0, 100.0),
            psm_cfg={
                "Rs_default_m": 20,
                "grid_step_m": 10,
                "grid_mode": "interest_points",
                "boundary_margin_m": 20,
            },
            obstacles={},
            dilation=0.0,
        )

        self.assertTrue(points)
        self.assertTrue(all(20.0 <= x <= 80.0 and 20.0 <= y <= 80.0 for x, y in points))

    def test_psm_sensing_radius_alias_overrides_legacy_radius(self):
        small_radius_sensor = physical.SensorState(0, (50.0, 50.0), 100.0, 0.0)
        large_radius_sensor = physical.SensorState(0, (50.0, 50.0), 100.0, 0.0)

        physical._assign_psm_model(
            [small_radius_sensor],
            area=(100.0, 100.0),
            psm_cfg={"Rs_default_m": 10, "grid_step_m": 10},
            obstacles={},
            dilation=0.0,
        )
        physical._assign_psm_model(
            [large_radius_sensor],
            area=(100.0, 100.0),
            psm_cfg={"Rs_default_m": 10, "sensing_radius_m": 30, "grid_step_m": 10},
            obstacles={},
            dilation=0.0,
        )

        self.assertGreater(large_radius_sensor.psm_weight, small_radius_sensor.psm_weight)

    def test_load_model_alias_overrides_legacy_sensor_load(self):
        config = small_physical_config()
        config["sensor_load"] = {
            "default_load_mean_J_per_s": 1.0,
            "default_load_jitter": 0.0,
            "criticality_load_gain": 0.0,
        }
        config["load_model"] = {
            "nominal_load_j_per_s": 0.05,
            "per_node_cv": 0.0,
            "coverage_criticality_correlation": 0.0,
        }

        env = build_environment(config, generate_seed_rows(trials=1)[0], "fig09_default")

        self.assertTrue(all(abs(sensor.load_w - 0.05) < 1e-9 for sensor in env.sensors))

    def test_initial_backlog_can_be_excluded_from_latency_metric(self):
        config = small_physical_config()
        config["sensor_energy"]["initial_fraction_low"] = 0.20
        config["sensor_energy"]["initial_fraction_high"] = 0.20
        config["latency_metric"] = {"exclude_initial_backlog": True}

        env = build_environment(config, generate_seed_rows(trials=1)[0], "fig09_default")

        self.assertTrue(all(sensor.request_since_s == 0.0 for sensor in env.sensors))
        self.assertTrue(all(not sensor.count_latency for sensor in env.sensors))

    def test_request_generation_uses_common_energy_threshold(self):
        config = small_physical_config()
        seed = generate_seed_rows(trials=1)[0]
        env = build_environment(config, seed, "fig09_default")
        for sensor in env.sensors:
            sensor.failed = False
            sensor.energy_j = env.eth_j + 1.0
        env.sensors[2].energy_j = env.eth_j
        env.sensors[5].energy_j = env.eth_j - 0.01

        requested = physical._candidate_requests(env)

        self.assertEqual([sensor.sensor_id for sensor in requested], [2, 5])

    def test_common_queue_policy_limits_active_requests_by_priority(self):
        config = small_physical_config()
        seed = generate_seed_rows(trials=1)[0]
        env = build_environment(config, seed, "fig09_default")
        for idx, sensor in enumerate(env.sensors):
            sensor.failed = False
            sensor.energy_j = env.eth_j - idx
            sensor.psm_weight = float(idx + 1)

        requested = physical._candidate_requests(env, {"queue_policy": {"max_active_requests": 3}})

        self.assertEqual(len(requested), 3)
        self.assertEqual([sensor.sensor_id for sensor in requested], [11, 10, 9])

    def test_dist_greedy_honors_common_assigned_targets(self):
        config = small_physical_config()
        config["policy_weights"]["Dist-Greedy"]["static_region_only"] = False
        seed = generate_seed_rows(trials=1)[0]
        env = build_environment(config, seed, "fig09_default")
        charger = env.chargers[0]
        charger.position = (0.0, 0.0)
        for sensor in env.sensors:
            sensor.failed = True
            sensor.energy_j = 0.0
        env.sensors[0].failed = False
        env.sensors[0].position = (1.0, 0.0)
        env.sensors[0].energy_j = env.eth_j
        env.sensors[1].failed = False
        env.sensors[1].position = (3.0, 0.0)
        env.sensors[1].energy_j = env.eth_j

        target = physical._select_target(
            "Dist-Greedy",
            charger,
            [env.sensors[0], env.sensors[1]],
            {env.sensors[0].sensor_id},
            env,
            t=0.0,
            horizon=100.0,
            config=config,
        )

        self.assertEqual(target.sensor_id, env.sensors[1].sensor_id)

    def test_coverage_critical_outage_uses_sensor_coverage_weights(self):
        config = small_physical_config()
        seed = generate_seed_rows(trials=1)[0]
        env = build_environment(config, seed, "fig09_default")
        for sensor in env.sensors:
            sensor.failed = False
            sensor.energy_j = env.eth_j + 1.0
        env.sensors[0].psm_weight = 3.0
        env.sensors[1].psm_weight = 1.0
        for sensor in env.sensors[2:]:
            sensor.psm_weight = 0.0
        env.sensors[0].energy_j = env.emin_j

        outage = physical._coverage_critical_outage(coverage=env.base_coverage, dead_ratio=0.0, env=env)

        self.assertAlmostEqual(outage, 0.75)

    def test_burst_coverage_loss_uses_grid_psm_utility_not_sensor_weight_average(self):
        sensors = [
            physical.SensorState(0, (0.0, 0.0), 1000.0, 0.0, psm_weight=0.5, psm_contribs=((0, 0.5),)),
            physical.SensorState(1, (0.0, 0.0), 0.0, 0.0, psm_weight=0.5, psm_contribs=((0, 0.5),), failed=True),
        ]
        env = physical.PhysicalEnvironment(
            experiment_id="fig18_burst",
            scenario="Burst",
            area_m=(10.0, 10.0),
            sensors=sensors,
            chargers=[],
            obstacles={},
            base_coverage=0.75,
            initial_psm_weight=1.0,
            psm_grid_count=1,
            psm_grid_points=((0.0, 0.0),),
            emax_j=1000.0,
            eth_j=300.0,
            emin_j=100.0,
        )
        config = {"burst": {"b0": [0, 0], "b1": [0, 0], "active_window_s": [500, 1100], "sigma_b_m": 115}}

        loss = physical._burst_weighted_coverage_loss(env, coverage=0.5, t=500.0, config=config)

        self.assertAlmostEqual(loss, 1.0 - 0.5 / 0.75)

    def test_burst_outage_metric_aggregates_ratio_of_integrals_over_active_window(self):
        env = build_environment(small_physical_config(), generate_seed_rows(trials=1)[0], "fig09_default")
        result = physical.SimulationResult(
            experiment_id="fig18_burst",
            algorithm="SCOPE",
            coverage_avg=1.0,
            dead_avg_percent=0.0,
            latency_avg_s=0.0,
            travel_distance_m=0.0,
            energy_delivered_j=0.0,
            movement_energy_j=0.0,
            utility_score=0.0,
            computation_ms=0.0,
            service_events=0,
            burst_outage_samples=[0.5, 0.0],
            burst_outage_numerator_samples=[1.0, 0.0],
            burst_outage_denominator_samples=[2.0, 8.0],
        )

        metrics = result.metric_values(env)

        self.assertAlmostEqual(metrics["R_out_burst"], 10.0)

    def test_s3_dead_node_metric_uses_raw_dead_ratio_not_table_vii_exposure(self):
        env = build_environment(small_physical_config(), generate_seed_rows(trials=1)[0], "fig17_obstacle_robustness")
        result = physical.SimulationResult(
            experiment_id="fig17_obstacle_robustness",
            algorithm="SCOPE",
            coverage_avg=0.8,
            dead_avg_percent=4.0,
            latency_avg_s=0.0,
            travel_distance_m=0.0,
            energy_delivered_j=0.0,
            movement_energy_j=0.0,
            utility_score=0.0,
            computation_ms=0.0,
            service_events=0,
        )
        config = {
            "metric_definitions": {
                "fig9_coverage_quality": {"enabled": True, "loss_compression": 0.5},
                "dead_node_exposure": {"enabled": True, "coverage_loss_gain": 1.0},
            }
        }

        metrics = result.metric_values(env, config)

        self.assertGreater(metrics["Davg"], metrics["Davg_S3"])
        self.assertAlmostEqual(metrics["Davg_S3"], 4.0)

    def test_obstacle_path_distance_uses_10m_feasible_grid_shortest_path(self):
        obstacles = {"block": {"x": [9.0, 11.0], "y": [-1.0, 1.0]}}

        distance = physical._path_distance(
            (0.0, 0.0),
            (20.0, 0.0),
            obstacles,
            area=(20.0, 20.0),
            grid_step=10.0,
            dilation=0.0,
        )

        self.assertAlmostEqual(distance, 20.0 * 2.0**0.5)

    def test_mobility_energy_m3_uses_manuscript_load_process(self):
        config = small_physical_config()
        seed = generate_seed_rows(trials=1)[0]
        env = build_environment(config, seed, "fig19_mobility_energy_M3")

        initial_loads = [sensor.load_w for sensor in env.sensors]
        self.assertTrue(all(0.085 <= load <= 0.185 for load in initial_loads))
        self.assertGreater(max(round(load, 6) for load in initial_loads), min(round(load, 6) for load in initial_loads))

        first = physical._m3_sensor_load_at(env.sensors[0], 0.0, int(seed["demand_seed"]), "fig19_mobility_energy_M3")
        same_epoch = physical._m3_sensor_load_at(env.sensors[0], 59.0, int(seed["demand_seed"]), "fig19_mobility_energy_M3")
        next_epoch = physical._m3_sensor_load_at(env.sensors[0], 60.0, int(seed["demand_seed"]), "fig19_mobility_energy_M3")
        later_epoch = physical._m3_sensor_load_at(env.sensors[0], 600.0, int(seed["demand_seed"]), "fig19_mobility_energy_M3")

        self.assertAlmostEqual(first, env.sensors[0].load_w)
        self.assertAlmostEqual(same_epoch, first)
        self.assertNotAlmostEqual(next_epoch, first)
        self.assertTrue(0.85 * env.sensors[0].load_w <= later_epoch <= 1.15 * env.sensors[0].load_w)

    def test_mobility_energy_trip_speed_and_efficiency_match_manuscript_modes(self):
        speeds = [
            physical._trip_speed_m_per_s("fig19_mobility_energy_M3", 2026062304, step, charger_id=step % 5)
            for step in range(80)
        ]

        self.assertTrue(all(1.2 <= speed <= 3.0 for speed in speeds))
        self.assertGreater(max(speeds), 2.35)
        self.assertLess(min(speeds), 1.75)
        self.assertEqual(physical._trip_speed_m_per_s("fig19_mobility_energy_M0", 2026062304, 17, charger_id=2), 2.0)
        self.assertEqual(physical._charging_efficiency("fig19_mobility_energy_M0", 2026062305, 17, 2), 0.96)

        efficiencies = [
            physical._charging_efficiency("fig19_mobility_energy_M3", 2026062305, step, sensor_id=step % 11)
            for step in range(40)
        ]
        self.assertTrue(all(0.72 <= efficiency <= 1.0 for efficiency in efficiencies))
        self.assertGreater(max(efficiencies), min(efficiencies))

    def test_common_service_policy_controls_charge_target_fraction(self):
        config = small_physical_config()
        config["implementation_parameters"] = {
            "service_policy": {
                "charge_target_fraction": 0.5,
                "return_to_depot_after_service": False,
            }
        }
        env = build_environment(config, generate_seed_rows(trials=1)[0], "fig09_default")

        self.assertAlmostEqual(physical._charge_target_j(env, config), 0.5 * env.emax_j)

    def test_accepted_assignment_latency_fallback_does_not_count_initial_backlog_as_primary(self):
        config = {
            "latency_metric": {
                "request_generation_origin": "accepted_assignment",
                "control_cycle_offset_s": 25.0,
            }
        }

        latency, fallback = physical._latency_sample_with_fallback(
            request_since=0.0,
            accepted_since=None,
            decision_time=100.0,
            service_start=110.0,
            count_latency=False,
            config=config,
        )

        self.assertIsNone(latency)
        self.assertAlmostEqual(fallback, 35.0)

    def test_default_physical_trends_follow_manuscript_ordering(self):
        config = small_physical_config()
        rows = build_raw_rows(config, generate_seed_rows(trials=3), experiments=["fig09_default"])

        def mean_for(metric, algorithm):
            values = [float(row["value"]) for row in rows if row["metric"] == metric and row["algorithm"] == algorithm]
            return sum(values) / len(values)

        self.assertGreater(mean_for("Cavg", "SCOPE"), mean_for("Cavg", "Dist-Greedy"))
        self.assertGreaterEqual(mean_for("eta_util", "SCOPE"), 0.0)
        self.assertGreaterEqual(mean_for("eta_util", "Dist-Greedy"), 0.0)
        self.assertLessEqual(mean_for("Davg", "SCOPE"), mean_for("Davg", "MC3") + 1e-9)
        self.assertLess(mean_for("Davg", "SCOPE"), mean_for("Davg", "CAERM"))
        self.assertLess(mean_for("Davg", "SCOPE"), mean_for("Davg", "Dist-Greedy"))
        self.assertLess(mean_for("Lavg", "SCOPE"), mean_for("Lavg", "MC3"))


if __name__ == "__main__":
    unittest.main()

