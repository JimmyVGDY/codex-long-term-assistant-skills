"""中文：基于一个已核实账本提供有界重试建议，不创建新授权。

English: Bounded retry advice from one verified budget journal, never a new grant.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Mapping

from . import g6_budget_v1 as budget
from .common import parse_iso
from .g6_flexible_policy import policy
from .routing_contract import fail, ref, sha

TRANSIENT = {"host_capacity", "rate_limit", "transport_interruption", "verified_transient_read"}
HARD = {"authorization", "security", "identity_conflict", "ledger_integrity", "payload_hash"}


def next_action(state: Mapping[str, Any], *, work_item_id: str, failure_kind: str,
                now: str, deadline_at: str, host_retry_after_ms: int | None = None,
                changed_input_ref: str | None = None) -> dict[str, Any]:
    """中文：检查真实尝试；终态未知时继续使用同一句柄。
    
    English: Inspect actual attempts; unknown terminal always keeps the same handle.
    """
    if not isinstance(work_item_id, str) or not work_item_id:
        fail("G6_RETRY_WORK_ITEM")
    moment, deadline = parse_iso(now), parse_iso(deadline_at)
    if moment.tzinfo is None or deadline.tzinfo is None:
        fail("G6_RETRY_TIME")
    if host_retry_after_ms is not None and (type(host_retry_after_ms) is not int
                                            or not 0 <= host_retry_after_ms <= 3_600_000):
        fail("G6_RETRY_HINT")
    if changed_input_ref is not None:
        sha(changed_input_ref)
    attempts = [(pid, state["permits"][pid], reservation)
                for pid, reservation in state["reservations"].items()
                if state["permits"][pid]["work_item_id"] == work_item_id]
    active = [(pid, reservation) for pid, _, reservation in attempts
              if pid not in state["terminals"]
              and state["receipts"].get(pid, {}).get("disposition") != "not_started"]
    source = {"schema_version": "g6-retry-decision/1", "policy_id": policy()["policy_id"],
              "ledger_head": state["head_hash"], "work_item_id": work_item_id,
              "failure_kind": failure_kind, "prior_attempts": len(attempts),
              "prior_created_attempts": sum(state["receipts"].get(pid, {}).get("disposition") == "created"
                                            for pid, _, _ in attempts),
              "deadline_at": deadline_at, "host_retry_after_ms": host_retry_after_ms,
              "changed_input_ref": changed_input_ref}

    def result(action: str, reason: str, *, wait_ms: int = 0, handle: str | None = None) -> dict[str, Any]:
        value = {**source, "action": action, "reason_code": reason,
                 "wait_ms": wait_ms, "same_handle_ref": handle}
        value["decision_ref"] = ref(value)
        return value

    if active:
        if len(active) != 1:
            fail("G6_RETRY_MULTIPLE_ACTIVE")
        return result("RESUME_SAME_HANDLE", "TERMINAL_UNKNOWN_OR_RUNNING",
                      handle=active[0][1]["host_call_ref"])
    if failure_kind in HARD:
        return result("STOP_AFFECTED_ACTION", "VERIFIED_HARD_FAILURE")
    if attempts and any(state["terminals"].get(pid, {}).get("outcome") == "PASS"
                        for pid, _, _ in attempts):
        return result("NO_RETRY", "WORK_ITEM_ALREADY_COMPLETED")
    if failure_kind == "quality":
        if changed_input_ref is None or (attempts and changed_input_ref ==
                                         ref(attempts[-1][1]["facts"])):
            return result("CONTINUE_LOCAL", "UNCHANGED_QUALITY_RESULT_NO_BLIND_RERUN")
        return result("REPREPARE_WITH_CHANGED_INPUT", "CHANGED_INPUT_REQUIRES_NEW_DECISION")
    if failure_kind not in TRANSIENT:
        return result("CONTINUE_LOCAL", "FAILURE_CLASS_UNCONFIRMED")
    maximum = 1 + policy()["retry_policy"]["transient_default_max_additional_attempts"]
    if len(attempts) >= maximum:
        return result("CONTINUE_LOCAL", "TRANSIENT_RETRY_LIMIT")
    view = budget.snapshot(state, work_item_id=work_item_id, depth=0)
    available_units = (view["capacity_units"] - view["completed_charged_units"]
                       - view["inflight_reserved_units"] - view["future_required_hold_units"])
    available_attempts = (view["capacity_attempts"] - view["completed_charged_attempts"]
                          - view["inflight_reserved_attempts"]
                          - view["future_required_hold_attempts"])
    if available_units < 1 or available_attempts < 1:
        return result("CONTINUE_LOCAL", "BUDGET_EXHAUSTED_FOR_RETRY")
    backoff = host_retry_after_ms if host_retry_after_ms is not None else min(
        8_000, 1_000 * (2 ** max(0, len(attempts) - 1)))
    if moment + timedelta(milliseconds=backoff) >= deadline:
        return result("CONTINUE_LOCAL", "RETRY_DEADLINE_EXHAUSTED")
    return result("RETRY_NEW_PERMIT", "VERIFIED_TRANSIENT_WITHIN_BOUNDS", wait_ms=backoff)
