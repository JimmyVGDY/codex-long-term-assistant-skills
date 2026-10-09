"""中文：普通固定策略兼容测试；合成卡片不授予真实模型资格。

English: Ordinary fixed-policy compatibility; synthetic cards never qualify real models.
"""
import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime.ordinary_routing_v5 import CONTRACT,cost,option,select
from cp_runtime.routing_contract import RoutingError,ref
from cp_runtime.routing_v4 import snapshot_references, select as reviewer_select
import v4_fixtures as fx
from test_routing_v4_selection_phase import prepared,slot

class OrdinaryRoutingTests(unittest.TestCase):
    def setup_case(self,profile='g56-luna-medium',role='worker'):
        request,snapshot=prepared(fx.bundle(fx.experiment(origin='desktop-evaluation')))
        declared={**fx.SCENARIO,'role':role,'phase':'pre'}
        current=slot('ordinary',[option(profile,declared)],role=role,phase='pre')
        current['scenario']=declared
        future=snapshot['phase_plan']['slots'][0];future['slot_id']='review'
        snapshot['phase_plan']['slots']=[current,future]
        snapshot['capability']['available_profiles']+=['g56-luna-low','g56-luna-medium','g56-terra-medium','g56-terra-high']
        request.update(scenario=declared,slot_id='ordinary')
        request['constraints']['allowed_profiles']=[profile]
        request['expected']=snapshot_references(snapshot)
        return request,snapshot

    def test_original_four_profiles_keep_frozen_costs(self):
        for name,units in [('g56-luna-low',1),('g56-luna-medium',2),('g56-terra-medium',4),('g56-terra-high',8)]:
            request,snapshot=self.setup_case(name)
            choice=select(request,snapshot)
            self.assertEqual('CANDIDATE_SELECTED',choice['status'])
            self.assertEqual(units,choice['reserve_units'])
            self.assertEqual(CONTRACT,choice['selection_basis'])
            self.assertEqual(name,choice['approved_profile'])

    def test_explorer_uses_same_ceiling_without_reviewer_qualification(self):
        request,snapshot=self.setup_case(role='explorer')
        self.assertEqual('CANDIDATE_SELECTED',select(request,snapshot)['status'])
        self.assertFalse(any(q['profile_id'].startswith('g56-') for q in snapshot['cards']['qualification']))

    def test_stronger_model_and_reviewer_role_cannot_use_ordinary_authority(self):
        for name in ('g56-sol-low','g6-luna-low','g6-sol-medium','g6-astra-high'):
            with self.assertRaisesRegex(RoutingError,'PROFILE_NOT_ALLOWED'):
                option(name,{**fx.SCENARIO,'role':'worker'})
        with self.assertRaises(RoutingError):option('g56-luna-low',fx.SCENARIO)

    def test_future_review_allowance_is_preserved(self):
        request,snapshot=self.setup_case('g56-terra-high')
        snapshot['budget']['remaining']['units']=17
        self.assertEqual('BUDGET_OR_PHASE_HOLD_BLOCKED',select(request,snapshot)['status'])
        snapshot['budget']['remaining']['units']=18
        self.assertEqual('CANDIDATE_SELECTED',select(request,snapshot)['status'])

    def test_fabricated_cost_or_policy_reference_is_rejected(self):
        request,snapshot=self.setup_case()
        snapshot['phase_plan']['slots'][0]['options'][0]['resources']['units']=1
        request['expected']=snapshot_references(snapshot)
        self.assertEqual('ORDINARY_FIXED_COST_REQUIRED',select(request,snapshot)['status'])

    def test_explicit_profile_and_truthful_deadline_are_required(self):
        request,snapshot=self.setup_case()
        request['constraints']['allowed_profiles']=None
        self.assertEqual('EXPLICIT_ORDINARY_PROFILE_REQUIRED',select(request,snapshot)['status'])
        request['constraints']['allowed_profiles']=['g56-luna-medium']
        request['constraints']['deadline_ms']=100
        self.assertEqual('DEADLINE_OR_SCOPE_UNSUPPORTED',select(request,snapshot)['status'])

    def test_reviewer_choice_reserves_frozen_ordinary_work_without_borrowing_quality(self):
        request,snapshot=prepared(fx.bundle(fx.experiment(origin='desktop-evaluation')))
        declared={**fx.SCENARIO,'role':'worker','phase':'pre'}
        future=slot('ordinary',[option('g56-luna-medium',declared)],role='worker',phase='pre')
        snapshot['phase_plan']['slots'].append(future)
        snapshot['capability']['available_profiles'].append('g56-luna-medium')
        request['constraints']['allowed_profiles']=['g6-sol-medium']
        request['expected']=snapshot_references(snapshot)
        self.assertEqual('BUDGET_OR_PHASE_HOLD_BLOCKED',reviewer_select(request,snapshot)['status'])
        self.assertEqual('CANDIDATE_SELECTED',reviewer_select(request,snapshot,ordinary_contract=CONTRACT)['status'])
        snapshot['budget']['remaining']['units']=17
        self.assertEqual('BUDGET_OR_PHASE_HOLD_BLOCKED',reviewer_select(request,snapshot,ordinary_contract=CONTRACT)['status'])
        snapshot['budget']['remaining']['units']=18
        self.assertEqual('CANDIDATE_SELECTED',reviewer_select(request,snapshot,ordinary_contract=CONTRACT)['status'])
        future['options'][0]['resources']['units']=1
        request['expected']=snapshot_references(snapshot)
        self.assertEqual('BUDGET_OR_PHASE_HOLD_BLOCKED',reviewer_select(request,snapshot,ordinary_contract=CONTRACT)['status'])

if __name__=='__main__':unittest.main()
