#!/usr/bin/env python3
"""中文：核对共享模型策略的发行投影，不读取任何宿主型号。

English: Verify package projections of the authoritative dispatch policy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.dispatch_policy import CURRENT_POLICY_ID, policy, policy_digest, profile_weights  # noqa: E402


def validate_projections(root: Path = ROOT) -> list[str]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    declared = manifest["model_routing"]
    contract = policy()
    mismatches = []
    expected = {
        "policy_id": CURRENT_POLICY_ID, "policy_digest": policy_digest(),
        "role_profiles": contract["role_profiles"], "selection_scoring": contract["scoring"],
        "calibration_cost_formula": {"version": contract["cost_formula_version"], "weights": profile_weights()},
        "automatic_reviewer_profiles": {name: {"model": value["model"], "reasoning_effort": value["effort"]}
                                        for name, value in contract["profiles"].items()},
    }
    for name, value in expected.items():
        if declared.get(name) != value:
            mismatches.append("model_routing." + name)
    if manifest["quality_limits"]["reviewer_model_profiles"] != contract["role_profiles"]["reviewer"]:
        mismatches.append("quality_limits.reviewer_model_profiles")
    if declared["delegation_budget"].get("premium_limits") != contract["premium_limits"]:
        mismatches.append("delegation_budget.premium_limits")
    if declared["delegation_budget"].get("review_extension_units") != contract["review_extension_units"]:
        mismatches.append("delegation_budget.review_extension_units")
    return mismatches


if __name__ == "__main__":
    failures = validate_projections()
    print(json.dumps({"ok": not failures, "policy_id": CURRENT_POLICY_ID, "policy_digest": policy_digest(),
                      "profiles": len(profile_weights()), "mismatches": failures}, indent=2))
    raise SystemExit(1 if failures else 0)
