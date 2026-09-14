"""中文：为 ``project-resume`` 提供有界、只读的仓库快照。

English: Bounded, read-only repository snapshots for ``project-resume``.

The snapshot hash follows ``cp_runtime.common.repo_snapshot`` for complete inputs,
but every subprocess, file read, and untracked-file walk is bounded.
"""
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .common import RuntimeContractError, ensure_git_repo, utc_now

MAX_GIT_BYTES = 8 * 1024 * 1024
MAX_UNTRACKED_FILES = 200
MAX_UNTRACKED_BYTES = 16 * 1024 * 1024
SNAPSHOT_TIMEOUT_SECONDS = 10.0
FULL_HASH_LIMIT = 4 * 1024 * 1024
SAMPLE_BYTES = 1024 * 1024


class SnapshotBudget:
    def __init__(self, timeout: float = SNAPSHOT_TIMEOUT_SECONDS, byte_limit: int = MAX_GIT_BYTES) -> None:
        self.deadline = time.monotonic() + timeout
        self.remaining = byte_limit
        self.untracked_remaining = MAX_UNTRACKED_BYTES
        self.complete = True
        self.limitations: List[str] = []

    def consume(self, count: int, label: str) -> None:
        self.remaining -= count
        if self.remaining < 0:
            self.complete = False
            self.limitations.append("GIT_OUTPUT_BUDGET_EXCEEDED:" + label)

    def check_time(self) -> None:
        if time.monotonic() > self.deadline:
            self.complete = False
            self.limitations.append("SNAPSHOT_TIMEOUT")
            raise RuntimeContractError("resume snapshot time budget exceeded")

    def consume_untracked(self, count: int, label: str) -> None:
        self.untracked_remaining -= count
        if self.untracked_remaining < 0:
            self.complete = False
            self.limitations.append("UNTRACKED_BYTE_LIMIT_EXCEEDED:" + label)


def _bounded_process(command: Sequence[str], cwd: Path, budget: SnapshotBudget) -> Tuple[bytes, int, bool]:
    budget.check_time()
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        process = subprocess.Popen(
            list(command), cwd=str(cwd), env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        budget.complete = False
        budget.limitations.append("PROCESS_START_FAILED:" + type(exc).__name__)
        return b"", 127, False

    holder: List[bytes] = []

    def reader() -> None:
        try:
            assert process.stdout is not None
            holder.append(process.stdout.read(max(0, budget.remaining) + 1))
        except OSError:
            holder.append(b"")

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    thread.join(max(0.05, budget.deadline - time.monotonic()))
    timed_out = thread.is_alive()
    if timed_out:
        process.kill()
        thread.join(1.0)
        budget.complete = False
        budget.limitations.append("PROCESS_TIMEOUT:" + str(command[0]))
    raw = holder[0] if holder else b""
    overflow = len(raw) > budget.remaining
    if overflow:
        process.kill()
        budget.complete = False
        budget.limitations.append("GIT_OUTPUT_LIMIT_EXCEEDED:" + str(command[1] if len(command) > 1 else command[0]))
        raw = raw[: max(0, budget.remaining)]
    budget.consume(len(raw), str(command[1] if len(command) > 1 else command[0]))
    try:
        returncode = process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        returncode = 124
        budget.complete = False
        budget.limitations.append("PROCESS_REAP_TIMEOUT:" + str(command[0]))
    if process.stdout is not None:
        process.stdout.close()
    return raw, returncode, not timed_out and not overflow and returncode == 0


def _git(root: Path, args: Sequence[str], budget: SnapshotBudget) -> Tuple[bytes, bool]:
    raw, _, ok = _bounded_process(["git", *args], root, budget)
    return raw, ok


def _sampled_file_digest(path: Path, budget: SnapshotBudget) -> Tuple[str, str]:
    info = path.lstat()
    digest = hashlib.sha256()
    digest.update(str(info.st_mode).encode())
    digest.update(b"\0")
    digest.update(str(info.st_size).encode())
    digest.update(b"\0")
    if stat.S_ISLNK(info.st_mode):
        digest.update(os.readlink(path).encode(errors="surrogateescape"))
        return digest.hexdigest(), "symlink"
    if not stat.S_ISREG(info.st_mode):
        digest.update(str(info.st_mtime_ns).encode())
        return digest.hexdigest(), "metadata"
    with path.open("rb") as handle:
        if info.st_size <= FULL_HASH_LIMIT:
            remaining = info.st_size
            while remaining:
                budget.check_time()
                block = handle.read(min(1024 * 1024, remaining))
                if not block:
                    break
                budget.consume_untracked(len(block), "untracked-file")
                digest.update(block)
                remaining -= len(block)
            return digest.hexdigest(), "full"
        first = handle.read(SAMPLE_BYTES)
        budget.consume_untracked(len(first), "untracked-file-sample")
        handle.seek(max(0, info.st_size - SAMPLE_BYTES))
        last = handle.read(SAMPLE_BYTES)
        budget.consume_untracked(len(last), "untracked-file-sample")
        digest.update(first)
        digest.update(last)
        digest.update(str(info.st_mtime_ns).encode())
        return digest.hexdigest(), "sampled"


def _untracked_digest(root: Path, budget: SnapshotBudget) -> Dict[str, Any]:
    raw, ok = _git(root, ["ls-files", "--others", "--exclude-standard", "-z"], budget)
    names = [item for item in raw.split(b"\0") if item]
    if len(names) > MAX_UNTRACKED_FILES:
        budget.complete = False
        budget.limitations.append("UNTRACKED_FILE_LIMIT_EXCEEDED")
        names = names[:MAX_UNTRACKED_FILES]
    digest = hashlib.sha256()
    sampled_count = 0
    for raw_name in sorted(names):
        relative = raw_name.decode("utf-8", errors="surrogateescape")
        path = root / relative
        digest.update(raw_name)
        digest.update(b"\0")
        try:
            if not path.exists() and not path.is_symlink():
                digest.update(b"missing")
                continue
            file_digest, mode = _sampled_file_digest(path, budget)
        except (OSError, RuntimeContractError) as exc:
            budget.complete = False
            budget.limitations.append("UNTRACKED_READ_FAILED:" + type(exc).__name__)
            digest.update(b"unreadable")
            continue
        if mode == "sampled":
            sampled_count += 1
        digest.update(mode.encode())
        digest.update(b":")
        digest.update(file_digest.encode())
        digest.update(b"\0")
        if budget.untracked_remaining < 0:
            budget.complete = False
            budget.limitations.append("UNTRACKED_BYTE_LIMIT_EXCEEDED")
            break
    return {"sha256": digest.hexdigest(), "count": len(names), "sampled_count": sampled_count, "git_ok": ok}


def bounded_repo_snapshot(repo: Path) -> Dict[str, Any]:
    root = ensure_git_repo(repo)
    budget = SnapshotBudget()
    head_raw, head_ok = _git(root, ["rev-parse", "HEAD"], budget)
    branch_raw, branch_code, branch_ok = _bounded_process(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"], root, budget
    )
    remote_raw, _ = _git(root, ["config", "--get", "remote.origin.url"], budget)
    status_raw, status_ok = _git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"], budget)
    diff_raw, diff_ok = _git(root, ["diff", "--binary", "--no-ext-diff", "HEAD", "--"], budget)
    staged_raw, staged_ok = _git(root, ["diff", "--cached", "--binary", "--no-ext-diff", "HEAD", "--"], budget)
    untracked = _untracked_digest(root, budget)
    upstream_raw, _ = _git(root, ["rev-parse", "@{upstream}"], budget)
    head = head_raw.decode("utf-8", errors="replace").strip()
    branch = branch_raw.decode("utf-8", errors="replace").strip() or "DETACHED"
    remote = remote_raw.decode("utf-8", errors="replace").strip()
    upstream = upstream_raw.decode("utf-8", errors="replace").strip()
    # 中文：detached HEAD 下 symbolic-ref 返回 1，但快照仍然完整，branch 显示为 DETACHED。
    # English: symbolic-ref returns 1 for a valid detached HEAD; the snapshot is complete with branch=DETACHED.
    branch_complete = branch_ok or (branch_code == 1 and bool(head))
    complete = budget.complete and all((head_ok, branch_complete, status_ok, diff_ok, staged_ok))
    digest = hashlib.sha256()
    for part in (head.encode(), status_raw, diff_raw, staged_raw, untracked["sha256"].encode()):
        digest.update(part)
        digest.update(b"\0")
    limitations = sorted(set(budget.limitations))
    return {
        "repo_path": str(root),
        "remote_origin": remote,
        "branch": branch,
        "head": head,
        "upstream_head": upstream,
        "tracking_matches_head": bool(upstream and upstream == head),
        "clean": not bool(status_raw),
        "sha256": digest.hexdigest() if complete else None,
        "status_sha256": hashlib.sha256(status_raw).hexdigest(),
        "diff_sha256": hashlib.sha256(diff_raw).hexdigest(),
        "staged_sha256": hashlib.sha256(staged_raw).hexdigest(),
        "untracked_sha256": untracked["sha256"],
        "untracked_count": untracked["count"],
        "untracked_sampled_count": untracked["sampled_count"],
        "complete": complete,
        "limitations": limitations,
        "captured_at": utc_now(),
    }
