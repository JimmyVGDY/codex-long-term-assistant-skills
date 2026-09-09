"""中文：项目显式启用和任务流程命令；宿主起点与原始完成hash不向CLI开放。

English: Explicit project opt-in and task commands; no CLI creation of host origins or caller finish hashes.
"""
from __future__ import annotations

import json
from pathlib import Path

from .capability_gate import GatePolicy, GateTask
from .capability_gate_workflow import GateWorkflow
from .capability_store import CapabilityError, CapabilityStore, bounded_read, unique_json_object


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
    task = GateTask(policy, args.session_id, args.turn_id)
    workflow = GateWorkflow(task)
    before = task.read()
    try:
        if args.gate_action == "prepare":
            return workflow.prepare(args.scope, args.term, initial_scan_required=args.local_only_reason is None,
                                    local_only_reason=args.local_only_reason or "")
        if args.gate_action == "finish":
            decisions = []
            if args.decisions:
                try:
                    decisions = json.loads(bounded_read(Path(args.decisions), 16 * 1024),
                                           object_pairs_hook=unique_json_object)
                except (ValueError, UnicodeError, RecursionError):
                    raise CapabilityError("GATE_DECISIONS_JSON") from None
            return workflow.finish(decisions)
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
            parser.add_argument("--session-id", required=True)
            parser.add_argument("--turn-id", required=True)
            if action == "prepare":
                parser.add_argument("--scope", action="append", required=True,
                                    help="Explicit file prepared before editing; repeat for additional files.")
                parser.add_argument("--term", required=True)
                parser.add_argument("--local-only-reason", help="Source-based reason for a local fix in one existing file. Public API extension or coordinated caller changes need initial scanning; multiple/new files cannot use the cold exception. Not semantic approval.")
            elif action == "finish":
                parser.add_argument("--decisions", help="Bounded JSON list covering required decisions. Store the task-specific file in authorized external context, outside the repository and runtime-managed files.")
