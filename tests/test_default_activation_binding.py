"""中文：激活固定引用只影响新根，不静默改变既有根的目标。

English: Activation pins affect new roots, never silently retarget an existing root.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import budget_v5 as budget
from cp_runtime.routing_context_v5 import build_root_binding,load_snapshot,verify_root
from cp_runtime.routing_contract import RoutingError,ref
import test_routing_v5_context as fixtures


class ActivationBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ContextV5Tests(methodName='runTest')
        self.fixture.setUp()

    def tearDown(self):self.fixture.tearDown()

    def test_activation_reference_is_part_of_immutable_root_identity(self):
        state=budget.read_budget(self.fixture.path)
        original=copy.deepcopy(state['root_binding'])
        envelope=self.fixture.f.envelope
        value=json.loads(envelope.read_text(encoding='utf8'))
        value['routing']['desktop_default_activation']={'path':str(self.fixture.f.root/'activation.json'),
                                                        'definition_ref':ref('new-default')}
        envelope.write_text(json.dumps(value),encoding='utf8')
        _,binding=build_root_binding(envelope,'desktop-session',original['context_runtime'])
        self.assertNotEqual(original['envelope_identity_ref'],binding['envelope_identity_ref'])
        with self.assertRaisesRegex(RoutingError,'ROOT_BINDING_MISMATCH'):
            verify_root(state,cwd=str(self.fixture.f.repo),host_session_id='desktop-session')
        self.assertEqual(original,budget.read_budget(self.fixture.path)['root_binding'])

    def test_production_without_qualification_activation_is_still_denied(self):
        state=budget.read_budget(self.fixture.path)
        state['execution_mode']='PRODUCTION'
        with self.assertRaisesRegex(RoutingError,'PRODUCTION_HOST_COVERAGE_UNQUALIFIED'):
            load_snapshot(state,self.fixture.request,'2030-01-01T00:00:00+00:00',
                          cwd=str(self.fixture.f.repo),host_session_id='desktop-session')
        self.assertFalse(budget.read_budget(self.fixture.path)['reservations'])

    def test_malformed_activation_reference_never_drops_to_the_legacy_root(self):
        state=budget.read_budget(self.fixture.path)
        envelope=self.fixture.f.envelope
        value=json.loads(envelope.read_text(encoding='utf8'))
        value['routing']['desktop_default_activation']={'path':'relative.json','definition_ref':ref('invalid')}
        envelope.write_text(json.dumps(value),encoding='utf8')
        with self.assertRaisesRegex(RoutingError,'ACTIVATION_PATH'):
            build_root_binding(envelope,'desktop-session',state['root_binding']['context_runtime'])


if __name__=='__main__':unittest.main()
