"""中文：TaskOutcomeEvent V2：最小、可验证、默认脱敏的生命周期事件；仅负责本地观察，不授予仓库写入、提交、部署或环境修改权限。

English: TaskOutcomeEvent V2 provides minimal, verifiable, redacted-by-default lifecycle events. It observes locally and grants no repository write, commit, deployment, or environment-modification authority.
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
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = "2.0"
ZERO_HASH = "0" * 64
TERMINAL_OUTCOMES = {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}
EVENT_TYPES = {"TURN_OPENED", "PRE_TOOL_GUARD", "SUBAGENT_STARTED", "SUBAGENT_STOPPED", "TASK_COMPLETED", "SESSION_ENDED"}
FACT_SOURCES = {"hook-payload", "host-attested-hook-payload", "unavailable"}
REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
KNOWN_CODEX_MODELS = {"gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.5",
                      "gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex-spark"}
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
    """中文：仅保留结构化元数据；疑似原文或凭据字段直接丢弃或脱敏。

    English: Keep only structured metadata; drop or redact fields suspected of containing raw content or credentials.
    """
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
        raise EventContractError("terminal_outcome 非法")
    actual_model = _text(payload.get("actual_model"))[:128]
    actual_effort = _text(payload.get("actual_reasoning_effort")).lower()[:64]
    if actual_model and actual_model not in KNOWN_CODEX_MODELS:
        raise EventContractError("actual_model 非法")
    if actual_effort and actual_effort not in REASONING_EFFORTS:
        raise EventContractError("actual_reasoning_effort 非法")
    sources = {
        "actual_model_source": _text(payload.get("actual_model_source"), "unavailable"),
        "actual_reasoning_effort_source": _text(payload.get("actual_reasoning_effort_source"), "unavailable"),
        "terminal_outcome_source": _text(payload.get("terminal_outcome_source"),
                                         "unavailable"),
    }
    if any(source not in FACT_SOURCES for source in sources.values()):
        raise EventContractError("宿主事实来源非法")
    if sources["actual_model_source"] in {"hook-payload", "host-attested-hook-payload"} and not actual_model:
        raise EventContractError("actual_model 与来源不一致")
    if sources["actual_reasoning_effort_source"] in {"hook-payload", "host-attested-hook-payload"} and not actual_effort:
        raise EventContractError("actual_reasoning_effort 与来源不一致")
    if sources["terminal_outcome_source"] == "hook-payload" and terminal == "UNKNOWN":
        raise EventContractError("terminal_outcome 与来源不一致")
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
        "actual_model": actual_model,
        "actual_reasoning_effort": actual_effort,
        **sources,
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
    """中文：进程拥有的原生文件锁；锁文件保持存在，所有权由操作系统句柄维持，进程终止会释放锁，不依赖删除陈旧文件或 PID 复用判断。

    English: Process-owned native file lock. The lock file remains persistent while ownership lives in the OS handle; process termination releases it without stale-file deletion or PID-reuse checks.
    """
    def __init__(self, path: Path, timeout: float = 2.0, stale: float = 120.0) -> None:
        self.path = Path(str(path) + ".lock")
        self.timeout = timeout
        self.stale = stale
        self.token = secrets.token_hex(16)
        self.handle: Any = None

    def __enter__(self) -> "OwnerTokenLock":
        deadline = time.monotonic() + self.timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw_path = str(self.path.absolute())
        native_path = "\\\\?\\" + raw_path if os.name == "nt" and not raw_path.startswith("\\\\?\\") else raw_path
        try:
            descriptor = os.open(native_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(descriptor, b"0"); os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except FileExistsError:
            pass
        self.handle = open(native_path, "r+b")
        while True:
            try:
                self.handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    self.handle.close()
                    self.handle = None
                    raise TimeoutError("获取事件锁超时")
                time.sleep(0.03)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.handle is not None:
            try:
                self.handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            finally:
                self.handle.close()
                self.handle = None


def _segment_pattern(path: Path) -> re.Pattern[str]:
    return re.compile(r"^%s\.segment-(\d{6})%s$" % (re.escape(path.stem), re.escape(path.suffix)))


def event_segment_paths(path: Path) -> List[Path]:
    path = Path(path)
    pattern = _segment_pattern(path)
    numbered: List[Tuple[int, Path]] = []
    for candidate in path.parent.glob(path.stem + ".segment-*" + path.suffix):
        match = pattern.fullmatch(candidate.name)
        if not match:
            raise EventContractError("事件分段文件名非法: %s" % candidate.name)
        numbered.append((int(match.group(1)), candidate))
    numbered.sort(key=lambda item: item[0])
    expected = list(range(1, len(numbered) + 1))
    actual = [number for number, _ in numbered]
    if actual != expected:
        raise EventContractError("事件分段编号不连续: %s" % actual)
    return [candidate for _, candidate in numbered]


def _quarantine_partial_tail(path: Path) -> Optional[Path]:
    """中文：只恢复活动文件中尚未提交的尾部，不修改历史分段。

    English: Recover only an uncommitted tail in the active file, never a historical segment.
    """
    if not path.is_file():
        return None
    raw = path.read_bytes()
    if not raw or raw.endswith(b"\n"):
        return None
    split = raw.rfind(b"\n")
    prefix = raw[:split + 1] if split >= 0 else b""
    tail = raw[split + 1:] if split >= 0 else raw
    digest = hashlib.sha256(tail).hexdigest()[:16]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    quarantine = path.with_name(path.stem + ".corrupt-tail-" + stamp + "-" + digest + ".bin")
    with quarantine.open("xb") as handle:
        handle.write(tail)
        handle.flush()
        os.fsync(handle.fileno())
    with path.open("r+b") as handle:
        handle.truncate(len(prefix))
        handle.flush()
        os.fsync(handle.fileno())
    return quarantine


def _read_event_files_unlocked(path: Path, *, recover_active_tail: bool = False) -> Tuple[List[Path], List[Dict[str, Any]], Optional[Path]]:
    path = Path(path)
    quarantine = _quarantine_partial_tail(path) if recover_active_tail else None
    files = event_segment_paths(path)
    if path.is_file():
        files.append(path)
    events: List[Dict[str, Any]] = []
    for source in files:
        raw = source.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise EventContractError("事件文件存在未提交尾部: %s" % source)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EventContractError("事件文件不是有效 UTF-8: %s" % source) from exc
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EventContractError("%s 第 %d 行 JSON 无效" % (source.name, number)) from exc
            if not isinstance(value, dict):
                raise EventContractError("%s 第 %d 行不是对象" % (source.name, number))
            value["__event_source_file"] = source.name
            value["__event_source_line"] = number
            events.append(value)
    return files, events, quarantine


_STORED_REQUIRED_FIELDS = {
    "schema_version", "event_id", "event_type", "captured_at", "captured_by", "session_id", "turn_id",
    "task_id", "project_id", "repo_fingerprint", "terminal_outcome", "recommended_model", "actual_model",
    "actual_reasoning_effort", "recommended_reviewers", "actual_reviewers", "blocking_findings",
    "nonblocking_findings", "repair_rounds", "duration_ms", "metadata",
}
_STORED_OPTIONAL_FIELDS = {"actual_model_source", "actual_reasoning_effort_source", "terminal_outcome_source"}


def _validate_stored_payload(payload: Mapping[str, Any], source: str, number: int) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise EventContractError("%s 第 %d 行 schema_version 非法" % (source, number))
    missing = _STORED_REQUIRED_FIELDS - set(payload)
    unknown = set(payload) - _STORED_REQUIRED_FIELDS - _STORED_OPTIONAL_FIELDS
    if missing or unknown:
        raise EventContractError("%s 第 %d 行 schema 字段不完整 missing=%s unknown=%s" %
                                 (source, number, sorted(missing), sorted(unknown)))
    validated = make_event(payload)
    for key, value in payload.items():
        if validated.get(key) != value:
            raise EventContractError("%s 第 %d 行字段非法或未规范化: %s" % (source, number, key))


def _verify_events(events: Iterable[Mapping[str, Any]], hmac_key: Optional[str], allow_duplicate_ids: bool) -> Dict[str, Any]:
    previous = ZERO_HASH
    count = 0
    duplicate_count = 0
    seen = set()
    for obj_with_source in events:
        obj = dict(obj_with_source)
        source = obj.pop("__event_source_file", "event")
        number = obj.pop("__event_source_line", count + 1)
        if obj.get("previous_hash") != previous:
            raise EventContractError("%s 第 %d 行 previous_hash 不一致" % (source, number))
        record_hash = obj.get("record_hash")
        payload = {k: v for k, v in obj.items() if k not in {"previous_hash", "record_hash", "record_hmac_sha256"}}
        _validate_stored_payload(payload, str(source), int(number))
        expected = sha256_hex(previous + "\n" + canonical_json(payload))
        if expected != record_hash:
            raise EventContractError("%s 第 %d 行 record_hash 不一致" % (source, number))
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
                raise EventContractError("%s 第 %d 行 HMAC 不一致" % (source, number))
        previous = record_hash
        count += 1
    return {"ok": True, "record_count": count, "head_hash": previous,
            "duplicate_event_id_count": duplicate_count}


def read_event_chain(path: Path, hmac_key: Optional[str] = None, allow_duplicate_ids: bool = False,
                     *, recover_active_tail: bool = False) -> Dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path):
        files, internal, quarantine = _read_event_files_unlocked(path, recover_active_tail=recover_active_tail)
        verification = _verify_events(internal, hmac_key, allow_duplicate_ids)
        events = [{k: v for k, v in item.items() if not k.startswith("__event_source_")} for item in internal]
        return {**verification, "files": [str(item) for item in files], "events": events,
                "quarantined_tail": str(quarantine) if quarantine else None}


def append_event(path: Path, event: Mapping[str, Any], hmac_key: Optional[str] = None,
                 *, deduplicate_event_id: bool = False,
                 deduplicate_identity_fields: Optional[Sequence[str]] = None,
                 lock_timeout: float = 2.0) -> Dict[str, Any]:
    validated = make_event(event)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=lock_timeout):
        _files, existing, _quarantine = _read_event_files_unlocked(path, recover_active_tail=True)
        # 中文：重复 ID 保持可观察并由聚合策略处理；追加操作仍需扩展其他部分有效的旧事件链。
        # English: Duplicate IDs remain observable and are handled by aggregation policy; append must still extend an otherwise valid legacy chain.
        verification = _verify_events(existing, hmac_key, allow_duplicate_ids=True)
        if deduplicate_event_id:
            for stored in existing:
                if stored.get("event_id") == validated["event_id"]:
                    return {key: value for key, value in stored.items() if not key.startswith("__event_source_")}
        if deduplicate_identity_fields:
            fields = tuple(deduplicate_identity_fields)
            if not fields or any(field not in _STORED_REQUIRED_FIELDS for field in fields):
                raise EventContractError("事件去重身份字段非法")
            for stored in existing:
                if all(stored.get(field) == validated.get(field) for field in fields):
                    return {key: value for key, value in stored.items() if not key.startswith("__event_source_")}
        threshold = int(os.environ.get("CP_ASSISTANT_EVENT_SEGMENT_BYTES", str(8 * 1024 * 1024)))
        if threshold < 256:
            raise EventContractError("事件分段阈值过小")
        if path.is_file() and path.stat().st_size >= threshold and path.stat().st_size > 0:
            number = len(event_segment_paths(path)) + 1
            segment = path.with_name("%s.segment-%06d%s" % (path.stem, number, path.suffix))
            if segment.exists():
                raise EventContractError("事件分段目标已存在: %s" % segment)
            os.replace(path, segment)
            _hard_crash_event("AFTER_SEGMENT_RENAME")
        previous = verification["head_hash"]
        envelope = dict(validated)
        envelope["previous_hash"] = previous
        digest = sha256_hex(previous + "\n" + canonical_json(validated))
        envelope["record_hash"] = digest
        if hmac_key:
            envelope["record_hmac_sha256"] = hmac.new(hmac_key.encode("utf-8"), canonical_json(envelope).encode("utf-8"), hashlib.sha256).hexdigest()
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            serialized = canonical_json(envelope) + "\n"
            hard_point = os.environ.get("CP_ASSISTANT_TEST_EVENT_HARD_CRASH_POINT")
            if hard_point == "MID_RECORD":
                prefix = serialized.encode("utf-8")[:max(1, len(serialized.encode("utf-8")) // 2)]
                handle.buffer.write(prefix)
                handle.flush()
                os.fsync(handle.fileno())
                os._exit(92)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        return envelope


def _hard_crash_event(point: str) -> None:
    if os.environ.get("CP_ASSISTANT_TEST_EVENT_HARD_CRASH_POINT") == point:
        os._exit(92)


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
            # 中文：无法证明进程已退出时失败关闭。
            # English: Inability to prove process exit is fail-closed.
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def verify_event_chain(path: Path, hmac_key: Optional[str] = None, allow_duplicate_ids: bool = False) -> Dict[str, Any]:
    result = read_event_chain(path, hmac_key=hmac_key, allow_duplicate_ids=allow_duplicate_ids)
    return {key: value for key, value in result.items() if key != "events"}


def aggregate_by_task(events: Iterable[Mapping[str, Any]], project_id: str, repo_fingerprint: str) -> Dict[str, Dict[str, Any]]:
    """中文：先按 event_id 去重，再按 task_id 聚合；项目或仓库身份不一致时直接拒绝。

    English: Deduplicate by event_id, then aggregate by task_id; reject mismatched project or repository identity.
    """
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
