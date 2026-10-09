"""中文：从现有根账本计算最小观察数据，不创建调用或改写路由。

English: Derive minimal observations from an existing root journal without dispatching or changing routing.
"""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from . import g6_budget_v1 as budget
from .common import parse_iso
from .event_v2 import OwnerTokenLock
from .g6_flexible_policy import POLICY_ID
from .routing_contract import ref, role_for


def collect(path: Path, *, expected_head: str) -> dict[str, Any]:
    """中文：同一已验证根内聚合，未知质量和真实费用保持未知。

    English: Aggregate one verified root; unknown quality and actual charges stay unknown.
    """
    with OwnerTokenLock(path, timeout=2):
        events = budget._read_events(path)
        state = budget.replay(events)
    if state["head_hash"] != expected_head:
        return {"schema_version": "g6-observation/1", "status": "STALE_SNAPSHOT",
                "next_action": "observe_latest_root_on_next_stop"}
    terminals_at = {e["data"]["permit_id"]: e["recorded_at"] for e in events
                    if e["event_type"] == "TERMINAL"}
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for permit_id, reservation in state["reservations"].items():
        permit = state["permits"][permit_id]
        key = (permit["approved_profile"], role_for(permit["agent_type"]))
        row = groups.setdefault(key, {"approved_profile": key[0], "role": key[1],
            "reserved_attempts": 0, "created_attempts": 0, "not_started_attempts": 0,
            "unresolved_attempts": 0, "charged_planning_units": 0,
            "inflight_planning_units": 0, "native_outcomes": Counter(),
            "work_items": set(), "durations_ms": [], "duration_unknown_count": 0})
        row["reserved_attempts"] += 1
        row["work_items"].add(permit["work_item_id"])
        receipt = state["receipts"].get(permit_id, {})
        terminal = state["terminals"].get(permit_id)
        if receipt.get("disposition") == "not_started":
            row["not_started_attempts"] += 1
        elif terminal:
            row["created_attempts"] += 1
            row["charged_planning_units"] += permit["planning_units"]
            row["native_outcomes"][terminal["outcome"]] += 1
            elapsed = (parse_iso(terminals_at[permit_id]) - parse_iso(reservation["reserved_at"])).total_seconds()
            if elapsed < 0 or not math.isfinite(elapsed):
                row["duration_unknown_count"] += 1
            else:
                row["durations_ms"].append(round(elapsed * 1000))
        else:
            row["created_attempts"] += int(receipt.get("disposition") == "created")
            row["unresolved_attempts"] += 1
            row["inflight_planning_units"] += permit["planning_units"]
    output = []
    for key in sorted(groups):
        row = groups[key]
        row["distinct_work_items"] = len(row.pop("work_items"))
        durations = sorted(row.pop("durations_ms"))
        row["native_outcomes"] = dict(sorted(row["native_outcomes"].items()))
        row["reservation_to_terminal_ms"] = {
            "sample_count": len(durations),
            "p50": median(durations) if durations else None,
            "p95": durations[math.ceil(len(durations) * .95) - 1] if durations else None}
        output.append(row)
    return {"schema_version": "g6-observation/1", "status": "OBSERVED",
            "policy_id": POLICY_ID, "policy_digest": state["root"]["policy_digest"],
            "identity": dict(state["root"]["identity"]),
            "root_session_ref": state["root"]["host_session_ref"],
            "ledger_head": expected_head, "source_ref": ref(events),
            "scope": "one-root; retries are attempts, not independent tasks",
            "groups": output,
            "business_completion_rate": None, "confirmed_finding_rate": None,
            "false_positive_rate": None, "rework_rate": None,
            "actual_credits": None, "main_agent_usage": None,
            "unknown_reasons": ["no-parent-finalized-quality-source", "no-bound-actual-cost-meter"],
            "units": {"planning": "policy-quota-only", "duration": "milliseconds"},
            "duration_definition": "reservation to journal terminal; includes lifecycle reporting delay",
            "strategy_change": "NONE", "execution_authorization": "NONE"}
