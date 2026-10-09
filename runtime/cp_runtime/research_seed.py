"""中文：有限研究承接，不重开旧根。English: bootstrap-only, prepaid succession."""
from __future__ import annotations
import copy
import hashlib
import re
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from . import budget_v5 as budget
from .approval import load_approval, consume_approval
from .common import atomic_write_json, utc_now, parse_iso, require_external_state
from .event_v2 import OwnerTokenLock, stable_repo_fingerprint
from .routing_contract import exact, fail, ref, sha, hex_digest, vector, add_vectors, fits, identity, policy_digest
from .routing_context_contract import safe_file,bounded_bytes
from .path_identity import same_path

CONTRACT = 'bootstrap-code-review/1'
POINTER = {'path','definition_ref'}
DEFINITION = {'schema_version','plan','manifest','grant'}
FILE = {'path','canonical_ref','bytes_sha256'}
PLAN = {'schema_version','stage_id','identity','policy_digest','host_session_ref','repo_path',
        'candidate_payload_digest','installation','runtime_ref','created_at','expires_at','predecessor','segments','capacity'}
SEGMENT = {'ordinal','task_id','ledger_path','capacity','calls'}
CALL = {'dispatch_key','request_ref','review_material_ref','profile_id','cost'}
GRANT = {'schema_version','grant_id','campaign_plan_ref','campaign_manifest_ref','identity','host_session_ref',
         'stage_id','scope','capacity','approved_at','expires_at','approval_source'}

def _read(path):
    from .routing_contract import read_document
    return read_document(safe_file(Path(path)))[0]

def _immutable(path, value):
    if path.exists():
        if _read(path) != value: fail('SEED_IMMUTABLE_CONFLICT')
    else: atomic_write_json(path,value)
    return value

def _file(source):
    exact(source,FILE,'SEED_FILE_FIELDS');sha(source['canonical_ref'])
    path=safe_file(Path(source['path']));raw=bounded_bytes(path,1_048_576);value=_read(path)
    if ref(value)!=source['canonical_ref'] or hashlib.sha256(raw).hexdigest()!=source['bytes_sha256']:
        fail('SEED_SOURCE_CHANGED')
    return value

def fingerprint(approval):
    return ref({k:v for k,v in approval.items() if k not in {'integrity','status','consumed_at','consumed_operation'}})

def approval_scope(plan_ref, manifest_ref, stage_id):
    return 'research-stage:'+ref({'plan_ref':plan_ref,'manifest_ref':manifest_ref,'stage_id':stage_id})

def definition(source):
    exact(source,POINTER,'SEED_POINTER');d=_read(source['path'])
    if ref(d)!=source['definition_ref']:fail('SEED_DEFINITION_CHANGED')
    exact(d,DEFINITION,'SEED_DEFINITION_FIELDS')
    if d['schema_version']!='bootstrap-stage-definition/1':fail('SEED_DEFINITION_VERSION')
    p=_file(d['plan']);m=_file(d['manifest']);g=_file(d['grant'])
    exact(p,PLAN,'SEED_PLAN_FIELDS');exact(g,GRANT,'SEED_GRANT_FIELDS')
    if p['schema_version']!='bootstrap-review-plan/1' or g['schema_version']!='research-stage-grant/1':fail('SEED_VERSION')
    if p['policy_digest']!=policy_digest():fail('SEED_POLICY')
    identity(p['identity']);sha(p['host_session_ref']);hex_digest(p['candidate_payload_digest']);sha(p['runtime_ref'])
    if not Path(p['repo_path']).is_absolute():fail('SEED_REPO_PATH')
    exact(m,{'schema_version','plan_ref','materials'},'SEED_MANIFEST_FIELDS')
    if m['schema_version']!='bootstrap-material-manifest/1' or m['plan_ref']!=ref(p):fail('SEED_MANIFEST_BINDING')
    if not isinstance(m['materials'],list) or not m['materials'] or len(m['materials'])>64:fail('SEED_MATERIAL_LIMIT')
    for item in m['materials']:
        exact(item,{'path','bytes_sha256'},'SEED_MATERIAL_FIELDS')
        if hashlib.sha256(bounded_bytes(Path(item['path']),1_048_576)).hexdigest()!=item['bytes_sha256']:fail('SEED_MATERIAL_CHANGED')
    if g['campaign_plan_ref']!=ref(p) or g['campaign_manifest_ref']!=ref(m) or any(g[k]!=p[k] for k in ('identity','host_session_ref','stage_id','capacity')):
        fail('SEED_FIXED_GRANT_SCOPE')
    if g['scope']!='BOOTSTRAP_CODE_REVIEW_ONLY' or parse_iso(g['approved_at'])<parse_iso(p['created_at']) or parse_iso(g['expires_at'])>parse_iso(p['expires_at']):fail('SEED_STAGE_SCOPE')
    exact(g['approval_source'],{'path','immutable_fingerprint'},'SEED_APPROVAL_SOURCE')
    a=load_approval(Path(g['approval_source']['path']))
    if fingerprint(a)!=g['approval_source']['immutable_fingerprint'] or a['note']!=approval_scope(ref(p),ref(m),p['stage_id']) or a['project_id']!=p['identity']['project_id'] or a['task_id']!=p['stage_id'] or a['environment']!='local' or a['operations']!=['make-effective'] or not a['one_time']:
        fail('SEED_AUTHORITY_SCOPE')
    segments=p['segments']
    if not isinstance(segments,list) or not 1<=len(segments)<=2:fail('SEED_LIMITED_SEGMENTS')
    paths=set();tasks=set();names=set();requests=set();resources=[]
    for i,s in enumerate(segments,1):
        exact(s,SEGMENT,'SEED_SEGMENT_FIELDS')
        if s['ordinal']!=i or not Path(s['ledger_path']).is_absolute() or s['ledger_path'] in paths or s['task_id'] in tasks:fail('SEED_SEGMENT_IDENTITY')
        paths.add(s['ledger_path']);tasks.add(s['task_id']);cap=vector(s['capacity']);resources.append(cap)
        if not isinstance(s['calls'],list) or not 1<=len(s['calls'])<=4 or cap['attempts']!=len(s['calls']):fail('SEED_CALL_LIMIT')
        costs=[]
        for call in s['calls']:
            exact(call,CALL,'SEED_CALL_FIELDS');sha(call['request_ref']);sha(call['review_material_ref'])
            from .routing_cards import validate_cost
            cost=validate_cost(call['cost'],scenario_ref=call['cost'].get('scenario_ref'))
            if cost['profile_id']!=call['profile_id'] or cost['source_ref']!=call['review_material_ref']:fail('SEED_COST_MATERIAL_SCOPE')
            name=call['dispatch_key']
            if not re.fullmatch(r'[a-z0-9_]{1,64}',name) or name in names or call['request_ref'] in requests:fail('SEED_DISPATCH_UNIQUE')
            names.add(name);requests.add(call['request_ref'])
            from .routing_contract import resource_need
            costs.append(resource_need(call['profile_id'],call['cost']['reserve_units']))
        if not fits(add_vectors(*costs),cap):fail('SEED_SEGMENT_CAPACITY')
    if add_vectors(*resources)!=vector(p['capacity']):fail('SEED_TOTAL_CAPACITY')
    exact(p['predecessor'],{'registry_path','registry_bytes_sha256','ledger_path','final_record_hash','closed_outcome'},'SEED_ANCHOR_FIELDS')
    return d,p,m,g,a

def _state_directory(path):
    if not path.is_absolute() or '..' in path.parts:fail('SEED_STATE_PATH')
    if os.name=='nt' and any(':' in part for part in path.parts[1:]):fail('SEED_STATE_ADS')
    for part in (path,*path.parents):
        if part.exists():
            info=part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:fail('SEED_STATE_REPARSE')
    return path

def _directory(source):return _state_directory(Path(source['path']).parent/'seed-state')

def _head(session, directory=None):
    from .routing_registry_v4 import _directory as registry_directory
    return _state_directory(registry_directory(directory))/('research-head-'+ref(session)[7:]+'.json')

def _history(session,head_ref,directory=None):
    sha(head_ref)
    return _head(session,directory).parent/'research-head-history'/ref(session)[7:]/(head_ref[7:]+'.json')

def archive_closed_head(session,*,directory=None):
    """中文：快照已关闭的前置研究，不删除或改变其活动头。
    
    English: Snapshot a closed predecessor without deleting or changing its active head.
    """
    from .routing_registry_v4 import _session_lock
    with OwnerTokenLock(_session_lock(session,directory),timeout=2):
        head=_read(_head(session,directory));ledger=lookup(session,directory=directory)
        if not budget.read_budget(ledger)['closed']:fail('SEED_PREDECESSOR_ACTIVE')
        latest=_stage_terminal(head['source'])
        if latest is not None and latest!=head:fail('SEED_STAGE_HEAD_STALE')
        path=_history(session,ref(head),directory);_state_directory(path.parent);path.parent.mkdir(parents=True,exist_ok=True)
        _immutable(path,head)
        return path

def _stage_terminal(source):
    """中文：账本或回执缺失记为失败，不能推断该段零消耗。
    
    English: Missing ledgers/receipts are failures, never inferred zero-spend segments.
    """
    _,plan,_,_,_=definition(source);directory=_directory(source);latest=None
    for segment in plan['segments']:
        _,_,_,_,state=_segment_state(source,segment['ordinal'])
        if not state['closed'] or any(a['state'] in {'RESERVED','STARTED'} for a in state.get('reservations',{}).values()) or any(p['status']=='PREPARED' for p in state['permits'].values()):fail('SEED_STAGE_NOT_TERMINAL')
        ordinal=segment['ordinal'];claim_path=directory/f'claim-{ordinal}.json';intent_path=directory/f'transition-{ordinal}.json'
        if intent_path.exists() and not claim_path.exists():fail('SEED_STAGE_TRANSACTION_UNRESOLVED')
        if not claim_path.exists():continue
        claim=_read(claim_path);admitted=_read(directory/'admitted.json')
        if claim!= {'schema_version':'seed-segment-claim/1','admission_ref':ref(admitted),'plan_ref':ref(plan),'segment_ref':ref(segment),'ordinal':ordinal,'capacity':segment['capacity']}:fail('SEED_STAGE_TRANSACTION_UNRESOLVED')
        if intent_path.exists():
            intent=_read(intent_path);commit_path=directory/f'commit-{ordinal}.json'
            if not commit_path.exists() or intent['claim_ref']!=ref(claim):fail('SEED_STAGE_TRANSACTION_UNRESOLVED')
            expected={'schema_version':'seed-session-head/1','session_ref':plan['host_session_ref'],'source':source,'ordinal':ordinal,'ledger_path':segment['ledger_path'],'transition_ref':ref(intent)}
            if _read(commit_path)!= {'head_ref':ref(expected)}:fail('SEED_STAGE_TRANSACTION_UNRESOLVED')
            latest=expected
        else:
            receipt_path=directory/f'claim-only-close-{ordinal}.json'
            expected={'schema_version':'seed-claim-only-close/1','claim_ref':ref(claim),'source':source,'ordinal':ordinal,'outcome':'SUSPENDED_NO_DISPATCH','refund':False}
            if not receipt_path.exists() or _read(receipt_path)!=expected:fail('SEED_STAGE_TRANSACTION_UNRESOLVED')
    return latest

def _valid(g,a,now):
    return parse_iso(g['approved_at'])<=parse_iso(now)<parse_iso(g['expires_at']) and parse_iso(now)<parse_iso(a['expires_at']) and a['status'] in {'active','consumed'}

def _check_host(p,cwd,session):
    if p['host_session_ref']!=ref(session) or not same_path(Path(cwd),Path(p['repo_path'])) or stable_repo_fingerprint(str(cwd))!=p['identity']['repo_fingerprint']:fail('SEED_REAL_HOST_BINDING')

def _anchor(p,session,directory,*,require_current_tip=True):
    from .routing_registry_v5 import _root,_read as registered_read
    anchor=p['predecessor'];path=safe_file(Path(anchor['registry_path']))
    if hashlib.sha256(path.read_bytes()).hexdigest()!=anchor['registry_bytes_sha256']:fail('SEED_ANCHOR_CHANGED')
    if same_path(path,_root(session,directory)):
        registration,state=registered_read(path,session,directory)
    else:
        registration=_read(path)
        if not same_path(path,_history(session,ref(registration),directory)) or registration.get('session_ref')!=ref(session):fail('SEED_ANCHOR_CHANGED')
        current_path=_head(session,directory)
        if require_current_tip and (not current_path.exists() or _read(current_path)!=registration):fail('SEED_HISTORY_NOT_CURRENT_TIP')
        latest=_stage_terminal(registration['source'])
        if latest is not None and latest!=registration:fail('SEED_STAGE_HEAD_STALE')
        _,_,_,_,state=_segment_state(registration['source'],registration['ordinal'])
        if any(state['identity'][k]!=v for k,v in p['identity'].items()):fail('SEED_ANCHOR_PROJECT')
    events=budget._read_events(Path(anchor['ledger_path']))
    if not state['closed'] or state['outcome']!=anchor['closed_outcome'] or events[-1]['record_hash']!=anchor['final_record_hash'] or not same_path(Path(registration['ledger_path']),Path(anchor['ledger_path'])):
        fail('SEED_ANCHOR_NOT_CLOSED')

def admit(source,*,cwd,session,now=None,directory=None):
    """中文：一次消费用户阶段授权，不初始化预算或调用模型。
    
    English: Consume user stage authority once. No budget initialization or model call.
    """
    now=now or utc_now();d,p,m,g,a=definition(source);_check_host(p,cwd,session)
    state_dir=_directory(source);require_external_state(state_dir,Path(cwd));state_dir.mkdir(parents=True,exist_ok=True)
    from .routing_registry_v4 import _session_lock
    with OwnerTokenLock(_session_lock(session,directory),timeout=2),OwnerTokenLock(state_dir/'stage',timeout=2),OwnerTokenLock(Path(g['approval_source']['path']),timeout=2):
        intent={'schema_version':'seed-admission-intent/1','definition_ref':source['definition_ref'],'grant_ref':ref(g),'approval_fingerprint':fingerprint(a)}
        original_intent=state_dir/'admission-intent.json'
        a=load_approval(Path(g['approval_source']['path']))
        consumed=bool(a.get('consumed_at')) and a.get('consumed_operation')=='make-effective'
        if consumed:
            if not original_intent.exists() or _read(original_intent)!=intent:fail('SEED_ADMISSION_RECOVERY_UNBOUND')
            _anchor(p,session,directory,require_current_tip=False)
        else:
            _anchor(p,session,directory)
        _immutable(state_dir/'admission-intent.json',intent)
        a=load_approval(Path(g['approval_source']['path']))
        if a['status']=='active':
            if not _valid(g,a,now):fail('SEED_STAGE_EXPIRED')
            from .seed_installation import verify_installation
            verify_installation(p)
            from .common import repo_snapshot
            if repo_snapshot(Path(cwd))['sha256']!=a['baseline_sha256']:fail('SEED_AUTHORITY_BASELINE')
            a=consume_approval(Path(g['approval_source']['path']),p['identity']['project_id'],p['stage_id'],'make-effective','local',a['baseline_sha256'])
        elif not a.get('consumed_at') or a.get('consumed_operation')!='make-effective':fail('SEED_STAGE_REVOKED')
        record={'schema_version':'seed-stage-admission/1','intent_ref':ref(intent),'grant_ref':ref(g),'plan_ref':ref(p),'manifest_ref':ref(m),'authority_consumed_at':a['consumed_at']}
        _immutable(state_dir/'admitted.json',record)
        _immutable(state_dir/'admission-receipt.json',{'admission_ref':ref(record)})
        if not _valid(g,a,now):atomic_write_json(state_dir/'suspended.json',{'reason':'authority-not-current','admission_ref':ref(record)})
        return record

def _segment_state(source,ordinal,*,state=None):
    d,p,m,g,a=definition(source)
    if type(ordinal)!=int or not 1<=ordinal<=len(p['segments']):fail('SEED_ORDINAL')
    s=p['segments'][ordinal-1];path=Path(s['ledger_path']);st=state if state is not None else budget.read_budget(path)
    envelope=_read(st['sources']['root_envelope'])
    if envelope.get('routing',{}).get('research_seed')!={'source':source,'ordinal':ordinal}:fail('SEED_ROOT_ENVELOPE_BINDING')
    if st['execution_mode']!='EVALUATION' or st['root_binding']['context_runtime'].get('bootstrap_contract')!=CONTRACT or ref(st['root_binding']['context_runtime'])!=p['runtime_ref'] or st['identity']['task_id']!=s['task_id'] or st['capacity']!=s['capacity'] or st['root_binding']['host_session_ref']!=p['host_session_ref'] or any(st['identity'][k]!=v for k,v in p['identity'].items()) or st['max_depth']!=1:
        fail('SEED_SEGMENT_BINDING')
    return p,g,a,s,st

def advance(source,*,ordinal,cwd,session,now=None,directory=None):
    now=now or utc_now();p,g,a,s,state=_segment_state(source,ordinal);_check_host(p,cwd,session)
    state_dir=_directory(source);head_path=_head(session,directory)
    require_external_state(head_path,Path(cwd));head_path.parent.mkdir(parents=True,exist_ok=True)
    from .routing_registry_v4 import _session_lock
    # 中文：按会话、阶段、ExpectedSpawn、预算的顺序解析，不能反向。
    # English: Session -> stage -> ExpectedSpawn -> budget; never reverse this order.
    with OwnerTokenLock(_session_lock(session,directory),timeout=2),OwnerTokenLock(state_dir/'stage',timeout=2),OwnerTokenLock(head_path.parent/'expected-spawn-index',timeout=2):
        admitted=_read(state_dir/'admitted.json')
        if admitted['grant_ref']!=ref(g) or admitted['plan_ref']!=ref(p):fail('SEED_ADMISSION_SCOPE')
        head=_read(head_path) if head_path.exists() else None
        intent_path=state_dir/f'transition-{ordinal}.json';claim_path=state_dir/f'claim-{ordinal}.json'
        if head and head['source']==source and head['ordinal']==ordinal:
            intent=_read(intent_path);claim=_read(claim_path)
            if head['transition_ref']!=ref(intent) or claim['segment_ref']!=ref(s):fail('SEED_COMMIT_CHANGED')
            _immutable(state_dir/f'commit-{ordinal}.json',{'head_ref':ref(head)})
            return head
        if intent_path.exists():intent=_read(intent_path)
        else:
            if claim_path.exists():
                # 中文：声明本身没有可信 expected-head 或 final-hash，只关闭元数据。
                # English: Claim alone has no trusted expected-head/final-hash. Close metadata only.
                claim=_read(claim_path)
                expected={'schema_version':'seed-segment-claim/1','admission_ref':ref(admitted),'plan_ref':ref(p),'segment_ref':ref(s),'ordinal':ordinal,'capacity':s['capacity']}
                if claim!=expected:fail('SEED_CLAIM_ONLY_CONFLICT')
                receipt={'schema_version':'seed-claim-only-close/1','claim_ref':ref(claim),'source':source,'ordinal':ordinal,'outcome':'SUSPENDED_NO_DISPATCH','refund':False}
                _immutable(state_dir/f'claim-only-close-{ordinal}.json',receipt)
                return receipt
            if not _valid(g,a,now):fail('SEED_STAGE_EXPIRED')
            from .seed_installation import verify_installation
            verify_installation(p)
            if ordinal==1:
                if head and ref(head)!=ref(_read(p['predecessor']['registry_path'])):fail('SEED_ACTIVE_HEAD_EXISTS')
                _anchor(p,session,directory);previous=p['predecessor']['final_record_hash']
            else:
                if not head or head['source']!=source or head['ordinal']!=ordinal-1:fail('SEED_SEGMENT_ORDER')
                prev=budget.read_budget(Path(head['ledger_path']))
                if not prev['closed'] or any(x['status']=='PREPARED' for x in prev['permits'].values()):fail('SEED_PREDECESSOR_ACTIVE')
                previous=budget._read_events(Path(head['ledger_path']))[-1]['record_hash']
            claim={'schema_version':'seed-segment-claim/1','admission_ref':ref(admitted),'plan_ref':ref(p),'segment_ref':ref(s),'ordinal':ordinal,'capacity':s['capacity']}
            _immutable(claim_path,claim)
            allocated=add_vectors(*[_read(state_dir/f'claim-{i}.json')['capacity'] for i in range(1,ordinal+1)])
            if not fits(allocated,p['capacity']):fail('SEED_STAGE_OVERDRAW')
            intent={'schema_version':'seed-transition/1','expected_head_ref':ref(head),'previous_final_hash':previous,'claim_ref':ref(claim),'source':source,'ordinal':ordinal,'ledger_path':s['ledger_path']}
            _immutable(intent_path,intent)
        claim=_read(claim_path)
        if intent['source']!=source or intent['ordinal']!=ordinal or intent['ledger_path']!=s['ledger_path'] or intent['claim_ref']!=ref(claim) or claim['segment_ref']!=ref(s) or intent['expected_head_ref']!=ref(head):fail('SEED_TRANSITION_CONFLICT')
        if ordinal==1:
            _anchor(p,session,directory)
            previous=p['predecessor']['final_record_hash']
        else:
            prev=budget.read_budget(Path(head['ledger_path']))
            if not prev['closed']:fail('SEED_PREDECESSOR_ACTIVE')
            previous=budget._read_events(Path(head['ledger_path']))[-1]['record_hash']
        if previous!=intent['previous_final_hash']:fail('SEED_PREDECESSOR_CHANGED')
        new={'schema_version':'seed-session-head/1','session_ref':ref(session),'source':source,'ordinal':ordinal,'ledger_path':s['ledger_path'],'transition_ref':ref(intent)}
        atomic_write_json(head_path,new)
        _immutable(state_dir/f'commit-{ordinal}.json',{'head_ref':ref(new)})
        if not _valid(g,a,now):atomic_write_json(state_dir/'suspended.json',{'reason':'authority-not-current','admission_ref':ref(admitted)})
        return new

def lookup(session,*,directory=None):
    if not session:return None
    path=_head(session,directory)
    if not path.exists():return None
    h=_read(path);p,g,a,s,st=_segment_state(h['source'],h['ordinal'])
    if h['session_ref']!=ref(session):fail('SEED_HEAD_SESSION')
    state_dir=_directory(h['source']);intent=_read(state_dir/f'transition-{h["ordinal"]}.json')
    if h['transition_ref']!=ref(intent) or intent['source']!=h['source'] or intent['ledger_path']!=h['ledger_path']:fail('SEED_HEAD_TAMPERED')
    admitted=_read(state_dir/'admitted.json')
    if admitted['grant_ref']!=ref(g) or admitted['plan_ref']!=ref(p):fail('SEED_ADMISSION_SCOPE')
    claims=[_read(state_dir/f'claim-{i}.json') for i in range(1,h['ordinal']+1)]
    if any(c['admission_ref']!=ref(admitted) or c['segment_ref']!=ref(p['segments'][i]) for i,c in enumerate(claims)) or not fits(add_vectors(*(c['capacity'] for c in claims)),p['capacity']):fail('SEED_STAGE_OVERDRAW')
    return Path(h['ledger_path'])

def is_seed(state):return state['root_binding']['context_runtime'].get('bootstrap_contract')==CONTRACT

def assert_dispatch(path,*,session,cwd,now=None,directory=None,state=None):
    if state is None and not same_path(path,lookup(session,directory=directory)):fail('SEED_HEAD_PATH')
    h=_read(_head(session,directory));p,g,a,s,st=_segment_state(h['source'],h['ordinal'],state=state);_check_host(p,cwd,session)
    intent=_read(_directory(h['source'])/f'transition-{h["ordinal"]}.json')
    if h['transition_ref']!=ref(intent) or h['session_ref']!=ref(session) or intent['source']!=h['source']:fail('SEED_HEAD_TAMPERED')
    if not same_path(path,Path(s['ledger_path'])) or st['closed'] or not _valid(g,a,now or utc_now()):fail('SEED_DISPATCH_DENIED')
    from .seed_installation import verify_installation
    verify_installation(p)
    return h,p,s,st

def _index_dir(directory=None):
    from .routing_registry_v4 import _directory
    return _state_directory(_directory(directory)/'expected-spawns')

def _index_key(session,task,role,depth=1):return ref({'parent_session_ref':ref(session),'task_path':task,'role':role,'depth':depth})[7:]

def task_name(stage_id,ordinal,request_ref):
    # 中文：哈希绑定完整标识；短前缀为 64 字符限制留出足够空间。
    # English: Hash binds full identifiers; short prefix leaves ample space under 64 characters.
    return 'rs_'+ref({'stage_id':stage_id,'ordinal':ordinal,'request_ref':request_ref})[7:63]

def request_core_ref(request):
    """中文：仅 expected 由控制器推导；业务与材料字段仍保持原绑定。
    
    English: Only expected is controller-derived; all business/material fields stay bound.
    """
    from .routing_context_contract import REQUEST
    exact(request,REQUEST,'SEED_REQUEST_FIELDS')
    return ref({**request,'expected':{}})

def reserve(path,data,args,callback,*,directory=None):
    session=data['session_id'];h,p,s,st=assert_dispatch(path,session=session,cwd=data['cwd'],directory=directory)
    state_dir=_directory(h['source']);indices=_index_dir(directory);indices.mkdir(parents=True,exist_ok=True)
    from .routing_registry_v4 import _session_lock,_directory as regdir
    task='/root/'+args['task_name'];key=_index_key(session,task,args['agent_type']);index_path=indices/(key+'.json')
    with OwnerTokenLock(_session_lock(session,directory),timeout=2),OwnerTokenLock(state_dir/'stage',timeout=2),OwnerTokenLock(regdir(directory)/'expected-spawn-index',timeout=2):
        h,p,s,st=assert_dispatch(path,session=session,cwd=data['cwd'],directory=directory)
        call=next((c for c in s['calls'] if c['dispatch_key']==args['task_name']),None)
        matches=[pmt for pmt in st['permits'].values() if pmt['dispatch_ref']==ref(args['task_name'])]
        if not call or len(matches)!=1 or request_core_ref(matches[0]['request'])!=call['request_ref'] or matches[0]['selection']['approved_profile']!=call['profile_id']:fail('SEED_UNREGISTERED_CALL')
        if index_path.exists():fail('SEED_SPAWN_REPLAY')
        if (indices/(key+'.intent.json')).exists():fail('SEED_SPAWN_RECOVERY_REQUIRED')
        intent={'schema_version':'seed-spawn-intent/1','session_ref':ref(session),'task_path':task,'role':args['agent_type'],'depth':1,'ledger_path':str(path),'host_call_ref':ref(data['tool_use_id']),'parameters_ref':ref(args)}
        _immutable(indices/(key+'.intent.json'),intent)
        budget.bind_native_root(path,session_ref=ref(session),repo_ref=ref(st['root_binding']['repo_path']),host_call_ref=ref(data['tool_use_id']))
        result=callback(lambda locked:assert_dispatch(path,session=session,cwd=data['cwd'],directory=directory,state=locked))
        index={**intent,'status':'READY','reservation_id':result['reservation_id'],'permit_id':matches[0]['permit_id'],'segment_ref':ref(s),'repo_path':p['repo_path']}
        _immutable(index_path,index)
        call_key=ref({'parent_session_ref':ref(session),'host_call_ref':ref(data['tool_use_id'])})[7:]
        _immutable(indices/('call-'+call_key+'.json'),{'index_key':key,'index_ref':ref(index)})
        if _read(index_path)!=index:fail('SEED_INDEX_NOT_READY')
        return result

def event_path(data,*,directory=None):
    """中文：依据真实头部识别子任务，即使父级 POST 回执尚未到达。
    
    English: Resolve children from authentic header, even before parent POST receipt.
    """
    session=data.get('session_id','');head=_head(session,directory)
    if not session or not head.exists():return None
    for alias in ('sessionId','thread_id','threadId','root_session_id','rootSessionId'):
        if alias in data and data[alias]!=session:fail('SEED_SESSION_ALIAS_CONFLICT')
    if not data.get('agent_id'):
        if data.get('hook_event_name')=='PostToolUse':
            call_key=ref({'parent_session_ref':ref(session),'host_call_ref':ref(data.get('tool_use_id'))})[7:]
            call_path=_index_dir(directory)/('call-'+call_key+'.json')
            if call_path.exists():
                link=_read(call_path);index=_read(_index_dir(directory)/(link['index_key']+'.json'))
                if ref(index)!=link['index_ref'] or index['session_ref']!=ref(session) or index['host_call_ref']!=ref(data.get('tool_use_id')):fail('SEED_POST_AMBIGUOUS')
                return Path(index['ledger_path'])
        return lookup(session,directory=directory)
    from .routing_hook_v5 import _identity,_transcript_path,_header_from_bytes
    from .context_final_v2 import read_bound_transcript
    parent,child=_identity(data);raw,binding=read_bound_transcript(_transcript_path(data),header_only=True)
    import json
    from .routing_contract import _object,_constant
    header=json.loads(raw.splitlines()[0],object_pairs_hook=_object,parse_constant=_constant)['payload'];spawn=header['source']['subagent']['thread_spawn']
    key=_index_key(parent,spawn['agent_path'],spawn['agent_role'],spawn['depth']);ip=_index_dir(directory)/(key+'.json')
    if not ip.exists():fail('SEED_UNKNOWN_CHILD')
    index=_read(ip);path=Path(index['ledger_path']);state=budget.read_budget(path)
    verified=_header_from_bytes(data,state,raw.splitlines(keepends=True)[0],binding)
    if index['status']!='READY' or index['task_path']!=verified['task_path'] or index['role']!=verified['role'] or index['session_ref']!=ref(parent):fail('SEED_CHILD_INDEX_MISMATCH')
    child_path=ip.with_suffix('.child.json')
    from .routing_registry_v4 import _session_lock,_directory as regdir
    with OwnerTokenLock(_session_lock(parent,directory),timeout=2),OwnerTokenLock(_directory(_read(head)['source'])/'stage',timeout=2),OwnerTokenLock(regdir(directory)/'expected-spawn-index',timeout=2):
        _immutable(child_path,{'child_ref':ref(child),'header_ref':verified['header_ref'],'index_ref':ref(index),'file_binding':binding})
    return path

def closed_duplicate(path,data):
    state=budget.read_budget(path)
    if not is_seed(state) or not state['closed']:return False
    # 中文：调用前验证头部和索引；已关闭账本保持不可变。
    # English: Authenticate header/index before this call. Closed journals remain immutable.
    child=data.get('agent_id');event=data.get('hook_event_name')
    if child:
        linked=[(rid,v) for rid,v in state['host_identity_links'].items() if v['agent_ref']==ref(child)]
        if len(linked)!=1:fail('SEED_CLOSED_EVENT_CONFLICT')
        rid,link=linked[0]
        if event=='SubagentStart':return True
        if event=='SubagentStop':
            from .context_final_v2 import read_bound_transcript,extract_final
            from .routing_hook_v5 import _transcript_path
            raw,binding=read_bound_transcript(_transcript_path(data))
            permit=state['permits'][state['reservations'][rid]['permit_id']]
            pointer=_read(state['sources']['root_envelope'])['routing']['research_seed']
            segment=_segment_state(pointer['source'],pointer['ordinal'],state=state)[3]
            dispatch=next(c['dispatch_key'] for c in segment['calls'] if ref(c['dispatch_key'])==permit['dispatch_ref'])
            text,proof=extract_final(raw,child_id=child,root_id=data['session_id'],task_path='/root/'+dispatch,role=permit['role'],repo_path=state['root_binding']['repo_path'])
            sealed=state['context_raw_finals'].get(rid)
            observed=state['host_observations'].get(ref(child),{})
            if 'stop' not in observed or observed['stop']!=data.get('terminal_outcome','UNKNOWN'):fail('V5_OBSERVATION_CONFLICT')
            if sealed and all(sealed[k]==v for k,v in proof.items()):return True
        fail('SEED_CLOSED_EVENT_CONFLICT')
    if not child and ref(data.get('tool_use_id')) in state['host_dispatches']:
        import json
        response=data.get('tool_response');response=json.loads(response) if isinstance(response,str) else response
        rid=state['host_dispatches'][ref(data['tool_use_id'])]
        receipt=state['host_receipts'].get(rid)
        if isinstance(response,dict) and receipt and receipt['agent_ref']==ref(response.get('task_name')):return True
    fail('SEED_CLOSED_EVENT_CONFLICT')


def recover_spawn_intent(source, *, session, task_path, role, original_host_call_id, evidence_path, cwd, directory=None):
    """中文：显式恢复原记录元数据，不重新创建调用或退款。
    
    English: Explicit original-record metadata recovery, never retry creation or refund.
    """
    from .spawn_recovery import recover
    return recover(source,session=session,task_path=task_path,role=role,original_host_call_id=original_host_call_id,evidence_path=evidence_path,cwd=cwd,directory=directory)
