"""中文：独立 GPT-6 策略与预算流水的 Hook 适配器。

English: Hook adapter for the independent GPT-6 policy and budget journal.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from . import g6_budget_v1 as budget, g6_handoff_v1 as handoff, research_campaign
from .g6_flexible_policy import PROFILES, decide, policy, profile_spec
from .g6_fact_collector import (ALL_REPO_SCOPE, MetricReceiptIntegrityError,
                                collect as collect_scope_facts, store_metric_receipt)
from .common import RuntimeContractError, repo_snapshot, resolve_codex_home, utc_now
from .dispatch_policy import delegation_tool_name
from .event_v2 import project_identity_for
from .routing_contract import _constant, _object, fail, ref


def _deny(code: str, *, next_action: str = "continue_local") -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "deny", "permissionDecisionReason":
            f"{code}; next_action={next_action}"}}


def _root_path(session: str) -> Path:
    return resolve_codex_home() / "cp-assistant" / "g6-routing" / "roots" / (ref(session)[7:] + ".jsonl")


def _ensure_new_session(data: Mapping[str, Any]) -> bool:
    """中文：仅在旧受管研究头没有占用该聊天时使用已安装默认。

    English: Use the installed default only when no older managed research head owns this chat.
    """
    session, cwd = data.get("session_id"), data.get("cwd")
    if not isinstance(session, str) or not session or not isinstance(cwd, str) or not cwd:
        return False
    if os.environ.get("CP_DELEGATION_BUDGET_PATH", "").strip():
        return False
    from .g6_default_activation import resolve as resolve_current_default
    if resolve_current_default(session_id=session, cwd=Path(cwd))["status"] != "NEW_TASK_DEFAULT":
        return False
    repo = Path(cwd).resolve()
    fingerprint, project_id = project_identity_for(cwd)
    identity = {"project_id": project_id, "repo_fingerprint": fingerprint}
    task_id = str(data.get("task_id") or session)
    path = _root_path(session)
    budget.initialize(path, identity_value=identity, host_session_id=session,
                      repo_path=repo, task_id=task_id,
                      authorization_ref=ref({"source": "installed-g6-default",
                                             "session_ref": ref(session),
                                             "repo_fingerprint": fingerprint}))
    handoff.bind(session_id=session, repo_path=repo, new_ledger_path=path,
                 user_change_ref=ref({"source": "installed-g6-default",
                                      "session_ref": ref(session)}))
    return True


def _facts(root: Mapping[str, Any], args: Mapping[str, Any], *, persist: bool = False) -> dict[str, Any]:
    sources: list[str] = []
    try:
        snapshot = repo_snapshot(Path(root["repo_path"]))
        baseline = snapshot["sha256"]
        missing = ["task_classification", "quality_card", "gain_card", "historical_samples"]
        try:
            scope_facts = collect_scope_facts(Path(root["repo_path"]),
                                              baseline_commit=snapshot["head"],
                                              scope_paths=[ALL_REPO_SCOPE])
            receipt_ref = (store_metric_receipt(scope_facts, identity=dict(root["identity"]),
                                                host_session_ref=root["host_session_ref"],
                                                baseline_sha256=baseline,
                                                repo_path=Path(root["repo_path"]))
                           if persist else None)
            if receipt_ref is not None:
                sources.append(receipt_ref)
            if scope_facts["collection_status"] != "COMPLETE":
                missing.append("scope_metrics")
            elif scope_facts["changed_lines"] is None:
                missing.append("changed_lines")
        except MetricReceiptIntegrityError:
            raise
        except (OSError, ValueError, TimeoutError, RuntimeError):
            # 中文：可选 Git 范围测量失败不升级为任务难度或派发资格墙。
            # English: Optional Git scope collection cannot become a difficulty or dispatch gate.
            missing.append("scope_metrics")
    except (OSError, ValueError, TimeoutError, RuntimeContractError):
        baseline = None
        missing = ["baseline_sha256", "task_classification", "quality_card",
                   "gain_card", "historical_samples", "scope_metrics"]
    scope = {"session_ref": root["host_session_ref"], "task_name": args["task_name"],
             "message_sha256": hashlib.sha256(args["message"].encode("utf-8")).hexdigest()}
    work_item_id = ref({"role": args["agent_type"], "message_sha256": scope["message_sha256"]})
    return {"schema_version": "g6-task-facts/1", "identity": root["identity"],
            "task_id": root["task_id"], "work_item_id": work_item_id,
            "baseline_sha256": baseline, "scope_ref": ref(scope),
            "task_kind": "unknown", "task_kind_source": "unknown", "source_refs": sources,
            "missing_evidence": missing}


def preview(*, session_id: str, cwd: Path, agent_type: str, task_name: str,
            message: str, requested_profile: str | None = None,
            turn_id: str | None = None) -> dict[str, Any]:
    """中文：只读预览 Desktop 决策，实际许可由 Hook 签发。

    English: Read-only Desktop decision preview; the Hook issues the actual permit.
    """
    binding = handoff.read(session_id)
    if binding is not None:
        state = budget.read_budget(Path(binding["new_ledger_path"]))
        root = state["root"]
        if Path(root["repo_path"]).resolve() != cwd.resolve():
            fail("G6_PREVIEW_REPOSITORY_CONFLICT")
        item = _facts(root, {"task_name": task_name, "agent_type": agent_type,
                             "message": message})
        view = budget.snapshot(state, work_item_id=item["work_item_id"], depth=0)
    else:
        if research_campaign._head(session_id).exists():
            fail("G6_PREVIEW_HANDOFF_REQUIRED")
        from .routing_registry_v4 import lookup as legacy_lookup
        from .routing_registry_v5 import lookup as v5_lookup
        if v5_lookup(host_session_id=session_id) is not None or \
                legacy_lookup(cwd=str(cwd), host_session_id=session_id) is not None:
            fail("G6_PREVIEW_LEGACY_ROOT_ACTIVE")
        fingerprint, project_id = project_identity_for(str(cwd))
        root = {"identity": {"project_id": project_id, "repo_fingerprint": fingerprint},
                "task_id": session_id, "host_session_ref": ref(session_id),
                "repo_path": str(cwd.resolve())}
        item = _facts(root, {"task_name": task_name, "agent_type": agent_type,
                             "message": message})
        config = policy()
        view = {"schema_version": "g6-budget-snapshot/1", "ledger_head": "0" * 64,
                "capacity_class": "STANDARD",
                "capacity_units": config["budget_templates"]["STANDARD"]["units"],
                "capacity_attempts": config["budget_templates"]["STANDARD"]["attempts"],
                "completed_charged_units": 0, "completed_charged_attempts": 0,
                "inflight_reserved_units": 0, "inflight_reserved_attempts": 0,
                "future_required_hold_units": 0, "future_required_hold_attempts": 0,
                "parallel_limit": config["concurrency_defaults"]["STANDARD"]["parallel"],
                "active_calls": 0, "depth_limit": config["concurrency_defaults"]["STANDARD"]["depth"],
                "depth": 0, "astra_active": 0, "upward_adjustments_used": 0}
    if requested_profile is not None and requested_profile not in PROFILES:
        fail("G6_PREVIEW_PROFILE")
    from .g6_user_choice_v1 import read_choice
    choice = read_choice(session_id=session_id, turn_id=turn_id or "", cwd=cwd)
    if choice is not None:
        if requested_profile is not None and requested_profile != choice["profile_id"]:
            fail("G6_PREVIEW_USER_PROFILE_CONFLICT")
        requested_profile = choice["profile_id"]
    adjustment = ({"requested_profile": requested_profile, "source": "model_semantic",
                   "reason": "", "source_ref": None}
                  if choice is None and requested_profile is not None
                  and requested_profile != "g6-sol-medium" else None)
    return decide(facts=item, budget=view,
                  capability={"schema_version": "g6-desktop-capability/1",
                              "available_profiles": None, "source_ref": None},
                  gates=[], agent_type=agent_type, task_name=task_name,
                  message=message, decision_time=utc_now(), adjustment=adjustment,
                  explicit_user_profile=choice["profile_id"] if choice else None)


def _pretool(path: Path, data: Mapping[str, Any], args: Mapping[str, Any]) -> dict[str, Any]:
    root = budget.read_budget(path)["root"]
    if data.get("agent_id"):
        return _deny("G6_NESTED_NATIVE_BINDING_UNAVAILABLE",
                     next_action="continue_local_or_request_parent_dispatch")
    if root["capacity_class"] != "STANDARD":
        return _deny("G6_NONDEFAULT_CAPACITY_NEEDS_TRUSTED_CONTROLLER")
    if not isinstance(args.get("message"), str) or not args["message"]:
        return _deny("G6_MESSAGE_REQUIRED")
    task_name = args.get("task_name")
    if not isinstance(task_name, str):
        return _deny("G6_TASK_NAME_REQUIRED")
    state = budget.read_budget(path)
    from .g6_user_choice_v1 import read_choice
    user_choice = read_choice(session_id=str(data["session_id"]),
                              turn_id=str(data.get("turn_id") or ""),
                              cwd=Path(str(data["cwd"])))
    matches = [p for p in state["permits"].values() if p["task_name"] == task_name]
    if matches:
        matches.sort(key=lambda item: item["prepared_at"])
        latest = matches[-1]
        if latest["permit_id"] not in state["reservations"] and \
                budget.parse_iso(utc_now()) >= budget.parse_iso(latest["expires_at"]):
            matches = []
        else:
            matches = [latest]
    if not matches:
        collected = _facts(root, args, persist=True)
        requested = next((name for name in PROFILES
                          if profile_spec(name)["model"] == args.get("model")
                          and profile_spec(name)["effort"] == args.get("reasoning_effort")), None)
        if requested is None:
            return _deny("G6_GPT6_PROFILE_REQUIRED", next_action="use_available_gpt6_tuple")
        if user_choice is not None and requested != user_choice["profile_id"]:
            selected = profile_spec(user_choice["profile_id"])
            return _deny("G6_USER_PROFILE_REQUIRED_" + selected["model"] + "_" + selected["effort"],
                         next_action="retry_with_user_selected_tuple")
        adjustment = ({"requested_profile": requested, "source": "model_semantic",
                       "reason": "", "source_ref": None}
                      if user_choice is None and requested != "g6-sol-medium" else None)
        prepared = budget.prepare(path, facts=collected,
                                  capability={"schema_version": "g6-desktop-capability/1",
                                              "available_profiles": None, "source_ref": None},
                                  gates=[], agent_type=args.get("agent_type"),
                                  task_name=task_name, message=args["message"],
                                  decision_time=utc_now(), adjustment=adjustment,
                                  explicit_user_profile=user_choice["profile_id"] if user_choice else None,
                                  depth=1 if data.get("agent_id") else 0)
        if prepared["permit_id"] is None:
            decision = prepared["decision"]
            return _deny("G6_" + decision["decision"], next_action=decision["next_action"])
        permit_id = prepared["permit_id"]
        expected = prepared["decision"]["exact_tool_parameters"]
    else:
        permit_id = matches[0]["permit_id"]
        prior = matches[0]
        if (prior["facts"]["task_kind_source"] not in {"unknown", "semantic_proposal"}
                or (prior["explicit_user_profile"] is not None and
                    (user_choice is None or user_choice["profile_id"] != prior["explicit_user_profile"]))
                or prior["adjustment"] is not None and prior["adjustment"]["source"] != "model_semantic"
                or prior["capability"]["available_profiles"] is not None
                or any(gate["state"] != "MISSING_EVIDENCE" for gate in prior["gates"])):
            return _deny("G6_UNTRUSTED_SOURCE_LABEL", next_action="use_default_or_verified_controller")
        expected = {"task_name": matches[0]["task_name"], "agent_type": matches[0]["agent_type"],
                    "model": matches[0]["model"], "reasoning_effort": matches[0]["reasoning_effort"],
                    "fork_turns": "none"}
    if any(args.get(key) != value for key, value in expected.items()
           if key != "message"):
        return _deny("G6_EXACT_PROFILE_REQUIRED_" + str(expected["model"]) + "_" +
                     str(expected["reasoning_effort"]), next_action="retry_with_exact_parameters")
    if collected := (matches[0]["facts"] if matches else collected):
        prior = collected["baseline_sha256"]
        if prior is not None:
            try:
                if repo_snapshot(Path(root["repo_path"]))["sha256"] != prior:
                    return _deny("G6_BASELINE_CHANGED", next_action="reprepare")
            except (OSError, ValueError, TimeoutError, RuntimeContractError):
                # 中文：可选快照缺失不能伪装成已确认的不一致。
                # English: A missing optional snapshot never turns into a fake mismatch.
                pass
    try:
        budget.approve_and_reserve(path, permit_id=permit_id,
                                   host_call_id=str(data.get("tool_use_id") or ""),
                                   session_id=str(data["session_id"]), cwd=Path(str(data["cwd"])),
                                   args=args, now=utc_now(), depth=1 if data.get("agent_id") else 0)
    except (ValueError, OSError, TimeoutError) as exc:
        return _deny(str(exc), next_action="reprepare_or_continue_local")
    return {}


def _posttool(path: Path, data: Mapping[str, Any], args: Mapping[str, Any]) -> dict[str, Any]:
    response = data.get("tool_response")
    if isinstance(response, str):
        try:
            response = json.loads(response, object_pairs_hook=_object, parse_constant=_constant)
        except (ValueError, UnicodeError):
            return {}
    expected = "/root/" + str(args.get("task_name") or "")
    if not isinstance(response, dict) or response.get("task_name") != expected:
        # 中文：宿主响应含糊时，保持费用和在途状态，等待有证据的恢复。
        # English: Ambiguous host response remains charged and in flight until genuine recovery.
        return {}
    budget.record_receipt(path, host_call_id=str(data.get("tool_use_id") or ""),
                          disposition="created", agent_path=expected,
                          proof_ref=ref({"source": "native-post-tool", "session_ref": ref(data["session_id"]),
                                         "call_ref": ref(data["tool_use_id"]),
                                         "response_ref": ref(response)}))
    return {}


def _terminal(path: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    from .g6_handoff_v1 import _child_task_path
    from .routing_hook_v5 import _transcript_path

    task = _child_task_path(dict(data))
    state = budget.read_budget(path)
    matched = [permit_id for permit_id, receipt in state["receipts"].items()
               if receipt["disposition"] == "created" and receipt["agent_ref"] == ref(task)]
    if len(matched) == 1 and matched[0] in state["terminals"]:
        # 中文：同一已创建子任务的原生 Stop 已结算后，转录后续追加不得改写结果或重复计费。
        # English: A later transcript append must not rewrite or double-charge the
        # native Stop already settled for this same created child.
        return {}
    transcript = _transcript_path(data)
    with transcript.open("rb") as stream:
        raw = stream.read(2_000_001)
    if len(raw) > 2_000_000 or (raw and not raw.endswith(b"\n")):
        return {}
    terminal_kind = None
    final_refs = []
    try:
        for line in raw.splitlines():
            event = json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
            payload = event.get("payload")
            if event.get("type") == "event_msg" and isinstance(payload, dict):
                if payload.get("type") in {"turn_aborted", "turn_complete", "task_complete"}:
                    terminal_kind = payload["type"]
            if (event.get("type") == "response_item" and isinstance(payload, dict)
                    and payload.get("type") == "message" and payload.get("role") == "assistant"
                    and payload.get("phase") in {"final", "final_answer"}):
                content = payload.get("content")
                if (not isinstance(content, list) or len(content) != 1
                        or not isinstance(content[0], dict)
                        or content[0].get("type") != "output_text"
                        or not isinstance(content[0].get("text"), str)):
                    return {}
                final_refs.append(ref(payload))
    except (ValueError, UnicodeError, RecursionError):
        return {}
    if terminal_kind is None:
        if len(final_refs) != 1:
            return {}
        terminal_kind = "native_stop_with_final_answer"
    host_outcome = str(data.get("terminal_outcome") or "UNKNOWN").upper()
    outcome = "CANCELLED" if terminal_kind == "turn_aborted" else (
        "UNKNOWN" if terminal_kind == "native_stop_with_final_answer" else
        host_outcome if host_outcome in budget.OUTCOMES else "UNKNOWN")
    budget.record_terminal(path, agent_path=task, outcome=outcome,
                           proof_ref=ref({"source": "native-subagent-stop",
                                          "child_ref": ref(data["agent_id"]),
                                          "task_path_ref": ref(task),
                                          "transcript_sha256": hashlib.sha256(raw).hexdigest(),
                                          "terminal_kind": terminal_kind,
                                          "final_ref": final_refs[-1] if final_refs else None,
                                          "host_outcome": host_outcome}))
    from .g6_review_receipt_v1 import ingest
    ingest(path, raw_transcript=raw, task_path=task)
    return {}


def handle(data: dict[str, Any], hook_name: str) -> tuple[bool, dict[str, Any] | None]:
    """中文：返回是否已处理及响应；旧归属事件继续交给冻结的 V5。

    English: Return handled/response; old-owner events fall through to frozen V5.
    """
    session = data.get("session_id")
    if not isinstance(session, str) or not session:
        return False, None
    if hook_name == "UserPromptSubmit":
        from .g6_user_choice_v1 import observe_native_prompt
        try:
            observe_native_prompt(data)
        except (OSError, ValueError, TimeoutError):
            # 中文：可选偏好记录不得阻止用户提示提交。
            # English: An optional preference record must never block the user prompt.
            pass
        return False, None
    tool = delegation_tool_name(data.get("tool_name"))
    delegated = tool == "spawn_agent"
    if (handoff.read(session) is None and hook_name == "PreToolUse" and delegated
            and not data.get("agent_id")):
        if not _ensure_new_session(data):
            return False, None
    owner = handoff.route(data)
    if owner is None or owner[0] == "old":
        return False, None
    path = owner[1]
    if hook_name == "PreToolUse" and tool in {
            "followup_task", "send_input", "resume_agent", "send_message"}:
        if tool != "send_message":
            return True, _deny("G6_CONTINUATION_HOST_BINDING_UNAVAILABLE",
                               next_action="spawn_agent_with_new_budget_permit")
        inputs = data.get("tool_input")
        target = inputs.get("target") if isinstance(inputs, Mapping) else None
        if not isinstance(target, str) or not target:
            return True, _deny("G6_MESSAGE_TARGET_REQUIRED")
        if data.get("agent_id"):
            # 中文：归属路由已核验原生子任务头；回传还要求其创建回执仍活跃。
            # English: Ownership routing verified the native child header; parent
            # reporting additionally requires its created receipt to remain active.
            task = handoff._child_task_path(data)
            state = budget.read_budget(path)
            active = [pid for pid, receipt in state["receipts"].items()
                      if receipt["disposition"] == "created"
                      and receipt["agent_ref"] == ref(task)
                      and pid not in state["terminals"]]
            if len(active) != 1:
                return True, _deny("G6_MESSAGE_SOURCE_NOT_ACTIVE_IN_ROOT")
            if target == "/root":
                return True, {}
        path_name = target if target.startswith("/root/") else "/root/" + target
        state = budget.read_budget(path)
        matching = [pid for pid, receipt in state["receipts"].items()
                    if receipt["disposition"] == "created"
                    and receipt["agent_ref"] == ref(path_name)
                    and pid not in state["terminals"]]
        if len(matching) != 1:
            return True, _deny("G6_MESSAGE_TARGET_NOT_ACTIVE_IN_ROOT")
        return True, {}
    if hook_name == "PreToolUse" and delegated:
        inputs = data.get("tool_input")
        if not isinstance(inputs, Mapping):
            return True, _deny("G6_TOOL_INPUT_REQUIRED")
        return True, _pretool(path, data, inputs)
    if hook_name == "PostToolUse" and delegated and not data.get("agent_id"):
        return True, _posttool(path, data, data.get("tool_input") or {})
    if hook_name == "SubagentStart":
        return True, {}
    if hook_name == "SubagentStop":
        return True, _terminal(path, data)
    if hook_name == "Stop" and not data.get("agent_id"):
        from .g6_review_receipt_v1 import project_delivery
        project_delivery(path)
        return False, None
    return False, None
