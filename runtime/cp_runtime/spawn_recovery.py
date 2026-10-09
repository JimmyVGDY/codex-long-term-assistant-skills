"""中文：以只允许追加的原生记录证明元数据，不创建调用或退款。

English: Append-stable native record evidence; metadata only, never spawn/refund.
"""
import json,os,stat
from pathlib import Path
from .routing_contract import exact,fail,ref,integer,identifier,_object,_constant
from .routing_context_contract import safe_file,digest
from .path_identity import path_aliases,path_is_within,same_path
from .common import resolve_codex_home,atomic_write_json
MAX_RECORD=262144
def _parse(raw):return json.loads(raw,object_pairs_hook=_object,parse_constant=_constant)
def _location(path):
    safe=safe_file(Path(path));home=resolve_codex_home()
    if not path_is_within(safe,home/'sessions') or not safe.name.startswith('rollout-') or safe.suffix!='.jsonl':fail('SPAWN_NATIVE_LOCATION')
    canonical=min((str(p) for p in path_aliases(safe)),key=lambda x:(len(x),x))
    return safe,ref(os.path.normcase(canonical))
def _read(path,records,expected=None):
    safe,path_ref=_location(path);before=safe.stat()
    with safe.open('rb') as stream:
        opened=os.fstat(stream.fileno());identity=(opened.st_dev,opened.st_ino)
        if not stat.S_ISREG(opened.st_mode) or opened.st_ino<=0 or (before.st_dev,before.st_ino)!=identity:fail('SPAWN_FILE_IDENTITY')
        header_raw=stream.readline(131073)
        if len(header_raw)>131072 or not header_raw.endswith(b'\n'):fail('SPAWN_HEADER_BOUND')
        header=_parse(header_raw)
        if header.get('type')!='session_meta' or not safe.name.endswith(identifier(header['payload']['id'])+'.jsonl'):fail('SPAWN_NATIVE_HEADER')
        binding={'path_ref':path_ref,'file_ref':ref({'device':identity[0],'inode':identity[1]}),'header_ref':ref(header)}
        if expected and (any(expected[k]!=v for k,v in binding.items()) or opened.st_size<expected['minimum_size']):fail('SPAWN_NATIVE_CHANGED')
        events={};bounded={}
        for label,row in records.items():
            if label not in {'call','result'}:fail('SPAWN_RECORD_LABEL')
            exact(row,{'offset','length'}|({'bytes_sha256'} if expected else set()),'SPAWN_RECORD_FIELDS')
            start=integer(row['offset'],'SPAWN_OFFSET',minimum=len(header_raw),maximum=2**53-1);length=integer(row['length'],'SPAWN_LENGTH',minimum=1,maximum=MAX_RECORD)
            if start+length>opened.st_size:fail('SPAWN_RECORD_TRUNCATED')
            stream.seek(start-1)
            if stream.read(1)!=b'\n':fail('SPAWN_RECORD_START')
            value=stream.read(length)
            if not value.endswith(b'\n') or b'\n' in value[:-1]:fail('SPAWN_RECORD_LINE')
            checksum=digest(value)
            if expected and row['bytes_sha256']!=checksum:fail('SPAWN_RECORD_CHANGED')
            events[label]=_parse(value);bounded[label]={**row,'bytes_sha256':checksum}
        after=os.fstat(stream.fileno());current=safe_file(safe).stat()
        if (after.st_dev,after.st_ino)!=identity or (current.st_dev,current.st_ino)!=identity or after.st_size<opened.st_size or current.st_size<opened.st_size:fail('SPAWN_NATIVE_CHANGED')
    return header,events,{'schema_version':'native-spawn-records/1','path':str(safe),**binding,'minimum_size':opened.st_size,'records':bounded}
def capture_native_records(path,records):
    """中文：不全文件扫描；调用方最多提供原始调用与结果的偏移位置。
    
    English: No full-file scan: caller supplies at most the original call/result offsets.
    """
    if not isinstance(records,dict) or 'call' not in records or len(records)>2:fail('SPAWN_RECORD_SET')
    return _read(path,records)[2]
def verify_native_records(evidence):
    exact(evidence,{'schema_version','path','path_ref','file_ref','header_ref','minimum_size','records'},'SPAWN_EVIDENCE_FIELDS')
    if evidence['schema_version']!='native-spawn-records/1':fail('SPAWN_EVIDENCE_VERSION')
    integer(evidence['minimum_size'],'SPAWN_MINIMUM_SIZE',minimum=1,maximum=2**53-1)
    if not isinstance(evidence['records'],dict) or 'call' not in evidence['records'] or len(evidence['records'])>2:fail('SPAWN_RECORD_SET')
    return _read(evidence['path'],evidence['records'],expected=evidence)
def classify(evidence,*,session,task_path,role,host_call_id,parameters_ref,cwd):
    header,events,binding=verify_native_records(evidence);meta=header['payload']
    if meta['id']!=session or not same_path(Path(meta['cwd']),Path(cwd)) or isinstance(meta.get('source'),dict) and 'subagent' in meta['source']:fail('SPAWN_PARENT_IDENTITY')
    call=events['call'];p=call.get('payload',{})
    from .dispatch_policy import delegation_tool_name
    if call.get('type')!='response_item' or p.get('type')!='function_call' or delegation_tool_name(p.get('name'))!='spawn_agent' or p.get('call_id')!=host_call_id:fail('SPAWN_CALL_BINDING')
    args=_parse(p['arguments']) if isinstance(p.get('arguments'),str) else p.get('arguments')
    if not isinstance(args,dict) or ref(args)!=parameters_ref or '/root/'+str(args.get('task_name'))!=task_path or args.get('agent_type')!=role:fail('SPAWN_PARAMETERS_BINDING')
    result=events.get('result')
    if result is None:return 'UNKNOWN',binding
    if evidence['records']['result']['offset']<=evidence['records']['call']['offset']:fail('SPAWN_RESULT_ORDER')
    output=result.get('payload',{})
    if result.get('type')!='response_item' or output.get('type')!='function_call_output' or output.get('call_id')!=host_call_id:fail('SPAWN_RESULT_BINDING')
    value=output.get('output')
    try:value=_parse(value) if isinstance(value,str) else value
    except (ValueError,TypeError):return 'UNKNOWN',binding
    # 中文：创建形状与现有原生 PostToolUse 适配器完全一致。
    # English: Exact same creation shape as the existing native PostToolUse adapter.
    if isinstance(value,dict) and set(value)=={'task_name'} and value['task_name']==task_path:return 'created',binding
    # 中文：该 Desktop 构建没有已核验的未创建响应形状，不能从错误文字推断。
    # English: This Desktop build has no verified negative creation shape. Never infer it from error text.
    return 'UNKNOWN',binding
def recover(source,*,session,task_path,role,original_host_call_id,evidence_path,cwd,directory=None):
    from . import research_seed as seed,budget_v5 as budget
    from .routing_registry_v4 import _session_lock,_directory as registry_dir
    from .event_v2 import OwnerTokenLock
    from .context_final_v2 import read_bound_transcript
    from .routing_hook_v5 import _header_from_bytes
    identifier(session);identifier(original_host_call_id)
    evidence=seed._read(Path(evidence_path));exact(evidence,{'schema_version','parent','child_path'},'SPAWN_RECOVERY_INPUT')
    if evidence['schema_version']!='spawn-recovery-evidence/1':fail('SPAWN_RECOVERY_VERSION')
    key=seed._index_key(session,task_path,role);indices=seed._index_dir(directory);intent_path=indices/(key+'.intent.json');state_dir=seed._directory(source)
    with OwnerTokenLock(_session_lock(session,directory),timeout=2),OwnerTokenLock(state_dir/'stage',timeout=2),OwnerTokenLock(registry_dir(directory)/'expected-spawn-index',timeout=2):
        intent=seed._read(intent_path)
        research=intent.get('schema_version')=='research-spawn-intent/1'
        if research:
            exact(intent,{'schema_version','source','segment_binding_ref','session_ref','task_path','role','depth','ledger_path','host_call_ref','parameters_ref'},'RESEARCH_RECOVERY_INTENT_FIELDS')
            if intent['depth']!=1 or intent['session_ref']!=ref(session) or intent['task_path']!=task_path or intent['role']!=role or intent['host_call_ref']!=ref(original_host_call_id):fail('SPAWN_INTENT_BINDING')
            from .research_campaign import recovery_context
            plan,segment,state,permits=recovery_context(source,intent,cwd=cwd,session=session,task_path=task_path,role=role);path=Path(intent['ledger_path'])
        else:
            exact(intent,{'schema_version','session_ref','task_path','role','depth','ledger_path','host_call_ref','parameters_ref'},'SPAWN_INTENT_FIELDS')
            if intent['schema_version']!='seed-spawn-intent/1' or intent['depth']!=1 or intent['session_ref']!=ref(session) or intent['task_path']!=task_path or intent['role']!=role or intent['host_call_ref']!=ref(original_host_call_id):fail('SPAWN_INTENT_BINDING')
            _,plan,_,_,_=seed.definition(source);seed._check_host(plan,cwd,session)
            admitted=seed._read(state_dir/'admitted.json')
            if admitted['plan_ref']!=ref(plan):fail('SPAWN_RECOVERY_ADMISSION')
            matches=[s for s in plan['segments'] if same_path(Path(s['ledger_path']),Path(intent['ledger_path']))]
            if len(matches)!=1:fail('SPAWN_RECOVERY_SEGMENT')
            segment=matches[0];_,_,_,_,state=seed._segment_state(source,segment['ordinal']);path=Path(intent['ledger_path'])
            calls=[c for c in segment['calls'] if '/root/'+c['dispatch_key']==task_path]
            permits=[p for p in state['permits'].values() if p['dispatch_ref']==ref(task_path.rsplit('/',1)[-1]) and p['role']==role and p['depth']==1]
            if len(calls)!=1 or len(permits)!=1 or seed.request_core_ref(permits[0]['request'])!=calls[0]['request_ref'] or permits[0]['selection']['approved_profile']!=calls[0]['profile_id']:fail('SPAWN_RECOVERY_PERMIT')
        outcome,native=classify(evidence['parent'],session=session,task_path=task_path,role=role,host_call_id=original_host_call_id,parameters_ref=intent['parameters_ref'],cwd=cwd)
        rid=state['host_dispatches'].get(ref(original_host_call_id));permit=permits[0]
        if rid and state['reservations'][rid]['permit_id']!=permit['permit_id']:fail('SPAWN_RECOVERY_RESERVATION')
        if outcome=='created' and not rid:fail('SPAWN_CREATED_WITHOUT_RESERVATION')
        child_proof=None
        if outcome=='created':
            if not evidence['child_path']:outcome='UNKNOWN'
            else:
                _location(evidence['child_path']);raw,child_binding=read_bound_transcript(Path(evidence['child_path']),header_only=True);child_meta=_parse(raw)['payload']
                verified=_header_from_bytes({'session_id':session,'agent_id':child_meta['id'],'agent_type':role},state,raw,child_binding)
                if verified['task_path']!=task_path or not Path(evidence['child_path']).name.endswith(child_meta['id']+'.jsonl'):fail('SPAWN_RECOVERY_CHILD')
                child_proof={'child_ref':ref(child_meta['id']),'header_ref':verified['header_ref'],'file_binding':child_binding}
        receipt={'schema_version':'spawn-metadata-recovery/1','intent_ref':ref(intent),'source':source,'reservation_id':rid or '', 'outcome':outcome,'native_ref':ref(evidence['parent']),'child':child_proof,'refund':False,'spawn':False}
        journal=seed._state_directory(indices/(key+'.recovery'))
        # 中文：再次验证原记录区间和文件身份，允许追加，不允许改写。
        # English: Verify old original intervals and file identities again; append is allowed, rewrite is not.
        history=list(journal.glob('*.json'))
        if len(history)>64:fail('SPAWN_RECOVERY_HISTORY_BOUND')
        for existing in history:
            prior=seed._read(existing)
            if prior['kind']=='evidence':verify_native_records(prior['parent'])
            elif prior['receipt']['outcome']=='created' and prior['receipt']['child']!=child_proof:fail('SPAWN_RECOVERY_CHILD_CONFLICT')
        receipt_path=journal/('receipt-'+ref(receipt)[7:]+'.json')
        if receipt_path.exists():
            if seed._read(receipt_path)!={'kind':'receipt','receipt':receipt}:fail('SPAWN_RECOVERY_RECEIPT_CONFLICT')
            if outcome=='created':
                index={**intent,'status':'READY','reservation_id':rid,'permit_id':permit['permit_id'],**({} if research else {'segment_ref':ref(segment)}),'repo_path':plan['repo_path']}
                ip=indices/(key+'.json');callkey=ref({'parent_session_ref':ref(session),'host_call_ref':ref(original_host_call_id)})[7:]
                expected_link={'reservation_id':rid,'task_path_ref':ref(task_path),'agent_ref':ref(child_meta['id']),'dispatch_ref':ref(task_path.rsplit('/',1)[-1]),'role':role,'proof_ref':ref(verified)}
                expected_receipt={'reservation_id':rid,'agent_ref':ref(task_path),'disposition':'created','proof_ref':ref({'source':'native-post-tool','root':state['root_binding']['host_session_ref'],'call':ref(original_host_call_id),'agent':ref(task_path)})}
                if seed._read(ip)!=index or seed._read(indices/('call-'+callkey+'.json'))!={'index_key':key,'index_ref':ref(index)} or seed._read(ip.with_suffix('.child.json'))!={**child_proof,'index_ref':ref(index)} or state['host_identity_links'].get(rid)!=expected_link or state['host_receipts'].get(rid)!=expected_receipt:fail('SPAWN_RECOVERY_SEALED_FACT_CONFLICT')
            return receipt
        if state['closed']:fail('SPAWN_RECOVERY_CLOSED')
        journal.mkdir(exist_ok=True)
        seed._immutable(journal/('evidence-'+ref(evidence['parent'])[7:]+'.json'),{'kind':'evidence','parent':evidence['parent']})
        if outcome=='created':
            index={**intent,'status':'READY','reservation_id':rid,'permit_id':permit['permit_id'],**({} if research else {'segment_ref':ref(segment)}),'repo_path':plan['repo_path']}
            ip=indices/(key+'.json');seed._immutable(ip,index)
            callkey=ref({'parent_session_ref':ref(session),'host_call_ref':ref(original_host_call_id)})[7:]
            seed._immutable(indices/('call-'+callkey+'.json'),{'index_key':key,'index_ref':ref(index)})
            seed._immutable(ip.with_suffix('.child.json'),{**child_proof,'index_ref':ref(index)})
            budget.link_host_identity(path,reservation_id=rid,task_path=task_path,agent_id=child_meta['id'],dispatch_key=task_path.rsplit('/',1)[-1],role=role,proof_ref=ref(verified))
            budget.record_receipt(path,host_dispatch_id=original_host_call_id,agent_id=task_path)
        seed._immutable(journal/('receipt-'+ref(receipt)[7:]+'.json'),{'kind':'receipt','receipt':receipt})
        return receipt
