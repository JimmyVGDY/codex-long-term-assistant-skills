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
from .capability_gate import POLICY_LIMIT, GatePolicy, _read, worktree_key
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
    # 中文：R1 将提示提交和 Stop 留给宿主控制；门禁失败不得合成续跑或控制上下文响应。
    # English: R1 keeps prompt submission and Stop under host control; gate failure must not synthesize continuation or control context.
    return {}


def legacy_write_response() -> dict[str, Any]:
    """中文：不查询旧门禁任务状态，直接拒绝旧版原生写入。

    English: Deny legacy native writes without consulting prior gate-task state.
    """
    return failure_response("PreToolUse", "LEGACY_WRITE_ORIGIN_UNAVAILABLE")


def _legacy_write_is_enabled(cwd: str) -> bool:
    """中文：只读取有界策略记录，绝不打开旧版 GateTask。

    English: Read only the bounded policy record; never open a legacy GateTask.
    """
    path = locate_policy(cwd)
    if path is None:
        return False
    policy = load_policy(path)
    return bool(policy.read()["enabled"])


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
    else:
        # 中文：R1 中 UserPromptSubmit/Stop 只观察；拒绝旧 decision/block/continue 或 additionalContext 注入。
        # English: UserPromptSubmit and Stop are observation-only in R1; reject legacy control fields and additionalContext injection.
        require(event in {"UserPromptSubmit", "Stop"}, "GATE_WORKER_FAILED")
        require(not output, "GATE_WORKER_FAILED")


def handle(root: Path, data: dict[str, Any]) -> dict[str, Any]:
    event = data.get("hook_event_name")
    require(event in EVENTS, "GATE_HOOK_EVENT")
    if event == "UserPromptSubmit":
        # 中文：提示提交期间不构造 GateTask、不查询策略或索引、不扫描源码，也不注入旧控制指令。
        # English: During prompt submission, do not construct GateTask, query policy/index, scan source, or inject legacy control instructions.
        return {"enabled": False, "response": {}, "observe": True, "allow_feedback": False}
    if event == "Interrupt":
        # 中文：取消完全由宿主控制；此路径不得修改旧 GateTask 或伪造取消结果。
        # English: Cancellation remains with the host; this path must not mutate legacy GateTask or manufacture a cancellation outcome.
        return {"enabled": False, "response": {}, "observe": False, "allow_feedback": False}
    if event == "PreToolUse":
        tool = str(data.get("tool_name") or "").lower()
        if tool in WRITE_TOOLS:
            # 中文：绝不复用 v1 遗留的 PREPARED/PASS；迁移期策略缺失或停用时保持中性。
            # English: Never reuse v1 PREPARED/PASS; an absent or disabled policy remains neutral during transition.
            enabled = _legacy_write_is_enabled(str(data.get("cwd") or ""))
            return {"enabled": enabled, "response": legacy_write_response() if enabled else {},
                    "observe": False, "allow_feedback": False}
        return {"enabled": False, "response": {}, "observe": True, "allow_feedback": False}
    # 中文：Stop 只观察；不读取或修改旧状态，不检查证据、记录失败或请求修复。
    # English: Stop is observation-only; do not read or alter legacy state, check evidence, record failure, or request repair.
    return {"enabled": False, "response": {}, "observe": True, "allow_feedback": True}
