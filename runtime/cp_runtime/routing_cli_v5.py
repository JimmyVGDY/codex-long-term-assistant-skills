"""中文：桌面上下文内部管理入口。English: Internal Desktop context management; no standalone client support."""
import argparse
import json
import os
from pathlib import Path
from . import budget_v5 as budget, review_v5 as review
from .common import atomic_write_json, repo_snapshot, require_external_state, utc_now
from .routing_context_contract import CONTEXT_64K, ISOLATED_PHASES, create_bundle, runtime, load_bundle, MODE, MODE_V2
from .routing_context_v5 import build_root_binding, loader, verify_root
from .routing_contract import exact, fail, read_document, ref
from .routing_registry_v5 import bind, retire

def main():
    parser = argparse.ArgumentParser(description="Opt-in Desktop authoritative review context")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--config", required=True)
    init.add_argument("--root-envelope", required=True)
    init.add_argument("--reader", required=True)
    init.add_argument("--python", required=True)
    init.add_argument("--transport-mode", choices=(MODE, MODE_V2), default=None)
    init.add_argument("--context-profile",choices=(CONTEXT_64K,))
    init.add_argument('--evaluation-contract',choices=(ISOLATED_PHASES,))
    from .review_vector_transport import CONTRACT as VECTOR_CONTRACT
    init.add_argument('--review-contract',choices=(VECTOR_CONTRACT,))
    from .ordinary_routing_v5 import CONTRACT
    init.add_argument('--ordinary-contract',choices=(CONTRACT,))
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
    p.add_argument("--context-profile",choices=(CONTEXT_64K,))
    p=sub.add_parser('ordinary-prepare')
    for field in ('ledger','host-session-id','request','dispatch-key'):p.add_argument('--'+field,required=True)
    p.add_argument('--transition')
    p=sub.add_parser('ordinary-result')
    for field in ('ledger','host-session-id','reservation-id','response','validation'):p.add_argument('--'+field,required=True)
    p.add_argument('--status',choices=('pass','incomplete'),required=True)
    p = sub.add_parser("review-init")
    p.add_argument("--ledger", required=True)
    p.add_argument("--review-dir", required=True)
    p.add_argument("--boundary-id", required=True)
    for name in ("result", "failure-accounting", "review-status", "review-close"):
        p = sub.add_parser(name)
        p.add_argument("--review-dir", required=True)
        if name == "result":
            p.add_argument("--permit-id", required=True)
            p.add_argument("--response", required=True)
        if name == "failure-accounting":
            p.add_argument("--permit-id", required=True)
            p.add_argument("--evidence-ref", required=True)
        if name == "review-close":
            p.add_argument("--conclusion", required=True)
    p = sub.add_parser("qualification-size-plan")
    p.add_argument("--comparisons", type=int, required=True)
    p = sub.add_parser("qualification-grade")
    for field in ("ledger", "reservation-id", "response", "gold", "rubric", "transcript", "grade"):
        p.add_argument("--" + field, required=True)
    p.add_argument("--repetition", type=int, default=1)
    p.add_argument("--host-session-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    p = sub.add_parser("qualification-assemble")
    for field in ("study", "evaluation", "trial-sources", "experiment-id", "issuer-task-id", "output"):
        p.add_argument("--" + field, required=True)
    p = sub.add_parser("qualification-study-audit")
    for field in ("study", "trial-sources"):
        p.add_argument("--" + field,required=True)
    p = sub.add_parser("qualification-study-bind")
    for field in ("study", "protocol-ref", "output"):
        p.add_argument("--" + field,required=True)
    for name,fields in {
        "default-prepare":("definition","output","task-id"),
        "default-verify-install":("source",),
        "default-activate":("source","approval","task-id"),
        "default-revoke":("source","reason-ref"),
        "default-restore-legacy":("source","reason-ref","approval","task-id"),
        "default-resolve":("profile","task-id"),
    }.items():
        p=sub.add_parser(name)
        for field in fields:p.add_argument("--"+field,required=True)
    args = parser.parse_args()
    try:
        if args.command.startswith("default-"):
            from . import desktop_default_activation as defaults
            from .event_v2 import stable_repo_fingerprint
            from .project import validate_binding
            if args.command=="default-prepare":
                definition,_=read_document(Path(args.definition),maximum=8_388_608)
                result=defaults.prepare(Path(args.output),definition,repo_path=Path.cwd(),task_id=args.task_id,now=utc_now())
            elif args.command=="default-resolve":
                bound=validate_binding(Path(args.profile),Path.cwd())
                identity={"project_id":bound.project_id,"repo_fingerprint":stable_repo_fingerprint(str(Path.cwd()))}
                result=defaults.resolve_default(defaults.pointer_for(identity),expected_identity=identity,
                                               task_id=args.task_id,now=utc_now())
            else:
                source,_=read_document(Path(args.source))
                if args.command=="default-verify-install":
                    result=defaults.verify_installation(source,repo_path=Path.cwd(),now=utc_now())
                elif args.command=="default-revoke":
                    result=defaults.revoke(source,repo_path=Path.cwd(),reason_ref=args.reason_ref,now=utc_now())
                elif args.command=="default-restore-legacy":
                    result=defaults.restore_legacy(source,approval_path=Path(args.approval),repo_path=Path.cwd(),
                        task_id=args.task_id,reason_ref=args.reason_ref,now=utc_now())
                else:
                    definition=defaults._read(source)["definition"]
                    result=defaults.activate(source,pointer_path=defaults.pointer_for(definition["identity"]),
                        approval_path=Path(args.approval),repo_path=Path.cwd(),task_id=args.task_id,now=utc_now())
        elif args.command == "qualification-size-plan":
            from .routing_qualification_plan import zero_discordance_plan
            result = zero_discordance_plan(args.comparisons)
        elif args.command == "qualification-grade":
            from .routing_evaluation_v5 import record_trial
            result = record_trial(Path(args.ledger), cwd=os.getcwd(), host_session_id=args.host_session_id,
                reservation_id=args.reservation_id, repetition=args.repetition, response_path=Path(args.response),
                gold_path=Path(args.gold), rubric_path=Path(args.rubric), transcript_path=Path(args.transcript),
                grade=read_document(Path(args.grade))[0])
        elif args.command == "qualification-assemble":
            from .routing_evaluation_v5 import assemble_experiment
            from .qualification_study import audit_study
            from .routing_evaluation_v4 import file_reference
            source, _ = read_document(Path(args.trial_sources), maximum=8_388_608)
            exact(source, {"trials"}, "EVALUATION_TRIAL_SOURCES")
            study, _ = read_document(Path(args.study), maximum=8_388_608)
            audit = audit_study(study,source["trials"],now=utc_now())
            if not audit["complete"]:
                fail("CONTEXT_QUALIFICATION_STUDY_INCOMPLETE")
            qualification_source={"study":{"path":str(Path(args.study).resolve()),"sha256":file_reference(Path(args.study))},
                "trials":{"path":str(Path(args.trial_sources).resolve()),"sha256":file_reference(Path(args.trial_sources))},
                "audit_ref":ref(audit)}
            result = assemble_experiment(read_document(Path(args.evaluation), maximum=8_388_608)[0], source["trials"],
                experiment_id=args.experiment_id, issuer_task_id=args.issuer_task_id,
                issuer_baseline=repo_snapshot(Path.cwd())["sha256"],qualification_source=qualification_source)
            output = Path(args.output).resolve()
            require_external_state(output, Path.cwd())
            if output.exists():
                if read_document(output, maximum=8_388_608)[0] != result:
                    fail("CONTEXT_EVALUATION_EXPERIMENT_IMMUTABLE")
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_json(output, result)
            result = {"status":"ASSEMBLED_NOT_PUBLISHED", "output":str(output),
                      "samples":len(result["samples"]), "schema_version":result["schema_version"]}
        elif args.command == "qualification-study-audit":
            from .qualification_study import audit_study
            study,_=read_document(Path(args.study),maximum=8_388_608)
            sources,_=read_document(Path(args.trial_sources),maximum=8_388_608)
            exact(sources,{"trials"},"STUDY_TRIAL_SOURCES")
            result=audit_study(study,sources["trials"],now=utc_now())
        elif args.command == "qualification-study-bind":
            from .qualification_study import _independence_evidence, bind_evaluation
            study,_=read_document(Path(args.study),maximum=8_388_608)
            result=bind_evaluation(study,args.protocol_ref)
            _independence_evidence(study,fresh=True)
            output=Path(args.output).resolve()
            require_external_state(output,Path.cwd())
            if output.exists() and read_document(output,maximum=8_388_608)[0] != result:
                fail("STUDY_BOUND_PLAN_IMMUTABLE")
            if not output.exists():
                output.parent.mkdir(parents=True,exist_ok=True)
                atomic_write_json(output,result)
            result={"status":"PREREGISTERED_NOT_QUALIFIED","output":str(output),"study_ref":ref(study)}
        elif args.command == "init":
            config, _ = read_document(Path(args.config))
            exact(config, {"budget_id", "sources", "execution_mode", "capacity", "role_capacity",
                           "phase_capacity", "phase_plan", "max_parallel", "max_depth"}, "V5_INIT_FIELDS")
            if config["execution_mode"] not in {"EVALUATION","PRODUCTION"} or config["max_depth"] != 1:
                fail("V5_EVALUATION_DEPTH_ONE_ONLY")
            if args.review_contract and config['execution_mode']!='EVALUATION':
                fail('VECTOR_DEVELOPMENT_ONLY')
            if args.evaluation_contract and config['execution_mode']!='EVALUATION':
                fail('V5_PHASE_EVALUATION_ONLY')
            if Path(config["sources"]["root_envelope"]).resolve() != Path(args.root_envelope).resolve():
                fail("V5_ENVELOPE_SOURCE_MISMATCH")
            transport_mode=args.transport_mode or (MODE_V2 if config["execution_mode"]=="PRODUCTION" else MODE)
            selected_ordinary=args.ordinary_contract
            selected_profile=args.context_profile
            selected_delivery=None
            if config['execution_mode']=='PRODUCTION':
                from .desktop_default_activation import _read
                envelope,_=read_document(Path(args.root_envelope))
                activation=envelope.get('routing',{}).get('desktop_default_activation')
                if activation:
                    definition=_read(activation)['definition']
                    if selected_ordinary is None:selected_ordinary=definition.get('ordinary_contract')
                    if definition['schema_version']=='desktop-default-activation/3':
                        if args.context_profile not in (None,definition['context_profile']) or selected_ordinary!=definition.get('ordinary_contract'):
                            fail('DEFAULT_MATRIX_RUNTIME_CONTRACT')
                        selected_profile=definition['context_profile']
                        selected_delivery=definition['delivery_contract']
            identity, binding = build_root_binding(Path(args.root_envelope), args.host_session_id,
                                                   runtime(Path(args.reader), Path(args.python), transport_mode=transport_mode,
                                                           context_profile=selected_profile,ordinary_contract=selected_ordinary,
                                                           evaluation_contract=args.evaluation_contract, review_contract=args.review_contract,
                                                           delivery_contract=selected_delivery))
            if config["execution_mode"]=="PRODUCTION":
                from .desktop_default_activation import verify_active, verify_root_card_sources
                envelope,_=read_document(Path(args.root_envelope))
                source=envelope.get("routing",{}).get("desktop_default_activation")
                if not source or transport_mode!=MODE_V2:
                    fail("V5_PRODUCTION_HOST_COVERAGE_UNQUALIFIED")
                active=verify_active(source,expected_identity={key:identity[key] for key in
                    ("project_id","repo_fingerprint")},now=utc_now(),consumer_task_id=identity["task_id"])
                verify_root_card_sources(active["definition"],config["sources"]["card_sets"])
            result = budget.initialize(Path(args.ledger), declared_identity={**identity, "budget_id": config["budget_id"]},
                root_binding=binding, **{k:v for k,v in config.items() if k != "budget_id"})
        elif args.command == 'ordinary-prepare':
            from .ordinary_routing_v5 import enabled
            request,_=read_document(Path(args.request))
            state=budget.read_budget(Path(args.ledger))
            runtime_config=state['root_binding']['context_runtime']
            if not enabled(runtime_config,request['scenario']['role']):fail('ORDINARY_CONTRACT_REQUIRED')
            result=budget.prepare(Path(args.ledger),request,dispatch_key=args.dispatch_key,depth=1,
                snapshot_loader=loader(cwd=os.getcwd(),host_session_id=args.host_session_id),
                transition=read_document(Path(args.transition))[0] if args.transition else None)
            if result.get('status') in {'CANDIDATE_SELECTED','EVALUATION_SELECTED'}:
                from .routing_context_contract import load_bundle
                result['request_parameters'].update(task_name=args.dispatch_key,fork_turns='none',
                    message=load_bundle(request,runtime_config)['business_prompt'])
        elif args.command == 'ordinary-result':
            from .ordinary_delegation_v5 import record_result
            result=record_result(Path(args.ledger),cwd=os.getcwd(),host_session_id=args.host_session_id,
                reservation_id=args.reservation_id,response_path=Path(args.response),
                validation_path=Path(args.validation),status=args.status)
        elif args.command == "bundle":
            spec, _ = read_document(Path(args.manifest))
            exact(spec, {"business_prompt", "packet_sha256", "baseline_sha256", "artifacts"}, "V5_BUNDLE_INPUT")
            result = create_bundle(Path(args.output), repo=Path.cwd(), business_prompt=Path(spec["business_prompt"]),
                packet_sha256=spec["packet_sha256"], baseline_sha256=spec["baseline_sha256"],
                artifacts={k:Path(v) for k,v in spec["artifacts"].items()},context_profile=args.context_profile)
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
        elif args.command == "failure-accounting":
            result = review.record_failure_accounting(Path(args.review_dir), args.permit_id, evidence_ref=args.evidence_ref)
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
