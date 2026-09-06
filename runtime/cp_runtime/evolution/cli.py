"""中文：V6 受控演进命令行入口。

English: V6 controlled-evolution command-line entry point.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .contracts import DecisionType, ExecutionAuthorization, ProposalStatus, to_primitive
from .registry import ProposalRegistry
from .service import ControlledEvolutionService, load_policy
from .storage import resolve_project_dir, safe_child
from .task_feedback import finalize_feedback, run_validation
from .incremental import automation_tick, configure_automation, run_incremental


def _json_dump(value: Any) -> str:
    return json.dumps(to_primitive(value), ensure_ascii=False, sort_keys=True, indent=2)


def _service(args: argparse.Namespace) -> ControlledEvolutionService:
    policy = load_policy(Path(args.policy).expanduser()) if getattr(args, "policy", None) else load_policy()
    return ControlledEvolutionService(
        context_root=Path(args.context_root).expanduser(),
        project_id=args.project_id,
        policy=policy,
        create_project_dir=bool(getattr(args, "create_project_context", False)),
    )


def _registry(args: argparse.Namespace) -> ProposalRegistry:
    project_dir = resolve_project_dir(Path(args.context_root).expanduser(), args.project_id, create=False)
    if not project_dir.exists():
        raise RuntimeError("项目上下文目录不存在: %s" % project_dir)
    evolution_root = safe_child(project_dir, "evolution")
    return ProposalRegistry(evolution_root, args.project_id)


def _cmd_observe(args: argparse.Namespace) -> Mapping[str, Any]:
    service = _service(args)
    snapshot = service.observe(explicit_sources=args.source or None)
    assessments = service.analyze(snapshot)
    proposals = service.propose(snapshot, assessments)
    return {
        "mode": "OBSERVE_ONLY",
        "project_id": args.project_id,
        "snapshot": to_primitive(snapshot),
        "assessment_count": len(assessments),
        "proposal_candidate_count": len(proposals),
        "execution_authorization": ExecutionAuthorization.NONE.value,
        "automatic_execution": False,
    }


def _cmd_run(args: argparse.Namespace) -> Mapping[str, Any]:
    return _service(args).run(explicit_sources=args.source or None, dry_run=args.dry_run)


def _view_payload(view: Any) -> Mapping[str, Any]:
    return {
        "proposal": to_primitive(view.proposal),
        "current_status": view.current_status.value,
        "latest_decision": None if view.latest_decision is None else to_primitive(view.latest_decision),
        "latest_benefit": to_primitive(view.latest_benefit),
        "final_outcome": view.final_outcome,
        "execution_authorization": ExecutionAuthorization.NONE.value,
    }


def _cmd_list(args: argparse.Namespace) -> Mapping[str, Any]:
    registry = _registry(args)
    views = registry.list()
    if args.status:
        expected = ProposalStatus(args.status)
        views = [view for view in views if view.current_status is expected]
    return {
        "project_id": args.project_id,
        "count": len(views),
        "items": [_view_payload(view) for view in views],
        "execution_authorization": ExecutionAuthorization.NONE.value,
    }


def _cmd_show(args: argparse.Namespace) -> Mapping[str, Any]:
    return _view_payload(_registry(args).get(args.proposal_id))


def _cmd_decide(args: argparse.Namespace) -> Mapping[str, Any]:
    mapping = {
        "accept": DecisionType.ACCEPT,
        "reject": DecisionType.REJECT,
        "defer": DecisionType.DEFER,
    }
    view = _registry(args).decide(
        proposal_id=args.proposal_id,
        decision=mapping[args.decision],
        actor=args.actor,
        rationale=args.rationale,
    )
    return {
        "result": _view_payload(view),
        "notice": "该决策不授予执行权限；实施仍需新的 Task Envelope、基线冻结和显式 Approval。",
        "execution_authorization": ExecutionAuthorization.NONE.value,
    }



def _cmd_link_implementation(args: argparse.Namespace) -> Mapping[str, Any]:
    view = _registry(args).link_implementation(args.proposal_id, args.actor, args.task_id, args.git_baseline)
    return {"result": _view_payload(view), "execution_authorization": ExecutionAuthorization.NONE.value}


def _cmd_record_validation(args: argparse.Namespace) -> Mapping[str, Any]:
    view = _registry(args).record_validation(args.proposal_id, args.actor, args.commit, args.evidence or [])
    return {"result": _view_payload(view), "execution_authorization": ExecutionAuthorization.NONE.value}


def _cmd_close(args: argparse.Namespace) -> Mapping[str, Any]:
    view = _registry(args).close(args.proposal_id, args.actor, args.final_outcome, args.evidence)
    return {"result": _view_payload(view), "execution_authorization": ExecutionAuthorization.NONE.value}


def _cmd_benefit(args: argparse.Namespace) -> Mapping[str, Any]:
    view = _registry(args).observe_benefit(args.proposal_id, args.actor,
                                          {"path": args.before, "content_hash": args.before_hash},
                                          {"path": args.after, "content_hash": args.after_hash})
    return _view_payload(view)

def _cmd_validate(args: argparse.Namespace) -> Mapping[str, Any]:
    return _registry(args).validate()


def _cmd_task_validation(args: argparse.Namespace) -> Mapping[str, Any]:
    project = resolve_project_dir(Path(args.context_root), args.project_id)
    command = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    return run_validation(project, args.session_id, args.turn_id, args.task_id, command, args.timeout)


def _cmd_task_feedback(args: argparse.Namespace) -> Mapping[str, Any]:
    project = resolve_project_dir(Path(args.context_root), args.project_id)
    return finalize_feedback(project, args.session_id, args.turn_id, args.task_id, actor=args.actor,
                             outcome=args.outcome, failure_category=args.failure_category,
                             routing_deviation=args.routing_deviation, repair_rounds=args.repair_rounds,
                             evidence_paths=args.evidence, root_cause_id=args.root_cause_id,
                             root_cause_confirmed=args.root_cause_confirmed)


def _cmd_health(args: argparse.Namespace) -> Mapping[str, Any]:
    return _service(args).health(args.source or None, max_age_days=args.max_age_days)


def _cmd_snapshot(args: argparse.Namespace) -> Mapping[str, Any]:
    from .snapshots import persist_snapshot
    service = _service(args)
    snapshot = service.observe(window_start=args.window_start, window_end=args.window_end)
    return {"reference": persist_snapshot(service.project_dir, snapshot), "snapshot": to_primitive(snapshot)}


def _cmd_incremental(args: argparse.Namespace) -> Mapping[str, Any]:
    return run_incremental(_service(args), milestone=args.milestone, minimum_new_tasks=args.minimum_new_tasks,
                           cooldown_seconds=args.cooldown_seconds, max_age_days=args.max_age_days)


def _cmd_automation(args: argparse.Namespace) -> Mapping[str, Any]:
    project = resolve_project_dir(Path(args.context_root), args.project_id)
    if args.action == "tick":
        return automation_tick(project)
    return configure_automation(project, enabled=args.action == "enable", minimum_new_tasks=args.minimum_new_tasks,
                                cooldown_seconds=args.cooldown_seconds, max_age_days=args.max_age_days)


def _cmd_calibration_source(args: argparse.Namespace) -> Mapping[str, Any]:
    from .calibration_sources import register_source
    return register_source(resolve_project_dir(Path(args.context_root), args.project_id), args.ledger, args.samples)


def _cmd_calibration_replay(args: argparse.Namespace) -> Mapping[str, Any]:
    from .calibration_sources import project_calibration
    return project_calibration(resolve_project_dir(Path(args.context_root), args.project_id),
                               minimum_samples=args.minimum_samples, minimum_tasks=args.minimum_tasks)[1]


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-id", required=True, help="已完成 Onboarding 的项目 ID")
    parser.add_argument(
        "--context-root",
        default=str(Path.home() / ".codex" / "project-context"),
        help="仓库外项目上下文根目录，默认 ~/.codex/project-context",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-evolution",
        description="Codex 跨项目长期技术助手 V6 确定性自观察与受控演进工具。不会自动修改任何规则或代码。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Read-only identity, integrity, coverage and freshness checks")
    _add_common(health)
    health.add_argument("--source", action="append", default=[])
    health.add_argument("--policy")
    health.add_argument("--max-age-days", type=int, default=30)
    health.set_defaults(func=_cmd_health)

    snapshot = sub.add_parser("snapshot", help="Capture immutable evidence for a half-open observation window")
    _add_common(snapshot)
    snapshot.add_argument("--policy")
    snapshot.add_argument("--window-start", required=True)
    snapshot.add_argument("--window-end", required=True)
    snapshot.set_defaults(func=_cmd_snapshot)

    incremental = sub.add_parser("incremental-run", help="Analyze verified new inputs with an idempotent receipt")
    automation = sub.add_parser("automation", help="Explicitly enable, disable or tick project automation")
    for item in (incremental, automation):
        _add_common(item)
        item.add_argument("--minimum-new-tasks", type=int, default=3)
        item.add_argument("--cooldown-seconds", type=int, default=3600)
        item.add_argument("--max-age-days", type=int, default=30)
    incremental.add_argument("--policy")
    incremental.add_argument("--milestone", default="")
    incremental.set_defaults(func=_cmd_incremental)
    automation.add_argument("action", choices=("enable", "disable", "tick"))
    automation.set_defaults(func=_cmd_automation)

    calibration_source = sub.add_parser("calibration-source", help="Bind relative sample and ledger paths to this project")
    _add_common(calibration_source)
    calibration_source.add_argument("--ledger", required=True)
    calibration_source.add_argument("--samples", required=True)
    calibration_source.set_defaults(func=_cmd_calibration_source)
    calibration_replay = sub.add_parser("calibration-replay", help="Replay verified samples across same-project task ledgers")
    _add_common(calibration_replay)
    calibration_replay.add_argument("--minimum-samples", type=int, default=3)
    calibration_replay.add_argument("--minimum-tasks", type=int, default=3)
    calibration_replay.set_defaults(func=_cmd_calibration_replay)

    task_validation = sub.add_parser("validate-task", help="Run bounded validation and retain structured results only")
    task_feedback = sub.add_parser("finalize-task", help="Finalize evidence-bound task feedback as the parent coordinator")
    for item in (task_validation, task_feedback):
        _add_common(item)
        item.add_argument("--session-id", required=True)
        item.add_argument("--turn-id", required=True)
        item.add_argument("--task-id", required=True)
    task_validation.add_argument("--timeout", type=int, default=600)
    task_validation.add_argument("argv", nargs=argparse.REMAINDER)
    task_validation.set_defaults(func=_cmd_task_validation)
    task_feedback.add_argument("--actor", required=True)
    task_feedback.add_argument("--outcome", required=True, choices=("PASS", "FAILED", "BLOCKED", "CANCELLED", "PARTIAL", "UNKNOWN"))
    task_feedback.add_argument("--failure-category", required=True, choices=("NONE", "INPUT_CONTRACT", "ROUTING", "IMPLEMENTATION", "VALIDATION", "REVIEW", "ENVIRONMENT", "UNKNOWN"))
    task_feedback.add_argument("--routing-deviation", required=True, choices=("MATCHED", "MISSED", "UNNECESSARY", "WRONG_DOMAIN", "UNKNOWN"))
    task_feedback.add_argument("--repair-rounds", required=True, type=int)
    task_feedback.add_argument("--evidence", required=True, action="append")
    task_feedback.add_argument("--root-cause-id", default="")
    task_feedback.add_argument("--root-cause-confirmed", action="store_true")
    task_feedback.set_defaults(func=_cmd_task_feedback)

    observe = sub.add_parser("observe", help="只生成内存观察快照，不写注册表")
    _add_common(observe)
    observe.add_argument("--source", action="append", default=[], help="项目上下文内的相对 JSONL 路径，可重复")
    observe.add_argument("--policy", help="自定义 EvolutionPolicy JSON")
    observe.add_argument("--create-project-context", action="store_true", help="仅创建仓库外项目上下文目录")
    observe.set_defaults(func=_cmd_observe)

    run = sub.add_parser("run", help="执行 Observation → Analysis → Proposal")
    _add_common(run)
    run.add_argument("--source", action="append", default=[], help="项目上下文内的相对 JSONL 路径，可重复")
    run.add_argument("--policy", help="自定义 EvolutionPolicy JSON")
    run.add_argument("--dry-run", action="store_true", help="只输出候选，不写快照和提案注册表")
    run.add_argument("--create-project-context", action="store_true", help="仅创建仓库外项目上下文目录")
    run.set_defaults(func=_cmd_run)

    list_parser = sub.add_parser("list", help="列出项目优化提案")
    _add_common(list_parser)
    list_parser.add_argument("--status", choices=[status.value for status in ProposalStatus])
    list_parser.set_defaults(func=_cmd_list)

    show = sub.add_parser("show", help="查看单个提案")
    _add_common(show)
    show.add_argument("--proposal-id", required=True)
    show.set_defaults(func=_cmd_show)

    decide = sub.add_parser("decide", help="记录人工接受、拒绝或延期决定")
    _add_common(decide)
    decide.add_argument("--proposal-id", required=True)
    decide.add_argument("--decision", required=True, choices=("accept", "reject", "defer"))
    decide.add_argument("--actor", required=True, help="明确的人工决策者或审批主体")
    decide.add_argument("--rationale", required=True, help="至少 10 个字符的决策理由")
    decide.set_defaults(func=_cmd_decide)

    link_impl = sub.add_parser("link-implementation", help="人工 ACCEPT 后绑定新的实施 Task 与 Git Baseline")
    _add_common(link_impl)
    link_impl.add_argument("--proposal-id", required=True)
    link_impl.add_argument("--actor", required=True)
    link_impl.add_argument("--task-id", required=True)
    link_impl.add_argument("--git-baseline", required=True)
    link_impl.set_defaults(func=_cmd_link_implementation)

    validation_event = sub.add_parser("record-validation", help="记录实施 Commit 与验证 Evidence")
    _add_common(validation_event)
    validation_event.add_argument("--proposal-id", required=True)
    validation_event.add_argument("--actor", required=True)
    validation_event.add_argument("--commit", required=True)
    validation_event.add_argument("--evidence", action="append", default=[], required=True)
    validation_event.set_defaults(func=_cmd_record_validation)

    close_event = sub.add_parser("close", help="验证完成后关闭提案")
    _add_common(close_event)
    close_event.add_argument("--proposal-id", required=True)
    close_event.add_argument("--actor", required=True)
    close_event.add_argument("--final-outcome", choices=("PASS","FAILED","ROLLED_BACK","CANCELLED"), required=True)
    close_event.add_argument("--evidence", action="append", default=[])
    close_event.set_defaults(func=_cmd_close)

    benefit = sub.add_parser("observe-benefit", help="Verify implementation evidence and measure the registered hypothesis")
    _add_common(benefit)
    for name in ("proposal-id", "actor", "before", "before-hash", "after", "after-hash"):
        benefit.add_argument("--" + name, required=True)
    benefit.set_defaults(func=_cmd_benefit)

    validate = sub.add_parser("validate", help="验证提案、决策与生命周期哈希链")
    _add_common(validate)
    validate.set_defaults(func=_cmd_validate)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except Exception as exc:
        error = {
            "ok": False,
            "error_type": exc.__class__.__name__,
            "message": str(exc),
            "execution_authorization": ExecutionAuthorization.NONE.value,
            "automatic_execution": False,
        }
        print(_json_dump(error), file=sys.stderr)
        return 2
    print(_json_dump({"ok": True, "result": result}))
    if args.command == "validate-task" and (result["exit_code"] != 0 or not result["workspace_unchanged"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
