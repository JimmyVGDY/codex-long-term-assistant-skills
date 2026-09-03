#!/usr/bin/env python3
"""中文：Codex V7.4 生命周期 Hook：模型上限、统一委派预算与最小元数据观测。

English: Codex V6 lifecycle Hook for model-ceiling enforcement and minimal local metadata observation.
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
from cp_runtime.event_v2 import append_event, project_id_for, stable_repo_fingerprint  # noqa: E402
from cp_runtime.delegation_budget import (  # noqa: E402
    DelegationBudgetError, mark_completed, mark_started, profile_for, read_budget,
    reserve_budget,
)
from cp_runtime.model_evidence import verify_hook_runtime_evidence  # noqa: E402
from cp_runtime.seal_queue import enqueue_session_end, launch_worker  # noqa: E402

ALLOWED_REASONING = {"", "none", "minimal", "low", "medium", "high"}
ALLOWED_AUTOMATIC_MODELS = {"gpt-5.6-luna", "gpt-5.6-terra"}
DENY_MARKERS = ("sol", "gpt-5.6-sol", "xhigh", "extra-high", "extra_high", "ultra", "max")
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


def _lookup(data: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in data and data.get(name) is not None:
            return data.get(name)
    return None


def _tool_input(data: Mapping[str, Any]) -> Mapping[str, Any]:
    candidate = _lookup(data, "tool_input", "input", "arguments")
    return candidate if isinstance(candidate, Mapping) else {}


def _guard(data: Mapping[str, Any]) -> Dict[str, Any] | None:
    tool = str(_lookup(data, "tool_name", "tool") or "").lower()
    if tool not in {"agent", "spawn_agent"}:
        return None
    args = _tool_input(data)
    model = str(_lookup(args, "model", "model_name") or "").strip().lower()
    effort = str(_lookup(args, "reasoning_effort", "reasoning", "effort") or "").strip().lower()
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
            dispatch_key = str(_lookup(args, "task_name", "taskName", "dispatch_key", "delegation_key") or "").strip()
            host_dispatch_id = str(_lookup(data, "tool_use_id", "toolUseId", "tool_call_id", "toolCallId") or "").strip()
            role = str(_lookup(args, "agent_type", "agentType", "role") or "").strip()
            if not dispatch_key or not host_dispatch_id or not role:
                reason = _policy_message("budget_input")
            else:
                try:
                    state = read_budget(Path(ledger_text).expanduser().resolve())
                    profile, basis = profile_for(model, effort, state["default_model_profile"])
                    reservation = reserve_budget(
                        Path(ledger_text).expanduser().resolve(), dispatch_key=dispatch_key,
                        host_dispatch_id=host_dispatch_id, requested_profile=profile,
                        request_basis=basis, role=role,
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
    """中文：只在宿主显式传播 reservation_id 时对账；0.153.0 缺失时保留 RESERVED。

    English: Reconcile only when the host explicitly propagates reservation_id; keep RESERVED when Codex 0.153.0 omits it.
    """
    ledger_text = os.environ.get("CP_DELEGATION_BUDGET_PATH", "").strip()
    if not ledger_text or hook_name not in {"SubagentStart", "SubagentStop"}:
        return
    reservation_id = str(_lookup(data, "delegation_id", "delegationId", "reservation_id", "reservationId") or "").strip()
    agent_id = str(_lookup(data, "agent_id", "agentId") or "").strip()
    if not reservation_id or not agent_id:
        return
    ledger = Path(ledger_text).expanduser().resolve()
    if hook_name == "SubagentStart":
        runtime = verify_hook_runtime_evidence(data, hook_name)
        actual_profile = ""
        evidence = "unavailable"
        if runtime["status"] == "VERIFIED":
            actual_profile, _basis = profile_for(runtime["model"], runtime["reasoning_effort"], "luna-low")
            evidence = "host-attested-hook-payload"
        mark_started(ledger, reservation_id=reservation_id, agent_id=agent_id,
                     actual_profile=actual_profile, runtime_evidence=evidence)
    else:
        outcome = str(_lookup(data, "terminal_outcome", "outcome") or "UNKNOWN").upper()
        mark_completed(ledger, reservation_id=reservation_id, outcome=outcome)


def _event(data: Mapping[str, Any]) -> Dict[str, Any] | None:
    hook = str(_lookup(data, "hook_event_name", "hookEventName", "event_name", "event") or "")
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
    cwd = str(_lookup(data, "cwd", "working_directory") or os.getcwd())
    fingerprint = stable_repo_fingerprint(cwd)
    session_id = str(_lookup(data, "session_id", "sessionId", "thread_id") or "")
    turn_id = str(_lookup(data, "turn_id", "turnId") or "")
    task_id = str(_lookup(data, "task_id", "taskId") or turn_id or session_id)
    # 中文：实际运行值需要外部配置的宿主信任锚；Codex 0.153.0 的普通 Hook 字段不构成此证明。
    # English: Actual runtime values require an external host trust anchor; ordinary Codex 0.153.0 Hook fields do not provide that attestation.
    runtime_evidence = verify_hook_runtime_evidence(data, hook)
    model = runtime_evidence["model"] if runtime_evidence["status"] == "VERIFIED" else ""
    effort = runtime_evidence["reasoning_effort"] if runtime_evidence["status"] == "VERIFIED" else ""
    terminal_value = data.get("terminal_outcome") if event_type == "TASK_COMPLETED" else None
    terminal = str(terminal_value or "UNKNOWN").upper()
    metadata: Dict[str, Any] = {}
    for key in ("agent_id", "agent_type", "permission_mode", "tool_name", "stop_hook_active"):
        value = data.get(key)
        if value is not None:
            metadata[key] = value
    metadata["runtime_model_evidence"] = runtime_evidence["status"]
    metadata["runtime_model_evidence_reason"] = runtime_evidence["reason_code"]
    if runtime_evidence.get("attestation_id"):
        metadata["host_attestation_ref"] = "sha256:" + hashlib.sha256(
            runtime_evidence["attestation_id"].encode("utf-8")).hexdigest()
    return {
        "event_type": event_type,
        "session_id": session_id,
        "turn_id": turn_id,
        "task_id": task_id,
        "project_id": project_id_for(fingerprint, cwd),
        "repo_fingerprint": fingerprint,
        "terminal_outcome": terminal,
        "terminal_outcome_source": "hook-payload" if terminal_value is not None and terminal != "UNKNOWN" else "unavailable",
        "actual_model": model,
        "actual_model_source": "host-attested-hook-payload" if model else "unavailable",
        "actual_reasoning_effort": effort,
        "actual_reasoning_effort_source": "host-attested-hook-payload" if effort else "unavailable",
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
    return root / "feedback" / "task-outcome-v2.jsonl"


def _sandbox_fallback_path(event: Mapping[str, Any]) -> Path:
    """中文：返回 Codex workspace-write 沙箱允许的仓库外路径；仅在账户级 CODEX_HOME 写入被拒时使用，完整性或 Schema 错误仍失败关闭，不重定向到新链。

    English: Return a repository-external path permitted by the Codex workspace-write sandbox. Use it only when account-level CODEX_HOME writes are denied; integrity and schema errors still fail closed and never redirect to a fresh chain.
    """
    temp_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir())
    return (
        temp_root
        / "codex-cp-assistant-v6"
        / "project-context"
        / str(event["project_id"])
        / "feedback"
        / "task-outcome-v2.jsonl"
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
    queue = event_path.parent / "seal-queue"
    enqueue_session_end(queue, event)
    try:
        launch_worker(ROOT, queue)
    except Exception:
        # 中文：已签名 pending 任务保持持久，可由后续 worker 恢复；启动失败需显式报告。
        # English: The signed pending job remains durable and recoverable by a later worker; report launch failure explicitly.
        _session_end_diagnostic(event, "SEAL_WORKER_LAUNCH_FAILED")


def main() -> int:
    data = _read()
    expected_hook = sys.argv[1] if len(sys.argv) > 1 else ""
    allowed_hooks = {"UserPromptSubmit", "PreToolUse", "SubagentStart", "SubagentStop", "Stop", "SessionEnd"}
    if expected_hook not in allowed_hooks:
        expected_hook = ""
    hook_name = str(_lookup(data, "hook_event_name", "hookEventName", "event_name", "event") or expected_hook)
    if hook_name and "hook_event_name" not in data:
        data["hook_event_name"] = hook_name
    if expected_hook == "PreToolUse" and not str(_lookup(data, "tool_name", "tool") or ""):
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
    if hook_name == "Stop":
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
        elif expected == "Stop":
            print("{}")
        raise SystemExit(0)
