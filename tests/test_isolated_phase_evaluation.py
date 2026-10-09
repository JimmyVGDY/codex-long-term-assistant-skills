"""中文：合成阶段快照不能证明真实模型资格或生产修复。

English: Synthetic phase snapshots never prove live model qualification or production repair.
"""
import copy
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import budget_v4, budget_v5 as budget, review_v5 as review
from cp_runtime.routing_cards import protocol_reference
from cp_runtime.routing_context_contract import ISOLATED_PHASES, ISOLATED_PHASES_V2, MODE, MODE_V2, runtime
from cp_runtime.routing_contract import RoutingError, ref
import test_routing_v4_context as base
import test_routing_v5_context as contexts
import test_routing_context_transport_v2 as transport
import v4_fixtures as fx


class IsolatedPhaseTests(unittest.TestCase):
    def fixture(self,phase,*,opt_in=True,execution_mode='EVALUATION',condition='always',evaluation_contract=None):
        original_experiment=fx.experiment
        original_slot=base.slot
        original_initialize=budget_v4.initialize
        original_v5_initialize=budget.initialize
        def experiment(*args,**kwargs):
            value=original_experiment(*args,**kwargs)
            value['scenario']['phase']=phase
            value['protocol_ref']=protocol_reference(value)
            return value
        def slot(*args,**kwargs):
            value=original_slot(*args,**kwargs)
            value['scenario']['phase']=phase
            value['condition']=condition
            return value
        def initialize(path,**kwargs):
            kwargs['phase_capacity']={key:100 if key==phase else 0 for key in ('pre','post','repair')}
            return original_initialize(path,**kwargs)
        def initialize_v5(path,**kwargs):
            kwargs['execution_mode']=execution_mode
            return original_v5_initialize(path,**kwargs)
        holder=contexts.ContextV5Tests(methodName='runTest')
        try:
            with patch.object(fx,'experiment',experiment),patch.object(base,'slot',slot), \
                 patch.object(budget_v4,'initialize',initialize),patch.object(budget,'initialize',initialize_v5), \
                 patch.object(contexts,'runtime',lambda reader,python:runtime(reader,python,transport_mode=MODE_V2,
                     evaluation_contract=(evaluation_contract or ISOLATED_PHASES) if opt_in else None)):
                holder.setUp()
        except Exception:
            if hasattr(holder,'env'):holder.env.stop()
            if hasattr(holder,'f'):holder.f.tearDown()
            raise
        self.addCleanup(holder.tearDown)
        value=transport.TransportV2Tests(methodName='runTest')
        value.f=holder;value.path=holder.path;value.response=holder.f.root/'native-final.json'
        return value

    def test_pre_post_and_repair_snapshots_have_bound_native_shaped_completion(self):
        for phase in ('pre','post','repair'):
            with self.subTest(phase=phase):
                value=self.fixture(phase)
                value.begin();value.read();value.final()
                state=review.record_semantic(value.f.review_dir,value.f.pid,value.response)
                ledger=budget.read_budget(value.path)
                self.assertEqual(phase,ledger['permits'][value.f.pid]['request']['scenario']['phase'])
                self.assertEqual('SATISFIED',ledger['phase_plan']['slots'][0]['status'])
                self.assertEqual(1,len(ledger['context_finals']))
                self.assertEqual(1,len(state['results']))
                review.close(value.f.review_dir,conclusion='PASS')
                budget.close(value.path,outcome='PASS',evidence_ref=ref('synthetic phase only'))
                traces=budget.export_traces(value.path)
                self.assertEqual(1,len(traces))
                self.assertTrue(next(iter(traces.values()))['native_response_verified'])

    def test_blocking_isolated_pre_and_repair_finish_the_single_evaluation_slot(self):
        finding = {'id': 'scoped-gap', 'dimension': 'scoped review', 'severity': 'blocking',
                   'blocking': True, 'evidence_level': 'confirmed', 'summary': 'A bounded issue.',
                   'location': 'provided material', 'root_cause_group': 'bounded-gap',
                   'required_validation': ['Check the bounded issue.']}
        payload = {'status': 'blocking', 'findings': [finding],
                   'checked_scope': ['provided material'], 'unverified_items': [],
                   'summary': 'The bounded issue needs repair.'}
        for phase in ('pre', 'repair'):
            with self.subTest(phase=phase):
                value = self.fixture(phase,evaluation_contract=ISOLATED_PHASES_V2)
                value.begin(); value.read(); value.final(payload=payload)
                review.record_semantic(value.f.review_dir, value.f.pid, value.response)
                state = budget.read_budget(value.path)
                self.assertEqual('SATISFIED', state['phase_plan']['slots'][0]['status'])
                self.assertEqual('blocking', next(iter(state['accepted_results'].values()))['status'])
                self.assertEqual(1, len(state['reservations']))
        previous_contract = self.fixture('pre')
        previous_contract.begin(); previous_contract.read(); previous_contract.final(payload=payload)
        review.record_semantic(previous_contract.f.review_dir, previous_contract.f.pid, previous_contract.response)
        self.assertEqual('PENDING', budget.read_budget(previous_contract.path)['phase_plan']['slots'][0]['status'])
        ordinary = self.fixture('pre', opt_in=False)
        ordinary.begin(); ordinary.read(); ordinary.final(payload=payload)
        review.record_semantic(ordinary.f.review_dir, ordinary.f.pid, ordinary.response)
        self.assertEqual('PENDING', budget.read_budget(ordinary.path)['phase_plan']['slots'][0]['status'])

    def test_unflagged_repair_still_requires_a_real_post_result(self):
        with self.assertRaisesRegex(RoutingError,'REPAIR_TRANSITION_REQUIRED'):
            self.fixture('repair',opt_in=False)

    def test_phase_evaluation_contract_cannot_initialize_production(self):
        with self.assertRaisesRegex(RoutingError,'PHASE_EVALUATION_ONLY'):
            self.fixture('repair',execution_mode='PRODUCTION')

    def test_phase_snapshots_cannot_claim_production_repair_dependencies(self):
        with self.assertRaisesRegex(RoutingError,'REQUIRES_ISOLATED_REVIEW_SLOTS'):
            self.fixture('repair',condition='repair-after-post')

    def test_old_transport_cannot_enable_isolated_phase_evaluation(self):
        with self.assertRaisesRegex(RoutingError,'EVALUATION_CONTRACT'):
            runtime(ROOT/'hooks/review_context_reader.py',Path(sys.executable),transport_mode=MODE,
                    evaluation_contract=ISOLATED_PHASES)

    def test_internal_init_pins_contract_and_rejects_production_before_writing(self):
        from cp_runtime.routing_cli_v5 import main
        value=self.fixture('repair')
        holder=value.f
        state=budget.read_budget(value.path)
        config=holder.f.root/'phase-init-config.json'
        fields=('sources','execution_mode','capacity','role_capacity','phase_capacity','phase_plan','max_parallel','max_depth')
        declaration={key:state[key] for key in fields}
        declaration['phase_plan']['slots'][0]['status']='PENDING'
        declaration['budget_id']='phase-cli'
        base.write(config,declaration)
        path=holder.f.root/'phase-cli-budget.jsonl'
        args=['routing-v5','init','--config',str(config),'--root-envelope',str(holder.f.envelope),
              '--reader',str(ROOT/'hooks/review_context_reader.py'),'--python',sys.executable,
              '--ledger',str(path),'--host-session-id','desktop-session','--transport-mode',MODE_V2,
              '--evaluation-contract',ISOLATED_PHASES]
        captured=io.StringIO()
        with patch.object(sys,'argv',args),redirect_stdout(captured):main()
        initialized=budget.read_budget(path)
        self.assertEqual(ISOLATED_PHASES,initialized['root_binding']['context_runtime']['evaluation_contract'])
        self.assertFalse(initialized['permits'])
        declaration['execution_mode']='PRODUCTION'
        base.write(config,declaration)
        forbidden=holder.f.root/'production-cli-budget.jsonl'
        args[args.index('--ledger')+1]=str(forbidden)
        captured=io.StringIO()
        with patch.object(sys,'argv',args),redirect_stdout(captured),self.assertRaises(SystemExit) as error:main()
        self.assertEqual(2,error.exception.code)
        self.assertEqual('V5_PHASE_EVALUATION_ONLY',json.loads(captured.getvalue())['reason'])
        self.assertFalse(forbidden.exists())


if __name__=='__main__':unittest.main()
