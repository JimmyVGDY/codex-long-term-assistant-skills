"""中文：持久、签名的 SessionEnd 追加与封印队列。

English: Durable, signed SessionEnd append-and-seal queue.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .event_v2 import OwnerTokenLock, append_event, canonical_json, make_event
from .integrity import active_secret, seal_event_chain, secret_by_id
from .atomic_io import replace_with_retry

JOB_SCHEMA = "1.0"
JOB_STATES = ("pending", "running", "done", "dead-letter")
JOB_NAME = re.compile(r"^job-[0-9a-f]{64}\.json$")


class SealQueueError(RuntimeError):
    pass


def _codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME", "").strip()
    if os.name == "nt" and re.match(r"^/mnt/[A-Za-z](?:/|$)", raw):
        raw = raw[5].upper() + ":\\" + raw[7:].replace("/", "\\")
    return Path(raw).expanduser() if raw else Path.home() / ".codex"


def _managed_roots() -> list[Path]:
    roots = [_codex_home() / "project-context"]
    temporary = Path(os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir())
    roots.append(temporary / "codex-cp-assistant-v6" / "project-context")
    if os.environ.get("CP_ASSISTANT_DATA"):
        roots.append(Path(os.environ["CP_ASSISTANT_DATA"]).expanduser())
    return roots


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _lexical_relative(path: Path, root: Path) -> Optional[Path]:
    candidate = Path(os.path.abspath(os.fspath(path)))
    base = Path(os.path.abspath(os.fspath(root)))
    try:
        return candidate.relative_to(base)
    except ValueError:
        return None


def _validate_queue(queue: Path, project_id: str) -> Path:
    queue = Path(queue)
    if queue.name != "seal-queue" or queue.parent.name != "feedback" or queue.parent.parent.name != project_id:
        raise SealQueueError("QUEUE_PATH_INVALID")
    root = next((candidate for candidate in _managed_roots()
                 if _lexical_relative(queue, candidate) is not None), None)
    if root is None:
        raise SealQueueError("QUEUE_ROOT_UNMANAGED")
    root = Path(os.path.abspath(os.fspath(root)))
    queue = Path(os.path.abspath(os.fspath(queue)))
    current = root
    if _is_reparse(current):
        raise SealQueueError("QUEUE_REPARSE_REJECTED")
    relative = _lexical_relative(queue, root)
    if relative is None:
        raise SealQueueError("QUEUE_ROOT_UNMANAGED")
    for part in relative.parts:
        current = current / part
        if _is_reparse(current):
            raise SealQueueError("QUEUE_REPARSE_REJECTED")
    if not _inside(queue, root):
        raise SealQueueError("QUEUE_ROOT_UNMANAGED")
    event_path = queue.parent / "task-outcome-v2.jsonl"
    if event_path.exists() and _is_reparse(event_path):
        raise SealQueueError("EVENT_REPARSE_REJECTED")
    return event_path


def _sign(job: Dict[str, Any], key: bytes, key_id: str) -> Dict[str, Any]:
    signed = dict(job)
    signed["key_id"] = key_id
    signed.pop("job_hmac_sha256", None)
    signed["job_hmac_sha256"] = hmac.new(key, canonical_json(signed).encode("utf-8"), hashlib.sha256).hexdigest()
    return signed


def _verify(job: Mapping[str, Any], keyring_path: Optional[Path]) -> Dict[str, Any]:
    if job.get("schema_version") != JOB_SCHEMA or str(job.get("state")) not in JOB_STATES:
        raise SealQueueError("JOB_SCHEMA_INVALID")
    key_id = str(job.get("key_id") or "")
    _ring, secret = secret_by_id("event-hmac", key_id, keyring_path)
    unsigned = {key: value for key, value in job.items() if key != "job_hmac_sha256"}
    expected = hmac.new(secret, canonical_json(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(job.get("job_hmac_sha256") or ""), expected):
        raise SealQueueError("JOB_HMAC_INVALID")
    return dict(job)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush(); os.fsync(handle.fileno())
        replace_with_retry(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _load(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SealQueueError("JOB_READ_INVALID") from exc
    if not isinstance(value, dict):
        raise SealQueueError("JOB_SCHEMA_INVALID")
    return value


def _job_file(queue: Path, state: str, job_name: str) -> Path:
    if state not in JOB_STATES or not JOB_NAME.fullmatch(job_name):
        raise SealQueueError("JOB_NAME_INVALID")
    return queue / state / job_name


def enqueue_session_end(queue: Path, event: Mapping[str, Any], keyring_path: Optional[Path] = None) -> Dict[str, Any]:
    validated = make_event(event)
    if validated["event_type"] != "SESSION_ENDED":
        raise SealQueueError("JOB_EVENT_TYPE_INVALID")
    event_path = _validate_queue(Path(queue), validated["project_id"])
    identity = canonical_json({key: validated[key] for key in (
        "event_type", "session_id", "turn_id", "task_id", "project_id", "repo_fingerprint")})
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    job_name = "job-" + digest + ".json"
    queue = Path(queue)
    queue.mkdir(parents=True, exist_ok=True)
    for state in JOB_STATES:
        (queue / state).mkdir(exist_ok=True)
    with OwnerTokenLock(queue / "queue-state", timeout=0.35):
        existing = next((state for state in JOB_STATES if _job_file(queue, state, job_name).exists()), None)
        if existing:
            return {"ok": True, "enqueued": False, "state": existing, "job_ref": "sha256:" + digest}
        maximum = int(os.environ.get("CP_ASSISTANT_SEAL_QUEUE_MAX_JOBS", "10000"))
        count = sum(1 for state in JOB_STATES for item in (queue / state).glob("job-*.json") if JOB_NAME.fullmatch(item.name))
        if count >= maximum:
            raise SealQueueError("QUEUE_CAPACITY_EXCEEDED")
        _ring, secret, key_id = active_secret("event-hmac", keyring_path)
        job = {
            "schema_version": JOB_SCHEMA, "job_id": digest, "idempotency_key": digest,
            "state": "pending", "attempt": 0, "lease_epoch": 0, "lease_pid": 0,
            "lease_process_identity": "",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "project_id": validated["project_id"], "repo_fingerprint": validated["repo_fingerprint"],
            "event_file": event_path.name, "event": validated, "error_code": "NONE",
        }
        _atomic_json(_job_file(queue, "pending", job_name), _sign(job, secret, key_id))
    return {"ok": True, "enqueued": True, "state": "pending", "job_ref": "sha256:" + digest}


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        ctypes = __import__("ctypes")
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            exit_code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            # 中文：Windows 状态码 259 表示进程仍在运行。
            # English: Windows status code 259 means the process is still active.
            return bool(ok and exit_code.value == 259)
        return False
    try:
        os.kill(pid, 0); return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _process_identity(pid: int) -> str:
    """中文：在可观察时返回抵抗 PID 复用的进程启动身份。

    English: Return a PID-reuse-resistant process-start identity when observable.
    """
    if pid <= 0:
        return ""
    if os.name == "nt":
        ctypes = __import__("ctypes")
        from ctypes import wintypes

        class FileTime(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return ""
        created, exited, kernel, user = FileTime(), FileTime(), FileTime(), FileTime()
        try:
            ok = ctypes.windll.kernel32.GetProcessTimes(
                handle, ctypes.byref(created), ctypes.byref(exited),
                ctypes.byref(kernel), ctypes.byref(user))
            if not ok:
                return ""
            value = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
            return "windows-filetime:%d" % value
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        fields = (Path("/proc") / str(pid) / "stat").read_text(encoding="ascii").split()
        return "proc-start:%s" % fields[21] if len(fields) > 21 else ""
    except (OSError, UnicodeError):
        return ""


def _resign(job: Dict[str, Any], keyring_path: Optional[Path]) -> Dict[str, Any]:
    _ring, secret, key_id = active_secret("event-hmac", keyring_path)
    return _sign(job, secret, key_id)


def _recover_running(queue: Path, keyring_path: Optional[Path]) -> None:
    for path in sorted((queue / "running").glob("job-*.json")):
        if not JOB_NAME.fullmatch(path.name):
            continue
        try:
            job = _verify(_load(path), keyring_path)
            pid = int(job.get("lease_pid") or 0)
            expected_identity = str(job.get("lease_process_identity") or "")
            if expected_identity and _pid_alive(pid) and _process_identity(pid) == expected_identity:
                continue
            job.update(state="pending", lease_pid=0, lease_process_identity="",
                       error_code="RECOVERED_AFTER_WORKER_EXIT")
            _atomic_json(path, _resign(job, keyring_path))
            replace_with_retry(path, _job_file(queue, "pending", path.name))
        except Exception:
            replace_with_retry(path, _job_file(queue, "dead-letter", path.name))


def _crash(point: str) -> None:
    if os.environ.get("CP_ASSISTANT_TEST_SEAL_WORKER_HARD_CRASH_POINT") == point:
        os._exit(94)


def process_queue(queue: Path, keyring_path: Optional[Path] = None, max_jobs: int = 100) -> Dict[str, Any]:
    queue = Path(queue)
    project_id = queue.parent.parent.name
    event_path = _validate_queue(queue, project_id)
    processed = completed = retried = dead = 0
    for _ in range(max_jobs):
        with OwnerTokenLock(queue / "queue-state", timeout=2.0):
            _recover_running(queue, keyring_path)
            pending = next(iter(sorted((queue / "pending").glob("job-*.json"))), None)
            if pending is None:
                break
            if not JOB_NAME.fullmatch(pending.name):
                raise SealQueueError("JOB_NAME_INVALID")
            try:
                job = _verify(_load(pending), keyring_path)
            except Exception:
                replace_with_retry(pending, _job_file(queue, "dead-letter", pending.name))
                dead += 1
                continue
            if job.get("project_id") != project_id or job.get("event_file") != event_path.name:
                replace_with_retry(pending, _job_file(queue, "dead-letter", pending.name)); dead += 1; continue
            job["state"] = "running"; job["attempt"] = int(job.get("attempt") or 0) + 1
            job["lease_epoch"] = int(job.get("lease_epoch") or 0) + 1; job["lease_pid"] = os.getpid()
            job["lease_process_identity"] = _process_identity(os.getpid())
            if not job["lease_process_identity"]:
                raise SealQueueError("WORKER_PROCESS_IDENTITY_UNAVAILABLE")
            _atomic_json(pending, _resign(job, keyring_path))
            running = _job_file(queue, "running", pending.name)
            replace_with_retry(pending, running)
        _crash("AFTER_CLAIM")
        processed += 1
        try:
            if job["event"].get("project_id") != job["project_id"] or job["event"].get("repo_fingerprint") != job["repo_fingerprint"]:
                raise SealQueueError("JOB_PROJECT_BINDING_MISMATCH")
            _crash("BEFORE_APPEND")
            append_event(event_path, job["event"], deduplicate_event_id=True)
            _crash("AFTER_APPEND")
            seal = seal_event_chain(event_path, keyring_path=keyring_path)
            _crash("AFTER_SEAL")
            with OwnerTokenLock(queue / "queue-state", timeout=2.0):
                current = _verify(_load(running), keyring_path)
                if int(current.get("lease_epoch") or 0) != job["lease_epoch"]:
                    raise SealQueueError("JOB_LEASE_MISMATCH")
                current.update(state="done", lease_pid=0, lease_process_identity="", error_code="NONE",
                               completion={"seal_status": seal["seal_status"],
                                           "sealed_record_count": seal["sealed_record_count"]})
                _atomic_json(running, _resign(current, keyring_path)); _crash("BEFORE_ACK")
                replace_with_retry(running, _job_file(queue, "done", running.name))
            completed += 1
        except Exception as exc:
            code = str(exc) if isinstance(exc, SealQueueError) and re.fullmatch(r"[A-Z0-9_]+", str(exc)) else "WORKER_OPERATION_FAILED"
            with OwnerTokenLock(queue / "queue-state", timeout=2.0):
                if not running.exists():
                    continue
                current = _load(running)
                current.update(state="dead-letter" if int(current.get("attempt") or 0) >= 3 else "pending",
                               lease_pid=0, lease_process_identity="", error_code=code)
                _atomic_json(running, _resign(current, keyring_path))
                target_state = str(current["state"])
                replace_with_retry(running, _job_file(queue, target_state, running.name))
                if target_state == "dead-letter": dead += 1
                else: retried += 1
    return {"ok": dead == 0, "processed": processed, "completed": completed,
            "retried": retried, "dead_letter": dead}


def launch_worker(plugin_root: Path, queue: Path, keyring_path: Optional[Path] = None) -> Dict[str, Any]:
    script = Path(plugin_root) / "hooks" / "seal_worker.py"
    command = [sys.executable, str(script), "--queue", str(queue), "--max-jobs", "100"]
    if keyring_path is not None:
        command.extend(["--keyring", str(keyring_path)])
    kwargs: Dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                              "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                                   | getattr(subprocess, "DETACHED_PROCESS", 0)
                                   | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    wait_ms = int(os.environ.get("CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS", "0") or "0")
    if wait_ms > 0:
        try:
            exit_code = process.wait(timeout=min(wait_ms, 2500) / 1000.0)
        except subprocess.TimeoutExpired:
            return {"launched": True, "worker_pid": process.pid, "test_wait_status": "TIMEOUT"}
        return {"launched": True, "worker_pid": process.pid, "test_wait_status": "EXITED",
                "worker_exit_code": exit_code}
    return {"launched": True, "worker_pid": process.pid, "test_wait_status": "NOT_REQUESTED"}
