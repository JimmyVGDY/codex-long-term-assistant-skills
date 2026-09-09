"""中文：可选Hook的有限查找、宿主协议与进程超时保护；不扫描业务或运行测试。

English: Bounded opt-in lookup, host protocol, and process deadlines; no business scans or tests.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .atomic_io import native_path
from .capability_gate import ACTIVE, POLICY_LIMIT, GatePolicy, GateTask, _read, worktree_key
from .capability_gate_evidence import capture_worktree, changed_paths
from .capability_gate_workflow import GateWorkflow
from .capability_store import CapabilityError, CapabilityStore, bounded_read, fields, require, safe_path, unique_json_object
from .common import resolve_codex_home

WRITE_TOOLS = {"apply_patch", "edit", "write"}
EVENTS = {"UserPromptSubmit", "PreToolUse", "Stop", "Interrupt"}
WIRE_LIMIT = 16 * 1024
WORKER_TIMEOUT = 4.0
INTERRUPT_TIMEOUT = 2.2


def locate_policy(cwd: str) -> Path | None:
    configured = Path(os.environ["CP_CAPABILITY_GATE_ROOT"]) if os.environ.get("CP_CAPABILITY_GATE_ROOT") else None
    require(configured is None or configured.is_absolute(), "GATE_ROOT_INVALID")
    root = safe_path(configured or resolve_codex_home() / "capability-gates")
    if not native_path(root).exists():
        return None
    require(native_path(root).is_dir(), "GATE_ROOT_INVALID")
    repo = safe_path(Path(cwd))
    for depth, parent in enumerate((repo, *repo.parents)):
        require(depth < 64, "GATE_LOOKUP_LIMIT")
        path = safe_path(root / (worktree_key(parent) + ".json"))
        if native_path(path).exists() or native_path(path.with_suffix(".previous.json")).exists():
            return path
    return None


def load_policy(path: Path) -> GatePolicy:
    value = _read(path, POLICY_LIMIT)
    fields(value, {"schema_version", "revision", "enabled", "identity", "integrity"})
    identity = value["identity"]
    fields(identity, {"project_id", "repo_fingerprint", "profile_path", "profile_binding", "worktree_root", "worktree_id", "index_root"})
    require(all(isinstance(item, str) and 0 < len(item) <= 2048 for item in identity.values()), "GATE_SCHEMA")
    repo = safe_path(Path(identity["worktree_root"]))
    require(path.name == worktree_key(repo) + ".json", "GATE_IDENTITY_MISMATCH")
    policy = GatePolicy(CapabilityStore(Path(identity["profile_path"]), repo, Path(identity["index_root"])), path.parent)
    policy.read()
    return policy


def runtime_entry(root: Path, name: str = "cp-runtime.py") -> Path:
    require(name in {"cp-runtime.py", "evolution.py"}, "GATE_RUNTIME_ENTRY_UNAVAILABLE")
    source = safe_path(root / "scripts" / name)
    if source.is_file():
        return source
    home = safe_path(resolve_codex_home())
    try:
        state = json.loads(bounded_read(home / "cp-assistant-v6-state.json", 256 * 1024),
                           object_pairs_hook=unique_json_object)
        require(isinstance(state, dict), "GATE_RUNTIME_ENTRY_UNAVAILABLE")
        if state.get("mode") == "standalone":
            expected = home
        else:
            require(state.get("mode") == "plugin", "GATE_RUNTIME_ENTRY_UNAVAILABLE")
            version = state.get("version")
            require(isinstance(version, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", version) is not None,
                    "GATE_RUNTIME_ENTRY_UNAVAILABLE")
            expected = home / "plugins" / "cache" / "cp-assistant-local" / "codex-cross-project-engineering-assistant" / version
        require(safe_path(expected) == safe_path(root), "GATE_RUNTIME_ENTRY_UNAVAILABLE")
        entry = safe_path(home / "tools" / name)
        bounded_read(entry, 16 * 1024)
        return entry
    except (ValueError, UnicodeError, OSError):
        raise CapabilityError("GATE_RUNTIME_ENTRY_UNAVAILABLE") from None


def failure_response(event: str, reason: str) -> dict[str, Any]:
    message = "Capability gate: " + reason + ". No current process PASS was verified."
    if event == "PreToolUse":
        return {"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny", "permissionDecisionReason": message}}
    if event == "Interrupt":
        return {"systemMessage": message + " Host interruption remains in control."}
    return {"continue": False, "stopReason": message, "systemMessage": message}


def supervise(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    event = payload["hook_event_name"]
    if len(raw) > WIRE_LIMIT:
        return failure_response(event, "GATE_INPUT_LIMIT")
    try:
        worker = safe_path(root / "hooks" / "cp_gate.py")
        if not worker.is_file():
            # 中文：standalone采用同一受管Hook目录；确认账户运行绑定后再选择入口。
            # English: Standalone uses its managed Hook directory after account binding validation.
            runtime_entry(root)
            require(safe_path(root) == safe_path(resolve_codex_home()), "GATE_RUNTIME_ENTRY_UNAVAILABLE")
            worker = safe_path(root / "cp-assistant-hooks" / "cp_gate.py")
            require(worker.is_file(), "GATE_RUNTIME_ENTRY_UNAVAILABLE")
        result = subprocess.run([sys.executable, "-B", str(worker)],
            input=raw, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=INTERRUPT_TIMEOUT if event == "Interrupt" else WORKER_TIMEOUT,
            env={**os.environ, "PLUGIN_ROOT": str(root)})
        require(result.returncode == 0 and len(result.stdout) <= WIRE_LIMIT, "GATE_WORKER_FAILED")
        output = json.loads(result.stdout, object_pairs_hook=unique_json_object)
        require(isinstance(output, dict), "GATE_WORKER_FAILED")
        validate_response(event, output)
        return output
    except subprocess.TimeoutExpired:
        return failure_response(event, "GATE_HOST_DEADLINE")
    except (OSError, ValueError, CapabilityError):
        return failure_response(event, "GATE_WORKER_FAILED")


def validate_response(event: str, output: dict[str, Any]) -> None:
    """中文：父进程拒绝会导致宿主错误放行的未知字段组合。

    English: Reject unknown output shapes that could make the host silently allow a failed Hook.
    """
    if not output:
        return
    if event == "PreToolUse":
        fields(output, {"hookSpecificOutput"})
        specific = output["hookSpecificOutput"]
        fields(specific, {"hookEventName", "permissionDecision", "permissionDecisionReason"})
        require(specific["hookEventName"] == event and specific["permissionDecision"] == "deny"
                and isinstance(specific["permissionDecisionReason"], str), "GATE_WORKER_FAILED")
    elif event == "Interrupt":
        fields(output, {"systemMessage"})
        require(isinstance(output["systemMessage"], str), "GATE_WORKER_FAILED")
    elif "continue" in output:
        fields(output, {"continue", "stopReason", "systemMessage"})
        require(output["continue"] is False and isinstance(output["stopReason"], str)
                and isinstance(output["systemMessage"], str), "GATE_WORKER_FAILED")
    elif event == "Stop":
        if "decision" in output:
            fields(output, {"decision", "reason"})
            require(output["decision"] == "block" and isinstance(output["reason"], str), "GATE_WORKER_FAILED")
        else:
            fields(output, {"systemMessage"})
            require(isinstance(output["systemMessage"], str), "GATE_WORKER_FAILED")
    else:
        require(event == "UserPromptSubmit", "GATE_WORKER_FAILED")
        fields(output, {"hookSpecificOutput"})
        specific = output["hookSpecificOutput"]
        fields(specific, {"hookEventName", "additionalContext"})
        require(specific["hookEventName"] == event and isinstance(specific["additionalContext"], str),
                "GATE_WORKER_FAILED")


def task_context(root: Path, task: GateTask) -> str:
    args = {"entry": str(runtime_entry(root)), "profile": str(task.policy.store.profile_path),
            "repo_path": str(task.policy.store.repo_path), "gate_root": str(task.policy.root),
            "index_root": str(task.policy.store.root), "session_id": task.session_id, "turn_id": task.turn_id}
    return ("Project capability gate is enabled. Runtime binding: " + json.dumps(args, ensure_ascii=True) +
            ". Before editing, call capability-task-prepare with the binding arguments, explicit --scope file(s) and --term. "
            "Only a local implementation fix in one existing file may use --local-only-reason; "
            "public API extensions, new features, or coordinated caller changes require initial scanning even when small. "
            "Prepare all intended files before editing; expanding a cold local exception after edits cannot retroactively prove initial scanning. "
            "After editing, call capability-task-finish with --decisions pointing to a JSON list covering every required_decisions ID: "
            "{id,choice,reason}, choice reuse/extend/extract/independent/unused. "
            "Keep this JSON and other task-only helper files in the already-authorized external context containing the profile, with task-specific names. "
            "Do not create them in the repository or overwrite runtime-managed profile, index, gate, or receipt files. "
            "Declare actual adopted candidates; finish refreshes adopted stale sources. "
            "Call capability-task-check for current evidence. PARTIAL/BLOCKED/NO_CHANGE are distinct from PASS; semantic suitability still requires source checks and tests.")


def handle(root: Path, data: dict[str, Any]) -> dict[str, Any]:
    event = data["hook_event_name"]
    path = locate_policy(data["cwd"])
    require(path is not None, "GATE_POLICY_CHANGED")
    policy = load_policy(path)
    with policy.store.bounded_identity_session():
        return _handle_policy(root, data, policy)


def _handle_policy(root: Path, data: dict[str, Any], policy: GatePolicy) -> dict[str, Any]:
    event = data["hook_event_name"]
    if not policy.read()["enabled"]:
        return {"enabled": False, "response": {}, "observe": True, "allow_feedback": True}
    task = GateTask(policy, data.get("session_id", ""), data.get("turn_id", ""))
    flow = GateWorkflow(task)
    if event == "UserPromptSubmit":
        state = flow.begin()
        return {"enabled": True, "response": {"hookSpecificOutput": {"hookEventName": event,
                "additionalContext": task_context(root, task)}}, "observe": True, "allow_feedback": False}
    if event == "Interrupt":
        task.cancel()
        return {"enabled": True, "response": {}, "observe": False, "allow_feedback": False}
    state = task.read()
    if event == "PreToolUse":
        preparation = flow._preparation(state)
        decision = task.before_write(has_scope=bool(preparation and preparation["files"]))
        response = {} if decision["allowed"] else failure_response(event, "NEEDS_PREPARE: " + task_context(root, task))
        return {"enabled": True, "response": response, "observe": False, "allow_feedback": False}
    require(event == "Stop", "GATE_HOOK_EVENT")
    if state["phase"] in {"PASS", "NO_CHANGE"}:
        checked = flow.check()
        phase = checked["state"]["phase"]
        response = {} if checked["valid"] else failure_response(event, phase)
        return {"enabled": True, "response": response, "observe": True,
                "allow_feedback": checked["valid"] and phase == "PASS"}
    if state["phase"] not in ACTIVE:
        return {"enabled": True, "response": failure_response(event, state["phase"]), "observe": True, "allow_feedback": False}
    if state["evidence"]["prepare_sha256"] is None:
        if "NEEDS_PREPARE" not in state["reason_codes"]:
            try:
                flow.no_change()
                return {"enabled": True, "response": {"systemMessage": "Capability gate: NO_CHANGE in the bounded Git-visible scope."},
                        "observe": True, "allow_feedback": False}
            except CapabilityError as exc:
                flow.record_failure(str(exc), state["revision"])
                return {"enabled": True, "response": failure_response(event, str(exc)), "observe": True, "allow_feedback": False}
        start = flow._get("baseline", state["evidence"]["baseline_sha256"])
        current = capture_worktree(flow.repo, sorted(start["files"]))
        if changed_paths(start, current):
            flow.record_failure("GATE_MODIFIED_BEFORE_PREPARE", state["revision"])
            return {"enabled": True, "response": failure_response(event, "GATE_MODIFIED_BEFORE_PREPARE"), "observe": True, "allow_feedback": False}
        reason = "NEEDS_PREPARE"
    else:
        flow._preparation(state)
        reason = "NEEDS_FINISH"
    decision = task.request_repair(data.get("stop_hook_active", False), [reason])
    response = ({"decision": "block", "reason": reason + ": " + task_context(root, task)}
                if decision["action"] == "CONTINUE" else failure_response(event, decision["state"]["phase"]))
    return {"enabled": True, "response": response, "observe": decision["action"] != "CONTINUE", "allow_feedback": False}
