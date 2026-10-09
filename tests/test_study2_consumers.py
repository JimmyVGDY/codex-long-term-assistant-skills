"""中文：验证来源 Schema、成本谱系与叶子生产拒绝，不授予原生资格。

English: Source schema/cost lineage/leaf-production refusal; no native qualification.
"""
import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime.qualification_study import bind_evaluation,validate_qualification_source,audit_study
from cp_runtime.routing_cards import validate_bundle
from cp_runtime.routing_contract import ref
import test_research_documents as docs
class Study2ConsumerTests(unittest.TestCase):
    def setUp(self):self.f=docs.ResearchDocumentTests(methodName='runTest');self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def test_costs_are_bound_to_complete_envelope_without_mutating_ancestors(self):
        envelope=self.f.envelopes[0];plan=self.f.plans[0];old=copy.deepcopy(plan);protocol=plan['evaluations'][0]['protocol_ref'];bound=bind_evaluation(envelope,protocol)
        self.assertEqual(old,plan);self.assertTrue(all(c['source_ref']==ref(envelope) for c in bound['costs']))
        expected=copy.deepcopy(plan['evaluations'][0])
        for cost in expected['costs']:cost['source_ref']=ref(envelope)
        self.assertEqual(expected,bound)
    def test_source_schema_is_explicit_and_middle_leaf_production_rejected(self):
        source={'schema_version':'study-qualification-source/2','study':{'path':str(self.f.base/'study.json'),'sha256':ref('study')},'trials':{'path':str(self.f.base/'trials.json'),'sha256':ref('trials')},'campaign':{'path':str(self.f.base/'manifest.json'),'sha256':ref('campaign')},'audit_ref':ref('audit')}
        self.assertTrue(validate_qualification_source(source))
        with self.assertRaises(ValueError):validate_qualification_source({**source,'schema_version':'unknown'})
        with self.assertRaisesRegex(ValueError,'LEAF_AUDIT_ONLY'):validate_bundle({}, {'qualification_source':source},now=self.f.plans[0]['created_at'],production=True)
    def test_full_authority_is_required_before_study2_attempt_audit(self):
        with self.assertRaisesRegex(ValueError,'CAMPAIGN_AUDIT_REQUIRED'):audit_study(self.f.envelopes[0],[],now=self.f.plans[0]['created_at'])
if __name__=='__main__':unittest.main()
