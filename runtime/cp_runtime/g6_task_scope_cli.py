"""中文：Desktop 任务范围的内部管理入口，不启动模型或授予文件权限。
English: Internal Desktop task management; no model execution or file permission grant.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import g6_task_origin as origin, g6_task_scope as scope
from .capability_store import bounded_read
from .common import RuntimeContractError


def run(args):
    cwd = Path(args.repo_path).resolve()
    if args.command in {"task-scope-origins", "task-scope-recover-source"}:
        try:
            value = (origin.prepare(args.session_id, cwd, before_byte=args.before_byte) if args.command == "task-scope-origins"
                     else origin.recover_source(args.session_id, cwd, Path(args.transcript_path) if args.transcript_path else None))
        except (OSError, ValueError, RuntimeContractError) as exc:
            print(json.dumps(origin.diagnose(args.session_id, cwd, error=exc), ensure_ascii=False, indent=2))
            raise SystemExit(1) from None
    elif args.command == "task-scope-select":
        value = scope.select(session=args.session_id, cwd=cwd, task_id=args.task_id,
                             origin_ref=args.origin_ref, relation=args.relation, task_scope=args.task_scope)
    elif args.command == "task-scope-complete":
        value = scope.complete(args.session_id, cwd, args.task_scope)
    elif args.command == "task-scope-preview":
        from .g6_hook_v1 import preview
        value = preview(session_id=args.session_id, cwd=cwd, task_scope=args.task_scope,
                        agent_type=args.agent_type, task_name=args.task_name,
                        message=bounded_read(Path(args.message_file), 262_144).decode("utf-8"),
                        requested_profile=args.model_profile)
    else:
        value = scope.registry(args.session_id)
        if value is None:
            value = {"schema_version": "g6-task-scope-view/1", "legacy": scope.read(args.session_id),
                     "next_action": "bind_existing_task_before_selecting_independent_goal"}
        elif not scope.same_path(Path(value["repo_path"]), cwd) or value["project_identity"] != origin._identity(cwd):
            raise ValueError("TASK_PROJECT_CONFLICT")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def add_commands(sub):
    for command in ("task-scope-origins", "task-scope-recover-source", "task-scope-show", "task-scope-select",
                    "task-scope-complete", "task-scope-preview"):
        item = sub.add_parser(command)
        item.add_argument("--session-id", required=True)
        item.add_argument("--repo-path", required=True)
        if command == "task-scope-recover-source":
            item.add_argument("--transcript-path", help="Optional cross-check of the host-observed path; cannot register a source.")
        if command == "task-scope-origins":
            item.add_argument("--before-byte", type=int)
        if command == "task-scope-select":
            item.add_argument("--task-id", required=True)
            item.add_argument("--origin-ref", required=True)
            item.add_argument("--relation", choices=("independent", "continue", "resume"), required=True)
            item.add_argument("--task-scope")
        if command in {"task-scope-complete", "task-scope-preview"}:
            item.add_argument("--task-scope", required=True)
        if command == "task-scope-preview":
            item.add_argument("--agent-type", required=True)
            item.add_argument("--task-name", required=True)
            item.add_argument("--message-file", required=True)
            item.add_argument("--model-profile")
        item.set_defaults(func=run)
