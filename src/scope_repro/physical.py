from __future__ import annotations

import copy
import heapq
import math
import random
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable

from scope_repro.models.mobility import euclidean
from scope_repro.models.psm import detection_probability
from scope_repro.scenarios.burst import burst_multiplier, moving_hotspot_center
from scope_repro.scenarios.obstacles import point_in_any_obstacle


DEFAULT_OBSTACLES = {
    "O1": {"x": [90, 130], "y": [350, 425]},
    "O2": {"x": [170, 190], "y": [220, 275]},
    "O3": {"x": [205, 245], "y": [130, 215]},
    "O4": {"x": [285, 325], "y": [370, 465]},
    "O5": {"x": [325, 400], "y": [360, 390]},
    "O6": {"x": [390, 455], "y": [255, 285]},
    "O7": {"x": [430, 465], "y": [285, 330]},
    "O8": {"x": [335, 380], "y": [135, 170]},
    "O9": {"x": [420, 445], "y": [30, 85]},
}

MOBILITY_ENERGY_V0_M_PER_S = 2.0
MOBILITY_ENERGY_VMIN_M_PER_S = 1.2
MOBILITY_ENERGY_VMAX_M_PER_S = 3.0
MOBILITY_ENERGY_SIGMA_V_M_PER_S = 0.35
M0_SENSOR_LOAD_J_PER_S = 0.10
M0_CHARGING_EFFICIENCY = 0.96
M3_PI0_LOW_J_PER_S = 0.085
M3_PI0_HIGH_J_PER_S = 0.185
M3_LOAD_TAU_S = 60.0
M3_LOAD_ALPHA = 0.85
M3_LOAD_SIGMA = 0.03
M3_LOAD_XI_MAX = 0.15
M3_ETA_LOW = 0.72
M3_ETA_HIGH = 1.0


@dataclass
class SensorState:
    sensor_id: int
    position: tuple[float, float]
    energy_j: float
    load_w: float
    psm_weight: float = 0.0
    psm_contribs: tuple[tuple[int, float], ...] = ()
    request_since_s: float | None = None
    count_latency: bool = True
    latency_origin_s: float | None = None
    failed: bool = False
    load_perturbation_epoch: int = 0
    load_perturbation_xi: float = 0.0


@dataclass
class ChargerState:
    charger_id: int
    position: tuple[float, float]
    battery_j: float
    travel_distance_m: float = 0.0
    service_events: int = 0
    available_at_s: float = 0.0


@dataclass
class PhysicalEnvironment:
    experiment_id: str
    scenario: str
    area_m: tuple[float, float]
    sensors: list[SensorState]
    chargers: list[ChargerState]
    obstacles: dict
    base_coverage: float
    initial_psm_weight: float
    psm_grid_count: int
    psm_grid_points: tuple[tuple[float, float], ...]
    emax_j: float
    eth_j: float
    emin_j: float

    def clone(self) -> "PhysicalEnvironment":
        sensors = [
            SensorState(
                sensor.sensor_id,
                sensor.position,
                sensor.energy_j,
                sensor.load_w,
                sensor.psm_weight,
                sensor.psm_contribs,
                sensor.request_since_s,
                sensor.count_latency,
                sensor.latency_origin_s,
                sensor.failed,
                sensor.load_perturbation_epoch,
                sensor.load_perturbation_xi,
            )
            for sensor in self.sensors
        ]
        chargers = [copy.copy(charger) for charger in self.chargers]
        return PhysicalEnvironment(
            experiment_id=self.experiment_id,
            scenario=self.scenario,
            area_m=self.area_m,
            sensors=sensors,
            chargers=chargers,
            obstacles=self.obstacles,
            base_coverage=self.base_coverage,
            initial_psm_weight=self.initial_psm_weight,
            psm_grid_count=self.psm_grid_count,
            psm_grid_points=self.psm_grid_points,
            emax_j=self.emax_j,
            eth_j=self.eth_j,
            emin_j=self.emin_j,
        )

    def coverage_ratio(self) -> float:
        return _psm_coverage(self)


@dataclass
class SimulationResult:
    experiment_id: str
    algorithm: str
    coverage_avg: float
    dead_avg_percent: float
    latency_avg_s: float
    travel_distance_m: float
    energy_delivered_j: float
    movement_energy_j: float
    utility_score: float
    computation_ms: float
    service_events: int
    seed_token: int = 0
    coverage_samples: list[float] = field(default_factory=list)
    dead_samples: list[float] = field(default_factory=list)
    burst_loss_samples: list[float] = field(default_factory=list)
    burst_outage_samples: list[float] = field(default_factory=list)
    burst_outage_numerator_samples: list[float] = field(default_factory=list)
    burst_outage_denominator_samples: list[float] = field(default_factory=list)
    outage_samples: list[float] = field(default_factory=list)

    def metric_values(self, environment: PhysicalEnvironment, config: dict | None = None) -> dict[str, float]:
        metric_cfg = config.get("metric_definitions", {}) if isinstance(config, dict) else {}
        travel_eff = self.energy_delivered_j / max(self.travel_distance_m, 1.0)
        energy_cost = self.energy_delivered_j + self.movement_energy_j
        coverage_value = _fig9_coverage_value(self.coverage_avg, self.dead_avg_percent, metric_cfg)
        dead_value = _dead_node_exposure_value(self.dead_avg_percent, coverage_value, metric_cfg)
        utility_eff = 0.0 if energy_cost <= 1e-9 else 1000.0 * self.utility_score / energy_cost
        if bool(metric_cfg.get("utility_efficiency_coverage_weighted", False)):
            utility_eff *= coverage_value
        utility_quality_exponent = float(metric_cfg.get("utility_quality_exponent", 0.0))
        if utility_quality_exponent > 0.0:
            utility_eff *= max(coverage_value, 0.0) ** utility_quality_exponent
        utility_eff *= float(metric_cfg.get("utility_unit_scale", 1.0))
        retention = _reference_coverage_retention(self.coverage_avg, environment)
        peak_burst_loss = max(self.burst_loss_samples) * 100.0 if self.burst_loss_samples else max(0.0, 1.0 - self.coverage_avg) * 100.0
        burst_outage_denominator = sum(self.burst_outage_denominator_samples)
        if burst_outage_denominator > 1e-12:
            burst_outage = 100.0 * sum(self.burst_outage_numerator_samples) / burst_outage_denominator
        else:
            burst_outage = _mean_percent(self.burst_outage_samples)
        rout = _mean_percent(self.outage_samples)
        return {
            "Cavg": coverage_value,
            "eta_travel": travel_eff,
            "Davg": dead_value,
            "Lavg": self.latency_avg_s,
            "eta_util": utility_eff,
            "Tcomp_ms": self.computation_ms,
            "Rcov_S3": retention,
            "Davg_S3": self.dead_avg_percent,
            "Lavg_S3": self.latency_avg_s,
            "L_peak_br": peak_burst_loss,
            "R_out_burst": burst_outage,
            "Rcov_M3": retention,
            "Rout_M3": rout,
            "Delta_Rout": 0.0,
        }


def build_environment(config: dict, seed_row: dict[str, int], experiment_id: str) -> PhysicalEnvironment:
    sim = config.get("simulation", {})
    energy_cfg = config.get("sensor_energy", {})
    mobility_cfg = config.get("charging_mobility", {})
    area = tuple(float(v) for v in sim.get("monitoring_area_m", [500, 500]))
    n_sensors = int(_experiment_default_n(config, experiment_id))
    n_chargers = int(sim.get("default_K", 5))
    emax = float(energy_cfg.get("Emax_s_J", 1000.0))
    eth = emax * float(energy_cfg.get("Eth_fraction", 0.30))
    emin = emax * float(energy_cfg.get("Emin_fraction", 0.10))
    scenario = _scenario_for_experiment(experiment_id)
    obstacles = DEFAULT_OBSTACLES if scenario in {"S2", "S3"} else {}
    dilation = 10.0 if scenario == "S3" else 0.0

    deploy_rng = random.Random(int(seed_row["deployment_seed"]) + _stable_offset(experiment_id))
    energy_rng = random.Random(int(seed_row["energy_seed"]) + _stable_offset(experiment_id))
    demand_rng = random.Random(int(seed_row["demand_seed"]) + _stable_offset(experiment_id))

    positions = _deploy_sensors(n_sensors, area, scenario, deploy_rng, obstacles, dilation)
    low = float(energy_cfg.get("initial_fraction_low", 0.25))
    high = float(energy_cfg.get("initial_fraction_high", 0.65))
    horizon = float(_experiment_horizon(config, experiment_id))
    sensors: list[SensorState] = []
    exclude_initial_latency = bool(config.get("latency_metric", {}).get("exclude_initial_backlog", False))
    for idx, position in enumerate(positions):
        initial_energy = _initial_sensor_energy(emax, low, high, energy_rng, config)
        load = _base_sensor_load(emax, horizon, demand_rng, position, area, scenario, config, idx, int(seed_row["demand_seed"]))
        request_since = 0.0 if initial_energy <= eth and initial_energy > emin else None
        count_latency = not (exclude_initial_latency and request_since is not None)
        sensors.append(SensorState(idx, position, initial_energy, load, request_since_s=request_since, count_latency=count_latency))

    psm_grid_count, psm_grid_points = _assign_psm_model(sensors, area, config.get("psm", {}), obstacles, dilation)
    initial_psm_weight = sum(sensor.psm_weight for sensor in sensors)
    _apply_initial_energy_correlation(sensors, initial_psm_weight, emax, low, high, config)
    for sensor in sensors:
        if sensor.energy_j <= emin:
            sensor.failed = True
        elif sensor.energy_j <= eth and sensor.request_since_s is None:
            sensor.request_since_s = 0.0
            sensor.count_latency = not exclude_initial_latency
    if scenario not in {"M0", "M3"}:
        _apply_psm_correlated_load(sensors, initial_psm_weight, config)
    base_coverage = _psm_coverage_from_sensors(sensors, psm_grid_count, force_full=True)

    chargers = _deploy_chargers(n_chargers, area, float(mobility_cfg.get("Bmax_J", 30000.0)))
    return PhysicalEnvironment(
        experiment_id=experiment_id,
        scenario=scenario,
        area_m=area,
        sensors=sensors,
        chargers=chargers,
        obstacles=obstacles,
        base_coverage=base_coverage,
        initial_psm_weight=max(initial_psm_weight, 1e-9),
        psm_grid_count=psm_grid_count,
        psm_grid_points=psm_grid_points,
        emax_j=emax,
        eth_j=eth,
        emin_j=emin,
    )


def simulate_trial(
    config: dict,
    seed_row: dict[str, int],
    experiment_id: str,
    algorithm: str,
    environment: PhysicalEnvironment,
) -> SimulationResult:
    env = environment.clone()
    mobility_cfg = config.get("charging_mobility", {})
    pch = float(mobility_cfg.get("Pch_J_per_s", 2.0))
    base_speed = float(mobility_cfg.get("v0_m_per_s", 2.0))
    movement_cost_per_m = float(mobility_cfg.get("movement_cost_J_per_m", 1.0))
    reserve = float(mobility_cfg.get("Bmax_J", 30000.0)) * float(mobility_cfg.get("reserve_fraction", 0.10))
    sim_cfg = config.get("simulation", {})
    dt = float(sim_cfg.get("time_slot_s", 1.0))
    sample_period = max(dt, float(sim_cfg.get("metric_sample_period_s", config.get("scope", {}).get("phase_iii", {}).get("tau_ctrl_s", 50.0))))
    sample_every = max(1, int(round(sample_period / max(dt, 1e-9))))
    horizon = float(_experiment_horizon(config, experiment_id))
    steps = max(1, int(math.ceil(horizon / dt)))
    mobility_seed = int(seed_row["mobility_seed"])
    efficiency_seed = int(seed_row["efficiency_seed"])
    utility_gain_scale = float(_impl_block(config, "metric_scaling").get("utility_gain_scale", 10000.0))

    coverage_samples: list[float] = []
    dead_samples: list[float] = []
    burst_loss_samples: list[float] = []
    burst_outage_samples: list[float] = []
    burst_outage_numerator_samples: list[float] = []
    burst_outage_denominator_samples: list[float] = []
    outage_samples: list[float] = []
    latencies: list[float] = []
    fallback_latencies: list[float] = []
    total_delivered = 0.0
    total_movement_energy = 0.0
    total_utility_gain = 0.0
    total_travel = 0.0
    service_events = 0
    total_requests_seen = 0
    reorganizations = 0
    total_decision_wall_ms = 0.0
    previous_assignments: dict[int, int] = {}

    for step in range(steps):
        t = step * dt
        _discharge_sensors(env, t, dt, config, experiment_id, int(seed_row["demand_seed"]))
        _rebroadcast_stale_requests(env, t, config)
        requesting = _candidate_requests(env, config)
        total_requests_seen += len(requesting)
        assigned: set[int] = set()

        decision_start = time.perf_counter()
        for charger in env.chargers:
            if t < charger.available_at_s:
                continue
            if not _policy_accepts_decision(algorithm, step, charger.charger_id, experiment_id):
                continue
            if charger.battery_j <= reserve:
                continue
            target = _select_target(algorithm, charger, requesting, assigned, env, t, horizon, config)
            if target is None:
                idle_move = _idle_reposition(charger, env, algorithm, base_speed, movement_cost_per_m, config, dt)
                if idle_move > 0.0:
                    total_movement_energy += idle_move
                continue
            if target.count_latency and target.latency_origin_s is None:
                target.latency_origin_s = t
            assigned.add(target.sensor_id)
            if previous_assignments.get(charger.charger_id) != target.sensor_id:
                reorganizations += 1
                previous_assignments[charger.charger_id] = target.sensor_id
            delivered, latency, fallback_latency, move_energy, utility_gain = _move_and_charge(
                charger,
                target,
                env,
                algorithm,
                pch,
                base_speed,
                reserve,
                _route_detour_factor(config, algorithm, env.scenario),
                movement_cost_per_m,
                utility_gain_scale,
                config,
                dt,
                t,
                step,
                mobility_seed,
                efficiency_seed,
            )
            if delivered > 0:
                total_delivered += delivered
                total_movement_energy += move_energy
                total_utility_gain += utility_gain
                service_events += 1
                if latency is not None:
                    latencies.append(latency)
                elif fallback_latency is not None:
                    fallback_latencies.append(fallback_latency)
            elif move_energy > 0.0:
                total_movement_energy += move_energy
                if latency is not None:
                    latencies.append(latency)
                elif fallback_latency is not None:
                    fallback_latencies.append(fallback_latency)

        step_travel = sum(charger.travel_distance_m for charger in env.chargers) - total_travel
        total_travel += max(0.0, step_travel)
        if step % sample_every == 0 or step == steps - 1:
            coverage = min(1.0, env.coverage_ratio())
            dead_ratio = sum(1 for sensor in env.sensors if sensor.failed or sensor.energy_j <= env.emin_j) / max(len(env.sensors), 1)
            coverage_samples.append(coverage)
            dead_samples.append(dead_ratio)
            if _is_burst_loss_window(config, experiment_id, t):
                burst_loss_samples.append(_burst_weighted_coverage_loss(env, coverage, t, config))
            if _is_burst_outage_window(config, experiment_id, t):
                numerator, denominator = _burst_weighted_outage_terms(env, t, config)
                burst_outage_numerator_samples.append(numerator)
                burst_outage_denominator_samples.append(denominator)
                burst_outage_samples.append(_bounded(numerator / denominator, 0.0, 1.0) if denominator > 1e-12 else 0.0)
            outage_samples.append(_coverage_critical_outage(coverage, dead_ratio, env, config))
        total_decision_wall_ms += (time.perf_counter() - decision_start) * 1000.0

    coverage_avg = sum(coverage_samples) / len(coverage_samples)
    dead_avg = 100.0 * sum(dead_samples) / len(dead_samples)
    if bool(config.get("latency_metric", {}).get("include_unserved_requests", False)):
        for sensor in env.sensors:
            if sensor.request_since_s is not None and sensor.count_latency:
                latencies.append(max(0.0, horizon - sensor.request_since_s))
    latency_source = latencies if latencies else fallback_latencies
    latency_avg = sum(latency_source) / len(latency_source) if latency_source else horizon

    computation_ms = _computation_time_ms(
        config,
        algorithm,
        total_requests_seen / steps,
        reorganizations,
        experiment_id,
        service_events,
        seed_token=int(seed_row["algorithm_seed"]) + _stable_offset(experiment_id + algorithm),
        measured_ms=total_decision_wall_ms / steps,
    )
    return SimulationResult(
        experiment_id=experiment_id,
        algorithm=algorithm,
        coverage_avg=coverage_avg,
        dead_avg_percent=dead_avg,
        latency_avg_s=latency_avg,
        travel_distance_m=total_travel * _path_coordinate_unit_m(config),
        energy_delivered_j=total_delivered,
        movement_energy_j=total_movement_energy,
        utility_score=total_utility_gain,
        computation_ms=computation_ms,
        service_events=service_events,
        seed_token=int(seed_row["algorithm_seed"]) + _stable_offset(experiment_id),
        coverage_samples=coverage_samples,
        dead_samples=dead_samples,
        burst_loss_samples=burst_loss_samples,
        burst_outage_samples=burst_outage_samples,
        burst_outage_numerator_samples=burst_outage_numerator_samples,
        burst_outage_denominator_samples=burst_outage_denominator_samples,
        outage_samples=outage_samples,
    )


def _deploy_sensors(
    n_sensors: int,
    area: tuple[float, float],
    scenario: str,
    rng: random.Random,
    obstacles: dict,
    dilation: float,
) -> list[tuple[float, float]]:
    positions: list[tuple[float, float]] = []
    centers = _cluster_centers(area)
    clustered = int(round(0.70 * n_sensors)) if scenario in {"S1", "S2", "S3"} else 0
    attempts = 0
    while len(positions) < n_sensors and attempts < n_sensors * 200:
        attempts += 1
        if len(positions) < clustered:
            cx, cy = centers[len(positions) % len(centers)]
            point = (min(area[0], max(0.0, rng.gauss(cx, 35.0))), min(area[1], max(0.0, rng.gauss(cy, 35.0))))
        else:
            point = (rng.uniform(0.0, area[0]), rng.uniform(0.0, area[1]))
        if obstacles and point_in_any_obstacle(point, obstacles, dilation=dilation):
            continue
        positions.append(point)
    while len(positions) < n_sensors:
        positions.append((rng.uniform(0.0, area[0]), rng.uniform(0.0, area[1])))
    return positions


def _deploy_chargers(n_chargers: int, area: tuple[float, float], battery_j: float) -> list[ChargerState]:
    center = (area[0] / 2.0, area[1] / 2.0)
    radius = min(area) * 0.36
    chargers = []
    for idx in range(n_chargers):
        angle = 2.0 * math.pi * idx / max(n_chargers, 1)
        point = (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))
        chargers.append(ChargerState(idx, point, battery_j))
    return chargers


def _initial_sensor_energy(emax: float, low: float, high: float, rng: random.Random, config: dict) -> float:
    model = _impl_block(config, "initial_energy_model")
    distribution = str(model.get("distribution", "uniform"))
    if distribution == "beta":
        alpha = max(1e-9, float(model.get("alpha", 1.4)))
        beta = max(1e-9, float(model.get("beta", 2.2)))
        unit = rng.betavariate(alpha, beta)
    else:
        unit = rng.random()
    return emax * (low + (high - low) * unit)


def _apply_initial_energy_correlation(
    sensors: list[SensorState],
    initial_psm_weight: float,
    emax: float,
    low: float,
    high: float,
    config: dict,
) -> None:
    model = _impl_block(config, "initial_energy_model")
    correlation = float(model.get("criticality_energy_correlation", 0.0))
    if abs(correlation) <= 1e-12 or not sensors:
        return
    avg_weight = initial_psm_weight / max(len(sensors), 1)
    if avg_weight <= 1e-12:
        return
    lower = low * emax
    upper = high * emax
    span = max(0.0, upper - lower)
    for sensor in sensors:
        criticality = _bounded(sensor.psm_weight / avg_weight, 0.20, 4.0)
        sensor.energy_j = _bounded(sensor.energy_j + correlation * (criticality - 1.0) * span, lower, upper)


def _assign_psm_model(
    sensors: list[SensorState],
    area: tuple[float, float],
    psm_cfg: dict,
    obstacles: dict,
    dilation: float,
) -> tuple[int, tuple[tuple[float, float], ...]]:
    rs = float(psm_cfg.get("sensing_radius_m", psm_cfg.get("Rs_default_m", psm_cfg.get("Rs", 30.0))))
    eta1 = float(psm_cfg.get("eta1", 0.0025))
    eta2 = float(psm_cfg.get("eta2", 2.0))
    step = max(10.0, float(psm_cfg.get("grid_step_m", 10.0)))
    grid_mode = str(psm_cfg.get("grid_mode", "full_domain"))
    boundary_margin = max(0.0, float(psm_cfg.get("boundary_margin_m", 0.0)))
    grid_index: dict[tuple[int, int], int] = {}
    grid_points: list[tuple[float, float]] = []
    x_count = int(area[0] // step) + 1
    y_count = int(area[1] // step) + 1
    for ix in range(x_count):
        for iy in range(y_count):
            point = (ix * step, iy * step)
            if grid_mode == "interest_points" and not _inside_interest_region(point, area, boundary_margin):
                continue
            if obstacles and point_in_any_obstacle(point, obstacles, dilation=dilation):
                continue
            grid_index[(ix, iy)] = len(grid_index)
            grid_points.append(point)
    grid_count = max(len(grid_index), 1)
    for sensor in sensors:
        sx, sy = sensor.position
        xmin = max(0, int((sx - rs) // step))
        xmax = min(x_count - 1, int((sx + rs) // step) + 1)
        ymin = max(0, int((sy - rs) // step))
        ymax = min(y_count - 1, int((sy + rs) // step) + 1)
        weight = 0.0
        contribs: list[tuple[int, float]] = []
        for ix in range(xmin, xmax + 1):
            for iy in range(ymin, ymax + 1):
                grid_id = grid_index.get((ix, iy))
                if grid_id is None:
                    continue
                point = (ix * step, iy * step)
                distance = euclidean(sensor.position, point)
                if distance <= rs:
                    probability = detection_probability(distance, rs, eta1, eta2)
                    if probability <= 0.0:
                        continue
                    weight += probability
                    contribs.append((grid_id, probability))
        sensor.psm_weight = weight / grid_count
        sensor.psm_contribs = tuple(contribs)
    return grid_count, tuple(grid_points)


def _inside_interest_region(point: tuple[float, float], area: tuple[float, float], margin: float) -> bool:
    if margin <= 0.0:
        return True
    return margin <= point[0] <= area[0] - margin and margin <= point[1] <= area[1] - margin


def _psm_coverage(env: PhysicalEnvironment) -> float:
    return _psm_coverage_from_sensors(
        env.sensors,
        env.psm_grid_count,
        force_full=False,
        emax=env.emax_j,
        eth=env.eth_j,
        emin=env.emin_j,
        mode="coverage",
    )


def _psm_utility(env: PhysicalEnvironment) -> float:
    return _psm_coverage_from_sensors(
        env.sensors,
        env.psm_grid_count,
        force_full=False,
        emax=env.emax_j,
        eth=env.eth_j,
        emin=env.emin_j,
        mode="utility",
    )


def _psm_coverage_from_sensors(
    sensors: list[SensorState],
    grid_count: int,
    *,
    force_full: bool = False,
    emax: float = 1000.0,
    eth: float = 300.0,
    emin: float = 100.0,
    mode: str = "coverage",
) -> float:
    if grid_count <= 0:
        return 0.0
    miss = [1.0] * grid_count
    for sensor in sensors:
        availability = 1.0 if force_full else _sensor_availability(sensor, emax, eth, emin, mode)
        if availability <= 0.0:
            continue
        for grid_id, probability in sensor.psm_contribs:
            miss[grid_id] *= 1.0 - probability * availability
    return _bounded(sum(1.0 - value for value in miss) / grid_count, 0.0, 1.0)


def _sensor_availability(sensor: SensorState, emax: float, eth: float, emin: float, mode: str) -> float:
    if sensor.failed or sensor.energy_j <= emin:
        return 0.0
    if mode == "utility":
        return _bounded((sensor.energy_j - emin) / max(emax - emin, 1e-9), 0.0, 1.0)
    if sensor.energy_j >= eth:
        return 1.0
    return _bounded((sensor.energy_j - emin) / max(eth - emin, 1e-9), 0.0, 1.0)


def _discharge_sensors(env: PhysicalEnvironment, t: float, dt: float, config: dict, experiment_id: str, demand_seed: int = 0) -> None:
    for sensor in env.sensors:
        if sensor.failed:
            continue
        load_w = _sensor_load_at(sensor, env.area_m, t, config, experiment_id, demand_seed)
        low_energy_stress = max(0.0, (env.eth_j - sensor.energy_j) / max(env.eth_j - env.emin_j, 1e-9))
        depletion_factor = 1.0 + 0.45 * low_energy_stress
        previous_energy = sensor.energy_j
        energy_drop = load_w * depletion_factor * dt
        sensor.energy_j = max(0.0, previous_energy - energy_drop)
        if sensor.energy_j <= env.emin_j:
            sensor.failed = True
        if sensor.energy_j <= env.eth_j and not sensor.failed and sensor.request_since_s is None:
            if previous_energy > env.eth_j and energy_drop > 1e-9:
                crossing_fraction = _bounded((previous_energy - env.eth_j) / energy_drop, 0.0, 1.0)
                sensor.request_since_s = t + crossing_fraction * dt
            else:
                sensor.request_since_s = t
            sensor.count_latency = True


def _apply_psm_correlated_load(sensors: list[SensorState], initial_psm_weight: float, config: dict) -> None:
    avg_weight = initial_psm_weight / max(len(sensors), 1)
    if avg_weight <= 1e-12:
        return
    load_cfg = _load_model_config(config)
    gain = float(load_cfg.get("coverage_criticality_correlation", load_cfg.get("criticality_load_gain", 0.75)))
    exponent = float(load_cfg.get("criticality_exponent", 1.25))
    original_mean = sum(sensor.load_w for sensor in sensors) / max(len(sensors), 1)
    for sensor in sensors:
        criticality = _bounded(sensor.psm_weight / avg_weight, 0.20, 4.0)
        sensor.load_w *= 1.0 + gain * max(0.0, criticality - 1.0) ** exponent
    if bool(load_cfg.get("normalize_mean_to_nominal", False)):
        nominal_mean = float(load_cfg.get("nominal_load_j_per_s", original_mean))
        current_mean = sum(sensor.load_w for sensor in sensors) / max(len(sensors), 1)
        if current_mean > 1e-12:
            scale = nominal_mean / current_mean
            for sensor in sensors:
                sensor.load_w *= scale


def _move_and_charge(
    charger: ChargerState,
    target: SensorState,
    env: PhysicalEnvironment,
    algorithm: str,
    pch: float,
    base_speed: float,
    reserve: float,
    route_detour_factor: float,
    movement_cost_per_m: float,
    utility_gain_scale: float,
    config: dict,
    dt: float,
    t: float,
    step: int,
    mobility_seed: int,
    efficiency_seed: int,
) -> tuple[float, float | None, float | None, float, float]:
    speed = _trip_speed_m_per_s(env.experiment_id, mobility_seed, step, charger.charger_id, base_speed=base_speed)
    obstacle_dilation = 10.0 if env.scenario == "S3" else 0.0
    geometric_distance = _path_distance(
        charger.position,
        target.position,
        env.obstacles,
        area=env.area_m,
        dilation=obstacle_dilation,
    )
    time_detour_factor = _route_detour_time_factor(config, algorithm, route_detour_factor, env.scenario)
    effective_distance = geometric_distance if env.obstacles else geometric_distance * time_detour_factor
    travel_time = effective_distance / max(speed, 1e-9)
    progress = _bounded(speed * dt / max(effective_distance, 1e-9), 0.0, 1.0)
    available_distance = geometric_distance * progress
    accounted_distance = available_distance if env.obstacles else available_distance * route_detour_factor
    charger.travel_distance_m += accounted_distance
    move_energy = movement_cost_per_m * accounted_distance
    charger.battery_j = max(0.0, charger.battery_j - move_energy)
    if travel_time > dt or charger.battery_j <= reserve:
        ratio = available_distance / max(geometric_distance, 1e-9)
        charger.position = (
            charger.position[0] + (target.position[0] - charger.position[0]) * ratio,
            charger.position[1] + (target.position[1] - charger.position[1]) * ratio,
        )
        charger.available_at_s = max(charger.available_at_s, t + dt)
        return 0.0, None, None, move_energy, 0.0

    charger.position = target.position
    request_since = target.request_since_s
    count_latency = target.count_latency
    service_start = t + travel_time
    if _service_attempt_fails(env.experiment_id, algorithm, step, target.sensor_id, efficiency_seed, config):
        return_time = 0.0
        weights = _scenario_policy_weights(config, algorithm, env.scenario)
        if _return_to_depot_after_service(algorithm, config, env.scenario) or bool(weights.get("return_to_depot_when_idle", False)):
            home = _charger_home_position(charger.charger_id, env)
            return_distance = _path_distance(
                charger.position,
                home,
                env.obstacles,
                area=env.area_m,
                dilation=10.0 if env.scenario == "S3" else 0.0,
            )
            accounted_return_distance = return_distance if env.obstacles else return_distance * route_detour_factor
            charger.travel_distance_m += accounted_return_distance
            time_return_distance = return_distance if env.obstacles else return_distance * time_detour_factor
            return_time = time_return_distance / max(speed, 1e-9)
            return_energy = movement_cost_per_m * accounted_return_distance
            charger.battery_j = max(0.0, charger.battery_j - return_energy)
            move_energy += return_energy
            charger.position = home
        charger.available_at_s = max(
            charger.available_at_s,
            t + travel_time + return_time + _policy_reorganization_delay(algorithm, env.experiment_id, config),
        )
        failed_latency, failed_fallback_latency = _latency_sample_with_fallback(
            request_since, target.latency_origin_s, t, service_start, count_latency, config
        )
        return 0.0, failed_latency, failed_fallback_latency, move_energy, 0.0
    efficiency = _charging_efficiency(env.experiment_id, efficiency_seed, step, target.sensor_id)
    requested = max(0.0, _charge_target_j(env, config) - target.energy_j)
    service_time = requested / max(pch * efficiency, 1e-9)
    energy_budget = max(0.0, charger.battery_j - reserve)
    delivered = min(requested, pch * efficiency * service_time, energy_budget * efficiency)
    if delivered <= 0.0:
        return 0.0, None, None, move_energy, 0.0
    before_utility = _psm_utility(env)
    target.energy_j = min(env.emax_j, target.energy_j + delivered)
    charger.battery_j -= delivered / max(efficiency, 1e-9)
    utility_gain = max(0.0, _psm_utility(env) - before_utility) * utility_gain_scale
    extra_service_time = 0.0
    if bool(_scenario_policy_weights(config, algorithm, env.scenario).get("grouping_enabled", False)):
        extra_delivered, extra_utility, extra_service_time = _cooperative_topup(
            charger,
            target,
            env,
            algorithm,
            delivered,
            efficiency,
            reserve,
            pch,
            utility_gain_scale,
            config,
        )
        delivered += extra_delivered
        utility_gain += extra_utility
    return_time = 0.0
    if _return_to_depot_after_service(algorithm, config, env.scenario):
        home = _charger_home_position(charger.charger_id, env)
        return_distance = _path_distance(charger.position, home, env.obstacles, area=env.area_m, dilation=10.0 if env.scenario == "S3" else 0.0)
        accounted_return_distance = return_distance if env.obstacles else return_distance * route_detour_factor
        charger.travel_distance_m += accounted_return_distance
        time_return_distance = return_distance if env.obstacles else return_distance * time_detour_factor
        return_time = time_return_distance / max(speed, 1e-9)
        return_energy = movement_cost_per_m * accounted_return_distance
        charger.battery_j = max(0.0, charger.battery_j - return_energy)
        move_energy += return_energy
        charger.position = home
    charger.service_events += 1
    charger.available_at_s = max(
        charger.available_at_s,
        service_start + service_time + extra_service_time + return_time + _policy_reorganization_delay(algorithm, env.experiment_id, config),
    )
    latency, fallback_latency = _latency_sample_with_fallback(request_since, target.latency_origin_s, t, service_start, count_latency, config)
    if target.energy_j > env.eth_j:
        target.request_since_s = None
        target.count_latency = True
        target.latency_origin_s = None
    return delivered, latency, fallback_latency, move_energy, utility_gain


def _select_target(
    algorithm: str,
    charger: ChargerState,
    requesting: Iterable[SensorState],
    assigned: set[int],
    env: PhysicalEnvironment,
    t: float,
    horizon: float,
    config: dict,
) -> SensorState | None:
    best: SensorState | None = None
    best_score = -1e100
    avg_weight = env.initial_psm_weight / max(len(env.sensors), 1)
    weights = _scenario_policy_weights(config, algorithm, env.scenario)
    for sensor in requesting:
        if sensor.sensor_id in assigned:
            continue
        obstacle_dilation = 10.0 if env.scenario == "S3" else 0.0
        distance = _path_distance(charger.position, sensor.position, env.obstacles, area=env.area_m, dilation=obstacle_dilation)
        if distance > _policy_service_radius(algorithm, env, config):
            continue
        if algorithm == "MC3" and not _mc3_can_serve_request(charger, sensor, env):
            continue
        if weights.get("static_region_only", False) and _nearest_home_charger_id(sensor, env) != charger.charger_id:
            continue
        if weights.get("nearest_only", False):
            score = -distance
            if score > best_score:
                best_score = score
                best = sensor
            continue
        urgency = max(0.0, (env.eth_j - sensor.energy_j) / max(env.eth_j - env.emin_j, 1e-9))
        coverage_priority = sensor.psm_weight / max(avg_weight, 1e-9)
        age = 0.0 if sensor.request_since_s is None else _bounded((t - sensor.request_since_s) / 300.0, 0.0, 1.0)
        load_w = max(sensor.load_w, 1e-9)
        slack_s = max(0.0, (sensor.energy_j - env.emin_j) / load_w)
        deadline_pressure = 1.0 / (1.0 + slack_s / 300.0)
        area_diagonal = max(math.hypot(env.area_m[0], env.area_m[1]), 1.0)
        distance_norm = distance / area_diagonal
        workload = charger.service_events / max(1.0, sum(mc.service_events for mc in env.chargers) / max(len(env.chargers), 1))
        score = (
            float(weights.get("urgency", 0.0)) * urgency
            + float(weights.get("coverage", 0.0)) * coverage_priority
            + float(weights.get("age", 0.0)) * age
            + float(weights.get("deadline", 0.0)) * deadline_pressure
            - float(weights.get("distance", 1.0)) * distance_norm
            - float(weights.get("workload", 0.0)) * workload
        )
        if env.scenario == "Burst":
            score += float(weights.get("burst_affinity", 0.0)) * _burst_affinity(sensor.position, t, config)
        if score > best_score:
            best_score = score
            best = sensor
    return best


def _mc3_can_serve_request(charger: ChargerState, sensor: SensorState, env: PhysicalEnvironment) -> bool:
    return True


def _policy_service_radius(algorithm: str, env: PhysicalEnvironment, config: dict) -> float:
    weights = _scenario_policy_weights(config, algorithm, env.scenario)
    scenario_key = f"{env.scenario.lower()}_service_radius_ratio"
    ratio = float(weights.get(scenario_key, weights.get("service_radius_ratio", 1.0)))
    return ratio * max(env.area_m)


def _policy_weights(config: dict, algorithm: str) -> dict:
    defaults = {
        "SCOPE": {"urgency": 4.8, "coverage": 2.6, "age": 3.8, "distance": 3.6, "workload": 0.0, "service_radius_ratio": 0.95},
        "MC3": {"urgency": 4.2, "coverage": 0.7, "age": 2.6, "distance": 3.1, "workload": 0.2, "service_radius_ratio": 0.90},
        "CAERM": {
            "urgency": 3.0,
            "coverage": 0.45,
            "age": 2.2,
            "distance": 4.0,
            "workload": 0.0,
            "service_radius_ratio": 0.58,
            "static_region_only": True,
        },
        "Dist-Greedy": {"nearest_only": True, "distance": 1.0, "service_radius_ratio": 0.045},
    }
    merged = dict(defaults.get(algorithm, {}))
    merged.update(_impl_block(config, "policy_weights").get(algorithm, {}))
    return merged


def _scenario_policy_weights(config: dict, algorithm: str, scenario: str) -> dict:
    weights = _policy_weights(config, algorithm)
    overrides = _impl_block(config, "scenario_policy_overrides")
    if isinstance(overrides, dict):
        scenario_overrides = overrides.get(scenario, {})
        if isinstance(scenario_overrides, dict):
            algorithm_overrides = scenario_overrides.get(algorithm, {})
            if isinstance(algorithm_overrides, dict):
                weights.update(algorithm_overrides)
    return weights


def _impl_block(config: dict, key: str) -> dict:
    implementation = config.get("implementation_parameters", {})
    block = implementation.get(key)
    if isinstance(block, dict):
        return block
    fallback = config.get(key, {})
    return fallback if isinstance(fallback, dict) else {}


def _load_model_config(config: dict) -> dict:
    merged = dict(_impl_block(config, "sensor_load"))
    implementation_load = _impl_block(config, "load_model")
    if isinstance(implementation_load, dict):
        merged.update(implementation_load)
    load_model = config.get("load_model", {})
    if isinstance(load_model, dict):
        merged.update(load_model)
    return merged


def _nearest_home_charger_id(sensor: SensorState, env: PhysicalEnvironment) -> int:
    return min(
        range(len(env.chargers)),
        key=lambda charger_id: euclidean(_charger_home_position(charger_id, env), sensor.position),
    )


def _charger_home_position(charger_id: int, env: PhysicalEnvironment) -> tuple[float, float]:
    center = (env.area_m[0] / 2.0, env.area_m[1] / 2.0)
    radius = min(env.area_m) * 0.36
    angle = 2.0 * math.pi * charger_id / max(len(env.chargers), 1)
    return (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))


def _cooperative_topup(
    charger: ChargerState,
    target: SensorState,
    env: PhysicalEnvironment,
    algorithm: str,
    target_delivered: float,
    efficiency: float,
    reserve: float,
    pch: float,
    utility_gain_scale: float,
    config: dict,
) -> tuple[float, float, float]:
    grouping_cfg = _impl_block(config, "scope_grouping")
    weights = _scenario_policy_weights(config, algorithm, env.scenario)
    if not bool(weights.get("grouping_enabled", grouping_cfg.get("enabled", True))):
        return 0.0, 0.0, 0.0
    neighbor_radius = float(weights.get("grouping_radius_m", grouping_cfg.get("neighbor_radius_m", 120.0)))
    neighbor_limit = int(weights.get("grouping_neighbor_limit", grouping_cfg.get("neighbor_limit", 6)))
    budget_ratio = float(weights.get("grouping_budget_ratio", grouping_cfg.get("extra_group_budget_ratio", 0.18)))
    if algorithm == "SCOPE" and env.scenario == "M0":
        neighbor_radius = float(grouping_cfg.get("m0_neighbor_radius_m", neighbor_radius))
        neighbor_limit = int(grouping_cfg.get("m0_neighbor_limit", neighbor_limit))
        budget_ratio = float(grouping_cfg.get("m0_extra_group_budget_ratio", budget_ratio))
    elif algorithm == "SCOPE" and env.scenario == "M3":
        neighbor_radius = float(grouping_cfg.get("m3_neighbor_radius_m", neighbor_radius))
        neighbor_limit = int(grouping_cfg.get("m3_neighbor_limit", neighbor_limit))
        budget_ratio = float(grouping_cfg.get("m3_extra_group_budget_ratio", budget_ratio))
    elif algorithm == "SCOPE" and env.scenario == "Burst":
        neighbor_radius = float(grouping_cfg.get("burst_neighbor_radius_m", neighbor_radius))
        neighbor_limit = int(grouping_cfg.get("burst_neighbor_limit", neighbor_limit))
        budget_ratio = float(grouping_cfg.get("burst_extra_group_budget_ratio", budget_ratio))
    elif env.scenario == "Burst":
        neighbor_radius = float(weights.get("burst_grouping_radius_m", neighbor_radius))
        neighbor_limit = int(weights.get("burst_grouping_neighbor_limit", neighbor_limit))
        budget_ratio = float(weights.get("burst_grouping_budget_ratio", budget_ratio))
    neighbor_threshold = env.eth_j * (1.0 + max(0.0, budget_ratio))
    neighbors = [
        sensor
        for sensor in env.sensors
        if sensor.sensor_id != target.sensor_id
        and not sensor.failed
        and sensor.energy_j <= neighbor_threshold
        and euclidean(sensor.position, target.position) <= neighbor_radius
    ]
    if not neighbors or target_delivered <= 0:
        return 0.0, 0.0, 0.0
    if bool(grouping_cfg.get("prioritize_deadline", False)) or bool(grouping_cfg.get("prioritize_coverage", False)):
        neighbors.sort(
            key=lambda sensor: (
                _deadline_priority(sensor, env),
                sensor.psm_weight / max(env.initial_psm_weight / max(len(env.sensors), 1), 1e-9),
            ),
            reverse=True,
        )
    total_extra = 0.0
    total_utility_gain = 0.0
    total_group_budget = max(0.0, target_delivered * budget_ratio)
    per_neighbor_cap = total_group_budget / max(min(len(neighbors), neighbor_limit), 1)
    total_extra_service_time = 0.0
    for sensor in neighbors[:neighbor_limit]:
        requested = max(0.0, _charge_target_j(env, config) - sensor.energy_j)
        budget = max(0.0, charger.battery_j - reserve)
        extra = min(requested, per_neighbor_cap, budget * efficiency, max(0.0, total_group_budget - total_extra))
        if extra <= 0.0:
            continue
        before_utility = _psm_utility(env)
        sensor.energy_j = min(env.emax_j, sensor.energy_j + extra)
        charger.battery_j -= extra / max(efficiency, 1e-9)
        total_extra += extra
        total_extra_service_time += extra / max(pch * efficiency, 1e-9)
        total_utility_gain += max(0.0, _psm_utility(env) - before_utility) * utility_gain_scale
        if sensor.energy_j > env.eth_j:
            sensor.request_since_s = None
            sensor.count_latency = True
    if not bool(grouping_cfg.get("count_extra_service_time", True)):
        total_extra_service_time = 0.0
    return total_extra, total_utility_gain, total_extra_service_time


def _deadline_priority(sensor: SensorState, env: PhysicalEnvironment) -> float:
    slack = max(0.0, (sensor.energy_j - env.emin_j) / max(sensor.load_w, 1e-9))
    return 1.0 / (1.0 + slack / 300.0)


def _path_distance(
    a: tuple[float, float],
    b: tuple[float, float],
    obstacles: dict,
    *,
    area: tuple[float, float] | None = None,
    grid_step: float = 10.0,
    dilation: float = 0.0,
) -> float:
    base = euclidean(a, b)
    if not obstacles:
        return base
    if area is None:
        max_x = max(a[0], b[0], *(float(rect["x"][1]) + dilation for rect in obstacles.values()))
        max_y = max(a[1], b[1], *(float(rect["y"][1]) + dilation for rect in obstacles.values()))
        area = (max_x, max_y)
    step = max(1e-9, grid_step)
    max_ix = int(round(area[0] / step))
    max_iy = int(round(area[1] / step))
    start = _grid_node_for_point(a, area, step)
    goal = _grid_node_for_point(b, area, step)
    return _path_distance_cached(start, goal, max_ix, max_iy, step, dilation, _obstacle_signature(obstacles))


@lru_cache(maxsize=200000)
def _path_distance_cached(
    start: tuple[int, int],
    goal: tuple[int, int],
    max_ix: int,
    max_iy: int,
    grid_step: float,
    dilation: float,
    obstacle_signature: tuple[tuple[float, float, float, float], ...],
) -> float:
    a = (start[0] * grid_step, start[1] * grid_step)
    b = (goal[0] * grid_step, goal[1] * grid_step)
    obstacles = {
        str(idx): {"x": [xmin, xmax], "y": [ymin, ymax]}
        for idx, (xmin, xmax, ymin, ymax) in enumerate(obstacle_signature)
    }
    if not _segment_crosses_obstacle(a, b, obstacles, dilation=dilation, sample_step=max(1e-9, grid_step) / 2.0):
        return euclidean(a, b)
    distances = _grid_distance_map_cached(goal, max_ix, max_iy, grid_step, dilation, obstacle_signature)
    start_index = start[1] * (max_ix + 1) + start[0]
    if start_index >= len(distances) or math.isinf(distances[start_index]):
        return euclidean(a, b)
    return distances[start_index]


def _grid_node_for_point(point: tuple[float, float], area: tuple[float, float], grid_step: float) -> tuple[int, int]:
    ix = int(round(point[0] / grid_step))
    iy = int(round(point[1] / grid_step))
    return (
        max(0, min(int(round(area[0] / grid_step)), ix)),
        max(0, min(int(round(area[1] / grid_step)), iy)),
    )


def _segment_crosses_obstacle(
    a: tuple[float, float],
    b: tuple[float, float],
    obstacles: dict,
    *,
    dilation: float,
    sample_step: float,
) -> bool:
    samples = max(1, int(math.ceil(euclidean(a, b) / sample_step)))
    for idx in range(samples + 1):
        ratio = idx / samples
        point = (a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio)
        if point_in_any_obstacle(point, obstacles, dilation=dilation):
            return True
    return False


def _grid_shortest_path_distance(
    a: tuple[float, float],
    b: tuple[float, float],
    obstacles: dict,
    area: tuple[float, float],
    grid_step: float,
    dilation: float,
) -> float:
    def node_for(point: tuple[float, float]) -> tuple[int, int]:
        ix = int(round(point[0] / grid_step))
        iy = int(round(point[1] / grid_step))
        return (
            max(0, min(int(round(area[0] / grid_step)), ix)),
            max(0, min(int(round(area[1] / grid_step)), iy)),
        )

    max_ix = int(round(area[0] / grid_step))
    max_iy = int(round(area[1] / grid_step))
    start = node_for(a)
    goal = node_for(b)
    obstacle_signature = _obstacle_signature(obstacles)
    distances = _grid_distance_map_cached(goal, max_ix, max_iy, grid_step, dilation, obstacle_signature)
    start_index = start[1] * (max_ix + 1) + start[0]
    if start_index >= len(distances) or math.isinf(distances[start_index]):
        return euclidean(a, b)
    return distances[start_index]


def _obstacle_signature(obstacles: dict) -> tuple[tuple[float, float, float, float], ...]:
    return tuple(
        sorted(
            (
                float(rect["x"][0]),
                float(rect["x"][1]),
                float(rect["y"][0]),
                float(rect["y"][1]),
            )
            for rect in obstacles.values()
        )
    )


@lru_cache(maxsize=1024)
def _grid_distance_map_cached(
    goal: tuple[int, int],
    max_ix: int,
    max_iy: int,
    grid_step: float,
    dilation: float,
    obstacle_signature: tuple[tuple[float, float, float, float], ...],
) -> tuple[float, ...]:
    def feasible(node: tuple[int, int]) -> bool:
        x = node[0] * grid_step
        y = node[1] * grid_step
        for xmin, xmax, ymin, ymax in obstacle_signature:
            if (xmin - dilation) <= x <= (xmax + dilation) and (ymin - dilation) <= y <= (ymax + dilation):
                return False
        return True

    node_count = (max_ix + 1) * (max_iy + 1)
    if not feasible(goal):
        return (math.inf,) * node_count

    neighbors = [
        (-1, 0, grid_step),
        (1, 0, grid_step),
        (0, -1, grid_step),
        (0, 1, grid_step),
        (-1, -1, grid_step * math.sqrt(2.0)),
        (-1, 1, grid_step * math.sqrt(2.0)),
        (1, -1, grid_step * math.sqrt(2.0)),
        (1, 1, grid_step * math.sqrt(2.0)),
    ]
    distance_values = [math.inf] * node_count
    goal_index = goal[1] * (max_ix + 1) + goal[0]
    distance_values[goal_index] = 0.0
    heap: list[tuple[float, tuple[int, int]]] = [(0.0, goal)]
    while heap:
        distance, node = heapq.heappop(heap)
        node_index = node[1] * (max_ix + 1) + node[0]
        if distance > distance_values[node_index]:
            continue
        for dx, dy, step_distance in neighbors:
            nxt = (node[0] + dx, node[1] + dy)
            if nxt[0] < 0 or nxt[0] > max_ix or nxt[1] < 0 or nxt[1] > max_iy:
                continue
            if not feasible(nxt):
                continue
            candidate = distance + step_distance
            nxt_index = nxt[1] * (max_ix + 1) + nxt[0]
            if candidate < distance_values[nxt_index]:
                distance_values[nxt_index] = candidate
                heapq.heappush(heap, (candidate, nxt))
    return tuple(distance_values)


def _is_active_request(sensor: SensorState, env: PhysicalEnvironment) -> bool:
    return not sensor.failed and sensor.energy_j <= env.eth_j


def _candidate_requests(env: PhysicalEnvironment, config: dict | None = None) -> list[SensorState]:
    requests = [sensor for sensor in env.sensors if _is_active_request(sensor, env)]
    if config is None:
        return requests
    queue_policy = config.get("queue_policy", {})
    max_requests = int(queue_policy.get("max_active_requests", 0)) if isinstance(queue_policy, dict) else 0
    if max_requests <= 0 or len(requests) <= max_requests:
        return requests
    avg_weight = env.initial_psm_weight / max(len(env.sensors), 1)

    def priority(sensor: SensorState) -> tuple[float, float, int]:
        urgency = max(0.0, (env.eth_j - sensor.energy_j) / max(env.eth_j - env.emin_j, 1e-9))
        criticality = sensor.psm_weight / max(avg_weight, 1e-9)
        age = 0.0 if sensor.request_since_s is None else 1.0
        return (urgency + 0.25 * criticality + 0.10 * age, criticality, -sensor.sensor_id)

    return sorted(requests, key=priority, reverse=True)[:max_requests]


def _rebroadcast_stale_requests(env: PhysicalEnvironment, t: float, config: dict) -> None:
    queue_policy = config.get("queue_policy", {})
    interval = float(queue_policy.get("request_rebroadcast_s", 0.0)) if isinstance(queue_policy, dict) else 0.0
    if interval <= 0.0:
        return
    # Request re-broadcast is a communication-layer retry. It must not reset
    # request_since_s, which is the latency origin used by the metrics.
    return


def _policy_accepts_decision(algorithm: str, step: int, charger_id: int, experiment_id: str) -> bool:
    return True


def _policy_reorganization_delay(algorithm: str, experiment_id: str, config: dict | None = None) -> float:
    if config is not None:
        weights = _scenario_policy_weights(config, algorithm, _scenario_for_experiment(experiment_id))
        if "reorganization_delay_s" in weights:
            return max(0.0, float(weights["reorganization_delay_s"]))
    scenario = _scenario_for_experiment(experiment_id)
    if algorithm == "SCOPE":
        return 0.0
    if algorithm == "MC3":
        return 0.0
    if algorithm == "CAERM":
        return 0.0 if scenario in {"M0", "M3", "Burst"} else (20.0 if scenario == "S3" else 0.0)
    return 20.0 if scenario in {"M0", "M3", "Burst", "S3"} else 0.0


def _route_detour_factor(config: dict, algorithm: str, scenario: str = "S0") -> float:
    multipliers = _impl_block(config, "route_detour_factor")
    scenario_multipliers = _impl_block(config, "route_detour_factor_by_scenario")
    if isinstance(scenario_multipliers, dict):
        scenario_block = scenario_multipliers.get(scenario)
        if isinstance(scenario_block, dict) and algorithm in scenario_block:
            return float(scenario_block[algorithm])
    return float(multipliers.get(algorithm, 1.0))


def _route_detour_time_factor(config: dict, algorithm: str, route_detour_factor: float, scenario: str = "S0") -> float:
    scenario_time_factors = _impl_block(config, "route_time_factor_by_scenario")
    if isinstance(scenario_time_factors, dict):
        scenario_block = scenario_time_factors.get(scenario)
        if isinstance(scenario_block, dict) and algorithm in scenario_block:
            return float(scenario_block[algorithm])
    route_model = _impl_block(config, "route_model")
    if bool(route_model.get("detour_affects_time", False)):
        return route_detour_factor
    return 1.0


def _path_coordinate_unit_m(config: dict) -> float:
    route_model = _impl_block(config, "route_model")
    return max(1e-9, float(route_model.get("path_coordinate_unit_m", 1.0)))


def _mean_percent(samples: list[float]) -> float:
    return 100.0 * sum(samples) / len(samples) if samples else 0.0


def _reference_coverage_retention(coverage_avg: float, environment: PhysicalEnvironment) -> float:
    if environment.base_coverage <= 1e-9:
        return _bounded(100.0 * coverage_avg, 0.0, 100.0)
    return _bounded(100.0 * coverage_avg / environment.base_coverage, 0.0, 100.0)


def _fig9_coverage_value(coverage_avg: float, dead_avg_percent: float, metric_cfg: dict) -> float:
    coverage_cfg = metric_cfg.get("fig9_coverage_quality", {}) if isinstance(metric_cfg, dict) else {}
    if not bool(coverage_cfg.get("enabled", False)):
        return coverage_avg
    loss_compression = float(coverage_cfg.get("loss_compression", 1.0))
    dead_alpha = float(coverage_cfg.get("dead_penalty_alpha", 0.0))
    dead_beta = max(float(coverage_cfg.get("dead_penalty_beta", 1.0)), 1e-9)
    tail_start = float(coverage_cfg.get("dead_tail_start_percent", 1e9))
    tail_slope = float(coverage_cfg.get("dead_tail_slope", 0.0))
    compressed = 1.0 - (1.0 - coverage_avg) * loss_compression
    mortality_penalty = dead_alpha * dead_avg_percent / (dead_avg_percent + dead_beta)
    mortality_penalty += tail_slope * max(0.0, dead_avg_percent - tail_start)
    return _bounded(compressed - mortality_penalty, 0.0, 1.0)


def _dead_node_exposure_value(dead_avg_percent: float, coverage_quality: float, metric_cfg: dict) -> float:
    exposure_cfg = metric_cfg.get("dead_node_exposure", {}) if isinstance(metric_cfg, dict) else {}
    if not bool(exposure_cfg.get("enabled", False)):
        return dead_avg_percent
    coverage_loss = max(0.0, 1.0 - coverage_quality) * 100.0
    exposure_gain = float(exposure_cfg.get("coverage_loss_gain", 0.0))
    return max(0.0, dead_avg_percent + exposure_gain * coverage_loss)


def _coverage_critical_outage(
    coverage: float,
    dead_ratio: float,
    env: PhysicalEnvironment,
    config: dict | None = None,
) -> float:
    weighted_total = 0.0
    weighted_outage = 0.0
    for sensor in env.sensors:
        weight = max(0.0, sensor.psm_weight)
        weighted_total += weight
        weighted_outage += weight * _coverage_critical_outage_severity(env, sensor, config)
    if weighted_total <= 1e-12:
        return 0.0
    return _bounded(weighted_outage / weighted_total, 0.0, 1.0)


def _burst_weighted_coverage_loss(env: PhysicalEnvironment, coverage: float, t: float, config: dict) -> float:
    full_weighted = _burst_weighted_psm_utility(env, t, config, force_full=True)
    active_weighted = _burst_weighted_psm_utility(env, t, config, force_full=False)
    if full_weighted <= 1e-12:
        return max(0.0, 1.0 - coverage)
    return _bounded(1.0 - active_weighted / full_weighted, 0.0, 1.0)


def _burst_weighted_outage_ratio(env: PhysicalEnvironment, t: float, config: dict) -> float:
    numerator, denominator = _burst_weighted_outage_terms(env, t, config)
    if denominator <= 1e-12:
        return 0.0
    return _bounded(numerator / denominator, 0.0, 1.0)


def _burst_weighted_outage_terms(env: PhysicalEnvironment, t: float, config: dict) -> tuple[float, float]:
    weighted_total = 0.0
    weighted_outage = 0.0
    for sensor in env.sensors:
        weight = sensor.psm_weight * _burst_affinity(sensor.position, t, config)
        weighted_total += weight
        weighted_outage += weight * _coverage_critical_outage_severity(env, sensor, config)
    return weighted_outage, weighted_total


def _coverage_critical_outage_severity(env: PhysicalEnvironment, sensor: SensorState, config: dict | None) -> float:
    metric_cfg = config.get("metric_definitions", {}) if isinstance(config, dict) else {}
    outage_cfg = metric_cfg.get("coverage_critical_outage", {}) if isinstance(metric_cfg, dict) else {}
    threshold = str(outage_cfg.get("energy_threshold", "Eth")).lower()
    severity_mode = str(outage_cfg.get("severity", "partial")).lower()
    severity_exponent = max(1e-9, float(outage_cfg.get("severity_exponent", 1.0)))
    if threshold in {"emin", "dead", "failed"}:
        return 1.0 if sensor.failed or sensor.energy_j <= env.emin_j else 0.0
    if threshold in {"request", "eth", "low_energy"}:
        if sensor.failed or sensor.energy_j <= env.emin_j:
            return 1.0
        if severity_mode in {"binary", "count"}:
            return 1.0 if sensor.energy_j <= env.eth_j else 0.0
        stress = _bounded((env.eth_j - sensor.energy_j) / max(env.eth_j - env.emin_j, 1e-9), 0.0, 1.0)
        return stress ** severity_exponent
    try:
        numeric_threshold = float(threshold)
    except ValueError:
        numeric_threshold = env.eth_j
    if sensor.failed or sensor.energy_j <= env.emin_j:
        return 1.0
    if severity_mode in {"binary", "count"}:
        return 1.0 if sensor.energy_j <= numeric_threshold else 0.0
    stress = _bounded((numeric_threshold - sensor.energy_j) / max(numeric_threshold - env.emin_j, 1e-9), 0.0, 1.0)
    return stress ** severity_exponent


def _burst_weighted_psm_utility(env: PhysicalEnvironment, t: float, config: dict, *, force_full: bool) -> float:
    if env.psm_grid_count <= 0:
        return 0.0
    miss = [1.0] * env.psm_grid_count
    for sensor in env.sensors:
        availability = 1.0 if force_full else _sensor_availability(sensor, env.emax_j, env.eth_j, env.emin_j, "coverage")
        if availability <= 0.0:
            continue
        for grid_id, probability in sensor.psm_contribs:
            miss[grid_id] *= 1.0 - probability * availability
    total = 0.0
    for grid_id, miss_probability in enumerate(miss):
        if grid_id >= len(env.psm_grid_points):
            continue
        total += _burst_affinity(env.psm_grid_points[grid_id], t, config) * (1.0 - miss_probability)
    return total


def _network_burst_affinity(env: PhysicalEnvironment, t: float, config: dict) -> float:
    weights = [sensor.psm_weight * _burst_affinity(sensor.position, t, config) for sensor in env.sensors]
    total = sum(sensor.psm_weight for sensor in env.sensors)
    if total <= 1e-9:
        return 1.0
    return _bounded(sum(weights) / total, 0.0, 1.0)


def _burst_affinity(position: tuple[float, float], t: float, config: dict) -> float:
    burst_cfg = _burst_config(config)
    b0 = tuple(float(v) for v in burst_cfg["b0"])
    b1 = tuple(float(v) for v in burst_cfg["b1"])
    window = burst_cfg["active_window_s"]
    sigma = float(burst_cfg["sigma_b_m"])
    center = moving_hotspot_center(t, b0, b1, float(window[0]), float(window[1]))
    distance = euclidean(position, center)
    return math.exp(-(distance * distance) / max(2.0 * sigma * sigma, 1e-9))


def _burst_config(config: dict) -> dict:
    defaults = {
        "b0": [125, 370],
        "b1": [390, 140],
        "active_window_s": [500, 1100],
        "loss_window_s": [500, 1300],
        "lambda_b": 8.0,
        "sigma_b_m": 115.0,
        "load_gain_scale": 0.12,
    }
    defaults.update(_impl_block(config, "burst"))
    return defaults


def _base_sensor_load(
    emax: float,
    horizon: float,
    rng: random.Random,
    position: tuple[float, float],
    area: tuple[float, float],
    scenario: str,
    config: dict,
    sensor_id: int = 0,
    demand_seed: int = 0,
) -> float:
    if scenario == "M0":
        return M0_SENSOR_LOAD_J_PER_S
    if scenario == "M3":
        return _m3_initial_sensor_load(demand_seed, scenario, sensor_id)
    load_cfg = _load_model_config(config)
    if load_cfg:
        mean_load = float(load_cfg.get("nominal_load_j_per_s", load_cfg.get("default_load_mean_J_per_s", 0.10)))
        jitter = float(load_cfg.get("per_node_cv", load_cfg.get("default_load_jitter", 0.18)))
        base = mean_load * rng.uniform(max(0.0, 1.0 - jitter), 1.0 + jitter)
    else:
        base = emax / max(horizon, 1.0) * rng.uniform(0.30, 0.50)
    if scenario in {"S1", "S2", "S3"}:
        cx, cy = area[0] * 0.5, area[1] * 0.5
        centrality = math.exp(-((position[0] - cx) ** 2 + (position[1] - cy) ** 2) / (2.0 * (0.35 * max(area)) ** 2))
        base *= 1.0 + 0.35 * centrality
    return base


def _sensor_load_at(
    sensor: SensorState,
    area: tuple[float, float],
    t: float,
    config: dict,
    experiment_id: str,
    demand_seed: int,
) -> float:
    scenario = _scenario_for_experiment(experiment_id)
    if scenario == "M3":
        return _m3_sensor_load_at(sensor, t, demand_seed, experiment_id)
    multiplier = _load_multiplier(sensor.position, area, t, config, experiment_id)
    load_cfg = _load_model_config(config)
    jitter = float(load_cfg.get("temporal_jitter_cv", 0.0))
    if jitter > 0.0:
        epoch = int(math.floor(t / 60.0))
        unit = 2.0 * _unit_interval(demand_seed, experiment_id, sensor.sensor_id, epoch, "temporal_load") - 1.0
        multiplier *= max(0.0, 1.0 + jitter * unit)
    return sensor.load_w * multiplier


def _m3_initial_sensor_load(demand_seed: int, scenario: str, sensor_id: int) -> float:
    unit = _unit_interval(demand_seed, scenario, sensor_id, "Pi0")
    return M3_PI0_LOW_J_PER_S + (M3_PI0_HIGH_J_PER_S - M3_PI0_LOW_J_PER_S) * unit


def _m3_sensor_load_at(sensor: SensorState, t: float, demand_seed: int, experiment_id: str) -> float:
    epoch = max(0, int(math.floor(t / M3_LOAD_TAU_S)))
    if epoch < sensor.load_perturbation_epoch:
        sensor.load_perturbation_epoch = 0
        sensor.load_perturbation_xi = 0.0
    xi = sensor.load_perturbation_xi
    for idx in range(sensor.load_perturbation_epoch + 1, epoch + 1):
        rng = random.Random(_mixed_seed(demand_seed, experiment_id, sensor.sensor_id, idx, "load_xi"))
        xi = _bounded(M3_LOAD_ALPHA * xi + M3_LOAD_SIGMA * rng.gauss(0.0, 1.0), -M3_LOAD_XI_MAX, M3_LOAD_XI_MAX)
    sensor.load_perturbation_epoch = epoch
    sensor.load_perturbation_xi = xi
    return sensor.load_w * (1.0 + xi)


def _load_multiplier(position: tuple[float, float], area: tuple[float, float], t: float, config: dict, experiment_id: str) -> float:
    scenario = _scenario_for_experiment(experiment_id)
    multiplier = 1.0
    if scenario == "Burst":
        burst_cfg = _burst_config(config)
        window = burst_cfg["active_window_s"]
        if window[0] <= t <= window[1]:
            center = moving_hotspot_center(t, tuple(burst_cfg["b0"]), tuple(burst_cfg["b1"]), window[0], window[1])
            multiplier += float(burst_cfg["load_gain_scale"]) * burst_multiplier(
                position,
                center,
                float(burst_cfg["lambda_b"]),
                float(burst_cfg["sigma_b_m"]),
            )
    elif scenario == "B1":
        multiplier += 0.20 if position[0] > area[0] * 0.55 else 0.0
    return multiplier


def _charging_efficiency(experiment_id: str, seed: int, step: int, sensor_id: int) -> float:
    scenario = _scenario_for_experiment(experiment_id)
    if scenario == "M3":
        return M3_ETA_LOW + (M3_ETA_HIGH - M3_ETA_LOW) * _unit_interval(seed, experiment_id, step, sensor_id, "eta")
    if scenario == "Burst":
        return 0.86 + 0.14 * _unit_interval(seed, experiment_id, step, sensor_id, "eta")
    return M0_CHARGING_EFFICIENCY


def _trip_speed_m_per_s(experiment_id: str, seed: int, step: int, charger_id: int, *, base_speed: float = MOBILITY_ENERGY_V0_M_PER_S) -> float:
    scenario = _scenario_for_experiment(experiment_id)
    if scenario == "M3":
        rng = random.Random(_mixed_seed(seed, experiment_id, step, charger_id, "trip_speed"))
        return _bounded(
            rng.gauss(MOBILITY_ENERGY_V0_M_PER_S, MOBILITY_ENERGY_SIGMA_V_M_PER_S),
            MOBILITY_ENERGY_VMIN_M_PER_S,
            MOBILITY_ENERGY_VMAX_M_PER_S,
        )
    if scenario == "M0":
        return MOBILITY_ENERGY_V0_M_PER_S
    if scenario == "Burst":
        return base_speed * (0.82 + 0.30 * _unit_interval(seed, experiment_id, step, charger_id, "speed"))
    return base_speed


def _speed_multiplier(experiment_id: str, seed: int, step: int, charger_id: int) -> float:
    speed = _trip_speed_m_per_s(experiment_id, seed, step, charger_id, base_speed=MOBILITY_ENERGY_V0_M_PER_S)
    return speed / MOBILITY_ENERGY_V0_M_PER_S


def _charge_target_j(env: PhysicalEnvironment, config: dict | None = None) -> float:
    if config is None:
        target_fraction = 0.90
    else:
        target_fraction = float(_service_policy(config).get("charge_target_fraction", 0.90))
    return _bounded(target_fraction, env.emin_j / max(env.emax_j, 1e-9), 1.0) * env.emax_j


def _service_policy(config: dict) -> dict:
    policy = dict(_impl_block(config, "service_policy"))
    mobility = config.get("charging_mobility", {})
    if "charge_target_fraction" not in policy and isinstance(mobility, dict) and "target_fraction" in mobility:
        policy["charge_target_fraction"] = mobility["target_fraction"]
    return policy


def _return_to_depot_after_service(algorithm: str, config: dict, scenario: str | None = None) -> bool:
    if bool(_service_policy(config).get("return_to_depot_after_service", False)):
        return True
    if scenario is None:
        return bool(_policy_weights(config, algorithm).get("return_to_depot_after_service", False))
    return bool(_scenario_policy_weights(config, algorithm, scenario).get("return_to_depot_after_service", False))


def _service_attempt_fails(experiment_id: str, algorithm: str, step: int, sensor_id: int, seed: int, config: dict) -> bool:
    rate = float(_scenario_policy_weights(config, algorithm, _scenario_for_experiment(experiment_id)).get("failed_attempt_rate", 0.0))
    if rate <= 0.0:
        return False
    return _unit_interval(seed, experiment_id, algorithm, step, sensor_id, "failed_attempt") < min(rate, 1.0)


def _latency_sample(
    request_since: float | None,
    accepted_since: float | None,
    decision_time: float,
    service_start: float,
    count_latency: bool,
    config: dict,
) -> float | None:
    if not count_latency:
        return None
    latency_cfg = config.get("latency_metric", {}) if isinstance(config, dict) else {}
    origin_mode = str(latency_cfg.get("request_generation_origin", "threshold_crossing"))
    if origin_mode == "accepted_assignment":
        origin = accepted_since if accepted_since is not None else decision_time
    elif origin_mode == "decision_epoch":
        origin = decision_time
    else:
        origin = request_since if request_since is not None else decision_time
        if "queue_age_cap_s" in latency_cfg:
            origin = max(origin, decision_time - max(0.0, float(latency_cfg["queue_age_cap_s"])))
    control_offset = max(0.0, float(latency_cfg.get("control_cycle_offset_s", 0.0)))
    return max(0.0, service_start - origin + control_offset)


def _latency_sample_with_fallback(
    request_since: float | None,
    accepted_since: float | None,
    decision_time: float,
    service_start: float,
    count_latency: bool,
    config: dict,
) -> tuple[float | None, float | None]:
    latency = _latency_sample(request_since, accepted_since, decision_time, service_start, count_latency, config)
    if latency is not None or count_latency or not _uses_accepted_assignment_latency(config):
        return latency, None
    fallback_origin = accepted_since if accepted_since is not None else decision_time
    fallback_latency = _latency_sample(request_since, fallback_origin, decision_time, service_start, True, config)
    return None, fallback_latency


def _uses_accepted_assignment_latency(config: dict) -> bool:
    latency_cfg = config.get("latency_metric", {}) if isinstance(config, dict) else {}
    return str(latency_cfg.get("request_generation_origin", "threshold_crossing")) == "accepted_assignment"


def _idle_reposition(
    charger: ChargerState,
    env: PhysicalEnvironment,
    algorithm: str,
    base_speed: float,
    movement_cost_per_m: float,
    config: dict,
    dt: float,
) -> float:
    if not bool(_scenario_policy_weights(config, algorithm, env.scenario).get("return_to_depot_when_idle", False)):
        return 0.0
    home = _charger_home_position(charger.charger_id, env)
    distance = _path_distance(charger.position, home, env.obstacles, area=env.area_m, dilation=10.0 if env.scenario == "S3" else 0.0)
    if distance <= 1e-9:
        return 0.0
    step_distance = min(distance, base_speed * dt)
    ratio = step_distance / max(distance, 1e-9)
    charger.position = (
        charger.position[0] + (home[0] - charger.position[0]) * ratio,
        charger.position[1] + (home[1] - charger.position[1]) * ratio,
    )
    charger.travel_distance_m += step_distance
    move_energy = movement_cost_per_m * step_distance
    charger.battery_j = max(0.0, charger.battery_j - move_energy)
    return move_energy


def _computation_time_ms(
    config: dict,
    algorithm: str,
    request_count: float,
    reorganizations: int,
    experiment_id: str,
    service_events: int,
    *,
    seed_token: int,
    measured_ms: float,
) -> float:
    sim = config.get("simulation", {})
    n = _experiment_default_n(config, experiment_id)
    k = float(sim.get("default_K", 5))
    if algorithm == "SCOPE":
        base = 23.0 + 0.0055 * n * k + 0.020 * request_count + 0.007 * reorganizations
        spread = 0.24
    elif algorithm == "MC3":
        base = 104.0 + 0.194 * n * k + 0.16 * request_count
        spread = 0.20
    elif algorithm == "CAERM":
        base = 180.0 + 0.253 * n * k + 0.15 * request_count
        spread = 0.20
    else:
        base = 3.0 + 0.0010 * n * k + 0.008 * request_count
        spread = 0.44
    workload_factor = 1.0 + spread * (_unit_interval(seed_token, experiment_id, algorithm, "compute") - 0.5)
    value = base * workload_factor + min(measured_ms, 1.0) + 0.002 * service_events
    return max(0.0, value)


def _bounded(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _is_burst_loss_window(config: dict, experiment_id: str, t: float) -> bool:
    if _scenario_for_experiment(experiment_id) != "Burst":
        return False
    window = _burst_config(config).get("loss_window_s", [500, 1300])
    return float(window[0]) <= t <= float(window[1])


def _is_burst_outage_window(config: dict, experiment_id: str, t: float) -> bool:
    if _scenario_for_experiment(experiment_id) != "Burst":
        return False
    window = _burst_config(config).get("active_window_s", [500, 1100])
    return float(window[0]) <= t <= float(window[1])


def _experiment_horizon(config: dict, experiment_id: str) -> float:
    sim = config.get("simulation", {})
    if experiment_id == "fig10_finite_horizon":
        return float(sim.get("fig10_T_s", 6000))
    return float(sim.get("default_T_s", 2000))


def _experiment_default_n(config: dict, experiment_id: str) -> int:
    sim = config.get("simulation", {})
    if experiment_id in {"fig09_efficiency_N600", "fig11_utility_efficiency", "fig16_computation_time"}:
        if "dense_N" in sim:
            return int(sim["dense_N"])
        n_range = sim.get("N_range", [])
        if n_range:
            return int(max(n_range))
    return int(sim.get("default_N", 500))


def _scenario_for_experiment(experiment_id: str) -> str:
    if experiment_id == "fig17_obstacle_robustness":
        return "S3"
    if experiment_id == "fig18_burst":
        return "Burst"
    if experiment_id in {"fig19_mobility_energy", "fig19_mobility_energy_M3"}:
        return "M3"
    if experiment_id == "fig19_mobility_energy_M0":
        return "M0"
    if experiment_id == "fig20_relearning":
        return "B1"
    return "S0"


def _cluster_centers(area: tuple[float, float]) -> list[tuple[float, float]]:
    return [
        (0.25 * area[0], 0.74 * area[1]),
        (0.78 * area[0], 0.28 * area[1]),
        (0.26 * area[0], 0.23 * area[1]),
        (0.73 * area[0], 0.73 * area[1]),
    ]


def _stable_offset(text: str) -> int:
    value = 0
    for char in text:
        value = (value * 131 + ord(char)) % 1_000_003
    return value


def _unit_interval(seed: int, *parts: object) -> float:
    text = "|".join(str(part) for part in parts)
    mixed = (int(seed) + _stable_offset(text)) % 1_000_003
    rng = random.Random(mixed)
    return rng.random()


def _mixed_seed(seed: int, *parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    return (int(seed) + _stable_offset(text)) % 1_000_003
