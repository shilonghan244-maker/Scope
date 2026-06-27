from __future__ import annotations


def travel_normalized(charged_energy_j: float, travel_m: float) -> float:
    return charged_energy_j / max(travel_m, 1e-9)


def utility_normalized(coverage_utility: float, energy_kj: float) -> float:
    return coverage_utility / max(energy_kj, 1e-9)
