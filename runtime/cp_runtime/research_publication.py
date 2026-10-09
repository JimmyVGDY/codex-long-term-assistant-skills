"""中文：一次决定完整必需矩阵；叶子结果仍仅供审计。

English: One all-required matrix decision; leaves remain audit-only.
"""
import copy
from pathlib import Path
from .routing_contract import exact,fail,ref,sha,read_document
from .routing_context_contract import safe_file
from .research_documents import read_manifest
from .research_audit import audit_campaign
def _file(pointer):
    exact(pointer,{'path','sha256'},'RESEARCH_PUBLICATION_SOURCE');sha(pointer['sha256']);value,digest=read_document(safe_file(Path(pointer['path'])),maximum=8388608)
    if digest!=pointer['sha256']:fail('RESEARCH_PUBLICATION_SOURCE_CHANGED')
    return value
def read_audit_source(source,*,now):
    exact(source,{'manifest','trials','audit_ref'},'RESEARCH_CAMPAIGN_AUDIT_SOURCE');manifest=_file(source['manifest']);trials=_file(source['trials']);report,reports,sources=audit_campaign(manifest,trials,now=now)
    if ref(report)!=source['audit_ref']:fail('RESEARCH_CAMPAIGN_AUDIT_CHANGED')
    return manifest,trials,report,reports,sources
def qualify_matrix(source,*,now):
    exact(source,{'schema_version','confirmation','development'},'RESEARCH_MATRIX_SOURCE')
    if source['schema_version']!='research-matrix-source/1':fail('RESEARCH_MATRIX_SOURCE_VERSION')
    manifest,trials,audit,reports,sources=read_audit_source(source['confirmation'],now=now);campaign,plans,envelopes,bindings=read_manifest(manifest);scope=campaign['comparison_scope']
    development,_,dev_audit,_,_=read_audit_source(source['development'],now=now);dev_campaign,_,_,dev_bindings=read_manifest(development)
    if scope['stage']!='CONFIRMATION' or dev_campaign['comparison_scope']['stage']!='DEVELOPMENT_SCREEN' or not dev_audit['complete'] or not audit['complete']:fail('RESEARCH_MATRIX_EXECUTION_INCOMPLETE')
    from .research_documents import read_file
    if read_file(scope['development_manifest'])!=development:fail('RESEARCH_MATRIX_DEVELOPMENT_CHANGED')
    from .common import parse_iso
    from . import budget_v5 as budget
    if any(parse_iso(budget._read_events(Path(b['ledger_path']))[-1]['recorded_at'])>parse_iso(campaign['created_at']) for b in dev_bindings):fail('RESEARCH_CONFIRMATION_BEFORE_DEVELOPMENT_CLOSED')
    from .qualification_study import bind_evaluation
    from .routing_evaluation_v5 import assemble_experiment
    from .routing_cards import derived_cards
    experiments=[];qualification={};gains=[];costs=[];qualified_rows=[]
    for plan,envelope,trial_sources,report,trial_pointer in zip(plans,envelopes,sources,reports,trials['studies']):
        study_pointer=next(p for p in manifest['study_envelopes'] if p['canonical_ref']==ref(envelope))
        # 中文：资格来源是后代记录，不改写祖先。
        # English: Qualification source is a descendant; ancestors are never rewritten.
        from .routing_evaluation_v4 import file_reference
        qualified_source={'schema_version':'study-qualification-source/2','study':{'path':study_pointer['path'],'sha256':'sha256:'+study_pointer['bytes_sha256']},'trials':trial_pointer['trials'],'campaign':source['confirmation']['manifest'],'audit_ref':ref(report)}
        from .qualification_study import _independence_evidence
        reviewed=_independence_evidence(plan)
        for e in plan['evaluations']:
            frozen=bind_evaluation(envelope,e['protocol_ref']);experiment=assemble_experiment(frozen,trial_sources,experiment_id='matrix-'+e['protocol_ref'][7:31],issuer_task_id=plan['independence']['reviewed_by'][7:],issuer_baseline=reviewed['baseline']['sha256'],qualification_source=qualified_source)
            rows,leaf_gains=derived_cards(experiment);cell=next(c for c in scope['cells'] if c['protocol_ref']==e['protocol_ref']);selected=cell['candidate_profile']
            if not any(r['profile_id']==selected and r['scenario_ref']==cell['scenario_ref'] and r['qualified'] for r in rows):fail('RESEARCH_REQUIRED_CELL_NOT_QUALIFIED')
            qualification[cell['scenario_ref']]=[selected];qualified_rows.extend(r for r in rows if r['profile_id']==selected);experiments.append(experiment);gains.extend(leaf_gains);costs.extend(frozen['costs'])
    if len(experiments)!=21 or len(qualification)!=21:fail('RESEARCH_MATRIX_MISSING_CELL')
    return {'schema_version':'research-matrix-qualification/1','source_ref':ref(source),'campaign_ref':ref(campaign),'campaign_audit_ref':ref(audit),'development_audit_ref':ref(dev_audit),'identity':campaign['identity'],'candidate_payload_digest':campaign['candidate_payload_digest'],'claim':'ALL_REQUIRED_NO_SIMULTANEOUS_CI','qualified':True,'global_simultaneous_ci_claim':False,'experiments':experiments,'qualification':qualification,'qualified_rows':qualified_rows,'gains':gains,'costs':costs}
def production_snapshot(definition,state,request,*,now,cwd):
    from .common import repo_snapshot
    from .routing_contract import HOST_SURFACE,assert_current_window,policy_digest
    from .budget_v5 import snapshot_budget,validate_sources
    from .routing_context_v4 import _requirement_evidence
    from .routing_context_contract import policy_request
    if definition['schema_version']!='desktop-default-activation/3' or state['execution_mode']!='PRODUCTION' or state['sources']['card_sets']:fail('RESEARCH_MATRIX_ROOT_SOURCE')
    if repo_snapshot(Path(cwd))['sha256']!=request['baseline_sha256']:fail('RESEARCH_MATRIX_ROOT_BASELINE')
    sources=validate_sources(state['sources']);capability,_=read_document(safe_file(Path(sources['capability'])))
    if capability.get('host_surface')!=HOST_SURFACE or capability.get('root_session_ref')!=state['root_binding']['host_session_ref']:fail('RESEARCH_MATRIX_CAPABILITY_ROOT')
    assert_current_window(capability,now)
    source=_file(definition['research_matrix']['source']);matrix=verify_matrix_publication(_file(definition['research_matrix']['publication']),source,now=now)
    evidence=_requirement_evidence(state,policy_request(request),evaluation=None)
    if evidence!=request['evidence']:fail('RESEARCH_MATRIX_REQUIREMENT_EVIDENCE')
    cards={'schema_version':'verified-card-set/1','identity':matrix['identity'],'origin':'published','bundle_refs':[ref(matrix)],'publication_refs':[ref(_file(definition['research_matrix']['publication']))],'qualification':matrix['qualified_rows'],'gains':matrix['gains'],'costs':matrix['costs']}
    return {'schema_version':'routing-input/1','identity':matrix['identity'],'policy_digest':policy_digest(),'execution_mode':'PRODUCTION','cards':cards,'capability':capability,'phase_plan':copy.deepcopy(state['phase_plan']),'budget':snapshot_budget(state),'now':now}
def _publication_authority(value,source):
    from .approval import load_approval
    from .research_seed import fingerprint
    exact(value,{'schema_version','matrix_ref','source_ref','identity','candidate_payload_digest','claim','authority'},'RESEARCH_MATRIX_PUBLICATION')
    auth=exact(value['authority'],{'approval','approval_fingerprint','intent','intent_ref','consumed_at'},'RESEARCH_MATRIX_PUBLICATION_AUTHORITY')
    approval=load_approval(Path(auth['approval']));intent,_=read_document(safe_file(Path(auth['intent'])))
    exact(intent,{'schema_version','base','approval','approval_fingerprint','publication_path','task_id','baseline_sha256'},'RESEARCH_PUBLICATION_INTENT_FIELDS')
    campaign=read_manifest(_file(source['confirmation']['manifest']))[0]
    if intent['schema_version']!='research-matrix-publication-intent/1' or value['schema_version']!='research-matrix-publication/1' or value['source_ref']!=ref(source) or approval.get('one_time') is not True or approval.get('status')!='consumed' or approval.get('environment')!='local' or 'make-effective' not in approval.get('operations',[]) or approval.get('project_id')!=value['identity']['project_id'] or campaign['identity']!=value['identity'] or approval.get('task_id')!=campaign['stage_id'] or intent['task_id']!=campaign['stage_id'] or approval.get('baseline_sha256')!=intent['baseline_sha256'] or not auth['consumed_at']:fail('RESEARCH_MATRIX_PUBLICATION_SCOPE_MISMATCH')
    if ref(intent)!=auth['intent_ref'] or intent['base']!={k:v for k,v in value.items() if k!='authority'} or intent['approval']!=auth['approval'] or intent['approval_fingerprint']!=auth['approval_fingerprint'] or fingerprint(approval)!=auth['approval_fingerprint'] or approval.get('consumed_operation')!='make-effective' or approval.get('consumed_at')!=auth['consumed_at'] or approval.get('status')=='revoked' or approval.get('note')!='research-matrix-publication:'+ref({'matrix_ref':value['matrix_ref'],'source_ref':value['source_ref']}):fail('RESEARCH_MATRIX_PUBLICATION_UNAUTHORIZED')
    return approval,intent


def verify_matrix_publication(value,source,*,now):
    _publication_authority(value,source);matrix=qualify_matrix(source,now=now)
    expected={'schema_version':'research-matrix-publication/1','matrix_ref':ref(matrix),'source_ref':ref(source),'identity':matrix['identity'],'candidate_payload_digest':matrix['candidate_payload_digest'],'claim':matrix['claim']}
    if {k:v for k,v in value.items() if k!='authority'}!=expected:fail('RESEARCH_MATRIX_PUBLICATION_CHANGED')
    return matrix


def publish_matrix(path,source,*,approval_path,repo_path,now):
    from .approval import load_approval,consume_approval,check_approval
    from .common import repo_snapshot,require_external_state,atomic_write_json
    from .event_v2 import OwnerTokenLock,stable_repo_fingerprint
    from .research_seed import fingerprint,_immutable
    path=Path(path);approval_path=Path(approval_path);intent_path=path.with_suffix('.publication-intent.json');require_external_state(path,Path(repo_path));path.parent.mkdir(parents=True,exist_ok=True)
    with OwnerTokenLock(path,timeout=2),OwnerTokenLock(approval_path,timeout=2):
        approval=load_approval(approval_path)
        if intent_path.exists():
            intent=read_document(safe_file(intent_path))[0]
            exact(intent,{'schema_version','base','approval','approval_fingerprint','publication_path','task_id','baseline_sha256'},'RESEARCH_PUBLICATION_INTENT_FIELDS')
            if intent['schema_version']!='research-matrix-publication-intent/1':fail('RESEARCH_PUBLICATION_INTENT_VERSION')
            if intent['base']['source_ref']!=ref(source) or intent['approval']!=str(approval_path) or intent['approval_fingerprint']!=fingerprint(approval) or intent['publication_path']!=str(path):fail('RESEARCH_PUBLICATION_INTENT_CHANGED')
        else:
            matrix=qualify_matrix(source,now=now);manifest=_file(source['confirmation']['manifest']);campaign=read_manifest(manifest)[0];snapshot=repo_snapshot(Path(repo_path))
            if matrix['identity']['repo_fingerprint']!=stable_repo_fingerprint(str(repo_path)) or approval.get('one_time') is not True or approval.get('note')!='research-matrix-publication:'+ref({'matrix_ref':ref(matrix),'source_ref':ref(source)}):fail('RESEARCH_MATRIX_PUBLICATION_APPROVAL_SCOPE')
            checked=check_approval(approval_path,matrix['identity']['project_id'],campaign['stage_id'],'make-effective','local',snapshot['sha256'])
            if not checked.valid:fail('RESEARCH_MATRIX_PUBLICATION_APPROVAL_REQUIRED')
            base={'schema_version':'research-matrix-publication/1','matrix_ref':ref(matrix),'source_ref':ref(source),'identity':matrix['identity'],'candidate_payload_digest':matrix['candidate_payload_digest'],'claim':matrix['claim']}
            intent={'schema_version':'research-matrix-publication-intent/1','base':base,'approval':str(approval_path),'approval_fingerprint':fingerprint(approval),'publication_path':str(path),'task_id':campaign['stage_id'],'baseline_sha256':snapshot['sha256']};_immutable(intent_path,intent)
        current=repo_snapshot(Path(repo_path))
        if current['sha256']!=intent['baseline_sha256'] or stable_repo_fingerprint(str(repo_path))!=intent['base']['identity']['repo_fingerprint']:
            fail('RESEARCH_PUBLICATION_BASELINE_STALE')
        consumed=approval.get('consumed_operation')=='make-effective' and bool(approval.get('consumed_at'))
        if not consumed:
            # 中文：原意图过期或被撤销后，不能单独授权新的发布。
            # English: The original intent alone cannot authorize a new publication after expiry/revocation.
            matrix=qualify_matrix(source,now=now)
            if ref(matrix)!=intent['base']['matrix_ref']:fail('RESEARCH_PUBLICATION_MATRIX_DRIFT')
            approval=consume_approval(approval_path,intent['base']['identity']['project_id'],intent['task_id'],'make-effective','local',intent['baseline_sha256'])
        value={**intent['base'],'authority':{'approval':str(approval_path),'approval_fingerprint':intent['approval_fingerprint'],'intent':str(intent_path),'intent_ref':ref(intent),'consumed_at':approval['consumed_at']}}
        if path.exists():
            if read_document(safe_file(path))[0]!=value:fail('RESEARCH_MATRIX_PUBLICATION_IMMUTABLE')
            _publication_authority(value,source);return value
        _publication_authority(value,source);atomic_write_json(path,value);return value
