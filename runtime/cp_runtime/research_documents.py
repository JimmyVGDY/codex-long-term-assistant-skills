"""中文：验证完整无环研究文档，不因此授予执行权限。

English: Complete acyclic research documents; validation grants no execution authority.
"""
import copy,hashlib
from pathlib import Path
from .routing_contract import exact,fail,ref,sha,hex_digest,identifier,identity,policy_digest,vector,add_vectors,fits,assert_current_window,read_document
from .routing_context_contract import safe_file,bounded_bytes
from .research_seed import _state_directory
FILE={'path','canonical_ref','bytes_sha256'}
SEGMENT={'segment_id','root_task_id','ledger_path','host_session_ref','trial_refs','capacity'}
BINDING={'schema_version','campaign_plan_ref','study_plan_ref'}|SEGMENT
CAMPAIGN={'schema_version','campaign_id','stage_id','identity','policy_digest','candidate_payload_digest','host_session_ref','runtime_ref','created_at','expires_at','predecessor','studies','capacity','comparison_scope','retry_policy','historical_evidence_refs'}
def read_file(pointer):
    exact(pointer,FILE,'RESEARCH_FILE_FIELDS');sha(pointer['canonical_ref']);hex_digest(pointer['bytes_sha256'])
    path=safe_file(Path(pointer['path']));raw=bounded_bytes(path,1048576)
    value,digest=read_document(path)
    if digest!='sha256:'+hashlib.sha256(raw).hexdigest() or hashlib.sha256(raw).hexdigest()!=pointer['bytes_sha256'] or ref(value)!=pointer['canonical_ref']:fail('RESEARCH_FILE_CHANGED')
    return value
def validate_study_plan(value):
    from .qualification_study import _validate_structure
    plan=_validate_structure(value,version='research-study-plan/1',segment_fields=SEGMENT,same_host=True,root_tasks=True)
    for segment in plan['segments']:_state_directory(Path(segment['ledger_path']))
    return plan
def validate_campaign(value):
    exact(value,CAMPAIGN,'RESEARCH_CAMPAIGN_FIELDS')
    if value['schema_version']!='research-campaign-plan/1' or value['policy_digest']!=policy_digest():fail('RESEARCH_CAMPAIGN_VERSION')
    identifier(value['campaign_id']);identifier(value['stage_id']);identity(value['identity']);hex_digest(value['candidate_payload_digest']);sha(value['host_session_ref']);sha(value['runtime_ref']);assert_current_window(value,value['created_at']);vector(value['capacity'])
    predecessor=exact(value['predecessor'],{'registry_path','registry_bytes_sha256','ledger_path','final_record_hash','closed_outcome'},'RESEARCH_PREDECESSOR_FIELDS')
    _state_directory(Path(predecessor['registry_path']));_state_directory(Path(predecessor['ledger_path']));hex_digest(predecessor['registry_bytes_sha256']);hex_digest(predecessor['final_record_hash'])
    if predecessor['closed_outcome'] not in {'PASS','BLOCKED','FAILED','CANCELLED','PARTIAL','UNKNOWN'}:fail('RESEARCH_PREDECESSOR_OUTCOME')
    if value['retry_policy']!='NO_CREATED_TRIAL_REPLAY':fail('RESEARCH_RETRY_POLICY')
    if not isinstance(value['studies'],list) or not 1<=len(value['studies'])<=100:fail('RESEARCH_CAMPAIGN_STUDIES')
    ids=set();refs=set()
    for row in value['studies']:
        exact(row,{'study_id','study_plan_ref'},'RESEARCH_CAMPAIGN_STUDY_FIELDS');identifier(row['study_id']);sha(row['study_plan_ref'])
        if row['study_id'] in ids or row['study_plan_ref'] in refs:fail('RESEARCH_CAMPAIGN_STUDY_REUSED')
        ids.add(row['study_id']);refs.add(row['study_plan_ref'])
    scope=value['comparison_scope']
    if not isinstance(scope,dict) or scope.get('schema_version')!='research-comparison-scope/1':fail('RESEARCH_COMPARISON_SCOPE_REQUIRED')
    if not isinstance(value['historical_evidence_refs'],list) or len(value['historical_evidence_refs'])>1000 or len(set(value['historical_evidence_refs']))!=len(value['historical_evidence_refs']):fail('RESEARCH_HISTORY_REFS')
    for item in value['historical_evidence_refs']:sha(item)
    return copy.deepcopy(value)
def _binding_against_validated(value,study,campaign,study_ref,campaign_ref):
    exact(value,BINDING,'RESEARCH_BINDING_FIELDS')
    if value['schema_version']!='research-segment-binding/1':fail('RESEARCH_BINDING_VERSION')
    sha(value['campaign_plan_ref']);sha(value['study_plan_ref'])
    if value['study_plan_ref']!=study_ref:fail('RESEARCH_BINDING_STUDY_CHANGED')
    segment=next((s for s in study['segments'] if s['segment_id']==value['segment_id']),None)
    if segment is None or any(value[k]!=segment[k] for k in SEGMENT):fail('RESEARCH_BINDING_ALLOCATION_CHANGED')
    _state_directory(Path(value['ledger_path']))
    if campaign is not None:
        if value['campaign_plan_ref']!=campaign_ref or study['identity']!=campaign['identity'] or value['host_session_ref']!=campaign['host_session_ref'] or {'study_id':study['study_id'],'study_plan_ref':study_ref} not in campaign['studies']:fail('RESEARCH_BINDING_CAMPAIGN_CHANGED')
    return copy.deepcopy(value)
def validate_binding(value,study,campaign=None):
    study=validate_study_plan(study)
    campaign=validate_campaign(campaign) if campaign is not None else None
    return _binding_against_validated(value,study,campaign,ref(study),ref(campaign) if campaign is not None else None)
def read_study_envelope(value,campaign=None):
    exact(value,{'schema_version','study_plan','segment_bindings'},'RESEARCH_STUDY_ENVELOPE_FIELDS')
    if value['schema_version']!='qualification-study/2':fail('RESEARCH_STUDY_ENVELOPE_VERSION')
    study=validate_study_plan(read_file(value['study_plan']));pointers=value['segment_bindings']
    if not isinstance(pointers,list) or len(pointers)!=len(study['segments']):fail('RESEARCH_STUDY_BINDING_COVERAGE')
    campaign=validate_campaign(campaign) if campaign is not None else None
    study_ref=ref(study);campaign_ref=ref(campaign) if campaign is not None else None
    bindings=[_binding_against_validated(read_file(p),study,campaign,study_ref,campaign_ref) for p in pointers]
    if [b['segment_id'] for b in bindings]!=[s['segment_id'] for s in study['segments']] or len({b['campaign_plan_ref'] for b in bindings})!=1:fail('RESEARCH_STUDY_BINDING_ORDER')
    return study,bindings
def read_manifest(value,*,complete_scope=True):
    exact(value,{'schema_version','campaign_plan','study_envelopes'},'RESEARCH_MANIFEST_FIELDS')
    if value['schema_version']!='research-campaign-manifest/1':fail('RESEARCH_MANIFEST_VERSION')
    campaign=validate_campaign(read_file(value['campaign_plan']));pointers=value['study_envelopes']
    if not isinstance(pointers,list) or len(pointers)!=len(campaign['studies']):fail('RESEARCH_MANIFEST_STUDIES')
    envelopes=[];plans=[];all_bindings=[];paths=set();tasks=set();trials=set()
    for p,row in zip(pointers,campaign['studies']):
        envelope=read_file(p);study,bindings=read_study_envelope(envelope,campaign)
        if row!={'study_id':study['study_id'],'study_plan_ref':ref(study)}:fail('RESEARCH_MANIFEST_STUDY_ORDER')
        envelopes.append(envelope);plans.append(study)
        for b in bindings:
            path=str(Path(b['ledger_path']).resolve()).casefold()
            if path in paths or b['root_task_id'] in tasks or trials.intersection(b['trial_refs']):fail('RESEARCH_CAMPAIGN_ALLOCATION_REUSED')
            paths.add(path);tasks.add(b['root_task_id']);trials.update(b['trial_refs']);all_bindings.append(b)
    if not fits(add_vectors(*(s['capacity'] for s in plans)),campaign['capacity']):fail('RESEARCH_CAMPAIGN_CAPACITY')
    from .research_claim_scope import validate,check_independent_confirmation
    validate(campaign['comparison_scope'],[e for p in plans for e in p['evaluations']],complete=complete_scope)
    if complete_scope:check_independent_confirmation(campaign['comparison_scope'],plans)
    return campaign,plans,envelopes,all_bindings
