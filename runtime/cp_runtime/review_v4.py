"""中文：Review State V9 / Result V6；根预算仍是唯一派发所有者。

English: V9 review projection and V6 results; the budget owns every dispatch.
"""
from __future__ import annotations

import copy
import hashlib
import secrets
from pathlib import Path
from typing import Any, Mapping

from . import budget_v4
from .common import atomic_write_json, atomic_write_bytes, read_json, repo_snapshot, utc_now, require_external_state
from .event_v2 import OwnerTokenLock
from .review_contract import ISOLATION_LEVELS, STATUSES, validate_findings
from .routing_contract import (
    POLICY_ID, RoutingError, exact, fail, hex_digest, identifier, integer,
    policy_digest, profile_spec, read_document, ref, role_for, sha, strings,
)

STATE_FILE = "review-state.json"
STATE_FIELDS = {"schema_version", "review_id", "review_state_ref", "identity", "boundary_id",
                "ledger_path", "repo_path", "isolation_level", "status", "entries", "results",
                "created_at", "updated_at", "conclusion"}
RESULT_FIELDS = {"schema_version", "result_id", "review_state_ref", "identity", "boundary_id",
                 "reviewer", "phase", "review_kind", "slot_id", "packet_sha256", "baseline_sha256",
                 "decision_ref", "permit_id", "profile_id", "policy_id", "policy_digest",
                 "qualification_ref", "gain_ref", "cost_ref", "reserved_units", "cost_basis",
                 "status", "isolation_level", "findings", "checked_scope", "unverified_items",
                 "summary", "supersedes"}


def _validate_state(value: Mapping[str, Any]) -> None:
    exact(dict(value), STATE_FIELDS, "REVIEW_V9_FIELDS")
    if value["schema_version"] != 9 or value["review_state_ref"] != ref(value["review_id"]):
        fail("REVIEW_V9_IDENTITY")
    identifier(value["review_id"]); identifier(value["boundary_id"])
    if value["isolation_level"] not in ISOLATION_LEVELS or value["status"] not in {"open", "closed"}:
        fail("REVIEW_V9_STATE")
    if (value["status"] == "open" and value["conclusion"] != "") or (value["status"] == "closed" and
            value["conclusion"] not in {"PASS", "PARTIAL", "FAILED", "CANCELLED"}):
        fail("REVIEW_V9_CONCLUSION")
    if not isinstance(value["entries"], dict) or not isinstance(value["results"], dict) \
            or len(value["entries"]) > 256 or len(value["results"]) > 256:
        fail("REVIEW_V9_LIMIT")


def initialize(directory: Path, *, ledger_path: Path, boundary_id: str,
               isolation_level: str = "logical-readonly") -> dict[str, Any]:
    state = budget_v4.read_budget(ledger_path)
    if isolation_level not in ISOLATION_LEVELS or isolation_level == "system-readonly":
        fail("REVIEW_V9_ISOLATION_PROOF_REQUIRED")
    require_external_state(directory.resolve(), Path(state["root_binding"]["repo_path"]).resolve())
    review_id = "RV9_" + secrets.token_hex(16)
    value = {
        "schema_version": 9, "review_id": review_id, "review_state_ref": ref(review_id),
        "identity": copy.deepcopy(state["identity"]), "boundary_id": identifier(boundary_id),
        "ledger_path": str(ledger_path.resolve()), "repo_path": state["root_binding"]["repo_path"],
        "isolation_level": isolation_level, "status": "open", "entries": {}, "results": {},
        "created_at": utc_now(), "updated_at": utc_now(), "conclusion": "",
    }
    directory.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(directory / STATE_FILE, timeout=2):
        if (directory / STATE_FILE).exists():
            fail("REVIEW_V9_ALREADY_EXISTS")
        atomic_write_json(directory / STATE_FILE, value, seal=True)
    return value


def read_state(directory: Path) -> dict[str, Any]:
    value = read_json(directory / STATE_FILE, verify=True, label="Review V9")
    value.pop("integrity")
    _validate_state(value)
    return value


def reconcile(directory: Path) -> dict[str, Any]:
    """中文：先锁审查投影，再读根账本；根账本不反向读取审查投影。

    English: Review lock precedes budget lock; budget never loads the projection.
    """
    state = read_state(directory)
    with OwnerTokenLock(directory / STATE_FILE, timeout=2):
        observed = read_state(directory)
        if any(observed[key] != state[key] for key in
               ("review_id", "review_state_ref", "identity", "boundary_id", "ledger_path", "repo_path")):
            fail("REVIEW_V9_PROJECTION_IDENTITY_CHANGED")
        state = observed
        authoritative = budget_v4.read_budget(Path(state["ledger_path"]))
        if authoritative["identity"] != state["identity"]:
            fail("REVIEW_V9_BUDGET_IDENTITY")
        state["entries"] = {}
        for permit_id, permit in authoritative["permits"].items():
            binding = permit["review_binding"]
            if not binding or binding["review_state_ref"] != state["review_state_ref"]:
                continue
            if binding["boundary_id"] != state["boundary_id"]:
                fail("REVIEW_V9_BOUNDARY_MISMATCH")
            entry = {"permit_id": permit_id, "slot_id": permit["slot_id"], "reviewer": binding["reviewer"],
                     "decision_ref": permit["selection"]["decision_ref"], "state": permit["status"],
                     "reservation_id": "", "result_ref": ""}
            for rid, reservation in authoritative["reservations"].items():
                if reservation["permit_id"] == permit_id:
                    entry.update(reservation_id=rid, state=reservation["state"])
                    accepted = authoritative["accepted_results"].get(rid)
                    if accepted:
                        entry["result_ref"] = accepted["result_ref"]
            state["entries"][permit_id] = entry
        owned_results = {entry["result_ref"] for entry in state["entries"].values() if entry["result_ref"]}
        state["results"] = {key: value for key, value in state["results"].items() if key in owned_results}
        for entry in state["entries"].values():
            result_ref = entry["result_ref"]
            if result_ref:
                stored = directory / "results" / (result_ref[7:] + ".json")
                if stored.is_file():
                    payload, observed_ref = read_document(stored)
                    if observed_ref != result_ref or payload.get("review_state_ref") != state["review_state_ref"]:
                        fail("REVIEW_V9_STORED_RESULT_INTEGRITY")
                    state["results"][result_ref] = {"result_path": str(stored.resolve()),
                                                   "permit_id": entry["permit_id"], "status": payload["status"]}
        state["updated_at"] = utc_now()
        atomic_write_json(directory / STATE_FILE, state, seal=True)
    return state


def prepare(directory: Path, request: Mapping[str, Any], *, dispatch_key: str, depth: int,
            snapshot_loader: budget_v4.SnapshotLoader, transition: Mapping[str, Any] | None = None) -> dict[str, Any]:
    role_for(request["scenario"]["role"])
    with OwnerTokenLock(directory / STATE_FILE, timeout=2):
        state = read_state(directory)
        if state["status"] != "open" or request["task_id"] != state["identity"]["task_id"]:
            fail("REVIEW_V9_NOT_OPEN_OR_FOREIGN_TASK")
        output = budget_v4.prepare(Path(state["ledger_path"]), request, dispatch_key=dispatch_key, depth=depth,
                                  snapshot_loader=snapshot_loader, transition=transition, review_binding={
                                      "review_state_ref": state["review_state_ref"], "boundary_id": state["boundary_id"],
                                      "reviewer": request["scenario"]["role"]})
    reconcile(directory)
    return output


def result_template(directory: Path, permit_id: str) -> dict[str, Any]:
    state = reconcile(directory)
    entry = state["entries"].get(permit_id)
    if not entry:
        fail("REVIEW_V9_PERMIT_UNKNOWN")
    ledger = budget_v4.read_budget(Path(state["ledger_path"]))
    permit = ledger["permits"][permit_id]
    if permit["review_binding"] != {"review_state_ref": state["review_state_ref"],
                                    "boundary_id": state["boundary_id"], "reviewer": permit["role"]}:
        fail("REVIEW_V9_PERMIT_OWNER_MISMATCH")
    return expected_result(ledger, permit_id, isolation_level=state["isolation_level"])


def expected_result(ledger: Mapping[str, Any], permit_id: str, *, isolation_level: str) -> dict[str, Any]:
    permit = ledger["permits"][permit_id]
    binding = permit["review_binding"]
    if not binding or isolation_level not in ISOLATION_LEVELS or isolation_level == "system-readonly":
        fail("REVIEW_V6_OWNER_OR_ISOLATION")
    request, choice = permit["request"], permit["selection"]
    phase = request["scenario"]["phase"]
    value = {
        "schema_version": 6, "result_id": "", "review_state_ref": binding["review_state_ref"],
        "identity": ledger["identity"], "boundary_id": binding["boundary_id"], "reviewer": permit["role"],
        "phase": "post" if phase == "repair" else phase, "review_kind": "repair" if phase == "repair" else "initial",
        "slot_id": permit["slot_id"], "packet_sha256": request["packet_sha256"],
        "baseline_sha256": request["baseline_sha256"], "decision_ref": choice["decision_ref"],
        "permit_id": permit_id, "profile_id": choice["approved_profile"], "policy_id": POLICY_ID,
        "policy_digest": policy_digest(), "qualification_ref": choice["qualification_ref"],
        "gain_ref": choice["gain_ref"], "cost_ref": choice["cost_ref"],
        "reserved_units": choice["reserve_units"], "cost_basis": choice["cost_basis"],
        "status": "incomplete", "isolation_level": isolation_level, "findings": [],
        "checked_scope": [], "unverified_items": [], "summary": "", "supersedes": [],
    }
    value["result_id"] = "RVR6_" + ref({key: value[key] for key in
        ("review_state_ref", "identity", "boundary_id", "reviewer", "slot_id", "decision_ref", "permit_id")})[7:]
    return value


def validate_result(value: Any, expected: Mapping[str, Any]) -> dict[str, Any]:
    exact(value, RESULT_FIELDS, "REVIEW_V6_FIELDS")
    mutable = {"status", "findings", "checked_scope", "unverified_items", "summary", "supersedes"}
    if any(value[key] != expected[key] for key in RESULT_FIELDS - mutable):
        fail("REVIEW_V6_ASSIGNMENT_MISMATCH")
    if value["status"] not in STATUSES:
        fail("REVIEW_V6_STATUS")
    for key in ("checked_scope", "unverified_items"):
        if not isinstance(value[key], list) or len(value[key]) > 256 \
                or any(not isinstance(item, str) or len(item) > 4096 for item in value[key]):
            fail("REVIEW_V6_TEXT_LIST")
    for reference in strings(value["supersedes"], "REVIEW_V6_SUPERSEDES", maximum=10):
        sha(reference)
    if not isinstance(value["summary"], str) or len(value["summary"]) > 16384:
        fail("REVIEW_V6_SUMMARY")
    if value["status"] != "incomplete" and (not value["summary"].strip() or not value["checked_scope"]
            or any(not scope.strip() for scope in value["checked_scope"])):
        fail("REVIEW_V6_COMPLETED_SCOPE_REQUIRED")
    validate_findings(value["findings"], value["status"])
    return copy.deepcopy(value)


def record_result(directory: Path, result_path: Path, *, response_ref: str) -> dict[str, Any]:
    payload, file_ref = read_document(result_path)
    expected = result_template(directory, payload.get("permit_id", ""))
    value = validate_result(payload, expected)
    state = read_state(directory)
    if state["status"] != "open":
        fail("REVIEW_V9_CLOSED")
    if value["status"] != "incomplete" and repo_snapshot(Path(state["repo_path"]))["sha256"] != value["baseline_sha256"]:
        fail("REVIEW_V6_BASELINE_STALE")
    entry = state["entries"][value["permit_id"]]
    if not entry["reservation_id"]:
        fail("REVIEW_V6_HOST_RESERVATION_REQUIRED")
    stored = directory / "results" / (file_ref[7:] + ".json")
    raw = result_path.read_bytes()
    if "sha256:" + hashlib.sha256(raw).hexdigest() != file_ref:
        fail("REVIEW_V6_RESULT_CHANGED_DURING_READ")
    if stored.is_file() and stored.read_bytes() != raw:
        fail("REVIEW_V6_IMMUTABLE_RESULT_COLLISION")
    if not stored.exists():
        atomic_write_bytes(stored, raw)
    # 中文：先提交根账本再更新投影；中断后由对账恢复，不猜造结果或再次扣费。
    # English: The ledger commit precedes projection. Reconciliation repairs a projection
    # write interruption without inventing a result or charging another attempt.
    with OwnerTokenLock(directory / STATE_FILE, timeout=2):
        state = read_state(directory)
        if state["status"] != "open":
            fail("REVIEW_V9_CLOSED")
        budget_v4.accept_result(
            Path(state["ledger_path"]), reservation_id=entry["reservation_id"], result_ref=file_ref,
            status=value["status"], response_ref=sha(response_ref), baseline_sha256=value["baseline_sha256"],
            supersedes=value["supersedes"])
        state["results"][file_ref] = {"result_path": str(stored.resolve()), "permit_id": value["permit_id"],
                                     "status": value["status"]}
        state["updated_at"] = utc_now()
        atomic_write_json(directory / STATE_FILE, state, seal=True)
    return reconcile(directory)


def close(directory: Path, *, conclusion: str) -> dict[str, Any]:
    reconcile(directory)
    if conclusion not in {"PASS", "PARTIAL", "FAILED", "CANCELLED"}:
        fail("REVIEW_V9_CONCLUSION")
    with OwnerTokenLock(directory / STATE_FILE, timeout=2):
        state = read_state(directory)
        if state["status"] == "closed":
            if state["conclusion"] != conclusion:
                fail("REVIEW_V9_CLOSE_CONFLICT")
            return state
        ledger = budget_v4.read_budget(Path(state["ledger_path"]))
        permits = {pid for pid, permit in ledger["permits"].items()
                   if permit["review_binding"].get("review_state_ref") == state["review_state_ref"]}
        owned = [attempt for attempt in ledger["reservations"].values() if attempt["permit_id"] in permits]
        if any(ledger["permits"][pid]["status"] == "PREPARED" for pid in permits) or \
                any(attempt["state"] in {"RESERVED", "STARTED"} for attempt in owned):
            fail("REVIEW_V9_ACTIVE_ATTEMPTS")
        if conclusion == "PASS":
            if not owned or any(attempt["reservation_id"] not in ledger["accepted_results"] for attempt in owned):
                fail("REVIEW_V9_INCOMPLETE_RESULTS")
            results = [ledger["accepted_results"][attempt["reservation_id"]] for attempt in owned]
            superseded = {reference for result in results for reference in result["supersedes"]}
            current_results = []
            for result in results:
                payload, result_ref = read_document(directory / "results" / (result["result_ref"][7:] + ".json"))
                attempt = ledger["reservations"][result["reservation_id"]]
                validate_result(payload, expected_result(ledger, attempt["permit_id"],
                                                         isolation_level=state["isolation_level"]))
                if result_ref != result["result_ref"] or payload["status"] != result["status"]:
                    fail("REVIEW_V9_STORED_RESULT_INTEGRITY")
                if result_ref not in superseded:
                    current_results.append(payload)
            if any(result["status"] in {"blocking", "incomplete"} and result["result_ref"] not in superseded
                   for result in results):
                fail("REVIEW_V9_UNRESOLVED_FINDINGS")
            implementation = [result for result in current_results if result["phase"] == "post"]
            current_baseline = repo_snapshot(Path(state["repo_path"]))["sha256"]
            if any(result["baseline_sha256"] != current_baseline for result in (implementation or current_results)):
                fail("REVIEW_V9_CLOSE_BASELINE_STALE")
        state["status"] = "closed"
        state["conclusion"] = conclusion
        state["updated_at"] = utc_now()
        atomic_write_json(directory / STATE_FILE, state, seal=True)
    return state
