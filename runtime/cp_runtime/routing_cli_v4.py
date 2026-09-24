#!/usr/bin/env python3
"""中文：桌面插件的 V4 根预算与审查管理入口。

English: Internal Desktop plugin tooling, not a standalone client support surface.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from cp_runtime import budget_v4, review_v4
from cp_runtime.common import atomic_write_json
from cp_runtime.routing_contract import RoutingError, exact, policy, policy_digest, read_document, ref
from cp_runtime.routing_context_v4 import build_root_binding, loader, verify_root
from cp_runtime import routing_controls_v4 as controls


def emit(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Desktop V4 routing controls")
    sub = parser.add_subparsers(dest="command", required=True)
    controls.add_commands(sub)
    sub.add_parser("catalog")
    initialize = sub.add_parser("init")
    initialize.add_argument("--ledger", required=True)
    initialize.add_argument("--config", required=True)
    initialize.add_argument("--root-envelope", required=True)
    initialize.add_argument("--host-session-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--ledger", required=True)
    prepare.add_argument("--request", required=True)
    prepare.add_argument("--body-file", required=True)
    prepare.add_argument("--dispatch-key", required=True)
    prepare.add_argument("--review-dir", default="")
    prepare.add_argument("--transition", default="")
    prepare.add_argument("--depth", type=int, default=1)
    prepare.add_argument("--wire", choices=["named", "native"], default="named")
    prepare.add_argument("--host-session-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    status = sub.add_parser("status")
    status.add_argument("--ledger", required=True)
    for name in ("bind-desktop", "retire-desktop"):
        command = sub.add_parser(name)
        command.add_argument("--host-session-id", default=os.environ.get("CODEX_THREAD_ID", ""))
        if name == "bind-desktop":
            command.add_argument("--ledger", required=True)
    review_init = sub.add_parser("review-init")
    review_init.add_argument("--ledger", required=True)
    review_init.add_argument("--review-dir", required=True)
    review_init.add_argument("--boundary-id", required=True)
    for name in ("result-template", "result", "review-status", "review-close"):
        command = sub.add_parser(name)
        command.add_argument("--review-dir", required=True)
        if name == "result-template":
            command.add_argument("--permit-id", required=True); command.add_argument("--output", required=True)
        if name == "result":
            command.add_argument("--result-file", required=True); command.add_argument("--response-ref", required=True)
        if name == "review-close":
            command.add_argument("--conclusion", choices=["PASS", "PARTIAL", "FAILED", "CANCELLED"], required=True)
    close = sub.add_parser("close")
    close.add_argument("--ledger", required=True)
    close.add_argument("--outcome", required=True)
    close.add_argument("--evidence-ref", required=True)
    close.add_argument("--host-session-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    args = parser.parse_args()
    if args.command in controls.COMMANDS:
        emit(controls.run(args))
    elif args.command == "catalog":
        emit({"policy": policy(), "policy_digest": policy_digest()})
    elif args.command == "init":
        config, _ = read_document(Path(args.config))
        exact(config, {"budget_id", "sources", "execution_mode", "capacity", "role_capacity",
                       "phase_capacity", "phase_plan", "max_parallel", "max_depth"}, "V4_INIT_CONFIG_FIELDS")
        declared, binding = build_root_binding(Path(args.root_envelope), args.host_session_id)
        if Path(config["sources"]["root_envelope"]).resolve() != Path(args.root_envelope).resolve():
            raise RoutingError("V4_INIT_ENVELOPE_SOURCE_MISMATCH")
        result = budget_v4.initialize(
            Path(args.ledger), declared_identity={**declared, "budget_id": config["budget_id"]},
            root_binding=binding, **{key: config[key] for key in config if key != "budget_id"})
        emit({"schema_version": "routing-control/1", "status": "INITIALIZED",
              "identity": result["identity"], "policy_id": result["policy_id"]})
    elif args.command in {"bind-desktop", "retire-desktop"}:
        from cp_runtime.routing_registry_v4 import bind, retire
        emit(bind(Path(args.ledger), cwd=os.getcwd(), host_session_id=args.host_session_id)
             if args.command == "bind-desktop" else
             retire(cwd=os.getcwd(), host_session_id=args.host_session_id))
    elif args.command == "prepare":
        request, _ = read_document(Path(args.request))
        from cp_runtime.routing_evaluation_v4 import file_reference
        if file_reference(Path(args.body_file), prompt=True) != "sha256:" + request["message_sha256"]:
            raise RoutingError("V4_BODY_FILE_DIGEST_MISMATCH")
        state = budget_v4.read_budget(Path(args.ledger))
        verify_root(state, cwd=os.getcwd(), host_session_id=args.host_session_id)
        context_loader = loader(cwd=os.getcwd(), host_session_id=args.host_session_id)
        transition = read_document(Path(args.transition))[0] if args.transition else None
        if args.review_dir:
            review_state = review_v4.read_state(Path(args.review_dir))
            if Path(review_state["ledger_path"]).resolve() != Path(args.ledger).resolve():
                raise RoutingError("V4_REVIEW_LEDGER_MISMATCH")
            result = review_v4.prepare(Path(args.review_dir), request, dispatch_key=args.dispatch_key,
                                      depth=args.depth, snapshot_loader=context_loader, transition=transition)
        else:
            if state["execution_mode"] == "PRODUCTION":
                raise RoutingError("V4_PRODUCTION_REVIEW_OWNER_REQUIRED")
            result = budget_v4.prepare(Path(args.ledger), request, dispatch_key=args.dispatch_key,
                                      depth=args.depth, snapshot_loader=context_loader, transition=transition)
        if result["status"] in budget_v4.SELECTED:
            params = result["request_parameters"]
            if args.wire == "named":
                params.update(task_name=args.dispatch_key, fork_turns="none")
                result["native_message_prefix"] = ""
            else:
                params.update(fork_context=False)
            result["enforcement"] = "prepared-not-reserved"
        emit(result)
    elif args.command == "status":
        state = budget_v4.read_budget(Path(args.ledger))
        emit({"schema_version": state["schema_version"], "identity": state["identity"],
              "policy_id": state["policy_id"], "closed": state["closed"], "outcome": state["outcome"],
              "budget": budget_v4.snapshot_budget(state), "phase_plan": state["phase_plan"],
              "permit_count": len(state["permits"]), "attempt_count": len(state["reservations"])})
    elif args.command == "review-init":
        emit(review_v4.initialize(Path(args.review_dir), ledger_path=Path(args.ledger), boundary_id=args.boundary_id))
    elif args.command == "result-template":
        value = review_v4.result_template(Path(args.review_dir), args.permit_id)
        atomic_write_json(Path(args.output), value)
        emit({"schema_version": 6, "result_id": value["result_id"], "output": args.output})
    elif args.command == "result":
        emit(review_v4.record_result(Path(args.review_dir), Path(args.result_file), response_ref=args.response_ref))
    elif args.command == "review-status":
        emit(review_v4.reconcile(Path(args.review_dir)))
    elif args.command == "review-close":
        emit(review_v4.close(Path(args.review_dir), conclusion=args.conclusion))
    else:
        state = budget_v4.read_budget(Path(args.ledger))
        verify_root(state, cwd=os.getcwd(), host_session_id=args.host_session_id)
        emit(budget_v4.close(Path(args.ledger), outcome=args.outcome, evidence_ref=args.evidence_ref))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, TimeoutError, KeyError, TypeError) as exc:
        emit({"status": "BLOCKED", "reason": str(exc)})
        raise SystemExit(2)
