"""中文：综合开发生命周期夹具，不代表真实 Desktop 或资格证据。

English: Integrated development lifecycle fixtures; not live Desktop or qualification evidence.
"""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import budget_v5 as budget,review_v5 as review
from cp_runtime.common import canonical_json
from cp_runtime.routing_cards import protocol_reference
from cp_runtime.routing_context_contract import MODE,MODE_V2,runtime
from cp_runtime.routing_contract import ref,RoutingError
from cp_runtime.review_vector_transport import CONTRACT,create_input
from cp_runtime.review_vector_contract import DIMENSIONS
import test_isolated_phase_evaluation as phases
import test_routing_v5_context as contexts
import test_review_vector_contract as vectors
import v4_fixtures as fx

class VectorLifecycleTests(unittest.TestCase):
    def make(self,phase='post',scope_change=None):
        material='Synthetic source for a full lifecycle only.'
        source='sha256:'+hashlib.sha256(material.encode()).hexdigest()
        self.scope={d:{'state':'applicable','evidence_refs':[source]} for d in DIMENSIONS}
        if scope_change:scope_change(self.scope)
        self.input=create_input(phase=phase,instructions='Check every applicable dimension.',
                                scope=self.scope,materials={'fixture':material})
        original_experiment=fx.experiment
        original_bundle=contexts.create_bundle
        def experiment(*args,**kwargs):
            value=original_experiment(*args,**kwargs)
            for sample in value['samples']:
                if sample['prompt_ref']==ref('synthetic-prompt-0'):sample['prompt_ref']=ref(self.input)
                sample['case_ref']=fx.case_reference(sample)
            value['case_plan']=sorted({sample['case_ref'] for sample in value['samples']})
            value['protocol_ref']=protocol_reference(value)
            return value
        def bundle(*args,**kwargs):
            kwargs['business_prompt'].write_text(canonical_json(self.input),encoding='utf-8')
            return original_bundle(*args,**kwargs)
        holder=phases.IsolatedPhaseTests(methodName='runTest')
        self.addCleanup(holder.doCleanups)
        with patch.object(fx,'experiment',experiment),patch.object(contexts,'create_bundle',bundle), \
             patch.object(phases,'runtime',lambda *args,**kwargs:runtime(*args,**kwargs,review_contract=CONTRACT)):
            return holder.fixture(phase)

    def test_three_phases_finish_once_and_cannot_enter_legacy_qualification(self):
        from cp_runtime.routing_evaluation_v5 import _native
        for phase in ('pre','post','repair'):
            with self.subTest(phase=phase):
                value=self.make(phase);value.begin();value.read()
                payload,_=vectors.fixture();value.final(payload)
                first=review.record_semantic(value.f.review_dir,value.f.pid,value.response)
                review.record_semantic(value.f.review_dir,value.f.pid,value.response)
                state=budget.read_budget(value.path)
                self.assertEqual(1,len(state['accepted_results']))
                self.assertEqual(1,state['_usage_cache']['resources']['attempts'])
                self.assertEqual(1,len(state['context_finals']))
                result=json.loads(Path(next(iter(first['results'].values()))['result_path']).read_text())
                self.assertEqual(8,result['schema_version']);self.assertEqual(CONTRACT,result['review_contract'])
                self.assertEqual(ref(self.input),result['review_input_ref'])
                self.assertEqual(7,len(result['checked_scope']))
                rid=next(iter(state['reservations']))
                with self.assertRaisesRegex(RoutingError,'VECTOR_LEGACY_QUALIFICATION_DENIED'):
                    _native(state,rid,value.response,value.response,value.response,1)
                review.close(value.f.review_dir,conclusion='PASS')
                budget.close(value.path,outcome='PASS',evidence_ref=ref('synthetic lifecycle only'))
                with self.assertRaisesRegex(RoutingError,'VECTOR_LEGACY_QUALIFICATION_DENIED'):
                    budget.export_traces(value.path)

    def test_incomplete_dimension_keeps_confirmed_blocker_and_prevents_pass(self):
        value=self.make(scope_change=lambda scope:scope.update({DIMENSIONS[-1]:{'state':'unknown','evidence_refs':[]}}))
        value.begin();value.read();payload,_=vectors.fixture()
        payload['dimensions'][0].update(status='blocking',findings=[vectors.finding(DIMENSIONS[0])])
        payload['dimensions'][-1].update(status='incomplete',checked_scope=[],unverified_items=['Missing context'])
        value.final(payload)
        result=review.record_semantic(value.f.review_dir,value.f.pid,value.response)
        saved=json.loads(Path(next(iter(result['results'].values()))['result_path']).read_text())
        self.assertEqual('incomplete',saved['status']);self.assertTrue(saved['findings'][0]['blocking'])
        with self.assertRaisesRegex(RoutingError,'UNRESOLVED_FINDINGS'):
            review.close(value.f.review_dir,conclusion='PASS')
        review.close(value.f.review_dir,conclusion='PARTIAL')

    def test_cancelled_vector_retains_charge_and_original_answer(self):
        value=self.make();value.begin();value.read();payload,_=vectors.fixture()
        value.final(payload,outcome='CANCELLED');original=value.response.read_bytes()
        Path(value.f.request['context_bundle']['path']).write_text('{}',encoding='utf-8')
        result=review.record_failure_accounting(value.f.review_dir,value.f.pid,evidence_ref=ref('cancel evidence'))
        saved=json.loads(Path(next(iter(result['results'].values()))['result_path']).read_text())
        self.assertEqual(8,saved['schema_version']);self.assertEqual('incomplete',saved['status'])
        self.assertEqual(original,value.response.read_bytes())
        self.assertEqual(1,budget.read_budget(value.path)['_usage_cache']['resources']['attempts'])

    def test_legacy_answer_cannot_complete_an_integrated_contract(self):
        value=self.make();value.begin();value.read()
        with self.assertRaisesRegex(RoutingError,'VECTOR_FIELDS'):value.final()
        self.assertFalse(budget.read_budget(value.path)['context_finals'])
        review.record_failure_accounting(value.f.review_dir,value.f.pid,evidence_ref=ref('wrong output shape'))
        self.assertEqual('incomplete',next(iter(budget.read_budget(value.path)['accepted_results'].values()))['status'])

    def test_scope_cannot_reference_undelivered_evidence(self):
        with self.assertRaisesRegex(RoutingError,'VECTOR_SCOPE_SOURCE_NOT_DELIVERED'):
            self.make(scope_change=lambda scope:scope[DIMENSIONS[0]].update(evidence_refs=[ref('absent')]))

    def test_contract_cannot_enable_production_or_old_transport(self):
        value=self.make();state=budget.read_budget(value.path)
        keys=('root_binding','sources','capacity','role_capacity','phase_capacity','phase_plan','max_parallel','max_depth')
        with self.assertRaisesRegex(RoutingError,'VECTOR_DEVELOPMENT_ONLY'):
            budget.initialize(value.path.with_name('forbidden.jsonl'),declared_identity=state['identity'],
                execution_mode='PRODUCTION',**{key:state[key] for key in keys})
        self.assertFalse(value.path.with_name('forbidden.jsonl').exists())
        with self.assertRaisesRegex(RoutingError,'V5_REVIEW_CONTRACT'):
            runtime(ROOT/'hooks/review_context_reader.py',Path(sys.executable),transport_mode=MODE,review_contract=CONTRACT)

if __name__=='__main__':unittest.main()
