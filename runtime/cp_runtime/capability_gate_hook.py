"""中文：可选Hook的有限查找、宿主协议与进程超时保护；不扫描业务或运行测试。

English: Bounded opt-in lookup, host protocol, and process deadlines; no business scans or tests.
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .atomic_io import native_path
from .capability_gate import POLICY_LIMIT, GatePolicy, _read, worktree_key
from .capability_operation import CapabilityOperation, _digest_json
from .patch_intent import PatchIntentError, parse_apply_patch, revalidate_intent
from .capability_store import CapabilityError, CapabilityStore, bounded_read, fields, require, safe_path, unique_json_object
from .common import resolve_codex_home

WRITE_TOOLS = {"apply_patch", "edit", "write"}
EVENTS = {"UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "Interrupt"}
WIRE_LIMIT = 16 * 1024
# 中文：JSON 转义与有界 PostTool 响应需要高于规范 1 MiB 命令的余量。
# English: JSON escaping and bounded PostTool responses need headroom above the 1 MiB command limit.
INPUT_LIMIT = 2 * 1024 * 1024
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
    if event == "PostToolUse":
        return _post_block(message)
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


def _post_block(reason: str) -> dict[str, Any]:
    return {"decision": "block", "reason": reason,
            "hookSpecificOutput": {"hookEventName": "PostToolUse",
                                    "additionalContext": "副作用已可能发生；operation 已收敛为 OUTCOME_UNKNOWN。"}}


def _canonical_patch(data: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    """中文：只读取规范安全字段；别名不进入 R2。

    English: Read only canonical security fields; aliases never enter R2.
    """
    official = {"hook_event_name", "session_id", "turn_id", "agent_id", "agent_type",
                "transcript_path", "cwd", "model", "permission_mode", "tool_name",
                "tool_input", "tool_use_id", "tool_response", "task_id"}
    if set(data) - official:
        raise CapabilityError("OP_CANONICAL_INPUT")
    if (data.get("tool_name") != "apply_patch"
            or not isinstance(data.get("tool_use_id"), str) or not data["tool_use_id"]):
        raise CapabilityError("OP_CANONICAL_INPUT")
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict) or set(tool_input) != {"command"} or not isinstance(tool_input["command"], str):
        raise CapabilityError("OP_CANONICAL_INPUT")
    if (not isinstance(data.get("session_id"), str) or not data["session_id"]
            or not isinstance(data.get("turn_id"), str) or not data["turn_id"]
            or not isinstance(data.get("cwd"), str) or not data["cwd"]):
        raise CapabilityError("OP_CANONICAL_INPUT")
    if data.get("hook_event_name") == "PostToolUse" and "tool_response" not in data:
        raise CapabilityError("OP_CANONICAL_INPUT")
    return data["tool_use_id"], data["session_id"], data["turn_id"], tool_input


def _post_recovery_binding(data: dict[str, Any]) -> tuple[str, str, str, str]:
    """中文：即使 PostTool 响应字段缺失，也提取足够的规范身份以收敛已派发操作。

    English: Extract enough canonical identity to converge a dispatched operation when response data is missing.
    """
    require(data.get("hook_event_name") == "PostToolUse"
            and data.get("tool_name") == "apply_patch", "OP_CANONICAL_INPUT")
    values = tuple(data.get(key) for key in ("tool_use_id", "session_id", "turn_id", "cwd"))
    require(all(isinstance(value, str) and value for value in values), "OP_CANONICAL_INPUT")
    return values  # type: ignore[return-value]


def _trusted_repo(policy: GatePolicy, cwd: str) -> Path:
    """中文：把可信 Hook cwd 绑定到策略的精确 Git 工作区根。

    English: Bind trusted Hook cwd to the policy's exact Git worktree root.
    """
    current = safe_path(Path(cwd))
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "rev-parse", "--show-toplevel"],
            cwd=current, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=1.5,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
        )
        require(result.returncode == 0 and len(result.stdout) <= 4096, "OP_REPO_IDENTITY")
        root = safe_path(Path(result.stdout.decode("utf-8", errors="strict").strip()))
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        raise CapabilityError("OP_REPO_IDENTITY") from None
    require(root == safe_path(policy.store.repo_path), "OP_REPO_IDENTITY")
    return root


def _disabled_post_has_inflight_operation(policy: GatePolicy, data: dict[str, Any]) -> bool:
    """Keep disabled policies neutral unless this exact PostToolUse must settle an in-flight B."""
    tool_use_id, session_id, turn_id, cwd = _post_recovery_binding(data)
    _trusted_repo(policy, cwd)
    scope = _digest_json([session_id, turn_id])[:16]
    operation_root = safe_path(
        policy.store.profile_path.parent / "capability-operation" /
        policy.store.identity["worktree_id"] / scope,
    )
    if not native_path(operation_root).is_dir():
        return False
    operation = CapabilityOperation(policy, session_id, turn_id)
    return any(
        item["dispatch_tool_use_id"] == tool_use_id and
        item["state"] not in {"VERIFIED", "DENIED", "CANCELLED", "EXPIRED", "OUTCOME_UNKNOWN"}
        for item in operation._scan()
    )


def _v2_patch(root: Path, data: dict[str, Any], event: str) -> dict[str, Any]:
    """中文：通过 Operation v2 路由规范 apply_patch。

    English: Route canonical apply_patch through Operation v2.
    """
    try:
        policy_path = locate_policy(str(data.get("cwd") or ""))
        if policy_path is None:
            return {}
        policy = load_policy(policy_path)
        policy_record = policy.read()
        if event == "PreToolUse" and not policy_record["enabled"]:
            return {}
        if event == "PostToolUse" and not policy_record["enabled"]:
            try:
                if not _disabled_post_has_inflight_operation(policy, data):
                    return {}
            except (CapabilityError, OSError, ValueError, KeyError):
                return {}
        tool_use_id, session_id, turn_id, tool_input = _canonical_patch(data)
        repo = _trusted_repo(policy, str(data["cwd"]))
        operation = CapabilityOperation(policy, session_id, turn_id)
        if event == "PreToolUse":
            intent = parse_apply_patch(tool_input["command"], repo)
            # 中文：解析结果不含正文，是 A/B 共同使用的精确冻结意图和前态。
            # English: The content-free parser result is the exact frozen intent/prestate for A and B.
            revalidate_intent(intent, repo)
            claimed = operation.find_and_claim(
                tool_use_id=tool_use_id, intent=intent,
                targets=intent["target_paths"], prestate=intent,
            )
            if claimed is not None:
                return {}
            origin = operation.create_or_replay_origin(
                tool_use_id, intent, intent["target_paths"], intent,
            )
            command = (
                "cp-runtime.py capability-task-prepare"
                " --profile \"%s\" --repo-path \"%s\" --index-root \"%s\""
                " --gate-root \"%s\" --operation-ref %s --term \"<task-term>\""
                % (policy.store.profile_path, policy.store.repo_path, policy.store.root,
                   policy.root, origin["operation_ref"])
            )
            return failure_response(
                "PreToolUse", "operation_ref=%s; prepare command: %s"
                % (origin["operation_ref"], command),
            )
        if event == "PostToolUse":
            matches = [item for item in operation._scan()
                       if item["dispatch_tool_use_id"] == tool_use_id]
            require(len(matches) == 1, "POST_TOOL_UNKNOWN_OPERATION")
            item = matches[0]
            command = tool_input["command"].encode("utf-8", errors="strict")
            require(len(command) <= 1024 * 1024, "COMMAND_TOO_LARGE")
            require(item["prestate"].get("command_sha256") ==
                    hashlib.sha256(command).hexdigest(), "OP_INTENT_MISMATCH")
            ref = item["operation_ref"]
            response = data.get("tool_response", {})
            require(isinstance(response, str) and bool(response.strip()),
                    "POST_TOOL_RESPONSE_SCHEMA")
            recorded = operation.record_posttool(
                ref, tool_use_id, response, summary_code="APPLY_PATCH_SUCCEEDED",
            )
            if recorded["state"] != "RESULT_PENDING":
                return _post_block("POST_TOOL_POLICY_CHANGED")
            return {}
        return {}
    except (PatchIntentError, CapabilityError, OSError, ValueError, KeyError):
        if event == "PostToolUse":
            try:
                policy_path = locate_policy(str(data.get("cwd") or ""))
                if policy_path is not None:
                    policy = load_policy(policy_path)
                    tool_use_id, session_id, turn_id, cwd = _post_recovery_binding(data)
                    _trusted_repo(policy, cwd)
                    operation = CapabilityOperation(policy, session_id, turn_id)
                    for item in operation._scan():
                        if item["dispatch_tool_use_id"] == tool_use_id and item["state"] not in {"VERIFIED", "DENIED", "CANCELLED", "EXPIRED", "OUTCOME_UNKNOWN"}:
                            operation.stop(item["operation_ref"], "POST_TOOL_RECONCILIATION_FAILED")
                            break
            except Exception:
                pass
            return _post_block("POST_TOOL_RECONCILIATION_FAILED")
        return legacy_write_response()


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
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    event = payload["hook_event_name"]
    if len(raw) > INPUT_LIMIT:
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
    elif event == "PostToolUse":
        fields(output, {"decision", "reason", "hookSpecificOutput"})
        specific = output["hookSpecificOutput"]
        fields(specific, {"hookEventName", "additionalContext"})
        require(output["decision"] == "block" and isinstance(output["reason"], str)
                and specific["hookEventName"] == event and isinstance(specific["additionalContext"], str),
                "GATE_WORKER_FAILED")
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
        tool = str(data.get("tool_name") or "")
        if tool == "apply_patch":
            response = _v2_patch(root, data, event)
            return {"enabled": bool(response), "response": response, "observe": False, "allow_feedback": False}
        if tool.lower() in {"edit", "write"}:
            # 中文：绝不复用 v1 遗留的 PREPARED/PASS；迁移期策略缺失或停用时保持中性。
            # English: Never reuse v1 PREPARED/PASS; an absent or disabled policy remains neutral during transition.
            enabled = _legacy_write_is_enabled(str(data.get("cwd") or ""))
            return {"enabled": enabled, "response": legacy_write_response() if enabled else {},
                    "observe": False, "allow_feedback": False}
        return {"enabled": False, "response": {}, "observe": True, "allow_feedback": False}
    if event == "PostToolUse":
        if data.get("tool_name") == "apply_patch":
            response = _v2_patch(root, data, event)
            return {"enabled": bool(response), "response": response, "observe": False, "allow_feedback": False}
        return {"enabled": False, "response": {}, "observe": False, "allow_feedback": False}
    # 中文：Stop 只观察；不读取或修改旧状态，不检查证据、记录失败或请求修复。
    # English: Stop is observation-only; do not read or alter legacy state, check evidence, record failure, or request repair.
    return {"enabled": False, "response": {}, "observe": True, "allow_feedback": True}
