"""中文：研究的来源与授权分开处理；文档图本身不授予执行权限。

English: Campaign provenance and authority: a document graph never grants execution.
"""
from pathlib import Path
from .routing_contract import exact,fail,ref,sha,read_document
from .research_documents import read_file,read_manifest,FILE
from .approval import load_approval
from .research_seed import fingerprint,_directory,_read
from .path_identity import same_path
from .common import utc_now,parse_iso,require_external_state,repo_snapshot,atomic_write_json
from .event_v2 import OwnerTokenLock,stable_repo_fingerprint
from . import budget_v5 as budget
LEGACY_CONTRACT='desktop-research-campaign/1'
CONTRACT='desktop-research-campaign/2'
SUPPORTED_CONTRACTS={LEGACY_CONTRACT,CONTRACT}
SOURCE={'path','definition_ref'}
def definition(source):
    exact(source,SOURCE,'RESEARCH_SOURCE_FIELDS');sha(source['definition_ref'])
    document=_read(Path(source['path']))
    exact(document,{'schema_version','manifest','grant','installation'},'RESEARCH_DEFINITION_FIELDS')
    if document['schema_version']!='research-campaign-definition/1' or ref(document)!=source['definition_ref']:fail('RESEARCH_DEFINITION_CHANGED')
    manifest=read_file(document['manifest']);campaign,plans,envelopes,bindings=read_manifest(manifest)
    grant=read_file(document['grant'])
    fields={'schema_version','grant_id','campaign_plan_ref','campaign_manifest_ref','identity','host_session_ref','stage_id','scope','capacity','approved_at','expires_at','approval_source'}
    exact(grant,fields,'RESEARCH_STAGE_GRANT_FIELDS')
    if grant['schema_version']!='research-stage-grant/1' or grant['campaign_plan_ref']!=ref(campaign) or grant['campaign_manifest_ref']!=ref(manifest) or grant['identity']!=campaign['identity'] or grant['host_session_ref']!=campaign['host_session_ref'] or grant['stage_id']!=campaign['stage_id'] or grant['scope']!=campaign['comparison_scope']['stage'] or grant['capacity']!=campaign['capacity'] or grant['expires_at']!=campaign['expires_at']:fail('RESEARCH_STAGE_GRANT_CHANGED')
    approval_source=exact(grant['approval_source'],{'path','immutable_fingerprint'},'RESEARCH_APPROVAL_SOURCE')
    approval=load_approval(Path(approval_source['path']))
    if fingerprint(approval)!=approval_source['immutable_fingerprint']:fail('RESEARCH_APPROVAL_CHANGED')
    return document,manifest,campaign,plans,envelopes,bindings,grant,approval
def approval_scope(campaign,manifest):
    return 'research-stage:'+ref({'campaign_plan_ref':ref(campaign),'campaign_manifest_ref':ref(manifest),'stage_id':campaign['stage_id']})
def _admission(source,p,m,g,a,cwd,intent):
    return {'schema_version':'research-stage-admission/1','definition_ref':source['definition_ref'],'grant_ref':ref(g),'plan_ref':ref(p),'manifest_ref':ref(m),'approval_fingerprint':fingerprint(a),'repo_path':str(Path(cwd).absolute()),'authority_consumed_at':a['consumed_at'],'intent_ref':ref(intent)}
def verify_historical_root(declared,state,campaign,binding):
    """中文：即使授权后来过期，仍要求密封的原始准入与范围声明事实。
    
    English: Require sealed original admission/claim facts even when grants later expire.
    """
    exact(declared,{'source','segment_binding_ref'},'RESEARCH_ENVELOPE_FIELDS')
    d,m,p,plans,envelopes,bindings,g,a=definition(declared['source'])
    if p!=campaign or declared['segment_binding_ref']!=ref(binding) or binding not in bindings:fail('RESEARCH_HISTORICAL_GRAPH_CHANGED')
    if state['execution_mode']!='EVALUATION' or state['identity']['task_id']!=binding['root_task_id'] or state['capacity']!=binding['capacity'] or state['root_binding']['host_session_ref']!=p['host_session_ref'] or any(state['identity'][k]!=v for k,v in p['identity'].items()):fail('RESEARCH_HISTORICAL_ROOT_IDENTITY')
    if state['root_binding']['context_runtime'].get('research_contract') not in SUPPORTED_CONTRACTS or ref(state['root_binding']['context_runtime'])!=p['runtime_ref']:fail('RESEARCH_HISTORICAL_RUNTIME')
    if not same_path(Path(state['sources']['root_envelope']).parent,Path(binding['ledger_path']).parent):fail('RESEARCH_HISTORICAL_ROOT_PATH')
    folder=_directory(declared['source']);admitted=_read(folder/'admitted.json');ordinal=bindings.index(binding)+1;claim=_read(folder/f'claim-{ordinal}.json')
    intent=_read(folder/'admission-intent.json')
    if admitted!=_admission(declared['source'],p,m,g,a,state['root_binding']['repo_path'],intent):fail('RESEARCH_HISTORICAL_ADMISSION')
    if a.get('consumed_operation')!='make-effective' or not a.get('consumed_at') or a.get('note')!=approval_scope(p,m):fail('RESEARCH_HISTORICAL_APPROVAL')
    expected={'schema_version':'research-segment-claim/1','stage_admission_ref':ref(admitted),'campaign_plan_ref':ref(p),'segment_binding_ref':ref(binding),'segment_ordinal':ordinal,'capacity':binding['capacity']}
    if claim!=expected:fail('RESEARCH_HISTORICAL_CLAIM')
    return {'campaign_ref':ref(p),'manifest_ref':ref(m),'study_binding_ref':ref(binding),'admission_ref':ref(admitted),'claim_ref':ref(claim)}

def _valid(p,g,a,now):
    moment=parse_iso(now)
    return a.get('status') in {'active','consumed'} and p['identity']['project_id']==a.get('project_id') and p['stage_id']==a.get('task_id') and a.get('one_time') is True and 'make-effective' in a.get('operations',[]) and a.get('environment')=='local' and parse_iso(p['created_at'])<=moment<min(parse_iso(p['expires_at']),parse_iso(g['expires_at']),parse_iso(a['expires_at']))
def _host(p,cwd,session):
    if p['host_session_ref']!=ref(session) or stable_repo_fingerprint(str(cwd))!=p['identity']['repo_fingerprint']:fail('RESEARCH_REAL_HOST')
def _installation(d,p):
    from .seed_installation import verify_installation
    return verify_installation({'candidate_payload_digest':p['candidate_payload_digest'],'installation':d['installation']})
def _head(session,directory=None):
    from .research_seed import _head as original_head
    return original_head(session,directory)
def _anchor(p,session,directory=None,*,current=True):
    anchor=p['predecessor'];stored=_read(Path(anchor['registry_path']));head=_head(session,directory)
    if stored.get('schema_version')=='seed-session-head/1':
        from .research_seed import _anchor as original_anchor
        return original_anchor(p,session,directory,require_current_tip=current)
    if stored.get('schema_version')!='research-session-head/1':fail('RESEARCH_ANCHOR_VERSION')
    import hashlib
    if hashlib.sha256(Path(anchor['registry_path']).read_bytes()).hexdigest()!=anchor['registry_bytes_sha256'] or stored.get('session_ref')!=ref(session) or current and (not head.exists() or _read(head)!=stored):fail('RESEARCH_ANCHOR_CHANGED')
    state=budget.read_budget(Path(anchor['ledger_path']))
    if not state['closed'] or state['outcome']!=anchor['closed_outcome'] or budget._read_events(Path(anchor['ledger_path']))[-1]['record_hash']!=anchor['final_record_hash'] or any(state['identity'][k]!=v for k,v in p['identity'].items()):fail('RESEARCH_ANCHOR_NOT_CLOSED')
    stage_terminal(stored['source'])
def admit(source,*,cwd,session,directory=None,now=None):
    """中文：一次密封准入只回放原始消费意图。
    
    English: One sealed admission; replay only the original consumption intent.
    """
    from .routing_registry_v4 import _session_lock
    from .research_seed import _immutable
    from .approval import consume_approval
    now=now or utc_now();d,m,p,_,_,_,g,a=definition(source);_host(p,cwd,session);folder=_directory(source);require_external_state(folder,Path(cwd));folder.mkdir(parents=True,exist_ok=True)
    with OwnerTokenLock(_session_lock(session,directory),timeout=2),OwnerTokenLock(folder/'stage',timeout=2),OwnerTokenLock(Path(g['approval_source']['path']),timeout=2):
        a=load_approval(Path(g['approval_source']['path']));intent={'schema_version':'research-admission-intent/1','definition_ref':source['definition_ref'],'grant_ref':ref(g),'approval_fingerprint':fingerprint(a),'repo_path':str(Path(cwd).absolute())}
        consumed=a.get('consumed_operation')=='make-effective' and bool(a.get('consumed_at'))
        if consumed and (not (folder/'admission-intent.json').exists() or _read(folder/'admission-intent.json')!=intent):fail('RESEARCH_CONSUMED_WITHOUT_INTENT')
        _anchor(p,session,directory,current=not consumed)
        if a.get('note')!=approval_scope(p,m):fail('RESEARCH_APPROVAL_SCOPE')
        _immutable(folder/'admission-intent.json',intent)
        if not consumed:
            if not _valid(p,g,a,now) or a['status']!='active':fail('RESEARCH_ADMISSION_EXPIRED')
            _installation(d,p)
            if repo_snapshot(Path(cwd))['sha256']!=a['baseline_sha256']:fail('RESEARCH_APPROVAL_BASELINE')
            a=consume_approval(Path(g['approval_source']['path']),p['identity']['project_id'],p['stage_id'],'make-effective','local',a['baseline_sha256'])
        admitted=_admission(source,p,m,g,a,cwd,intent);_immutable(folder/'admitted.json',admitted);_immutable(folder/'admission-receipt.json',{'admission_ref':ref(admitted)})
        return admitted
def _prior(p,bindings,ordinal,head,session,directory):
    if ordinal==1:
        _anchor(p,session,directory);return p['predecessor']['final_record_hash']
    previous=bindings[ordinal-2]
    if not head or head.get('schema_version')!='research-session-head/1' or head['segment_binding_ref']!=ref(previous) or head['campaign_ref']!=ref(p):fail('RESEARCH_SEGMENT_ORDER')
    state=budget.read_budget(Path(previous['ledger_path']))
    if not state['closed'] or budget._usage(state)['active'] or any(x['status']=='PREPARED' for x in state['permits'].values()):fail('RESEARCH_PREDECESSOR_ACTIVE')
    return budget._read_events(Path(previous['ledger_path']))[-1]['record_hash']
def prepare_segment(source,*,ordinal,cwd,session,directory=None,now=None):
    from .routing_registry_v4 import _session_lock
    from .research_seed import _immutable
    from .routing_contract import fits,add_vectors
    now=now or utc_now();d,m,p,_,_,bindings,g,a=definition(source);_host(p,cwd,session)
    if type(ordinal)!=int or not 1<=ordinal<=len(bindings):fail('RESEARCH_ORDINAL')
    folder=_directory(source);binding=bindings[ordinal-1]
    with OwnerTokenLock(_session_lock(session,directory),timeout=2),OwnerTokenLock(folder/'stage',timeout=2):
        admitted=_read(folder/'admitted.json');head=_read(_head(session,directory)) if _head(session,directory).exists() else None;cp=folder/f'claim-{ordinal}.json';ip=folder/f'transition-{ordinal}.json'
        if admitted!=_admission(source,p,m,g,a,cwd,_read(folder/'admission-intent.json')):fail('RESEARCH_ADMISSION_CHANGED')
        claim={'schema_version':'research-segment-claim/1','stage_admission_ref':ref(admitted),'campaign_plan_ref':ref(p),'segment_binding_ref':ref(binding),'segment_ordinal':ordinal,'capacity':binding['capacity']}
        if ip.exists():
            intent=_read(ip)
            if intent['claim_ref']!=ref(claim) or intent['source']!=source:fail('RESEARCH_TRANSITION_CHANGED')
            return intent
        if cp.exists():
            if _read(cp)!=claim:fail('RESEARCH_CLAIM_CHANGED')
            receipt={'schema_version':'research-claim-only-close/1','claim_ref':ref(claim),'outcome':'SUSPENDED_NO_DISPATCH','refund':False};_immutable(folder/f'claim-only-close-{ordinal}.json',receipt);return receipt
        if not _valid(p,g,a,now):fail('RESEARCH_SEGMENT_EXPIRED')
        _installation(d,p);previous=_prior(p,bindings,ordinal,head,session,directory);_immutable(cp,claim)
        if not fits(add_vectors(*(_read(folder/f'claim-{i}.json')['capacity'] for i in range(1,ordinal+1))),p['capacity']):fail('RESEARCH_ALLOCATION_OVERDRAWN')
        intent={'schema_version':'research-transition-intent/1','source':source,'ordinal':ordinal,'expected_head_ref':ref(head),'previous_final_record_hash':previous,'claim_ref':ref(claim),'segment_binding_ref':ref(binding)};_immutable(ip,intent);return intent
def commit_segment(source,*,ordinal,cwd,session,directory=None):
    from .routing_registry_v4 import _session_lock
    from .research_seed import _immutable
    d,m,p,_,_,bindings,g,a=definition(source);_host(p,cwd,session);folder=_directory(source)
    if type(ordinal)!=int or not 1<=ordinal<=len(bindings):fail('RESEARCH_ORDINAL')
    binding=bindings[ordinal-1]
    with OwnerTokenLock(_session_lock(session,directory),timeout=2),OwnerTokenLock(folder/'stage',timeout=2):
        intent=_read(folder/f'transition-{ordinal}.json');head=_read(_head(session,directory)) if _head(session,directory).exists() else None;claim=_read(folder/f'claim-{ordinal}.json')
        target={'schema_version':'research-session-head/1','session_ref':ref(session),'source':source,'campaign_ref':ref(p),'ordinal':ordinal,'segment_binding_ref':ref(binding),'ledger_path':binding['ledger_path'],'transition_ref':ref(intent)}
        if head==target:_immutable(folder/f'commit-{ordinal}.json',{'head_ref':ref(target)});return target
        if intent['source']!=source or intent['ordinal']!=ordinal or intent['claim_ref']!=ref(claim) or intent['segment_binding_ref']!=ref(binding) or intent['expected_head_ref']!=ref(head) or _prior(p,bindings,ordinal,head,session,directory)!=intent['previous_final_record_hash']:fail('RESEARCH_HEAD_CAS_CONFLICT')
        state=budget.read_budget(Path(binding['ledger_path']));root,_=read_document(Path(state['sources']['root_envelope']))
        verify_historical_root(root['routing']['research_campaign'],state,p,binding)
        if state['closed'] or state['reservations'] or state['permits']:fail('RESEARCH_NEW_ROOT_NOT_PRISTINE')
        atomic_write_json(_head(session,directory),target);_immutable(folder/f'commit-{ordinal}.json',{'head_ref':ref(target)});return target
def stage_terminal(source):
    d,m,p,_,_,bindings,g,a=definition(source);folder=_directory(source);admitted=_read(folder/'admitted.json')
    for ordinal,binding in enumerate(bindings,1):
        cp=folder/f'claim-{ordinal}.json';ip=folder/f'transition-{ordinal}.json';commit=folder/f'commit-{ordinal}.json';close=folder/f'claim-only-close-{ordinal}.json'
        if not cp.exists():fail('RESEARCH_STAGE_NOT_ALLOCATED')
        claim=_read(cp);expected={'schema_version':'research-segment-claim/1','stage_admission_ref':ref(admitted),'campaign_plan_ref':ref(p),'segment_binding_ref':ref(binding),'segment_ordinal':ordinal,'capacity':binding['capacity']}
        if claim!=expected:fail('RESEARCH_TERMINAL_CLAIM_CHANGED')
        if close.exists():
            receipt={'schema_version':'research-claim-only-close/1','claim_ref':ref(claim),'outcome':'SUSPENDED_NO_DISPATCH','refund':False}
            if _read(close)!=receipt or ip.exists() or commit.exists():fail('RESEARCH_CLAIM_ONLY_CLOSE_CONFLICT')
            if Path(binding['ledger_path']).exists():
                state=budget.read_budget(Path(binding['ledger_path']))
                if not state['closed'] or state['reservations'] or state['permits']:fail('RESEARCH_CLAIM_ONLY_ROOT_ACTIVE')
            continue
        state=budget.read_budget(Path(binding['ledger_path']))
        if not state['closed'] or budget._usage(state)['active'] or any(x['status']=='PREPARED' for x in state['permits'].values()):fail('RESEARCH_STAGE_NOT_TERMINAL')
        if not ip.exists() or not commit.exists():fail('RESEARCH_UNRESOLVED_TRANSITION')
        intent=_read(ip)
        target={'schema_version':'research-session-head/1','session_ref':p['host_session_ref'],'source':source,'campaign_ref':ref(p),'ordinal':ordinal,'segment_binding_ref':ref(binding),'ledger_path':binding['ledger_path'],'transition_ref':ref(intent)}
        if intent['source']!=source or intent['claim_ref']!=ref(claim) or intent['segment_binding_ref']!=ref(binding) or _read(commit)!={'head_ref':ref(target)}:fail('RESEARCH_TERMINAL_COMMIT_CHANGED')
    return True

def assert_dispatch(declared,state,*,cwd,session,now=None,directory=None):
    d,m,p,_,_,bindings,g,a=definition(declared['source']);_host(p,cwd,session)
    binding=next((b for b in bindings if ref(b)==declared['segment_binding_ref']),None)
    if binding is None:fail('RESEARCH_DISPATCH_BINDING')
    verify_historical_root(declared,state,p,binding)
    head=_read(_head(session,directory))
    if head.get('schema_version')!='research-session-head/1' or head['source']!=declared['source'] or head['segment_binding_ref']!=ref(binding) or head['campaign_ref']!=ref(p) or state['closed'] or not _valid(p,g,a,now or utc_now()):fail('RESEARCH_DISPATCH_DENIED')
    intent=_read(_directory(declared['source'])/f'transition-{head["ordinal"]}.json')
    if ref(intent)!=head['transition_ref'] or intent['source']!=declared['source']:fail('RESEARCH_HEAD_CHANGED')
    _installation(d,p);return p,binding
def dispatch_key(campaign_ref,binding_ref,trial_ref):
    return 'rc_'+ref({'campaign_ref':campaign_ref,'binding_ref':binding_ref,'trial_ref':trial_ref})[7:63]
def reserve(path,data,args,callback,*,directory=None):
    from .routing_registry_v4 import _session_lock,_directory as registry_dir
    from .research_seed import _index_dir,_index_key,_immutable
    from .qualification_study import planned_trials,bind_evaluation,trial_key
    from .routing_context_v4 import read_evaluation
    from .routing_evaluation_v4 import trial_packet
    session=data['session_id'];state=budget.read_budget(path);env,_=read_document(Path(state['sources']['root_envelope']));declared=env['routing']['research_campaign'];folder=_directory(declared['source']);indices=_index_dir(directory);indices.mkdir(parents=True,exist_ok=True);task='/root/'+args['task_name'];key=_index_key(session,task,args['agent_type']);ip=indices/(key+'.json')
    with OwnerTokenLock(_session_lock(session,directory),timeout=2),OwnerTokenLock(folder/'stage',timeout=2),OwnerTokenLock(registry_dir(directory)/'expected-spawn-index',timeout=2):
        state=budget.read_budget(path);p,binding=assert_dispatch(declared,state,cwd=data['cwd'],session=session,directory=directory);_,_,_,plans,envelopes,_,_,_=definition(declared['source'])
        permit=[v for v in state['permits'].values() if v['dispatch_ref']==ref(args['task_name'])]
        if len(permit)!=1:fail('RESEARCH_SPAWN_PERMIT')
        permit=permit[0];request=permit['request'];evaluation=read_evaluation(state,case_ref=request['evaluation_case_ref']);profile=permit['selection']['approved_profile'];study_index=next(i for i,s in enumerate(plans) if ref(s)==binding['study_plan_ref']);expected=bind_evaluation(envelopes[study_index],evaluation['protocol_ref'])
        if evaluation!=expected or request['scenario']!=evaluation['scenario']:fail('RESEARCH_SPAWN_PROTOCOL')
        repetitions=[n for n in range(1,evaluation['repetitions']+1) if trial_packet(request['evaluation_case_ref'],profile,n)==request['packet_sha256']]
        if len(repetitions)!=1:fail('RESEARCH_SPAWN_REPETITION')
        trial=trial_key(evaluation['protocol_ref'],request['evaluation_case_ref'],profile,repetitions[0])
        case=next(c for c in evaluation['cases'] if c['case_ref']==request['evaluation_case_ref'])
        if trial not in binding['trial_refs'] or args['task_name']!=dispatch_key(ref(p),ref(binding),trial) or request['business_prompt_sha256']!=case['prompt_ref'][7:] or request['constraints']['allowed_profiles']!=[profile]:fail('RESEARCH_SPAWN_ALLOCATION')
        if ip.exists() or ip.with_suffix('.intent.json').exists():fail('RESEARCH_SPAWN_REPLAY_OR_RECOVERY_REQUIRED')
        intent={'schema_version':'research-spawn-intent/1','source':declared['source'],'segment_binding_ref':ref(binding),'session_ref':ref(session),'task_path':task,'role':args['agent_type'],'depth':1,'ledger_path':str(path),'host_call_ref':ref(data['tool_use_id']),'parameters_ref':ref(args)};_immutable(ip.with_suffix('.intent.json'),intent)
        budget.bind_native_root(path,session_ref=ref(session),repo_ref=ref(state['root_binding']['repo_path']),host_call_ref=ref(data['tool_use_id']))
        result=callback(lambda locked:assert_dispatch(declared,locked,cwd=data['cwd'],session=session,directory=directory));index={**intent,'status':'READY','reservation_id':result['reservation_id'],'permit_id':permit['permit_id'],'repo_path':state['root_binding']['repo_path']};_immutable(ip,index)
        callkey=ref({'parent_session_ref':ref(session),'host_call_ref':ref(data['tool_use_id'])})[7:];_immutable(indices/('call-'+callkey+'.json'),{'index_key':key,'index_ref':ref(index)})
        return result
def event_path(data,*,directory=None):
    from .research_seed import _index_dir,_index_key,_immutable
    from .routing_hook_v5 import _identity,_header_from_bytes,_transcript_path
    from .context_final_v2 import read_bound_transcript
    from .dispatch_policy import delegation_tool_name
    session,child=_identity(data);hp=_head(session,directory)
    if not hp.exists():return None
    head=_read(hp)
    if head.get('schema_version')!='research-session-head/1':return None
    if not child:
        if data.get('hook_event_name')=='PostToolUse' and delegation_tool_name(data.get('tool_name'))!='spawn_agent':return None
        if data.get('hook_event_name')=='PostToolUse':
            callkey=ref({'parent_session_ref':ref(session),'host_call_ref':ref(data['tool_use_id'])})[7:];pointer=_read(_index_dir(directory)/('call-'+callkey+'.json'));index=_read(_index_dir(directory)/(pointer['index_key']+'.json'))
            if pointer['index_ref']!=ref(index):fail('RESEARCH_POST_INDEX_CHANGED')
            return Path(index['ledger_path'])
        return Path(head['ledger_path'])
    raw,binding=read_bound_transcript(_transcript_path(data),header_only=True)
    from .routing_contract import _object,_constant
    import json
    meta=json.loads(raw,object_pairs_hook=_object,parse_constant=_constant)['payload'];spawn=meta['source']['subagent']['thread_spawn'];ip=_index_dir(directory)/(_index_key(session,spawn['agent_path'],spawn['agent_role'],spawn['depth'])+'.json');index=_read(ip)
    # 中文：旧密封启动子任务保持原归属，不猜当前头指向谁。
    # English: Old sealed bootstrap children keep their original owner; no current-head guessing.
    path=Path(index['ledger_path']);state=budget.read_budget(path);header=_header_from_bytes(data,state,raw,binding)
    if index.get('status')!='READY' or index['task_path']!=header['task_path'] or index['role']!=header['role'] or index['session_ref']!=ref(session):fail('RESEARCH_CHILD_INDEX_CHANGED')
    from .routing_registry_v4 import _session_lock,_directory as registry_dir
    original_env,_=read_document(Path(state['sources']['root_envelope']))
    owner_source=index.get('source') or original_env.get('routing',{}).get('research_seed',{}).get('source')
    if not owner_source:fail('RESEARCH_CHILD_OWNER_UNKNOWN')
    owner=_directory(owner_source)
    with OwnerTokenLock(_session_lock(session,directory),timeout=2),OwnerTokenLock(owner/'stage',timeout=2),OwnerTokenLock(registry_dir(directory)/'expected-spawn-index',timeout=2):
        _immutable(ip.with_suffix('.child.json'),{'child_ref':ref(child),'header_ref':header['header_ref'],'index_ref':ref(index),'file_binding':binding})
    return path
def closed_duplicate(path,data):
    state=budget.read_budget(path)
    if state['root_binding']['context_runtime'].get('research_contract') not in SUPPORTED_CONTRACTS or not state['closed']:return False
    child=data.get('agent_id');event=data.get('hook_event_name')
    if child:
        found=[(rid,v) for rid,v in state['host_identity_links'].items() if v['agent_ref']==ref(child)]
        if len(found)!=1:fail('RESEARCH_CLOSED_EVENT_UNKNOWN')
        rid,link=found[0]
        if event=='SubagentStart':return True
        if event=='SubagentStop':
            from .context_final_v2 import read_bound_transcript,extract_final
            from .routing_hook_v5 import _transcript_path
            raw,_=read_bound_transcript(_transcript_path(data));permit=state['permits'][state['reservations'][rid]['permit_id']];_,proof=extract_final(raw,child_id=child,root_id=data['session_id'],task_path='/root/'+json_task(state,permit),role=permit['role'],repo_path=state['root_binding']['repo_path'])
            sealed=state['context_raw_finals'].get(rid);observed=state['host_observations'].get(ref(child),{})
            if observed.get('stop')!=data.get('terminal_outcome','UNKNOWN'):fail('RESEARCH_CLOSED_STOP_CONFLICT')
            if sealed and all(sealed[k]==v for k,v in proof.items()):return True
        fail('RESEARCH_CLOSED_EVENT_CONFLICT')
    if ref(data.get('tool_use_id')) in state['host_dispatches']:
        import json
        result=data.get('tool_response');result=json.loads(result) if isinstance(result,str) else result;rid=state['host_dispatches'][ref(data['tool_use_id'])]
        if isinstance(result,dict) and set(result)=={'task_name'} and state['host_receipts'].get(rid,{}).get('agent_ref')==ref(result['task_name']):return True
    fail('RESEARCH_CLOSED_EVENT_CONFLICT')
def json_task(state,permit):
    from .qualification_study import trial_key
    from .routing_evaluation_v4 import trial_packet
    from .routing_context_v4 import read_evaluation
    env,_=read_document(Path(state['sources']['root_envelope']));declared=env['routing']['research_campaign'];_,_,p,_,_,_,_,_=definition(declared['source']);request=permit['request'];profile=permit['selection']['approved_profile'];evaluation=read_evaluation(state,case_ref=request['evaluation_case_ref']);repetition=next(r for r in range(1,evaluation['repetitions']+1) if trial_packet(request['evaluation_case_ref'],profile,r)==request['packet_sha256'])
    return dispatch_key(ref(p),declared['segment_binding_ref'],trial_key(evaluation['protocol_ref'],request['evaluation_case_ref'],profile,repetition))

def recover_spawn_intent(source,**kwargs):
    from .spawn_recovery import recover
    return recover(source,**kwargs)

def recovery_context(source,intent,*,cwd,session,task_path,role):
    d,m,p,plans,envelopes,bindings,g,a=definition(source);_host(p,cwd,session)
    if intent['source']!=source:fail('RESEARCH_RECOVERY_SOURCE')
    found=[b for b in bindings if ref(b)==intent['segment_binding_ref'] and same_path(Path(b['ledger_path']),Path(intent['ledger_path']))]
    if len(found)!=1:fail('RESEARCH_RECOVERY_BINDING')
    binding=found[0];state=budget.read_budget(Path(binding['ledger_path']));env,_=read_document(Path(state['sources']['root_envelope']))
    verify_historical_root(env['routing']['research_campaign'],state,p,binding)
    permits=[x for x in state['permits'].values() if x['role']==role and x['depth']==1 and x['dispatch_ref']==ref(task_path.rsplit('/',1)[-1])]
    if len(permits)!=1 or '/root/'+json_task(state,permits[0])!=task_path:fail('RESEARCH_RECOVERY_TRIAL')
    return {**p,'repo_path':state['root_binding']['repo_path']},binding,state,permits
