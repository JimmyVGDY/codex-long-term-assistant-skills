"""中文：资格通过后的桌面默认激活。English: defaults are explicit, pinned and reversible."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from .approval import check_approval, consume_approval, load_approval
from .common import atomic_write_json, read_json, repo_snapshot, require_external_state, resolve_codex_home, parse_iso
from .event_v2 import OwnerTokenLock, stable_repo_fingerprint
from .path_identity import same_path
from .payload_integrity import load_manifest, verify_payload
from .routing_cards import load_publication, validate_bundle
from .routing_context_contract import CONTEXT_64K, MODE_V2, bounded_bytes, digest
from .routing_context_v4 import _trace_loader
from .routing_contract import (POLICY_ID, assert_current_window, exact, fail, identifier, identity,
                               integer, policy_digest, profile_spec, read_document, ref, sha)

DEFINITION_FIELDS={"schema_version","activation_id","identity","policy_id","policy_digest","transport_mode",
    "consumer_version","created_at","expires_at","required_scenarios","cards","installation"}
INSTALLATION_FIELDS={"manifest","source_root","managed_root","cache_root","enhancement_home","required_hooks","python"}
CARD_FIELDS={"bundle","experiment","publication","trace_ledgers","bundle_ref","experiment_ref",
             "publication_ref","publication_revision"}
STATE_FIELDS={"schema_version","definition","definition_ref","status","installation_ref","history"}
SOURCE_FIELDS={"path","definition_ref"}
REQUIRED_RUNTIME=("default_qualification_plan.py","budget_v5.py","review_v5.py","routing_context_v5.py","routing_hook_v5.py",
                  "routing_context_delivery_v2.py","context_tool_surface.py","desktop_default_activation.py",
                  "routing_cards.py","qualification_study.py")
REQUIRED_ORDINARY_RUNTIME=('ordinary_routing_v5.py','ordinary_delegation_v5.py')
REQUIRED_HOOKS=("cp_hook.py","cp_context.py","review_context_reader.py")


def _absolute(value: Any) -> Path:
    if not isinstance(value,str) or not Path(value).is_absolute():
        fail("DEFAULT_ACTIVATION_PATH")
    return Path(value)


def validate_definition(value: Mapping[str,Any]) -> dict:
    extra={k for k in ('context_profile','ordinary_contract','qualification_plan','research_matrix') if k in value} if isinstance(value,dict) else set()
    if isinstance(value,dict) and value.get('schema_version')=='desktop-default-activation/3' and 'delivery_contract' in value:
        extra.add('delivery_contract')
    exact(value,DEFINITION_FIELDS|extra,"DEFAULT_ACTIVATION_FIELDS")
    if 'context_profile' in extra and value["context_profile"]!=CONTEXT_64K:
        fail("DEFAULT_ACTIVATION_CONTEXT_PROFILE")
    if 'ordinary_contract' in extra:
        from .ordinary_routing_v5 import CONTRACT
        if value['ordinary_contract']!=CONTRACT:fail('DEFAULT_ACTIVATION_ORDINARY_CONTRACT')
    if value["schema_version"] not in {"desktop-default-activation/1","desktop-default-activation/2","desktop-default-activation/3"} or value["policy_id"]!=POLICY_ID \
            or value["policy_digest"]!=policy_digest() or value["transport_mode"]!=MODE_V2 \
            or value["consumer_version"]!=("qualification-study/2" if value["schema_version"]=="desktop-default-activation/3" else "qualification-study/1"):
        fail("DEFAULT_ACTIVATION_VERSION")
    if value['schema_version']=='desktop-default-activation/3':
        from .notify_wire import CONTRACT as WIRE_CONTRACT
        if value.get('context_profile')!=CONTEXT_64K or value.get('delivery_contract')!=WIRE_CONTRACT:
            fail('DEFAULT_MATRIX_DELIVERY_REQUIRED')
        if 'research_matrix' not in extra or 'qualification_plan' not in extra:fail('DEFAULT_MATRIX_SOURCE_REQUIRED')
        matrix=exact(value['research_matrix'],{'source','publication'},'DEFAULT_MATRIX_FIELDS')
        for field in ('source','publication'):
            pointer=exact(matrix[field],{'path','sha256'},'DEFAULT_MATRIX_POINTER');_absolute(pointer['path']);sha(pointer['sha256'])
    elif 'research_matrix' in extra:fail('DEFAULT_MATRIX_VERSION_REQUIRED')
    if value["schema_version"] in {"desktop-default-activation/2","desktop-default-activation/3"}:
        if 'qualification_plan' not in extra:fail('DEFAULT_ACTIVATION_COMPLETE_PLAN_REQUIRED')
        pointer=exact(value['qualification_plan'],{'path','sha256'},'DEFAULT_ACTIVATION_QUALIFICATION_PLAN')
        _absolute(pointer['path']);sha(pointer['sha256'])
    elif 'qualification_plan' in extra:fail('DEFAULT_ACTIVATION_VERSION')
    identifier(value["activation_id"]);identity(value["identity"])
    assert_current_window(value,value["created_at"])
    scenarios=value["required_scenarios"]
    if not isinstance(scenarios,list) or not scenarios or len(scenarios)>100 or len(set(scenarios))!=len(scenarios):
        fail("DEFAULT_ACTIVATION_SCENARIOS")
    for scenario_ref in scenarios:sha(scenario_ref)
    cards=value["cards"]
    if not isinstance(cards,list) or (not cards and value["schema_version"]!="desktop-default-activation/3") or len(cards)>100 or value["schema_version"]=="desktop-default-activation/3" and cards:
        fail("DEFAULT_ACTIVATION_CARDS")
    for card in cards:
        exact(card,CARD_FIELDS,"DEFAULT_ACTIVATION_CARD_FIELDS")
        for name in ("bundle","experiment","publication"):_absolute(card[name])
        for name in ("bundle_ref","experiment_ref","publication_ref"):sha(card[name])
        integer(card["publication_revision"],"DEFAULT_ACTIVATION_PUBLICATION_REVISION",minimum=1)
        if not isinstance(card["trace_ledgers"],list) or not card["trace_ledgers"] or len(card["trace_ledgers"])>100:
            fail("DEFAULT_ACTIVATION_TRACE_SOURCES")
        for path in card["trace_ledgers"]:_absolute(path)
    installation=exact(value["installation"],INSTALLATION_FIELDS,"DEFAULT_ACTIVATION_INSTALLATION_FIELDS")
    pointer=exact(installation["manifest"],{"path","sha256"},"DEFAULT_ACTIVATION_MANIFEST")
    _absolute(pointer["path"]);sha(pointer["sha256"])
    executable=exact(installation["python"],{"path","sha256"},"DEFAULT_ACTIVATION_PYTHON")
    _absolute(executable["path"]);sha(executable["sha256"])
    roots=[_absolute(installation[key]) for key in ("source_root","managed_root","cache_root","enhancement_home")]
    if any(same_path(a,b) for i,a in enumerate(roots) for b in roots[i+1:]):
        fail("DEFAULT_ACTIVATION_DISTINCT_COPIES_REQUIRED")
    hooks=installation["required_hooks"]
    if not isinstance(hooks,list) or not hooks or len(hooks)>32:
        fail("DEFAULT_ACTIVATION_HOOKS_REQUIRED")
    for hook in hooks:
        exact(hook,{"event","matcher","command"},"DEFAULT_ACTIVATION_HOOK_FIELDS")
        if hook["event"] not in {"PreToolUse","PostToolUse","SubagentStart","SubagentStop"} \
                or not isinstance(hook["matcher"],str) or not isinstance(hook["command"],str) or not hook["command"]:
            fail("DEFAULT_ACTIVATION_HOOK_FIELDS")
    if {h["event"] for h in hooks}!={"PreToolUse","PostToolUse","SubagentStart","SubagentStop"} \
            or any(not any(h["event"]==event and h["matcher"]==".*" and "cp_context.py" in h["command"]
                       for h in hooks) for event in ("PreToolUse","PostToolUse")) \
            or any(not any(h["event"]==event and "cp_hook.py" in h["command"] for h in hooks)
                   for event in ("PreToolUse","PostToolUse","SubagentStart","SubagentStop")):
        fail("DEFAULT_ACTIVATION_HOOK_COVERAGE")
    return copy.deepcopy(dict(value))


def verify_root_card_sources(definition: Mapping[str,Any], sources: list[dict]) -> None:
    """中文：任务最多从项目级激活记录加载十个固定来源。
    
    English: A task loads at most ten pinned sources from the project-wide activation.
    """
    if definition['schema_version']=='desktop-default-activation/3':
        if sources!=[]:fail('DEFAULT_MATRIX_LEAF_SOURCE_DENIED')
        return
    if not isinstance(sources,list) or not sources or len(sources)>10:
        fail("DEFAULT_ACTIVATION_ROOT_SCOPE_MISMATCH")
    admitted={ref(source) for source in definition["cards"]}
    requested=[ref(source) for source in sources]
    if len(set(requested))!=len(requested) or not set(requested).issubset(admitted):
        fail("DEFAULT_ACTIVATION_ROOT_SCOPE_MISMATCH")


def expected_cells_role_names():
    from .routing_contract import policy
    return set(policy()['reviewer_roles'])


def _cards(definition: Mapping[str,Any], *, now: str, consumer_task_id: str) -> dict:
    from .default_qualification_plan import expected_cells,verify_plan,verify_confirmation
    if definition['schema_version']=='desktop-default-activation/3':
        from .research_publication import _file,verify_matrix_publication
        source=_file(definition['research_matrix']['source']);publication=_file(definition['research_matrix']['publication']);matrix=verify_matrix_publication(publication,source,now=now)
        if matrix['identity']!=definition['identity'] or set(matrix['qualification'])!=set(definition['required_scenarios']):fail('DEFAULT_MATRIX_IDENTITY_OR_SCOPE')
        manifest,_=read_document(Path(definition['installation']['manifest']['path']))
        if manifest['payload_digest']!=matrix['candidate_payload_digest']:fail('DEFAULT_MATRIX_PAYLOAD_CHANGED')
        checked=verify_plan(definition['qualification_plan'],definition,now=now)
        verify_confirmation(checked,matrix['experiments'],matrix['qualification'])
        return matrix['qualification']
    checked=verify_plan(definition['qualification_plan'],definition,now=now) if definition['schema_version']=='desktop-default-activation/2' else None
    qualified={};seen=set();covered=set();experiments=[]
    for source in definition["cards"]:
        bundle,_=read_document(Path(source["bundle"]))
        experiment,_=read_document(Path(source["experiment"]),maximum=8_388_608)
        if bundle.get("schema_version")!="routing-card-bundle/2" or ref(bundle)!=source["bundle_ref"] \
                or ref(experiment)!=source["experiment_ref"]:
            fail("DEFAULT_ACTIVATION_CARD_CHANGED")
        if definition.get("context_profile")==CONTEXT_64K and (
                experiment["scenario"]["context_bucket"]!="bounded-review-64k"
                or experiment["scenario"]["tools_profile"]!="desktop-context-reader-64k-v1"):
            fail("DEFAULT_ACTIVATION_CONTEXT_PROFILE")
        if experiment['scenario']['role'] not in expected_cells_role_names():
            fail('DEFAULT_ACTIVATION_REVIEWER_ROLE_REQUIRED')
        validate_bundle(bundle,experiment,now=now,trace_loader=_trace_loader(source["trace_ledgers"]))
        experiments.append(experiment)
        publication=load_publication(Path(source["publication"]),bundle=bundle,consumer_identity=definition["identity"],
            consumer_task_id=consumer_task_id,now=now,expected_revision=source["publication_revision"])
        if ref(publication)!=source["publication_ref"] or publication["scope"]["consumption"]!="project-bound-reuse":
            fail("DEFAULT_ACTIVATION_PUBLICATION_CHANGED")
        for card in bundle["qualification"]:
            key=(card["scenario_ref"],card["profile_id"])
            if key in seen:fail("DEFAULT_ACTIVATION_CARD_AMBIGUOUS")
            seen.add(key)
            if card["qualified"] and profile_spec(card["profile_id"])["generation"]=="6":
                qualified.setdefault(card["scenario_ref"],[]).append(card["profile_id"])
                if card["scenario_ref"] in definition["required_scenarios"]:
                    covered.add((experiment["scenario"]["role"],experiment["scenario"]["phase"]))
    if any(scope not in qualified for scope in definition["required_scenarios"]):
        fail("DEFAULT_ACTIVATION_QUALIFICATION_INCOMPLETE")
    if covered!=expected_cells():fail("DEFAULT_ACTIVATION_ROLE_PHASE_MATRIX_INCOMPLETE")
    if checked is not None:verify_confirmation(checked,experiments,qualified)
    return {scope:sorted(profiles) for scope,profiles in sorted(qualified.items())}


def _installation(definition: Mapping[str,Any], *, include_source: bool) -> dict:
    installed=definition["installation"]
    pointer=installed["manifest"]
    manifest_path=Path(pointer["path"])
    if "sha256:"+digest(bounded_bytes(manifest_path,1_048_576))!=pointer["sha256"]:
        fail("DEFAULT_ACTIVATION_MANIFEST_CHANGED")
    manifest=load_manifest(manifest_path)
    names={item["path"] for item in manifest["files"]}
    required={"runtime/cp_runtime/"+name for name in REQUIRED_RUNTIME}|{"hooks/"+name for name in REQUIRED_HOOKS}
    if definition['schema_version']=='desktop-default-activation/3':
        required.update('runtime/cp_runtime/'+name for name in ('research_documents.py','research_claim_scope.py','research_campaign.py','research_audit.py','research_negative.py','research_publication.py','notify_wire.py'))
    if definition.get('ordinary_contract'):
        required.update('runtime/cp_runtime/'+name for name in REQUIRED_ORDINARY_RUNTIME)
    if not required.issubset(names):
        fail("DEFAULT_ACTIVATION_PAYLOAD_INCOMPLETE")
    roots=("source_root","managed_root","cache_root") if include_source else ("managed_root","cache_root")
    for key in roots:
        verify_payload(Path(installed[key]),manifest,package="codex-cross-project-engineering-assistant")
    home=Path(installed["enhancement_home"])
    if not same_path(home,resolve_codex_home()):
        fail("DEFAULT_ACTIVATION_HOST_HOME")
    python=installed["python"]
    if "sha256:"+digest(bounded_bytes(Path(python["path"]),64*1024*1024))!=python["sha256"]:
        fail("DEFAULT_ACTIVATION_PYTHON_CHANGED")
    live={}
    for item in manifest["files"]:
        relative=item["path"]
        path=None
        if relative.startswith("runtime/cp_runtime/"):
            path=home/relative
        elif relative in {"hooks/"+name for name in REQUIRED_HOOKS}:
            path=home/"cp-assistant-hooks"/relative.split("/",1)[1]
        if path:
            observed=digest(bounded_bytes(path,64*1024*1024))
            if observed!=item["sha256"]:
                fail("DEFAULT_ACTIVATION_LIVE_FILE_CHANGED")
            live[str(path.resolve())]=observed
    hooks,_=read_document(home/"hooks.json")
    for expected in installed["required_hooks"]:
        groups=hooks.get("hooks",{}).get(expected["event"],[])
        if not any(group.get("matcher","")==expected["matcher"] and any(
            handler.get("type")=="command" and handler.get("command")==expected["command"]
            for handler in group.get("hooks",[])) for group in groups):
            fail("DEFAULT_ACTIVATION_HOOK_MISSING")
    return {"payload_digest":manifest["payload_digest"],"live_files_ref":ref(live),
            "required_hooks_ref":ref(installed["required_hooks"]),"python_ref":ref(python)}


def _read(source: Mapping[str,Any]) -> dict:
    exact(source,SOURCE_FIELDS,"DEFAULT_ACTIVATION_SOURCE")
    path=_absolute(source["path"]);sha(source["definition_ref"])
    state=read_json(path,verify=True,label="Desktop default activation")
    state.pop("integrity")
    exact(state,STATE_FIELDS,"DEFAULT_ACTIVATION_STATE_FIELDS")
    definition=validate_definition(state["definition"])
    if state["schema_version"]!="desktop-default-state/1" or state["definition_ref"]!=ref(definition) \
            or source["definition_ref"]!=state["definition_ref"] \
            or state["status"] not in {"PREPARED","INSTALLED_VERIFIED","ACTIVE","REVOKED","LEGACY_RESTORED"}:
        fail("DEFAULT_ACTIVATION_STATE_BINDING")
    if not isinstance(state["history"],list) or len(state["history"])>8:
        fail("DEFAULT_ACTIVATION_HISTORY")
    transitions={None:{"PREPARED"},"PREPARED":{"INSTALLED_VERIFIED","REVOKED"},
        "INSTALLED_VERIFIED":{"ACTIVE","REVOKED","LEGACY_RESTORED"},"ACTIVE":{"REVOKED","LEGACY_RESTORED"},
        "REVOKED":{"LEGACY_RESTORED"},"LEGACY_RESTORED":set()}
    previous=None
    for item in state["history"]:
        if not isinstance(item,dict) or item.get("action") not in transitions[previous]:
            fail("DEFAULT_ACTIVATION_HISTORY")
        previous=item["action"]
    if previous!=state["status"]:
        fail("DEFAULT_ACTIVATION_HISTORY")
    return state


def verify_active(source: Mapping[str,Any], *, expected_identity: Mapping[str,str], now: str,
                  consumer_task_id: str) -> dict:
    state=_read(source);definition=state["definition"]
    if state["status"]!="ACTIVE" or definition["identity"]!=dict(expected_identity):
        fail("DEFAULT_ACTIVATION_NOT_ACTIVE_OR_FOREIGN")
    assert_current_window(definition,now)
    installation=_installation(definition,include_source=False)
    if ref(installation)!=state["installation_ref"]:
        fail("DEFAULT_ACTIVATION_INSTALLATION_CHANGED")
    qualified=_cards(definition,now=now,consumer_task_id=consumer_task_id)
    return {"definition":definition,"qualified":qualified,"source":dict(source)}


def prepare(path: Path, definition: Mapping[str,Any], *, repo_path: Path, task_id: str, now: str) -> dict:
    definition=validate_definition(definition)
    if definition["schema_version"] not in {"desktop-default-activation/2","desktop-default-activation/3"}:fail("DEFAULT_ACTIVATION_COMPLETE_PLAN_REQUIRED")
    from .ordinary_routing_v5 import CONTRACT
    if definition.get('ordinary_contract')!=CONTRACT:fail('DEFAULT_ACTIVATION_ORDINARY_COMPAT_REQUIRED')
    require_external_state(path.resolve(),repo_path.resolve())
    require_external_state(Path(definition["installation"]["manifest"]["path"]).resolve(),repo_path.resolve())
    if stable_repo_fingerprint(str(repo_path))!=definition["identity"]["repo_fingerprint"]:
        fail("DEFAULT_ACTIVATION_REPOSITORY")
    _cards(definition,now=now,consumer_task_id=task_id)
    state={"schema_version":"desktop-default-state/1","definition":definition,"definition_ref":ref(definition),
           "status":"PREPARED","installation_ref":"","history":[{"action":"PREPARED","at":now}]}
    path.parent.mkdir(parents=True,exist_ok=True)
    with OwnerTokenLock(path,timeout=2):
        if path.exists():fail("DEFAULT_ACTIVATION_ALREADY_EXISTS")
        path.parent.mkdir(parents=True,exist_ok=True)
        atomic_write_json(path,state,seal=True)
    return {"path":str(path.resolve()),"definition_ref":state["definition_ref"]}


def verify_installation(source: Mapping[str,Any], *, repo_path: Path, now: str) -> dict:
    path=Path(source["path"])
    with OwnerTokenLock(path,timeout=2):
        state=_read(source)
        if stable_repo_fingerprint(str(repo_path))!=state["definition"]["identity"]["repo_fingerprint"]:
            fail("DEFAULT_ACTIVATION_REPOSITORY")
        if state["status"]!="PREPARED":fail("DEFAULT_ACTIVATION_PREPARED_REQUIRED")
        assert_current_window(state["definition"],now)
        installed=_installation(state["definition"],include_source=True)
        state.update(status="INSTALLED_VERIFIED",installation_ref=ref(installed))
        state["history"].append({"action":"INSTALLED_VERIFIED","at":now,"installation_ref":ref(installed)})
        atomic_write_json(path,state,seal=True)
    return installed


def approval_note(source: Mapping[str,Any]) -> str:
    return "desktop-default-activation:"+ref(dict(source))


def _approval_fingerprint(value):
    return ref({key:item for key,item in value.items()
                if key not in {'integrity','status','consumed_at','consumed_operation'}})


def activate(source: Mapping[str,Any], *, pointer_path: Path, approval_path: Path,
             repo_path: Path, task_id: str, now: str) -> dict:
    path=Path(source['path'])
    require_external_state(pointer_path.resolve(),repo_path.resolve())
    pointer_path.parent.mkdir(parents=True,exist_ok=True)
    intent_path=path.with_suffix('.activation-intent.json')
    with OwnerTokenLock(pointer_path,timeout=2),OwnerTokenLock(path,timeout=2),OwnerTokenLock(approval_path,timeout=2):
        state=_read(source);definition=state['definition']
        if definition['schema_version'] not in {'desktop-default-activation/2','desktop-default-activation/3'}:
            fail('DEFAULT_ACTIVATION_COMPLETE_PLAN_REQUIRED')
        if not same_path(pointer_path,pointer_for(definition['identity'])):
            fail('DEFAULT_ACTIVATION_POINTER_SCOPE')
        if stable_repo_fingerprint(str(repo_path))!=definition['identity']['repo_fingerprint']:
            fail('DEFAULT_ACTIVATION_REPOSITORY')
        if state['status'] not in {'INSTALLED_VERIFIED','ACTIVE'}:
            fail('DEFAULT_ACTIVATION_INSTALLATION_REQUIRED')
        assert_current_window(definition,now)
        if ref(_installation(definition,include_source=False))!=state['installation_ref']:
            fail('DEFAULT_ACTIVATION_INSTALLATION_CHANGED')
        _cards(definition,now=now,consumer_task_id=task_id)
        enrollment=pointer_path.with_suffix('.enrollment.json')
        enrolled={'schema_version':'desktop-default-enrollment/1','identity':definition['identity']}
        if enrollment.exists():
            old=read_json(enrollment,verify=True,label='Desktop default enrollment');old.pop('integrity')
            if old!=enrolled:fail('DEFAULT_ACTIVATION_ENROLLMENT_CONFLICT')
        pointer={'schema_version':'desktop-default-pointer/1','identity':definition['identity'],'source':dict(source)}
        current=None
        if pointer_path.exists():
            current=read_json(pointer_path,verify=True,label='Desktop default pointer');current.pop('integrity')
            exact(current,{'schema_version','identity','source'},'DEFAULT_ACTIVATION_POINTER_FIELDS')
            if current['schema_version']!='desktop-default-pointer/1' or current['identity']!=definition['identity']:
                fail('DEFAULT_ACTIVATION_POINTER_IDENTITY')
        baseline=repo_snapshot(repo_path)['sha256']
        approval=load_approval(approval_path)
        fingerprint=_approval_fingerprint(approval)
        core={'schema_version':'desktop-activation-intent/1','source_ref':ref(dict(source)),
              'identity':definition['identity'],'task_id':task_id,'baseline_sha256':baseline,
              'approval_path':str(approval_path.resolve()),'approval_fingerprint':fingerprint,
              'pointer_path':str(pointer_path.resolve())}
        intent=None
        if intent_path.exists():
            intent=read_json(intent_path,verify=True,label='Desktop activation intent');intent.pop('integrity')
            exact(intent,set(core)|{'prepared_at','previous_pointer_ref'},'DEFAULT_ACTIVATION_INTENT_FIELDS')
            if any(intent[key]!=item for key,item in core.items()):
                fail('DEFAULT_ACTIVATION_INTENT_CONFLICT')
            if current!=pointer and (ref(current) if current else None)!=intent['previous_pointer_ref']:
                fail('DEFAULT_ACTIVATION_POINTER_COMMIT_CONFLICT')
        if approval.get('one_time') is not True or approval.get('note')!=approval_note(source):
            fail('DEFAULT_ACTIVATION_APPROVAL_REQUIRED')
        if approval.get('status')=='active':
            if state['status']!='INSTALLED_VERIFIED' or not check_approval(approval_path,
                    definition['identity']['project_id'],task_id,'make-effective','local',baseline).valid:
                fail('DEFAULT_ACTIVATION_APPROVAL_REQUIRED')
            if intent is None:
                intent={**core,'prepared_at':now,'previous_pointer_ref':ref(current) if current else None}
                atomic_write_json(intent_path,intent,seal=True)
            if not enrollment.exists():atomic_write_json(enrollment,enrolled,seal=True)
            consume_approval(approval_path,definition['identity']['project_id'],task_id,'make-effective','local',baseline)
        elif approval.get('status')=='consumed':
            if (intent is None or approval.get('project_id')!=definition['identity']['project_id']
                    or approval.get('task_id')!=task_id or approval.get('baseline_sha256')!=baseline
                    or approval.get('environment')!='local' or approval.get('consumed_operation')!='make-effective'
                    or 'make-effective' not in approval.get('operations',[]) or not enrollment.exists()
                    or not parse_iso(approval['issued_at'])<=parse_iso(approval['consumed_at'])<parse_iso(approval['expires_at'])
                    or parse_iso(approval['consumed_at'])<parse_iso(intent['prepared_at'])):
                fail('DEFAULT_ACTIVATION_APPROVAL_REQUIRED')
        else:
            fail('DEFAULT_ACTIVATION_APPROVAL_REQUIRED')
        if state['status']=='INSTALLED_VERIFIED':
            state['status']='ACTIVE'
            state['history'].append({'action':'ACTIVE','at':now,'approval_ref':fingerprint,'intent_ref':ref(intent)})
            atomic_write_json(path,state,seal=True)
        elif state['history'][-1].get('approval_ref')!=fingerprint or state['history'][-1].get('intent_ref')!=ref(intent):
            fail('DEFAULT_ACTIVATION_INTENT_CONFLICT')
        if current!=pointer:atomic_write_json(pointer_path,pointer,seal=True)
    return pointer


def revoke(source: Mapping[str,Any], *, repo_path: Path, reason_ref: str, now: str) -> dict:
    sha(reason_ref)
    path=Path(source["path"])
    with OwnerTokenLock(path,timeout=2):
        state=_read(source)
        if stable_repo_fingerprint(str(repo_path))!=state["definition"]["identity"]["repo_fingerprint"]:
            fail("DEFAULT_ACTIVATION_REPOSITORY")
        if state["status"] in {"REVOKED","LEGACY_RESTORED"}:return state
        state["status"]="REVOKED"
        state["history"].append({"action":"REVOKED","at":now,"reason_ref":reason_ref})
        atomic_write_json(path,state,seal=True)
    return state


def resolve_default(pointer_path: Path, *, expected_identity: Mapping[str,str], task_id: str, now: str) -> dict:
    from .dispatch_policy import CURRENT_POLICY_ID, policy_digest as legacy_digest
    enrollment=pointer_path.with_suffix(".enrollment.json")
    if not pointer_path.exists():
        if enrollment.exists():fail("DEFAULT_ACTIVATION_POINTER_MISSING")
        return {"policy_id":CURRENT_POLICY_ID,"policy_digest":legacy_digest(),"selection_mode":"luna-first-evidence-score"}
    enrolled=read_json(enrollment,verify=True,label="Desktop default enrollment")
    enrolled.pop("integrity")
    if enrolled!={"schema_version":"desktop-default-enrollment/1","identity":dict(expected_identity)}:
        fail("DEFAULT_ACTIVATION_ENROLLMENT_CONFLICT")
    pointer=read_json(pointer_path,verify=True,label="Desktop default pointer")
    pointer.pop("integrity")
    exact(pointer,{"schema_version","identity","source"},"DEFAULT_ACTIVATION_POINTER_FIELDS")
    if pointer["schema_version"]!="desktop-default-pointer/1" or pointer["identity"]!=dict(expected_identity):
        fail("DEFAULT_ACTIVATION_POINTER_IDENTITY")
    restored=_read(pointer["source"])
    if restored["definition"]["identity"]!=dict(expected_identity):
        fail("DEFAULT_ACTIVATION_NOT_ACTIVE_OR_FOREIGN")
    if restored["status"]=="LEGACY_RESTORED":
        return {"policy_id":CURRENT_POLICY_ID,"policy_digest":legacy_digest(),"selection_mode":"luna-first-evidence-score",
                "explicit_restore_ref":ref(restored["history"][-1])}
    active=verify_active(pointer["source"],expected_identity=expected_identity,now=now,consumer_task_id=task_id)
    return {"policy_id":POLICY_ID,"policy_digest":policy_digest(),"selection_mode":"quality-gain-routing-v1",
            "desktop_default_activation":active["source"]}


def pointer_for(declared_identity: Mapping[str,str]) -> Path:
    return resolve_codex_home()/"cp-assistant"/"model-defaults"/(ref(identity(dict(declared_identity)))[7:]+".json")


def restore_legacy(source: Mapping[str,Any], *, approval_path: Path, repo_path: Path,
                   task_id: str, reason_ref: str, now: str) -> dict:
    """中文：显式回退仍保留登记、激活、资格和消耗记录。
    
    English: Explicit rollback; keep enrollment, activation, qualifications and spending.
    """
    sha(reason_ref)
    state=_read(source)
    pointer_path=pointer_for(state["definition"]["identity"])
    path=Path(source["path"])
    with OwnerTokenLock(pointer_path,timeout=2),OwnerTokenLock(path,timeout=2),OwnerTokenLock(approval_path,timeout=2):
        state=_read(source);definition=state["definition"]
        if stable_repo_fingerprint(str(repo_path))!=definition["identity"]["repo_fingerprint"]:
            fail("DEFAULT_ACTIVATION_REPOSITORY")
        missing_pointer=not pointer_path.exists()
        if missing_pointer:
            enrollment=read_json(pointer_path.with_suffix('.enrollment.json'),verify=True,label='Desktop default enrollment')
            enrollment.pop('integrity')
            if enrollment!={'schema_version':'desktop-default-enrollment/1','identity':definition['identity']}:
                fail('DEFAULT_ACTIVATION_ENROLLMENT_CONFLICT')
            if state['status'] not in {'INSTALLED_VERIFIED','ACTIVE','REVOKED','LEGACY_RESTORED'}:
                fail('DEFAULT_ACTIVATION_ROLLBACK_STATE')
        else:
            pointer=read_json(pointer_path,verify=True,label="Desktop default pointer")
            if pointer.get("source")!=dict(source) or pointer.get("identity")!=definition["identity"]:
                fail("DEFAULT_ACTIVATION_NOT_CURRENT")
            if state["status"] not in {"ACTIVE","REVOKED","LEGACY_RESTORED"}:
                fail("DEFAULT_ACTIVATION_ROLLBACK_STATE")
        baseline=repo_snapshot(repo_path)["sha256"]
        approval=load_approval(approval_path)
        note="desktop-default-restore-legacy:"+ref({"source":dict(source),"reason_ref":reason_ref})
        if state['status']=='LEGACY_RESTORED':
            last=state['history'][-1]
            if (approval.get('status')!='consumed' or approval.get('one_time') is not True
                    or approval.get('note')!=note or approval.get('project_id')!=definition['identity']['project_id']
                    or approval.get('task_id')!=task_id or approval.get('baseline_sha256')!=baseline
                    or approval.get('environment')!='local' or approval.get('consumed_operation')!='make-effective'
                    or last.get('reason_ref')!=reason_ref or last.get('approval_ref')!=_approval_fingerprint(approval)):
                fail('DEFAULT_ACTIVATION_APPROVAL_REQUIRED')
            if missing_pointer:
                atomic_write_json(pointer_path,{'schema_version':'desktop-default-pointer/1',
                    'identity':definition['identity'],'source':dict(source)},seal=True)
            return state
        if approval.get("one_time") is not True or approval.get("note")!=note \
                or not check_approval(approval_path,definition["identity"]["project_id"],task_id,
                                      "make-effective","local",baseline).valid:
            fail("DEFAULT_ACTIVATION_APPROVAL_REQUIRED")
        consume_approval(approval_path,definition["identity"]["project_id"],task_id,"make-effective","local",baseline)
        state["status"]="LEGACY_RESTORED"
        state["history"].append({"action":"LEGACY_RESTORED","at":now,"reason_ref":reason_ref,"approval_ref":_approval_fingerprint(approval)})
        atomic_write_json(path,state,seal=True)
        if missing_pointer:
            atomic_write_json(pointer_path,{'schema_version':'desktop-default-pointer/1',
                'identity':definition['identity'],'source':dict(source)},seal=True)
    return state
