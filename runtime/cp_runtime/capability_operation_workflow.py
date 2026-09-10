"""中文：Operation v2 的证据工作流；只消费 Hook 已创建的 operation_ref。

English: Evidence workflow for Operation v2; consumes only Hook-created references.
"""
from __future__ import annotations

import copy
import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from .atomic_io import native_path
from .capability_gate import TASK_LIMIT, _digest, _read, _write
from .capability_index import ReadBudget, SOURCE_SUFFIXES, git_baseline, invalidate, query, scan
from .capability_operation import CapabilityOperation
from .capability_store import (
    CapabilityError, bounded_read, fields, hash_field, relative_path, require,
    safe_path, text_field,
)
from .common import canonical_json
from .patch_intent import MAX_FILE_BYTES, revalidate_intent

DECISIONS = {"reuse", "extend", "extract", "independent", "unused"}
MAX_RECEIPTS = 32


def _index_digest(operation: CapabilityOperation) -> str | None:
    store = operation.policy.store
    if not native_path(store.current).exists():
        require(not native_path(store.previous).exists(), "RECOVERY_REQUIRED")
        store._guard()
        return None
    return _digest(store.read())


def _index_projection(operation: CapabilityOperation, paths: list[str]) -> str | None:
    """中文：只绑定本操作采用或变更路径的索引事实。

    English: Bind only index facts for paths changed or adopted by this operation.
    """
    store = operation.policy.store
    if not native_path(store.current).exists():
        require(not native_path(store.previous).exists(), "RECOVERY_REQUIRED")
        return None
    record = store.read()
    selected = sorted(paths)
    entries = [entry for entry in record["entries"] if entry["path"] in selected]
    return _digest({"identity": record["identity"], "paths": selected, "entries": entries})


def _file_digest(repo: Path, relative: str) -> str | None:
    relative_path(relative)
    path = safe_path(repo / relative)
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise CapabilityError("OP_SCOPE_UNREADABLE") from None
    require(stat.S_ISREG(before.st_mode), "OP_SCOPE_NOT_FILE")
    require(not stat.S_ISLNK(before.st_mode)
            and not getattr(before, "st_file_attributes", 0) & 0x400, "LINK_REJECTED")
    require(before.st_size <= MAX_FILE_BYTES, "OP_SCOPE_TOO_LARGE")
    raw = bounded_read(path, MAX_FILE_BYTES)
    try:
        after = path.lstat()
    except OSError:
        raise CapabilityError("OP_SCOPE_CHANGED") from None
    stamp = lambda value: (value.st_dev, value.st_ino, value.st_mtime_ns, value.st_size)
    require(stamp(before) == stamp(after), "OP_SCOPE_CHANGED")
    return hashlib.sha256(raw).hexdigest()


def _scope_snapshot(repo: Path, targets: list[str]) -> dict[str, Any]:
    """中文：只捕获声明目标；无关脏文件和大文件保持在范围外。

    English: Capture only declared targets; unrelated dirt and large files stay out of scope.
    """
    require(isinstance(targets, list) and 0 < len(targets) <= 64, "OP_TARGETS")
    first = git_baseline(repo)
    files = {path: _file_digest(repo, path) for path in targets}
    require(git_baseline(repo) == first, "OP_SCOPE_CHANGED")
    return {"schema_version": 1, "git": first, "files": files}


def _validate_snapshot(value: Any) -> None:
    require(isinstance(value, dict), "OP_RECEIPT_INVALID")
    fields(value, {"schema_version", "git", "files"})
    require(value["schema_version"] == 1 and isinstance(value["git"], dict)
            and set(value["git"]) == {"head", "branch"}, "OP_RECEIPT_INVALID")
    require(isinstance(value["files"], dict) and 0 < len(value["files"]) <= 64,
            "OP_RECEIPT_INVALID")
    for path, digest in value["files"].items():
        relative_path(path)
        if digest is not None:
            hash_field(digest)


def _scan_scopes(repo: Path, targets: list[str]) -> list[str]:
    scopes: set[str] = set()
    for relative in targets:
        target = safe_path(repo / relative)
        if target.is_file() and target.suffix.lower() in SOURCE_SUFFIXES:
            scopes.add(relative)
            continue
        parent = target.parent
        while parent != repo and not parent.exists():
            parent = parent.parent
        require(parent == repo or parent.is_relative_to(repo), "PATH_ESCAPE")
        scopes.add("." if parent == repo else parent.relative_to(repo).as_posix())
    return sorted(scopes)


def _observed(budget: ReadBudget) -> dict[str, str | None]:
    result = {path: hashlib.sha256(raw).hexdigest()
              for path, raw in budget.observed.items()}
    for path, exists in budget.context_probes.items():
        if not exists:
            result[path] = None
    return dict(sorted(result.items()))


class OperationWorkflow:
    def __init__(self, operation: CapabilityOperation):
        self.operation = operation
        self.repo = operation.policy.store.repo_path
        self.receipts = safe_path(operation.root / "receipts")

    def _put(self, kind: str, operation_ref: str, identity: dict[str, Any],
             payload: dict[str, Any]) -> str:
        value = {"schema_version": 2, "kind": kind, "operation_ref": operation_ref,
                 "identity": copy.deepcopy(identity), "payload": copy.deepcopy(payload)}
        digest = _digest(value)
        target = safe_path(self.receipts / (digest + ".json"))
        if native_path(target).exists():
            require(self._get(kind, digest, operation_ref) == payload, "OP_RECEIPT_CONFLICT")
            return digest
        if native_path(self.receipts).exists():
            with os.scandir(native_path(self.receipts)) as entries:
                require(sum(1 for _ in entries) < MAX_RECEIPTS, "OP_RECEIPT_LIMIT")
        _write(target, value, TASK_LIMIT)
        require(self._get(kind, digest, operation_ref) == payload, "OP_COMMIT_UNCERTAIN")
        return digest

    def _get(self, kind: str, digest: str, operation_ref: str) -> dict[str, Any]:
        hash_field(digest)
        value = _read(safe_path(self.receipts / (digest + ".json")), TASK_LIMIT)
        fields(value, {"schema_version", "kind", "operation_ref", "identity", "payload", "integrity"})
        require(value["schema_version"] == 2 and value["kind"] == kind
                and value["operation_ref"] == operation_ref, "OP_RECEIPT_INVALID")
        require(value["identity"] == self.operation._binding(), "OP_RECEIPT_IDENTITY")
        require(_digest({key: item for key, item in value.items() if key != "integrity"}) == digest,
                "OP_RECEIPT_HASH")
        require(isinstance(value["payload"], dict), "OP_RECEIPT_INVALID")
        return value["payload"]

    @staticmethod
    def _candidates(value: Any) -> list[dict[str, str]]:
        require(isinstance(value, list) and len(value) <= 20, "OP_CANDIDATE_LIMIT")
        result, seen = [], set()
        for candidate in value:
            require(isinstance(candidate, dict), "OP_CANDIDATE_INVALID")
            fields(candidate, {"id", "path", "freshness"})
            require(isinstance(candidate["id"], str) and candidate["id"] not in seen,
                    "OP_CANDIDATE_INVALID")
            relative_path(candidate["path"])
            require(candidate["freshness"] in {"matched", "stale", "recheck", "unknown"},
                    "OP_CANDIDATE_INVALID")
            seen.add(candidate["id"])
            result.append(dict(candidate))
        return result

    @classmethod
    def _decisions(cls, candidates: list[dict[str, str]],
                   decisions: list[dict[str, str]]) -> list[str]:
        known = {candidate["id"]: candidate for candidate in cls._candidates(candidates)}
        require(isinstance(decisions, list) and len(decisions) == len(known),
                "OP_DECISIONS_INCOMPLETE")
        seen, adopted = set(), set()
        for decision in decisions:
            require(isinstance(decision, dict), "OP_DECISIONS_INCOMPLETE")
            fields(decision, {"id", "choice", "reason"})
            require(decision["id"] in known and decision["id"] not in seen,
                    "OP_DECISIONS_INCOMPLETE")
            require(decision["choice"] in DECISIONS, "OP_DECISION_INVALID")
            text_field(decision["reason"], 200)
            require(bool(decision["reason"].strip()), "OP_DECISION_INVALID")
            seen.add(decision["id"])
            if decision["choice"] in {"reuse", "extend", "extract"}:
                adopted.add(known[decision["id"]]["path"])
        require(seen == set(known), "OP_DECISIONS_INCOMPLETE")
        return sorted(adopted)

    def prepare(self, operation_ref: str, *, term: str,
                scopes: list[str] | None = None) -> dict[str, Any]:
        text_field(term, 256)
        require(bool(term.strip()), "OP_TERM_REQUIRED")
        state = self.operation.check(operation_ref)
        require(state["state"] == "PREPARING", "OP_NOT_PREPARING")
        intent = state["prestate"]
        require(state["intent_digest"] == state["prestate_digest"], "OP_INTENT_MISMATCH")
        require(intent.get("target_paths") == state["targets"], "OP_TARGETS_MISMATCH")
        if scopes is not None:
            require(sorted(scopes) == state["targets"], "OP_TARGETS_MISMATCH")
        revalidate_intent(intent, self.repo)
        start = _scope_snapshot(self.repo, state["targets"])

        observed: dict[str, str | None] = {}
        query_budget = ReadBudget(self.repo)
        result = query(self.operation.policy.store, term, _budget=query_budget)
        observed.update(_observed(query_budget))
        initial_scan = False
        if (result.get("reason") == "INDEX_MISSING"
                or not result.get("coverage", {}).get("complete", False)):
            scan_budget = ReadBudget(self.repo)
            scanned = scan(self.operation.policy.store, _scan_scopes(self.repo, state["targets"]),
                           _budget=scan_budget)
            observed.update(_observed(scan_budget))
            require(scanned["coverage"]["complete"], "OP_PARTIAL_COVERAGE")
            initial_scan = result.get("reason") == "INDEX_MISSING"
            query_budget = ReadBudget(self.repo)
            result = query(self.operation.policy.store, term, _budget=query_budget)
            observed.update(_observed(query_budget))
        candidates = self._candidates([
            {key: candidate[key] for key in ("id", "path", "freshness")}
            for candidate in result.get("candidates", [])
        ])
        revalidate_intent(intent, self.repo)
        require(_scope_snapshot(self.repo, state["targets"]) == start, "OP_SCOPE_CHANGED")
        payload = {
            "snapshot": start,
            "targets": list(state["targets"]),
            "intent_digest": state["intent_digest"],
            "prestate_digest": state["prestate_digest"],
            "observed": dict(sorted(observed.items())),
            "candidates": candidates,
            "term": term,
            "initial_scan_completed": initial_scan,
            "index_sha256": _index_digest(self.operation),
        }
        receipt = self._put("prepare", operation_ref, state["identity"], payload)
        ready = self.operation.prepare_ready(
            operation_ref, intent=intent, targets=state["targets"], prestate=intent,
            prepare_sha256=receipt,
        )
        return {"state": ready, "required_decisions": candidates,
                "semantic_reuse_approved": False}

    def finish(self, operation_ref: str, *, tool_use_id: str,
               decisions: list[dict[str, str]]) -> dict[str, Any]:
        state = self.operation.check(operation_ref)
        require(state["state"] == "RESULT_PENDING", "OP_RESULT_PENDING_REQUIRED")
        require(state["posttool"]["tool_use_id"] == tool_use_id, "OP_POSTTOOL_REQUIRED")
        prepare_sha = state["evidence"]["prepare_sha256"]
        require(prepare_sha is not None, "OP_PREPARE_REQUIRED")
        prepared = self._get("prepare", prepare_sha, operation_ref)
        _validate_snapshot(prepared["snapshot"])
        adopted = self._decisions(prepared["candidates"], decisions)
        current = _scope_snapshot(self.repo, state["targets"])
        require(current["git"] == prepared["snapshot"]["git"], "OP_SCOPE_CHANGED")
        changed = sorted(path for path in state["targets"]
                         if current["files"][path] != prepared["snapshot"]["files"][path])
        require(bool(changed), "OP_NO_CHANGE")

        before_index = self.operation.check(operation_ref)
        require(before_index["state"] == "RESULT_PENDING"
                and before_index["revision"] == state["revision"], "OP_REVISION_CONFLICT")

        store = self.operation.policy.store
        # 中文：索引维护是独立、幂等的定位元数据更新，不是 Operation 许可或业务副作用。
        # 取消若在维护期间胜出，后续复核阻止 finish 回执和 VERIFIED；已完成的索引刷新保留。
        # English: Index maintenance is independent idempotent locator metadata, not permission.
        # A cancellation during maintenance prevents the finish receipt/VERIFIED; completed refreshes remain.
        if native_path(store.current).exists():
            record = store.read()
            invalidate(store, changed, record["revision"])
            scan_scopes = sorted({path for path in changed + adopted
                                  if Path(path).suffix.lower() in SOURCE_SUFFIXES})
            if scan_scopes:
                scan(store, scan_scopes)
            refreshed = store.read()
            for entry in refreshed["entries"]:
                if entry["path"] in adopted and entry["lifecycle"] != "removed":
                    require(entry["freshness"] == "matched", "OP_ADOPTED_STALE")
        after_index = self.operation.check(operation_ref)
        require(after_index["state"] == "RESULT_PENDING"
                and after_index["revision"] == state["revision"], "OP_REVISION_CONFLICT")
        payload = {
            "snapshot": current,
            "changed_paths": changed,
            "decisions": copy.deepcopy(decisions),
            "decisions_sha256": hashlib.sha256(canonical_json(decisions).encode("utf-8")).hexdigest(),
            "prepare_sha256": prepare_sha,
            "posttool_sha256": state["posttool"]["response_sha256"],
            "index_paths": sorted(set(changed) | set(adopted)),
            "index_sha256": _index_projection(
                self.operation, sorted(set(changed) | set(adopted)),
            ),
        }
        def persist_evidence() -> tuple[str, str]:
            receipt = self._put("finish", operation_ref, state["identity"], payload)
            return receipt, receipt

        verified = self.operation.finish_with_factory(
            operation_ref, tool_use_id, evidence_factory=persist_evidence,
        )
        return {"state": verified, "changed_paths": changed,
                "semantic_reuse_approved": False}

    def check(self, operation_ref: str) -> dict[str, Any]:
        state = self.operation.check(operation_ref)
        if state["state"] != "VERIFIED":
            return {"state": state, "valid": False, "semantic_reuse_approved": False}
        try:
            finish_sha = state["evidence"]["finish_sha256"]
            prepare_sha = state["evidence"]["prepare_sha256"]
            require(finish_sha is not None and prepare_sha is not None, "OP_RECEIPT_INVALID")
            prepared = self._get("prepare", prepare_sha, operation_ref)
            finished = self._get("finish", finish_sha, operation_ref)
            _validate_snapshot(prepared["snapshot"])
            _validate_snapshot(finished["snapshot"])
            self._decisions(prepared["candidates"], finished["decisions"])
            require(finished["prepare_sha256"] == prepare_sha
                    and finished["posttool_sha256"] == state["posttool"]["response_sha256"],
                    "OP_RECEIPT_INVALID")
            require(hashlib.sha256(canonical_json(finished["decisions"]).encode("utf-8")).hexdigest()
                    == finished["decisions_sha256"], "OP_RECEIPT_INVALID")
            require(isinstance(finished["index_paths"], list)
                    and len(finished["index_paths"]) <= 128
                    and finished["index_paths"] == sorted(set(finished["index_paths"])),
                    "OP_RECEIPT_INVALID")
            for path in finished["index_paths"]:
                relative_path(path)
            current = _scope_snapshot(self.repo, state["targets"])
            require(current == finished["snapshot"]
                    and _index_projection(self.operation, finished["index_paths"])
                    == finished["index_sha256"],
                    "OP_EVIDENCE_STALE")
            require(self.operation.check(operation_ref) == state, "OP_REVISION_CONFLICT")
            return {"state": state, "valid": True, "semantic_reuse_approved": False}
        except CapabilityError as exc:
            invalid = self.operation.invalidate_completion(operation_ref, str(exc))
            return {"state": invalid, "valid": False, "semantic_reuse_approved": False}

    def cancel(self, operation_ref: str, reason: str = "CANCELLED") -> dict[str, Any]:
        return {"state": self.operation.cancel(operation_ref, reason),
                "semantic_reuse_approved": False}
