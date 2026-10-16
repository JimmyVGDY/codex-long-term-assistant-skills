"""中文：同聊天的逻辑任务选择、不可改写调用归属与旧账本兼容。
English: Logical tasks within a chat, immutable call ownership, and legacy journals.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from . import g6_budget_v1 as budget, g6_handoff_v1 as legacy
from .capability_store import bounded_read, safe_path
from .common import atomic_write_bytes, atomic_write_json, resolve_codex_home, verify_record
from .dispatch_policy import delegation_tool_name
from .event_v2 import OwnerTokenLock
from .g6_task_origin import _identity, read_origin
from .path_identity import same_path
from .routing_contract import _constant, _object, exact, fail, ref

SCHEMA = "g6-task-routing/1"
MAX_TASKS = 128
FIELDS = {"schema_version", "session_ref", "repo_path", "project_identity", "active_scope",
          "scopes", "origins", "legacy_digest"}
ROW_FIELDS = {"scope_ref", "task_id", "ledger_task_id", "ledger_path", "session_ref",
              "repo_path", "identity", "origin_ref", "kind"}
SCOPE = re.compile(r"TS1-[0-9a-f]{32}")
NAME = re.compile(r"t([0-9a-f]{32})_[0-9a-f]{30}")
BILLABLE = {"spawn_agent", "followup_task", "send_input", "resume_agent"}
# 中文：未迁移的单任务聊天保留冻结初始化；子任务头协议没有变化。
# English: Unmigrated single-task chats retain frozen initialization and child headers.
bind = legacy.bind
_child_task_path = legacy._child_task_path


def _home() -> Path:
    return safe_path(resolve_codex_home() / "cp-assistant/g6-routing")


def _sealed(path: Path, limit: int = 524_288) -> dict:
    value = json.loads(bounded_read(safe_path(path), limit), object_pairs_hook=_object, parse_constant=_constant)
    verify_record(value, "task routing")
    value.pop("integrity")
    return value


def _registry_unlocked(session: str) -> dict | None:
    path = legacy.pointer_for(session)
    if not path.exists():
        return None
    value = _sealed(path)
    if value.get("schema_version") == legacy.SCHEMA:
        return None
    exact(value, FIELDS, "TASK_REGISTRY_FIELDS")
    if (value["schema_version"] != SCHEMA or value["session_ref"] != ref(session)
            or not isinstance(value["scopes"], dict) or not 1 <= len(value["scopes"]) <= MAX_TASKS
            or not isinstance(value["origins"], dict) or len(value["origins"]) > 4096
            or value["active_scope"] not in value["scopes"]):
        fail("TASK_REGISTRY_IDENTITY")
    for key, row in value["scopes"].items():
        exact(row, ROW_FIELDS | {"status"}, "TASK_SCOPE_FIELDS")
        if (not SCOPE.fullmatch(key) or row["scope_ref"] != key
                or row["session_ref"] != ref(session) or row["identity"] != value["project_identity"]
                or row["repo_path"] != value["repo_path"] or row["kind"] not in {"legacy", "task"}
                or row["status"] not in {"ACTIVE", "COMPLETE"}):
            fail("TASK_SCOPE_IDENTITY")
    if any(scope not in value["scopes"] for scope in value["origins"].values()):
        fail("TASK_ORIGIN_OWNER")
    if value["legacy_digest"] is not None:
        archived = _legacy_directory(session) / path.name
        if hashlib.sha256(bounded_read(archived, 524_288)).hexdigest() != value["legacy_digest"]:
            fail("TASK_LEGACY_POINTER_CHANGED")
    return value


def registry(session: str) -> dict | None:
    path = legacy.pointer_for(session)
    if not path.exists():
        return None
    with OwnerTokenLock(path, timeout=2):
        return _registry_unlocked(session)


def _legacy_directory(session: str) -> Path:
    return _home() / "legacy-pointers" / ref(session)[7:]


def _check_row(row: Mapping[str, Any], session: str, cwd: Path | None = None) -> dict:
    state = budget.read_budget(safe_path(Path(row["ledger_path"])))
    root = state["root"]
    if (row["session_ref"] != ref(session) or root["host_session_ref"] != ref(session)
            or root["identity"] != row["identity"] or root["task_id"] != row["ledger_task_id"]
            or not same_path(Path(root["repo_path"]), Path(row["repo_path"]))
            or cwd is not None and (not same_path(Path(row["repo_path"]), cwd)
                                    or row["identity"] != _identity(cwd))):
        fail("TASK_BOUND_ROOT_CHANGED")
    return state


def _binding(row: Mapping[str, Any], session: str) -> dict:
    _check_row(row, session)
    return {"new_ledger_path": row["ledger_path"], "repo_path": row["repo_path"],
            "project_identity": row["identity"], "task_scope": row["scope_ref"],
            "task_id": row["task_id"], "old_stop_evidence": None}


def read(session: str, *, task_scope: str | None = None,
         ledger_path: Path | None = None, task_id: str | None = None) -> dict | None:
    """中文：无选择器仅供状态展示；派发必须使用固定范围。
    English: An unqualified read is for display; dispatch requires a fixed scope.
    """
    value = registry(session)
    if value is None:
        binding = legacy.read(session)
        if task_scope is not None:
            fail("TASK_SCOPE_NOT_REGISTERED")
        if binding and ledger_path is not None and not same_path(Path(binding["new_ledger_path"]), ledger_path):
            fail("TASK_LEDGER_NOT_REGISTERED")
        return binding
    rows = list(value["scopes"].values())
    if task_scope is not None:
        rows = [row for row in rows if row["scope_ref"] == task_scope]
    if ledger_path is not None:
        rows = [row for row in rows if same_path(Path(row["ledger_path"]), ledger_path)]
    if task_id is not None:
        rows = [row for row in rows if row["task_id"] == task_id]
    if task_scope is None and ledger_path is None and task_id is None:
        rows = [value["scopes"][value["active_scope"]]]
    if len(rows) != 1:
        fail("TASK_SCOPE_UNKNOWN_OR_CONFLICT")
    return _binding(rows[0], session)


def _scope_ref(identity: dict, task_id: str) -> str:
    if not isinstance(task_id, str) or not 0 < len(task_id) <= 160:
        fail("TASK_ID_REQUIRED")
    return "TS1-" + ref([identity, task_id])[7:39]


def _claim(session: str, cwd: Path, task_id: str, origin: dict,
           existing: Path | None = None, *, freeze: Callable[[], None] | None = None) -> dict:
    identity = origin["identity"]
    scope_ref = _scope_ref(identity, task_id)
    path = _home() / "tasks" / (scope_ref + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=2):
        if path.exists():
            row = _sealed(path, 16_384)
            exact(row, ROW_FIELDS, "TASK_SCOPE_FIELDS")
            if row["scope_ref"] != scope_ref or row["task_id"] != task_id:
                fail("TASK_SCOPE_CONFLICT")
            if row["session_ref"] != ref(session):
                fail("TASK_EXISTING_ROOT_HANDOFF_REQUIRED")
            _check_row(row, session, cwd)
            if existing is not None and not same_path(Path(row["ledger_path"]), existing):
                fail("TASK_LEGACY_ROOT_CONFLICT")
            if freeze is not None:
                freeze()
            return row
        ledger = existing or (_home() / "roots" / (scope_ref + ".jsonl"))
        if ledger.exists():
            root = budget.read_budget(ledger)["root"]
            if (root["host_session_ref"] != ref(session) or root["identity"] != identity
                    or not same_path(Path(root["repo_path"]), cwd)
                    or existing is None and root["task_id"] != task_id):
                fail("TASK_BOUND_ROOT_CHANGED")
        # 中文：归属冲突在冻结前失败；冻结与新根创建共用任务锁。
        # English: Reject ownership conflicts before freezing; freeze and root creation share the task lock.
        if freeze is not None:
            freeze()
        if existing is None:
            budget.initialize(ledger, identity_value=identity, host_session_id=session, repo_path=cwd,
                              task_id=task_id, authorization_ref=ref(["native-task-origin", origin["origin_ref"]]))
        root = budget.read_budget(ledger)["root"]
        row = {"scope_ref": scope_ref, "task_id": task_id, "ledger_task_id": root["task_id"],
               "ledger_path": str(ledger.resolve()), "session_ref": ref(session),
               "repo_path": str(cwd), "identity": identity, "origin_ref": origin["origin_ref"],
               "kind": "legacy" if existing is not None else "task"}
        _check_row(row, session, cwd)
        atomic_write_json(path, row, seal=True)
        return row


def _selection_path(session: str, origin: dict) -> Path:
    return _home() / "task-selections" / ref(session)[7:] / (origin["origin_ref"] + ".json")


def _selection(session: str, origin: dict, value: dict | None,
                      task_id: str, relation: str, task_scope: str | None) -> dict:
    """中文：重放已冻结选择或构建待核验选择；归属核验后才保存。
    English: Replay a frozen choice or construct a pending choice; persist only after ownership checks.
    """
    path = _selection_path(session, origin)
    fixed = {"schema_version": "g6-task-selection/1", "session_ref": ref(session),
             "origin_ref": origin["origin_ref"], "identity": origin["identity"],
             "repo_path": origin["repo_path"]}
    if path.exists():
        choice = _sealed(path, 16_384)
        exact(choice, set(fixed) | {"task_id", "relation", "task_scope"}, "TASK_SELECTION_FIELDS")
        if any(choice[key] != item for key, item in fixed.items()):
            fail("TASK_SELECTION_IDENTITY")
        if choice["relation"] not in {"independent", "continue", "resume"}:
            fail("TASK_SELECTION_RELATION")
        expected = choice["task_scope"] or _scope_ref(choice["identity"], choice["task_id"])
        if not SCOPE.fullmatch(expected) or task_scope is not None and task_scope != expected:
            fail("TASK_ORIGIN_ALREADY_BOUND")
        return choice
    prior = value["origins"].get(origin["origin_ref"]) if value else None
    if prior:
        if task_scope is not None and task_scope != prior:
            fail("TASK_ORIGIN_ALREADY_BOUND")
        task_scope, task_id, relation = prior, value["scopes"][prior]["task_id"], "resume"
    elif value and relation in {"continue", "resume"}:
        matches = [key for key, row in value["scopes"].items() if row["task_id"] == task_id]
        if relation == "resume" and task_scope is None and len(matches) != 1:
            fail("TASK_RESUME_UNKNOWN")
        task_scope = task_scope or (matches[0] if len(matches) == 1 else value["active_scope"])
        if task_scope not in value["scopes"]:
            fail("TASK_SCOPE_NOT_REGISTERED")
        task_id = value["scopes"][task_scope]["task_id"]
    if relation == "independent":
        if origin["kind"] != "goal_candidate":
            fail("TASK_INDEPENDENT_GOAL_SOURCE_REQUIRED")
        if task_scope is not None:
            fail("TASK_NEW_SCOPE_IS_SCRIPT_ASSIGNED")
    _scope_ref(origin["identity"], task_id)
    choice = {**fixed, "task_id": task_id, "relation": relation, "task_scope": task_scope}
    return choice


def select(*, session: str, cwd: Path, task_id: str, origin_ref: str,
           relation: str, task_scope: str | None = None) -> dict:
    """中文：语义由主Agent判断；来源重放、改名及恢复不产生第二份额度。
    English: The coordinator judges semantics; replay, rename and resume never mint another budget.
    """
    from .g6_runtime_support import installed_task_scope_support
    if not installed_task_scope_support()["supported"]:
        fail("TASK_MATCHING_INSTALLED_READER_REQUIRED")
    if relation not in {"independent", "continue", "resume"}:
        fail("TASK_RELATION")
    cwd = safe_path(cwd)
    origin = read_origin(session, cwd, origin_ref)
    pointer = legacy.pointer_for(session)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    # 中文：所有选择与调用冻结使用同一会话锁；账本仍由自己的锁校验并预占。
    # English: Selection and call freezing share one session lock; journals still reserve under their own locks.
    with OwnerTokenLock(pointer, timeout=2):
        value = _registry_unlocked(session)
        choice = _selection(session, origin, value, task_id, relation, task_scope)
        task_id, relation, task_scope = (choice[key] for key in ("task_id", "relation", "task_scope"))
        def freeze() -> None:
            selection = _selection_path(session, origin)
            if not selection.exists():
                atomic_write_json(selection, choice, seal=True)

        if value is None:
            # 中文：旧读取器自带锁，复制后从不可变归档读取。
            # English: Legacy.read owns a lock; read the immutable archive after copying.
            previous = bounded_read(pointer, 524_288) if pointer.exists() else None
            value = {"schema_version": SCHEMA, "session_ref": ref(session), "repo_path": str(cwd),
                     "project_identity": origin["identity"], "active_scope": None,
                     "scopes": {}, "origins": {}, "legacy_digest": None}
            if previous is not None:
                archive = _legacy_directory(session) / pointer.name
                if archive.exists() and bounded_read(archive, 524_288) != previous:
                    fail("TASK_LEGACY_POINTER_CHANGED")
                atomic_write_bytes(archive, previous)
                old = legacy.read(session, directory=archive.parent)
                if not same_path(Path(old["repo_path"]), cwd) or old["project_identity"] != origin["identity"]:
                    fail("TASK_LEGACY_PROJECT_CONFLICT")
                old_ledger = Path(old["new_ledger_path"])
                old_task = task_id if relation == "continue" else budget.read_budget(old_ledger)["root"]["task_id"]
                imported = _claim(session, cwd, old_task, origin, old_ledger,
                                  freeze=freeze if relation == "continue" else None)
                value["scopes"][imported["scope_ref"]] = {**imported, "status": "ACTIVE"}
                value["active_scope"] = imported["scope_ref"]
                value["legacy_digest"] = hashlib.sha256(previous).hexdigest()
            else:
                from .g6_default_activation import resolve
                if resolve(session_id=session, cwd=cwd)["status"] == "LEGACY_ROOT_BOUND":
                    fail("TASK_LEGACY_POLICY_HANDOFF_REQUIRED")
        if not same_path(Path(value["repo_path"]), cwd) or value["project_identity"] != origin["identity"]:
            fail("TASK_PROJECT_CONFLICT")
        prior = value["origins"].get(origin_ref)
        if prior:
            if task_scope is not None and task_scope != prior:
                fail("TASK_ORIGIN_ALREADY_BOUND")
            chosen = prior
        elif relation == "continue" and value["active_scope"] is not None:
            matches = [key for key, row in value["scopes"].items() if row["task_id"] == task_id]
            chosen = task_scope or (matches[0] if len(matches) == 1 else value["active_scope"])
        elif relation == "resume":
            matches = [key for key, row in value["scopes"].items()
                       if (task_scope is not None and key == task_scope)
                       or (task_scope is None and row["task_id"] == task_id)]
            if len(matches) != 1:
                fail("TASK_RESUME_UNKNOWN")
            chosen = matches[0]
        else:
            if origin["kind"] != "goal_candidate":
                fail("TASK_INDEPENDENT_GOAL_SOURCE_REQUIRED")
            if task_scope is not None:
                fail("TASK_NEW_SCOPE_IS_SCRIPT_ASSIGNED")
            row = _claim(session, cwd, task_id, origin, freeze=freeze)
            chosen = row["scope_ref"]
            if chosen not in value["scopes"] and len(value["scopes"]) >= MAX_TASKS:
                fail("TASK_SESSION_INDEX_FULL")
            value["scopes"].setdefault(chosen, {**row, "status": "ACTIVE"})
        if chosen not in value["scopes"]:
            fail("TASK_SCOPE_NOT_REGISTERED")
        _check_row(value["scopes"][chosen], session, cwd)
        freeze()
        value["origins"][origin_ref] = chosen
        if len(value["origins"]) > 4096:
            fail("TASK_SOURCE_INDEX_FULL")
        value["scopes"][chosen]["status"] = "ACTIVE"
        value["active_scope"] = chosen
        atomic_write_json(pointer, value, seal=True)
    return {**_binding(value["scopes"][chosen], session), "relation": relation,
            "semantic_boundary": "coordinator-policy", "execution_authorization": "NONE"}


def namespace(name: str, scope: str | None) -> str:
    if scope is None:
        return name
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", name) or not SCOPE.fullmatch(scope):
        fail("TASK_DISPATCH_NAME")
    match = NAME.fullmatch(name)
    if match:
        if match[1] != scope[4:]:
            fail("TASK_DISPATCH_SCOPE_CONFLICT")
        return name
    return "t" + scope[4:] + "_" + ref(name)[7:37]


def preview_binding(session: str, *, task_scope: str | None = None,
                    ledger_path: Path | None = None) -> dict | None:
    if registry(session) is not None and task_scope is None and ledger_path is None:
        fail("TASK_EXPLICIT_SCOPE_REQUIRED")
    return read(session, task_scope=task_scope, ledger_path=ledger_path)


def name_for_ledger(name: str, ledger: Path, session: str) -> str:
    binding = read(session, ledger_path=ledger)
    return namespace(name, binding.get("task_scope") if binding else None)


def _named_row(value: dict, task: str) -> dict | None:
    match = NAME.fullmatch(task.removeprefix("/root/"))
    return value["scopes"].get("TS1-" + match[1]) if match else None


def _owns(row: dict, task: str, *, pending: bool = False) -> bool:
    state = budget.read_budget(Path(row["ledger_path"]))
    if any(item["disposition"] == "created" and item["agent_ref"] == ref(task)
           for item in state["receipts"].values()):
        return True
    return pending and any(pid not in state["receipts"] and "/root/" + state["permits"][pid]["task_name"] == task
                           for pid in state["reservations"])


def child_owner(data: Mapping[str, Any]) -> tuple[str, Path] | None:
    session = str(data.get("session_id") or "")
    value = registry(session)
    if value is None:
        binding = legacy.read(session)
        return ("new", Path(binding["new_ledger_path"])) if binding else None
    task = legacy._child_task_path(dict(data))
    row = _named_row(value, task)
    if row is not None:
        _check_row(row, session)
        if not _owns(row, task, pending=True):
            fail("TASK_CHILD_NOT_RESERVED")
        return "new", Path(row["ledger_path"])
    for row in value["scopes"].values():
        if row["kind"] == "legacy" and _owns(row, task, pending=True):
            _check_row(row, session)
            return "new", Path(row["ledger_path"])
    if value["legacy_digest"] is not None:
        return legacy.route(dict(data), directory=_legacy_directory(session))
    fail("TASK_CHILD_OWNER_UNKNOWN")


def _target_row(value: dict, session: str, target: str) -> dict:
    from .g6_agent_identity import _path, resolve
    if not isinstance(target, str) or not target or len(target) > 256:
        fail("TASK_TARGET_REQUIRED")
    canonical = target if target.startswith("/root/") else "/root/" + target
    row = _named_row(value, canonical)
    candidates = [row] if row is not None else [
        item for item in value["scopes"].values()
        if item["kind"] == "legacy" and re.fullmatch(r"/root/[a-z0-9_]{1,64}", canonical)
        or _path(Path(item["ledger_path"]), target).exists()]
    owned = []
    for item in candidates:
        task = resolve(Path(item["ledger_path"]), target, session_id=session)
        if _owns(item, task):
            owned.append(item)
    if len(owned) != 1:
        fail("TASK_TARGET_OWNER_UNKNOWN_OR_AMBIGUOUS")
    return owned[0]


def _call_path(session: str, call_id: str) -> Path:
    if not isinstance(call_id, str) or not call_id:
        fail("TASK_NATIVE_CALL_ID_REQUIRED")
    return _home() / "task-calls" / ref(session)[7:] / (ref(call_id)[7:] + ".json")


def route(data: dict[str, Any]) -> tuple[str, Path] | None:
    session = data.get("session_id")
    if not isinstance(session, str) or not session:
        return None
    value = registry(session)
    if value is None:
        return legacy.route(data)
    if data.get("agent_id"):
        return child_owner(data)
    if data.get("hook_event_name") == "Stop":
        # 中文：维护可以选择当前任务；计费调用永不使用此分支。
        # English: Maintenance may select the current task; billable calls never use this branch.
        row = value["scopes"][value["active_scope"]]
        _check_row(row, session)
        return "new", Path(row["ledger_path"])
    tool, event = delegation_tool_name(data.get("tool_name")), data.get("hook_event_name")
    if tool not in BILLABLE | {"send_message"} or event not in {"PreToolUse", "PostToolUse"}:
        return None
    args = data.get("tool_input")
    if not isinstance(args, dict):
        fail("TASK_CALL_INPUT")
    call_path = _call_path(session, data.get("tool_use_id"))
    with OwnerTokenLock(legacy.pointer_for(session), timeout=2):
        value = _registry_unlocked(session)
        if call_path.exists():
            call = _sealed(call_path, 16_384)
            exact(call, {"schema_version", "session_ref", "call_ref", "scope_ref",
                         "tool", "args_ref", "turn_ref"}, "TASK_CALL_FIELDS")
            if (call["schema_version"] != "g6-task-call/1" or call["session_ref"] != ref(session)
                    or call["call_ref"] != ref(data["tool_use_id"]) or call["tool"] != tool
                    or call["args_ref"] != ref(args)
                    or event == "PreToolUse" and call["turn_ref"] != ref(data.get("turn_id"))):
                fail("TASK_CALL_BINDING_CHANGED")
            row = value["scopes"].get(call["scope_ref"])
        elif event == "PostToolUse":
            if value["legacy_digest"] is not None:
                return legacy.route(data, directory=_legacy_directory(session))
            fail("TASK_CALL_OWNER_UNKNOWN")
        else:
            if tool == "spawn_agent":
                row = _named_row(value, str(args.get("task_name") or ""))
                if row is None:
                    fail("TASK_EXPLICIT_SCOPE_REQUIRED")
            else:
                row = _target_row(value, session, args.get("target", args.get("id")))
            if row is None:
                fail("TASK_SCOPE_NOT_REGISTERED")
            _check_row(row, session, Path(str(data.get("cwd") or "")))
            call = {"schema_version": "g6-task-call/1", "session_ref": ref(session),
                    "call_ref": ref(data["tool_use_id"]), "scope_ref": row["scope_ref"],
                    "tool": tool, "args_ref": ref(args), "turn_ref": ref(data.get("turn_id"))}
            atomic_write_json(call_path, call, seal=True)
        if row is None:
            fail("TASK_CALL_OWNER_UNKNOWN")
        _check_row(row, session, Path(str(data.get("cwd") or "")))
        return "new", Path(row["ledger_path"])


def approve_and_reserve(ledger: Path, **parameters: Any) -> dict:
    """中文：完成与实际预占串行化；Post/Stop 不经过新派发检查。
    English: Serialize completion with actual reservation; late Post/Stop never use admission.
    """
    session = parameters["session_id"]
    with OwnerTokenLock(legacy.pointer_for(session), timeout=2):
        value = _registry_unlocked(session)
        if value is not None:
            rows = [row for row in value["scopes"].values()
                    if same_path(Path(row["ledger_path"]), ledger)]
            if len(rows) != 1:
                fail("TASK_LEDGER_NOT_REGISTERED")
            row = rows[0]
            _check_row(row, session, parameters["cwd"])
            if row["status"] != "ACTIVE":
                fail("TASK_SCOPE_COMPLETE_RESUME_REQUIRED")
        return budget.approve_and_reserve(ledger, **parameters)


def complete(session: str, cwd: Path, task_scope: str) -> dict:
    path = legacy.pointer_for(session)
    with OwnerTokenLock(path, timeout=2):
        value = _registry_unlocked(session)
        if value is None or task_scope not in value["scopes"]:
            fail("TASK_SCOPE_NOT_REGISTERED")
        row = value["scopes"][task_scope]
        state = _check_row(row, session, cwd)
        if any(pid not in state["terminals"] and state["receipts"].get(pid, {}).get("disposition") != "not_started"
               for pid in state["reservations"]):
            fail("TASK_NATIVE_OUTCOME_PENDING")
        row["status"] = "COMPLETE"
        atomic_write_json(path, value, seal=True)
    return {"task_scope": task_scope, "status": "COMPLETE", "budget_preserved": True}
