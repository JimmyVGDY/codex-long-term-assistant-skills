"""TaskOutcomeEvent V2：最小、可验证、默认脱敏的生命周期事件。

该模块只负责本地观测，不授予仓库写入、提交、部署或自修改权限。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

SCHEMA_VERSION = "2.0"
ZERO_HASH = "0" * 64
TERMINAL_OUTCOMES = {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}
EVENT_TYPES = {"TURN_OPENED", "PRE_TOOL_GUARD", "SUBAGENT_STARTED", "SUBAGENT_STOPPED", "TASK_COMPLETED", "SESSION_ENDED"}
SENSITIVE_KEY = re.compile(r"(prompt|content|message|response|completion|patch|diff|code|token|secret|password|authorization|cookie|api.?key|private.?key)", re.I)

class EventContractError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="surrogateescape")).hexdigest()


def _text(value: Any, default: str = "") -> str:
    return str(value).strip() if value is not None else default


def _nonnegative(value: Any, name: str) -> int:
    try:
        result = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise EventContractError("%s 必须是整数" % name) from exc
    if result < 0:
        raise EventContractError("%s 不能为负数" % name)
    return result


def sanitize(value: Any, depth: int = 0) -> Any:
    """仅保留结构化元数据；疑似原文/凭据字段直接丢弃或脱敏。"""
    if depth > 6:
        return "<depth-limit>"
    if isinstance(value, Mapping):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            k = str(key)
            if SENSITIVE_KEY.search(k):
                out[k] = "<redacted>"
            else:
                out[k] = sanitize(item, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [sanitize(item, depth + 1) for item in list(value)[:100]]
    if isinstance(value, str):
        text = value[:2048]
        text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1<redacted>", text)
        text = re.sub(r"(?i)(sk-[A-Za-z0-9_-]{8,})", "<redacted>", text)
        return text
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:512]


def stable_repo_fingerprint(cwd: str) -> str:
    path = Path(cwd or os.getcwd()).expanduser().resolve(strict=False)
    root = path
    probe = path
    while probe.parent != probe:
        if (probe / ".git").exists():
            root = probe
            break
        probe = probe.parent
    remote = ""
    config = root / ".git" / "config"
    try:
        if config.is_file():
            text = config.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r'(?ms)^\s*\[remote\s+"origin"\].*?^\s*url\s*=\s*(.+?)\s*$', text)
            if match:
                remote = match.group(1).strip()
    except OSError:
        pass
    return "sha256:" + sha256_hex(str(root) + "\n" + remote)


def project_id_for(repo_fingerprint: str, cwd: str = "") -> str:
    explicit = os.environ.get("CP_PROJECT_ID", "").strip()
    if explicit and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", explicit):
        return explicit
    path = Path(cwd or os.getcwd()).expanduser().resolve(strict=False)
    root = path
    probe = path
    while probe.parent != probe:
        if (probe / ".git").exists():
            root = probe
            break
        probe = probe.parent
    remote = ""
    config = root / ".git" / "config"
    try:
        if config.is_file():
            text = config.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r'(?ms)^\s*\[remote\s+"origin"\].*?^\s*url\s*=\s*(.+?)\s*$', text)
            if match:
                remote = match.group(1).strip()
    except OSError:
        pass
    source = remote or str(root)
    suffix = sha256_hex(source)[:10]
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", root.name).strip("-._") or "project"
    return (slug[:48] + "-" + suffix)[:128]


def make_event(payload: Mapping[str, Any]) -> Dict[str, Any]:
    event_type = _text(payload.get("event_type")).upper()
    if event_type not in EVENT_TYPES:
        raise EventContractError("未知 event_type: %s" % event_type)
    repo_fingerprint = _text(payload.get("repo_fingerprint"))
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", repo_fingerprint):
        raise EventContractError("repo_fingerprint 非法")
    project_id = _text(payload.get("project_id"))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", project_id):
        raise EventContractError("project_id 非法")
    terminal = _text(payload.get("terminal_outcome"), "UNKNOWN").upper()
    if terminal not in TERMINAL_OUTCOMES:
        terminal = "UNKNOWN"
    event: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": _text(payload.get("event_id")) or ("EVT_" + secrets.token_hex(16)),
        "event_type": event_type,
        "captured_at": _text(payload.get("captured_at")) or utc_now(),
        "captured_by": _text(payload.get("captured_by")) or "codex-hook-v6",
        "session_id": _text(payload.get("session_id"))[:160],
        "turn_id": _text(payload.get("turn_id"))[:160],
        "task_id": _text(payload.get("task_id"))[:160],
        "project_id": project_id,
        "repo_fingerprint": repo_fingerprint,
        "terminal_outcome": terminal,
        "recommended_model": _text(payload.get("recommended_model"))[:128],
        "actual_model": _text(payload.get("actual_model"))[:128],
        "actual_reasoning_effort": _text(payload.get("actual_reasoning_effort"))[:64],
        "recommended_reviewers": _nonnegative(payload.get("recommended_reviewers"), "recommended_reviewers"),
        "actual_reviewers": _nonnegative(payload.get("actual_reviewers"), "actual_reviewers"),
        "blocking_findings": _nonnegative(payload.get("blocking_findings"), "blocking_findings"),
        "nonblocking_findings": _nonnegative(payload.get("nonblocking_findings"), "nonblocking_findings"),
        "repair_rounds": _nonnegative(payload.get("repair_rounds"), "repair_rounds"),
        "duration_ms": _nonnegative(payload.get("duration_ms"), "duration_ms"),
        "metadata": sanitize(payload.get("metadata") or {}),
    }
    return event


class OwnerTokenLock:
    """O_EXCL 锁 + owner token，旧持有者不能删除新锁。"""
    def __init__(self, path: Path, timeout: float = 2.0, stale: float = 120.0) -> None:
        self.path = Path(str(path) + ".lock")
        self.timeout = timeout
        self.stale = stale
        self.token = secrets.token_hex(16)
        self.fd: Optional[int] = None

    def __enter__(self) -> "OwnerTokenLock":
        deadline = time.monotonic() + self.timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(self.fd, canonical_json({"pid": os.getpid(), "token": self.token, "created_at": utc_now()}).encode("utf-8"))
                os.fsync(self.fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > self.stale:
                        current = json.loads(self.path.read_text(encoding="utf-8"))
                        stale_token = current.get("token")
                        owner_pid = int(current.get("pid") or 0)
                        # A slow but live writer must never lose its lock merely
                        # because the wall-clock stale threshold elapsed.
                        if stale_token and owner_pid > 0 and not _pid_is_alive(owner_pid):
                            confirmed = json.loads(self.path.read_text(encoding="utf-8"))
                            if confirmed.get("token") != stale_token:
                                continue
                            self.path.unlink(missing_ok=True)
                            continue
                except (OSError, ValueError, json.JSONDecodeError):
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError("获取事件锁超时")
                time.sleep(0.03)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            finally:
                self.fd = None
        try:
            current = json.loads(self.path.read_text(encoding="utf-8"))
            if current.get("token") == self.token:
                self.path.unlink(missing_ok=True)
        except (OSError, ValueError, json.JSONDecodeError):
            pass


def _last_hash(path: Path) -> str:
    if not path.is_file():
        return ZERO_HASH
    last = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last = line
    if not last:
        return ZERO_HASH
    obj = json.loads(last)
    return _text(obj.get("record_hash"), ZERO_HASH)


def append_event(path: Path, event: Mapping[str, Any], hmac_key: Optional[str] = None) -> Dict[str, Any]:
    validated = make_event(event)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path):
        previous = _last_hash(path)
        envelope = dict(validated)
        envelope["previous_hash"] = previous
        digest = sha256_hex(previous + "\n" + canonical_json(validated))
        envelope["record_hash"] = digest
        if hmac_key:
            envelope["record_hmac_sha256"] = hmac.new(hmac_key.encode("utf-8"), canonical_json(envelope).encode("utf-8"), hashlib.sha256).hexdigest()
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(envelope) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return envelope


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return True  # inability to prove death is fail-closed
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def verify_event_chain(path: Path, hmac_key: Optional[str] = None, allow_duplicate_ids: bool = False) -> Dict[str, Any]:
    previous = ZERO_HASH
    count = 0
    duplicate_count = 0
    seen = set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        obj = json.loads(line)
        if obj.get("previous_hash") != previous:
            raise EventContractError("第 %d 行 previous_hash 不一致" % number)
        record_hash = obj.get("record_hash")
        payload = {k: v for k, v in obj.items() if k not in {"previous_hash", "record_hash", "record_hmac_sha256"}}
        expected = sha256_hex(previous + "\n" + canonical_json(payload))
        if expected != record_hash:
            raise EventContractError("第 %d 行 record_hash 不一致" % number)
        event_id = obj.get("event_id")
        if event_id in seen:
            duplicate_count += 1
            if not allow_duplicate_ids:
                raise EventContractError("event_id 重复: %s" % event_id)
        seen.add(event_id)
        if hmac_key:
            signature = obj.get("record_hmac_sha256")
            unsigned = {k: v for k, v in obj.items() if k != "record_hmac_sha256"}
            expected_hmac = hmac.new(hmac_key.encode("utf-8"), canonical_json(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(_text(signature), expected_hmac):
                raise EventContractError("第 %d 行 HMAC 不一致" % number)
        previous = record_hash
        count += 1
    return {"ok": True, "record_count": count, "head_hash": previous, "duplicate_event_id_count": duplicate_count}


def aggregate_by_task(events: Iterable[Mapping[str, Any]], project_id: str, repo_fingerprint: str) -> Dict[str, Dict[str, Any]]:
    """先 event_id 去重，再按 task_id 聚合；项目或仓库不一致直接拒绝。"""
    result: Dict[str, Dict[str, Any]] = {}
    seen = set()
    for raw in events:
        event = make_event(raw)
        if event["project_id"] != project_id or event["repo_fingerprint"] != repo_fingerprint:
            raise EventContractError("检测到跨项目或跨仓库事件")
        if event["event_id"] in seen:
            continue
        seen.add(event["event_id"])
        task_id = event["task_id"] or event["turn_id"] or event["session_id"] or event["event_id"]
        current = result.setdefault(task_id, {"task_id": task_id, "event_count": 0, "terminal_outcome": "UNKNOWN", "actual_reviewers": 0, "blocking_findings": 0, "nonblocking_findings": 0, "repair_rounds": 0})
        current["event_count"] += 1
        if event["event_type"] == "SUBAGENT_STARTED":
            current["actual_reviewers"] += 1
        if event["event_type"] == "TASK_COMPLETED":
            current["terminal_outcome"] = event["terminal_outcome"]
            current["blocking_findings"] = event["blocking_findings"]
            current["nonblocking_findings"] = event["nonblocking_findings"]
            current["repair_rounds"] = event["repair_rounds"]
    return result
