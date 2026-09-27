"""中文：桌面上下文内部管理入口。English: Internal Desktop context management; no standalone client support."""
import argparse
import json
import os
from pathlib import Path
from . import budget_v5 as budget, review_v5 as review
from .common import atomic_write_json
from .routing_context_contract import create_bundle, runtime, load_bundle
from .routing_context_v5 import build_root_binding, loader, verify_root
from .routing_contract import exact, fail, read_document
from .routing_registry_v5 import bind, retire

def main():
    parser = argparse.ArgumentParser(description="Opt-in Desktop authoritative review context")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--config", required=True)
    init.add_argument("--root-envelope", required=True)
    init.add_argument("--reader", required=True)
    init.add_argument("--python", required=True)
    for name in ("init", "bind-desktop", "retire-desktop", "status", "prepare", "close"):
        p = init if name == "init" else sub.add_parser(name)
        p.add_argument("--ledger", required=True)
        p.add_argument("--host-session-id", default=os.environ.get("CODEX_THREAD_ID", ""))
        if name == "prepare":
            p.add_argument("--request", required=True)
            p.add_argument("--dispatch-key", required=True)
            p.add_argument("--review-dir", required=True)
            p.add_argument("--transition")
        if name == "close":
            p.add_argument("--outcome", required=True)
            p.add_argument("--evidence-ref", required=True)
    p = sub.add_parser("bundle")
    p.add_argument("--manifest", required=True)
    p.add_argument("--output", required=True)
    p = sub.add_parser("review-init")
    p.add_argument("--ledger", required=True)
    p.add_argument("--review-dir", required=True)
    p.add_argument("--boundary-id", required=True)
    for name in ("result", "review-status", "review-close"):
        p = sub.add_parser(name)
        p.add_argument("--review-dir", required=True)
        if name == "result":
            p.add_argument("--permit-id", required=True)
            p.add_argument("--response", required=True)
        if name == "review-close":
            p.add_argument("--conclusion", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            config, _ = read_document(Path(args.config))
            exact(config, {"budget_id", "sources", "execution_mode", "capacity", "role_capacity",
                           "phase_capacity", "phase_plan", "max_parallel", "max_depth"}, "V5_INIT_FIELDS")
            if config["execution_mode"] != "EVALUATION" or config["max_depth"] != 1:
                fail("V5_EVALUATION_DEPTH_ONE_ONLY")
            if Path(config["sources"]["root_envelope"]).resolve() != Path(args.root_envelope).resolve():
                fail("V5_ENVELOPE_SOURCE_MISMATCH")
            identity, binding = build_root_binding(Path(args.root_envelope), args.host_session_id,
                                                   runtime(Path(args.reader), Path(args.python)))
            result = budget.initialize(Path(args.ledger), declared_identity={**identity, "budget_id": config["budget_id"]},
                root_binding=binding, **{k:v for k,v in config.items() if k != "budget_id"})
        elif args.command == "bundle":
            spec, _ = read_document(Path(args.manifest))
            exact(spec, {"business_prompt", "packet_sha256", "baseline_sha256", "artifacts"}, "V5_BUNDLE_INPUT")
            result = create_bundle(Path(args.output), repo=Path.cwd(), business_prompt=Path(spec["business_prompt"]),
                packet_sha256=spec["packet_sha256"], baseline_sha256=spec["baseline_sha256"],
                artifacts={k:Path(v) for k,v in spec["artifacts"].items()})
        elif args.command == "bind-desktop":
            result = bind(Path(args.ledger), cwd=os.getcwd(), host_session_id=args.host_session_id)
        elif args.command == "retire-desktop":
            state = budget.read_budget(Path(args.ledger))
            verify_root(state, cwd=os.getcwd(), host_session_id=args.host_session_id)
            result = retire(host_session_id=args.host_session_id)
        elif args.command == "status":
            state = budget.read_budget(Path(args.ledger))
            result = {"schema_version":"5.0", "closed":state["closed"], "outcome":state["outcome"],
                      "budget":budget.snapshot_budget(state), "attempts":len(state["reservations"]),
                      "deliveries":len(state["context_deliveries"]), "accepted_results":len(state["accepted_results"])}
        elif args.command == "prepare":
            request, _ = read_document(Path(args.request))
            state = budget.read_budget(Path(args.ledger))
            verify_root(state, cwd=os.getcwd(), host_session_id=args.host_session_id)
            owned = review.read_state(Path(args.review_dir))
            if Path(owned["ledger_path"]).resolve() != Path(args.ledger).resolve():
                fail("V5_REVIEW_LEDGER_MISMATCH")
            result = review.prepare(Path(args.review_dir), request, dispatch_key=args.dispatch_key, depth=1,
                snapshot_loader=loader(cwd=os.getcwd(), host_session_id=args.host_session_id),
                transition=read_document(Path(args.transition))[0] if args.transition else None)
            if result["status"] in budget.SELECTED:
                result["request_parameters"].update(task_name=args.dispatch_key, fork_turns="none",
                    message="Use the authoritative Desktop developer context for this bounded review.")
        elif args.command == "review-init":
            result = review.initialize(Path(args.review_dir), ledger_path=Path(args.ledger), boundary_id=args.boundary_id)
        elif args.command == "review-status":
            result = review.reconcile(Path(args.review_dir))
        elif args.command == "result":
            result = review.record_semantic(Path(args.review_dir), args.permit_id, Path(args.response))
        elif args.command == "review-close":
            result = review.close(Path(args.review_dir), conclusion=args.conclusion)
        else:
            state = budget.read_budget(Path(args.ledger))
            verify_root(state, cwd=os.getcwd(), host_session_id=args.host_session_id)
            result = budget.close(Path(args.ledger), outcome=args.outcome, evidence_ref=args.evidence_ref)
            retire(host_session_id=args.host_session_id)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    except (ValueError, RuntimeError, OSError, TimeoutError, KeyError, TypeError) as exc:
        print(json.dumps({"status":"BLOCKED", "reason":str(exc)}, ensure_ascii=True))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
