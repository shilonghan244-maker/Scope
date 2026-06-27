from __future__ import annotations

import math


def detection_probability(distance_m: float, sensing_radius_m: float, eta1: float, eta2: float) -> float:
    if distance_m >= sensing_radius_m:
        return 0.0
    return math.exp(-eta1 * (distance_m**eta2))


def cooperative_coverage(probabilities: list[float]) -> float:
    miss = 1.0
    for probability in probabilities:
        miss *= 1.0 - max(0.0, min(1.0, probability))
    return 1.0 - miss


def grid_coverage_ratio(sensor_points: list[tuple[float, float]], grid_points: list[tuple[float, float]], params: dict) -> float:
    if not grid_points:
        return 0.0
    total = 0.0
    for gx, gy in grid_points:
        probs = []
        for sx, sy in sensor_points:
            distance = math.hypot(gx - sx, gy - sy)
            probs.append(detection_probability(distance, params["Rs"], params["eta1"], params["eta2"]))
        total += cooperative_coverage(probs)
    return total / len(grid_points)
