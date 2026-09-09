"""中文：可选门禁的身份绑定配置与原子任务状态；不独立批准复用。

English: Identity-bound optional gate policy and atomic task state; never approve reuse alone.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .atomic_io import native_path

from .capability_store import (
    CapabilityError, CapabilityStore, bounded_read, fields, hash_field, integer,
    require, safe_path, unique_json_object,
)
from .common import (
    RuntimeContractError, atomic_write_bytes, canonical_json, require_external_state,
    resolve_codex_home, seal_record, validate_identifier, verify_record,
)
from .event_v3 import OwnerTokenLock

POLICY_LIMIT = 16 * 1024
TASK_LIMIT = 256 * 1024
ACTIVE = {"NEW", "PREPARED", "REPAIR_REQUESTED"}
TERMINAL = {"PASS", "PARTIAL", "BLOCKED", "FAILED", "CANCELLED", "NO_CHANGE"}
REASONS = {
    "NEEDS_PREPARE", "NEEDS_FINISH", "STALE_ADOPTED", "EVIDENCE_STALE",
    "STOP_REPLAY", "REPAIR_LIMIT", "CANCELLED", "PARTIAL_COVERAGE",
    "BASELINE_CHANGED", "OUTSIDE_SCOPE", "VALIDATION_FAILED", "INITIAL_SCAN_NOT_PROVEN",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def worktree_key(repo: Path) -> str:
    return hashlib.sha256(os.path.normcase(str(safe_path(repo))).encode("utf-8")).hexdigest()


def _read(path: Path, limit: int) -> dict[str, Any]:
    try:
        value = json.loads(bounded_read(native_path(path), limit), object_pairs_hook=unique_json_object)
        require(isinstance(value, dict), "GATE_SCHEMA")
        fields(value.get("integrity"), {"algorithm", "sha256"})
        verify_record(value, "CapabilityGate")
        return value
    except (ValueError, UnicodeError, RecursionError, RuntimeContractError):
        raise CapabilityError("GATE_RECORD_INVALID") from None


def _write(path: Path, value: dict[str, Any], limit: int) -> dict[str, Any]:
    sealed = seal_record(value)
    raw = (canonical_json(sealed) + "\n").encode("utf-8")
    require(len(raw) <= limit, "GATE_RECORD_LIMIT")
    safe_path(path)
    try:
        atomic_write_bytes(native_path(path), raw)
        require(bounded_read(native_path(path), limit) == raw, "GATE_COMMIT_UNCERTAIN")
    except (OSError, RuntimeContractError):
        raise CapabilityError("GATE_COMMIT_UNCERTAIN") from None
    return sealed


def _reason_codes(reasons: list[str]) -> None:
    require(isinstance(reasons, list) and len(reasons) <= 20, "GATE_REASONS")
    require(all(isinstance(code, str) and code in REASONS for code in reasons), "GATE_REASONS")
    require(len(set(reasons)) == len(reasons), "GATE_REASONS")


class GatePolicy:
    """中文：只管理显式策略，不自动创建索引或修改 Profile。

    English: Manage explicit policy without creating an index or modifying a Profile.
    """

    def __init__(self, store: CapabilityStore, config_root: Path | None = None):
        self.store = store
        require(config_root is None or config_root.is_absolute(), "GATE_ROOT_INVALID")
        self.root = safe_path(config_root or resolve_codex_home() / "capability-gates")
        require_external_state(self.root, store.repo_path)
        self.path = self.root / (worktree_key(store.repo_path) + ".json")
        self.previous = self.path.with_suffix(".previous.json")
        self.state_root = safe_path(store.profile_path.parent / "capability-gate" / store.identity["worktree_id"])
        require_external_state(self.state_root, store.repo_path)

    def _paths(self) -> None:
        for path in (self.path, self.previous, self.state_root, Path(str(self.path) + ".lock")):
            safe_path(path)

    def _validate(self, value: dict[str, Any]) -> None:
        fields(value, {"schema_version", "revision", "enabled", "identity", "integrity"})
        require(type(value["schema_version"]) is int and value["schema_version"] == 1, "GATE_SCHEMA")
        integer(value["revision"], 2**63 - 1)
        require(type(value["enabled"]) is bool, "GATE_SCHEMA")
        require(value["identity"] == self.store.identity, "GATE_IDENTITY_MISMATCH")

    def read(self) -> dict[str, Any] | None:
        self._paths()
        self.store._guard()
        if not native_path(self.path).exists():
            require(not native_path(self.previous).exists(), "GATE_POLICY_MISSING")
            return None
        value = _read(self.path, POLICY_LIMIT)
        self._validate(value)
        self.store._guard()
        return value

    def set_enabled(self, enabled: bool, expected_revision: int | None) -> dict[str, Any]:
        require(type(enabled) is bool, "GATE_SCHEMA")
        if expected_revision is not None:
            integer(expected_revision, 2**63 - 2)
        self._paths()
        with OwnerTokenLock(self.path):
            current = self.read()
            require((current is None and expected_revision is None)
                    or (current is not None and current["revision"] == expected_revision), "GATE_REVISION_CONFLICT")
            if current is not None and current["enabled"] == enabled:
                return current
            require(current is not None or enabled, "GATE_POLICY_MISSING")
            value = {"schema_version": 1, "revision": current["revision"] + 1 if current else 0,
                     "enabled": enabled, "identity": copy.deepcopy(self.store.identity)}
            if current:
                _write(self.previous, current, POLICY_LIMIT)
            result = _write(self.path, value, POLICY_LIMIT)
            self.store._guard()
            return result


class GateTask:
    """中文：只提供状态事务；调用方仍须核实 manifest 和完成证据。

    English: Supply state transactions; callers must verify manifests and completion evidence.
    """

    def __init__(self, policy: GatePolicy, session_id: str, turn_id: str):
        self.policy = policy
        try:
            self.session_id = validate_identifier(session_id, "session")
            self.turn_id = validate_identifier(turn_id, "turn")
        except (RuntimeContractError, AttributeError):
            raise CapabilityError("GATE_HOST_IDENTITY_MISSING") from None
        record = policy.read()
        require(record is not None and record["enabled"], "GATE_NOT_ENABLED")
        self.policy_sha256 = _digest(record)
        key = _digest([self.policy_sha256, self.session_id, self.turn_id])
        self.path = policy.state_root / key / "task.json"
        self.identity = {"policy_sha256": self.policy_sha256, "project": copy.deepcopy(policy.store.identity),
                         "session_id": self.session_id, "turn_id": self.turn_id}

    def _guard(self) -> None:
        safe_path(self.path)
        safe_path(Path(str(self.path) + ".lock"))
        current = self.policy.read()
        require(current is not None and current["enabled"] and _digest(current) == self.policy_sha256,
                "GATE_POLICY_CHANGED")

    def _validate(self, value: dict[str, Any]) -> None:
        fields(value, {"schema_version", "revision", "identity", "phase", "progress_revision",
                       "repair_count", "last_stop_key", "evidence", "reason_codes", "integrity"})
        require(type(value["schema_version"]) is int and value["schema_version"] == 1, "GATE_SCHEMA")
        require(value["identity"] == self.identity, "GATE_TASK_IDENTITY_MISMATCH")
        for key in ("revision", "progress_revision"):
            integer(value[key], 2**63 - 1)
        integer(value["repair_count"], 2)
        require(isinstance(value["phase"], str) and value["phase"] in ACTIVE | TERMINAL, "GATE_SCHEMA")
        if value["last_stop_key"] is not None:
            hash_field(value["last_stop_key"])
        fields(value["evidence"], {"baseline_sha256", "prepare_sha256", "finish_sha256"})
        hash_field(value["evidence"]["baseline_sha256"])
        for key in ("prepare_sha256", "finish_sha256"):
            if value["evidence"][key] is not None:
                hash_field(value["evidence"][key])
        if value["phase"] in {"PREPARED", "PASS", "NO_CHANGE"}:
            require(value["evidence"]["prepare_sha256"] is not None, "GATE_PREPARE_REQUIRED")
        if value["phase"] in {"PASS", "NO_CHANGE", "PARTIAL"}:
            require(value["evidence"]["finish_sha256"] is not None, "GATE_FINISH_REQUIRED")
        _reason_codes(value["reason_codes"])

    def _read_locked(self) -> dict[str, Any]:
        require(native_path(self.path).exists(), "GATE_TASK_MISSING")
        value = _read(self.path, TASK_LIMIT)
        self._validate(value)
        return value

    def read(self) -> dict[str, Any]:
        self._guard()
        value = self._read_locked()
        self._guard()
        return value

    def _commit(self, old: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        if old == candidate:
            return old
        candidate["revision"] = old["revision"] + 1
        self._validate(candidate)
        self._guard()
        result = _write(self.path, candidate, TASK_LIMIT)
        self._guard()
        return result

    def create(self, baseline_sha256: str) -> dict[str, Any]:
        hash_field(baseline_sha256)
        self._guard()
        with OwnerTokenLock(self.path):
            self._guard()
            if native_path(self.path).exists():
                current = self._read_locked()
                require(current["evidence"]["baseline_sha256"] == baseline_sha256, "GATE_BASELINE_CONFLICT")
                return current
            value = seal_record({"schema_version": 1, "revision": 0, "identity": self.identity,
                "phase": "NEW", "progress_revision": 0, "repair_count": 0, "last_stop_key": None,
                "evidence": {"baseline_sha256": baseline_sha256, "prepare_sha256": None, "finish_sha256": None},
                "reason_codes": []})
            self._validate(value)
            result = _write(self.path, value, TASK_LIMIT)
            self._guard()
            return result

    def record_prepared(self, prepare_sha256: str, expected_revision: int) -> dict[str, Any]:
        hash_field(prepare_sha256)
        integer(expected_revision, 2**63 - 2)
        self._guard()
        with OwnerTokenLock(self.path):
            old = self._read_locked()
            require(old["revision"] == expected_revision, "GATE_REVISION_CONFLICT")
            require(old["phase"] in ACTIVE, "GATE_TERMINAL")
            candidate = copy.deepcopy(old)
            if candidate["evidence"]["prepare_sha256"] != prepare_sha256:
                candidate["progress_revision"] += 1
            candidate["evidence"]["prepare_sha256"] = prepare_sha256
            candidate["phase"] = "PREPARED"
            candidate["reason_codes"] = []
            return self._commit(old, candidate)

    def finish(self, phase: str, finish_sha256: str, expected_revision: int,
               reasons: list[str] | None = None) -> dict[str, Any]:
        require(isinstance(phase, str) and phase in TERMINAL - {"CANCELLED"}, "GATE_PHASE")
        hash_field(finish_sha256)
        integer(expected_revision, 2**63 - 2)
        codes = list(reasons or [])
        _reason_codes(codes)
        self._guard()
        with OwnerTokenLock(self.path):
            old = self._read_locked()
            require(old["revision"] == expected_revision, "GATE_REVISION_CONFLICT")
            if old["phase"] in TERMINAL:
                require(old["phase"] == phase and old["evidence"]["finish_sha256"] == finish_sha256
                        and old["reason_codes"] == codes, "GATE_TERMINAL")
                return old
            candidate = copy.deepcopy(old)
            candidate["phase"] = phase
            candidate["evidence"]["finish_sha256"] = finish_sha256
            candidate["reason_codes"] = codes
            return self._commit(old, candidate)

    def cancel(self) -> dict[str, Any]:
        self._guard()
        with OwnerTokenLock(self.path):
            old = self._read_locked()
            if old["phase"] == "CANCELLED":
                return old
            candidate = copy.deepcopy(old)
            candidate["phase"] = "CANCELLED"
            candidate["reason_codes"] = ["CANCELLED"]
            return self._commit(old, candidate)

    def before_write(self, *, has_scope: bool = True) -> dict[str, Any]:
        """中文：先使旧完成回执失效，再允许受控写；取消和失败终态不可恢复。

        English: Invalidate prior completion before controlled writes; never revive cancelled/failed work.
        """
        require(type(has_scope) is bool, "GATE_SCHEMA")
        self._guard()
        with OwnerTokenLock(self.path):
            old = self._read_locked()
            candidate = copy.deepcopy(old)
            if old["phase"] in {"PASS", "NO_CHANGE"}:
                candidate["phase"] = "PREPARED"
                candidate["evidence"]["finish_sha256"] = None
                candidate["progress_revision"] += 1
                candidate["reason_codes"] = []
            elif old["phase"] not in ACTIVE:
                return {"allowed": False, "state": old}
            if not has_scope:
                candidate["evidence"]["prepare_sha256"] = None
                candidate["phase"] = "NEW"
            allowed = candidate["evidence"]["prepare_sha256"] is not None
            if not allowed:
                candidate["reason_codes"] = ["NEEDS_PREPARE"]
            return {"allowed": allowed, "state": self._commit(old, candidate)}

    def invalidate_completion(self, reason: str = "EVIDENCE_STALE") -> dict[str, Any]:
        require(reason in {"EVIDENCE_STALE", "INITIAL_SCAN_NOT_PROVEN"}, "GATE_REASONS")
        self._guard()
        with OwnerTokenLock(self.path):
            old = self._read_locked()
            if old["phase"] not in {"PASS", "NO_CHANGE"}:
                return old
            candidate = copy.deepcopy(old)
            candidate["phase"] = "BLOCKED"
            candidate["reason_codes"] = [reason]
            return self._commit(old, candidate)

    def request_repair(self, stop_hook_active: bool, reasons: list[str]) -> dict[str, Any]:
        require(type(stop_hook_active) is bool, "GATE_STOP_IDENTITY")
        _reason_codes(reasons)
        require(bool(reasons) and set(reasons) <= {"NEEDS_PREPARE", "NEEDS_FINISH", "STALE_ADOPTED"}, "GATE_NOT_REPAIRABLE")
        self._guard()
        with OwnerTokenLock(self.path):
            old = self._read_locked()
            if old["phase"] in TERMINAL:
                return {"action": "HALT", "state": old}
            candidate = copy.deepcopy(old)
            key = _digest([self.identity, stop_hook_active, old["progress_revision"]])
            if key == old["last_stop_key"] or old["repair_count"] == 2:
                candidate["phase"] = "BLOCKED"
                candidate["reason_codes"] = ["STOP_REPLAY" if key == old["last_stop_key"] else "REPAIR_LIMIT"]
                action = "HALT"
            else:
                candidate["phase"] = "REPAIR_REQUESTED"
                candidate["repair_count"] += 1
                candidate["last_stop_key"] = key
                candidate["reason_codes"] = list(reasons)
                action = "CONTINUE"
            # 中文：落盘和读回失败会抛出异常，绝不先返回续行决定。
            # English: Persistence/readback failure raises before any continuation decision is returned.
            return {"action": action, "state": self._commit(old, candidate)}
