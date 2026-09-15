"""中文：恢复查询的有界 Git 快照，保持既有内容摘要算法。

English: Bounded Git snapshots for recovery, preserving the existing digest algorithm.
"""
from __future__ import annotations

import hashlib
import os
import queue
import signal
import stat
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Sequence

from .common import FULL_HASH_LIMIT, SAMPLE_BYTES, RuntimeContractError, utc_now
from .capability_store import CapabilityError, bounded_read, safe_path

MAX_GIT_BYTES = 8 * 1024 * 1024
MAX_UNTRACKED_FILES = 200
MAX_UNTRACKED_BYTES = 16 * 1024 * 1024
SNAPSHOT_TIMEOUT_SECONDS = 10.0


def _windows_job(process):
    """中文：用进程拥有的 Job 在关闭时回收后代，不依赖 taskkill 权限。

    English: Own descendants with a kill-on-close Job rather than depending on taskkill permissions.
    """
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    class BasicLimits(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                    ("flags", wintypes.DWORD), ("minimum", ctypes.c_size_t), ("maximum", ctypes.c_size_t),
                    ("active_processes", wintypes.DWORD), ("affinity", ctypes.c_size_t),
                    ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]
    class Limits(ctypes.Structure):
        _fields_ = [("basic", BasicLimits), ("io", ctypes.c_uint64 * 6),
                    ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                    ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise OSError("JOB_CREATE_FAILED")
    limits = Limits()
    limits.basic.flags = 0x2000
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(job, int(process._handle)):
        kernel.CloseHandle(job)
        raise OSError("JOB_ASSIGN_FAILED")
    return lambda: kernel.CloseHandle(job)


class SnapshotLimit(RuntimeContractError):
    """中文：读取不完整，不表示记录损坏。 English: Incomplete input, not corrupt records."""


class SnapshotBudget:
    def __init__(self, timeout: float | None = None, byte_limit: int = MAX_GIT_BYTES,
                 deadline: float | None = None) -> None:
        self.deadline = deadline if deadline is not None else time.monotonic() + (
            SNAPSHOT_TIMEOUT_SECONDS if timeout is None else timeout
        )
        self.remaining = byte_limit
        self.untracked_remaining = MAX_UNTRACKED_BYTES
        self.complete = True
        self.limitations: list[str] = []

    def fail(self, reason: str) -> None:
        self.complete = False
        if reason not in self.limitations:
            self.limitations.append(reason)

    def check_time(self) -> None:
        if time.monotonic() >= self.deadline:
            self.fail("SNAPSHOT_TIMEOUT")
            raise SnapshotLimit("SNAPSHOT_TIMEOUT")


def _bounded_process(command: Sequence[str], cwd: Path,
                     budget: SnapshotBudget) -> tuple[bytes, int, bool]:
    budget.check_time()
    if budget.remaining <= 0:
        budget.fail("GIT_OUTPUT_BUDGET_EXCEEDED")
        return b"", 124, False
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS="0", PYTHONDONTWRITEBYTECODE="1")
    try:
        process = subprocess.Popen(
            list(command), cwd=str(cwd), env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
    except OSError:
        budget.fail("PROCESS_START_FAILED")
        return b"", 127, False
    try:
        close_job = _windows_job(process)
    except OSError:
        process.kill()
        process.wait(timeout=1)
        process.stdout.close()
        process.stderr.close()
        budget.fail("PROCESS_CONTAINMENT_UNAVAILABLE")
        return b"", 127, False
    events: queue.Queue[tuple[int, bytes | None]] = queue.Queue(maxsize=8)
    stopped = threading.Event()

    def read_pipe(stream, channel: int) -> None:
        try:
            while not stopped.is_set():
                chunk = stream.read1(65536)
                value = (channel, chunk if chunk else None)
                while not stopped.is_set():
                    try:
                        events.put(value, timeout=0.05)
                        break
                    except queue.Full:
                        continue
                if not chunk:
                    break
        except (OSError, ValueError):
            while not stopped.is_set():
                try:
                    events.put((-1, None), timeout=0.05)
                    break
                except queue.Full:
                    continue

    readers = [
        threading.Thread(target=read_pipe, args=(process.stdout, 0), daemon=True),
        threading.Thread(target=read_pipe, args=(process.stderr, 1), daemon=True),
    ]
    for reader in readers:
        reader.start()
    output = bytearray()
    finished: set[int] = set()
    complete = True
    returncode = 124
    try:
        while len(finished) < 2:
            budget.check_time()
            try:
                channel, chunk = events.get(timeout=min(0.05, max(0.001, budget.deadline - time.monotonic())))
            except queue.Empty:
                continue
            if channel == -1:
                budget.fail("PROCESS_STREAM_READ_FAILED")
                complete = False
                break
            if chunk is None:
                finished.add(channel)
                continue
            if len(chunk) > budget.remaining:
                budget.fail("GIT_OUTPUT_BUDGET_EXCEEDED")
                complete = False
                break
            budget.remaining -= len(chunk)
            if channel == 0:
                output.extend(chunk)
        if complete:
            returncode = process.wait(timeout=max(0.001, budget.deadline - time.monotonic()))
    except (SnapshotLimit, subprocess.TimeoutExpired):
        budget.fail("SNAPSHOT_TIMEOUT")
        complete = False
    finally:
        stopped.set()
        if close_job:
            close_job()
        if process.poll() is None:
            try:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            budget.fail("PROCESS_REAP_TIMEOUT")
            complete = False
        for reader in readers:
            reader.join(timeout=0.2)
        for reader, stream in zip(readers, (process.stdout, process.stderr)):
            if reader.is_alive():
                budget.fail("PROCESS_STREAM_CLOSE_TIMEOUT")
                complete = False
            elif stream is not None:
                stream.close()
    return bytes(output), returncode, complete and budget.complete


def _git(root: Path, args: Sequence[str], budget: SnapshotBudget,
         allowed_codes: tuple[int, ...] = (0,)) -> bytes:
    raw, code, complete = _bounded_process(["git", "-c", "core.fsmonitor=false", *args], root, budget)
    if not complete or code not in allowed_codes:
        budget.fail("GIT_QUERY_INCOMPLETE")
        raise SnapshotLimit("GIT_QUERY_INCOMPLETE")
    return raw


def _untracked_digest(root: Path, budget: SnapshotBudget) -> dict[str, Any]:
    raw = _git(root, ["ls-files", "--others", "--exclude-standard", "-z"], budget)
    names = [name for name in raw.split(b"\0") if name]
    if len(names) > MAX_UNTRACKED_FILES:
        budget.fail("UNTRACKED_FILE_LIMIT_EXCEEDED")
        raise SnapshotLimit("UNTRACKED_FILE_LIMIT_EXCEEDED")
    digest = hashlib.sha256()
    for raw_name in sorted(names):
        budget.check_time()
        relative = raw_name.decode("utf-8", errors="surrogateescape")
        path = root / relative
        digest.update(raw_name)
        digest.update(b"\0")
        try:
            safe = safe_path(path)
            info = safe.stat()
            if not stat.S_ISREG(info.st_mode):
                budget.fail("UNTRACKED_NOT_REGULAR")
                raise SnapshotLimit("UNTRACKED_NOT_REGULAR")
            if info.st_size > FULL_HASH_LIMIT:
                budget.fail("UNTRACKED_SAMPLED_CONTENT")
                raise SnapshotLimit("UNTRACKED_SAMPLED_CONTENT")
            if info.st_size > budget.untracked_remaining:
                budget.fail("UNTRACKED_BYTE_LIMIT_EXCEEDED")
                raise SnapshotLimit("UNTRACKED_BYTE_LIMIT_EXCEEDED")
            content = bounded_read(path, min(FULL_HASH_LIMIT, budget.untracked_remaining))
            budget.untracked_remaining -= len(content)
            after = safe.stat()
            if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise SnapshotLimit("UNTRACKED_CHANGED")
            file_digest = hashlib.sha256()
            file_digest.update(str(info.st_mode).encode())
            file_digest.update(b"\0")
            file_digest.update(str(info.st_size).encode())
            file_digest.update(b"\0")
            file_digest.update(content)
            digest.update(b"full:")
            digest.update(file_digest.hexdigest().encode())
            digest.update(b"\0")
        except (OSError, CapabilityError) as exc:
            budget.fail("UNTRACKED_READ_INCOMPLETE")
            raise SnapshotLimit("UNTRACKED_READ_INCOMPLETE") from exc
    return {"sha256": digest.hexdigest(), "count": len(names), "sampled_count": 0}


def _check_textconv(root: Path, budget: SnapshotBudget) -> None:
    """中文：只在变更路径实际使用转换器时保留未知，不执行外部转换器。

    English: Keep unknown only when changed paths select a converter; never execute external converters.
    """
    keys = _git(root, ["config", "--name-only", "--get-regexp", r"^diff\..*\.textconv$"], budget, (0, 1))
    drivers = {key[len(b"diff."):-len(b".textconv")] for key in keys.splitlines()}
    if not drivers:
        return
    paths: set[bytes] = set()
    for stage in ([], ["--cached"]):
        changed = _git(root, ["diff", *stage, "--name-only", "-z", "--no-renames",
                              "--no-ext-diff", "--no-textconv", "HEAD", "--"], budget)
        paths.update(path for path in changed.split(b"\0") if path)
    pending = sorted(paths)
    while pending:
        batch: list[str] = []
        size = 0
        while pending and len(batch) < 32:
            path = pending[0].decode("utf-8", errors="surrogateescape")
            if len(path) > 6000:
                raise SnapshotLimit("ATTRIBUTE_PATH_BUDGET_EXCEEDED")
            if batch and size + len(path) + 3 > 6000:
                break
            batch.append(path)
            size += len(path) + 3
            pending.pop(0)
        for stage in ([], ["--cached"]):
            raw = _git(root, ["check-attr", *stage, "-z", "diff", "--", *batch], budget)
            parts = raw.split(b"\0")
            if parts[-1:] != [b""] or len(parts) != len(batch) * 3 + 1:
                raise SnapshotLimit("ATTRIBUTE_QUERY_INCOMPLETE")
            if any(parts[index] in drivers for index in range(2, len(parts) - 1, 3)):
                raise SnapshotLimit("EXTERNAL_DIFF_FILTER_NOT_EVALUATED")


def _snapshot_once(root: Path, budget: SnapshotBudget) -> dict[str, Any]:
    head = _git(root, ["rev-parse", "HEAD"], budget).decode("utf-8").strip()
    branch = _git(root, ["symbolic-ref", "--quiet", "--short", "HEAD"], budget, (0, 1)).decode("utf-8").strip() or "DETACHED"
    remote = _git(root, ["config", "--get", "remote.origin.url"], budget, (0, 1)).decode("utf-8").strip()
    status = _git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"], budget)
    diff = _git(root, ["diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--"], budget)
    staged = _git(root, ["diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--"], budget)
    if diff or staged:
        _check_textconv(root, budget)
    untracked = _untracked_digest(root, budget)
    upstream = _git(root, ["rev-parse", "--verify", "--quiet", "@{upstream}"], budget, (0, 1, 128)).decode("utf-8").strip()
    digest = hashlib.sha256()
    for part in (head.encode(), status, diff, staged, untracked["sha256"].encode()):
        digest.update(part)
        digest.update(b"\0")
    return {
        "repo_path": str(root), "remote_origin": remote, "branch": branch, "head": head,
        "upstream_head": upstream, "tracking_matches_head": bool(upstream and upstream == head),
        "clean": not bool(status), "sha256": digest.hexdigest(),
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "diff_sha256": hashlib.sha256(diff).hexdigest(),
        "staged_sha256": hashlib.sha256(staged).hexdigest(),
        "untracked_sha256": untracked["sha256"], "untracked_count": untracked["count"],
        "untracked_sampled_count": 0,
    }


def bounded_repo_snapshot(repo: Path, *, budget: SnapshotBudget | None = None) -> dict[str, Any]:
    """中文：同次查询共享一次稳定性核验，不为每条证据重跑。

    English: Share one stability-checked snapshot across all evidence in a query.
    """
    budget = budget or SnapshotBudget()
    try:
        requested = safe_path(repo)
    except CapabilityError as exc:
        raise RuntimeContractError("REPOSITORY_PATH_UNSAFE") from exc
    if not requested.is_dir():
        raise RuntimeContractError("REPOSITORY_DIRECTORY_MISSING")
    result: dict[str, Any] = {"repo_path": str(requested), "root_verified": False,
                              "sha256": None, "complete": False}
    try:
        raw = _git(requested, ["rev-parse", "--show-toplevel"], budget)
        root = safe_path(Path(raw.decode("utf-8").strip()))
        result.update(repo_path=str(root), root_verified=True)
        first = _snapshot_once(root, budget)
        second = _snapshot_once(root, budget)
        budget.check_time()
        if any(first[key] != second[key] for key in ("sha256", "remote_origin", "branch", "upstream_head")):
            budget.fail("REPOSITORY_CHANGED_DURING_READ")
        result.update(second)
        result["complete"] = budget.complete
        if not budget.complete:
            result["sha256"] = None
    except (SnapshotLimit, CapabilityError, OSError, UnicodeError) as exc:
        budget.fail(str(exc) if isinstance(exc, SnapshotLimit) else "SNAPSHOT_UNREADABLE")
        result["sha256"] = None
        result["complete"] = False
    result["limitations"] = sorted(set(budget.limitations))
    result["captured_at"] = utc_now()
    return result
