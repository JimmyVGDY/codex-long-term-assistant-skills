"""中文：完整资格试验与分段预算。English: no survivor-only study accounting.

Each segment is a distinct Desktop root with a disjoint, prepaid allocation.
Its native budget remains the dispatch owner. This module neither resets a
budget nor starts a model, and never treats registration as independence proof.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from . import budget_v5 as budget
from .common import parse_iso, verify_record
from .event_v2 import stable_repo_fingerprint
from .evidence import check_evidence
from .routing_context_contract import MODE_V2
from .routing_context_v4 import read_evaluations, validate_evaluation
from .routing_contract import (VECTOR_KEYS, add_vectors, assert_current_window, exact, fail,
    fits, identifier, identity, integer, policy, policy_digest, profile_spec, read_document, ref, resource_need, sha, vector)
from .routing_evaluation_v4 import trial_packet

STUDY_FIELDS = {"schema_version", "study_id", "identity", "policy_digest", "created_at", "expires_at",
                "evaluations", "independence", "segments", "capacity"}
SEGMENT_FIELDS = {"segment_id", "ledger_path", "host_session_ref", "trial_refs", "capacity"}
INDEPENDENCE_FIELDS = {"schema_version", "reviewed_by", "review_evidence", "cases"}
CASE_PROOF_FIELDS = {"case_ref", "cluster_id", "source_problem_ref", "root_cause_ref"}
MAX_SEGMENTS = 100
MAX_SEGMENT_ATTEMPTS = 64


def trial_key(protocol_ref: str, case_ref: str, profile_id: str, repetition: int) -> str:
    sha(protocol_ref); sha(case_ref); profile_spec(profile_id)
    integer(repetition, "STUDY_REPETITION", minimum=1, maximum=20)
    return ref({"protocol_ref":protocol_ref,"case_ref":case_ref,"profile_id":profile_id,"repetition":repetition})


def planned_trials(evaluations: list[Mapping[str, Any]]) -> dict[str, dict]:
    if not isinstance(evaluations, list) or not evaluations or len(evaluations) > 100:
        fail("STUDY_EVALUATIONS_LIMIT")
    trials, protocols = {}, set()
    for value in evaluations:
        plan = validate_evaluation(value)
        if plan["protocol_ref"] in protocols:
            fail("STUDY_PROTOCOL_DUPLICATE")
        protocols.add(plan["protocol_ref"])
        costs = {cost["profile_id"]:cost for cost in plan["costs"]}
        for case in plan["cases"]:
            for profile_id, cost in costs.items():
                for repetition in range(1, plan["repetitions"] + 1):
                    key = trial_key(plan["protocol_ref"], case["case_ref"], profile_id, repetition)
                    trials[key] = {"protocol_ref":plan["protocol_ref"],"case_ref":case["case_ref"],
                        "profile_id":profile_id,"repetition":repetition,"cluster_id":case["cluster_id"],
                        "resources":resource_need(profile_id,cost["reserve_units"])}
                    if len(trials) > policy()["limits"]["max_cases"]:
                        fail("STUDY_TRIAL_LIMIT")
    return trials


def _validate_structure(value: Mapping[str, Any], *, version="qualification-study/1", segment_fields=SEGMENT_FIELDS, same_host=False, root_tasks=False) -> dict:
    exact(value, STUDY_FIELDS, "STUDY_FIELDS")
    if value["schema_version"] != version or value["policy_digest"] != policy_digest():
        fail("STUDY_VERSION_OR_POLICY")
    identifier(value["study_id"])
    declared = identity(value["identity"])
    assert_current_window(value, value["created_at"])
    trials = planned_trials(value["evaluations"])
    cases = {}
    for plan in value["evaluations"]:
        if plan["identity"] != declared:
            fail("STUDY_PROJECT_MISMATCH")
        for case in plan["cases"]:
            old = cases.setdefault(case["case_ref"], case)
            if old != case:
                fail("STUDY_CASE_CONFLICT")
    independence = exact(value["independence"], INDEPENDENCE_FIELDS, "STUDY_INDEPENDENCE_FIELDS")
    if independence["schema_version"] != "reviewed-case-independence/1" \
            or not isinstance(independence["reviewed_by"], str) \
            or not independence["reviewed_by"].startswith("parent:"):
        fail("STUDY_INDEPENDENCE_REVIEW_REQUIRED")
    identifier(independence["reviewed_by"][7:])
    evidence = exact(independence["review_evidence"], {"path","sha256"}, "STUDY_INDEPENDENCE_SOURCE")
    sha(evidence["sha256"])
    if not isinstance(evidence["path"],str) or not Path(evidence["path"]).is_absolute():
        fail("STUDY_INDEPENDENCE_SOURCE_PATH")
    proofs = independence["cases"]
    if not isinstance(proofs, list) or len(proofs) != len(cases):
        fail("STUDY_INDEPENDENCE_COVERAGE")
    seen, problem_clusters, cause_clusters, prompt_clusters = set(), {}, {}, {}
    for proof in proofs:
        exact(proof, CASE_PROOF_FIELDS, "STUDY_CASE_PROOF_FIELDS")
        case_ref = sha(proof["case_ref"])
        if case_ref in seen or case_ref not in cases or proof["cluster_id"] != cases[case_ref]["cluster_id"]:
            fail("STUDY_INDEPENDENCE_COVERAGE")
        seen.add(case_ref)
        prompt = cases[case_ref]["prompt_ref"]
        if prompt_clusters.setdefault(prompt,proof["cluster_id"]) != proof["cluster_id"]:
            fail("STUDY_IDENTICAL_PROMPT_CLUSTER_ALIAS")
        for field, groups in (("source_problem_ref",problem_clusters),("root_cause_ref",cause_clusters)):
            source = sha(proof[field])
            cluster = groups.setdefault(source, proof["cluster_id"])
            if cluster != proof["cluster_id"]:
                fail("STUDY_INDEPENDENT_CLUSTER_ALIAS")
    segments = value["segments"]
    if not isinstance(segments, list) or not segments or len(segments) > MAX_SEGMENTS:
        fail("STUDY_SEGMENT_LIMIT")
    allocated, ids, roots, paths, tasks = set(), set(), set(), set(), set()
    capacities = []
    for segment in segments:
        exact(segment, segment_fields, "STUDY_SEGMENT_FIELDS")
        sid = identifier(segment["segment_id"])
        session = sha(segment["host_session_ref"])
        path = segment["ledger_path"]
        if not isinstance(path,str) or not Path(path).is_absolute():
            fail("STUDY_SEGMENT_PATH")
        normalized = str(Path(path).resolve()).casefold()
        if sid in ids or (not same_host and session in roots) or normalized in paths:
            fail("STUDY_SEGMENT_REUSED")
        if root_tasks:
            task=identifier(segment["root_task_id"])
            if task in tasks:fail("STUDY_TASK_REUSED")
            tasks.add(task)
        ids.add(sid); roots.add(session); paths.add(normalized)
        keys = segment["trial_refs"]
        if not isinstance(keys,list) or not keys or len(keys) > MAX_SEGMENT_ATTEMPTS \
                or any(not isinstance(key,str) or key not in trials or key in allocated for key in keys) \
                or len(keys) != len(set(keys)):
            fail("STUDY_SEGMENT_ALLOCATION")
        capacity = vector(segment["capacity"])
        if capacity["attempts"] > MAX_SEGMENT_ATTEMPTS \
                or not fits(add_vectors(*(trials[key]["resources"] for key in keys)), capacity):
            fail("STUDY_SEGMENT_CAPACITY")
        allocated.update(keys); capacities.append(capacity)
    if allocated != set(trials):
        fail("STUDY_PLANNED_TRIALS_UNALLOCATED")
    if not fits(add_vectors(*capacities), vector(value["capacity"])):
        fail("STUDY_AGGREGATE_CAPACITY")
    return copy.deepcopy(dict(value))


def validate_study(value: Mapping[str, Any]) -> dict:
    """中文：显式选择 Schema，不升级或对投影后的第一版文档重新计算哈希。
    
    English: Select an explicit schema; never upgrade or hash a projected /1 document.
    """
    if isinstance(value,dict) and value.get('schema_version')=='qualification-study/2':
        from .research_documents import read_study_envelope
        read_study_envelope(value)
        return copy.deepcopy(value)
    return _validate_structure(value)


def study_plan(value):
    """中文：第二版计划是独立哈希的祖先文档，不是改写后的信封。
    
    English: A /2 plan is an independently hashed ancestor, not a rewritten envelope.
    """
    validated=validate_study(value)
    if validated['schema_version']=='qualification-study/2':
        from .research_documents import read_study_envelope
        return read_study_envelope(validated)[0]
    return validated


def bind_evaluation(study: Mapping[str, Any], protocol_ref: str) -> dict:
    study = validate_study(study)
    matches = [plan for plan in study_plan(study)["evaluations"] if plan["protocol_ref"] == protocol_ref]
    if len(matches) != 1:
        fail("STUDY_PROTOCOL_UNKNOWN")
    plan = copy.deepcopy(matches[0])
    for cost in plan["costs"]:
        # 中文：原生预算在允许派发前冻结评测文档，包括这份预登记哈希。
        # English: The native budget freezes the evaluation document, including this
        # preregistration hash, before any dispatch is permitted.
        cost["source_ref"] = ref(study)
    return validate_evaluation(plan)


def independence_scope(study: Mapping[str, Any]) -> str:
    """中文：范围排除自身 Evidence 引用，避免循环摘要。
    
    English: Scope excludes its own Evidence reference to avoid a circular digest.
    """
    return ref({"schema_version":"case-independence-scope/1","identity":study["identity"],
                "policy_digest":study["policy_digest"],
                "protocol_refs":sorted(p["protocol_ref"] for p in study["evaluations"]),
                "reviewed_by":study["independence"]["reviewed_by"],
                "cases":sorted(study["independence"]["cases"],key=ref)})


def _independence_evidence(study: Mapping[str, Any], *, fresh: bool = False) -> dict:
    source = study["independence"]["review_evidence"]
    path = Path(source["path"])
    record, digest = read_document(path)
    verify_record(record,"Case independence review")
    repo = Path(record.get("baseline",{}).get("repo_path",""))
    reviewer = study["independence"]["reviewed_by"][7:]
    if digest != source["sha256"] or not repo.is_absolute() or record.get("schema_version") != 1 \
            or record.get("status") != "valid" \
            or record.get("source") != "parent-reviewed-case-independence" or record.get("kind") != "review" \
            or record.get("task_id") != reviewer or record.get("project_id") != study["identity"]["project_id"] \
            or stable_repo_fingerprint(str(repo)) != study["identity"]["repo_fingerprint"] \
            or "independence:" + independence_scope(study) not in record.get("scope_refs",[]) \
            or parse_iso(record["recorded_at"]) > parse_iso(study["created_at"]):
        fail("STUDY_INDEPENDENCE_EVIDENCE_INVALID")
    if fresh and not check_evidence(path,repo,study["identity"]["project_id"],reviewer).valid:
        fail("STUDY_INDEPENDENCE_EVIDENCE_STALE")
    return record


def audit_study(study: Mapping[str, Any], trial_sources: list[Mapping[str, Any]], *, now: str, campaign_manifest=None) -> dict:
    """中文：重建每个已分配根，包括失败和未评分预占。返回的是记账报告，不授予资格或派发权限；缺段或缺评分必须显式保留，不能从分母消失。
    
    English: Rebuild every allocated root, including failed/ungraded reservations.
    
    Returns an accounting report, not qualification or dispatch authority. A
    missing segment/grade is visible rather than disappearing from a denominator.
    """
    from .routing_evaluation_v5 import SOURCE_FIELDS, read_trial
    envelope = validate_study(study)
    bindings=None;campaign=None
    if envelope['schema_version']=='qualification-study/2':
        if campaign_manifest is None:fail('RESEARCH_CAMPAIGN_AUDIT_REQUIRED')
        from .research_documents import read_manifest,read_study_envelope
        campaign,all_plans,all_envelopes,_=read_manifest(campaign_manifest)
        if envelope not in all_envelopes:fail('RESEARCH_UNREGISTERED_STUDY')
        study,bindings=read_study_envelope(envelope,campaign)
    else:study=envelope
    assert_current_window(study, now)
    independence = _independence_evidence(study)
    if not isinstance(trial_sources,list) or len(trial_sources) > policy()["limits"]["max_cases"]:
        fail("STUDY_TRIAL_SOURCE_LIMIT")
    trials = planned_trials(study["evaluations"])
    expected_plans = {p["protocol_ref"]:bind_evaluation(envelope,p["protocol_ref"]) for p in study["evaluations"]}
    counts = dict(planned=len(trials),attempts=0,created=0,not_started=0,unattributed=0,
                  terminal=0,active=0,delivered=0,final_bound=0,graded=0,semantic_passed=0,
                  controller_accounting=0,missing_segments=0,missing_trials=0)
    counts["model_incomplete"] = 0
    counts["model_invalid_format"] = 0
    if bindings is not None:counts["model_boundary_negatives"]=0
    resources = {key:0 for key in VECTOR_KEYS}
    issues, observed, cache, root_ids, hashes, grades = [], {}, {}, set(), {}, {}
    allocated_paths = {str(Path(s["ledger_path"]).resolve()).casefold():s for s in study["segments"]}
    for segment in study["segments"]:
        path = Path(segment["ledger_path"])
        if not path.exists():
            counts["missing_segments"] += 1
            issues.append({"segment_id":segment["segment_id"],"reason":"MISSING_SEGMENT"})
            continue
        events = budget._read_events(path)
        state = budget.replay(events)
        if state["identity"]["task_id"] in root_ids:
            fail("STUDY_NATIVE_ROOT_REUSED")
        root_ids.add(state["identity"]["task_id"])
        pair = {key:state["identity"][key] for key in ("project_id","repo_fingerprint")}
        if pair != study["identity"] or state["execution_mode"] != "EVALUATION" \
                or state["root_binding"]["context_runtime"]["transport_mode"] != MODE_V2 \
                or state["root_binding"]["host_session_ref"] != segment["host_session_ref"] \
                or state["capacity"] != segment["capacity"] or state["max_depth"] != 1:
            fail("STUDY_SEGMENT_ROOT_BINDING")
        if bindings is not None:
            binding=next(b for b in bindings if b['segment_id']==segment['segment_id'])
            root,_=read_document(Path(state['sources']['root_envelope']))
            declared=root.get('routing',{}).get('research_campaign')
            if not isinstance(declared,dict) or declared.get('segment_binding_ref')!=ref(binding) or state['identity']['task_id']!=binding['root_task_id']:
                fail('RESEARCH_STUDY_NATIVE_SEGMENT_BINDING')
            # 中文：完整阶段授权由研究协调者核验，不能从这个字段推断。
            # English: Full stage authority must be checked by the campaign owner, not inferred from this field.
            from .research_campaign import verify_historical_root
            verify_historical_root(declared,state,campaign,binding)
        if parse_iso(events[0]["recorded_at"]) < parse_iso(study["created_at"]):
            fail("STUDY_PREREGISTRATION_REQUIRED")
        plans = read_evaluations(state)
        if any(p["protocol_ref"] not in expected_plans or p != expected_plans[p["protocol_ref"]] for p in plans):
            fail("STUDY_NATIVE_PLAN_BINDING")
        if state["closed"]:
            cache[str(path.resolve())] = events,state
        else:
            issues.append({"segment_id":segment["segment_id"],"reason":"SEGMENT_NOT_CLOSED"})
        hashes[segment["segment_id"]] = events[-1]["record_hash"]
        usage = budget._usage(state)
        resources = add_vectors(resources, usage["resources"])
        for rid, attempt in state["reservations"].items():
            counts["attempts"] += 1
            permit = state["permits"][attempt["permit_id"]]
            request = permit["request"]
            if request["baseline_sha256"] != independence["baseline"]["sha256"]:
                fail("STUDY_NATIVE_BASELINE_CHANGED")
            plan = next((p for p in plans if request["evaluation_case_ref"] in p["case_plan"]),None)
            if not plan:
                fail("STUDY_NATIVE_CASE_UNKNOWN")
            profile = permit["selection"]["approved_profile"]
            repetitions = [r for r in range(1,plan["repetitions"]+1)
                if trial_packet(request["evaluation_case_ref"],profile,r) == request["packet_sha256"]]
            if len(repetitions) != 1:
                fail("STUDY_NATIVE_REPETITION_BINDING")
            key = trial_key(plan["protocol_ref"],request["evaluation_case_ref"],profile,repetitions[0])
            if key not in segment["trial_refs"]:
                fail("STUDY_NATIVE_ALLOCATION_VIOLATION")
            receipt = state["host_receipts"].get(rid)
            if attempt["state"] == "NOT_STARTED_RELEASED":
                counts["not_started"] += 1
                continue
            if key in observed:
                fail("STUDY_MODEL_TRIAL_REPEATED")
            observed[key] = (str(path.resolve()),rid)
            if not receipt or receipt["disposition"] != "created":
                counts["unattributed"] += 1
                issues.append({"trial_ref":key,"reason":"CREATION_NOT_CONFIRMED"})
            else:
                counts["created"] += 1
            counts["terminal"] += int(attempt["state"] == "COMPLETED")
            counts["active"] += int(attempt["state"] in {"RESERVED","STARTED"})
            counts["delivered"] += int(rid in state["context_deliveries"])
            counts["final_bound"] += int(rid in state["context_finals"])
            accepted = state["accepted_results"].get(rid)
            if accepted and accepted["status"] == "incomplete":
                final = state["context_finals"].get(rid,{})
                if final.get("response_ref") == accepted["response_ref"]:
                    counts["model_incomplete"] += 1
                elif rid in state.get("context_raw_finals",{}):
                    counts["model_invalid_format"] += 1
                else:
                    counts["controller_accounting"] += 1
                    issues.append({"trial_ref":key,"reason":"CONTROLLER_ONLY_FAILURE_ACCOUNTING"})
    if counts["attempts"] != counts["created"] + counts["not_started"] + counts["unattributed"] \
            or counts["attempts"] != resources["attempts"] or not fits(resources,study["capacity"]):
        fail("STUDY_RESOURCE_RECONCILIATION")
    for source in trial_sources:
        exact(source,SOURCE_FIELDS,"STUDY_TRIAL_SOURCE_FIELDS")
        path = str(Path(source.get("ledger", "")).resolve())
        if path.casefold() not in allocated_paths:
            fail("STUDY_UNREGISTERED_GRADE_SOURCE")
        if path not in cache:
            issues.append({"segment_id":allocated_paths[path.casefold()]["segment_id"],"reason":"GRADE_ROOT_NOT_CLOSED"})
            continue
        sample, trace, plan = read_trial(source,cache=cache)
        key = trial_key(plan["protocol_ref"],sample["case_ref"],sample["profile_id"],sample["repetition"])
        if key in grades or key not in observed or observed[key][0] != path:
            fail("STUDY_GRADE_DUPLICATE_OR_FOREIGN")
        if sample["receipt_ref"] != trace["receipt_ref"]:
            fail("STUDY_GRADE_RECEIPT_BINDING")
        grades[key] = sample
        if bindings is not None and trace.get('schema_version')=='desktop-evaluation-trace/5':
            if trace.get('negative_verified') is not True or sample['passed'] or not sample['boundary_failure']:fail('RESEARCH_NEGATIVE_NOT_PROVEN')
            counts['model_boundary_negatives']+=1
            issues=[i for i in issues if not (i.get('trial_ref')==key and i.get('reason')=='CONTROLLER_ONLY_FAILURE_ACCOUNTING')]
    counts["graded"] = len(grades)
    counts["semantic_passed"] = sum(sample["passed"] for sample in grades.values())
    counts["missing_trials"] = len(set(trials)-set(observed))
    counts["ungraded_trials"] = len(set(trials)-set(grades))
    complete = not issues and set(grades) == set(trials) and counts["terminal"] == len(trials)
    if not complete and not issues:
        issues.append({"reason":"STUDY_INCOMPLETE_DENOMINATOR"})
    report = {"schema_version":"qualification-study-audit/2" if bindings is not None else "qualification-study-audit/1","study_ref":ref(envelope),"identity":study["identity"],
            "complete":complete,"counts":counts,"resources":resources,"billing":"UNKNOWN",
            "resources_complete":counts["missing_segments"] == 0,
            "source_ledger_heads":hashes,"sample_refs":{key:ref(sample) for key,sample in sorted(grades.items())},
            "issues":issues,"qualification_granted":False}
    if bindings is not None:
        report.update(execution_complete=counts['missing_segments']==0 and counts['missing_trials']==0 and counts['active']==0 and counts['terminal']==len(trials),
            accounting_complete=counts['missing_segments']==0 and counts['unattributed']==0,
            quality_evidence_complete=set(grades)==set(trials),
            quality_all_passed=set(grades)==set(trials) and all(s['passed'] and not s['boundary_failure'] and not s['critical_failure'] for s in grades.values()))
    return report


def validate_qualification_source(source):
    modern=isinstance(source,dict) and source.get('schema_version')=='study-qualification-source/2'
    exact(source,{'study','trials','audit_ref'}|({'schema_version','campaign'} if modern else set()),'STUDY_QUALIFICATION_SOURCE')
    sha(source['audit_ref'])
    for name in ('study','trials')+ (('campaign',) if modern else ()):
        pointer=exact(source[name],{'path','sha256'},'STUDY_QUALIFICATION_DOCUMENT');sha(pointer['sha256'])
        if not isinstance(pointer['path'],str) or not Path(pointer['path']).is_absolute():fail('STUDY_QUALIFICATION_SOURCE_PATH')
    return modern


def load_study_sources(source: Mapping[str, Any], *, now: str) -> tuple[dict,list,dict]:
    """中文：重读完整登记图；旧第一版不能消费第二版信封。
    
    English: Re-read the full registered graph; old /1 cannot consume a /2 envelope.
    """
    modern=validate_qualification_source(source);documents={}
    from .routing_context_contract import safe_file
    for name in ('study','trials')+(('campaign',) if modern else ()):
        try:document,digest=read_document(safe_file(Path(source[name]['path'])),maximum=8_388_608)
        except OSError:fail('CONTEXT_QUALIFICATION_STUDY_UNAVAILABLE')
        if digest!=source[name]['sha256']:fail('STUDY_QUALIFICATION_SOURCE_CHANGED')
        documents[name]=document
    if (documents['study'].get('schema_version')=='qualification-study/2')!=modern:fail('RESEARCH_STUDY_SOURCE_VERSION_REQUIRED')
    trials=exact(documents['trials'],{'trials'},'STUDY_TRIAL_SOURCES')['trials']
    report=audit_study(documents['study'],trials,now=now,campaign_manifest=documents.get('campaign'))
    if not report['complete']:fail('CONTEXT_QUALIFICATION_STUDY_INCOMPLETE')
    if ref(report)!=source['audit_ref']:fail('STUDY_QUALIFICATION_AUDIT_CHANGED')
    return documents['study'],trials,report


def require_experiment_study(experiment: Mapping[str, Any], *, now: str) -> dict:
    envelope,_,report=load_study_sources(experiment["qualification_source"],now=now)
    study=study_plan(envelope)
    if study["identity"] != experiment["identity"]:
        fail("STUDY_EXPERIMENT_IDENTITY")
    reviewed = _independence_evidence(study)
    if experiment["issuer"]["baseline_sha256"] != reviewed["baseline"]["sha256"]:
        fail("STUDY_EXPERIMENT_BASELINE_CHANGED")
    plans=[p for p in study["evaluations"] if p["protocol_ref"] == experiment["protocol_ref"]]
    if len(plans) != 1:
        fail("STUDY_EXPERIMENT_PROTOCOL")
    plan=plans[0]
    for key in ("scenario","rubric_ref","minimum_pass_bp","baseline_profile","comparisons",
                "family_intervals","case_plan","repetitions"):
        if experiment[key] != plan[key]:
            fail("STUDY_EXPERIMENT_PROTOCOL")
    expected={key:row for key,row in planned_trials(study["evaluations"]).items()
              if row["protocol_ref"] == experiment["protocol_ref"]}
    actual={}
    for row in experiment["samples"]:
        key=trial_key(experiment["protocol_ref"],row["case_ref"],row["profile_id"],row["repetition"])
        if key in actual:
            fail("STUDY_EXPERIMENT_TRIAL_REPEATED")
        actual[key]=ref(row)
    if set(actual) != set(expected) or any(report["sample_refs"].get(key) != digest for key,digest in actual.items()):
        fail("STUDY_EXPERIMENT_GRADES_CHANGED")
    return report
