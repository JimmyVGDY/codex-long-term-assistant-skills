"""中文：普通委派在共享 V5 预算中采用冻结策略，不要求复审资格。

English: Frozen ordinary delegation policy in a shared V5 budget; no reviewer qualification.
"""
from __future__ import annotations
from .routing_contract import (ALGORITHM_ID,POLICY_ID,RoutingError,admitted,fail,profile_spec,ref,
                               resource_need,role_for,scenario)
from .routing_phase_plan import capacity_after_choice,current_slot
from .routing_v4 import _validate,snapshot_references,verified_option
from .dispatch_policy import policy as legacy_policy,policy_digest as legacy_digest

CONTRACT='frozen-v3-four-tier/1'
LEGACY_POLICY='reviewer-matrix-v3'

def enabled(runtime,role):
    return runtime.get('ordinary_contract')==CONTRACT and role in {'worker','explorer'}

def cost(profile_id,declared):
    role=role_for(declared['role'])
    if role not in {'worker','explorer'} or profile_id not in admitted(role):
        fail('ORDINARY_PROFILE_NOT_ALLOWED')
    current=profile_spec(profile_id)
    legacy=legacy_policy(LEGACY_POLICY)
    match=next((legacy['profiles'][name] for name in legacy['role_profiles'][role]
                if legacy['profiles'][name]['model']==current['model']
                and legacy['profiles'][name]['effort']==current['effort']),None)
    if not match:fail('ORDINARY_LEGACY_PROFILE_MISMATCH')
    units=match['units']
    return {'profile_id':profile_id,'scenario_ref':ref(scenario(declared)),
            'cost_basis':'frozen-ordinary-v3','measurement':'declared_proxy','plan_cost':units,
            'reserve_units':units,'latency_ms':900000,'source_ref':legacy_digest(LEGACY_POLICY)}

def option(profile_id,declared):
    value=cost(profile_id,declared)
    authority=ref({'contract':CONTRACT,'legacy_policy':legacy_digest(LEGACY_POLICY),
                   'role':declared['role'],'profile_id':profile_id})
    # 中文：旧 option 字段在此保存固定策略依据，不伪造经验资格卡；selection_basis 区分两种来源。
    # English: The historical option field stores fixed-policy authority here, never a
    # fabricated empirical qualification card. selection_basis distinguishes it.
    return {'profile_id':profile_id,'qualification_ref':authority,'cost_ref':ref(value),
            'resources':resource_need(profile_id,value['reserve_units'])}

def select(request,snapshot):
    try:request,snapshot=_validate(dict(request),dict(snapshot))
    except (RoutingError,ValueError,KeyError,TypeError) as exc:
        return {'schema_version':'selection-scorecard/2','status':str(exc) if isinstance(exc,RoutingError) else 'ORDINARY_INPUT_INVALID'}
    declared=request['scenario']
    basis={'schema_version':'selection-scorecard/2','algorithm_id':ALGORITHM_ID,'policy_id':POLICY_ID,
           'policy_digest':request['policy_digest'],'identity':request['identity'],'task_id':request['task_id'],
           'slot_id':request['slot_id'],'baseline_sha256':request['baseline_sha256'],
           'packet_sha256':request['packet_sha256'],'scenario_ref':ref(declared),
           'execution_mode':request['execution_mode'],'snapshots':snapshot_references(snapshot),
           'request_ref':ref(request),'selection_basis':CONTRACT}
    def result(status,**extra):
        value={**basis,'status':status,**extra};value['decision_ref']=ref(value);return value
    if declared['role'] not in {'worker','explorer'}:return result('ORDINARY_ROLE_NOT_ALLOWED')
    if not request['evidence']['ready'] or not request['evidence']['refs']:return result('NEEDS_EVIDENCE')
    if request['constraints']['deadline_ms'] is not None or request['constraints']['strict_wallclock']:
        return result('DEADLINE_OR_SCOPE_UNSUPPORTED')
    requested=request['constraints']['allowed_profiles']
    if not isinstance(requested,list) or len(requested)!=1:return result('EXPLICIT_ORDINARY_PROFILE_REQUIRED')
    name=requested[0]
    if name not in admitted(declared['role']):return result('ORDINARY_PROFILE_NOT_ALLOWED')
    if name not in snapshot['capability']['available_profiles']:return result('DESKTOP_CAPABILITY_UNAVAILABLE')
    try:slot=current_slot(snapshot['phase_plan'],request['slot_id'])
    except RoutingError as exc:return result(str(exc))
    if slot['scenario']!=declared:return result('PHASE_SLOT_SCENARIO_MISMATCH')
    expected=option(name,declared)
    if expected not in slot['options']:return result('ORDINARY_FIXED_COST_REQUIRED')
    if not snapshot['budget']['parallel_available'] or not snapshot['budget']['depth_allowed']:
        return result('BUDGET_OR_PHASE_HOLD_BLOCKED')
    def eligible(other,item):
        if other['scenario']['role'] in {'worker','explorer'}:
            try:return item==option(item['profile_id'],other['scenario']) and item['profile_id'] in snapshot['capability']['available_profiles']
            except RoutingError:return False
        return verified_option(snapshot,other,item,request['execution_mode'])
    witness=capacity_after_choice(snapshot['phase_plan'],request['slot_id'],name,snapshot['budget']['remaining'],
        option_filter=eligible,role_capacity=snapshot['budget']['role_capacity'],
        phase_capacity=snapshot['budget']['phase_capacity'])
    if witness['status']!='FEASIBLE':return result('BUDGET_OR_PHASE_HOLD_BLOCKED')
    spec=profile_spec(name);value=cost(name,declared)
    return result('EVALUATION_SELECTED' if request['execution_mode']=='EVALUATION' else 'CANDIDATE_SELECTED',
        effective_mode='fixed-ordinary',anchor_profile=name,approved_profile=name,
        request_parameters={'model':spec['model'],'reasoning_effort':spec['effort'],'agent_type':declared['role']},
        reserve_units=value['reserve_units'],cost_basis=value['cost_basis'],cost_ref=ref(value),
        qualification_ref=expected['qualification_ref'],gain_ref='',future_witness=witness,
        exclusions={},candidate_profiles=[name])
