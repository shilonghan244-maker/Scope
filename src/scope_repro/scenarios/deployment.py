from __future__ import annotations

import random


def uniform_deployment(n: int, area: tuple[float, float], seed: int) -> list[tuple[float, float]]:
    rng = random.Random(seed)
    return [(rng.uniform(0, area[0]), rng.uniform(0, area[1])) for _ in range(n)]


def gaussian_mixture_deployment(
    n: int, area: tuple[float, float], seed: int, cluster_fraction: float = 0.7, sigma_c: float = 35.0
) -> list[tuple[float, float]]:
    rng = random.Random(seed)
    centers = [(125.0, 370.0), (390.0, 140.0), (130.0, 115.0), (365.0, 365.0)]
    clustered = int(round(n * cluster_fraction))
    points: list[tuple[float, float]] = []
    for i in range(clustered):
        cx, cy = centers[i % len(centers)]
        x = min(area[0], max(0.0, rng.gauss(cx, sigma_c)))
        y = min(area[1], max(0.0, rng.gauss(cy, sigma_c)))
        points.append((x, y))
    while len(points) < n:
        points.append((rng.uniform(0, area[0]), rng.uniform(0, area[1])))
    return points
