"""中文：为逻辑任务冻结原生人类输入引用，不保存提示正文或自动判定新任务。
English: Freeze native human-input references without storing prompt bodies or deciding task semantics.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from .capability_store import bounded_read, safe_path
from .common import RuntimeContractError, atomic_write_json, parse_iso, read_json, resolve_codex_home, utc_now, verify_record
from .event_v2 import OwnerTokenLock, project_identity_for
from .g6_allowance_authority import _native_header
from .path_identity import same_path
from .routing_contract import RoutingError, _constant, _object, exact, fail, ref

MAX_WINDOW = 2_000_000
MAX_RECORD = 1_048_576
ORIGIN = re.compile(r"TO1-[0-9a-f]{32}")
SOURCE_FIELDS = {"schema_version", "session_ref", "repo_path", "identity", "transcript_path",
                 "transcript_path_ref", "transcript_file_ref", "header_ref", "anchor", "observed_at"}
ORIGIN_FIELDS = {"schema_version", "origin_ref", "source", "session_ref", "repo_path", "identity",
                 "transcript_path", "transcript_path_ref", "transcript_file_ref", "header_ref",
                 "message_ref", "turn_ref", "native_turn_id", "text_ref", "record_ref",
                 "start", "end", "submitted_at", "kind"}
CONTROL = {"继续", "继续执行", "好的", "好", "确认", "同意", "批准", "yes", "ok", "continue"}
OBSERVATION_CODES = {"LINK_REJECTED", "PATH_UNREADABLE", "TASK_NATIVE_HOME_IDENTITY",
    "TASK_NATIVE_LOCATOR_FIELDS_MISSING", "TASK_SOURCE_CHANGED", "TASK_SOURCE_REPLACED",
    "TASK_SOURCE_IDENTITY", "TASK_SOURCE_FIELDS", "TASK_NATIVE_LOCATOR_IDENTITY",
    "G6_ALLOWANCE_NATIVE_SOURCE_PATH", "G6_ALLOWANCE_NATIVE_SOURCE_IDENTITY",
    "V5_ABSOLUTE_PATH_REQUIRED", "V5_REPARSE_PATH_DENIED", "V5_FILE_REQUIRED",
    "V5_ALTERNATE_STREAM_DENIED", "CONTEXT_V2_TRANSCRIPT_FILE_IDENTITY", "V5_CHILD_HEADER_BOUND",
    "TASK_NATIVE_LOCATOR_OBSERVATION_FAILED"}
OBSERVATION_CODES.update({"TASK_MATCHING_INSTALLED_READER_REQUIRED", "TASK_WORKSPACE_HANDOFF_REQUIRED",
    "TASK_WORKSPACE_BOUND_ROOT", "WORKSPACE_TURN_REQUIRED", "WORKSPACE_CONTEXT_UNAVAILABLE",
    "WORKSPACE_CONTEXT_IDENTITY", "WORKSPACE_CONTEXT_CHANGED", "WORKSPACE_SOURCE_REPLACED",
    "WORKSPACE_PROOF_FIELDS", "WORKSPACE_PROOF_IDENTITY", "WORKSPACE_PROOF_REFERENCE"})


def _directory(session: str, cwd: Path | None = None) -> Path:
    if not isinstance(session, str) or not 0 < len(session) <= 256:
        fail("TASK_SOURCE_SESSION")
    base = safe_path(resolve_codex_home() / "cp-assistant/g6-routing/task-origins" / ref(session)[7:])
    if cwd is not None:
        workspace = safe_path(base / "workspaces" / ref(_identity(cwd))[7:])
        if workspace.exists():
            return workspace
    return base


def _identity(cwd: Path) -> dict:
    fingerprint, project_id = project_identity_for(str(cwd))
    return {"project_id": project_id, "repo_fingerprint": fingerprint}


def _native_transcript_path(value: str) -> Path:
    """中文：父、子来源共用账户别名核验。English: Share account-alias checks with child readers."""
    from .native_transcript import transcript_path
    try:
        return transcript_path(Path(value).expanduser().absolute())
    except RoutingError as exc:
        if str(exc) == "V5_REPARSE_PATH_DENIED":
            from .capability_store import CapabilityError
            raise CapabilityError("LINK_REJECTED") from None
        raise


def observe(data: Mapping[str, Any]) -> dict | None:
    """中文：原生父Hook只绑定来源位置；不创建任务或预算。
    English: A native parent Hook binds the source locator, never a task or budget.
    """
    if data.get("agent_id") or data.get("hook_event_name") not in {"UserPromptSubmit", "PreToolUse"}:
        return None
    session, cwd, transcript = (data.get(key) for key in ("session_id", "cwd", "transcript_path"))
    if not all(isinstance(value, str) and value for value in (session, cwd, transcript)):
        return None
    value, _ = _bind_source(session, Path(cwd), _native_transcript_path(transcript),
                            refresh_anchor=data["hook_event_name"] == "UserPromptSubmit")
    return value


def observe_native_locator(data: Mapping[str, Any]) -> dict | None:
    """中文：只由原生父 PreToolUse 保存宿主定位；管理入口不能创建此证明。
    English: Only native parent PreToolUse captures the host locator; management commands cannot create this proof.
    """
    if data.get("agent_id") or data.get("agentId") or data.get("hook_event_name") != "PreToolUse":
        return None
    keys = ("session_id", "cwd", "transcript_path", "turn_id", "tool_use_id")
    if not all(isinstance(data.get(key), str) and data[key] for key in keys):
        return None
    session, cwd = data["session_id"], Path(data["cwd"])
    transcript = _native_transcript_path(data["transcript_path"])
    call_ref = ref([session, data["turn_id"], data["tool_use_id"]])
    try:
        value, _ = _bind_source(session, cwd, transcript, refresh_anchor=True, locator=True,
                               native_call_ref=call_ref)
    except RoutingError as exc:
        if str(exc) != "G6_ALLOWANCE_NATIVE_SOURCE_IDENTITY":
            raise
        value = _bind_workspace_locator(session, cwd, transcript, data["turn_id"], call_ref)
    return value


def _binding_header(value: Mapping[str, Any], session: str, cwd: Path) -> tuple[dict, dict]:
    if "workspace_proof" in value:
        from .native_workspace import verify
        return verify(Path(value["transcript_path"]), value["workspace_proof"], session_id=session, cwd=cwd)
    return _native_header(Path(value["transcript_path"]), session_id=session, cwd=cwd)


def _bind_workspace_locator(session: str, cwd: Path, transcript: Path, turn: str, call_ref: str) -> dict:
    """中文：首次选定项目采用新来源格式，保留 v1 和预算原始记录。
    English: First project selection uses a new source format, never rewriting v1 or budgets.
    """
    import subprocess
    from . import g6_default_activation as activation, g6_task_scope as scope
    from .g6_runtime_support import installed_task_scope_support
    from .native_transcript import session_header
    from .native_workspace import observe as workspace_observe, verify as workspace_verify
    if not installed_task_scope_support()["supported"]:
        fail("TASK_MATCHING_INSTALLED_READER_REQUIRED")
    cwd, transcript = safe_path(cwd), safe_path(transcript)
    header, binding = session_header(transcript, session_id=session)
    base = _directory(session)
    directory = safe_path(base / "workspaces" / ref(_identity(cwd))[7:])
    locator_path = directory / "native-locator.json"
    admitted = locator_path.exists() or (directory / "source.json").exists()
    if admitted:
        _read_binding(session, cwd, locator=locator_path.exists())
    else:
        initial = safe_path(Path(header["payload"]["cwd"]))
        # 中文：Git 探测失败不能证明无仓库；残缺或无权访问的 Git 边界同样禁止静默切换。
        # English: A failing Git probe cannot establish a non-repository; incomplete/inaccessible boundaries still prohibit handoff.
        for parent in (initial, *initial.parents):
            try:
                (parent / ".git").lstat()
            except FileNotFoundError:
                continue
            fail("TASK_WORKSPACE_HANDOFF_REQUIRED")
        # 中文：已有 Git 项目间的切换需要任务交接，不能用无活跃预算代替。
        # English: A Git-to-Git transition is a separate task handoff, even with no active budget.
        probe = subprocess.run(["git", "-C", str(initial), "rev-parse", "--show-toplevel"],
                               stdin=subprocess.DEVNULL, capture_output=True, timeout=3)
        if probe.returncode == 0 or not initial.is_dir():
            fail("TASK_WORKSPACE_HANDOFF_REQUIRED")
        if (any(activation.resolve(session_id=session, cwd=path)["status"] != "NEW_TASK_DEFAULT"
                for path in (initial, cwd)) or (base.parent.parent / "roots" / (ref(session)[7:] + ".jsonl")).exists()):
            fail("TASK_WORKSPACE_BOUND_ROOT")
    previous = _read_binding(session, cwd, locator=True) if locator_path.exists() else None
    if previous is not None and previous["workspace_proof"]["turn_id"] == turn:
        proof = previous["workspace_proof"]
        workspace_verify(transcript, proof, session_id=session, cwd=cwd)
    else:
        proof = workspace_observe(transcript, session_id=session, turn_id=turn, cwd=cwd)
    if ref(header) != proof["header_ref"] or any(proof[key] != item for key, item in binding.items()):
        fail("TASK_SOURCE_CHANGED")
    fixed = {"schema_version": "g6-task-native-locator/2", "session_ref": ref(session),
             "repo_path": str(cwd), "identity": _identity(cwd), "transcript_path": str(transcript),
             **binding, "header_ref": ref(header), "workspace_proof": proof, "native_call_ref": call_ref,
             "anchor": transcript.stat().st_size, "observed_at": utc_now()}
    directory.mkdir(parents=True, exist_ok=True)
    # 中文：与任务选择共用会话锁；观察只读取有界登记，不重放预算。
    # English: Share the selection lock; observation reads bounded metadata without replaying budgets.
    with OwnerTokenLock(scope.legacy.pointer_for(session), timeout=2), OwnerTokenLock(locator_path, timeout=2):
        owner = scope._registry_unlocked(session)
        if (not admitted and scope.legacy.pointer_for(session).exists()
                or owner is None and scope.legacy.pointer_for(session).exists()
                or owner is not None and (not same_path(Path(owner["repo_path"]), cwd)
                                          or owner["project_identity"] != _identity(cwd))):
            fail("TASK_WORKSPACE_BOUND_ROOT")
        workspace_verify(transcript, proof, session_id=session, cwd=cwd)
        if locator_path.exists():
            current = _read_binding_at(locator_path, session, cwd, locator=True)
            if any(current[key] != fixed[key] for key in ("header_ref", "transcript_path_ref", "transcript_file_ref")):
                fail("TASK_SOURCE_REPLACED")
            if current["workspace_proof"]["start"] > proof["start"]:
                return current
        atomic_write_json(locator_path, fixed, seal=True)
    return fixed


def record_locator_failure(data: Mapping[str, Any], error: Exception) -> None:
    """中文：仅保存观察失败码和字段存在性；诊断不能作为来源或授权。
    English: Retain only observation failure codes and field presence; diagnostics never establish provenance or authority.
    """
    session = data.get("session_id")
    if data.get("agent_id") or data.get("agentId") or not isinstance(session, str) or not session:
        return
    code = str(error)
    if code not in OBSERVATION_CODES:
        code = "TASK_NATIVE_LOCATOR_OBSERVATION_FAILED"
    fields = ("session_id", "cwd", "transcript_path", "turn_id", "tool_use_id")
    value = {"schema_version": "g6-native-locator-diagnostic/1", "session_ref": ref(session),
             "reason_code": code, "observed_at": utc_now(),
             "fields_present": {key: isinstance(data.get(key), str) and bool(data[key]) for key in fields}}
    path = _directory(session) / "observation-diagnostic.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, value, seal=True)


def _bind_source(session: str, cwd: Path, transcript: Path, *, refresh_anchor: bool,
                 locator: bool = False, native_call_ref: str | None = None) -> tuple[dict, bool]:
    """中文：Hook 与显式读回共用同一身份检查；恢复不冒充 Hook 事件。
    English: Hooks and explicit readback share identity checks; recovery never fabricates a Hook event.
    """
    cwd, source = safe_path(cwd), safe_path(transcript)
    # 中文：无效来源不得创建持久化状态目录。
    # English: Invalid sources must not create persistent state directories.
    _native_header(source, session_id=session, cwd=cwd)
    path = _directory(session) / ("native-locator.json" if locator else "source.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=2):
        header, binding = _native_header(source, session_id=session, cwd=cwd)
        with source.open("rb") as stream:
            opened = os.fstat(stream.fileno())
        if ref({"device": opened.st_dev, "inode": opened.st_ino}) != binding["transcript_file_ref"]:
            fail("TASK_SOURCE_CHANGED")
        fixed = {"schema_version": "g6-task-native-locator/1" if locator else "g6-task-native-source/1", "session_ref": ref(session),
                 "repo_path": str(cwd), "identity": _identity(cwd), "transcript_path": str(source),
                 **binding, "header_ref": ref(header)}
        if locator:
            fixed["native_call_ref"] = native_call_ref
        created = not path.exists()
        if path.exists():
            previous = _read_binding_at(path, session, cwd, locator=locator)
            fixed["identity"] = _identity(Path(previous["repo_path"]))
            # 中文：路径别名必须指向同一实体，其他身份和内容指纹仍需完全一致。
            # English: Path aliases must name the same entity; every other identity and content digest stays exact.
            locations = ("repo_path", "transcript_path")
            if (any(previous[key] != value for key, value in fixed.items() if key not in (*locations, "native_call_ref"))
                    or any(not same_path(Path(previous[key]), Path(fixed[key])) for key in locations)):
                fail("TASK_SOURCE_REPLACED")
            if not refresh_anchor:
                return previous, False
            fixed.update({key: previous[key] for key in locations})
        current = safe_path(source).stat()
        if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino) or current.st_size < opened.st_size:
            fail("TASK_SOURCE_CHANGED")
        value = {**fixed, "anchor": opened.st_size, "observed_at": utc_now()}
        atomic_write_json(path, value, seal=True)
    return value, created


def recover_source(session: str, cwd: Path, transcript: Path | None = None) -> dict:
    """中文：只消费宿主 Hook 已登记的定位；调用方路径只能交叉核验，不能授予来源资格。
    English: Consume a host-observed locator; a caller path can cross-check it but cannot establish provenance.
    """
    from .g6_runtime_support import installed_task_scope_support
    if not installed_task_scope_support()["supported"]:
        fail("TASK_MATCHING_INSTALLED_READER_REQUIRED")
    locator = _read_binding(session, safe_path(cwd), locator=True)
    trusted_path = Path(locator["transcript_path"])
    if transcript is not None and not same_path(safe_path(transcript), trusted_path):
        fail("TASK_SOURCE_REPLACED")
    if locator["schema_version"] == "g6-task-native-locator/2":
        target = _directory(session, cwd) / "source.json"
        with OwnerTokenLock(target, timeout=2):
            _binding_header(locator, session, cwd)
            created = not target.exists()
            if created:
                value = {key: item for key, item in locator.items() if key != "native_call_ref"}
                value["schema_version"] = "g6-task-native-source/2"
                atomic_write_json(target, value, seal=True)
            else:
                value = _read_binding_at(target, session, cwd)
    else:
        value, created = _bind_source(session, cwd, trusted_path, refresh_anchor=False)
    return {"schema_version": "g6-task-source-recovery/1",
            "status": "RECOVERED" if created else "ALREADY_BOUND",
            "provenance": "native_hook_locator_readback", "session_ref": value["session_ref"],
            "native_call_ref": locator["native_call_ref"],
            "source_ref": value["transcript_file_ref"], "next_action": "task_scope_origins",
            "host_enforcement": "UNVERIFIED", "execution_authorization": "NONE"}


def diagnose(session: str, cwd: Path, *, error: Exception | None = None) -> dict:
    """中文：返回只读且不含正文的恢复指引；登记存在不能证明宿主已执行。
    English: Return read-only, body-free recovery guidance; registration does not prove host execution.
    """
    present = False
    try:
        present = (_directory(session, cwd) / "source.json").exists()
        _read_source(session, safe_path(cwd))
    except (OSError, ValueError, RuntimeContractError) as exc:
        error = error or exc
    reason = "TASK_NATIVE_SOURCE_AVAILABLE" if error is None else str(error)
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,95}", reason):
        reason = "TASK_SOURCE_READ_FAILED"
    locator_available = False
    try:
        _read_binding(session, safe_path(cwd), locator=True)
        locator_available = True
    except (OSError, ValueError, RuntimeContractError):
        pass
    hooks = resolve_codex_home() / "hooks.json"
    registration = "MISSING"
    try:
        if hooks.exists():
            value = json.loads(bounded_read(hooks, 262_144), object_pairs_hook=_object, parse_constant=_constant)
            events = value.get("hooks", {})
            commands = [item.get("command", "") for name in ("UserPromptSubmit", "PreToolUse")
                        for group in events.get(name, []) for item in group.get("hooks", [])]
            registration = "REGISTERED_UNVERIFIED" if any("cp_hook.py" in item or "cp_context.py" in item for item in commands) else "NOT_REGISTERED"
    except (OSError, ValueError, RuntimeContractError, AttributeError, TypeError):
        registration = "UNREADABLE"
    observation = None
    try:
        diagnostic = _directory(session) / "observation-diagnostic.json"
        if not locator_available and diagnostic.exists():
            record = json.loads(bounded_read(diagnostic, 4096), object_pairs_hook=_object, parse_constant=_constant)
            verify_record(record, "native observation diagnostic")
            presence = record.get("fields_present")
            stamp = record.get("observed_at")
            if (record.get("schema_version") == "g6-native-locator-diagnostic/1" and record.get("session_ref") == ref(session)
                    and record.get("reason_code") in OBSERVATION_CODES and isinstance(presence, dict)
                    and set(presence) == {"session_id", "cwd", "transcript_path", "turn_id", "tool_use_id"}
                    and all(type(item) is bool for item in presence.values()) and isinstance(stamp, str) and len(stamp) <= 64):
                parse_iso(stamp)
                observation = {key: record.get(key) for key in ("reason_code", "fields_present", "observed_at")}
    except (OSError, ValueError, RuntimeContractError):
        pass
    action = ("continue_existing_task" if error is None else
              "repair_matching_installation" if reason == "TASK_MATCHING_INSTALLED_READER_REQUIRED" else
              "recover_existing_native_source" if reason == "TASK_NATIVE_SOURCE_UNAVAILABLE" and locator_available else
              ("inspect_native_hook_metadata" if observation else "verify_hook_execution") if registration == "REGISTERED_UNVERIFIED"
              and reason in {"TASK_NATIVE_SOURCE_UNAVAILABLE", "TASK_NATIVE_LOCATOR_UNAVAILABLE"} else "repair_hook_registration"
              if reason in {"TASK_NATIVE_SOURCE_UNAVAILABLE", "TASK_NATIVE_LOCATOR_UNAVAILABLE"} else
              "inspect_existing_source_integrity" if present else
              "inspect_native_source_identity")
    return {"schema_version": "g6-task-source-diagnostic/1",
            "status": "AVAILABLE" if error is None else "UNAVAILABLE" if reason in {"TASK_NATIVE_SOURCE_UNAVAILABLE", "TASK_NATIVE_LOCATOR_UNAVAILABLE"} else "BLOCKED",
            "reason_code": reason, "hooks_registration": registration,
            "next_action": action, "recovery_command": "task-scope-recover-source" if locator_available and not present else None,
            "native_locator_available": locator_available,
            "last_native_observation": observation,
            "recovery_requires": ["matching_installed_reader", "registered_native_parent_locator"],
            "installation_action": "verify_hook_execution" if registration == "REGISTERED_UNVERIFIED" else "repair_hook_registration",
            "repeat_user_input_required": False, "host_enforcement": "UNVERIFIED",
            "execution_authorization": "NONE"}


def _read_source(session: str, cwd: Path) -> dict:
    return _read_binding(session, cwd)


def _read_binding(session: str, cwd: Path, *, locator: bool = False) -> dict:
    path = _directory(session, cwd) / ("native-locator.json" if locator else "source.json")
    if not path.exists():
        fail("TASK_NATIVE_LOCATOR_UNAVAILABLE" if locator else "TASK_NATIVE_SOURCE_UNAVAILABLE")
    # 中文：Windows 普通读取句柄可能阻止原子替换；读写共享同一来源锁。
    # English: Windows read handles can prevent atomic replacement; readers and writers share the source lock.
    with OwnerTokenLock(path, timeout=2):
        return _read_binding_at(path, session, cwd, locator=locator)


def _read_binding_at(path: Path, session: str, cwd: Path, *, locator: bool = False) -> dict:
    """中文：调用方已持有该来源锁，路径在加锁前已冻结。
    English: The caller holds this source lock; its path was frozen before locking.
    """
    value = json.loads(bounded_read(path, 16_384), object_pairs_hook=_object, parse_constant=_constant)
    verify_record(value, "native task source")
    value.pop("integrity")
    version = 2 if "workspace_proof" in value else 1
    exact(value, SOURCE_FIELDS | ({"native_call_ref"} if locator else set())
          | ({"workspace_proof"} if version == 2 else set()), "TASK_SOURCE_FIELDS")
    expected_schema = ("g6-task-native-locator/" if locator else "g6-task-native-source/") + str(version)
    if locator and (not isinstance(value["native_call_ref"], str) or re.fullmatch(r"sha256:[0-9a-f]{64}", value["native_call_ref"]) is None):
        fail("TASK_NATIVE_LOCATOR_IDENTITY")
    if (value["schema_version"] != expected_schema or value["session_ref"] != ref(session)
            or not same_path(Path(value["repo_path"]), cwd)
            or value["identity"] != _identity(Path(value["repo_path"]))
            or type(value["anchor"]) is not int or value["anchor"] < 0):
        fail("TASK_SOURCE_IDENTITY")
    header, binding = _binding_header(value, session, cwd)
    if ref(header) != value["header_ref"] or any(value[key] != item for key, item in binding.items()):
        fail("TASK_SOURCE_REPLACED")
    return value


def _human(record: Mapping[str, Any]) -> tuple[str, str, str] | None:
    payload = record.get("payload", {})
    if (record.get("type") != "response_item" or not isinstance(payload, dict)
            or payload.get("type") != "message" or payload.get("role") != "user"
            or not isinstance(payload.get("id"), str) or not payload["id"]):
        return None
    meta, content = payload.get("internal_chat_message_metadata_passthrough"), payload.get("content")
    if not isinstance(meta, dict) or not isinstance(content, list) or not 0 < len(content) <= 16:
        return None
    kinds = meta.get("content_item_kinds")
    if (not isinstance(kinds, list) or not kinds or len(kinds) > 16
            or any(kind not in {"user.text", "user.image"} for kind in kinds)
            or "user.text" not in kinds or not isinstance(meta.get("turn_id"), str) or not meta["turn_id"]):
        return None
    texts = []
    for item in content:
        if not isinstance(item, dict) or item.get("type") not in {"input_text", "input_image"}:
            return None
        if item["type"] == "input_text":
            if not isinstance(item.get("text"), str):
                return None
            texts.append(item["text"])
    text = "\n".join(texts)
    if not text.strip() or len(text.encode("utf-8")) > 131_072:
        return None
    return payload["id"], meta["turn_id"], text


def _kind(text: str) -> str:
    if text.strip().startswith("<send_user_message_question_reply>"):
        return "control_reply"
    if text.strip().lower().rstrip("。.!") in CONTROL:
        return "continuation_hint"
    return "goal_candidate"


def prepare(session: str, cwd: Path, *, before_byte: int | None = None) -> dict:
    """中文：读取提交位置附近的有界完整行，冻结引用供主Agent作语义判断。
    English: Freeze bounded complete records near submission for the coordinator's semantic decision.
    """
    cwd = safe_path(cwd)
    try:
        source = _read_source(session, cwd)
    except RoutingError as exc:
        if str(exc) != "TASK_NATIVE_SOURCE_UNAVAILABLE" or not (_directory(session, cwd) / "native-locator.json").exists():
            raise
        recover_source(session, cwd)
        source = _read_source(session, cwd)
    anchor = source["anchor"]
    workspace_proof = source.get("workspace_proof")
    if (_directory(session, cwd) / "native-locator.json").exists():
        locator = _read_binding(session, cwd, locator=True)
        if any(locator[key] != source[key] for key in ("header_ref", "transcript_file_ref", "transcript_path_ref")):
            fail("TASK_SOURCE_REPLACED")
        anchor = max(anchor, locator["anchor"])
        workspace_proof = locator.get("workspace_proof")
    path = Path(source["transcript_path"])
    origins = []
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if opened.st_size < anchor:
            fail("TASK_SOURCE_TRUNCATED")
        if before_byte is not None and (type(before_byte) is not int or not 0 < before_byte <= opened.st_size):
            fail("TASK_SOURCE_SCAN_CURSOR")
        end = min(opened.st_size, anchor + 262_144) if before_byte is None else before_byte
        start = max(0, end - MAX_WINDOW)
        window_start = start
        stream.seek(start)
        raw = stream.read(end - start)
        after = os.fstat(stream.fileno())
    if ((opened.st_dev, opened.st_ino) != (after.st_dev, after.st_ino)
            or after.st_size < opened.st_size
            or ref({"device": opened.st_dev, "inode": opened.st_ino}) != source["transcript_file_ref"]):
        fail("TASK_SOURCE_CHANGED")
    if start:
        boundary = raw.find(b"\n")
        drop = len(raw) if boundary < 0 else boundary + 1
        start, raw = start + drop, raw[drop:]
    offset = start
    workspace_contexts = {}
    context_lookups, contexts_missing = 0, 0
    if workspace_proof is not None:
        from .native_workspace import observe as observe_workspace
    for line in raw.splitlines(keepends=True):
        here, offset = offset, offset + len(line)
        if not line.endswith(b"\n") or len(line) > MAX_RECORD:
            continue
        record = json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
        human = _human(record)
        if human is None:
            continue
        message_id, turn, text = human
        candidate_workspace = None
        if workspace_proof is not None:
            if turn == workspace_proof["turn_id"]:
                candidate_workspace = workspace_proof
            elif turn in workspace_contexts:
                candidate_workspace = workspace_contexts[turn]
            elif context_lookups < 4:
                context_lookups += 1
                try:
                    candidate_workspace = observe_workspace(path, session_id=session, turn_id=turn, cwd=cwd,
                                                            before_byte=min(opened.st_size, offset + 131_072))
                except RoutingError as exc:
                    if str(exc) not in {"WORKSPACE_CONTEXT_UNAVAILABLE", "WORKSPACE_CONTEXT_IDENTITY"}:
                        raise
                workspace_contexts[turn] = candidate_workspace
            if candidate_workspace is None:
                contexts_missing += 1
                continue
            if any(candidate_workspace[key] != source[key] for key in ("header_ref", "transcript_path_ref", "transcript_file_ref")):
                fail("TASK_SOURCE_CHANGED")
        stamp = record.get("timestamp")
        if not isinstance(stamp, str):
            continue
        parse_iso(stamp)
        message_ref = ref([ref(session), message_id])
        origin_ref = "TO1-" + message_ref[7:39]
        value = {"schema_version": "g6-native-task-origin/1", "origin_ref": origin_ref,
                 "source": "native-parent-message", "session_ref": ref(session),
                 "repo_path": source["repo_path"], "identity": source["identity"], "message_ref": message_ref,
                 "turn_ref": ref(turn), "native_turn_id": turn, "text_ref": ref(text),
                 "record_ref": "sha256:" + hashlib.sha256(line).hexdigest(), "start": here, "end": offset,
                 "submitted_at": stamp, "kind": _kind(text),
                 **{key: source[key] for key in ("transcript_path", "transcript_path_ref",
                                               "transcript_file_ref", "header_ref")}}
        if candidate_workspace is not None:
            value.update(schema_version="g6-native-task-origin/2", workspace_proof=candidate_workspace)
        target = _directory(session, cwd) / (origin_ref + ".json")
        with OwnerTokenLock(target, timeout=2):
            if target.exists():
                old = json.loads(bounded_read(target, 16_384), object_pairs_hook=_object, parse_constant=_constant)
                verify_record(old, "native task origin")
                old.pop("integrity")
                if old != value:
                    fail("TASK_ORIGIN_CONFLICT")
            else:
                atomic_write_json(target, value, seal=True)
        origins.append({"origin_ref": origin_ref, "turn_ref": value["turn_ref"],
                        "submitted_at": stamp, "kind": value["kind"], "text_ref": value["text_ref"]})
    next_before = (start if start < end else window_start) if window_start else None
    result = {"schema_version": "g6-task-origin-view/1", "origins": origins[-16:],
            "latest_goal_candidate": next((item for item in reversed(origins)
                                           if item["kind"] == "goal_candidate"), None),
            "bytes_read": len(raw), "next_before_byte": next_before,
            "next_action": "select_existing_origin" if origins else
                           "scan_previous_native_records" if next_before else "native_human_source_not_found",
            "repeat_user_input_required": False, "execution_authorization": "NONE"}
    if workspace_proof is not None:
        result.update(workspace_context_lookups=context_lookups, workspace_context_lookup_limit=4,
                      workspace_contexts_missing=contexts_missing)
        if not origins and not next_before and contexts_missing:
            result["next_action"] = "inspect_bounded_native_workspace_context"
    return result


def read_origin(session: str, cwd: Path, origin_ref: str) -> dict:
    """中文：重读原始片段和身份，缓存或调用方声明不能替代来源。
    English: Recheck source bytes and identity; cached or caller-supplied labels are insufficient.
    """
    if not isinstance(origin_ref, str) or ORIGIN.fullmatch(origin_ref) is None:
        fail("TASK_ORIGIN_REF")
    path = _directory(session, cwd) / (origin_ref + ".json")
    value = json.loads(bounded_read(path, 16_384), object_pairs_hook=_object, parse_constant=_constant)
    verify_record(value, "native task origin")
    value.pop("integrity")
    version = 2 if "workspace_proof" in value else 1
    exact(value, ORIGIN_FIELDS | ({"workspace_proof"} if version == 2 else set()), "TASK_ORIGIN_FIELDS")
    if (value["schema_version"] != "g6-native-task-origin/" + str(version) or value["origin_ref"] != origin_ref
            or value["session_ref"] != ref(session) or not same_path(Path(value["repo_path"]), cwd)
            or value["identity"] != _identity(Path(value["repo_path"]))
            or value["kind"] not in {"goal_candidate", "control_reply", "continuation_hint"}
            or type(value["start"]) is not int or type(value["end"]) is not int
            or value["start"] < 0 or not 0 < value["end"] - value["start"] <= MAX_RECORD):
        fail("TASK_ORIGIN_IDENTITY")
    if version == 2 and (not isinstance(value["workspace_proof"], dict)
                         or value["workspace_proof"].get("turn_id") != value["native_turn_id"]):
        fail("TASK_ORIGIN_IDENTITY")
    header, binding = _binding_header(value, session, cwd)
    if ref(header) != value["header_ref"] or any(value[key] != item for key, item in binding.items()):
        fail("TASK_SOURCE_REPLACED")
    with Path(value["transcript_path"]).open("rb") as stream:
        opened = os.fstat(stream.fileno())
        stream.seek(value["start"])
        raw = stream.read(value["end"] - value["start"])
        if ref({"device": opened.st_dev, "inode": opened.st_ino}) != value["transcript_file_ref"]:
            fail("TASK_SOURCE_REPLACED")
    if "sha256:" + hashlib.sha256(raw).hexdigest() != value["record_ref"]:
        fail("TASK_ORIGIN_CHANGED")
    record = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    human = _human(record)
    if human is None:
        fail("TASK_ORIGIN_NOT_HUMAN")
    message_id, turn, text = human
    if (ref([ref(session), message_id]) != value["message_ref"] or ref(turn) != value["turn_ref"]
            or turn != value["native_turn_id"] or ref(text) != value["text_ref"]
            or _kind(text) != value["kind"] or record.get("timestamp") != value["submitted_at"]):
        fail("TASK_ORIGIN_CHANGED")
    return value
