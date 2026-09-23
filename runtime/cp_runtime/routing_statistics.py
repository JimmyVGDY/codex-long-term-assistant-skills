"""中文：V4 配对结果的有界统计；不调用模型，不自动批准卡片。

English: Bounded paired statistics, separate from model calls and publication.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache
from typing import Any, Sequence

from .routing_contract import RoutingError, fail, integer, ref

EXACT_METHOD = "paired-exact-bounds-v1"
BOOTSTRAP_METHOD = "paired-cluster-bootstrap-v1"


def _cdf(k: int, n: int, p: float) -> float:
    if k < 0:
        return 0.0
    if k >= n or p == 0.0:
        return 1.0
    if p == 1.0:
        return 0.0
    logp, logq = math.log(p), math.log1p(-p)
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
             + i * logp + (n - i) * logq for i in range(k + 1)]
    pivot = max(terms)
    return min(1.0, math.exp(pivot) * math.fsum(math.exp(value - pivot) for value in terms))


def _cdf_root(k: int, n: int, target: float) -> float:
    low, high = 0.0, 1.0
    for _ in range(48):
        middle = (low + high) / 2
        if _cdf(k, n, middle) > target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


@lru_cache(maxsize=1024)
def exact_binomial(successes: int, trials: int, alpha_ppm: int = 50000,
                   family_intervals: int = 1) -> tuple[float, float]:
    integer(trials, "STAT_TRIALS", minimum=1, maximum=10000)
    integer(successes, "STAT_SUCCESSES", maximum=trials)
    integer(alpha_ppm, "STAT_ALPHA", minimum=1, maximum=500000)
    integer(family_intervals, "STAT_COMPARISON_FAMILY", minimum=1, maximum=4096)
    tail = alpha_ppm / 1_000_000 / family_intervals / 2
    lower = 0.0 if successes == 0 else _cdf_root(successes - 1, trials, 1 - tail)
    upper = 1.0 if successes == trials else _cdf_root(successes, trials, tail)
    return lower, upper


def paired_quality(anchor: Sequence[bool], challenger: Sequence[bool], *,
                   family_intervals: int, alpha_ppm: int = 50000) -> dict[str, Any]:
    if len(anchor) != len(challenger) or not anchor or len(anchor) > 10000 \
            or any(type(value) is not bool for value in (*anchor, *challenger)):
        fail("PAIRED_BINARY_SAMPLES_INVALID")
    if type(family_intervals) is not int or family_intervals < 2:
        fail("PAIRED_FAMILY_REQUIRES_BOTH_PRIMITIVE_INTERVALS")
    wins = sum(b and not a for a, b in zip(anchor, challenger))
    losses = sum(a and not b for a, b in zip(anchor, challenger))
    win_low, win_high = exact_binomial(wins, len(anchor), alpha_ppm, family_intervals)
    loss_low, loss_high = exact_binomial(losses, len(anchor), alpha_ppm, family_intervals)
    return {
        "method": EXACT_METHOD, "n": len(anchor), "wins": wins, "losses": losses,
        "alpha_ppm": alpha_ppm, "family_intervals": family_intervals,
        "mean_delta_bp": round((wins - losses) * 10000 / len(anchor)),
        "lower_delta_bp": math.floor((win_low - loss_high) * 10000),
        "upper_delta_bp": math.ceil((win_high - loss_low) * 10000),
    }


def _quantile(values: list[float], probability: float) -> float:
    position = (len(values) - 1) * probability
    index = int(position)
    right = min(index + 1, len(values) - 1)
    return values[index] + (values[right] - values[index]) * (position - index)


def paired_ratio(anchor: Sequence[int], challenger: Sequence[int], *,
                 family_intervals: int, resamples: int = 100000,
                 alpha_ppm: int = 50000) -> dict[str, Any]:
    integer(family_intervals, "BOOTSTRAP_FAMILY", minimum=1, maximum=4096)
    integer(resamples, "BOOTSTRAP_RESAMPLES", minimum=1000, maximum=100000)
    integer(alpha_ppm, "BOOTSTRAP_ALPHA", minimum=1, maximum=500000)
    if len(anchor) != len(challenger) or not anchor or len(anchor) > 2000:
        fail("PAIRED_RESOURCE_SAMPLES_INVALID")
    for value in (*anchor, *challenger):
        integer(value, "PAIRED_RESOURCE_VALUE", maximum=1_000_000_000)
    source = ref({"anchor": list(anchor), "challenger": list(challenger),
                  "method": BOOTSTRAP_METHOD, "resamples": resamples,
                  "family_intervals": family_intervals, "alpha_ppm": alpha_ppm})
    common = {"method": BOOTSTRAP_METHOD, "n": len(anchor), "source_ref": source,
              "resamples": resamples, "alpha_ppm": alpha_ppm, "family_intervals": family_intervals}
    tail = alpha_ppm / 1_000_000 / family_intervals / 2
    if len(anchor) < 30 or sum(anchor) == 0 or resamples * tail < 10:
        return {**common, "status": "UNCERTAIN", "reason": "INSUFFICIENT_SAMPLES_OR_TAIL_RESOLUTION"}
    if len(set(zip(anchor, challenger))) < 2:
        return {**common, "status": "UNCERTAIN", "reason": "DEGENERATE_SAMPLES"}
    seed = int(source[7:23], 16)
    rng = random.Random(seed)
    ratios: list[float] = []
    for _ in range(resamples):
        indices = [rng.randrange(len(anchor)) for _ in anchor]
        denominator = sum(anchor[i] for i in indices)
        if not denominator:
            return {**common, "status": "UNCERTAIN", "reason": "ZERO_RESAMPLED_DENOMINATOR"}
        ratios.append(sum(challenger[i] for i in indices) / denominator)
    ratios.sort()
    if ratios[0] == ratios[-1]:
        return {**common, "status": "UNCERTAIN", "reason": "DEGENERATE_RATIO"}
    return {**common, "status": "ESTIMATED", "seed": seed,
            "lower_ratio_ppm": math.floor(_quantile(ratios, tail) * 1_000_000),
            "upper_ratio_ppm": math.ceil(_quantile(ratios, 1 - tail) * 1_000_000),
            "coverage_claim": "empirical-bootstrap-not-exact"}
