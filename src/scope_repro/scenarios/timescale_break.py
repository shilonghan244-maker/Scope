from __future__ import annotations


def break_description(name: str) -> str:
    return {
        "B1": "regional consumption shift",
        "B2": "sensor re-deployment into a new spatial cluster",
        "B3": "large-scale permanent sensor failures",
    }[name]
