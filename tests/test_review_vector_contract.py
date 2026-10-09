"""中文：合成结构检查，不作为模型资格研究。

English: Synthetic structural checks, never a model-qualification study.
"""
import copy
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime.review_vector_contract import DIMENSIONS,VERSION,audit_matrix,project_dimensions,validate_vector
from cp_runtime.context_semantics_v2 import expand_semantics
from cp_runtime.routing_contract import RoutingError,ref

def fixture():
    scope={d:{'state':'applicable','evidence_refs':[ref('scoped fixture '+d)]} for d in DIMENSIONS}
    payload={'schema_version':VERSION,'summary':'All declared fixture dimensions checked.',
        'dimensions':[{'dimension':d,'status':'pass','findings':[],'checked_scope':['fixture'],
                       'unverified_items':[],'summary':'Declared fixture checked.'} for d in DIMENSIONS]}
    return payload,scope

def finding(dimension):
    return {'id':'finding-1','dimension':dimension,'severity':'high','evidence_level':'confirmed','blocking':True,
        'summary':'Fixture violation','location':'fixture:1','root_cause_group':'root-cause-1','required_validation':['check fixture']}

def case(phase='post',cluster='one'):
    _,scope=fixture()
    return {'case_ref':ref(phase+cluster),'cluster_id':cluster,'source_problem_ref':ref('problem'+cluster),
        'root_cause_ref':ref('cause'+cluster),'phase':phase,'scope':scope,
        'labels':{d:{'clean':True,'critical':False} for d in DIMENSIONS}}

class VectorTests(unittest.TestCase):
    def test_projection_preserves_one_source_and_original_payload(self):
        payload,scope=fixture();before=copy.deepcopy(payload)
        views=project_dimensions(payload,scope)
        self.assertEqual(7,len(views));self.assertEqual(1,len({v['vector_ref'] for v in views}))
        self.assertTrue(all(not v['independent_model_call'] and not v['qualification_granted'] for v in views))
        self.assertEqual(before,payload)

    def test_missing_and_duplicate_dimension_are_rejected(self):
        payload,scope=fixture()
        payload['dimensions'].pop()
        with self.assertRaisesRegex(RoutingError,'COVERAGE'):validate_vector(payload,scope)
        payload,scope=fixture();payload['dimensions'][-1]=copy.deepcopy(payload['dimensions'][0])
        with self.assertRaisesRegex(RoutingError,'COVERAGE'):validate_vector(payload,scope)

    def test_model_cannot_choose_applicability_or_complete_unknown_scope(self):
        payload,scope=fixture();payload['dimensions'][0]['status']='not-applicable'
        with self.assertRaisesRegex(RoutingError,'FORGERY'):validate_vector(payload,scope)
        payload,scope=fixture();scope[DIMENSIONS[0]]={'state':'unknown','evidence_refs':[]}
        with self.assertRaisesRegex(RoutingError,'FORGERY'):validate_vector(payload,scope)

    def test_not_applicable_needs_parent_evidence_and_does_not_become_pass(self):
        payload,scope=fixture()
        for row in payload['dimensions']:
            scope[row['dimension']]['state']='not-applicable'
            row.update(status='not-applicable',checked_scope=[])
        self.assertEqual('incomplete',validate_vector(payload,scope)['overall_status'])
        scope[DIMENSIONS[0]]['evidence_refs']=[]
        with self.assertRaisesRegex(RoutingError,'EVIDENCE_REQUIRED'):validate_vector(payload,scope)

    def test_missing_evidence_preserves_known_blocker(self):
        payload,scope=fixture()
        payload['dimensions'][0].update(status='blocking',findings=[finding(DIMENSIONS[0])])
        scope[DIMENSIONS[1]]={'state':'unknown','evidence_refs':[]}
        payload['dimensions'][1].update(status='incomplete',unverified_items=['missing dependency'])
        result=validate_vector(payload,scope)
        self.assertEqual('incomplete',result['overall_status']);self.assertTrue(result['has_blocking_findings'])
        self.assertEqual('PENDING',result['dimensions'][0]['findings'][0]['disposition'])

    def test_cross_dimension_finding_and_forged_envelope_fields_are_denied(self):
        payload,scope=fixture();payload['dimensions'][0].update(status='blocking',findings=[finding(DIMENSIONS[1])])
        with self.assertRaisesRegex(RoutingError,'FINDING_IDENTITY'):validate_vector(payload,scope)
        payload,scope=fixture();payload['cost_units']=1
        with self.assertRaisesRegex(RoutingError,'VECTOR_FIELDS'):validate_vector(payload,scope)

    def test_completed_verdict_needs_scope_without_unverified_dependencies(self):
        payload,scope=fixture();payload['dimensions'][0]['checked_scope']=[]
        with self.assertRaisesRegex(RoutingError,'SCOPE_REQUIRED'):validate_vector(payload,scope)
        payload,scope=fixture();payload['dimensions'][0]['unverified_items']=['not inspected']
        with self.assertRaisesRegex(RoutingError,'CANNOT_COMPLETE'):validate_vector(payload,scope)

    def test_old_semantic_consumer_does_not_accept_vector(self):
        payload,_=fixture()
        with self.assertRaisesRegex(RoutingError,'SEMANTIC_FIELDS'):expand_semantics(payload)

    def test_invalid_types_and_total_response_size_fail_closed(self):
        for field in ('dimension','status'):
            payload,scope=fixture();payload['dimensions'][0][field]=[]
            with self.subTest(field=field),self.assertRaises(RoutingError):validate_vector(payload,scope)
        payload,scope=fixture();scope[DIMENSIONS[0]]['evidence_refs']=[{}]
        with self.assertRaises(RoutingError):validate_vector(payload,scope)
        payload,scope=fixture()
        for row in payload['dimensions']:row['checked_scope']=['x'*4096]*40
        with self.assertRaisesRegex(RoutingError,'RESPONSE_SIZE'):validate_vector(payload,scope)

class MatrixTests(unittest.TestCase):
    def test_variants_and_phases_do_not_inflate_independent_clusters(self):
        original=case();duplicate=copy.deepcopy(original);duplicate['case_ref']=ref('another variant')
        report=audit_matrix([original,duplicate,case('pre')])
        for row in report['coverage']:
            expected=0 if row['phase']=='repair' else 1
            self.assertEqual(expected,row['independent_clusters'])
        self.assertFalse(report['coverage_complete']);self.assertFalse(report['qualification_granted'])

    def test_unknown_and_inapplicable_dimensions_do_not_fill_denominators(self):
        value=case();dimension=DIMENSIONS[2]
        value['scope'][dimension]={'state':'unknown','evidence_refs':[]}
        value['labels'][dimension]={'clean':None,'critical':None}
        row=next(r for r in audit_matrix([value])['coverage'] if r['phase']=='post' and r['dimension']==dimension)
        self.assertEqual(0,row['clean']);self.assertEqual(1,row['unknown_clusters']);self.assertEqual(252,row['gaps']['clean'])

    def test_problem_aliases_and_conflicting_variant_labels_are_rejected(self):
        first=case();second=case(cluster='two');second['source_problem_ref']=first['source_problem_ref']
        with self.assertRaisesRegex(RoutingError,'CLUSTER_ALIAS'):audit_matrix([first,second])
        second=copy.deepcopy(first);second['case_ref']=ref('bad second variant')
        second['labels'][DIMENSIONS[0]]['clean']=False
        with self.assertRaisesRegex(RoutingError,'VARIANT_SELECTION'):audit_matrix([first,second])

if __name__=='__main__':unittest.main()
