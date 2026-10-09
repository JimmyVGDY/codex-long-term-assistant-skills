"""中文：资格试验的样本量规划；English: planning is never qualification."""
from __future__ import annotations

import math

from .routing_contract import integer, policy, policy_digest
from .routing_statistics import paired_quality


def zero_discordance_plan(comparisons: int) -> dict:
    """中文：使用与冻结策略完全相同的边界和取整规则。这是结果相同时的参考设计，不是通用样本下限；观测到改善时可用更少案例建立界限。同一问题的重复运行不增加独立案例数。
    
    English: Use the same exact bounds and rounding as the frozen policy.
    
    This is a reference design for equal outcomes, not a universal sample floor:
    observed improvement can establish a bound with fewer cases. Repetitions of
    one underlying problem never increase the independent-case count.
    """
    integer(comparisons, "PLANNING_COMPARISONS", minimum=1, maximum=153)
    limits = policy()["thresholds"]
    intervals = 4 * comparisons
    alpha = limits["family_alpha_ppm"]
    tail = alpha / 1_000_000 / intervals / 2

    def count(margin_bp: int) -> int:
        n = max(limits["min_independent_cases"], math.ceil(math.log(tail) / math.log1p(-margin_bp / 10000)))
        # 中文：核对整数边界实现，避免浮点与取整漂移。
        # English: Check the integer-bound implementation to avoid floating/rounding drift.
        while paired_quality([False] * n, [False] * n, family_intervals=intervals,
                             alpha_ppm=alpha)["upper_delta_bp"] > margin_bp:
            n += 1
        return n

    return {
        "schema_version": "qualification-size-plan/1", "policy_digest": policy_digest(),
        "comparisons": comparisons, "family_intervals": intervals,
        "alpha_ppm": alpha, "assumption": "zero-discordance-paired-outcomes",
        "independent_quality_cases": count(limits["noninferiority_margin_bp"]),
        "independent_clean_cases": count(limits["false_block_margin_bp"]),
        "qualification_granted": False,
        "limitations": ["Planning only; actual observations must pass all unchanged qualification gates.",
                        "Clean cases are a subset of independent cases, not extra evidence to double count.",
                        "Problem variants/repetitions are clustered before statistical calculation."],
    }
