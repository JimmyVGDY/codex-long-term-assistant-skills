#!/usr/bin/env python3
"""中文：为完整验证提供可比较的 Git 工作区快照。

English: Provide comparable Git worktree snapshots for complete validation.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Callable, TypeVar


class WorktreeMutationError(RuntimeError):
    pass


T = TypeVar("T")


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise WorktreeMutationError(
            "unable to capture validation worktree state: "
            + result.stderr.decode("utf-8", errors="replace").strip()
        )
    return result.stdout


def _content_fingerprints(repo: Path) -> bytes:
    paths = _git(repo, "ls-files", "-c", "-o", "--exclude-standard", "-z")
    entries = []
    for raw_path in paths.split(b"\0"):
        if not raw_path:
            continue
        relative = os.fsdecode(raw_path)
        path = repo / relative
        try:
            stat = path.lstat()
            if path.is_symlink():
                payload = b"symlink\0" + os.fsencode(os.readlink(path))
            elif path.is_file():
                payload = b"file\0" + path.read_bytes()
            else:
                payload = b"other\0"
            mode = stat.st_mode & 0o777
        except FileNotFoundError:
            payload = b"missing\0"
            mode = 0
        digest = hashlib.sha256(payload).hexdigest().encode("ascii")
        entries.append(raw_path + b"\0" + oct(mode).encode("ascii") + b"\0" + digest)
    return b"\0".join(entries)


def capture_worktree(repo: Path) -> bytes:
    repo = Path(repo)
    status = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    index = _git(repo, "ls-files", "--stage", "-z")
    content = _content_fingerprints(repo)
    return b"status\0" + status + b"\0index\0" + index + b"\0content\0" + content


def _entries(snapshot: bytes) -> list[str]:
    return sorted(
        entry.decode("utf-8", errors="replace")
        for entry in snapshot.split(b"\0")
        if entry
    )


def assert_worktree_unchanged(before: bytes, after: bytes) -> None:
    if before == after:
        return
    before_entries = set(_entries(before))
    after_entries = set(_entries(after))
    added = sorted(after_entries - before_entries)
    removed = sorted(before_entries - after_entries)
    raise WorktreeMutationError(
        "validation changed the Git-visible worktree; added_or_changed=%r removed_or_restored=%r"
        % (added, removed)
    )


def run_with_worktree_guard(repo: Path, action: Callable[[], T]) -> T:
    before = capture_worktree(repo)
    failure: BaseException | None = None
    result: T | None = None
    try:
        result = action()
    except BaseException as exc:
        failure = exc
    try:
        after = capture_worktree(repo)
        assert_worktree_unchanged(before, after)
    except Exception as worktree_error:
        if failure is not None:
            raise worktree_error from failure
        raise
    if failure is not None:
        raise failure
    return result  # type: ignore[return-value]


def require_output_outside_worktree(repo: Path, output: Path) -> Path:
    repo = Path(repo).resolve()
    output = Path(output).expanduser().resolve()
    try:
        output.relative_to(repo)
    except ValueError:
        return output
    raise WorktreeMutationError(
        "validation --output must be outside the validated Git worktree: " + str(output)
    )
