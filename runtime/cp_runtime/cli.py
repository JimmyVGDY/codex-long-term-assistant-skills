"""中文：V5.0 跨项目治理 Runtime 的命令行入口。

English: CLI for the V5.0 cross-project governance runtime.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .approval import check_approval, consume_approval, issue_approval
from .common import RuntimeContractError, repo_snapshot
from .evidence import check_evidence, record_evidence
from .feedback import record_feedback
from .finalization import build_finalization_report
from .memory import create_knowledge_candidate, create_projection_candidate, promote_projection
from .project import load_profile, load_state, onboard_project, refresh_project, validate_binding


def emit(value: Any) -> None:
    if hasattr(value, "__dict__"):
        value = value.__dict__
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def cmd_project_onboard(args: argparse.Namespace) -> None:
    binding = onboard_project(
        Path(args.repo_path), args.project_id, args.project_name,
        Path(args.context_dir) if args.context_dir else None,
        args.force, args.allow_inside_repo,
    )
    emit({
        "project_id": binding.project_id,
        "repo_path": str(binding.repo_path),
        "profile_path": str(binding.profile_path),
        "state_path": str(binding.state_path),
        "profile_sha256": binding.profile_sha256,
    })


def cmd_project_refresh(args: argparse.Namespace) -> None:
    binding = refresh_project(Path(args.profile), Path(args.state) if args.state else None)
    emit(binding.__dict__)


def cmd_project_show(args: argparse.Namespace) -> None:
    profile = load_profile(Path(args.profile))
    state_path = Path(args.state) if args.state else Path(args.profile).with_name("project-state.json")
    emit({"profile": profile, "state": load_state(state_path)})


def cmd_project_validate(args: argparse.Namespace) -> None:
    binding = validate_binding(
        Path(args.profile), Path(args.repo_path), args.project_id,
        Path(args.state) if args.state else None,
    )
    emit(binding.__dict__)


def cmd_approval_issue(args: argparse.Namespace) -> None:
    expires_at = args.expires_at
    if not expires_at:
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=args.ttl_minutes)).isoformat()
    emit(issue_approval(
        Path(args.output), args.approval_id, Path(args.profile), args.task_id,
        args.operation, args.environment, Path(args.repo_path), expires_at,
        args.approved_by, args.note, not args.reusable,
    ))


def _approval_result(args: argparse.Namespace, consume: bool) -> None:
    snapshot = repo_snapshot(Path(args.repo_path))
    project_id = args.project_id or str(load_profile(Path(args.profile))["project_id"])
    if consume:
        emit(consume_approval(
            Path(args.approval), project_id, args.task_id, args.operation,
            args.environment, snapshot["sha256"],
        ))
    else:
        emit(check_approval(
            Path(args.approval), project_id, args.task_id, args.operation,
            args.environment, snapshot["sha256"],
        ))


def cmd_evidence_record(args: argparse.Namespace) -> None:
    emit(record_evidence(
        Path(args.output), args.evidence_id, Path(args.profile), args.task_id,
        Path(args.repo_path), args.kind, args.subject, args.status,
        args.source, args.summary, args.scope_ref, args.confidence,
    ))


def cmd_evidence_check(args: argparse.Namespace) -> None:
    emit(check_evidence(
        Path(args.evidence), Path(args.repo_path) if args.repo_path else None,
        args.project_id, args.task_id,
    ))


def cmd_memory_project(args: argparse.Namespace) -> None:
    emit(create_projection_candidate(
        Path(args.output), Path(args.profile), args.task_id, args.projection_id,
        [Path(item) for item in args.source], args.fact, args.decision,
        args.risk, args.unknown, args.summary, args.allow_sensitive,
    ))


def cmd_memory_promote(args: argparse.Namespace) -> None:
    emit(promote_projection(Path(args.projection), Path(args.profile), args.reviewed_by))


def cmd_knowledge_candidate(args: argparse.Namespace) -> None:
    emit(create_knowledge_candidate(
        Path(args.output), Path(args.projection), Path(args.profile),
        args.knowledge_id, args.knowledge_type, args.applicability,
        args.limitation, args.summary,
    ))


def cmd_finalize(args: argparse.Namespace) -> None:
    report = build_finalization_report(
        Path(args.execution_state), Path(args.repo_path), args.claim,
        Path(args.output_json), Path(args.output_markdown) if args.output_markdown else None,
    )
    emit(report)
    if report["result"] != "PASS" and args.require_all:
        raise SystemExit(2)


def cmd_feedback(args: argparse.Namespace) -> None:
    payload: Dict[str, Any] = {
        "task_id": args.task_id,
        "project_id": args.project_id,
        "complexity": args.complexity,
        "recommended_model": args.recommended_model,
        "actual_model": args.actual_model,
        "recommended_reviewers": args.recommended_reviewers,
        "actual_reviewers": args.actual_reviewers,
        "blocking_findings": args.blocking_findings,
        "nonblocking_findings": args.nonblocking_findings,
        "repair_rounds": args.repair_rounds,
        "routing_deviation": args.routing_deviation,
        "quality_outcome": args.quality_outcome,
        "evidence_level": args.evidence_level,
    }
    emit(record_feedback(Path(args.output), payload))


def add_approval_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--approval", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--project-id")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--repo-path", required=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Codex 跨项目技术助手 V5.0 项目治理运行时")
    sub = parser.add_subparsers(dest="command", required=True)

    item = sub.add_parser("project-onboard")
    item.add_argument("--repo-path", required=True)
    item.add_argument("--project-id")
    item.add_argument("--project-name", default="")
    item.add_argument("--context-dir")
    item.add_argument("--force", action="store_true")
    item.add_argument("--allow-inside-repo", action="store_true")
    item.set_defaults(func=cmd_project_onboard)

    item = sub.add_parser("project-refresh")
    item.add_argument("--profile", required=True)
    item.add_argument("--state")
    item.set_defaults(func=cmd_project_refresh)

    item = sub.add_parser("project-show")
    item.add_argument("--profile", required=True)
    item.add_argument("--state")
    item.set_defaults(func=cmd_project_show)

    item = sub.add_parser("project-validate")
    item.add_argument("--profile", required=True)
    item.add_argument("--state")
    item.add_argument("--project-id")
    item.add_argument("--repo-path", required=True)
    item.set_defaults(func=cmd_project_validate)

    item = sub.add_parser("approval-issue")
    item.add_argument("--output", required=True)
    item.add_argument("--approval-id", required=True)
    item.add_argument("--profile", required=True)
    item.add_argument("--task-id", required=True)
    item.add_argument("--operation", action="append", required=True)
    item.add_argument("--environment", required=True)
    item.add_argument("--repo-path", required=True)
    item.add_argument("--expires-at")
    item.add_argument("--ttl-minutes", type=int, default=30)
    item.add_argument("--approved-by", default="explicit-user-approval")
    item.add_argument("--note", default="")
    item.add_argument("--reusable", action="store_true")
    item.set_defaults(func=cmd_approval_issue)

    item = sub.add_parser("approval-check")
    add_approval_common(item)
    item.set_defaults(func=lambda args: _approval_result(args, False))

    item = sub.add_parser("approval-consume")
    add_approval_common(item)
    item.set_defaults(func=lambda args: _approval_result(args, True))

    item = sub.add_parser("evidence-record")
    item.add_argument("--output", required=True)
    item.add_argument("--evidence-id", required=True)
    item.add_argument("--profile", required=True)
    item.add_argument("--task-id", required=True)
    item.add_argument("--repo-path", required=True)
    item.add_argument("--kind", required=True)
    item.add_argument("--subject", default="")
    item.add_argument("--status", required=True)
    item.add_argument("--source", default="")
    item.add_argument("--summary", default="")
    item.add_argument("--scope-ref", action="append", default=[])
    item.add_argument("--confidence", default="L2")
    item.set_defaults(func=cmd_evidence_record)

    item = sub.add_parser("evidence-check")
    item.add_argument("--evidence", required=True)
    item.add_argument("--repo-path")
    item.add_argument("--project-id")
    item.add_argument("--task-id")
    item.set_defaults(func=cmd_evidence_check)

    item = sub.add_parser("memory-project")
    item.add_argument("--output", required=True)
    item.add_argument("--profile", required=True)
    item.add_argument("--task-id", required=True)
    item.add_argument("--projection-id", required=True)
    item.add_argument("--source", action="append", default=[])
    item.add_argument("--fact", action="append", default=[])
    item.add_argument("--decision", action="append", default=[])
    item.add_argument("--risk", action="append", default=[])
    item.add_argument("--unknown", action="append", default=[])
    item.add_argument("--summary", default="")
    item.add_argument("--allow-sensitive", action="store_true")
    item.set_defaults(func=cmd_memory_project)

    item = sub.add_parser("memory-promote")
    item.add_argument("--projection", required=True)
    item.add_argument("--profile", required=True)
    item.add_argument("--reviewed-by", required=True)
    item.set_defaults(func=cmd_memory_promote)

    item = sub.add_parser("knowledge-candidate")
    item.add_argument("--output", required=True)
    item.add_argument("--projection", required=True)
    item.add_argument("--profile", required=True)
    item.add_argument("--knowledge-id", required=True)
    item.add_argument("--knowledge-type", required=True)
    item.add_argument("--applicability", action="append", default=[])
    item.add_argument("--limitation", action="append", default=[])
    item.add_argument("--summary", default="")
    item.set_defaults(func=cmd_knowledge_candidate)

    item = sub.add_parser("finalize")
    item.add_argument("--execution-state", required=True)
    item.add_argument("--repo-path", required=True)
    item.add_argument("--claim", action="append", default=[])
    item.add_argument("--output-json", required=True)
    item.add_argument("--output-markdown")
    item.add_argument("--require-all", action="store_true")
    item.set_defaults(func=cmd_finalize)

    item = sub.add_parser("feedback-record")
    item.add_argument("--output", required=True)
    item.add_argument("--task-id", required=True)
    item.add_argument("--project-id", required=True)
    item.add_argument("--complexity", default="L1")
    item.add_argument("--recommended-model", default="")
    item.add_argument("--actual-model", default="")
    item.add_argument("--recommended-reviewers", type=int, default=0)
    item.add_argument("--actual-reviewers", type=int, default=0)
    item.add_argument("--blocking-findings", type=int, default=0)
    item.add_argument("--nonblocking-findings", type=int, default=0)
    item.add_argument("--repair-rounds", type=int, default=0)
    item.add_argument("--routing-deviation", default="NONE")
    item.add_argument("--quality-outcome", default="unknown")
    item.add_argument("--evidence-level", default="unverified")
    item.set_defaults(func=cmd_feedback)

    args = parser.parse_args()
    try:
        args.func(args)
    except RuntimeContractError as exc:
        print("[FAIL] " + str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
