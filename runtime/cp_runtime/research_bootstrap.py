"""中文：代码复核材料不是统计gold。English: bootstrap transport without qualification."""
from pathlib import Path
from .routing_contract import fail,ref,assert_current_window,policy_digest
from .routing_context_contract import policy_request
from .common import repo_snapshot

def snapshot(state,request,now,*,cwd,host_session_id):
    from .research_seed import _read,_segment_state,_check_host,_valid,request_core_ref
    from .routing_context_v4 import _requirement_evidence
    from .routing_cards import validate_cost
    from .budget_v4 import snapshot_budget
    pointer=_read(state['sources']['root_envelope'])['routing']['research_seed']
    p,g,a,segment,checked=_segment_state(pointer['source'],pointer['ordinal'],state=state)
    _check_host(p,cwd,host_session_id)
    if state!=checked or not _valid(g,a,now):fail('BOOTSTRAP_BINDING_EXPIRED')
    if state['execution_mode']!='EVALUATION' or state['sources']['card_sets'] or state['sources']['evaluation_costs'] or state['sources']['evaluation_ref']:
        fail('BOOTSTRAP_NOT_A_STATISTICAL_EVALUATION')
    call=next((c for c in segment['calls'] if c['request_ref']==request_core_ref(request)),None)
    if not call or request['evaluation_case_ref']!=call['review_material_ref'] or request['constraints']['allowed_profiles']!=[call['profile_id']]:fail('BOOTSTRAP_REQUEST_NOT_FROZEN')
    if a['baseline_sha256']!=request['baseline_sha256'] or repo_snapshot(Path(cwd))['sha256']!=request['baseline_sha256']:fail('BOOTSTRAP_BASELINE_CHANGED')
    cost=validate_cost(call['cost'],scenario_ref=ref(request['scenario']))
    # 中文：成本来源是祖先材料引用，不使用包含自身的计划哈希。
    # English: Cost source is an ancestor material ref, never the self-containing plan hash.
    if cost['source_ref']!=call['review_material_ref'] or cost['profile_id']!=call['profile_id']:fail('BOOTSTRAP_COST_SOURCE')
    from .routing_contract import read_document
    capability,_=read_document(Path(state['sources']['capability']))
    if capability.get('root_session_ref')!=p['host_session_ref']:fail('BOOTSTRAP_CAPABILITY_HOST')
    assert_current_window(capability,now)
    evidence=_requirement_evidence(state,policy_request(request),evaluation=None)
    if request['evidence']!=evidence:fail('BOOTSTRAP_EVIDENCE_NOT_VERIFIED')
    return {'schema_version':'routing-input/1','identity':p['identity'],'policy_digest':policy_digest(),
        'execution_mode':'EVALUATION','cards':{'schema_version':'verified-card-set/1','identity':p['identity'],
        'origin':'evaluation','bundle_refs':[ref(p)],'publication_refs':[],'qualification':[],'gains':[],
        'costs':[c['cost'] for c in segment['calls']]},'capability':capability,
        'phase_plan':state['phase_plan'],'budget':snapshot_budget(state),'now':now}

def deny_statistics(state):
    from .research_seed import is_seed
    if is_seed(state):fail('BOOTSTRAP_CODE_REVIEW_HAS_NO_STATISTICAL_GOLD')
