"""中文：GPT-6 使用独立预算流水，并原子审批 Desktop 派发。

English: Independent GPT-6 budget journal with atomic Desktop dispatch admission.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from pathlib import Path
from typing import Any, Mapping

from .common import append_jsonl, canonical_json, parse_iso, require_external_state, utc_now
from .event_v2 import OwnerTokenLock
from .g6_flexible_policy import (POLICY_ID, POLICY_SHA256, PROFILES, decide,
                                 is_upward_adjustment, policy, profile_spec)
from .path_identity import same_path
from .routing_contract import _constant, _object, exact, fail, hex_digest, identity, ref, role_for, sha
from . import g6_allowance_contract as allowance
from . import g6_journal_capacity as capacity

SCHEMA = "g6-budget-journal/1"
ZERO_HASH = "0" * 64
EVENT_FIELDS = {"schema_version", "sequence", "event_id", "event_type", "recorded_at",
                "previous_hash", "data", "record_hash"}
MAX_RECORDS = 1000
MAX_BYTES = 2_000_000
ROOT_FIELDS = {"identity", "task_id", "host_session_ref", "repo_path", "capacity_class",
               "authorization_ref", "required_slots", "policy_digest"}
SLOT_FIELDS = {"work_item_id", "allowed_profiles", "baseline_profile"}
REVIEW_PHASES = {"pre_review", "post_review", "repair_review", "none"}
PREPARED_FIELDS = {"permit_id", "decision_ref", "work_item_id", "task_name", "agent_type",
                   "model", "reasoning_effort", "message_sha256", "planning_units",
                   "prepared_at", "expires_at", "facts", "capability", "gates", "adjustment",
                   "explicit_user_profile", "decision_time", "approved_profile", "upward_adjustment",
                   "depth"}
RESERVED_FIELDS = {"permit_id", "host_call_ref", "reserved_at"}
RECEIPT_FIELDS = {"permit_id", "disposition", "agent_ref", "proof_ref"}
TERMINAL_FIELDS = {"permit_id", "agent_ref", "outcome", "proof_ref"}
OUTCOMES = {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("rb") as stream:
        raw = stream.read(capacity.MAX_BYTES + 1)
    if len(raw) > capacity.MAX_BYTES or (raw and not raw.endswith(b"\n")):
        fail("G6_LEDGER_BOUND_OR_PARTIAL")
    lines = raw.splitlines(keepends=True)
    if len(lines) > capacity.MAX_RECORDS:
        fail("G6_LEDGER_RECORD_LIMIT")
    try:
        events, size = [], 0
        for line in lines:
            event = json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
            events.append(event)
            size += len(line)
            if isinstance(event, dict) and event.get("schema_version") == capacity.SCHEMA:
                if len(line) > capacity.MAX_EVENT_BYTES:
                    fail("G6_LEDGER_EVENT_SIZE_LIMIT")
            elif len(events) > MAX_RECORDS or size > MAX_BYTES:
                fail("G6_LEDGER_LEGACY_CAPACITY")
        return events
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("G6_LEDGER_INVALID_JSON") from exc


def _event(previous: dict[str, Any] | None, kind: str, data: Mapping[str, Any]) -> dict[str, Any]:
    version = (allowance.JOURNAL_SCHEMA if kind in allowance.EVENT_TYPES or
               previous is not None and previous["schema_version"] == allowance.JOURNAL_SCHEMA else SCHEMA)
    if (previous is not None and previous["schema_version"] == capacity.SCHEMA
            or kind == "REVIEW_WORK_REGISTERED" and data.get("phase") == allowance.TASK_PHASE):
        version = capacity.SCHEMA
    item = {"schema_version": version, "sequence": 1 if previous is None else previous["sequence"] + 1,
            "event_id": "G6E_" + secrets.token_hex(16), "event_type": kind,
            "recorded_at": utc_now(), "previous_hash": ZERO_HASH if previous is None else previous["record_hash"],
            "data": dict(data)}
    item["record_hash"] = ref(item)[7:]
    return item


def _append(path: Path, events: list[dict[str, Any]], kind: str,
            data: Mapping[str, Any]) -> dict[str, Any]:
    event = _event(events[-1] if events else None, kind, data)
    extended_capacity = event["schema_version"] == capacity.SCHEMA
    max_records, max_bytes = ((capacity.MAX_RECORDS, capacity.MAX_BYTES) if extended_capacity
                              else (MAX_RECORDS, MAX_BYTES))
    event_bytes = len(canonical_json(event).encode("utf-8")) + 1
    if extended_capacity and event_bytes > capacity.MAX_EVENT_BYTES:
        fail("G6_LEDGER_EVENT_SIZE_LIMIT")
    if len(events) >= max_records:
        fail("G6_LEDGER_RECORD_LIMIT")
    stored_bytes = (path.stat().st_size if path.exists() else 0) + event_bytes
    if stored_bytes > max_bytes:
        fail("G6_LEDGER_SIZE_LIMIT")
    updated = replay([*events, event])
    if extended_capacity:
        capacity.require_room(updated, stored_bytes)
    append_jsonl(path, event)
    return updated


def _slot_cost(slot: Mapping[str, Any]) -> int:
    if (not isinstance(slot, Mapping) or not SLOT_FIELDS.issubset(slot)
            or set(slot) - SLOT_FIELDS - {"review_phase", "origin_work_item_id"}):
        fail("G6_SLOT_FIELDS")
    origin = slot.get("origin_work_item_id")
    if origin is not None and (not isinstance(origin, str) or not origin or len(origin) > 160):
        fail("G6_SLOT_ORIGIN")
    if slot.get("review_phase", "none") not in REVIEW_PHASES:
        fail("G6_SLOT_REVIEW_PHASE")
    allowed = slot["allowed_profiles"]
    baseline = slot["baseline_profile"]
    if baseline not in PROFILES or (allowed is not None and
                                    (not isinstance(allowed, list) or not allowed
                                     or len(allowed) != len(set(allowed))
                                     or any(item not in PROFILES for item in allowed)
                                     or baseline not in allowed)):
        fail("G6_SLOT_PROFILE")
    return (min(profile_spec(item)["planning_units"] for item in allowed)
            if allowed is not None else profile_spec(baseline)["planning_units"])


def _root(data: Mapping[str, Any]) -> dict[str, Any]:
    root = exact(dict(data), ROOT_FIELDS, "G6_ROOT_FIELDS")
    identity(root["identity"])
    if not isinstance(root["task_id"], str) or not root["task_id"] or len(root["task_id"]) > 160:
        fail("G6_ROOT_TASK")
    sha(root["host_session_ref"])
    sha(root["authorization_ref"])
    if root["policy_digest"] != "sha256:" + POLICY_SHA256:
        fail("G6_ROOT_POLICY")
    if not isinstance(root["repo_path"], str) or not Path(root["repo_path"]).is_absolute():
        fail("G6_ROOT_REPO")
    if root["capacity_class"] not in policy()["budget_templates"]:
        fail("G6_ROOT_CAPACITY")
    slots = root["required_slots"]
    if not isinstance(slots, list) or len(slots) > 32:
        fail("G6_ROOT_SLOTS")
    names = set()
    for slot in slots:
        if (not isinstance(slot.get("work_item_id"), str) or not slot["work_item_id"]
                or slot["work_item_id"] in names):
            fail("G6_ROOT_SLOT_ID")
        names.add(slot["work_item_id"])
        _slot_cost(slot)
    return root


def replay(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        fail("G6_LEDGER_MISSING")
    state: dict[str, Any] | None = None
    previous = ZERO_HASH
    event_ids = set()
    extended = False
    protocol_version = 1
    for sequence, event in enumerate(events, 1):
        exact(event, EVENT_FIELDS, "G6_LEDGER_EVENT_FIELDS")
        version = event.get("schema_version")
        number = {SCHEMA: 1, allowance.JOURNAL_SCHEMA: 2, capacity.SCHEMA: 3}.get(version, 0)
        if (number < protocol_version
                or event.get("sequence") != sequence or event.get("previous_hash") != previous
                or event.get("record_hash") != ref({k: v for k, v in event.items()
                                                    if k != "record_hash"})[7:]
                or not isinstance(event["event_id"], str)
                or not re.fullmatch(r"G6E_[0-9a-f]{32}", event["event_id"])
                or event["event_id"] in event_ids):
            fail("G6_LEDGER_CHAIN")
        if number == 3 and protocol_version < 3 and not (
                event["event_type"] == "REVIEW_WORK_REGISTERED"
                and event["data"].get("phase") == allowance.TASK_PHASE):
            fail("G6_TASK_EXECUTION_UPGRADE_REQUIRED")
        protocol_version = number
        event_ids.add(event["event_id"])
        parse_iso(event["recorded_at"])
        previous = event["record_hash"]
        kind, data = event["event_type"], event["data"]
        if sequence == 1:
            if kind != "ROOT_INITIALIZED" or version != SCHEMA:
                fail("G6_LEDGER_FIRST_EVENT")
            root = _root(data)
            state = {"root": root, "permits": {}, "host_calls": {}, "reservations": {},
                     "receipts": {}, "terminals": {}, "sequence": sequence,
                     "head_hash": previous}
            continue
        assert state is not None
        if number >= 2 and not extended:
            extended = True
            state.update(protocol_version=2, review_work={}, allowance_requests={},
                         allowance_grants={}, allowance_revoked={}, review_calls={}, closed_review_work={})
        if number >= 2:
            state["protocol_version"] = number
        if kind in allowance.EVENT_TYPES:
            if not extended:
                fail("G6_EXTENSION_VERSION_REQUIRED")
            allowance.apply_event(state, kind, data)
            if kind == "REVIEW_WORK_REGISTERED" and data["base_funded"]:
                view = snapshot(state, work_item_id="status", depth=0)
                if (view["completed_charged_units"] + view["inflight_reserved_units"]
                        + view["future_required_hold_units"] > view["capacity_units"]
                        or view["completed_charged_attempts"] + view["inflight_reserved_attempts"]
                        + view["future_required_hold_attempts"] > view["capacity_attempts"]):
                    fail("G6_REQUIRED_REVIEW_EXCEEDS_BASE")
        elif kind == "PREPARED":
            exact(data, PREPARED_FIELDS | ({"funding_id"} if extended else set()), "G6_PREPARED_FIELDS")
            permit_id = data["permit_id"]
            previous_names = [(pid, p) for pid, p in state["permits"].items()
                              if p["task_name"] == data["task_name"]]
            if (not isinstance(permit_id, str) or not re.fullmatch(r"G6P_[0-9a-f]{32}", permit_id)
                    or not isinstance(data["task_name"], str)
                    or not re.fullmatch(r"[a-z0-9_]{1,64}", data["task_name"])
                    or data["agent_type"] is None):
                fail("G6_PREPARED_IDENTITY")
            role_for(data["agent_type"])
            sha(data["decision_ref"])
            hex_digest(data["message_sha256"])
            parse_iso(data["prepared_at"])
            parse_iso(data["expires_at"])
            if (data["approved_profile"] in PROFILES and
                    (data["model"] != profile_spec(data["approved_profile"])["model"]
                     or data["reasoning_effort"] != profile_spec(data["approved_profile"])["effort"])):
                fail("G6_PREPARED_PROFILE_TUPLE")
            if (permit_id in state["permits"] or data["approved_profile"] not in PROFILES
                    or data["planning_units"] != profile_spec(data["approved_profile"])["planning_units"]
                    or any(pid in state["reservations"] or
                           parse_iso(data["prepared_at"]) < parse_iso(p["expires_at"])
                           for pid, p in previous_names)):
                fail("G6_PREPARED_CONFLICT")
            state["permits"][permit_id] = data
        elif kind == "RESERVED":
            exact(data, RESERVED_FIELDS | ({"funding_id"} if extended else set()), "G6_RESERVED_FIELDS")
            permit_id = data["permit_id"]
            call_ref = sha(data["host_call_ref"])
            if (permit_id not in state["permits"] or permit_id in state["reservations"]
                    or call_ref in state["host_calls"]):
                fail("G6_RESERVATION_CONFLICT")
            if extended:
                permit = state["permits"][permit_id]
                if data["funding_id"] != permit.get("funding_id", "base"):
                    fail("G6_FUNDING_CHANGED")
                _check_funding(state, permit, data["funding_id"])
            state["reservations"][permit_id] = data
            state["host_calls"][call_ref] = permit_id
        elif kind == "HOST_RECEIPT":
            exact(data, RECEIPT_FIELDS, "G6_RECEIPT_FIELDS")
            permit_id = data["permit_id"]
            if permit_id not in state["reservations"] or permit_id in state["receipts"]:
                fail("G6_RECEIPT_CONFLICT")
            if data["disposition"] not in {"created", "not_started"}:
                fail("G6_RECEIPT_DISPOSITION")
            sha(data["proof_ref"])
            if data["disposition"] == "created":
                sha(data["agent_ref"])
            elif data["agent_ref"] is not None:
                fail("G6_NO_START_AGENT")
            state["receipts"][permit_id] = data
        elif kind == "NATIVE_COMPLETED_RECOVERED":
            # 中文：单独记录已经发生的完整调用，不伪造当时成功预占或业务通过。
            # English: Account for a completed native call without inventing admission or a passing task verdict.
            exact(data, {"permit_id", "host_call_ref", "agent_ref", "created_at", "proof_ref"},
                  "G6_RECOVERED_COMPLETION_FIELDS")
            pid, call_ref = data["permit_id"], sha(data["host_call_ref"])
            permit = state["permits"].get(pid)
            if (number != 3 or permit is None or pid in state["reservations"]
                    or call_ref in state["host_calls"]
                    or state["review_work"].get(permit["work_item_id"], {}).get("phase") != allowance.TASK_PHASE
                    or data["agent_ref"] != ref("/root/" + permit["task_name"])
                    or not parse_iso(permit["prepared_at"]) <= parse_iso(data["created_at"]) < parse_iso(permit["expires_at"])):
                fail("G6_RECOVERED_COMPLETION_IDENTITY")
            sha(data["proof_ref"])
            _check_funding(state, permit, permit.get("funding_id", "base"))
            state["reservations"][pid] = {"permit_id": pid, "host_call_ref": call_ref,
                "reserved_at": data["created_at"], "funding_id": permit.get("funding_id", "base"),
                "admission_verified": False}
            state["host_calls"][call_ref] = pid
            state["receipts"][pid] = {"permit_id": pid, "disposition": "created",
                "agent_ref": data["agent_ref"], "proof_ref": data["proof_ref"]}
            state["terminals"][pid] = {"permit_id": pid, "agent_ref": data["agent_ref"],
                "outcome": "UNKNOWN", "proof_ref": data["proof_ref"]}
        elif kind == "TERMINAL":
            exact(data, TERMINAL_FIELDS, "G6_TERMINAL_FIELDS")
            permit_id = data["permit_id"]
            receipt = state["receipts"].get(permit_id)
            if (not receipt or receipt["disposition"] != "created"
                    or permit_id in state["terminals"] or data["agent_ref"] != receipt["agent_ref"]
                    or data["outcome"] not in OUTCOMES):
                fail("G6_TERMINAL_CONFLICT")
            sha(data["proof_ref"])
            state["terminals"][permit_id] = data
        else:
            fail("G6_LEDGER_EVENT_UNKNOWN")
        state["sequence"] = sequence
        state["head_hash"] = previous
    assert state is not None
    return state


def read_budget(path: Path) -> dict[str, Any]:
    # 中文：锁内取得完整事件快照，锁外校验回放；写入方仍在自己的锁内重验。
    # English: Snapshot complete events under the lock, then validate/replay outside it;
    # writers still revalidate their own current state while holding the lock.
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
    return replay(events)


def _adjustment_origin(state: Mapping[str, Any], work_item_id: str) -> tuple[str, str]:
    # 中文：明确登记的工作谱系使用固定来源；未知谱系共享根额度，改名不能重置次数。
    # English: Registered lineage has a fixed origin; unknown lineage shares the root allowance across renames.
    slot = next((slot for slot in state["root"]["required_slots"]
                 if slot["work_item_id"] == work_item_id), None)
    return (("registered", slot.get("origin_work_item_id") or slot["work_item_id"])
            if slot is not None else ("root", state["root"]["task_id"]))


def _usage(state: Mapping[str, Any], work_item_id: str | None = None,
           funding_id: str | None = None) -> dict[str, int]:
    completed_units = completed_attempts = inflight_units = inflight_attempts = 0
    active = astra_active = upward = 0
    finished_items = set()
    for permit_id, reservation in state["reservations"].items():
        permit = state["permits"][permit_id]
        receipt = state["receipts"].get(permit_id)
        terminal = state["terminals"].get(permit_id)
        units = permit["planning_units"]
        included = funding_id is None or permit.get("funding_id", "base") == funding_id
        if receipt and receipt["disposition"] == "not_started":
            completed_attempts += int(included)
        elif terminal:
            completed_units += units if included else 0
            completed_attempts += int(included)
            if terminal["outcome"] == "PASS":
                finished_items.add(permit["work_item_id"])
        else:
            inflight_units += units if included else 0
            inflight_attempts += int(included)
            active += 1
            if permit["approved_profile"].startswith("g6-astra-"):
                astra_active += 1
        if work_item_id is not None and \
                _adjustment_origin(state, permit["work_item_id"]) == _adjustment_origin(state, work_item_id) \
                and permit["upward_adjustment"]:
            upward += 1
    pending_active_items = {state["permits"][permit_id]["work_item_id"]
                            for permit_id in state["reservations"]
                            if permit_id not in state["terminals"]
                            and state["receipts"].get(permit_id, {}).get("disposition") != "not_started"}
    hold_units = hold_attempts = 0
    for slot in state["root"]["required_slots"] if funding_id in {None, "base"} else []:
        item = slot["work_item_id"]
        if item in finished_items or item in pending_active_items or item == work_item_id:
            continue
        hold_units += _slot_cost(slot)
        hold_attempts += 1
    if funding_id in {None, "base"}:
        attempted = {state["permits"][pid]["work_item_id"] for pid in state["reservations"]
                     if state["receipts"].get(pid, {}).get("disposition") != "not_started"}
        attempt_capacity = policy()["budget_templates"][state["root"]["capacity_class"]]["attempts"]
        for work in state.get("review_work", {}).values():
            if (work["required"] and work["base_funded"] and work["work_id"] not in attempted
                    and work["work_id"] not in state.get("closed_review_work", {})
                    and work["work_id"] != work_item_id):
                hold_units += profile_spec(work["profile_id"])["planning_units"]
                hold_attempts += int(completed_attempts + inflight_attempts + hold_attempts < attempt_capacity)
    return {"completed_charged_units": completed_units,
            "completed_charged_attempts": completed_attempts,
            "inflight_reserved_units": inflight_units,
            "inflight_reserved_attempts": inflight_attempts,
            "future_required_hold_units": hold_units,
            "future_required_hold_attempts": hold_attempts,
            "active_calls": active, "astra_active": astra_active,
            "upward_adjustments_used": upward}


def snapshot(state: Mapping[str, Any], *, work_item_id: str, depth: int,
             funding_id: str = "base") -> dict[str, Any]:
    root = state["root"]
    capacity = policy()["budget_templates"][root["capacity_class"]]
    concurrency = policy()["concurrency_defaults"][root["capacity_class"]]
    authority = root["authorization_ref"]
    if funding_id != "base":
        bucket = allowance.buckets(state).get(funding_id)
        if bucket is None or bucket["work_id"] != work_item_id:
            fail("G6_ALLOWANCE_UNAVAILABLE_FOR_WORK")
        capacity = {"units": bucket["units"], "attempts": bucket["attempts"]}
        authority = bucket["authorization_ref"]
    result = {"schema_version": "g6-budget-snapshot/1", "ledger_head": state["head_hash"],
            "capacity_class": root["capacity_class"], "capacity_units": capacity["units"],
            "capacity_attempts": capacity["attempts"],
            **_usage(state, work_item_id, funding_id), "parallel_limit": concurrency["parallel"],
            "depth_limit": concurrency["depth"], "depth": depth}
    if state.get("protocol_version", 1) >= 2:
        result.update(schema_version="g6-budget-snapshot/2", funding_id=funding_id,
                      authorization_ref=authority)
    return result


def _check_funding(state: Mapping[str, Any], permit: Mapping[str, Any], funding_id: str) -> None:
    if permit["work_item_id"] in state.get("closed_review_work", {}):
        fail("G6_REVIEW_WORK_CLOSED")
    if any(state["permits"][pid]["work_item_id"] == permit["work_item_id"]
           and pid not in state["terminals"]
           and state["receipts"].get(pid, {}).get("disposition") != "not_started"
           for pid in state["reservations"]):
        fail("G6_WORK_ITEM_ALREADY_INFLIGHT")
    work = state.get("review_work", {}).get(permit["work_item_id"])
    if work and (permit["agent_type"] != work["agent_type"]
                 or permit["approved_profile"] != work["profile_id"]):
        fail("G6_ALLOWANCE_WORK_CONSTRAINT")
    if funding_id != "base":
        bucket = allowance.buckets(state).get(funding_id)
        if (not bucket or bucket["work_id"] != permit["work_item_id"]
                or bucket["agent_type"] != permit["agent_type"]
                or bucket["profile_id"] != permit["approved_profile"]):
            fail("G6_ALLOWANCE_SCOPE_CONFLICT")
    view = snapshot(state, work_item_id=permit["work_item_id"], depth=permit["depth"], funding_id=funding_id)
    if (view["completed_charged_units"] + view["inflight_reserved_units"]
            + view["future_required_hold_units"] + permit["planning_units"] > view["capacity_units"]
            or view["completed_charged_attempts"] + view["inflight_reserved_attempts"]
            + view["future_required_hold_attempts"] + 1 > view["capacity_attempts"]
            or view["active_calls"] >= view["parallel_limit"]
            or view["depth"] >= view["depth_limit"]
            or permit["approved_profile"].startswith("g6-astra-") and view["astra_active"] >= 1):
        fail("G6_ALLOWANCE_CAPACITY_EXCEEDED")


def _select_funding(state: Mapping[str, Any], work_item_id: str, depth: int) -> str:
    work = state.get("review_work", {}).get(work_item_id)
    if not work:
        return "base"
    cost = profile_spec(work["profile_id"])["planning_units"]
    # 中文：预算不足时使用该工作专属追加桶；不同桶不混用，旧支出不会变成退款。
    # English: Fall back to this work's grant, without pooling buckets or refunding history.
    choices = [*(key for key, value in allowance.buckets(state).items()
                 if value["work_id"] == work_item_id), "base"]
    for key in choices:
        view = snapshot(state, work_item_id=work_item_id, depth=depth, funding_id=key)
        if (view["capacity_units"] - view["completed_charged_units"] - view["inflight_reserved_units"]
                - view["future_required_hold_units"] >= cost
                and view["capacity_attempts"] - view["completed_charged_attempts"]
                - view["inflight_reserved_attempts"] - view["future_required_hold_attempts"] >= 1):
            return key
    return choices[-1]


def decision_for_work(state: Mapping[str, Any], *, facts: Mapping[str, Any],
                       capability: Mapping[str, Any], gates: list[Mapping[str, Any]],
                       agent_type: str, task_name: str, message: str, decision_time: str,
                       adjustment: Mapping[str, Any] | None = None,
                       explicit_user_profile: str | None = None, depth: int = 0,
                       funding_id: str = "base") -> dict[str, Any]:
    """中文：共享派发决策；工作档位约束不能冒充宿主不可用或用户选型。

    English: One decision path; a work constraint is not host capability or user authority.
    """
    item = facts["work_item_id"]
    work = state.get("review_work", {}).get(item)
    selected_adjustment = adjustment
    selected_user_profile = explicit_user_profile
    if work:
        if item in state.get("closed_review_work", {}) or agent_type != work["agent_type"]:
            fail("G6_REVIEW_WORK_ROLE_OR_STATE")
        if funding_id != "base":
            bucket = allowance.buckets(state).get(funding_id)
            if not bucket or bucket["work_id"] != item or bucket["agent_type"] != agent_type:
                fail("G6_ALLOWANCE_SCOPE_CONFLICT")
            # 中文：只有已入根账本的实际追加批准才能提供显式选型权限。
            # English: Only an actual root grant may supply this explicit profile authority.
            selected_user_profile = selected_user_profile or bucket["profile_id"]
        elif selected_user_profile is None and selected_adjustment is None:
            selected_adjustment = {"requested_profile": work["profile_id"], "source": "model_semantic",
                                   "reason": "Registered review requirement", "source_ref": None}
    result = decide(facts=facts, budget=snapshot(state, work_item_id=item, depth=depth, funding_id=funding_id),
                    capability=capability, gates=gates, agent_type=agent_type, task_name=task_name,
                    message=message, decision_time=decision_time, adjustment=selected_adjustment,
                    explicit_user_profile=selected_user_profile)
    if work and result["approved_profile"] not in {None, work["profile_id"]}:
        result = {key: value for key, value in result.items() if key not in {"decision_ref", "exact_tool_parameters"}}
        result.update(decision="CONTINUE_LOCAL", approved_profile=None, planning_units=0,
                      allowed_adjustment_profiles=[], tool_parameters_ref=None,
                      next_action="prepare_scoped_allowance_quote",
                      reason_codes=sorted(set(result["reason_codes"] + ["REVIEW_PROFILE_REQUIRES_AUTHORIZED_CAPACITY"])))
        result["decision_ref"] = ref(result)
        result["exact_tool_parameters"] = None
    return result


def register_review_work(path: Path, *, boundary_id: str, phase: str, agent_type: str,
                         profile_id: str, scope_paths: list[str], purpose: str,
                         required: bool = True) -> dict[str, Any]:
    if not isinstance(scope_paths, list):
        fail("G6_ALLOWANCE_SCOPE_PATHS")
    item = {"boundary_id": boundary_id, "phase": phase, "agent_type": agent_type,
            "profile_id": profile_id, "scope_paths": sorted(set(scope_paths)), "purpose": purpose,
            "required": required, "base_funded": False}
    item["work_id"] = allowance.work_identity(item)
    allowance.validate_work(item)
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        if any(slot["work_item_id"] == item["work_id"] for slot in state["root"]["required_slots"]):
            fail("G6_REVIEW_WORK_LEGACY_SLOT_CONFLICT")
        existing = state.get("review_work", {}).get(item["work_id"])
        if existing:
            if item["work_id"] in state.get("closed_review_work", {}):
                fail("G6_REVIEW_WORK_CLOSED")
            if existing["required"] != required:
                fail("G6_REVIEW_WORK_REQUIRED_CHANGED")
            return existing
        view = snapshot(state, work_item_id=item["work_id"], depth=0)
        item["base_funded"] = (
            view["capacity_units"] - view["completed_charged_units"] - view["inflight_reserved_units"]
            - view["future_required_hold_units"] >= profile_spec(profile_id)["planning_units"]
            and view["capacity_attempts"] - view["completed_charged_attempts"]
            - view["inflight_reserved_attempts"] - view["future_required_hold_attempts"] >= 1)
        _append(path, events, "REVIEW_WORK_REGISTERED", item)
        return item


def request_allowance(path: Path, *, work_ids: list[str], dispatches: int | Mapping[str, int] = 1,
                       retry_limit: int = 2) -> dict[str, Any]:
    from .routing_contract import integer
    integer(retry_limit, "G6_ALLOWANCE_RETRY_LIMIT", maximum=2)
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        works = state.get("review_work", {})
        if not isinstance(work_ids, list) or any(item not in works for item in work_ids):
            fail("G6_ALLOWANCE_WORK_UNKNOWN")
        if any(item in state.get("closed_review_work", {}) for item in work_ids):
            fail("G6_REVIEW_WORK_CLOSED")
        if isinstance(dispatches, Mapping) and set(dispatches) != set(work_ids):
            fail("G6_ALLOWANCE_DISPATCH_SCOPE")
        counts = {item: dispatches[item] if isinstance(dispatches, Mapping) else dispatches for item in work_ids}
        execution = any(works[key]["phase"] == allowance.TASK_PHASE for key in work_ids)
        for count in counts.values():
            integer(count, "G6_ALLOWANCE_DISPATCHES", minimum=1, maximum=128 if execution else 8)
        rows = [{"work_id": item, "dispatches": counts[item],
                 "attempts": counts[item] * (retry_limit + 1),
                 "units": counts[item] * profile_spec(works[item]["profile_id"])["planning_units"]}
                for item in work_ids]
        for key, previous in state.get("allowance_requests", {}).items():
            if (previous["allocations"] == rows and key not in state["allowance_grants"]
                    and key not in state["allowance_revoked"]):
                return previous
        request = {"request_id": "G6Q_" + secrets.token_hex(16), "allocations": rows,
                   "question_version": 2 if execution else 1,
                   "requested_at": utc_now(), "scope_ref": ref([works[item] for item in work_ids])}
        _append(path, events, "ALLOWANCE_REQUESTED", request)
        return request


def allowance_status(state: Mapping[str, Any]) -> dict[str, Any]:
    base = snapshot(state, work_item_id="status", depth=0)
    grants = []
    for key, bucket in allowance.buckets(state, include_revoked=True).items():
        grants.append({**bucket, "funding_id": key, "usage": _usage(state, bucket["work_id"], key),
                       "revoked": bucket["request_id"] in state.get("allowance_revoked", {})})
    return {"schema_version": "g6-allowance-status/1", "ledger_head": state["head_hash"],
            "base": base, "grants": grants,
            "pending_requests": [request for key, request in state.get("allowance_requests", {}).items()
                                 if key not in state.get("allowance_grants", {})
                                 and key not in state.get("allowance_revoked", {})],
            "closed_review_work": sorted(state.get("closed_review_work", {})),
            "total_usage": _usage(state), "actual_credits": None}


def close_review_work(path: Path, work_id: str) -> None:
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        if work_id not in state.get("closed_review_work", {}):
            _append(path, events, "REVIEW_WORK_CLOSED", {"work_id": work_id})


def initialize(path: Path, *, identity_value: Mapping[str, str], host_session_id: str,
               repo_path: Path, task_id: str, authorization_ref: str,
               capacity_class: str = "STANDARD",
               required_slots: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    root = {"identity": dict(identity_value), "task_id": task_id,
            "host_session_ref": ref(host_session_id),
            "repo_path": str(repo_path.resolve()), "capacity_class": capacity_class,
            "authorization_ref": authorization_ref,
            "required_slots": [dict(slot) for slot in (required_slots or [])],
            "policy_digest": "sha256:" + POLICY_SHA256}
    _root(root)
    require_external_state(path.resolve(), repo_path.resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        if events:
            state = replay(events)
            if state["root"] != root:
                fail("G6_ROOT_INITIALIZATION_CONFLICT")
            return state
        capacity = policy()["budget_templates"][capacity_class]
        required = sum(_slot_cost(slot) for slot in root["required_slots"])
        if required > capacity["units"] or len(root["required_slots"]) > capacity["attempts"]:
            fail("G6_REQUIRED_WORK_EXCEEDS_CAPACITY")
        return _append(path, [], "ROOT_INITIALIZED", root)


def prepare(path: Path, *, facts: Mapping[str, Any], capability: Mapping[str, Any],
            gates: list[Mapping[str, Any]], agent_type: str, task_name: str,
            message: str, decision_time: str, adjustment: Mapping[str, Any] | None = None,
            explicit_user_profile: str | None = None, depth: int = 0) -> dict[str, Any]:
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        root = state["root"]
        if facts["identity"] != root["identity"] or facts["task_id"] != root["task_id"]:
            fail("G6_PREPARE_PROJECT_CONFLICT")
        item = facts["work_item_id"]
        if any(p["task_name"] == task_name and
               (pid in state["reservations"] or
                parse_iso(decision_time) < parse_iso(p["expires_at"]))
               for pid, p in state["permits"].items()):
            fail("G6_TASK_NAME_REUSE")
        if any(p["work_item_id"] == item and pid in state["reservations"]
               and pid not in state["terminals"]
               and state["receipts"].get(pid, {}).get("disposition") != "not_started"
               for pid, p in state["permits"].items()):
            fail("G6_WORK_ITEM_ALREADY_INFLIGHT")
        # 中文：必需步骤只能消费自身允许的能力档位；预留金额不能代替能力约束。
        # English: Required work must use its allowed profiles; a quota hold is not a capability constraint.
        slot = next((slot for slot in root["required_slots"] if slot["work_item_id"] == item), None)
        if slot is not None:
            allowed = slot["allowed_profiles"] or [slot["baseline_profile"]]
            available = capability.get("available_profiles")
            capability = {**capability, "available_profiles":
                          [name for name in allowed if available is None or name in available]}
        work = state.get("review_work", {}).get(item)
        if work is not None:
            if item in state.get("closed_review_work", {}):
                fail("G6_REVIEW_WORK_CLOSED")
            if agent_type != work["agent_type"]:
                fail("G6_REVIEW_WORK_ROLE_CONFLICT")
        funding_id = _select_funding(state, item, depth)
        decision = decision_for_work(state, facts=facts, funding_id=funding_id, depth=depth,
                          capability=capability, gates=gates, agent_type=agent_type,
                          task_name=task_name, message=message, decision_time=decision_time,
                          adjustment=adjustment, explicit_user_profile=explicit_user_profile)
        if decision["exact_tool_parameters"] is None:
            return {"decision": decision, "permit_id": None}
        selected = decision["approved_profile"]
        preferred = decision["preferred_profile"]
        semantic_upward = (adjustment and adjustment.get("source") == "model_semantic"
                           and selected == adjustment.get("requested_profile"))
        registered_upward = work is not None and adjustment is None and explicit_user_profile is None
        upward = bool(funding_id == "base" and (semantic_upward or registered_upward)
                      and is_upward_adjustment(preferred, selected))
        permit_id = "G6P_" + secrets.token_hex(16)
        permit = {"permit_id": permit_id, "decision_ref": decision["decision_ref"],
                  "work_item_id": item, "task_name": task_name, "agent_type": agent_type,
                  "model": decision["exact_tool_parameters"]["model"],
                  "reasoning_effort": decision["exact_tool_parameters"]["reasoning_effort"],
                  "message_sha256": hashlib.sha256(message.encode("utf-8")).hexdigest(),
                  "planning_units": decision["planning_units"], "prepared_at": decision_time,
                  "expires_at": decision["expires_at"], "facts": dict(facts),
                  "capability": dict(capability), "gates": [dict(gate) for gate in gates],
                  "adjustment": dict(adjustment) if adjustment else None,
                  "explicit_user_profile": explicit_user_profile, "decision_time": decision_time,
                  "approved_profile": selected, "upward_adjustment": upward, "depth": depth}
        if state.get("protocol_version", 1) >= 2:
            permit["funding_id"] = funding_id
        _append(path, events, "PREPARED", permit)
        return {"decision": decision, "permit_id": permit_id}


def approve_and_reserve(path: Path, *, permit_id: str, host_call_id: str,
                        session_id: str, cwd: Path, args: Mapping[str, Any], now: str,
                        depth: int = 0) -> dict[str, Any]:
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        root = state["root"]
        if root["host_session_ref"] != ref(session_id) or not same_path(Path(root["repo_path"]), cwd):
            fail("G6_HOST_IDENTITY_CONFLICT")
        permit = state["permits"].get(permit_id)
        if permit is None:
            fail("G6_PERMIT_UNKNOWN")
        if permit["depth"] != depth:
            fail("G6_PERMIT_DEPTH_MISMATCH")
        exact(dict(args), {"task_name", "agent_type", "model", "reasoning_effort",
                           "fork_turns", "message"}, "G6_TOOL_FIELDS")
        if (args["task_name"] != permit["task_name"] or args["agent_type"] != permit["agent_type"]
                or args["model"] != permit["model"]
                or args["reasoning_effort"] != permit["reasoning_effort"]
                or args["fork_turns"] != "none"
                or not isinstance(args["message"], str)
                or hashlib.sha256(args["message"].encode("utf-8")).hexdigest()
                != permit["message_sha256"]):
            fail("G6_TOOL_PARAMETERS_MISMATCH")
        if parse_iso(now) < parse_iso(permit["prepared_at"]) or parse_iso(now) >= parse_iso(permit["expires_at"]):
            fail("G6_PERMIT_EXPIRED")
        call_ref = ref(host_call_id)
        if permit_id in state["reservations"]:
            if state["reservations"][permit_id]["host_call_ref"] == call_ref:
                return {"permit_id": permit_id, "host_call_ref": call_ref, "idempotent": True}
            fail("G6_PERMIT_REPLAY")
        if call_ref in state["host_calls"]:
            fail("G6_HOST_CALL_REPLAY")
        original_event_index = next((i for i, event in enumerate(events)
                                     if event["event_type"] == "PREPARED"
                                     and event["data"]["permit_id"] == permit_id), None)
        if original_event_index is None or original_event_index < 1:
            fail("G6_PERMIT_ORIGIN_MISSING")
        original_state = replay(events[:original_event_index])
        original = decision_for_work(original_state, facts=permit["facts"], depth=depth,
            funding_id=permit.get("funding_id", "base"),
            capability=permit["capability"], gates=permit["gates"],
            agent_type=permit["agent_type"], task_name=permit["task_name"],
            message=args["message"], decision_time=permit["decision_time"],
            adjustment=permit["adjustment"],
            explicit_user_profile=permit["explicit_user_profile"])
        if (original["decision_ref"] != permit["decision_ref"]
                or original["approved_profile"] != permit["approved_profile"]):
            fail("G6_PERMIT_ORIGIN_CHANGED")
        # 中文：以最新账本重新计算；决策变化需要新许可，Hook 不静默提高或放宽旧许可。
        # English: Recompute from the newest ledger.  A changed decision requires a new
        # permit; the Hook never silently upgrades or relaxes the old one.
        decision = decision_for_work(state, facts=permit["facts"], depth=depth,
            funding_id=permit.get("funding_id", "base"),
            capability=permit["capability"], gates=permit["gates"],
            agent_type=permit["agent_type"], task_name=permit["task_name"],
            message=args["message"], decision_time=permit["decision_time"],
            adjustment=permit["adjustment"],
            explicit_user_profile=permit["explicit_user_profile"])
        if decision["approved_profile"] != permit["approved_profile"]:
            fail("G6_PERMIT_STALE_RECOMPUTE_REQUIRED")
        reservation = {"permit_id": permit_id, "host_call_ref": call_ref, "reserved_at": now}
        if state.get("protocol_version", 1) >= 2:
            reservation["funding_id"] = permit.get("funding_id", "base")
        updated = _append(path, events, "RESERVED", reservation)
        return {"permit_id": permit_id, "host_call_ref": call_ref,
                "ledger_head": updated["head_hash"], "idempotent": False}


def record_native_completed(path: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    """中文：仅由已核验父调用与完整子转录的恢复入口使用。
    English: Called only after the recovery adapter verifies the parent call and complete child transcript.
    """
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        for event in events:
            if event["event_type"] == "NATIVE_COMPLETED_RECOVERED" and event["data"]["permit_id"] == data["permit_id"]:
                if event["data"] != data:
                    fail("G6_RECOVERED_COMPLETION_CHANGED")
                return {"permit_id": data["permit_id"], "idempotent": True}
        _append(path, events, "NATIVE_COMPLETED_RECOVERED", data)
        return {"permit_id": data["permit_id"], "idempotent": False}


def record_receipt(path: Path, *, host_call_id: str, disposition: str,
                   agent_path: str | None, proof_ref: str) -> dict[str, Any]:
    return _record_receipt(path, call_ref=ref(host_call_id), disposition=disposition,
                           agent_path=agent_path, proof_ref=proof_ref)


def record_bound_receipt(path: Path, *, host_call_ref: str, session_id: str, cwd: Path,
                         agent_path: str, proof_ref: str) -> dict[str, Any]:
    """中文：仅在调用者验证原生子任务头后补记已预占调用的创建事实。

    English: Reconcile creation for a reserved call after the caller verifies
    its native child header; never creates a reservation or changes capacity.
    """
    sha(host_call_ref)
    return _record_receipt(path, call_ref=host_call_ref, disposition="created",
                           agent_path=agent_path, proof_ref=proof_ref,
                           binding=(session_id, cwd))


def _record_receipt(path: Path, *, call_ref: str, disposition: str,
                    agent_path: str | None, proof_ref: str,
                    binding: tuple[str, Path] | None = None) -> dict[str, Any]:
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        if binding is not None and (state["root"]["host_session_ref"] != ref(binding[0])
                or not same_path(Path(state["root"]["repo_path"]), binding[1])):
            fail("G6_HOST_IDENTITY_CONFLICT")
        permit_id = state["host_calls"].get(call_ref)
        if permit_id is None:
            fail("G6_RECEIPT_CALL_UNKNOWN")
        receipt = {"permit_id": permit_id, "disposition": disposition,
                   "agent_ref": ref(agent_path) if agent_path else None,
                   "proof_ref": proof_ref}
        if permit_id in state["receipts"]:
            if state["receipts"][permit_id] != receipt:
                fail("G6_RECEIPT_CHANGED")
            return {"permit_id": permit_id, "idempotent": True}
        _append(path, events, "HOST_RECEIPT", receipt)
        return {"permit_id": permit_id, "idempotent": False}


def record_terminal(path: Path, *, agent_path: str, outcome: str,
                    proof_ref: str, permit_id: str | None = None) -> dict[str, Any]:
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        agent_ref = ref(agent_path)
        matches = [pid for pid, receipt in state["receipts"].items()
                   if receipt["disposition"] == "created" and receipt["agent_ref"] == agent_ref]
        if permit_id is not None:
            matches = [pid for pid in matches if pid == permit_id]
        else:
            active = [pid for pid in matches if pid not in state["terminals"]]
            if active:
                matches = active
        if len(matches) != 1:
            fail("G6_TERMINAL_AGENT_UNKNOWN")
        terminal = {"permit_id": matches[0], "agent_ref": agent_ref,
                    "outcome": outcome, "proof_ref": proof_ref}
        if matches[0] in state["terminals"]:
            if state["terminals"][matches[0]] != terminal:
                fail("G6_TERMINAL_CHANGED")
            return {"permit_id": matches[0], "idempotent": True}
        _append(path, events, "TERMINAL", terminal)
        return {"permit_id": matches[0], "idempotent": False}
