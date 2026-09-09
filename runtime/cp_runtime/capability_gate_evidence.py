"""中文：门禁的有界 Git 起点和完整文件指纹；不批准业务语义或交付。

English: Bounded Git origins and full file fingerprints; no semantic or delivery approval.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .capability_index import MAX_PATHS, MAX_READS, ReadBudget
from .capability_store import CapabilityError, fields, hash_field, relative_path, require, safe_path

GIT_OUTPUT_LIMIT = 256 * 1024
GIT_TIMEOUT = 8.0
MAX_FILES = MAX_READS // 2


def _bounded_process(argv: list[str], repo: Path, deadline: float, limit: int) -> tuple[int, bytes]:
    """中文：读取期间限制输出；不先无界收集再截断，也不返回底层错误正文。

    English: Bound output while reading, without unbounded capture or raw error disclosure.
    """
    require(time.monotonic() < deadline, "GATE_DEADLINE")
    try:
        process = subprocess.Popen(argv, cwd=repo, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
    except OSError:
        raise CapabilityError("GATE_GIT_UNAVAILABLE") from None
    output = bytearray()
    done = threading.Event()
    failure: list[str] = []

    def collect() -> None:
        try:
            while True:
                chunk = process.stdout.read1(min(4096, limit + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > limit:
                    failure.append("GATE_GIT_OUTPUT_LIMIT")
                    break
        except (OSError, ValueError):
            failure.append("GATE_GIT_UNAVAILABLE")
        finally:
            done.set()

    reader = threading.Thread(target=collect, daemon=True)
    reader.start()
    try:
        require(done.wait(max(0, deadline - time.monotonic())), "GATE_DEADLINE")
        require(not failure, failure[0] if failure else "GATE_GIT_UNAVAILABLE")
        try:
            code = process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise CapabilityError("GATE_DEADLINE") from None
        require(time.monotonic() <= deadline, "GATE_DEADLINE")
        return code, bytes(output)
    finally:
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass
        reader.join(timeout=0.5)
        # 中文：异常继承管道的进程不能让主线程无限等待关闭；正常 Git 已被回收。
        # English: An inherited pipe must not block the main thread during cleanup.
        if not reader.is_alive():
            process.stdout.close()


class GitView:
    def __init__(self, repo: Path, deadline: float):
        self.repo = safe_path(repo)
        self.deadline = deadline
        self.bytes_read = 0
        self.calls = 0

    def command(self, args: list[str], limit: int = GIT_OUTPUT_LIMIT) -> tuple[int, bytes]:
        result = _bounded_process(["git", "--no-optional-locks", "--literal-pathspecs",
            "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", *args],
            self.repo, self.deadline, limit)
        self.calls += 1
        self.bytes_read += len(result[1])
        return result

    def baseline(self) -> dict[str, str]:
        values = []
        for args in (["rev-parse", "--verify", "HEAD"], ["symbolic-ref", "--quiet", "--short", "HEAD"]):
            code, raw = self.command(args, 1024)
            require(code in {0, 1, 128}, "GATE_GIT_UNAVAILABLE")
            try:
                value = raw.decode("utf-8").strip() if code == 0 else ""
            except UnicodeError:
                raise CapabilityError("GATE_GIT_ENCODING") from None
            require(len(value) <= 256, "GATE_GIT_BASELINE")
            values.append(value)
        require(bool(values[0] or values[1]), "GATE_GIT_UNAVAILABLE")
        return {"head": values[0], "branch": values[1]}

    def status(self) -> dict[str, str]:
        code, raw = self.command(["status", "--porcelain=v1", "-z", "--untracked-files=all",
                                  "--no-renames", "--ignore-submodules=none"])
        require(code == 0, "GATE_GIT_UNAVAILABLE")
        require(not raw or raw.endswith(b"\0"), "GATE_GIT_STATUS")
        records = raw[:-1].split(b"\0") if raw else []
        require(len(records) <= MAX_PATHS, "GATE_PATH_LIMIT")
        result = {}
        for record in records:
            require(len(record) > 3 and record[2:3] == b" ", "GATE_GIT_STATUS")
            try:
                status, path = record[:2].decode("ascii"), record[3:].decode("utf-8")
            except UnicodeError:
                raise CapabilityError("GATE_GIT_ENCODING") from None
            require(all(char in " MADTU?!" for char in status), "GATE_GIT_STATUS")
            relative_path(path)
            require(path not in result, "GATE_GIT_STATUS")
            result[path] = status
        return result

    def require_visible_index(self) -> None:
        # 中文：只枚举有界Git索引元数据；隐藏标志会破坏修改前证明，不能当作干净。
        # English: Enumerate bounded index metadata; hidden flags invalidate pre-edit evidence.
        code, raw = self.command(["ls-files", "-v", "-z"])
        require(code == 0 and (not raw or raw.endswith(b"\0")), "GATE_GIT_STATUS")
        records = raw[:-1].split(b"\0") if raw else []
        require(len(records) <= MAX_PATHS, "GATE_PATH_LIMIT")
        require(all(len(record) > 2 and record[:2] == b"H " for record in records),
                "GATE_INDEX_VISIBILITY_UNPROVEN")


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    fields(snapshot, {"schema_version", "git", "status", "files", "cost"})
    require(type(snapshot["schema_version"]) is int and snapshot["schema_version"] == 1, "GATE_SCHEMA")
    fields(snapshot["git"], {"head", "branch"})
    require(all(isinstance(value, str) and len(value) <= 256 for value in snapshot["git"].values()), "GATE_SCHEMA")
    require(isinstance(snapshot["status"], dict) and len(snapshot["status"]) <= MAX_PATHS, "GATE_SCHEMA")
    require(isinstance(snapshot["files"], dict) and len(snapshot["files"]) <= MAX_FILES, "GATE_FILE_LIMIT")
    for path, status in snapshot["status"].items():
        relative_path(path)
        require(isinstance(status, str) and len(status) == 2
                and all(char in " MADTU?!" for char in status), "GATE_SCHEMA")
        require(path in snapshot["files"], "GATE_EVIDENCE_INCOMPLETE")
    for path, digest in snapshot["files"].items():
        relative_path(path)
        if digest is not None:
            hash_field(digest)
    fields(snapshot["cost"], {"git_calls", "git_bytes", "file_reads", "file_bytes"})
    require(all(type(n) is int and n >= 0 for n in snapshot["cost"].values()), "GATE_SCHEMA")


def capture_worktree(repo: Path, paths: list[str] | None = None, *, timeout: float = GIT_TIMEOUT,
                     _budget: ReadBudget | None = None) -> dict[str, Any]:
    """中文：捕获所有 Git 可见脏路径及指定文件；超限抛出固定原因而非完整证明。

    English: Capture Git-visible dirty paths and named files; limits fail instead of claiming proof.
    """
    require(type(timeout) in {int, float} and 0 < timeout <= GIT_TIMEOUT, "GATE_TIMEOUT_INVALID")
    require(paths is None or isinstance(paths, list) and len(paths) <= MAX_FILES, "GATE_FILE_LIMIT")
    for path in paths or []:
        relative_path(path)
    selected = set(paths or [])
    view = GitView(repo, time.monotonic() + timeout)
    view.require_visible_index()
    baseline, status = view.baseline(), view.status()
    selected.update(status)
    require(len(selected) <= MAX_FILES, "GATE_FILE_LIMIT")
    budget = _budget or ReadBudget(view.repo)
    require(budget.repo == view.repo, "BUDGET_IDENTITY_MISMATCH")
    fingerprints = {}
    for path in sorted(selected):
        require(time.monotonic() < view.deadline, "GATE_DEADLINE")
        if budget.context_exists(path):
            fingerprints[path] = hashlib.sha256(budget.read(path)).hexdigest()
        else:
            fingerprints[path] = None
    budget.verify()
    require(view.status() == status and view.baseline() == baseline, "GATE_BASELINE_CHANGED")
    view.require_visible_index()
    require(time.monotonic() <= view.deadline, "GATE_DEADLINE")
    result = {"schema_version": 1, "git": baseline, "status": status, "files": fingerprints,
              "cost": {"git_calls": view.calls, "git_bytes": view.bytes_read,
                       "file_reads": budget.reads, "file_bytes": budget.bytes_read}}
    _validate_snapshot(result)
    return result


def changed_paths(start: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """中文：初始脏内容保持不变不算本任务修改；HEAD/分支变化不可沿用起点。

    English: Unchanged initial dirt is not a task edit; HEAD/branch changes invalidate the origin.
    """
    _validate_snapshot(start)
    _validate_snapshot(current)
    require(start["git"] == current["git"], "GATE_BASELINE_CHANGED")
    require(set(start["files"]) <= set(current["files"]), "GATE_EVIDENCE_INCOMPLETE")
    changed = {path for path, digest in start["files"].items() if current["files"][path] != digest}
    # 中文：起点未读取的干净文件，在终态变脏即保守视为修改；不使用局部正文抽样。
    # English: A previously unobserved clean file becoming dirty conservatively counts as changed.
    changed.update(set(current["status"]) - set(start["files"]))
    return sorted(changed)


def prepare_files(repo: Path, start: dict[str, Any], paths: list[str],
                  previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """中文：新范围必须在修改前加入；已有准备文件可保留初值进行有界扩展。

    English: Add new scope before edits; bounded expansion retains prior prepared initial values.
    """
    _validate_snapshot(start)
    require(isinstance(paths, list) and 0 < len(paths) <= MAX_FILES, "GATE_FILE_LIMIT")
    prior = previous or {}
    require(isinstance(prior, dict) and len(prior) <= MAX_FILES, "GATE_FILE_LIMIT")
    for path, digest in prior.items():
        relative_path(path)
        if digest is not None:
            hash_field(digest)
    for path in paths:
        relative_path(path)
    selected = sorted(set(start["files"]) | set(prior) | set(paths))
    current = capture_worktree(repo, selected)
    require(not (set(changed_paths(start, current)) - set(prior)), "GATE_MODIFIED_BEFORE_PREPARE")
    return {**prior, **{path: current["files"][path] for path in paths if path not in prior}}


def verify_files(repo: Path, start: dict[str, Any], manifest: dict[str, str | None]) -> dict[str, Any]:
    """中文：完成回执重读必须覆盖起点和准备清单；未准备的改动不能补录成通过。

    English: Completion rereads cover the origin and manifest; out-of-scope edits cannot be approved.
    """
    _validate_snapshot(start)
    require(isinstance(manifest, dict) and len(manifest) <= MAX_FILES, "GATE_FILE_LIMIT")
    for path, digest in manifest.items():
        relative_path(path)
        if digest is not None:
            hash_field(digest)
    current = capture_worktree(repo, sorted(set(start["files"]) | set(manifest)))
    changes = set(changed_paths(start, current))
    require(changes <= set(manifest), "GATE_OUTSIDE_SCOPE")
    changes.update(path for path, digest in manifest.items() if current["files"][path] != digest)
    return {"snapshot": current, "changed_paths": sorted(changes),
            "manifest_matches": all(current["files"][path] == digest for path, digest in manifest.items()),
            "semantic_reuse_approved": False}
