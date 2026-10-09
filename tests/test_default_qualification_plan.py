"""中文：仅使用结构性负面夹具，不代表真实原生模型资格。

English: Structural negative fixtures only; never real native model qualification.
"""
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import default_qualification_plan as matrix
from cp_runtime.routing_contract import RoutingError,policy_digest,ref


class MatrixTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.value={'schema_version':'default-qualification-plan/1',
            'identity':{'project_id':'fixture','repo_fingerprint':ref('repo')},'policy_digest':policy_digest(),
            'candidate_payload_digest':'a'*64,'created_at':'2030-01-01T00:00:00+00:00',
            'selected':[],'screening_sources':[{'study':{},'trials':{},'audit_ref':ref('synthetic')}],
            'review_evidence':{'path':str(self.root/'review.json'),'sha256':ref('synthetic')}}
        self.experiments=[];self.qualified={}
        for i,(role,phase) in enumerate(sorted(matrix.expected_cells())):
            scenario={'role':role,'phase':phase,'semantic':1,'reasoning':2,'risk':2,'tags':['bounded_logic'],
                'context_bucket':'bounded-review-64k','tools_profile':'desktop-context-reader-64k-v1',
                'speed_mode':'standard','prompt_sha256':ref('rubric')[7:]}
            row={'role':role,'phase':phase,'scenario_ref':ref(scenario),'protocol_ref':ref('protocol-'+str(i)),
                'baseline_profile':'g56-sol-medium','selected_profile':'g6-sol-medium'}
            self.value['selected'].append(row);self.qualified[row['scenario_ref']]=['g6-sol-medium']
            self.experiments.append({'protocol_ref':row['protocol_ref'],'scenario':scenario,
                'baseline_profile':'g56-sol-medium','comparisons':[{'anchor':'g56-sol-medium','challenger':'g6-sol-medium'}],
                'samples':[{'profile_id':'g56-sol-medium'},{'profile_id':'g6-sol-medium'}]})
        self.study={'identity':self.value['identity'],'created_at':'2030-01-01T01:00:00+00:00',
            'evaluations':[{'protocol_ref':e['protocol_ref'],'cases':[{'prompt_ref':ref('holdout-prompt')}]} for e in self.experiments],
            'independence':{'cases':[{'cluster_id':'holdout','source_problem_ref':ref('holdout'),'root_cause_ref':ref('holdout-cause')}]}}
        source=self.root/'study.json';source.write_text(json.dumps(self.study),encoding='utf8')
        import hashlib
        pointer={'path':str(source),'sha256':'sha256:'+hashlib.sha256(source.read_bytes()).hexdigest()}
        for e in self.experiments:e['qualification_source']={'study':pointer}
        self.checked={'plan':self.value,'screening_problems':{('problem',ref('development'))}}

    def tearDown(self):self.temp.cleanup()

    def test_complete_role_phase_shape_is_required(self):
        self.assertEqual(21,len(matrix.validate_plan(self.value)['selected']))
        for role,phase in matrix.expected_cells():
            invalid=copy.deepcopy(self.value)
            invalid['selected']=[r for r in invalid['selected'] if (r['role'],r['phase'])!=(role,phase)]
            with self.subTest(role=role,phase=phase),self.assertRaisesRegex(RoutingError,'MATRIX_INCOMPLETE'):matrix.validate_plan(invalid)

    def test_duplicate_cell_or_nonreviewer_or_wrong_generation_rejects(self):
        for field,value in [('role','worker'),('phase','unknown'),('selected_profile','g56-sol-medium'),('baseline_profile','g6-luna-medium')]:
            invalid=copy.deepcopy(self.value);invalid['selected'][0][field]=value
            with self.subTest(field=field),self.assertRaises(RoutingError):matrix.validate_plan(invalid)
        invalid=copy.deepcopy(self.value);invalid['selected'][-1]=copy.deepcopy(invalid['selected'][0])
        with self.assertRaisesRegex(RoutingError,'MATRIX_INCOMPLETE'):matrix.validate_plan(invalid)

    def test_confirmation_requires_exact_complete_frozen_candidate(self):
        matrix.verify_confirmation(self.checked,self.experiments,self.qualified)
        with self.assertRaisesRegex(RoutingError,'CONFIRMATION_MATRIX_INCOMPLETE'):
            matrix.verify_confirmation(self.checked,self.experiments[:-1],self.qualified)
        invalid=copy.deepcopy(self.experiments);invalid[0]['comparisons'][0]['challenger']='g6-astra-high'
        with self.assertRaisesRegex(RoutingError,'FROZEN_COMPARISON_CHANGED'):
            matrix.verify_confirmation(self.checked,invalid,self.qualified)
        invalid=copy.deepcopy(self.experiments);invalid[0]['samples'].append({'profile_id':'g6-luna-low'})
        with self.assertRaisesRegex(RoutingError,'FROZEN_COMPARISON_CHANGED'):
            matrix.verify_confirmation(self.checked,invalid,self.qualified)

    def test_development_problem_overlap_cannot_become_holdout(self):
        self.checked['screening_problems']={('problem',ref('holdout'))}
        with self.assertRaisesRegex(RoutingError,'HOLDOUT_OVERLAP'):
            matrix.verify_confirmation(self.checked,self.experiments,self.qualified)

    def test_screening_requires_all18_profiles_and_all21_cells(self):
        from cp_runtime.routing_contract import policy
        screen=copy.deepcopy(self.study)
        screen['segments']=[]
        screen['evaluations']=[{'scenario':e['scenario'],'costs':[{'profile_id':p} for p in policy()['profiles']],
            'cases':[{'prompt_ref':ref('development-prompt')}]} for e in self.experiments]
        evidence={'status':'valid','kind':'review','source':'parent-reviewed-default-qualification-plan',
            'project_id':'fixture','baseline':{'repo_path':str(self.root)},
            'scope_refs':['qualification-plan:'+matrix.scope(self.value)],'recorded_at':'2029-12-31T00:00:00+00:00'}
        definition={'identity':self.value['identity'],'required_scenarios':[r['scenario_ref'] for r in self.value['selected']],
            'installation':{'manifest':{'path':'manifest','sha256':ref('manifest')}}}
        def document(pointer):
            return self.value if pointer=='plan' else {'payload_digest':'a'*64} if pointer==definition['installation']['manifest'] else evidence
        with patch.object(matrix,'_document',side_effect=document),patch.object(matrix,'verify_record'),\
                patch.object(matrix,'stable_repo_fingerprint',return_value=ref('repo')),\
                patch.object(matrix,'load_study_sources',return_value=(screen,[],{'complete':True})):
            matrix.verify_plan('plan',definition,now='2030-01-02T00:00:00+00:00')
            screen['evaluations'][0]['costs'].pop()
            with self.assertRaisesRegex(RoutingError,'SCREENING_CATALOG_INCOMPLETE'):
                matrix.verify_plan('plan',definition,now='2030-01-02T00:00:00+00:00')
            screen['evaluations'].pop(0)
            with self.assertRaisesRegex(RoutingError,'SCREENING_MATRIX_INCOMPLETE'):
                matrix.verify_plan('plan',definition,now='2030-01-02T00:00:00+00:00')


if __name__=='__main__':unittest.main()
