from __future__ import annotations


def time_averaged(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def normalized_retention(value: float, reference: float) -> float:
    if reference == 0:
        return 0.0
    return 100.0 * value / reference
