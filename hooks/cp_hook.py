#!/usr/bin/env python3
"""中文：Codex V7.4.3 生命周期 Hook：派发策略、统一委派预算与最小元数据观测。

English: Codex V7.4.3 lifecycle Hook for dispatch policy, delegation budget, and minimal metadata observation.
"""
from __future__ import annotations

import json
import os
import re
import hashlib
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping

sys.dont_write_bytecode = True

# 中文：Codex 以 UTF-8 写入 Hook payload；Windows 原生 Python 默认使用活动 ANSI 代码页解码重定向 stdin，会破坏含中文 last_assistant_message 的 Stop payload。
# English: Codex writes Hook payloads as UTF-8; native Windows Python otherwise decodes redirected stdin with the active ANSI code page and can corrupt Stop payloads containing Chinese text.
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="strict")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

ROOT = Path(os.environ.get("PLUGIN_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.event_v3 import append_event, project_id_for, stable_repo_fingerprint  # noqa: E402
from cp_runtime.delegation_budget import (  # noqa: E402
    DelegationBudgetError, mark_completed, mark_started, profile_for, read_budget,
    reserve_budget,
)
from cp_runtime.seal_queue import launch_worker  # noqa: E402

ALLOWED_REASONING = {"", "none", "minimal", "low", "medium", "high"}
ALLOWED_AUTOMATIC_MODELS = {"gpt-5.6-luna", "gpt-5.6-terra"}
DENY_MARKERS = ("sol", "gpt-5.6-sol", "xhigh", "extra-high", "extra_high", "ultra", "max")
HOOK_ALIASES = {
    "hook_event_name": ("hook_event_name", "hookEventName", "event_name", "event"),
    "tool_name": ("tool_name", "toolName", "tool"),
    "tool_input": ("tool_input", "toolInput", "input", "arguments"),
    "tool_use_id": ("tool_use_id", "toolUseId", "tool_call_id", "toolCallId"),
    "task_name": ("task_name", "taskName", "dispatch_key", "delegation_key"),
    "agent_type": ("agent_type", "agentType", "role"),
    "model": ("model", "model_name", "modelName"),
    "reasoning_effort": ("reasoning_effort", "reasoningEffort", "reasoning", "effort"),
    "reservation_id": ("reservation_id", "reservationId", "delegation_id", "delegationId"),
    "agent_id": ("agent_id", "agentId"),
    "session_id": ("session_id", "sessionId", "thread_id", "threadId"),
    "turn_id": ("turn_id", "turnId"),
    "task_id": ("task_id", "taskId"),
    "cwd": ("cwd", "working_directory", "workingDirectory"),
    "terminal_outcome": ("terminal_outcome", "terminalOutcome", "outcome"),
}
POLICY_MESSAGES = {
    "zh-CN": {
        "model_ceiling": "自动子 Agent 模型不得超过 Terra High；显式 Sol 或更高模型被策略拒绝。",
        "effort_ceiling": "自动子 Agent reasoning_effort 最高为 high。",
        "unknown_model": "显式模型无法证明不超过 Terra High，按 fail-closed 策略拒绝；可使用 gpt-5.6-luna、gpt-5.6-terra 或省略显式模型。",
        "invalid_input": "PreToolUse 输入无法解析，按 fail-closed 策略拒绝自动子 Agent。",
        "hook_failure": "PreToolUse Hook 异常，按 fail-closed 策略拒绝自动子 Agent。",
        "budget_denied": "统一委派预算拒绝此次子 Agent 派发；请先创建匹配的显式 dispatch permit，并检查余额、角色、并行数和深度。",
        "budget_input": "受控任务缺少稳定的派发关联字段或角色，按 fail-closed 策略拒绝。",
        "budget_unconfigured": "任务已启用统一委派预算，但未配置 CP_DELEGATION_BUDGET_PATH，按 fail-closed 策略拒绝。",
    },
    "en": {
        "model_ceiling": "Automatic subagent models cannot exceed Terra High; explicit Sol or stronger models are denied.",
        "effort_ceiling": "Automatic subagent reasoning_effort cannot exceed high.",
        "unknown_model": "The explicit model cannot be proven within the Terra High ceiling and is denied fail-closed; use gpt-5.6-luna, gpt-5.6-terra, or omit the explicit model.",
        "invalid_input": "PreToolUse input could not be parsed; automatic subagent dispatch is denied fail-closed.",
        "hook_failure": "PreToolUse Hook failed; automatic subagent dispatch is denied fail-closed.",
        "budget_denied": "The unified delegation budget denied this subagent dispatch. Create a matching explicit dispatch permit and check remaining units, role, parallelism, and depth.",
        "budget_input": "The controlled task lacks a stable dispatch correlation field or role and is denied fail-closed.",
        "budget_unconfigured": "The task has enabled the unified delegation budget, but CP_DELEGATION_BUDGET_PATH is not configured; the request is denied fail-closed.",
    },
}


def _policy_message(name: str) -> str:
    try:
        configured = json.loads((ROOT / "config" / "locale.json").read_text(encoding="utf-8"))
        locale = str(configured.get("locale") or "zh-CN")
    except (OSError, ValueError, TypeError):
        locale = "zh-CN"
    return POLICY_MESSAGES.get(locale, POLICY_MESSAGES["zh-CN"])[name]


def _read() -> Dict[str, Any]:
    raw = b""
    try:
        # 中文：由 json.loads 直接检查原始字节流及可选 UTF BOM，不依赖 Windows 重定向文本编码。
        # English: Let json.loads inspect the raw byte stream and optional UTF BOM instead of relying on Windows redirected-text encoding.
        raw = sys.stdin.buffer.read()
        data = json.loads(raw) if raw.strip() else {}
        return data
    except Exception:
        # 中文：Windows 原生 Codex CLI 0.152.1 构造 Stop stdin 时可能截断非 ASCII 的 last_assistant_message；生命周期身份字段位于该自由文本字段之前，因此只丢弃损坏尾部并恢复有效 JSON 前缀。
        # English: Native Windows Codex CLI 0.152.1 can truncate a non-ASCII last_assistant_message while constructing Stop stdin; lifecycle identity fields precede it, so discard only the damaged suffix and recover the valid JSON prefix.
        damaged = re.search(rb',\s*"last_assistant_message"\s*:', raw)
        if damaged is not None:
            try:
                recovered = json.loads(raw[: damaged.start()] + b"}")
                if isinstance(recovered, dict):
                    return recovered
            except Exception:
                pass
        # 中文：最后的事件名恢复只维持 Stop stdout 有效，不持久化 Prompt 或回答正文。
        # English: Last-resort event-name recovery keeps Stop stdout valid without persisting prompt or answer content.
        hook = re.search(rb'"hook_event_name"\s*:\s*"([A-Za-z]+)"', raw)
        if hook is not None:
            return {"hook_event_name": hook.group(1).decode("ascii")}
        return {}


class AliasConflictError(ValueError):
    pass


def _lookup(data: Mapping[str, Any], *names: str) -> Any:
    """中文：观察字段遇到互相冲突的别名时返回不可用。

    English: Observation lookup returns unavailable for conflicting aliases.
    """
    values = [data.get(name) for name in names if name in data and data.get(name) is not None]
    if not values:
        return None
    first = values[0]
    if any(value != first for value in values[1:]):
        return None
    return first


def _lookup_strict(data: Mapping[str, Any], *names: str) -> Any:
    """中文：安全字段遇到互相冲突的别名时失败关闭。

    English: Security lookup fails closed for conflicting aliases.
    """
    values = [data.get(name) for name in names if name in data and data.get(name) is not None]
    if not values:
        return None
    first = values[0]
    if any(value != first for value in values[1:]):
        raise AliasConflictError("conflicting hook aliases")
    return first


def _tool_input(data: Mapping[str, Any]) -> Mapping[str, Any]:
    candidate = _lookup_strict(data, *HOOK_ALIASES["tool_input"])
    return candidate if isinstance(candidate, Mapping) else {}


def _guard(data: Mapping[str, Any]) -> Dict[str, Any] | None:
    tool = str(_lookup_strict(data, *HOOK_ALIASES["tool_name"]) or "").lower()
    if tool not in {"agent", "spawn_agent"}:
        return None
    args = _tool_input(data)
    model = str(_lookup_strict(args, *HOOK_ALIASES["model"]) or "").strip().lower()
    effort = str(_lookup_strict(args, *HOOK_ALIASES["reasoning_effort"]) or "").strip().lower()
    reason = ""
    if any(marker in model for marker in DENY_MARKERS):
        reason = _policy_message("model_ceiling")
    elif effort not in ALLOWED_REASONING:
        reason = _policy_message("effort_ceiling")
    elif model and model not in ALLOWED_AUTOMATIC_MODELS:
        reason = _policy_message("unknown_model")
    if not reason:
        ledger_text = os.environ.get("CP_DELEGATION_BUDGET_PATH", "").strip()
        if not ledger_text:
            if os.environ.get("CP_DELEGATION_BUDGET_REQUIRED", "").strip() == "1":
                reason = _policy_message("budget_unconfigured")
            else:
                return None
        if not reason:
            dispatch_key = str(_lookup_strict(args, *HOOK_ALIASES["task_name"]) or "").strip()
            host_dispatch_id = str(_lookup_strict(data, *HOOK_ALIASES["tool_use_id"]) or "").strip()
            role = str(_lookup_strict(args, *HOOK_ALIASES["agent_type"]) or "").strip()
            if not dispatch_key or not host_dispatch_id or not role:
                reason = _policy_message("budget_input")
            else:
                try:
                    state = read_budget(Path(ledger_text).expanduser().resolve())
                    profile, basis = profile_for(model, effort, state["default_dispatch_profile"])
                    reservation = reserve_budget(
                        Path(ledger_text).expanduser().resolve(), dispatch_key=dispatch_key,
                        host_dispatch_id=host_dispatch_id, approved_profile=profile,
                        approval_basis=basis, role=role,
                    )
                    # 中文：仅把受控 reservation 标识留在本次内存 payload，绝不写回原始任务正文。
                    # English: Keep only the controlled reservation identifier in this in-memory payload.
                    if isinstance(data, dict):
                        data["_cp_reservation_id"] = reservation["reservation_id"]
                    return None
                except (DelegationBudgetError, OSError, TimeoutError):
                    reason = _policy_message("budget_denied")
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}


def _budget_lifecycle(data: Mapping[str, Any], hook_name: str) -> None:
    """中文：只在宿主显式传播 reservation_id 时对账；当前宿主缺失时保留 RESERVED。

    English: Reconcile only when the host explicitly propagates reservation_id; keep RESERVED when the current host omits it.
    """
    ledger_text = os.environ.get("CP_DELEGATION_BUDGET_PATH", "").strip()
    if not ledger_text or hook_name not in {"SubagentStart", "SubagentStop"}:
        return
    reservation_id = str(_lookup(data, *HOOK_ALIASES["reservation_id"]) or "").strip()
    agent_id = str(_lookup(data, *HOOK_ALIASES["agent_id"]) or "").strip()
    if not reservation_id or not agent_id:
        return
    ledger = Path(ledger_text).expanduser().resolve()
    if hook_name == "SubagentStart":
        mark_started(ledger, reservation_id=reservation_id, agent_id=agent_id)
    else:
        outcome = str(_lookup(data, *HOOK_ALIASES["terminal_outcome"]) or "UNKNOWN").upper()
        mark_completed(ledger, reservation_id=reservation_id, outcome=outcome)


def _event(data: Mapping[str, Any]) -> Dict[str, Any] | None:
    hook = str(_lookup(data, *HOOK_ALIASES["hook_event_name"]) or "")
    event_map = {
        "UserPromptSubmit": "TURN_OPENED",
        "PreToolUse": "PRE_TOOL_GUARD",
        "SubagentStart": "SUBAGENT_STARTED",
        "SubagentStop": "SUBAGENT_STOPPED",
        "Stop": "TASK_COMPLETED",
        "SessionEnd": "SESSION_ENDED",
    }
    event_type = event_map.get(hook)
    if not event_type:
        return None
    cwd = str(_lookup(data, *HOOK_ALIASES["cwd"]) or os.getcwd())
    fingerprint = stable_repo_fingerprint(cwd)
    session_id = str(_lookup(data, *HOOK_ALIASES["session_id"]) or "")
    turn_id = str(_lookup(data, *HOOK_ALIASES["turn_id"]) or "")
    task_id = str(_lookup(data, *HOOK_ALIASES["task_id"]) or turn_id or session_id)
    if event_type == "SESSION_ENDED" and not (session_id or turn_id or task_id):
        _session_end_diagnostic({
            "session_id": "", "turn_id": "", "task_id": "",
            "project_id": project_id_for(fingerprint, cwd), "repo_fingerprint": fingerprint,
        }, "SESSION_END_IDENTITY_UNAVAILABLE")
        return None
    terminal_value = _lookup(data, *HOOK_ALIASES["terminal_outcome"]) if event_type == "TASK_COMPLETED" else None
    terminal = str(terminal_value or "UNKNOWN").upper()
    metadata: Dict[str, Any] = {}
    for key in ("agent_id", "agent_type", "permission_mode", "tool_name", "stop_hook_active"):
        value = data.get(key)
        if value is not None:
            metadata[key] = value
    if event_type == "SESSION_ENDED":
        metadata["seal_required"] = True
    approved_profile = ""
    permit_ref = ""
    reserved_units = 0
    reservation_id = str(_lookup(data, *HOOK_ALIASES["reservation_id"]) or data.get("_cp_reservation_id") or "").strip()
    ledger_text = os.environ.get("CP_DELEGATION_BUDGET_PATH", "").strip()
    if reservation_id and ledger_text:
        try:
            budget = read_budget(Path(ledger_text).expanduser().resolve())
            reservation = budget.get("reservations", {}).get(reservation_id) or {}
            approved_profile = str(reservation.get("approved_profile") or reservation.get("requested_profile") or "")
            reserved_units = int(reservation.get("charged_units") or reservation.get("units") or 0)
            permit_ref = "sha256:" + hashlib.sha256(reservation_id.encode("utf-8")).hexdigest()
        except (DelegationBudgetError, OSError, TimeoutError, TypeError, ValueError):
            approved_profile = ""
            permit_ref = ""
            reserved_units = 0
    return {
        "event_type": event_type,
        "session_id": session_id,
        "turn_id": turn_id,
        "task_id": task_id,
        "project_id": project_id_for(fingerprint, cwd),
        "repo_fingerprint": fingerprint,
        "terminal_outcome": terminal,
        "terminal_outcome_source": "hook-payload" if terminal_value is not None and terminal != "UNKNOWN" else "unavailable",
        "approved_dispatch_profile": approved_profile,
        "dispatch_permit_ref": permit_ref,
        "reserved_units": reserved_units,
        "metadata": metadata,
    }


def _data_path(event: Mapping[str, Any]) -> Path:
    base = os.environ.get("CP_ASSISTANT_DATA")
    if base:
        root = Path(base).expanduser() / event["project_id"]
    else:
        configured = os.environ.get("CODEX_HOME")
        if configured and os.name == "nt":
            match = re.match(r"^/mnt/([A-Za-z])(?:/(.*))?$", configured.strip().replace("\\", "/"))
            if match:
                drive = match.group(1).upper()
                rest = (match.group(2) or "").replace("/", "\\")
                configured = drive + ":\\" + rest if rest else drive + ":\\"
        codex_home = Path(configured) if configured else (Path.home() / ".codex")
        root = codex_home / "project-context" / event["project_id"]
    return root / "feedback" / "task-outcome-v3.jsonl"


def _sandbox_fallback_path(event: Mapping[str, Any]) -> Path:
    """中文：返回 Codex workspace-write 沙箱允许的仓库外路径；仅在账户级 CODEX_HOME 写入被拒时使用，完整性或 Schema 错误仍失败关闭，不重定向到新链。

    English: Return a repository-external path permitted by the Codex workspace-write sandbox. Use it only when account-level CODEX_HOME writes are denied; integrity and schema errors still fail closed and never redirect to a fresh chain.
    """
    temp_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir())
    return (
        temp_root
        / "codex-cp-assistant-v7"
        / "project-context"
        / str(event["project_id"])
        / "feedback"
        / "task-outcome-v3.jsonl"
    )


def _session_end_diagnostic(event: Mapping[str, Any], code: str) -> None:
    """中文：有界 SessionEnd 工作失败时输出不含正文的显式状态。

    English: Emit an explicit, body-free status when bounded SessionEnd work fails.
    """
    identity = "|".join(str(event.get(key) or "") for key in (
        "session_id", "turn_id", "task_id", "project_id", "repo_fingerprint"))
    diagnostic = {
        "schema_version": "1.0",
        "component": "cp-assistant-session-end",
        "status": "DEFERRED_OBSERVATION_FAILED",
        "error_code": code,
        "event_ref": "sha256:" + hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        "contains_event_body": False,
    }
    print(json.dumps(diagnostic, ensure_ascii=False, sort_keys=True), file=sys.stderr, flush=True)


def _enqueue_and_launch(event_path: Path, event: Mapping[str, Any]) -> None:
    queue = event_path.parent / "seal-queue-v3"
    if not any(str(event.get(key) or "") for key in ("session_id", "turn_id", "task_id")):
        _session_end_diagnostic(event, "SESSION_END_IDENTITY_UNAVAILABLE")
        return
    identity = {
        key: str(event.get(key) or "")
        for key in ("event_type", "session_id", "turn_id", "task_id", "project_id", "repo_fingerprint")
    }
    queued_event = dict(event)
    queued_event["event_id"] = "EVT_" + hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:32]
    # 中文：SessionEnd Hook 只构造有上限、已净化的事件并启动 detached worker；事件链扫描、语义去重、追加、DPAPI、签名与封印全部移出宿主 3 秒预算。
    # English: The SessionEnd Hook only builds a capped, sanitized event and starts a detached worker. Chain scanning, semantic deduplication, append, DPAPI, signing, and sealing all run outside the host's three-second budget.
    try:
        worker = launch_worker(ROOT, queue, bootstrap_event=queued_event)
        if worker.get("test_wait_status") == "EXITED" and int(worker.get("worker_exit_code", 0)) != 0:
            _session_end_diagnostic(event, "SEAL_WORKER_EXITED_FAILED")
    except Exception:
        # 中文：派发失败不会在 Hook 内回退到事件链 I/O；输出无正文诊断并失败关闭本次终态观测。
        # English: Dispatch failure does not fall back to event-chain I/O in the Hook; emit a body-free diagnostic and fail closed for this terminal observation.
        _session_end_diagnostic(event, "SEAL_WORKER_LAUNCH_FAILED")


def main() -> int:
    data = _read()
    expected_hook = sys.argv[1] if len(sys.argv) > 1 else ""
    allowed_hooks = {"UserPromptSubmit", "PreToolUse", "SubagentStart", "SubagentStop", "Stop", "SessionEnd"}
    if expected_hook not in allowed_hooks:
        expected_hook = ""
    hook_name = str(_lookup(data, *HOOK_ALIASES["hook_event_name"]) or expected_hook)
    if hook_name and "hook_event_name" not in data:
        data["hook_event_name"] = hook_name
    if expected_hook == "PreToolUse" and not str(_lookup(data, *HOOK_ALIASES["tool_name"]) or ""):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": _policy_message("invalid_input")}}, ensure_ascii=False))
        return 0
    guard = _guard(data)
    if guard is not None:
        print(json.dumps(guard, ensure_ascii=False))
        return 0
    try:
        _budget_lifecycle(data, hook_name)
    except (DelegationBudgetError, OSError, TimeoutError) as exc:
        # 中文：启停 Hook 无权回滚已发生的宿主动作；保留预占并输出无正文诊断。
        # English: Lifecycle hooks cannot roll back a host action that already occurred; retain the reservation and emit a body-free diagnostic.
        diagnostic = {"schema_version": "1.0", "component": "delegation-budget",
                      "status": "RECONCILIATION_FAILED", "hook": hook_name,
                      "error_ref": "sha256:" + hashlib.sha256(str(exc).encode("utf-8")).hexdigest()}
        print(json.dumps(diagnostic, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    try:
        event = _event(data)
    except Exception:
        # 中文：部分 Windows 原生宿主路径可能产生不完整或异常的观察元数据；事件构造失败不得阻止 Stop 返回有效中性响应，PreToolUse 模型门禁仍失败关闭。
        # English: Some native Windows host paths may yield incomplete or malformed observation metadata; event-construction failure must not block Stop's neutral response, while the PreToolUse model guard remains fail-closed.
        event = None
    if event is not None:
        try:
            event_path = _data_path(event)
            if event["event_type"] == "SESSION_ENDED":
                _enqueue_and_launch(event_path, event)
            else:
                append_event(event_path, event, os.environ.get("CP_ASSISTANT_HMAC_KEY"))
        except PermissionError:
            try:
                event_path = _sandbox_fallback_path(event)
                if event["event_type"] == "SESSION_ENDED":
                    _enqueue_and_launch(event_path, event)
                else:
                    append_event(event_path, event, os.environ.get("CP_ASSISTANT_HMAC_KEY"))
            except Exception:
                # 中文：观察失败不打断开发任务；模型上限门禁已在前面独立失败关闭。
                # English: Observation failure does not interrupt engineering work; the model-ceiling guard has already failed closed independently.
                if event["event_type"] == "SESSION_ENDED":
                    _session_end_diagnostic(event, "SESSION_END_FALLBACK_ENQUEUE_FAILED")
        except Exception:
            # 中文：数据损坏或哈希链错误不得通过创建新链绕过。
            # English: Data corruption or hash-chain failure must not be bypassed by creating a fresh chain.
            if event["event_type"] == "SESSION_ENDED":
                _session_end_diagnostic(event, "SESSION_END_ENQUEUE_FAILED")
    # 中文：正常 Stop 处理返回宿主规定的中性响应；上方恢复逻辑确保 Windows 截断非 ASCII last_assistant_message 时仍能进入该分支。
    # English: Normal Stop handling returns the host-defined neutral response; the recovery above preserves this branch when Windows truncates a non-ASCII last_assistant_message.
    if hook_name in {"Stop", "SubagentStop"}:
        print("{}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        # 中文：生命周期观察可失败开放，但意外的 PreToolUse 失败绝不能变成模型策略的隐式放行。
        # English: Lifecycle observation is fail-open, but an unexpected PreToolUse failure must never become an implicit model-policy allow.
        expected = sys.argv[1] if len(sys.argv) > 1 else ""
        if expected == "PreToolUse":
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": _policy_message("hook_failure")}}, ensure_ascii=False))
        elif expected in {"Stop", "SubagentStop"}:
            print("{}")
        raise SystemExit(0)
