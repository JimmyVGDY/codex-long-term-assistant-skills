"""中文：精简模型字段；English: fixed governance fields belong to the controller."""
from __future__ import annotations

import copy
from .review_contract import FINDING_FIELDS, STATUSES, validate_findings
from .routing_contract import exact, fail

SEMANTIC_FIELDS = {"status", "findings", "checked_scope", "unverified_items", "summary"}
FIXED_FINDING = {"disposition": "PENDING", "adoption_reason": "UNSPECIFIED", "repaired": False,
                 "regression_prevented": False, "regression_evidence": []}
MODEL_FINDING_FIELDS = FINDING_FIELDS - FIXED_FINDING.keys()


def expand_semantics(payload: dict) -> dict:
    exact(payload, SEMANTIC_FIELDS, "CONTEXT_V2_SEMANTIC_FIELDS")
    result = copy.deepcopy(payload)
    # 中文：展开攻击者可控的数据前，先验证容器并限制大小。
    # English: Validate the container and bound it before expanding attacker-controlled data.
    if result["status"] not in STATUSES:
        fail("CONTEXT_V2_SEMANTIC_STATUS")
    if not isinstance(result["findings"], list) or len(result["findings"]) > 256:
        fail("CONTEXT_V2_FINDINGS")
    for finding in result["findings"]:
        exact(finding, MODEL_FINDING_FIELDS, "CONTEXT_V2_FINDING_FIELDS")
        finding.update(copy.deepcopy(FIXED_FINDING))
    validate_findings(result["findings"], result["status"])
    return result
