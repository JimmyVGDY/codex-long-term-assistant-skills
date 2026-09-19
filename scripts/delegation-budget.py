#!/usr/bin/env python3
"""中文：DelegationBudget V3 命令行与显式 V2 兼容入口。

English: DelegationBudget V3 CLI with explicit V2 compatibility.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.delegation_budget import (  # noqa: E402
    BUDGET_CLASSES, CONTEXT_SIZES, DIFFICULTIES, PROFILE_WEIGHTS, REASONS,
    RISK_DOMAINS, ROLES, DelegationBudgetError, close_budget, initialize_budget,
    mark_completed, mark_started, read_budget, record_decision, release_not_started,
    reserve_budget,
)
from cp_runtime.dispatch_policy import CURRENT_POLICY_ID, LEGACY_POLICY_ID, POLICY_FILES, DispatchPolicyError, profile_weights  # noqa: E402
from cp_runtime.dispatch_context import build_root_binding, prepare_review_selection, read_request_json, verify_root_binding  # noqa: E402
from cp_runtime.common import RuntimeContractError  # noqa: E402


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def read_input(filename: str) -> dict:
    return read_request_json(Path(filename))


def main() -> int:
    parser = argparse.ArgumentParser(description="维护 DelegationBudget V3 根任务预算账本；旧 V2 需显式选择")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--ledger", required=True); init.add_argument("--budget-id", required=True)
    init.add_argument("--task-id", required=True); init.add_argument("--project-id", required=True)
    init.add_argument("--repo-fingerprint", required=True)
    init.add_argument("--budget-class", choices=sorted(BUDGET_CLASSES), required=True)
    init.add_argument("--default-dispatch-profile", choices=list(PROFILE_WEIGHTS), default="luna-low")
    init.add_argument("--policy-id", choices=list(POLICY_FILES), default=CURRENT_POLICY_ID)
    init.add_argument("--review-extension", action="store_true")
    init.add_argument("--root-envelope", default=os.environ.get("CP_DELEGATION_ENVELOPE_PATH", ""))
    init.add_argument("--host-session-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    decide = sub.add_parser("decide")
    decide.add_argument("--ledger", required=True); decide.add_argument("--dispatch-key", required=True)
    decide.add_argument("--decision", choices=["INLINE", "DELEGATE"], required=True)
    decide.add_argument("--role", choices=sorted(ROLES), required=True)
    decide.add_argument("--approved-profile", choices=list(profile_weights()), default="")
    decide.add_argument("--selection-input", default="")
    decide.add_argument("--review-assignment", default="")
    decide.add_argument("--transition-input", default="")
    decide.add_argument("--root-envelope", default=os.environ.get("CP_DELEGATION_ENVELOPE_PATH", ""))
    decide.add_argument("--host-session-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    decide.add_argument("--reason-code", choices=sorted(REASONS), required=True)
    decide.add_argument("--responsibility", default="general")
    decide.add_argument("--difficulty", choices=sorted(DIFFICULTIES), default="UNKNOWN")
    decide.add_argument("--risk-domain", choices=sorted(RISK_DOMAINS), default="UNKNOWN")
    decide.add_argument("--context-size", choices=sorted(CONTEXT_SIZES), default="UNKNOWN")
    decide.add_argument("--parent-reservation-id", default="")
    decide.add_argument("--prior-profile", choices=[""] + list(PROFILE_WEIGHTS), default="")
    decide.add_argument("--prior-result-ref", default="")
    reserve = sub.add_parser("reserve")
    reserve.add_argument("--ledger", required=True); reserve.add_argument("--dispatch-key", required=True)
    reserve.add_argument("--host-dispatch-id", required=True)
    reserve.add_argument("--approved-profile", choices=[""] + list(profile_weights()), default="")
    reserve.add_argument("--approval-basis", choices=["", "policy-default", "explicit-request"], default="")
    reserve.add_argument("--role", choices=[""] + sorted(ROLES), default="")
    start = sub.add_parser("start")
    start.add_argument("--ledger", required=True); start.add_argument("--reservation-id", required=True)
    start.add_argument("--agent-id", required=True)
    complete = sub.add_parser("complete")
    complete.add_argument("--ledger", required=True); complete.add_argument("--reservation-id", required=True)
    complete.add_argument("--outcome", default="UNKNOWN")
    release = sub.add_parser("release-not-started")
    release.add_argument("--ledger", required=True); release.add_argument("--reservation-id", required=True)
    release.add_argument("--proof-ref", required=True)
    close = sub.add_parser("close")
    close.add_argument("--ledger", required=True); close.add_argument("--conclusion", required=True)
    status = sub.add_parser("status"); status.add_argument("--ledger", required=True)
    for command in (reserve, start, complete, release, close):
        command.add_argument("--root-envelope", default=os.environ.get("CP_DELEGATION_ENVELOPE_PATH", ""))
        command.add_argument("--host-session-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    args = parser.parse_args()
    ledger = Path(args.ledger).expanduser().resolve()
    try:
        if args.command not in {"init", "decide", "status"}:
            state = read_budget(ledger)
            if state["schema_version"] == "3.0":
                if not args.root_envelope:
                    raise DelegationBudgetError("V3 写入必须绑定根任务信封")
                verify_root_binding(state["root_binding"], state["identity"], envelope_path=Path(args.root_envelope),
                                    cwd=os.getcwd(), host_session_id=args.host_session_id)
        if args.command == "init":
            binding = None
            if args.policy_id != LEGACY_POLICY_ID:
                if not args.root_envelope:
                    raise DelegationBudgetError("V3 初始化必须指定 --root-envelope")
                identity, binding = build_root_binding(Path(args.root_envelope), args.host_session_id)
                if identity != {"task_id": args.task_id, "project_id": args.project_id,
                                "repo_fingerprint": args.repo_fingerprint}:
                    raise DelegationBudgetError("初始化身份与任务信封不一致")
            result = initialize_budget(ledger, budget_id=args.budget_id, task_id=args.task_id,
                                       project_id=args.project_id, repo_fingerprint=args.repo_fingerprint,
                                       budget_class=args.budget_class, default_dispatch_profile=args.default_dispatch_profile,
                                       policy_id=args.policy_id, review_extension=args.review_extension, root_binding=binding)
        elif args.command == "decide":
            state = read_budget(ledger)
            if state["schema_version"] == "3.0":
                if not args.root_envelope:
                    raise DelegationBudgetError("V3 决策必须绑定根任务信封")
                verify_root_binding(state["root_binding"], state["identity"], envelope_path=Path(args.root_envelope),
                                    cwd=os.getcwd(), host_session_id=args.host_session_id)
            selection, assignment, transition = {}, {}, {}
            approved_profile = args.approved_profile
            if state["schema_version"] == "3.0" and args.role == "reviewer" and args.decision == "DELEGATE":
                if not args.selection_input or not args.review_assignment or not args.root_envelope:
                    raise DelegationBudgetError("V3 复审必须提供评分输入、派发绑定和根任务信封")
                selection, assignment = prepare_review_selection(
                    state, read_input(args.selection_input), read_input(args.review_assignment),
                    envelope_path=Path(args.root_envelope), cwd=os.getcwd(), host_session_id=args.host_session_id)
                if approved_profile and approved_profile != selection["approved_profile"]:
                    raise DelegationBudgetError("显式档位与 Luna 起算的评分结果不一致")
                approved_profile = selection["approved_profile"]
                transition = read_input(args.transition_input) if args.transition_input else {}
            elif args.selection_input or args.review_assignment or args.transition_input:
                raise DelegationBudgetError("当前角色或旧策略不接受 V3 复审参数")
            if not approved_profile:
                approved_profile = "luna-low" if args.decision == "INLINE" else ""
            if not approved_profile:
                raise DelegationBudgetError("普通角色或旧策略必须提供 approved-profile")
            result = record_decision(ledger, dispatch_key=args.dispatch_key, decision=args.decision,
                                     role=args.role, approved_profile=approved_profile,
                                     reason_code=args.reason_code, responsibility=args.responsibility,
                                     difficulty=args.difficulty, risk_domain=args.risk_domain,
                                     context_size=args.context_size, parent_reservation_id=args.parent_reservation_id,
                                     prior_profile=args.prior_profile, prior_result_ref=args.prior_result_ref,
                                     selection_scorecard=selection, review_assignment=assignment, transition=transition)
        elif args.command == "reserve":
            result = reserve_budget(ledger, dispatch_key=args.dispatch_key, host_dispatch_id=args.host_dispatch_id,
                                    approved_profile=args.approved_profile, approval_basis=args.approval_basis,
                                    role=args.role)
        elif args.command == "start":
            result = mark_started(ledger, reservation_id=args.reservation_id, agent_id=args.agent_id)
        elif args.command == "complete":
            result = mark_completed(ledger, reservation_id=args.reservation_id, outcome=args.outcome)
        elif args.command == "release-not-started":
            result = release_not_started(ledger, reservation_id=args.reservation_id, proof_ref=args.proof_ref)
        elif args.command == "close":
            result = close_budget(ledger, conclusion=args.conclusion)
        else:
            result = read_budget(ledger)
        emit(result)
        return 0
    except (DelegationBudgetError, DispatchPolicyError, RuntimeContractError, OSError, TimeoutError, ValueError) as exc:
        print("[FAIL] " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
