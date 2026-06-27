from __future__ import annotations


def average_latency(latencies_s: list[float]) -> float:
    if not latencies_s:
        return 0.0
    return sum(latencies_s) / len(latencies_s)
