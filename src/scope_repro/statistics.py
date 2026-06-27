from __future__ import annotations

import math
from statistics import NormalDist

T_CRITICAL_975 = {
    1: 12.706204736432095,
    2: 4.302652729911275,
    3: 3.182446305284263,
    4: 2.7764451051977987,
    5: 2.570581835636314,
    6: 2.4469118487916806,
    7: 2.3646242510102993,
    8: 2.306004135204166,
    9: 2.2621571627409915,
    10: 2.2281388519649385,
    20: 2.0859634472658364,
    30: 2.0422724563012373,
    40: 2.021075390306273,
    49: 2.009575234489209,
}


def t_critical_975(df: int) -> float:
    if df in T_CRITICAL_975:
        return T_CRITICAL_975[df]
    if df < 1:
        raise ValueError("degrees of freedom must be positive")
    return 1.959963984540054


def mean_std_ci(values: list[float]) -> dict[str, float]:
    if not values:
        raise ValueError("values must not be empty")
    n = len(values)
    mean = sum(values) / n
    if n == 1:
        std = 0.0
        margin = 0.0
    else:
        variance = sum((value - mean) ** 2 for value in values) / (n - 1)
        std = math.sqrt(variance)
        margin = t_critical_975(n - 1) * std / math.sqrt(n)
    return {"n": float(n), "mean": mean, "std": std, "ci_low": mean - margin, "ci_high": mean + margin}


def paired_differences(
    scope_values: list[float], baseline_values: list[float], higher_is_better: bool = True
) -> list[float]:
    if len(scope_values) != len(baseline_values):
        raise ValueError("paired samples must have the same length")
    if higher_is_better:
        return [scope - base for scope, base in zip(scope_values, baseline_values)]
    return [base - scope for scope, base in zip(scope_values, baseline_values)]


def paired_effect_size(scope_values: list[float], baseline_values: list[float], higher_is_better: bool = True) -> float:
    diffs = paired_differences(scope_values, baseline_values, higher_is_better=higher_is_better)
    if len(diffs) < 2:
        return 0.0
    summary = mean_std_ci(diffs)
    if summary["std"] == 0:
        return 0.0
    return summary["mean"] / summary["std"]


def _rank_abs_values(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(abs(value) for value in values), key=lambda item: item[1])
    ranks = [0.0 for _ in values]
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and math.isclose(indexed[j][1], indexed[i][1], rel_tol=0.0, abs_tol=1e-12):
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def wilcoxon_signed_rank_pvalue(differences: list[float]) -> float:
    nonzero = [diff for diff in differences if abs(diff) > 1e-12]
    n = len(nonzero)
    if n == 0:
        return 1.0
    ranks = _rank_abs_values(nonzero)
    w_plus = sum(rank for rank, diff in zip(ranks, nonzero) if diff > 0)
    expected = n * (n + 1) / 4.0
    variance = n * (n + 1) * (2 * n + 1) / 24.0
    if variance == 0:
        return 1.0
    z = (abs(w_plus - expected) - 0.5) / math.sqrt(variance)
    p = 2.0 * (1.0 - NormalDist().cdf(z))
    return max(0.0, min(1.0, p))


def holm_adjust(p_values: list[float]) -> list[float]:
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted_sorted: list[tuple[int, float]] = []
    running = 0.0
    for rank, (idx, p_value) in enumerate(indexed):
        adjusted = min(1.0, (m - rank) * p_value)
        running = max(running, adjusted)
        adjusted_sorted.append((idx, running))
    adjusted = [0.0 for _ in p_values]
    for idx, value in adjusted_sorted:
        adjusted[idx] = value
    return adjusted
