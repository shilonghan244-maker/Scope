from __future__ import annotations


def dead_node_ratio(dead_count: int, total_count: int) -> float:
    if total_count <= 0:
        return 0.0
    return 100.0 * dead_count / total_count


def degradation(stressed: float, reference: float) -> float:
    return stressed - reference
