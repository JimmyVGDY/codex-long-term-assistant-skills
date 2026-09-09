"""中文：项目显式启用和任务流程命令；宿主起点与原始完成hash不向CLI开放。

English: Explicit project opt-in and task commands; no CLI creation of host origins or caller finish hashes.
"""
from __future__ import annotations

import json
from pathlib import Path

from .capability_gate import GatePolicy, GateTask
from .capability_gate_workflow import GateWorkflow
from .capability_operation import CapabilityOperation
from .capability_operation_workflow import OperationWorkflow
from .capability_store import CapabilityError, CapabilityStore, bounded_read, unique_json_object


def _decisions(path: str | None) -> list[dict[str, str]]:
    if not path:
        return []
    try:
        value = json.loads(bounded_read(Path(path), 16 * 1024),
                           object_pairs_hook=unique_json_object)
    except (ValueError, UnicodeError, RecursionError):
        raise CapabilityError("GATE_DECISIONS_JSON") from None
    if not isinstance(value, list):
        raise CapabilityError("GATE_DECISIONS_JSON")
    return value


def run(args):
    store = CapabilityStore(Path(args.profile), Path(args.repo_path), Path(args.index_root) if args.index_root else None)
    policy = GatePolicy(store, Path(args.gate_root) if args.gate_root else None)
    if args.gate_action in {"enable", "disable"}:
        return {"policy": policy.set_enabled(args.gate_action == "enable", args.expected_revision),
                "execution_authorization": "NONE"}
    if args.gate_action == "status":
        value = policy.read()
        return {"configured": value is not None, "enabled": bool(value and value["enabled"]),
                "policy": value, "execution_authorization": "NONE"}
    operation_ref = getattr(args, "operation_ref", None)
    session_id, turn_id = getattr(args, "session_id", None), getattr(args, "turn_id", None)
    if bool(operation_ref) == bool(session_id or turn_id):
        raise CapabilityError("GATE_PROTOCOL_SELECTION")
    if operation_ref:
        operation = CapabilityOperation.open(policy, operation_ref)
        workflow = OperationWorkflow(operation)
        if args.gate_action == "prepare":
            if args.local_only_reason is not None:
                raise CapabilityError("OP_LOCAL_ONLY_UNSUPPORTED")
            return workflow.prepare(operation_ref, term=args.term, scopes=args.scope)
        if args.gate_action == "finish":
            state = operation.check(operation_ref)
            tool_use_id = state.get("dispatch_tool_use_id")
            if not tool_use_id:
                raise CapabilityError("OP_DISPATCH_REQUIRED")
            return workflow.finish(operation_ref, tool_use_id=tool_use_id,
                                   decisions=_decisions(args.decisions))
        if args.gate_action == "cancel":
            return workflow.cancel(operation_ref)
        return workflow.check(operation_ref)
    if not session_id or not turn_id:
        raise CapabilityError("GATE_HOST_IDENTITY_MISSING")
    task = GateTask(policy, args.session_id, args.turn_id)
    workflow = GateWorkflow(task)
    before = task.read()
    try:
        if args.gate_action == "prepare":
            return workflow.prepare(args.scope, args.term, initial_scan_required=args.local_only_reason is None,
                                    local_only_reason=args.local_only_reason or "")
        if args.gate_action == "finish":
            return workflow.finish(_decisions(args.decisions))
        if args.gate_action == "cancel":
            return {"state": task.cancel(), "semantic_reuse_approved": False}
        return workflow.check()
    except CapabilityError as exc:
        state = workflow.record_failure(str(exc), before["revision"])
        if state is None:
            raise
        return {"state": state, "error": str(exc), "semantic_reuse_approved": False}


def _emit(args):
    result = run(args)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    if "error" in result:
        raise SystemExit(1)


def add_commands(subparsers):
    for action in ("enable", "disable", "status", "prepare", "finish", "check", "cancel"):
        namespace = "capability-gate-" if action in {"enable", "disable", "status"} else "capability-task-"
        parser = subparsers.add_parser(namespace + action)
        parser.add_argument("--profile", required=True)
        parser.add_argument("--repo-path", required=True)
        parser.add_argument("--index-root")
        parser.add_argument("--gate-root", help="External opt-in policy directory; normally omit for account default.")
        parser.set_defaults(gate_action=action, func=_emit)
        if action in {"enable", "disable"}:
            parser.add_argument("--expected-revision", type=int, required=action == "disable")
        elif action not in {"status"}:
            parser.add_argument("--operation-ref",
                                help="Existing Operation v2 reference created by PreToolUse A; the CLI never creates origins or dispatch IDs.")
            parser.add_argument("--session-id", help="Legacy GateTask v1 session identity.")
            parser.add_argument("--turn-id", help="Legacy GateTask v1 turn identity.")
            if action == "prepare":
                parser.add_argument("--scope", action="append",
                                    help="Legacy explicit scope, or an optional exact cross-check of Operation v2 targets.")
                parser.add_argument("--term", required=True)
                parser.add_argument("--local-only-reason", help="Source-based reason for a local fix in one existing file. Public API extension or coordinated caller changes need initial scanning; multiple/new files cannot use the cold exception. Not semantic approval.")
            elif action == "finish":
                parser.add_argument("--decisions", help="Bounded JSON list covering required decisions. Store the task-specific file in authorized external context, outside the repository and runtime-managed files.")
