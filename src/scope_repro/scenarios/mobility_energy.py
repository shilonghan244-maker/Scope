from __future__ import annotations


def scenario_load_multiplier(mode: str) -> float:
    return {"M0": 1.0, "M1": 1.03, "M2": 1.16, "M3": 1.18}.get(mode, 1.0)


def charging_efficiency_range(mode: str) -> tuple[float, float]:
    if mode == "M3":
        return (0.72, 1.0)
    return (1.0, 1.0)
