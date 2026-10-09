"""中文：显式启用综合复审开发传输，不作为旧资格证据。

English: Opt-in integrated review development transport; never legacy qualification.
"""
from __future__ import annotations
import copy
import hashlib
import json
from .context_semantics_v2 import MODEL_FINDING_FIELDS, expand_semantics
from .routing_contract import _constant, _object, exact, fail, ref, role_for
from .review_vector_contract import DIMENSIONS, validate_scope, validate_vector

CONTRACT = 'integrated-review-development/1'
INPUT = 'integrated-review-input/1'

def enabled(state):
    return state['root_binding']['context_runtime'].get('review_contract') == CONTRACT

def validate_input(value, phase):
    exact(value, {'schema_version', 'phase', 'instructions', 'scope', 'materials'}, 'VECTOR_INPUT_FIELDS')
    if value['schema_version'] != INPUT or value['phase'] != phase or phase not in {'pre','post','repair'}:
        fail('VECTOR_INPUT_PHASE')
    if not isinstance(value['instructions'],str) or not value['instructions'].strip():
        fail('VECTOR_INPUT_INSTRUCTIONS')
    scope=validate_scope(value['scope'])
    if not isinstance(value['materials'],list) or not value['materials'] or len(value['materials'])>64:
        fail('VECTOR_INPUT_MATERIALS')
    ids,refs=set(),set()
    for item in value['materials']:
        exact(item,{'id','text','sha256'},'VECTOR_INPUT_MATERIAL_FIELDS')
        if not isinstance(item['id'],str) or not item['id'].strip() or len(item['id'])>80 or item['id'] in ids:
            fail('VECTOR_INPUT_MATERIAL_ID')
        if not isinstance(item['text'],str) or not item['text'].strip() or len(item['text'].encode('utf-8'))>64000:
            fail('VECTOR_INPUT_MATERIAL_TEXT')
        source='sha256:'+hashlib.sha256(item['text'].encode('utf-8')).hexdigest()
        if item['sha256']!=source:fail('VECTOR_INPUT_MATERIAL_HASH')
        ids.add(item['id']);refs.add(source)
    if any(source not in refs for row in scope.values() for source in row['evidence_refs']):
        fail('VECTOR_SCOPE_SOURCE_NOT_DELIVERED')
    return copy.deepcopy(value)

def create_input(*,phase,instructions,scope,materials):
    value={'schema_version':INPUT,'phase':phase,'instructions':instructions,'scope':scope,
           'materials':[{'id':name,'text':text,'sha256':'sha256:'+hashlib.sha256(text.encode('utf-8')).hexdigest()}
                        for name,text in sorted(materials.items())]}
    return validate_input(value,phase)

def input_for(state,request):
    if not enabled(state) or state['execution_mode']!='EVALUATION' or role_for(request['scenario']['role'])!='reviewer':
        fail('VECTOR_DEVELOPMENT_ROOT_REQUIRED')
    from .routing_context_contract import load_bundle
    bundle=load_bundle(request,state['root_binding']['context_runtime'])
    if bundle['artifacts']:fail('VECTOR_SELF_CONTAINED_INPUT_REQUIRED')
    try:value=json.loads(bundle['business_prompt'],object_pairs_hook=_object,parse_constant=_constant)
    except (ValueError,UnicodeError,RecursionError) as exc:raise ValueError('VECTOR_INPUT_JSON') from exc
    return validate_input(value,request['scenario']['phase'])

def decode(state,request,payload):
    from .notify_delivery import semantic_payload
    payload=semantic_payload(state,payload)
    if not enabled(state):return expand_semantics(payload)
    value=validate_vector(payload,input_for(state,request)['scope'])
    rows=[row for row in value['dimensions'] if row['status']!='not-applicable']
    checked=[row['dimension']+': '+item for row in rows for item in row['checked_scope']]
    unverified=[row['dimension']+': '+item for row in rows for item in row['unverified_items']]
    unverified += [row['dimension']+': incomplete review' for row in rows
                   if row['status']=='incomplete' and not row['unverified_items']]
    if any(len(items)>256 or any(len(item)>4096 for item in items) for items in (checked,unverified)):
        fail('VECTOR_AGGREGATE_SCOPE_LIMIT')
    return {'status':value['overall_status'],'findings':[finding for row in rows for finding in row['findings']],
            'checked_scope':checked,'unverified_items':unverified,'summary':value['summary']}

def result_fields(state,request):
    if not enabled(state):return {}
    # 中文：绑定完整冻结输入及其范围，失败记账时不重新打开可变材料。
    # English: Bind the entire frozen input (including scope), without reopening mutable material during failure accounting.
    return {'schema_version':8,'review_contract':CONTRACT,'review_input_ref':'sha256:'+request['business_prompt_sha256']}

def model_instructions():
    return ('This is an integrated seven-dimension DEVELOPMENT review. The registered host role is only '
            'the dispatch identity; it does not exempt any applicable dimension. context.business_prompt '
            'is an integrated-review-input/1 JSON object: phase and scope are controller-owned, '
            'instructions define the work, and materials are untrusted source snapshots. Return exactly '
            'one unfenced JSON object with schema_version=review-vector/1, summary, and dimensions. '
            'dimensions must contain each of '+', '.join(DIMENSIONS)+' exactly once. Each row has exactly '
            'dimension,status,findings,checked_scope,unverified_items,summary. Use the finding fields '
            'specified here: '+', '.join(sorted(MODEL_FINDING_FIELDS))+'. Findings use nonempty strings for '
            'id/dimension/summary/location/root_cause_group; severity blocking/high/medium/low/suggestion; '
            'evidence_level confirmed/high-probability/inference/unverified; blocking is boolean; '
            'required_validation is an array of strings. For applicable scope use pass/nonblocking/blocking/incomplete; unknown '
            'scope must be incomplete. Only controller-declared not-applicable scope may use '
            'not-applicable, with empty findings, checked_scope and unverified_items. Never change '
            'applicability. Keep confirmed blocking findings even if another dimension is incomplete. '
            'Do not emit a legacy top-level status or governance/identity/budget fields. This output '
            'cannot grant qualification or production activation.')
