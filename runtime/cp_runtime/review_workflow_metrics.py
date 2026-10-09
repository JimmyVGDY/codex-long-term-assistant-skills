"""中文：分别记录交付、协议和语义证据，保留失败尝试；这些描述指标不授予生产资格，也不修改路由。

English: Separate delivery, protocol and semantic evidence without hiding failed attempts.

These descriptive metrics cannot grant production qualification or change routing.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Mapping

from .routing_contract import exact, fail, identifier, profile_spec

FIELDS = {"trial_id", "case_id", "profile_id", "excluded", "material_delivered",
          "protocol_valid", "boundary_compliant", "semantic_correct", "duration_ms", "cost_proxy"}


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator,
            "rate": numerator / denominator if denominator else None}


def summarize_trials(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """中文：消费控制器明确记录的观察，不从通用 status 推断评分。
    
    English: Consume explicit controller observations; never infer a grade from status.
    """
    if not isinstance(rows, list) or len(rows) > 10000:
        fail("WORKFLOW_TRIAL_LIMIT")
    seen = set()
    groups = defaultdict(list)
    for row in rows:
        exact(dict(row), FIELDS, "WORKFLOW_TRIAL_FIELDS")
        trial_id = identifier(row["trial_id"])
        identifier(row["case_id"])
        profile_spec(row["profile_id"])
        if trial_id in seen:
            fail("WORKFLOW_DUPLICATE_TRIAL")
        seen.add(trial_id)
        for key in ("excluded", "material_delivered", "protocol_valid", "boundary_compliant"):
            if type(row[key]) is not bool:
                fail("WORKFLOW_BOOLEAN_REQUIRED")
        if row["semantic_correct"] is not None and type(row["semantic_correct"]) is not bool:
            fail("WORKFLOW_SEMANTIC_GRADE_REQUIRED")
        if not row["material_delivered"] and row["semantic_correct"] is not None:
            fail("WORKFLOW_GRADE_WITHOUT_MATERIAL")
        for key in ("duration_ms", "cost_proxy"):
            value = row[key]
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                fail("WORKFLOW_RESOURCE_VALUE")
        groups[row["profile_id"]].append(row)

    def aggregate(values):
        eligible = [row for row in values if not row["excluded"]]
        scored = [row for row in eligible if row["semantic_correct"] is not None]
        complete = [row for row in eligible if row["material_delivered"] and row["protocol_valid"]
                    and row["boundary_compliant"] and row["semantic_correct"] is True]
        result = {
            "actual_attempts": len(values), "excluded_attempts": len(values) - len(eligible),
            "eligible_attempts": len(eligible),
            "independent_cases": len({row["case_id"] for row in eligible}),
            "material_delivery": _rate(sum(row["material_delivered"] for row in eligible), len(eligible)),
            "protocol_acceptance": _rate(sum(row["protocol_valid"] for row in eligible), len(eligible)),
            "semantic_accuracy_conditional_on_scored": _rate(sum(row["semantic_correct"] is True for row in scored), len(scored)),
            "semantic_scoring_coverage": _rate(len(scored), len(eligible)),
            "complete_workflow": _rate(len(complete), len(eligible)),
        }
        # 中文：失败、重试与排除的尝试仍计入资源总量。
        # English: Failed, retried and excluded attempts remain in the resource totals.
        for key in ("duration_ms", "cost_proxy"):
            measured = [row[key] for row in values if row[key] is not None]
            result[key] = {"known_sum": sum(measured), "known_attempts": len(measured),
                           "unknown_attempts": len(values) - len(measured)}
        return result

    return {"schema_version": "review-workflow-metrics/2", "production_qualification": "NOT_EVALUATED",
            "cost_basis": "declared_proxy_not_billing", "all": aggregate(rows),
            "profiles": {key: aggregate(values) for key, values in sorted(groups.items())}}
