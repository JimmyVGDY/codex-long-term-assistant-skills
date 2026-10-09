"""中文：版本化的可信传输，不由模型编写加密逻辑或增加读取器。

English: Versioned trusted wire; no model-authored cryptography or extra reader.
"""
import json
from pathlib import Path
from . import notify_delivery as old
from .routing_contract import exact,fail,ref,integer,sha as reference
from .routing_context_contract import safe_file
CONTRACT='same-call-notify/2'
MAX_WIRE=196608
MAX_GRANT=524288
FIELDS={'schema_version','delivery_contract','raw_output_ref','notifications','summary'}
EXTRA={'delivery_contract','wire','wire_sha256','wire_bytes','raw_bytes'}
def enabled(state):return state['root_binding']['context_runtime'].get('delivery_contract')==CONTRACT
def pack(raw,binding):
    parts,summary=old.construct(raw,binding)
    wire=old.canonical({'schema_version':'context-notify-wire/1','delivery_contract':CONTRACT,'raw_output_ref':'sha256:'+old.sha(raw),'notifications':parts+[old.completion(summary)],'summary':summary})+'\n'
    if len(wire.encode('utf8'))>MAX_WIRE:fail('WIRE_BOUND')
    return wire
def add_grant(grant,binding):
    wire=pack(grant['output'],binding)
    return {**grant,'delivery_contract':CONTRACT,'wire':wire,'wire_sha256':old.sha(wire),'wire_bytes':len(wire.encode('utf8')),'raw_bytes':len(grant['output'].encode('utf8'))}
def validate_grant(grant,binding):
    exact(grant,{'output','output_sha256','reservation_id','call_ref','context_profile'}|EXTRA,'WIRE_GRANT_FIELDS')
    if grant['context_profile']!='bounded-review-64k/1' or grant['delivery_contract']!=CONTRACT:fail('WIRE_GRANT_VERSION')
    if not isinstance(grant['output'],str) or not isinstance(grant['wire'],str):fail('WIRE_GRANT_TEXT')
    integer(grant['wire_bytes'],'WIRE_LENGTH',minimum=1,maximum=MAX_WIRE);integer(grant['raw_bytes'],'RAW_LENGTH',minimum=1,maximum=65536)
    if len(old.canonical(grant).encode('utf8'))>MAX_GRANT:fail('WIRE_GRANT_BOUND')
    if len(grant['wire'].encode('utf8'))!=grant['wire_bytes'] or len(grant['output'].encode('utf8'))!=grant['raw_bytes'] or old.sha(grant['output'])!=grant['output_sha256'] or old.sha(grant['wire'])!=grant['wire_sha256']:fail('WIRE_GRANT_HASH')
    if grant['wire']!=pack(grant['output'],binding):fail('WIRE_RAW_BINDING')
    return grant
BODY='''function deliver(response){
if(response.exit_code!==0||typeof response.output!=="string")throw Error("READER");
const w=JSON.parse(response.output);
if(w.schema_version!=="context-notify-wire/1"||w.delivery_contract!=="same-call-notify/2"||!Array.isArray(w.notifications)||w.notifications.length<2||w.notifications.length>9)throw Error("WIRE");
for(const part of w.notifications){if(part===null||Array.isArray(part)||typeof part!=="object")throw Error("PART");}
for(const part of w.notifications)notify(JSON.stringify(part));
text(w.summary);
}
'''
def reader_program(base):
    if base.count('text(result); break;')!=1:fail('WIRE_PROGRAM_SHAPE')
    first,rest=base.split('\n',1)
    if not first.startswith('// @exec:'):fail('WIRE_PROGRAM_DIRECTIVE')
    return '// @exec: {"max_output_tokens":2000}\n'+BODY+rest.replace('text(result); break;','deliver(result); break;')
def inspect_delivery(raw,program,request,state,rid,grant_path):
    from .routing_contract import read_document
    grant,_=read_document(safe_file(Path(grant_path)),maximum=MAX_GRANT)
    validate_grant(grant,old.binding_for(request))
    delivery=state.get('context_wire_deliveries',{}).get(rid)
    if not delivery or grant['reservation_id']!=rid or delivery!={'reservation_id':rid,'call_ref':grant['call_ref'],'raw_output_ref':'sha256:'+grant['output_sha256'],'wire_output_ref':'sha256:'+grant['wire_sha256'],'raw_bytes':grant['raw_bytes'],'wire_bytes':grant['wire_bytes'],'delivery_contract':CONTRACT}:fail('WIRE_LEDGER_BINDING')
    proof=old.inspect_raw(raw,program,old.binding_for(request),delivery['raw_output_ref'])
    proof.update(schema_version='desktop-tool-surface/3',delivery_contract=CONTRACT,wire_output_ref=delivery['wire_output_ref'],wire_bytes=delivery['wire_bytes'])
    return validate_proof(proof)
def validate_proof(proof):
    extra={'delivery_contract','wire_output_ref','wire_bytes'}
    if proof.get('schema_version')!='desktop-tool-surface/3' or proof.get('delivery_contract')!=CONTRACT:fail('WIRE_PROOF_VERSION')
    old.validate_proof({**{k:v for k,v in proof.items() if k not in extra},'schema_version':'desktop-tool-surface/2'})
    reference(proof['wire_output_ref']);integer(proof['wire_bytes'],'WIRE_PROOF_BYTES',minimum=1,maximum=MAX_WIRE)
    return proof
