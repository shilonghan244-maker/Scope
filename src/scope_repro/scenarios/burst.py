from __future__ import annotations

import math


def moving_hotspot_center(t: float, start: tuple[float, float], end: tuple[float, float], t0: float, t1: float) -> tuple[float, float]:
    if t <= t0:
        return start
    if t >= t1:
        return end
    ratio = (t - t0) / (t1 - t0)
    return (start[0] + ratio * (end[0] - start[0]), start[1] + ratio * (end[1] - start[1]))


def burst_multiplier(point: tuple[float, float], center: tuple[float, float], lambda_b: float, sigma_b: float) -> float:
    distance_sq = (point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2
    return lambda_b * math.exp(-distance_sq / (2.0 * sigma_b * sigma_b))
