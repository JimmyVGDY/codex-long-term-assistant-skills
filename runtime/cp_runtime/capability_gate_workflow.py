"""中文：用真实扫描、查询和文件证据推进可选门禁，不接受调用者伪造完成摘要。

English: Advance the optional gate from actual scans, queries, and file evidence, never caller hashes.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

from .atomic_io import native_path

from .capability_gate import ACTIVE, GateTask, TASK_LIMIT, _digest, _read, _write
from .capability_gate_evidence import MAX_FILES, _validate_snapshot, capture_worktree, changed_paths
from .capability_index import ReadBudget, SOURCE_SUFFIXES, invalidate, query, scan
from .capability_store import CapabilityError, fields, hash_field, relative_path, require, safe_path, text_field
from .event_v3 import OwnerTokenLock

MAX_RECEIPTS = 32


def _cold_local_only(files: dict[str, str | None], *, initial_scan_required: bool = False,
                     initial_scan_completed: bool = False, index_sha256: str | None = None) -> bool:
    """中文：无索引例外只容纳单个既有文件；不据文件数量批准业务语义。

    English: Bound the no-index exception to one existing file, without approving its semantics.
    """
    return (not initial_scan_required and not initial_scan_completed and index_sha256 is None
            and len(files) == 1 and all(digest is not None for digest in files.values()))


def _prepared_local_only(preparation: dict[str, Any]) -> bool:
    return _cold_local_only(preparation["files"], **{key: preparation[key] for key in
        ("initial_scan_required", "initial_scan_completed", "index_sha256")})


DECISIONS = {"reuse", "extend", "extract", "independent", "unused"}


def _files(value: Any) -> None:
    require(isinstance(value, dict) and len(value) <= MAX_FILES, "GATE_FILE_LIMIT")
    for path, digest in value.items():
        relative_path(path)
        if digest is not None:
            hash_field(digest)


def _observed(budget: ReadBudget) -> dict[str, str | None]:
    result = {path: budget.digest(path) for path in list(budget.observed)}
    for path, exists in budget.context_probes.items():
        require(not exists or path in result, "GATE_PARTIAL_COVERAGE")
        if not exists:
            result[path] = None
    _files(result)
    return result


class GateWorkflow:
    """中文：每次操作独立核验身份；取消或revision变化后不颁发完成状态。

    English: Revalidate identity per operation; cancellation/revision changes cannot produce completion.
    """

    def __init__(self, task: GateTask):
        self.task = task
        self.store = task.policy.store
        self.repo = self.store.repo_path
        self.receipts = safe_path(task.path.parent / "receipts")
        # 中文：长操作先串行化，索引操作结束后再进行任务CAS；不嵌套获取同一状态锁。
        # English: Serialize long operations, then CAS task state after index work; never reenter its lock.
        self.operation = OwnerTokenLock(task.path.parent / "operation")

    def _put(self, kind: str, payload: dict[str, Any]) -> str:
        self.task._guard()
        value = {"schema_version": 1, "kind": kind, "identity": self.task.identity, "payload": payload}
        digest = _digest(value)
        target = safe_path(self.receipts / (digest + ".json"))
        if native_path(target).exists():
            require(self._get(kind, digest) == payload, "GATE_RECEIPT_CONFLICT")
            return digest
        if native_path(self.receipts).exists():
            with os.scandir(native_path(self.receipts)) as entries:
                count = 0
                for entry in entries:
                    count += 1
                    require(count < MAX_RECEIPTS, "GATE_RECEIPT_LIMIT")
        _write(target, value, TASK_LIMIT)
        require(self._get(kind, digest) == payload, "GATE_COMMIT_UNCERTAIN")
        return digest

    def _get(self, kind: str, digest: str) -> dict[str, Any]:
        hash_field(digest)
        value = _read(safe_path(self.receipts / (digest + ".json")), TASK_LIMIT)
        fields(value, {"schema_version", "kind", "identity", "payload", "integrity"})
        require(type(value["schema_version"]) is int and value["schema_version"] == 1
                and value["kind"] == kind and value["identity"] == self.task.identity, "GATE_RECEIPT_IDENTITY")
        require(_digest({key: item for key, item in value.items() if key != "integrity"}) == digest,
                "GATE_RECEIPT_HASH")
        require(isinstance(value["payload"], dict), "GATE_SCHEMA")
        return value["payload"]

    def _index_digest(self) -> str | None:
        if not native_path(self.store.current).exists():
            require(not native_path(self.store.previous).exists(), "RECOVERY_REQUIRED")
            self.store._guard()
            return None
        return _digest(self.store.read())

    def begin(self) -> dict[str, Any]:
        with self.operation:
            self.task._guard()
            if native_path(self.task.path).exists():
                state = self.task.read()
                _validate_snapshot(self._get("baseline", state["evidence"]["baseline_sha256"]))
                return state
            baseline = capture_worktree(self.repo)
            return self.task.create(self._put("baseline", baseline))

    def _preparation(self, state: dict[str, Any]) -> dict[str, Any] | None:
        digest = state["evidence"]["prepare_sha256"]
        if digest is None:
            return None
        value = self._get("prepare", digest)
        fields(value, {"files", "observed", "candidates", "index_sha256", "initial_scan_required",
                       "initial_scan_completed", "scan_complete", "term", "local_only_reason"})
        _files(value["files"])
        _files(value["observed"])
        require(set(value["files"]) <= set(value["observed"]), "GATE_EVIDENCE_INCOMPLETE")
        if value["index_sha256"] is not None:
            hash_field(value["index_sha256"])
        for key in ("initial_scan_required", "initial_scan_completed", "scan_complete"):
            require(type(value[key]) is bool, "GATE_SCHEMA")
        text_field(value["term"], 256)
        text_field(value["local_only_reason"], 200)
        require(value["initial_scan_required"] or bool(value["local_only_reason"].strip()), "GATE_CLASSIFICATION_MISSING")
        require(isinstance(value["candidates"], list) and len(value["candidates"]) <= 20, "GATE_CANDIDATE_LIMIT")
        seen = set()
        for candidate in value["candidates"]:
            fields(candidate, {"id", "path", "freshness"})
            text_field(candidate["id"], 128)
            relative_path(candidate["path"])
            require(candidate["freshness"] in {"matched", "stale", "recheck", "unknown"}, "GATE_SCHEMA")
            require(candidate["id"] not in seen, "GATE_CANDIDATE_DUPLICATE")
            seen.add(candidate["id"])
        return value

    def prepare(self, paths: list[str], term: str, *, initial_scan_required: bool = True,
                local_only_reason: str = "") -> dict[str, Any]:
        require(type(initial_scan_required) is bool, "GATE_SCHEMA")
        text_field(local_only_reason, 200)
        require(initial_scan_required or bool(local_only_reason.strip()), "GATE_CLASSIFICATION_MISSING")
        require(isinstance(paths, list) and 0 < len(paths) <= MAX_FILES, "GATE_FILE_LIMIT")
        for path in paths:
            relative_path(path)
        text_field(term, 256)
        with self.operation:
            old = self.task.read()
            require(old["phase"] in ACTIVE, "GATE_TERMINAL")
            start = self._get("baseline", old["evidence"]["baseline_sha256"])
            _validate_snapshot(start)
            previous = self._preparation(old)
            prior = previous["files"] if previous else {}
            prior_observed = previous["observed"] if previous else {}
            budget = ReadBudget(self.repo)
            current = capture_worktree(self.repo, sorted(set(start["files"]) | set(prior_observed) | set(paths)), _budget=budget)
            require(not (set(changed_paths(start, current)) - set(prior)), "GATE_MODIFIED_BEFORE_PREPARE")
            prepared = {**prior, **{path: current["files"][path] for path in paths if path not in prior}}
            candidates = query(self.store, term, _budget=budget)
            required = initial_scan_required or bool(previous and previous["initial_scan_required"])
            completed = bool(previous and previous["initial_scan_completed"])
            complete = previous["scan_complete"] if previous else True
            missing = candidates.get("reason") == "INDEX_MISSING"
            cold_preparation = bool(previous and previous["index_sha256"] is None
                                    and not previous["initial_scan_completed"])
            if (missing and not _cold_local_only(prepared)) or (cold_preparation and not missing):
                required = True
            if required and (missing or cold_preparation):
                # 中文：扩大免初扫范围前，先前准备的文件也须保持初值，不能追认已修改内容。
                # English: Upgrading an exception requires previously prepared files to retain their original bytes.
                require(all(current["files"][path] == digest for path, digest in prior.items()),
                        "GATE_MODIFIED_BEFORE_PREPARE")
                scopes = [path for path, digest in prepared.items() if digest is not None]
                require(bool(scopes) and all(Path(path).suffix.lower() in SOURCE_SUFFIXES for path in scopes),
                        "GATE_PARTIAL_COVERAGE")
                scanned = scan(self.store, scopes, _budget=budget)
                completed, complete = True, scanned["coverage"]["complete"]
                candidates = query(self.store, term, _budget=budget)
            observed = _observed(budget)
            latest = capture_worktree(self.repo, sorted(set(start["files"]) | set(observed)), _budget=budget)
            require(not (set(changed_paths(start, latest)) - set(prior)), "GATE_MODIFIED_BEFORE_PREPARE")
            all_candidates = {c["id"]: c for c in previous["candidates"]} if previous else {}
            all_candidates.update({c["id"]: {key: c[key] for key in ("id", "path", "freshness")}
                                   for c in candidates["candidates"]})
            require(len(all_candidates) <= 20, "GATE_CANDIDATE_LIMIT")
            payload = {"files": prepared, "observed": observed,
                "candidates": sorted(all_candidates.values(), key=lambda c: c["id"]),
                "index_sha256": self._index_digest(), "initial_scan_required": required,
                "initial_scan_completed": completed, "scan_complete": complete, "term": term,
                "local_only_reason": "" if required else local_only_reason}
            receipt = self._put("prepare", payload)
            state = self.task.record_prepared(receipt, old["revision"])
            if not complete:
                partial = self._put("finish", {"complete": False, "reasons": ["PARTIAL_COVERAGE"]})
                state = self.task.finish("PARTIAL", partial, state["revision"], ["PARTIAL_COVERAGE"])
            return {"state": state, "query": candidates, "required_decisions": payload["candidates"],
                    "semantic_reuse_approved": False}

    def _decisions(self, preparation: dict[str, Any], decisions: list[dict[str, str]]) -> list[str]:
        require(isinstance(decisions, list) and len(decisions) <= 20, "GATE_CANDIDATE_LIMIT")
        known = {c["id"]: c for c in preparation["candidates"]}
        seen, adopted = set(), set()
        for decision in decisions:
            fields(decision, {"id", "choice", "reason"})
            require(isinstance(decision["id"], str) and decision["id"] in known
                    and decision["id"] not in seen, "GATE_CANDIDATE_UNKNOWN")
            require(isinstance(decision["choice"], str) and decision["choice"] in DECISIONS, "GATE_DECISION")
            text_field(decision["reason"], 200)
            require(bool(decision["reason"].strip()), "GATE_DECISION_REASON")
            seen.add(decision["id"])
            if decision["choice"] in {"reuse", "extend", "extract"}:
                adopted.add(known[decision["id"]]["path"])
        require(seen == set(known), "GATE_DECISIONS_MISSING")
        return sorted(adopted)

    def finish(self, decisions: list[dict[str, str]]) -> dict[str, Any]:
        with self.operation:
            old = self.task.read()
            require(old["phase"] in ACTIVE, "GATE_TERMINAL")
            preparation = self._preparation(old)
            require(preparation is not None, "GATE_PREPARE_REQUIRED")
            if preparation["index_sha256"] is None:
                require(_prepared_local_only(preparation), "GATE_INITIAL_SCAN_REQUIRED")
            adopted = self._decisions(preparation, decisions)
            start = self._get("baseline", old["evidence"]["baseline_sha256"])
            budget = ReadBudget(self.repo)
            current = capture_worktree(self.repo, sorted(set(start["files"]) | set(preparation["observed"])), _budget=budget)
            changed = set(changed_paths(start, current))
            changed.update(path for path, digest in preparation["files"].items() if current["files"][path] != digest)
            require(changed <= set(preparation["files"]), "GATE_OUTSIDE_SCOPE")
            complete = preparation["scan_complete"]
            if native_path(self.store.current).exists():
                if changed:
                    invalidate(self.store, sorted(changed), self.store.read()["revision"])
                scopes = sorted({path for path in changed if Path(path).suffix.lower() in SOURCE_SUFFIXES} | set(adopted))
                if scopes:
                    complete = scan(self.store, scopes, _budget=budget)["coverage"]["complete"] and complete
                record = self.store.read()
                for entry in record["entries"]:
                    if entry["path"] in scopes and entry["lifecycle"] != "removed":
                        complete = complete and entry["freshness"] == "matched"
            else:
                require(_prepared_local_only(preparation), "GATE_INITIAL_SCAN_REQUIRED")
            observed = _observed(budget)
            # 中文：回执保留准备时不存在的上下文，防止完成后新增配置静默逃过核验。
            # English: Keep absent preparation context so configuration created later cannot evade checks.
            observed.update({path: current["files"][path] for path in preparation["observed"] if path not in observed})
            latest = capture_worktree(self.repo, sorted(set(start["files"]) | set(observed)), _budget=budget)
            require(set(changed_paths(start, latest)) <= set(preparation["files"]), "GATE_OUTSIDE_SCOPE")
            phase = "PASS" if complete and changed else "NO_CHANGE" if complete else "PARTIAL"
            payload = {"complete": complete, "snapshot": latest, "files": observed,
                       "index_sha256": self._index_digest(), "decisions": copy.deepcopy(decisions),
                       "prepare_sha256": old["evidence"]["prepare_sha256"], "changed_paths": sorted(changed)}
            receipt = self._put("finish", payload)
            state = self.task.finish(phase, receipt, old["revision"], [] if complete else ["PARTIAL_COVERAGE"])
            return {"state": state, "changed_paths": sorted(changed), "semantic_reuse_approved": False}

    def record_failure(self, code: str, expected_revision: int) -> dict[str, Any] | None:
        """中文：仅已确认的覆盖或起点失败落为终态；输入缺项仍可显式补齐。

        English: Persist proven coverage/origin failures; missing input can still be completed explicitly.
        """
        partial = {"BUDGET", "TOO_LARGE", "UNREADABLE", "UNSUPPORTED", "NOT_REGULAR_FILE",
                   "GATE_FILE_LIMIT", "GATE_PATH_LIMIT", "GATE_GIT_OUTPUT_LIMIT", "GATE_PARTIAL_COVERAGE",
                   "GATE_CANDIDATE_LIMIT", "GATE_DEADLINE", "GATE_INDEX_VISIBILITY_UNPROVEN"}
        blocked = {"GATE_MODIFIED_BEFORE_PREPARE", "GATE_OUTSIDE_SCOPE", "GATE_BASELINE_CHANGED", "CHANGED", "READ_CHANGED",
                   "GATE_INITIAL_SCAN_REQUIRED"}
        if code not in partial | blocked:
            return None
        with self.operation:
            state = self.task.read()
            require(state["revision"] == expected_revision, "GATE_REVISION_CONFLICT")
            require(state["phase"] in ACTIVE, "GATE_TERMINAL")
            phase = "PARTIAL" if code in partial else "BLOCKED"
            reason = "PARTIAL_COVERAGE" if phase == "PARTIAL" else "OUTSIDE_SCOPE" if code == "GATE_OUTSIDE_SCOPE" else "BASELINE_CHANGED"
            if code == "GATE_INITIAL_SCAN_REQUIRED":
                reason = "INITIAL_SCAN_NOT_PROVEN"
            receipt = self._put("finish", {"complete": False, "reason_code": code})
            return self.task.finish(phase, receipt, state["revision"], [reason])

    def no_change(self) -> dict[str, Any]:
        """中文：未请求写入且Git可见范围无变化时，仅记录NO_CHANGE，不批准交付。

        English: Record only NO_CHANGE for an unchanged Git-visible scope with no write request.
        """
        with self.operation:
            old = self.task.read()
            require(old["phase"] in ACTIVE and old["evidence"]["prepare_sha256"] is None
                    and "NEEDS_PREPARE" not in old["reason_codes"], "GATE_PREPARE_REQUIRED")
            start = self._get("baseline", old["evidence"]["baseline_sha256"])
            current = capture_worktree(self.repo, sorted(start["files"]))
            require(not changed_paths(start, current), "GATE_MODIFIED_BEFORE_PREPARE")
            index_hash = self._index_digest()
            prepared = self._put("prepare", {"files": {}, "observed": current["files"], "candidates": [],
                "index_sha256": index_hash, "initial_scan_required": False, "initial_scan_completed": False,
                "scan_complete": True, "term": "", "local_only_reason": "No Git-visible changes and no controlled write request"})
            state = self.task.record_prepared(prepared, old["revision"])
            receipt = self._put("finish", {"complete": True, "snapshot": current, "files": current["files"],
                "index_sha256": index_hash, "decisions": [], "prepare_sha256": prepared, "changed_paths": []})
            return self.task.finish("NO_CHANGE", receipt, state["revision"])

    def check(self) -> dict[str, Any]:
        state = self.task.read()
        if state["phase"] not in {"PASS", "NO_CHANGE"}:
            return {"state": state, "valid": False, "semantic_reuse_approved": False}
        try:
            receipt = self._get("finish", state["evidence"]["finish_sha256"])
            fields(receipt, {"complete", "snapshot", "files", "index_sha256", "decisions", "prepare_sha256", "changed_paths"})
            require(receipt["complete"] is True
                    and receipt["prepare_sha256"] == state["evidence"]["prepare_sha256"], "GATE_RECEIPT_CONFLICT")
            _validate_snapshot(receipt["snapshot"])
            _files(receipt["files"])
            preparation = self._preparation(state)
            require(preparation is not None, "GATE_PREPARE_REQUIRED")
            if state["phase"] == "PASS" and preparation["index_sha256"] is None:
                require(_prepared_local_only(preparation), "GATE_INITIAL_SCAN_REQUIRED")
            self._decisions(preparation, receipt["decisions"])
            require(isinstance(receipt["changed_paths"], list) and len(receipt["changed_paths"]) <= MAX_FILES,
                    "GATE_FILE_LIMIT")
            for path in receipt["changed_paths"]:
                relative_path(path)
            if receipt["index_sha256"] is not None:
                hash_field(receipt["index_sha256"])
            current = capture_worktree(self.repo, sorted(set(receipt["snapshot"]["files"]) | set(receipt["files"])))
            require(not changed_paths(receipt["snapshot"], current)
                    and all(current["files"][path] == digest for path, digest in receipt["files"].items())
                    and self._index_digest() == receipt["index_sha256"], "GATE_EVIDENCE_STALE")
            require(self.task.read() == state, "GATE_REVISION_CONFLICT")
            return {"state": state, "valid": True, "semantic_reuse_approved": False}
        except CapabilityError as exc:
            reason = "INITIAL_SCAN_NOT_PROVEN" if str(exc) == "GATE_INITIAL_SCAN_REQUIRED" else "EVIDENCE_STALE"
            return {"state": self.task.invalidate_completion(reason), "valid": False, "semantic_reuse_approved": False}
