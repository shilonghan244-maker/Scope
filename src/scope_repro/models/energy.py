from __future__ import annotations


def update_sensor_energy(current_j: float, load_w: float, dt_s: float, emax_j: float) -> float:
    return max(0.0, min(emax_j, current_j - load_w * dt_s))


def is_requesting(energy_j: float, threshold_j: float) -> bool:
    return energy_j <= threshold_j


def is_dead(energy_j: float, minimum_j: float) -> bool:
    return energy_j <= minimum_j
