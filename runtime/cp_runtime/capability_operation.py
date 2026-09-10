"""中文：Operation v2 的独立、签名状态存储。

本模块不读取或修改 ``GateTask``。所有许可状态都绑定当前策略、项目身份、
session/turn 和调用意图，并通过一次持锁读-改-写完成 claim/CAS。

English: Independent sealed Operation v2 state, isolated from GateTask and bound to
policy, project, session, turn, and intent with locked claim/CAS transitions.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .atomic_io import native_path
from .capability_gate import GatePolicy, _digest, _read, _write
from .capability_store import CapabilityError, bounded_read, fields, hash_field, relative_path, require, safe_path, unique_json_object
from .common import RuntimeContractError, canonical_json, parse_iso, seal_record, verify_record
from .event_v3 import OwnerTokenLock

OP_LIMIT = 256 * 1024
READY_TTL = timedelta(minutes=5)
STATES = {"PREPARING", "READY", "DISPATCH_GRANTED", "RESULT_PENDING", "VERIFIED",
          "DENIED", "CANCELLED", "EXPIRED", "OUTCOME_UNKNOWN"}
TERMINAL = {"VERIFIED", "DENIED", "CANCELLED", "EXPIRED", "OUTCOME_UNKNOWN"}
OP_REF = re.compile(r"^OP2-[0-9a-f]{16}-[0-9a-f]{32}$")
MAX_SCAN = 64
RESPONSE_LIMIT = 64 * 1024


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _id(value: Any, label: str) -> str:
    require(isinstance(value, str) and 1 <= len(value) <= 256 and "\x00" not in value,
            "OP_INVALID_ID")
    return value


def _copy_json(value: Any) -> Any:
    try:
        return json.loads(canonical_json(value))
    except (TypeError, ValueError, RecursionError):
        raise CapabilityError("OP_INVALID_SCHEMA") from None


def _parse_time(value: str) -> datetime:
    try:
        return parse_iso(value)
    except (ValueError, RuntimeContractError):
        raise CapabilityError("OP_INVALID_TIMESTAMP") from None

def _targets(value: Any) -> list[str]:
    require(isinstance(value, list) and len(value) <= 64, "OP_TARGETS")
    require(all(isinstance(item, str) for item in value), "OP_TARGETS")
    result = sorted(set(value))
    require(len(result) == len(value), "OP_TARGETS")
    for item in result:
        try: relative_path(item)
        except CapabilityError: raise CapabilityError("OP_TARGETS") from None
        require(len(item.encode("utf-8")) <= 1024, "OP_TARGETS")
    return result


class CapabilityOperation:
    """中文：Profile 同级 capability-operation 下的 Operation v2 存储。

    English: Operation v2 storage under capability-operation beside the Profile.
    """

    def __init__(self, policy: GatePolicy, session_id: str, turn_id: str,
                 *, now: Callable[[], datetime] | None = None):
        require(isinstance(policy, GatePolicy), "OP_POLICY_REQUIRED")
        _id(session_id, "session")
        _id(turn_id, "turn")
        self.policy = policy
        self.session_id, self.turn_id = session_id, turn_id
        self._now = now or _now
        self.identity = copy.deepcopy(policy.store.identity)
        self._refresh_policy()
        scope = _digest_json([session_id, turn_id])[:16]
        root = safe_path(policy.store.profile_path.parent / "capability-operation" /
                         self.identity["worktree_id"] / scope)
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _refresh_policy(self) -> None:
        record = self.policy.read()
        require(record is not None, "OP_POLICY_MISSING")
        self.policy_record = record
        self.policy_sha256 = _digest(record)

    def _binding(self, *, require_enabled: bool = False) -> dict[str, Any]:
        self._refresh_policy()
        if require_enabled:
            require(self.policy_record["enabled"] is True, "OP_GATE_NOT_ENABLED")
        self.policy.store._guard()
        return {"policy_sha256": self.policy_sha256, "project": copy.deepcopy(self.identity),
                "session_id": self.session_id, "turn_id": self.turn_id}

    def _path(self, ref: str) -> Path:
        require(isinstance(ref, str) and OP_REF.fullmatch(ref) is not None, "OP_INVALID_OPERATION_REF")
        return self.root / (ref + ".json")

    def _decode(self, raw: bytes, *, enforce_current: bool = False) -> dict[str, Any]:
        try:
            value = json.loads(raw, object_pairs_hook=unique_json_object)
        except (ValueError, UnicodeError, RecursionError):
            raise CapabilityError("OP_INVALID_RECORD") from None
        require(isinstance(value, dict), "OP_INVALID_RECORD")
        fields(value, {"schema_version", "revision", "identity", "operation_ref", "origin_attempt_id",
                       "dispatch_tool_use_id", "state", "intent_digest", "targets_digest", "prestate_digest",
                       "targets", "prestate", "prepared_at", "ready_expires_at", "result_deadline",
                       "posttool", "verification", "evidence", "reason", "integrity"})
        require(value["schema_version"] == 2 and type(value["revision"]) is int and value["revision"] >= 0,
                "OP_SCHEMA")
        expected = value["identity"]
        fields(expected, {"policy_sha256", "project", "session_id", "turn_id"})
        hash_field(expected["policy_sha256"])
        _id(expected["session_id"], "session_id")
        _id(expected["turn_id"], "turn_id")
        require(expected.get("project") == self.identity, "OP_IDENTITY_MISMATCH")
        if enforce_current:
            require(expected == self._binding(), "OP_POLICY_CHANGED")
        require(OP_REF.fullmatch(value["operation_ref"] or "") is not None, "OP_INVALID_OPERATION_REF")
        _id(value["origin_attempt_id"], "origin_attempt_id")
        if value["dispatch_tool_use_id"] is not None:
            _id(value["dispatch_tool_use_id"], "dispatch_tool_use_id")
        require(value["state"] in STATES, "OP_SCHEMA")
        for key in ("intent_digest", "targets_digest", "prestate_digest"):
            hash_field(value[key])
        require(isinstance(value["targets"], list) and len(value["targets"]) <= 64, "OP_TARGETS")
        for target in value["targets"]:
            try: relative_path(target)
            except CapabilityError: raise CapabilityError("OP_TARGETS") from None
            require(len(target.encode("utf-8")) <= 1024, "OP_TARGETS")
        require(value["targets"] == sorted(set(value["targets"])), "OP_TARGETS")
        require(isinstance(value["prestate"], dict), "OP_PRESTATE")
        require(value["targets_digest"] == _digest_json(value["targets"])
                and value["prestate_digest"] == _digest_json(value["prestate"]), "OP_DIGEST_MISMATCH")
        for key in ("prepared_at", "ready_expires_at", "result_deadline"):
            require(value[key] is None or isinstance(value[key], str), "OP_TIMESTAMP")
            if value[key] is not None:
                _parse_time(value[key])
        fields(value["posttool"], {"tool_use_id", "summary_code", "response_sha256", "response_bytes", "recorded_at"})
        if value["posttool"]["tool_use_id"] is not None:
            require(value["posttool"]["tool_use_id"] == value["dispatch_tool_use_id"], "OP_POSTTOOL_ID")
            _id(value["posttool"]["tool_use_id"], "tool_use_id")
            require(isinstance(value["posttool"]["summary_code"], str) and re.fullmatch(r"[A-Z0-9_]{1,64}", value["posttool"]["summary_code"]), "OP_SUMMARY")
            hash_field(value["posttool"]["response_sha256"])
            require(type(value["posttool"]["response_bytes"]) is int and 0 <= value["posttool"]["response_bytes"] <= RESPONSE_LIMIT, "OP_SUMMARY")
            require(isinstance(value["posttool"]["recorded_at"], str), "OP_TIMESTAMP")
        else:
            require(value["posttool"]["summary_code"] is None and value["posttool"]["response_sha256"] is None and
                    value["posttool"]["response_bytes"] is None and
                    value["posttool"]["recorded_at"] is None, "OP_POSTTOOL")
        fields(value["verification"], {"evidence_sha256", "verified_at"})
        if value["verification"]["evidence_sha256"] is not None:
            hash_field(value["verification"]["evidence_sha256"])
            require(isinstance(value["verification"]["verified_at"], str), "OP_TIMESTAMP")
        else:
            require(value["verification"]["verified_at"] is None, "OP_VERIFICATION")
        require(value["state"] != "VERIFIED" or value["verification"]["evidence_sha256"] is not None, "OP_VERIFICATION")
        fields(value["evidence"], {"prepare_sha256", "finish_sha256"})
        for key in ("prepare_sha256", "finish_sha256"):
            if value["evidence"][key] is not None: hash_field(value["evidence"][key])
        require(value["state"] != "VERIFIED" or all(value["evidence"][key] is not None for key in ("prepare_sha256", "finish_sha256")), "OP_VERIFICATION")
        if value["state"] == "PREPARING":
            require(value["dispatch_tool_use_id"] is None and value["prepared_at"] is None
                    and value["ready_expires_at"] is None and value["result_deadline"] is None
                    and value["evidence"]["prepare_sha256"] is None, "OP_STATE_INVARIANT")
        if value["state"] == "READY":
            require(value["dispatch_tool_use_id"] is None and value["prepared_at"] is not None
                    and value["ready_expires_at"] is not None and value["result_deadline"] is None
                    and value["evidence"]["prepare_sha256"] is not None, "OP_STATE_INVARIANT")
        if value["state"] in {"DISPATCH_GRANTED", "RESULT_PENDING", "VERIFIED"}:
            require(value["dispatch_tool_use_id"] is not None and value["result_deadline"] is not None
                    and value["evidence"]["prepare_sha256"] is not None, "OP_STATE_INVARIANT")
        if value["state"] in {"RESULT_PENDING", "VERIFIED"}:
            require(value["posttool"]["tool_use_id"] == value["dispatch_tool_use_id"], "OP_STATE_INVARIANT")
        require(value["reason"] is None or isinstance(value["reason"], str) and len(value["reason"]) <= 256, "OP_REASON")
        verify_record(value, "CapabilityOperation")
        return value

    def _read(self, ref: str) -> dict[str, Any]:
        result = self._decode(bounded_read(self._path(ref), OP_LIMIT))
        return result

    def _policy_current(self, record: dict[str, Any]) -> bool:
        try:
            return record["identity"] == self._binding()
        except (CapabilityError, RuntimeContractError):
            return False

    def _write(self, value: dict[str, Any]) -> dict[str, Any]:
        raw = (canonical_json(seal_record(value)) + "\n").encode("utf-8")
        require(len(raw) <= OP_LIMIT, "OP_RECORD_LIMIT")
        try:
            from .common import atomic_write_bytes
            atomic_write_bytes(native_path(self._path(value["operation_ref"])), raw)
            require(bounded_read(self._path(value["operation_ref"]), OP_LIMIT) == raw, "OP_COMMIT_UNCERTAIN")
        except (OSError, RuntimeContractError):
            raise CapabilityError("OP_COMMIT_UNCERTAIN") from None
        return self._decode(raw)

    def _locked(self, ref: str):
        return OwnerTokenLock(self._path(ref))

    @classmethod
    def open(cls, policy: GatePolicy, operation_ref: str, *, now: Callable[[], datetime] | None = None) -> "CapabilityOperation":
        require(isinstance(operation_ref, str) and OP_REF.fullmatch(operation_ref) is not None, "OP_INVALID_OPERATION_REF")
        locator = operation_ref.split("-")[1]
        base = safe_path(policy.store.profile_path.parent / "capability-operation" / policy.store.identity["worktree_id"] / locator)
        path = base / (operation_ref + ".json")
        raw = bounded_read(path, OP_LIMIT)
        try: value = json.loads(raw, object_pairs_hook=unique_json_object)
        except (ValueError, UnicodeError, RecursionError): raise CapabilityError("OP_INVALID_RECORD") from None
        require(isinstance(value, dict) and isinstance(value.get("identity"), dict), "OP_INVALID_RECORD")
        identity = value["identity"]
        require(identity.get("session_id") and identity.get("turn_id"), "OP_INVALID_RECORD")
        result = cls(policy, identity["session_id"], identity["turn_id"], now=now)
        require(result._path(operation_ref) == path, "OP_INVALID_OPERATION_REF")
        result._read(operation_ref)
        return result

    def _scan(self) -> list[dict[str, Any]]:
        paths = sorted(self.root.glob("OP2-*.json"))
        require(len(paths) <= MAX_SCAN, "OP_SCAN_LIMIT")
        result = []
        for path in paths:
            # 中文：损坏或未知记录一律安全失败，不能跳过后继续选择候选。
            # English: Any malformed or unknown record is a safety failure, never a skipped candidate.
            result.append(self._read(path.stem))
        return result

    def create_or_replay_origin(self, origin_attempt_id: str, intent: Any, targets: list[str],
                                prestate: dict[str, Any] | None = None) -> dict[str, Any]:
        _id(origin_attempt_id, "origin_attempt_id")
        targets = _targets(targets)
        intent, prestate = _copy_json(intent), _copy_json(prestate or {})
        binding = self._binding(require_enabled=True)
        with OwnerTokenLock(self.root / ".origin.lock"):
            for old in self._scan():
                if old["origin_attempt_id"] == origin_attempt_id and old["identity"] == binding:
                    require((old["intent_digest"], old["targets_digest"], old["prestate_digest"]) ==
                            (_digest_json(intent), _digest_json(targets), _digest_json(prestate)), "OP_ORIGIN_CONFLICT")
                    return old
            locator = _digest_json([self.session_id, self.turn_id])[:16]
            ref = "OP2-" + locator + "-" + uuid.uuid4().hex
            value = {"schema_version": 2, "revision": 0, "identity": binding, "operation_ref": ref,
                     "origin_attempt_id": origin_attempt_id, "dispatch_tool_use_id": None, "state": "PREPARING",
                     "intent_digest": _digest_json(intent), "targets_digest": _digest_json(targets),
                     "prestate_digest": _digest_json(prestate), "targets": targets, "prestate": prestate,
                     "prepared_at": None, "ready_expires_at": None, "result_deadline": None,
                     "posttool": {"tool_use_id": None, "summary_code": None, "response_sha256": None, "response_bytes": None, "recorded_at": None},
                     "verification": {"evidence_sha256": None, "verified_at": None},
                     "evidence": {"prepare_sha256": None, "finish_sha256": None},
                     "reason": None}
            return self._write(value)

    replay_origin = create_or_replay_origin

    def prepare_ready(self, operation_ref: str, *, intent: Any | None = None,
                      targets: list[str] | None = None, prestate: dict[str, Any] | None = None,
                      prepare_sha256: str | None = None,
                      now: datetime | None = None) -> dict[str, Any]:
        with self._locked(operation_ref):
            old = self._read(operation_ref)
            require(self._policy_current(old), "OP_POLICY_CHANGED")
            require(old["identity"] == self._binding(require_enabled=True), "OP_IDENTITY_MISMATCH")
            require(old["state"] == "PREPARING", "OP_NOT_PREPARING")
            hash_field(prepare_sha256 or "")
            if intent is not None: require(old["intent_digest"] == _digest_json(_copy_json(intent)), "OP_INTENT_MISMATCH")
            if targets is not None: require(old["targets_digest"] == _digest_json(_targets(targets)), "OP_TARGETS_MISMATCH")
            if prestate is not None: require(old["prestate_digest"] == _digest_json(_copy_json(prestate)), "OP_PRESTATE_MISMATCH")
            stamp = now or self._now()
            value = copy.deepcopy(old); value.update(revision=old["revision"] + 1, state="READY",
                prepared_at=_iso(stamp), ready_expires_at=_iso(stamp + READY_TTL), reason=None)
            value["evidence"]["prepare_sha256"] = prepare_sha256
            return self._write(value)

    def find_and_claim(self, *, tool_use_id: str, intent: Any, targets: list[str],
                       prestate: dict[str, Any], now: datetime | None = None) -> dict[str, Any] | None:
        _id(tool_use_id, "dispatch_tool_use_id")
        targets = _targets(targets)
        target_digest, intent_digest, pre_digest = _digest_json(targets), _digest_json(_copy_json(intent)), _digest_json(_copy_json(prestate))
        stamp = now or self._now()
        self._binding(require_enabled=True)
        candidates = []
        for old in self._scan():
            if old["identity"] != self._binding(require_enabled=True) or old["state"] != "READY": continue
            if old["prepared_at"] and stamp < _parse_time(old["prepared_at"]):
                with self._locked(old["operation_ref"]):
                    current = self._read(old["operation_ref"])
                    if current["state"] == "READY":
                        self._transition(current, "EXPIRED", "CLOCK_ROLLBACK")
                continue
            if old["ready_expires_at"] and _parse_time(old["ready_expires_at"]) <= stamp:
                with self._locked(old["operation_ref"]):
                    current = self._read(old["operation_ref"])
                    if current["state"] == "READY" and current["ready_expires_at"] and _parse_time(current["ready_expires_at"]) <= stamp:
                        self._transition(current, "EXPIRED", "READY_EXPIRED")
                continue
            if (old["intent_digest"], old["targets_digest"], old["prestate_digest"]) == (intent_digest, target_digest, pre_digest): candidates.append(old["operation_ref"])
        require(len(candidates) <= 1, "OP_MULTIPLE_READY")
        if not candidates: return None
        ref = candidates[0]
        with OwnerTokenLock(self.policy.path):
            with self._locked(ref):
                old = self._read(ref)
                require(self._policy_current(old), "OP_POLICY_CHANGED")
                require(old["identity"] == self._binding(require_enabled=True), "OP_IDENTITY_MISMATCH")
                require(old["state"] == "READY" and old["dispatch_tool_use_id"] is None, "OP_ALREADY_CLAIMED")
                require((old["intent_digest"], old["targets_digest"], old["prestate_digest"]) ==
                        (intent_digest, target_digest, pre_digest), "OP_INTENT_MISMATCH")
                require(tool_use_id != old["origin_attempt_id"], "OP_TOOL_USE_REUSE")
                value = copy.deepcopy(old); value.update(revision=old["revision"] + 1, state="DISPATCH_GRANTED", dispatch_tool_use_id=tool_use_id, result_deadline=_iso(stamp + READY_TTL))
                return self._write(value)

    def _transition(self, old: dict[str, Any], state: str, reason: str | None = None) -> dict[str, Any]:
        require(state in STATES, "OP_SCHEMA")
        value = copy.deepcopy(old); value.update(revision=old["revision"] + 1, state=state, reason=reason)
        return self._write(value)

    def record_posttool(self, operation_ref: str, tool_use_id: str, response: Any, *, summary_code: str = "OK", now: datetime | None = None) -> dict[str, Any]:
        _id(tool_use_id, "tool_use_id"); require(re.fullmatch(r"[A-Z0-9_]{1,64}", summary_code or "") is not None, "OP_SUMMARY")
        response = _copy_json(response)
        response_bytes = len(canonical_json(response).encode("utf-8")); require(response_bytes <= RESPONSE_LIMIT, "OP_SUMMARY")
        response_sha256 = _digest_json(response)
        with self._locked(operation_ref):
            old = self._read(operation_ref)
            if not self._policy_current(old):
                if old["state"] not in TERMINAL: return self._transition(old, "OUTCOME_UNKNOWN", "POLICY_CHANGED")
                return old
            require(old["dispatch_tool_use_id"] == tool_use_id, "OP_TOOL_USE_MISMATCH")
            stamp = now or self._now()
            if old["prepared_at"] is not None and stamp < _parse_time(old["prepared_at"]):
                return old if old["state"] in TERMINAL else self._transition(old, "OUTCOME_UNKNOWN", "CLOCK_ROLLBACK")
            if old["posttool"]["tool_use_id"] == tool_use_id:
                require(old["posttool"]["response_sha256"] == response_sha256 and old["posttool"]["summary_code"] == summary_code, "OP_POSTTOOL_CONFLICT"); return old
            require(old["state"] in {"DISPATCH_GRANTED", "RESULT_PENDING"}, "OP_POSTTOOL_STATE")
            require(old["result_deadline"] is not None, "OP_RESULT_DEADLINE_MISSING")
            if stamp >= _parse_time(old["result_deadline"]):
                return self._transition(old, "OUTCOME_UNKNOWN", "POST_TOOL_RECEIPT_LATE")
            value = copy.deepcopy(old); value["state"] = "RESULT_PENDING"; value["revision"] += 1
            value["result_deadline"] = _iso(stamp + READY_TTL)
            value["posttool"] = {"tool_use_id": tool_use_id, "summary_code": summary_code, "response_sha256": response_sha256, "response_bytes": response_bytes, "recorded_at": _iso(stamp)}
            return self._write(value)

    def finish(self, operation_ref: str, tool_use_id: str, *, evidence_sha256: str, finish_sha256: str | None = None, outcome: str = "VERIFIED", now: datetime | None = None) -> dict[str, Any]:
        finish_sha256 = finish_sha256 or evidence_sha256
        return self.finish_with_factory(
            operation_ref, tool_use_id,
            evidence_factory=lambda: (evidence_sha256, finish_sha256),
            outcome=outcome, now=now,
        )

    def finish_with_factory(self, operation_ref: str, tool_use_id: str, *,
                            evidence_factory: Callable[[], tuple[str, str]],
                            outcome: str = "VERIFIED",
                            now: datetime | None = None) -> dict[str, Any]:
        """中文：在策略锁与操作锁内同时落回执引用和 VERIFIED 状态。

        English: Persist the receipt reference and VERIFIED state under policy and operation locks.
        """
        require(callable(evidence_factory), "OP_EVIDENCE_FACTORY")
        with OwnerTokenLock(self.policy.path):
            with self._locked(operation_ref):
                old = self._read(operation_ref)
                require(old["dispatch_tool_use_id"] == tool_use_id, "OP_TOOL_USE_MISMATCH")
                if not self._policy_current(old):
                    return old if old["state"] in TERMINAL else self._transition(old, "OUTCOME_UNKNOWN", "POLICY_CHANGED")
                require(old["posttool"]["tool_use_id"] == tool_use_id, "OP_POSTTOOL_REQUIRED")
                require(outcome == "VERIFIED", "OP_OUTCOME")
                if old["state"] == "VERIFIED":
                    return old
                require(old["state"] == "RESULT_PENDING", "OP_FINISH_STATE")
                require(old["evidence"]["prepare_sha256"] is not None, "OP_PREPARE_EVIDENCE_REQUIRED")
                stamp = now or self._now()
                require(old["result_deadline"] is not None, "OP_RESULT_DEADLINE_MISSING")
                if old["prepared_at"] is not None and stamp < _parse_time(old["prepared_at"]):
                    return self._transition(old, "OUTCOME_UNKNOWN", "CLOCK_ROLLBACK")
                if stamp >= _parse_time(old["result_deadline"]):
                    return self._transition(old, "OUTCOME_UNKNOWN", "FINISH_DEADLINE_EXPIRED")
                evidence_sha256, finish_sha256 = evidence_factory()
                hash_field(evidence_sha256)
                hash_field(finish_sha256)
                require(self._policy_current(old), "OP_POLICY_CHANGED")
                current = self._read(operation_ref)
                require(current["revision"] == old["revision"] and current == old,
                        "OP_REVISION_CONFLICT")
                value = copy.deepcopy(old)
                value["revision"] += 1
                value["state"] = "VERIFIED"
                value["verification"] = {"evidence_sha256": evidence_sha256,
                                         "verified_at": _iso(stamp)}
                value["evidence"]["finish_sha256"] = finish_sha256
                return self._write(value)

    def check(self, operation_ref: str) -> dict[str, Any]:
        with self._locked(operation_ref):
            old = self._read(operation_ref)
            if not self._policy_current(old):
                return old if old["state"] in TERMINAL else self._transition(old, "OUTCOME_UNKNOWN", "POLICY_CHANGED")
            return old

    def invalidate_completion(self, operation_ref: str,
                              reason: str = "OP_EVIDENCE_STALE") -> dict[str, Any]:
        """中文：持久化已验证回执不再匹配当前证据的事实。

        English: Persist that a verified receipt no longer matches current evidence.
        """
        require(isinstance(reason, str) and 0 < len(reason) <= 256, "OP_REASON")
        with self._locked(operation_ref):
            old = self._read(operation_ref)
            if not self._policy_current(old):
                return (old if old["state"] == "OUTCOME_UNKNOWN"
                        else self._transition(old, "OUTCOME_UNKNOWN", "POLICY_CHANGED"))
            if old["state"] == "OUTCOME_UNKNOWN":
                return old
            require(old["state"] == "VERIFIED", "OP_FINISH_STATE")
            return self._transition(old, "OUTCOME_UNKNOWN", reason)

    def cancel(self, operation_ref: str, reason: str = "CANCELLED") -> dict[str, Any]:
        with self._locked(operation_ref):
            old = self._read(operation_ref)
            if not self._policy_current(old):
                return old if old["state"] in TERMINAL else self._transition(old, "OUTCOME_UNKNOWN", "POLICY_CHANGED")
            if old["state"] in TERMINAL: return old
            if old["state"] in {"DISPATCH_GRANTED", "RESULT_PENDING"}:
                return self._transition(old, "OUTCOME_UNKNOWN", "CANCEL_AFTER_DISPATCH")
            return self._transition(old, "CANCELLED", reason)

    def stop(self, operation_ref: str, reason: str = "STOP") -> dict[str, Any]:
        with self._locked(operation_ref):
            old = self._read(operation_ref)
            if not self._policy_current(old):
                return old if old["state"] in TERMINAL else self._transition(old, "OUTCOME_UNKNOWN", "POLICY_CHANGED")
            if old["state"] in TERMINAL: return old
            return self._transition(old, "OUTCOME_UNKNOWN", reason)

    def reconcile_missing_result(self, operation_ref: str, *, now: datetime | None = None) -> dict[str, Any]:
        with self._locked(operation_ref):
            old = self._read(operation_ref)
            if old["state"] in TERMINAL: return old
            if not self._policy_current(old):
                return self._transition(old, "OUTCOME_UNKNOWN", "POLICY_CHANGED")
            if old["state"] == "RESULT_PENDING":
                return old
            require(old["state"] == "DISPATCH_GRANTED", "OP_RESULT_STATE")
            deadline = old["result_deadline"]
            require(deadline is not None, "OP_RESULT_DEADLINE_MISSING")
            stamp = now or self._now()
            if old["prepared_at"] is not None and stamp < _parse_time(old["prepared_at"]):
                return self._transition(old, "OUTCOME_UNKNOWN", "CLOCK_ROLLBACK")
            if stamp < _parse_time(deadline): return old
            return self._transition(old, "OUTCOME_UNKNOWN", "POST_TOOL_RECEIPT_MISSING")


OperationStore = CapabilityOperation
