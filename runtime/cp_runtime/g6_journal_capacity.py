"""中文：V3 有界账本为已报价尝试和迟到结算保留写入空间。
English: Bounded V3 journals reserve storage for quoted attempts and late settlement.
"""
from __future__ import annotations

from typing import Any, Mapping

from .g6_allowance_contract import funding_id
from .g6_flexible_policy import policy
from .routing_contract import fail

SCHEMA = "g6-budget-journal/3"
MAX_RECORDS = 8192
MAX_BYTES = 64 * 1024 * 1024
MAX_EVENT_BYTES = 16_384
RECORDS_PER_ATTEMPT = 6
ADMIN_RECORDS = 64


def projection(state: Mapping[str, Any], stored_bytes: int) -> dict[str, int]:
    spent: dict[str, int] = {}
    settlement = 0
    for pid in state["reservations"]:
        funding = state["permits"][pid].get("funding_id", "base")
        spent[funding] = spent.get(funding, 0) + 1
        if pid in state["terminals"] or state["receipts"].get(pid, {}).get("disposition") == "not_started":
            continue
        settlement += 1 if pid in state["receipts"] else 2
    remaining = max(0, policy()["budget_templates"][state["root"]["capacity_class"]]["attempts"]
                    - spent.get("base", 0))
    for key, request in state.get("allowance_requests", {}).items():
        if key in state.get("allowance_revoked", {}):
            continue
        for row in request["allocations"]:
            if row["work_id"] not in state.get("closed_review_work", {}):
                remaining += max(0, row["attempts"] - spent.get(funding_id(key, row["work_id"]), 0))
    held = remaining * RECORDS_PER_ATTEMPT + settlement + ADMIN_RECORDS
    return {"stored_records": state["sequence"], "stored_bytes": stored_bytes,
            "reserved_future_records": held, "reserved_future_bytes": held * MAX_EVENT_BYTES,
            "maximum_records": MAX_RECORDS, "maximum_bytes": MAX_BYTES}


def require_room(state: Mapping[str, Any], stored_bytes: int) -> dict[str, int]:
    result = projection(state, stored_bytes)
    if (result["stored_records"] + result["reserved_future_records"] > MAX_RECORDS
            or stored_bytes + result["reserved_future_bytes"] > MAX_BYTES):
        fail("G6_LEDGER_CAPACITY_INSUFFICIENT_FOR_QUOTE")
    return result
