#!/usr/bin/env python3
"""中文：DelegationBudget V1 命令行适配器。

English: DelegationBudget V1 command-line adapter.
"""
from __future__ import annotations

import argparse
import json
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


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="维护 DelegationBudget V1 根任务预算账本")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--ledger", required=True); init.add_argument("--budget-id", required=True)
    init.add_argument("--task-id", required=True); init.add_argument("--project-id", required=True)
    init.add_argument("--repo-fingerprint", required=True)
    init.add_argument("--budget-class", choices=sorted(BUDGET_CLASSES), required=True)
    init.add_argument("--default-model-profile", choices=list(PROFILE_WEIGHTS), required=True)
    decide = sub.add_parser("decide")
    decide.add_argument("--ledger", required=True); decide.add_argument("--dispatch-key", required=True)
    decide.add_argument("--decision", choices=["INLINE", "DELEGATE"], required=True)
    decide.add_argument("--role", choices=sorted(ROLES), required=True)
    decide.add_argument("--requested-profile", choices=list(PROFILE_WEIGHTS), required=True)
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
    reserve.add_argument("--requested-profile", choices=[""] + list(PROFILE_WEIGHTS), default="")
    reserve.add_argument("--request-basis", choices=["", "policy-default", "explicit-request"], default="")
    reserve.add_argument("--role", choices=[""] + sorted(ROLES), default="")
    start = sub.add_parser("start")
    start.add_argument("--ledger", required=True); start.add_argument("--reservation-id", required=True)
    start.add_argument("--agent-id", required=True); start.add_argument("--actual-profile", choices=[""] + list(PROFILE_WEIGHTS), default="")
    start.add_argument("--runtime-evidence", choices=["unavailable", "host-attested-hook-payload"], default="unavailable")
    complete = sub.add_parser("complete")
    complete.add_argument("--ledger", required=True); complete.add_argument("--reservation-id", required=True)
    complete.add_argument("--outcome", default="UNKNOWN")
    release = sub.add_parser("release-not-started")
    release.add_argument("--ledger", required=True); release.add_argument("--reservation-id", required=True)
    release.add_argument("--proof-ref", required=True)
    close = sub.add_parser("close")
    close.add_argument("--ledger", required=True); close.add_argument("--conclusion", required=True)
    status = sub.add_parser("status"); status.add_argument("--ledger", required=True)
    args = parser.parse_args()
    ledger = Path(args.ledger).expanduser().resolve()
    try:
        if args.command == "init":
            result = initialize_budget(ledger, budget_id=args.budget_id, task_id=args.task_id,
                                       project_id=args.project_id, repo_fingerprint=args.repo_fingerprint,
                                       budget_class=args.budget_class, default_model_profile=args.default_model_profile)
        elif args.command == "decide":
            result = record_decision(ledger, dispatch_key=args.dispatch_key, decision=args.decision,
                                     role=args.role, requested_profile=args.requested_profile,
                                     reason_code=args.reason_code, responsibility=args.responsibility,
                                     difficulty=args.difficulty, risk_domain=args.risk_domain,
                                     context_size=args.context_size, parent_reservation_id=args.parent_reservation_id,
                                     prior_profile=args.prior_profile, prior_result_ref=args.prior_result_ref)
        elif args.command == "reserve":
            result = reserve_budget(ledger, dispatch_key=args.dispatch_key, host_dispatch_id=args.host_dispatch_id,
                                    requested_profile=args.requested_profile, request_basis=args.request_basis,
                                    role=args.role)
        elif args.command == "start":
            result = mark_started(ledger, reservation_id=args.reservation_id, agent_id=args.agent_id,
                                  actual_profile=args.actual_profile, runtime_evidence=args.runtime_evidence)
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
    except (DelegationBudgetError, OSError, TimeoutError) as exc:
        print("[FAIL] " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
