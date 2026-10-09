"""中文：显式同call通知交付。English: bounded output sets, never a reading claim."""
from __future__ import annotations
import hashlib,json
from .routing_contract import _object,_constant,exact,fail,ref
CONTRACT='same-call-notify/1'
MAX_PAYLOAD=28000
MAX_PARTS=8
MAX_RAW=65536
def enabled(state):return state['root_binding']['context_runtime'].get('delivery_contract')in {CONTRACT,'same-call-notify/2'}
def canonical(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'),sort_keys=True)

def sha(s):return hashlib.sha256(s.encode('utf8')).hexdigest()

def frame(text,index,count,offset,binding,whole):
    return {'schema_version':'context-notify-part/1',**binding,'index':index,'count':count,'byte_offset':offset,'byte_length':len(text.encode('utf8')),'part_sha256':sha(text),'whole_output_sha256':whole,'text':text}

def construct(raw,binding):
    if not raw.endswith('\n') or len(raw.encode('utf8'))>MAX_RAW:raise ValueError('RAW_BOUND')
    parsed=json.loads(raw,object_pairs_hook=_object,parse_constant=_constant)
    if parsed.get('schema_version')!='context-reader-output/1':raise ValueError('RAW_VERSION')
    # 中文：以确定性最坏数量规划；数量值 8 为实际位数提供上界。
    # English: Exact deterministic worst-count planning; count=8 upper-bounds actual count digits.
    parts=[];chunk='';offset=0;whole=sha(raw)
    upper=frame('',MAX_PARTS,MAX_PARTS,MAX_RAW,binding,whole);upper['byte_length']=MAX_RAW
    base_bytes=len(canonical(upper).encode('utf8'));escaped_bytes=0
    for ch in raw:
        increment=len(canonical(ch)[1:-1].encode('utf8'))
        if base_bytes+escaped_bytes+increment>=MAX_PAYLOAD:
            if not chunk:raise ValueError('CHAR_BOUND')
            parts.append(chunk);offset+=len(chunk.encode('utf8'));chunk=ch;escaped_bytes=increment
        else:chunk+=ch;escaped_bytes+=increment
    if chunk:parts.append(chunk)
    if not 1<=len(parts)<=MAX_PARTS:raise ValueError('PART_LIMIT')
    result=[];offset=0
    for i,text in enumerate(parts):
        value=frame(text,i,len(parts),offset,binding,whole);offset+=value['byte_length']
        if len(canonical(value).encode('utf8'))>=MAX_PAYLOAD:raise ValueError('PAYLOAD_BOUND')
        result.append(value)
    summary={'schema_version':'context-notify-summary/1',**binding,'count':len(result),'raw_bytes':len(raw.encode('utf8')),'whole_output_sha256':whole,'part_sha256s':[p['part_sha256'] for p in result]}
    return result,summary

def completion(summary):
    return {**summary,'schema_version':'context-notify-complete/1','context_receipt':sha(canonical(summary))}

JS_HELPERS=r'''
function bytes(s){const a=[];for(const c of s){const n=c.codePointAt(0);if(n<128)a.push(n);else if(n<2048)a.push(192|(n>>6),128|(n&63));else if(n<65536){if(n>=55296&&n<=57343)throw Error("UTF8");a.push(224|(n>>12),128|((n>>6)&63),128|(n&63));}else a.push(240|(n>>18),128|((n>>12)&63),128|((n>>6)&63),128|(n&63));}return a;}
function hash(s){const a=bytes(s),length=a.length*8;const K=[1116352408,1899447441,3049323471,3921009573,961987163,1508970993,2453635748,2870763221,3624381080,310598401,607225278,1426881987,1925078388,2162078206,2614888103,3248222580,3835390401,4022224774,264347078,604807628,770255983,1249150122,1555081692,1996064986,2554220882,2821834349,2952996808,3210313671,3336571891,3584528711,113926993,338241895,666307205,773529912,1294757372,1396182291,1695183700,1986661051,2177026350,2456956037,2730485921,2820302411,3259730800,3345764771,3516065817,3600352804,4094571909,275423344,430227734,506948616,659060556,883997877,958139571,1322822218,1537002063,1747873779,1955562222,2024104815,2227730452,2361852424,2428436474,2756734187,3204031479,3329325298];const H=[1779033703,3144134277,1013904242,2773480762,1359893119,2600822924,528734635,1541459225];a.push(128);while(a.length%64!==56)a.push(0);for(let i=7;i>=0;i--)a.push(Math.floor(length/2**(8*i))&255);const R=(x,n)=>(x>>>n)|(x<<(32-n));for(let o=0;o<a.length;o+=64){const w=[];for(let i=0;i<16;i++)w[i]=((a[o+4*i]<<24)|(a[o+4*i+1]<<16)|(a[o+4*i+2]<<8)|a[o+4*i+3])>>>0;for(let i=16;i<64;i++){const x=w[i-15],y=w[i-2];w[i]=(w[i-16]+(R(x,7)^R(x,18)^(x>>>3))+w[i-7]+(R(y,17)^R(y,19)^(y>>>10)))>>>0;}let [b,c,d,e,f,g,h,j]=H;for(let i=0;i<64;i++){const t=(j+(R(f,6)^R(f,11)^R(f,25))+((f&g)^(~f&h))+K[i]+w[i])>>>0;const u=((R(b,2)^R(b,13)^R(b,22))+((b&c)^(b&d)^(c&d)))>>>0;j=h;h=g;g=f;f=(e+t)>>>0;e=d;d=c;c=b;b=(t+u)>>>0;}[b,c,d,e,f,g,h,j].forEach((v,i)=>H[i]=(H[i]+v)>>>0);}return H.map(v=>v.toString(16).padStart(8,"0")).join("");}
function canonical(v){if(Array.isArray(v))return "["+v.map(canonical).join(",")+"]";if(v!==null&&typeof v==="object")return "{"+Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+canonical(v[k])).join(",")+"}";return JSON.stringify(v);}
'''

def inspect(events,expected_program,binding,expected_raw):
    starts=[i for i,e in enumerate(events) if e.get('type')=='event_msg' and e.get('payload',{}).get('type')=='task_started']
    calls=[(i,e['payload']) for i,e in enumerate(events) if e.get('type')=='response_item' and e['payload'].get('type')=='custom_tool_call']
    outputs=[(i,e) for i,e in enumerate(events) if e.get('type')=='response_item' and e['payload'].get('type')=='custom_tool_call_output']
    finals=[i for i,e in enumerate(events) if e.get('type')=='response_item' and e['payload'].get('role')=='assistant' and e['payload'].get('phase')=='final_answer']
    allowed={'message','agent_message','reasoning','custom_tool_call','custom_tool_call_output'}
    if any(e['payload'].get('type') not in allowed for e in events if e.get('type')=='response_item'):raise ValueError('EXTRA_TOOL')
    if len(starts)!=1 or len(calls)!=1 or len(finals)!=1 or not 3<=len(outputs)<=10:raise ValueError('CALL_SET')
    ci,call=calls[0]
    if call.get('name')!='exec' or call['input'].strip()!=expected_program.strip():raise ValueError('PROGRAM')
    expected_parts,summary=construct(expected_raw,binding);frames=[];part_refs=[];summaries=[];completions=[]
    for j,(i,e) in enumerate(outputs):
        p=e['payload']
        if p['call_id']!=call['call_id'] or not starts[0]<ci<i<finals[0]:raise ValueError('CALL_ORDER')
        if isinstance(p.get('output'),str):
            if p.get('name')!='exec':raise ValueError('NOTIFY_NAME')
            metadata=e.get('metadata',{})
            budget=metadata.get('fallback_token_limit_override')
            text=p.get('output')
            if not isinstance(text,str) or type(budget)!=int or budget<=0:raise ValueError('NOTIFY_BUDGET_MISSING')
            if len(text.encode('utf8'))>=MAX_PAYLOAD or len(text.encode('utf8'))>budget*4:raise ValueError('HISTORY_BOUND')
            frame_value=json.loads(text,object_pairs_hook=_object,parse_constant=_constant)
            if canonical(frame_value)!=text:raise ValueError('CANONICAL_FRAME')
            if frame_value.get('schema_version')=='context-notify-complete/1':
                if frame_value!=completion(summary) or frames!=expected_parts:raise ValueError('COMPLETION_BEFORE_COMPLETE_SET')
                completions.append(frame_value)
            else:
                if completions:raise ValueError('PART_AFTER_COMPLETION')
                frames.append(frame_value);part_refs.append(sha(text))
        else:
            blocks=p['output']
            if not isinstance(blocks,list) or len(blocks)!=2 or any(not isinstance(b,dict) or set(b)!={'type','text'} or b['type']!='input_text' or not isinstance(b['text'],str) for b in blocks):raise ValueError('FINAL_SHAPE')
            budget=e.get('metadata',{}).get('fallback_token_limit_override')
            if type(budget)!=int or budget<=0 or sum(len(b['text'].encode('utf8')) for b in blocks)>budget*4:raise ValueError('FINAL_HISTORY_BOUND')
            terminal=json.loads(blocks[1]['text'],object_pairs_hook=_object,parse_constant=_constant)
            if terminal!=summary:raise ValueError('SUMMARY')
            summaries.append(terminal)
    if len(summaries)!=1:raise ValueError('SUMMARY_COUNT')
    if len(completions)!=1:raise ValueError('COMPLETION_COUNT')
    result_text=events[finals[0]]['payload']['content'][0]['text']
    result=json.loads(result_text,object_pairs_hook=_object,parse_constant=_constant)
    if result.get('context_receipt')!=completion(summary)['context_receipt']:raise ValueError('FINAL_RECEIPT')
    if frames!=expected_parts:raise ValueError('ORDER_COUNT_HASH')
    reconstructed=''.join(p['text'] for p in frames)
    if reconstructed!=expected_raw or sha(reconstructed)!=summary['whole_output_sha256']:raise ValueError('REASSEMBLY')
    return {'schema_version':'notify-tool-surface-prototype/1','single_code_mode_call':True,'reader_calls_in_fixed_program':1,'notify_parts':len(frames),'payload_bytes':[len(canonical(p).encode('utf8')) for p in frames],
      'whole_output_sha256':sha(reconstructed),'part_envelope_sha256s':part_refs,'completion_receipt':completion(summary)['context_receipt'],'native_acceptance':False}

DELIVER_BODY='\nif(response.exit_code!==0||typeof response.output!=="string")throw Error("READER");\nconst raw=response.output;const envelope=JSON.parse(raw);\nif(!raw.endsWith("\\n")||bytes(raw).length>65536||envelope.schema_version!=="context-reader-output/1")throw Error("RAW_BOUND");\nconst whole=hash(raw);const make=(s,index,count,offset)=>({schema_version:"context-notify-part/1",...binding,index,count,byte_offset:offset,byte_length:bytes(s).length,part_sha256:hash(s),whole_output_sha256:whole,text:s});\nconst upper=make("",8,8,65536);upper.byte_length=65536;const baseBytes=bytes(canonical(upper)).length;\nconst chunks=[];let chunk="",offset=0,escapedBytes=0;\nfor(const ch of raw){const increment=bytes(JSON.stringify(ch).slice(1,-1)).length;if(baseBytes+escapedBytes+increment>=28000){if(!chunk)throw Error("CHAR_BOUND");chunks.push(chunk);offset+=bytes(chunk).length;chunk=ch;escapedBytes=increment;}else{chunk+=ch;escapedBytes+=increment;}}\nif(chunk)chunks.push(chunk);if(chunks.length<1||chunks.length>8)throw Error("PART_LIMIT");\n// Validate every complete notification before sending any; no additional reader calls.\nconst parts=[];offset=0;for(let i=0;i<chunks.length;i++){const item=make(chunks[i],i,chunks.length,offset);offset+=item.byte_length;const wire=canonical(item);if(bytes(wire).length>=28000)throw Error("PAYLOAD_BOUND");parts.push({item,wire});}\nfor(const part of parts)notify(part.wire);\nconst summary={schema_version:"context-notify-summary/1",...binding,count:parts.length,raw_bytes:bytes(raw).length,whole_output_sha256:whole,part_sha256s:parts.map(p=>p.item.part_sha256)};\nnotify(canonical({...summary,schema_version:"context-notify-complete/1",context_receipt:hash(canonical(summary))}));\ntext(summary);\n'

def reader_program(base,binding):
    if base.count('text(result); break;')!=1:fail('NOTIFY_READER_PROGRAM_SHAPE')
    first,rest=base.split('\n',1)
    if not first.startswith('// @exec:'):fail('NOTIFY_READER_PROGRAM_DIRECTIVE')
    deliver=DELIVER_BODY.replace('notify(part.wire)','notify(part.wire)')
    function='function deliver(response){'+deliver+'\n}'
    return '// @exec: {"max_output_tokens":2000}\n'+JS_HELPERS+'\nconst binding='+canonical(binding)+';\n'+function+'\n'+rest.replace('text(result); break;','deliver(result); break;')

def binding_for(request):
    return {'bundle_ref':request['context_bundle']['sha256'],'packet_sha256':request['packet_sha256'],'baseline_sha256':request['baseline_sha256']}

def inspect_raw(raw,program,binding,expected_raw_ref):
    from .context_final_v2 import MAX_TRANSCRIPT_BYTES
    if not raw or len(raw)>MAX_TRANSCRIPT_BYTES or not raw.endswith(b'\n'):fail('NOTIFY_TRANSCRIPT_BOUND')
    lines=raw.splitlines()
    if len(lines)>4096 or any(len(x)>2*1024*1024 for x in lines):fail('NOTIFY_TRANSCRIPT_BOUND')
    events=[json.loads(x,object_pairs_hook=_object,parse_constant=_constant) for x in lines]
    parts=[]
    for event in events:
        payload=event.get('payload',{})
        if event.get('type')=='response_item' and payload.get('type')=='custom_tool_call_output' and isinstance(payload.get('output'),str):
            value=json.loads(payload['output'],object_pairs_hook=_object,parse_constant=_constant)
            if value.get('schema_version')=='context-notify-part/1':parts.append(value)
    joined=''.join(part['text'] for part in parts)
    if 'sha256:'+sha(joined)!=expected_raw_ref:fail('NOTIFY_RAW_DELIVERY_MISMATCH')
    proof=inspect(events,program,binding,joined)
    proof.update(schema_version='desktop-tool-surface/2',program_ref=ref(program),raw_output_ref=expected_raw_ref,
       call_ref=ref(next(e['payload']['call_id'] for e in events if e.get('type')=='response_item' and e['payload'].get('type')=='custom_tool_call')),
       output_refs=[ref(e) for e in events if e.get('type')=='response_item' and e['payload'].get('type')=='custom_tool_call_output'],
       history_budgets=[e.get('metadata',{}).get('fallback_token_limit_override') for e in events if e.get('type')=='response_item' and e['payload'].get('type')=='custom_tool_call_output'],
       coverage='bounded-same-call-notify',isolation_claim='logical-readonly')
    proof.pop('native_acceptance',None)
    return proof

def semantic_payload(state,payload):
    if not enabled(state):return payload
    from .context_semantics_v2 import SEMANTIC_FIELDS
    from .routing_contract import hex_digest
    exact(payload,SEMANTIC_FIELDS|{'context_receipt'},'NOTIFY_MODEL_FIELDS')
    hex_digest(payload['context_receipt'])
    return {k:v for k,v in payload.items() if k!='context_receipt'}

def validate_proof(proof):
    from .routing_contract import sha as reference,hex_digest,integer
    fields={'schema_version','single_code_mode_call','reader_calls_in_fixed_program','notify_parts','payload_bytes','whole_output_sha256','part_envelope_sha256s','completion_receipt',
            'program_ref','raw_output_ref','call_ref','output_refs','history_budgets','coverage','isolation_claim'}
    exact(proof,fields,'NOTIFY_PROOF_FIELDS')
    if proof['schema_version']!='desktop-tool-surface/2' or proof['single_code_mode_call'] is not True or proof['reader_calls_in_fixed_program']!=1 or proof['coverage']!='bounded-same-call-notify' or proof['isolation_claim']!='logical-readonly':fail('NOTIFY_PROOF_VERSION')
    count=integer(proof['notify_parts'],'NOTIFY_PART_COUNT',minimum=1,maximum=MAX_PARTS)
    for field in ('program_ref','raw_output_ref','call_ref'):reference(proof[field])
    for field in ('whole_output_sha256','completion_receipt'):hex_digest(proof[field])
    if proof['raw_output_ref']!='sha256:'+proof['whole_output_sha256']:fail('NOTIFY_PROOF_RAW_HASH')
    for name,length in (('payload_bytes',count),('part_envelope_sha256s',count),('output_refs',count+2),('history_budgets',count+2)):
        if not isinstance(proof[name],list) or len(proof[name])!=length:fail('NOTIFY_PROOF_COUNT')
    for size in proof['payload_bytes']:integer(size,'NOTIFY_PROOF_SIZE',minimum=1,maximum=MAX_PAYLOAD-1)
    for value in proof['part_envelope_sha256s']:hex_digest(value)
    for value in proof['output_refs']:reference(value)
    for budget in proof['history_budgets']:integer(budget,'NOTIFY_PROOF_BUDGET',minimum=1)
    return proof
