from __future__ import annotations

import math


def euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def movement_energy(distance_m: float, speed_mps: float, xi: float = 0.45, beta: float = 0.8) -> float:
    if speed_mps <= 0:
        raise ValueError("speed must be positive")
    power = xi * speed_mps * speed_mps + beta
    return power * distance_m / speed_mps
