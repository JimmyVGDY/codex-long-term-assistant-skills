"""中文：完整 21 格不可变文档图，不宣称模型能力或资格。

English: Complete 21-cell immutable document graph; no model or qualification claims.
"""
import copy,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import research_documents as docs
from cp_runtime.default_qualification_plan import expected_cells
from cp_runtime.qualification_study import planned_trials
from cp_runtime.routing_contract import add_vectors,policy,ref
from cp_runtime.routing_context_v4 import protocol_reference
import v4_fixtures as vf
import test_research_documents as file_fixture

class CompleteMatrixGraph(unittest.TestCase):
    def setUp(self):
        self.f=file_fixture.ResearchDocumentTests(methodName='runTest');self.f.setUp();self.base=self.f.base
    def tearDown(self):self.f.tearDown()
    def graph(self,stage,development=None):
        profiles=list(policy()['profiles']) if stage=='DEVELOPMENT_SCREEN' else ['g56-luna-high','g6-sol-medium']
        evaluations=[]
        for i,(role,phase) in enumerate(sorted(expected_cells())):
            exp=vf.experiment(2,profiles=tuple(profiles));exp['scenario'].update(role=role,phase=phase,prompt_sha256=ref(f'{stage}-scenario-{i}')[7:])
            for row in exp['samples']:
                row['case_id']=f'{stage}-{i}-{row["case_id"]}'
                row['cluster_id']=f'{stage}-{i}-{row["cluster_id"]}'
                row['prompt_ref']=ref(f'{stage}-{i}-{row["prompt_ref"]}')
                row['gold_ref']=ref(f'{stage}-{i}-{row["gold_ref"]}')
            vf.refreeze_protocol(exp)
            exp['costs']=vf.costs(exp)
            evaluation={key:copy.deepcopy(exp[key]) for key in ('schema_version','identity','scenario','rubric_ref','minimum_pass_bp','baseline_profile','comparisons','family_intervals','case_plan','repetitions','protocol_ref','costs')}
            evaluation['schema_version']='routing-evaluation/1'
            evaluation['cases']=[{key:row[key] for key in ('case_id','cluster_id','prompt_ref','gold_ref','clean','critical','case_ref')} for row in exp['samples'][:2]]
            evaluation['protocol_ref']=protocol_reference(evaluation)
            evaluations.append(evaluation)
        # 中文：文件图属于测试夹具，刻意不包含统计样本。
        # English: The test fixture owns the file graph; statistical samples are deliberately absent.
        from test_qualification_study import study_value
        study=study_value(evaluations[0],self.base/f'{stage}-initial.jsonl')
        study.update(schema_version='research-study-plan/1',study_id=f'{stage}-all-cells',evaluations=evaluations)
        trial_map=planned_trials(evaluations);keys=sorted(trial_map)
        study['segments']=[]
        for n in range(0,len(keys),60):
            selected=keys[n:n+60];ordinal=n//60+1
            study['segments'].append({'segment_id':f'{stage}-segment-{ordinal}','root_task_id':f'{stage}-task-{ordinal}','ledger_path':str(self.base/f'{stage}-segment-{ordinal}.jsonl'),'host_session_ref':ref('one-real-shaped-host'),'trial_refs':selected,'capacity':add_vectors(*(trial_map[k]['resources'] for k in selected))})
        study['capacity']=add_vectors(*(s['capacity'] for s in study['segments']))
        study['independence']['cases']=[{'case_ref':case['case_ref'],'cluster_id':case['cluster_id'],'source_problem_ref':ref('problem-'+case['cluster_id']),'root_cause_ref':ref('cause-'+case['cluster_id'])} for e in evaluations for case in e['cases']]
        campaign=copy.deepcopy(self.f.campaign)
        campaign.update(campaign_id=f'{stage}-complete',stage_id=stage,identity=study['identity'],created_at=study['created_at'],expires_at=study['expires_at'],studies=[{'study_id':study['study_id'],'study_plan_ref':ref(study)}],capacity=study['capacity'])
        cells=[]
        for e in evaluations:
            cell={'role':e['scenario']['role'],'phase':e['scenario']['phase'],'scenario_ref':ref(e['scenario']),'protocol_ref':e['protocol_ref']}
            if stage=='DEVELOPMENT_SCREEN':cell['profiles']=profiles
            else:cell.update(baseline_profile=profiles[0],candidate_profile=profiles[1],confirmation_case_refs=e['case_plan'])
            cells.append(cell)
        scope={'schema_version':'research-comparison-scope/1','stage':stage,'claim':'AUDIT_ONLY' if stage=='DEVELOPMENT_SCREEN' else 'ALL_REQUIRED_NO_SIMULTANEOUS_CI','cells':cells}
        if development is not None:scope['development_manifest']=self.f.put('development-complete.json',development)
        campaign['comparison_scope']=scope
        binding=[{'schema_version':'research-segment-binding/1','campaign_plan_ref':ref(campaign),'study_plan_ref':ref(study),**s} for s in study['segments']]
        envelope={'schema_version':'qualification-study/2','study_plan':self.f.put(f'{stage}-plan.json',study),'segment_bindings':[self.f.put(f'{stage}-binding-{n}.json',b) for n,b in enumerate(binding)]}
        manifest={'schema_version':'research-campaign-manifest/1','campaign_plan':self.f.put(f'{stage}-campaign.json',campaign),'study_envelopes':[self.f.put(f'{stage}-envelope.json',envelope)]}
        return manifest,campaign,study
    def test_complete_development_and_independent_confirmation_graph(self):
        development,_,_=self.graph('DEVELOPMENT_SCREEN')
        _,plans,_,bindings=docs.read_manifest(development)
        self.assertEqual(21,len(plans[0]['evaluations']))
        self.assertEqual(756,sum(len(b['trial_refs']) for b in bindings))
        confirmation,_,_=self.graph('CONFIRMATION',development)
        _,plans,_,bindings=docs.read_manifest(confirmation)
        self.assertEqual(21,len(plans[0]['evaluations']))
        self.assertEqual(84,sum(len(b['trial_refs']) for b in bindings))
    def test_missing_cell_is_rejected_before_consumption(self):
        development,campaign,_=self.graph('DEVELOPMENT_SCREEN')
        _,plans,_,_=docs.read_manifest(development)
        broken=copy.deepcopy(campaign['comparison_scope']);broken['cells'].pop()
        from cp_runtime.research_claim_scope import validate
        with self.assertRaisesRegex(ValueError,'INCOMPLETE'):validate(broken,plans[0]['evaluations'])
    def test_confirmation_overlap_and_pair_drift_are_rejected(self):
        from cp_runtime.research_claim_scope import check_independent_confirmation,validate
        development,_,dev_plan=self.graph('DEVELOPMENT_SCREEN')
        confirmation,campaign,_=self.graph('CONFIRMATION',development)
        _,plans,_,_=docs.read_manifest(confirmation)
        bad_plan=copy.deepcopy(plans[0])
        bad_plan['independence']['cases'][0]['source_problem_ref']=dev_plan['independence']['cases'][0]['source_problem_ref']
        with self.assertRaisesRegex(ValueError,'OVERLAP'):
            check_independent_confirmation(campaign['comparison_scope'],[bad_plan])
        bad_scope=copy.deepcopy(campaign['comparison_scope'])
        bad_scope['cells'][0]['candidate_profile']='g6-astra-high'
        with self.assertRaisesRegex(ValueError,'FIXED_PAIR'):
            validate(bad_scope,plans[0]['evaluations'])
    def test_matrix_consumer_requires_each_selected_leaf_even_with_other_leaves_qualified(self):
        from cp_runtime import research_publication as publication,budget_v5 as budget
        development,dev_campaign,_=self.graph('DEVELOPMENT_SCREEN')
        confirmation,campaign,_=self.graph('CONFIRMATION',development)
        source={'schema_version':'research-matrix-source/1','development':{'manifest':{'path':'synthetic-development','sha256':ref('dev')}},'confirmation':{'manifest':{'path':'synthetic-confirmation','sha256':ref('confirm')}}}
        fake_trials={'studies':[{'trials':{'path':'synthetic-trials','sha256':ref('trials')}}]}
        fake_report={'complete':True}
        def audit(which,*,now):
            manifest=development if which is source['development'] else confirmation
            return manifest,fake_trials,fake_report,[{'synthetic':True}],[[]]
        def leaf(plan,*args,**kwargs):return plan
        disqualified=set()
        def cards(plan):
            scenario_ref=ref(plan['scenario'])
            return [{'scenario_ref':scenario_ref,'profile_id':'g6-sol-medium','qualified':scenario_ref not in disqualified}],[]
        with patch.object(publication,'read_audit_source',side_effect=audit),patch.object(budget,'_read_events',return_value=[{'recorded_at':dev_campaign['created_at']}]),patch('cp_runtime.qualification_study._independence_evidence',return_value={'baseline':{'sha256':ref('baseline')}}),patch('cp_runtime.routing_evaluation_v5.assemble_experiment',side_effect=leaf),patch('cp_runtime.routing_cards.derived_cards',side_effect=cards):
            matrix=publication.qualify_matrix(source,now=campaign['created_at'])
            self.assertEqual(21,len(matrix['qualification']))
            self.assertFalse(matrix['global_simultaneous_ci_claim'])
            disqualified.add(ref(next(iter(docs.read_manifest(confirmation)[1]))['evaluations'][0]['scenario']))
            with self.assertRaisesRegex(ValueError,'REQUIRED_CELL_NOT_QUALIFIED'):
                publication.qualify_matrix(source,now=campaign['created_at'])

if __name__=='__main__':unittest.main()
