"""中文：新增研究专用、可归属的负面结果，不构成正向传输证明。

English: New research-only attributable negatives, never a positive transport attestation.
"""
import json
import copy
from pathlib import Path
from .routing_contract import exact,fail,ref,_object,_constant
from . import budget_v5 as budget
from .context_final_v2 import read_bound_transcript,extract_final
from .routing_hook_v5 import _header_from_bytes,_grant_path
from .context_tool_surface import reader_program
from .notify_wire import enabled,validate_grant,MAX_GRANT
from . import notify_delivery
from .routing_context_contract import safe_file
from .routing_contract import read_document
def delivery_before_extra(events,state,rid,request,grant_path,fixed_id,after,before):
    """中文：只验证原始输出，不投影、不注入最终回答，也不要求补造回执。
    
    English: Verify original outputs only: no projection, injected final or receipt requirement.
    """
    grant,_=read_document(safe_file(Path(grant_path)),maximum=MAX_GRANT);validate_grant(grant,notify_delivery.binding_for(request));delivery=state['context_wire_deliveries'].get(rid)
    if grant['reservation_id']!=rid or not delivery or delivery!={'reservation_id':rid,'call_ref':grant['call_ref'],'raw_output_ref':'sha256:'+grant['output_sha256'],'wire_output_ref':'sha256:'+grant['wire_sha256'],'raw_bytes':grant['raw_bytes'],'wire_bytes':grant['wire_bytes'],'delivery_contract':'same-call-notify/2'}:fail('RESEARCH_NEGATIVE_WIRE_BINDING')
    wire=json.loads(grant['wire'],object_pairs_hook=_object,parse_constant=_constant);expected=[notify_delivery.canonical(v) for v in wire['notifications']];notifications=[];summaries=[];refs=[]
    for i,e in enumerate(events):
        p=e.get('payload',{})
        if e.get('type')!='response_item' or p.get('type')!='custom_tool_call_output' or p.get('call_id')!=fixed_id:continue
        if not after<i<before:fail('RESEARCH_NEGATIVE_OUTPUT_ORDER')
        limit=e.get('metadata',{}).get('fallback_token_limit_override');output=p.get('output')
        if type(limit)!=int or limit<=0:fail('RESEARCH_NEGATIVE_BUDGET')
        if isinstance(output,str):
            if p.get('name')!='exec' or len(output.encode('utf8'))>=28000 or len(output.encode('utf8'))>limit*4:fail('RESEARCH_NEGATIVE_FRAME_BOUND')
            notifications.append(output)
        else:
            if not isinstance(output,list) or len(output)!=2 or any(not isinstance(b,dict) or set(b)!={'type','text'} or b['type']!='input_text' or not isinstance(b['text'],str) for b in output) or sum(len(b['text'].encode('utf8')) for b in output)>limit*4:fail('RESEARCH_NEGATIVE_SUMMARY_SHAPE')
            summaries.append(json.loads(output[1]['text'],object_pairs_hook=_object,parse_constant=_constant))
        refs.append(ref(e))
    if notifications!=expected or summaries!=[wire['summary']] or len(refs)!=len(expected)+1:fail('RESEARCH_NEGATIVE_DELIVERY_SET')
    return {'schema_version':'research-prior-delivery-proof/1','raw_output_ref':delivery['raw_output_ref'],'wire_output_ref':delivery['wire_output_ref'],'output_refs':refs,'positive_attestation':False}
def boundary_proof(path,state,rid,transcript,*,prefix_bytes=None):
    from .research_campaign import SUPPORTED_CONTRACTS
    if state['root_binding']['context_runtime'].get('research_contract') not in SUPPORTED_CONTRACTS or not enabled(state):fail('RESEARCH_NEGATIVE_ONLY')
    attempt=state['reservations'].get(rid);receipt=state['host_receipts'].get(rid)
    if not attempt or attempt['state']!='COMPLETED' or not receipt or receipt['disposition']!='created' or not state['root_host_binding'] or rid not in state['context_wire_deliveries']:fail('RESEARCH_NEGATIVE_CREATION_REQUIRED')
    permit=state['permits'][attempt['permit_id']];raw,file_binding=read_bound_transcript(Path(transcript),prefix_bytes=prefix_bytes);events=[json.loads(line,object_pairs_hook=_object,parse_constant=_constant) for line in raw.splitlines()];header=events[0]['payload'];spawn=header['source']['subagent']['thread_spawn'];child=header['id'];session=spawn['parent_thread_id']
    linked=_header_from_bytes({'session_id':session,'agent_id':child,'agent_type':permit['role']},state,raw.splitlines()[0],file_binding)
    if ref(linked)!=state['host_identity_links'][rid]['proof_ref'] or ref(child)!=budget.effective_agent_ref(state,rid) or set(state['host_observations'].get(ref(child),{}))!={'start','stop'}:fail('RESEARCH_NEGATIVE_FILE_IDENTITY')
    finals=[e for e in events if e.get('type')=='response_item' and e['payload'].get('role')=='assistant' and e['payload'].get('phase')=='final_answer']
    final_proof=None
    if len(finals)==1:
        content=finals[0]['payload'].get('content')
        if isinstance(content,list) and len(content)==1 and content[0].get('type')=='output_text' and isinstance(content[0].get('text'),str):
            final_proof={'response_ref':'sha256:'+notify_delivery.sha(content[0]['text']),'final_event_ref':ref(finals[0])}
    calls=[(i,e['payload']) for i,e in enumerate(events) if e.get('type')=='response_item' and e['payload'].get('type') in {'custom_tool_call','function_call'}]
    program=reader_program(path,state,permit['request'],session,child)
    if len(calls)<2 or calls[0][1].get('type')!='custom_tool_call' or calls[0][1].get('name')!='exec' or calls[0][1].get('input','').strip()!=program.strip():fail('RESEARCH_NEGATIVE_FIXED_READER')
    fixed_id=calls[0][1]['call_id'];outputs=[i for i,e in enumerate(events) if e.get('type')=='response_item' and e['payload'].get('type')=='custom_tool_call_output' and e['payload'].get('call_id')==fixed_id]
    if not outputs or any(i<=max(outputs) for i,_ in calls[1:]):fail('RESEARCH_NEGATIVE_DELIVERY_ORDER')
    extra_ids=[c['call_id'] for _,c in calls[1:]]
    denied=[e['data'] for e in budget._read_events(path) if e['event_type']=='CONTEXT_RECOVERY' and e['data']['reservation_id']==rid and e['data']['action']=='DENIED' and e['data']['reason']=='CONTEXT_V2_ONLY_FIXED_READER']
    if any(not any(d['call_ref']==ref(call) and d['agent_ref']==ref(child) for d in denied) for call in extra_ids):fail('RESEARCH_NEGATIVE_DENIAL_REQUIRED')
    denied=[next(d for d in denied if d['call_ref']==ref(call) and d['agent_ref']==ref(child)) for call in extra_ids]
    delivered=delivery_before_extra(events,state,rid,permit['request'],_grant_path(path,session,child),fixed_id,calls[0][0],calls[1][0])
    relevant=max([i for i,_ in calls]+outputs+[i for i,e in enumerate(events) if e in finals]);prefix=b''.join(raw.splitlines(keepends=True)[:relevant+1])
    return {'schema_version':'research-model-boundary-negative/1','reservation_id':rid,'failure_kind':'MODEL_BOUNDARY_VIOLATION','passed':False,'boundary_failure':True,'original_transcript_ref':ref(prefix.decode('utf8')),'prefix_bytes':len(prefix),'file_binding':file_binding,'native_final':final_proof,'final_event_refs':[ref(e) for e in finals],'prior_delivery_proof_ref':ref(delivered),'extra_call_refs':[ref(c) for _,c in calls[1:]],'denial_refs':[ref(d) for d in denied],'positive_attestation':False}
FIELDS={'schema_version','identity','reservation_id','accepted_result_ref','protocol_ref','case_ref','profile_id','repetition','response_ref','gold_ref','rubric_ref','grade','finalizer','negative_proof_ref','negative_prefix_bytes'}
def _material(state,rid,response,gold,rubric,repetition):
    from .routing_context_v4 import read_evaluation
    from .routing_evaluation_v4 import file_reference,trial_packet
    from .routing_contract import integer
    permit=state['permits'][state['reservations'][rid]['permit_id']];request=permit['request'];evaluation=read_evaluation(state,case_ref=request['evaluation_case_ref']);case=next(c for c in evaluation['cases'] if c['case_ref']==request['evaluation_case_ref']);profile=permit['selection']['approved_profile'];integer(repetition,'RESEARCH_REPETITION',minimum=1,maximum=evaluation['repetitions'])
    if request['packet_sha256']!=trial_packet(case['case_ref'],profile,repetition) or request['business_prompt_sha256']!=case['prompt_ref'][7:] or file_reference(gold)!=case['gold_ref'] or file_reference(rubric)!=evaluation['rubric_ref']:fail('RESEARCH_NEGATIVE_MATERIAL_BINDING')
    return evaluation,case,permit,file_reference(response) if response is not None else None
def _response_ref(proof,response):
    if proof['native_final'] is None:
        if response is not None:fail('RESEARCH_NEGATIVE_NO_FINAL_PATH')
        return ref({'schema_version':'research-model-final-unbound/1','transcript_ref':proof['original_transcript_ref'],'final_event_refs':proof['final_event_refs']})
    from .routing_evaluation_v4 import file_reference
    value=file_reference(response)
    if value!=proof['native_final']['response_ref']:fail('RESEARCH_NEGATIVE_FINAL_CHANGED')
    return value
def record_negative(path,*,reservation_id,response_path,gold_path,rubric_path,transcript_path,repetition,cwd):
    from .routing_evaluation_v4 import file_reference
    from .common import atomic_write_json,require_external_state,repo_snapshot
    from .event_v2 import OwnerTokenLock
    state=budget.read_budget(path);rid=reservation_id;proof=boundary_proof(path,state,rid,transcript_path);evaluation,case,permit,response_ref=_material(state,rid,response_path,gold_path,rubric_path,repetition)
    response_ref=_response_ref(proof,response_path)
    accepted=state['accepted_results'].get(rid)
    if not accepted or accepted['status']!='incomplete' or proof['native_final'] is not None and accepted['response_ref']!=response_ref or repo_snapshot(Path(cwd))['sha256']!=permit['request']['baseline_sha256']:fail('RESEARCH_NEGATIVE_PARENT_ACCOUNTING')
    value={'schema_version':'routing-trial-result/3','identity':copy.deepcopy(state['identity']),'reservation_id':rid,'accepted_result_ref':accepted['result_ref'],'protocol_ref':evaluation['protocol_ref'],'case_ref':case['case_ref'],'profile_id':permit['selection']['approved_profile'],'repetition':repetition,'response_ref':response_ref,'gold_ref':case['gold_ref'],'rubric_ref':evaluation['rubric_ref'],'grade':{'passed':False,'false_block':False,'critical_failure':False,'boundary_failure':True},'finalizer':'parent:'+state['identity']['task_id'],'negative_proof_ref':ref(proof),'negative_prefix_bytes':proof['prefix_bytes']}
    output=Path(path).parent/'qualification-grades'/(ref({'identity':state['identity'],'reservation_id':rid})[7:]+'.json');require_external_state(output,Path(cwd));output.parent.mkdir(parents=True,exist_ok=True)
    with OwnerTokenLock(output,timeout=2):
        if output.exists():
            from .routing_contract import read_document
            if read_document(output)[0]!=value:fail('RESEARCH_NEGATIVE_IMMUTABLE')
        else:atomic_write_json(output,value)
    return {'result_path':str(output),'result_ref':file_reference(output),'model_passed':False,'reservation_id':rid}
def read_negative(source,state,trial,events):
    from .routing_contract import integer
    from .common import parse_iso
    exact(trial,FIELDS,'RESEARCH_NEGATIVE_TRIAL_FIELDS')
    if trial['schema_version']!='routing-trial-result/3' or not state['closed'] or trial['identity']!=state['identity'] or trial['finalizer']!='parent:'+state['identity']['task_id']:fail('RESEARCH_NEGATIVE_PARENT')
    rid=trial['reservation_id'];path=Path(source['ledger']);proof=boundary_proof(path,state,rid,source['transcript'],prefix_bytes=trial['negative_prefix_bytes']);response=Path(source['response']) if source['response'] else None;evaluation,case,permit,response_ref=_material(state,rid,response,Path(source['gold']),Path(source['rubric']),trial['repetition']);response_ref=_response_ref(proof,response);accepted=state['accepted_results'].get(rid)
    if not accepted or accepted['status']!='incomplete' or trial['accepted_result_ref']!=accepted['result_ref'] or proof['native_final'] is not None and accepted['response_ref']!=response_ref or trial['negative_proof_ref']!=ref(proof) or any(trial[k]!=v for k,v in {'protocol_ref':evaluation['protocol_ref'],'case_ref':case['case_ref'],'profile_id':permit['selection']['approved_profile'],'response_ref':response_ref,'gold_ref':case['gold_ref'],'rubric_ref':evaluation['rubric_ref']}.items()) or trial['grade']!={'passed':False,'false_block':False,'critical_failure':False,'boundary_failure':True}:fail('RESEARCH_NEGATIVE_BINDING')
    trace=budget._trace_from_state(state,rid,evaluation);trace.update(schema_version='desktop-evaluation-trace/5',response_ref=response_ref,native_final_ref='',result_status='boundary-invalid',native_response_verified=False,negative_proof_ref=ref(proof),failure_kind=proof['failure_kind'],negative_verified=True)
    starts=[e['recorded_at'] for e in events if e['event_type']=='DISPATCH_RESERVED' and e['data']['reservation_id']==rid];stops=[e['recorded_at'] for e in events if e['event_type']=='HOST_OBSERVED' and e['data']['agent_ref']==trace['task_ref'] and e['data']['phase']=='stop']
    if len(starts)!=1 or len(stops)!=1:fail('RESEARCH_NEGATIVE_TIMING')
    latency=round((parse_iso(stops[0])-parse_iso(starts[0])).total_seconds()*1000);integer(latency,'RESEARCH_NEGATIVE_DURATION',maximum=604800000)
    sample={'sample_id':'trial-'+ref({'receipt':trace['receipt_ref'],'identity':state['identity']})[7:],**case,**trial['grade'],'repetition':trial['repetition'],**{k:trace[k] for k in ('task_ref','call_ref','receipt_ref','response_ref','profile_id')},'cost_units':permit['selection']['reserve_units'],'latency_ms':latency}
    return sample,trace,evaluation
