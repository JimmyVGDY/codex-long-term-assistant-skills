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
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES or (raw and not raw.endswith(b"\n")):
        fail("G6_LEDGER_BOUND_OR_PARTIAL")
    lines = raw.splitlines()
    if len(lines) > MAX_RECORDS:
        fail("G6_LEDGER_RECORD_LIMIT")
    try:
        return [json.loads(line, object_pairs_hook=_object, parse_constant=_constant) for line in lines]
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("G6_LEDGER_INVALID_JSON") from exc


def _event(previous: dict[str, Any] | None, kind: str, data: Mapping[str, Any]) -> dict[str, Any]:
    item = {"schema_version": SCHEMA, "sequence": 1 if previous is None else previous["sequence"] + 1,
            "event_id": "G6E_" + secrets.token_hex(16), "event_type": kind,
            "recorded_at": utc_now(), "previous_hash": ZERO_HASH if previous is None else previous["record_hash"],
            "data": dict(data)}
    item["record_hash"] = ref(item)[7:]
    return item


def _append(path: Path, events: list[dict[str, Any]], kind: str,
            data: Mapping[str, Any]) -> dict[str, Any]:
    event = _event(events[-1] if events else None, kind, data)
    if len(events) >= MAX_RECORDS:
        fail("G6_LEDGER_RECORD_LIMIT")
    if path.exists() and path.stat().st_size + len(canonical_json(event).encode("utf-8")) + 1 > MAX_BYTES:
        fail("G6_LEDGER_SIZE_LIMIT")
    updated = replay([*events, event])
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
    for sequence, event in enumerate(events, 1):
        exact(event, EVENT_FIELDS, "G6_LEDGER_EVENT_FIELDS")
        if (event.get("schema_version") != SCHEMA
                or event.get("sequence") != sequence or event.get("previous_hash") != previous
                or event.get("record_hash") != ref({k: v for k, v in event.items()
                                                    if k != "record_hash"})[7:]
                or not isinstance(event["event_id"], str)
                or not re.fullmatch(r"G6E_[0-9a-f]{32}", event["event_id"])
                or event["event_id"] in event_ids):
            fail("G6_LEDGER_CHAIN")
        event_ids.add(event["event_id"])
        parse_iso(event["recorded_at"])
        previous = event["record_hash"]
        kind, data = event["event_type"], event["data"]
        if sequence == 1:
            if kind != "ROOT_INITIALIZED":
                fail("G6_LEDGER_FIRST_EVENT")
            root = _root(data)
            state = {"root": root, "permits": {}, "host_calls": {}, "reservations": {},
                     "receipts": {}, "terminals": {}, "sequence": sequence,
                     "head_hash": previous}
            continue
        assert state is not None
        if kind == "PREPARED":
            exact(data, PREPARED_FIELDS, "G6_PREPARED_FIELDS")
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
            exact(data, RESERVED_FIELDS, "G6_RESERVED_FIELDS")
            permit_id = data["permit_id"]
            call_ref = sha(data["host_call_ref"])
            if (permit_id not in state["permits"] or permit_id in state["reservations"]
                    or call_ref in state["host_calls"]):
                fail("G6_RESERVATION_CONFLICT")
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
    with OwnerTokenLock(path, timeout=2):
        return replay(_read_events(path))


def _adjustment_origin(state: Mapping[str, Any], work_item_id: str) -> tuple[str, str]:
    # 中文：明确登记的工作谱系使用固定来源；未知谱系共享根额度，改名不能重置次数。
    # English: Registered lineage has a fixed origin; unknown lineage shares the root allowance across renames.
    slot = next((slot for slot in state["root"]["required_slots"]
                 if slot["work_item_id"] == work_item_id), None)
    return (("registered", slot.get("origin_work_item_id") or slot["work_item_id"])
            if slot is not None else ("root", state["root"]["task_id"]))


def _usage(state: Mapping[str, Any], work_item_id: str | None = None) -> dict[str, int]:
    completed_units = completed_attempts = inflight_units = inflight_attempts = 0
    active = astra_active = upward = 0
    finished_items = set()
    for permit_id, reservation in state["reservations"].items():
        permit = state["permits"][permit_id]
        receipt = state["receipts"].get(permit_id)
        terminal = state["terminals"].get(permit_id)
        units = permit["planning_units"]
        if receipt and receipt["disposition"] == "not_started":
            completed_attempts += 1
        elif terminal:
            completed_units += units
            completed_attempts += 1
            if terminal["outcome"] == "PASS":
                finished_items.add(permit["work_item_id"])
        else:
            inflight_units += units
            inflight_attempts += 1
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
    for slot in state["root"]["required_slots"]:
        item = slot["work_item_id"]
        if item in finished_items or item in pending_active_items or item == work_item_id:
            continue
        hold_units += _slot_cost(slot)
        hold_attempts += 1
    return {"completed_charged_units": completed_units,
            "completed_charged_attempts": completed_attempts,
            "inflight_reserved_units": inflight_units,
            "inflight_reserved_attempts": inflight_attempts,
            "future_required_hold_units": hold_units,
            "future_required_hold_attempts": hold_attempts,
            "active_calls": active, "astra_active": astra_active,
            "upward_adjustments_used": upward}


def snapshot(state: Mapping[str, Any], *, work_item_id: str, depth: int) -> dict[str, Any]:
    root = state["root"]
    capacity = policy()["budget_templates"][root["capacity_class"]]
    concurrency = policy()["concurrency_defaults"][root["capacity_class"]]
    return {"schema_version": "g6-budget-snapshot/1", "ledger_head": state["head_hash"],
            "capacity_class": root["capacity_class"], "capacity_units": capacity["units"],
            "capacity_attempts": capacity["attempts"],
            **_usage(state, work_item_id), "parallel_limit": concurrency["parallel"],
            "depth_limit": concurrency["depth"], "depth": depth}


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
        decision = decide(facts=facts, budget=snapshot(state, work_item_id=item, depth=depth),
                          capability=capability, gates=gates, agent_type=agent_type,
                          task_name=task_name, message=message, decision_time=decision_time,
                          adjustment=adjustment, explicit_user_profile=explicit_user_profile)
        if decision["exact_tool_parameters"] is None:
            return {"decision": decision, "permit_id": None}
        selected = decision["approved_profile"]
        preferred = decision["preferred_profile"]
        upward = bool(adjustment and adjustment.get("source") == "model_semantic"
                      and selected == adjustment.get("requested_profile")
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
        original = decide(facts=permit["facts"], budget=snapshot(
            original_state, work_item_id=permit["work_item_id"], depth=depth),
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
        decision = decide(facts=permit["facts"], budget=snapshot(
            state, work_item_id=permit["work_item_id"], depth=depth),
            capability=permit["capability"], gates=permit["gates"],
            agent_type=permit["agent_type"], task_name=permit["task_name"],
            message=args["message"], decision_time=permit["decision_time"],
            adjustment=permit["adjustment"],
            explicit_user_profile=permit["explicit_user_profile"])
        if decision["approved_profile"] != permit["approved_profile"]:
            fail("G6_PERMIT_STALE_RECOMPUTE_REQUIRED")
        updated = _append(path, events, "RESERVED", {"permit_id": permit_id,
                           "host_call_ref": call_ref, "reserved_at": now})
        return {"permit_id": permit_id, "host_call_ref": call_ref,
                "ledger_head": updated["head_hash"], "idempotent": False}


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
