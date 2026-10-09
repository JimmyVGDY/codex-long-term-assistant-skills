"""中文：验证启动选择器和类型边界；宿主授权另行覆盖。

English: Bootstrap selector/type boundary. Host authority is covered separately.
"""
import copy,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import research_bootstrap as boot,research_seed as seed,budget_v5 as budget
from cp_runtime.routing_v4 import select,snapshot_references
from cp_runtime.routing_context_contract import policy_request,runtime,MODE_V2
from cp_runtime.routing_contract import ref
from cp_runtime.common import utc_now
import test_routing_v5_context as fx

class BootstrapBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.f=fx.ContextV5Tests(methodName='runTest');self.f.setUp();self.state=budget.read_budget(self.f.path)
        self.state['root_binding']['context_runtime']['bootstrap_contract']=seed.CONTRACT
        self.state['sources'].update(evaluation_costs='',evaluation_ref='',card_sets=[])
        self.request=copy.deepcopy(self.f.request);self.request['evaluation_case_ref']=ref({'kind':'bootstrap-source-only'})
        cost=copy.deepcopy(self.f.f.evaluation['costs'][0]) if hasattr(self.f.f,'evaluation') else None
        from cp_runtime.routing_context_v4 import read_evaluations
        original=budget.read_budget(self.f.path);costs=read_evaluations(original)[0]['costs']
        self.profile=self.f.selected['approved_profile'];cost=next(copy.deepcopy(c) for c in costs if c['profile_id']==self.profile)
        cost['source_ref']=self.request['evaluation_case_ref']
        self.call={'request_ref':seed.request_core_ref(self.request),'review_material_ref':self.request['evaluation_case_ref'],'profile_id':self.profile,'cost':cost}
        self.segment={'calls':[self.call]};self.plan={'identity':self.request['identity'],'host_session_ref':self.state['root_binding']['host_session_ref']}
        self.state['phase_plan']=copy.deepcopy(self.state['phase_plan'])
        for slot in self.state['phase_plan']['slots']:
            for opt in slot['options']:
                if opt['profile_id']==self.profile:opt['cost_ref']=ref(cost)
        self.patches=[patch.object(seed,'_read',return_value={'routing':{'research_seed':{'source':{},'ordinal':1}}}),
          patch.object(seed,'_segment_state',return_value=(self.plan,{}, {'baseline_sha256':self.request['baseline_sha256']},self.segment,self.state)),
          patch.object(seed,'_check_host'),patch.object(seed,'_valid',return_value=True),
          patch('cp_runtime.routing_context_v4._requirement_evidence',return_value=self.request['evidence'])]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.f.tearDown()
    def snapshot(self):return boot.snapshot(self.state,self.request,utc_now(),cwd=str(self.f.f.repo),host_session_id='desktop-session')
    def test_code_review_selects_without_clean_critical_or_gold(self):
        snap=self.snapshot();req=policy_request(self.request);req['expected']=snapshot_references(snap)
        answer=select(req,snap)
        self.assertEqual('EVALUATION_SELECTED',answer['status']);self.assertEqual([],snap['cards']['qualification'])
        self.assertNotIn('gold_ref',self.call);self.assertNotIn('clean',self.call);self.assertNotIn('critical',self.call)
    def test_statistical_source_cannot_be_imported(self):
        self.state['sources']['evaluation_ref']=ref('statistics')
        with self.assertRaisesRegex(ValueError,'NOT_A_STATISTICAL'):self.snapshot()
    def test_request_core_pins_business_but_not_controller_expected(self):
        changed=copy.deepcopy(self.request);changed['expected']={'dynamic':'controller-only'}
        self.assertEqual(seed.request_core_ref(self.request),seed.request_core_ref(changed))
        changed['business_prompt_sha256']='a'*64
        self.assertNotEqual(seed.request_core_ref(self.request),seed.request_core_ref(changed))
    def test_both_trace_exports_and_trial_grading_deny_bootstrap(self):
        from cp_runtime.routing_evaluation_v5 import record_trial
        with patch.object(budget,'_read_events',return_value=[]),patch.object(budget,'replay',return_value=self.state):
            for fn,args in ((budget.export_trace,(self.f.path,ref('receipt'))),(budget.export_traces,(self.f.path,))):
                with self.assertRaisesRegex(ValueError,'NO_STATISTICAL_GOLD'):fn(*args)
        with patch.object(budget,'read_budget',return_value=self.state):
            with self.assertRaisesRegex(ValueError,'NO_STATISTICAL_GOLD'):
                record_trial(self.f.path,cwd=str(self.f.f.repo),host_session_id='desktop-session',reservation_id='none',repetition=1,response_path=Path('absent'),gold_path=Path('absent'),rubric_path=Path('absent'),transcript_path=Path('absent'),grade={})
    def new_budget(self,worker=False):
        old=budget.read_budget(self.f.path);binding=copy.deepcopy(old['root_binding'])
        binding['context_runtime']={**runtime(ROOT/'hooks/review_context_reader.py',Path(sys.executable),transport_mode=MODE_V2),'bootstrap_contract':seed.CONTRACT}
        sources=copy.deepcopy(old['sources']);sources.update(evaluation_costs='',evaluation_ref='',card_sets=[])
        plan=copy.deepcopy(old['phase_plan'])
        role_capacity=copy.deepcopy(old['role_capacity'])
        if worker:
            plan['slots'][0]['scenario']['role']='worker'
            role_capacity['worker']=old['capacity']['units']
        path=self.f.f.root/('bootstrap-worker.jsonl' if worker else 'bootstrap-new.jsonl')
        return budget.initialize(path,declared_identity={**old['identity'],'budget_id':'bootstrap-types'},root_binding=binding,
            sources=sources,execution_mode='EVALUATION',capacity=old['capacity'],role_capacity=role_capacity,
            phase_capacity=old['phase_capacity'],phase_plan=plan,max_parallel=1,max_depth=1)
    def test_real_temporary_bootstrap_budget_has_no_statistical_sources(self):
        value=self.new_budget();self.assertEqual('',value['sources']['evaluation_costs'])
        self.assertEqual(seed.CONTRACT,value['root_binding']['context_runtime']['bootstrap_contract'])
    def test_bootstrap_rejects_worker_slot(self):
        with self.assertRaisesRegex(ValueError,'REVIEWER_SLOTS_ONLY'):self.new_budget(worker=True)

if __name__=='__main__':unittest.main()
