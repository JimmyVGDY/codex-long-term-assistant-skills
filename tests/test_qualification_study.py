"""中文：合成研究记账测试，不建立模型资格。

English: Synthetic study accounting; these tests never establish model qualification.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import budget_v5 as budget, review_v5 as review
from cp_runtime.common import atomic_write_json, utc_now, repo_snapshot
from cp_runtime.evidence import record_evidence
from cp_runtime.qualification_study import (audit_study,bind_evaluation,independence_scope,
                                          planned_trials,validate_study)
from cp_runtime.routing_context_contract import create_bundle
from cp_runtime.routing_contract import RoutingError, add_vectors, policy_digest, ref, resource_need
from cp_runtime.routing_evaluation_v4 import file_reference,trial_packet
from cp_runtime.routing_evaluation_v5 import record_trial, assemble_experiment
from cp_runtime.routing_cards import build_bundle, validate_bundle
import v4_fixtures as fx
import test_routing_qualification_v2 as native


def study_value(evaluation,path,capacity=None):
    trials=planned_trials([evaluation])
    need=add_vectors(*(row['resources'] for row in trials.values()))
    limit=copy.deepcopy(capacity or need)
    now=datetime.now(timezone.utc)
    return {'schema_version':'qualification-study/1','study_id':'synthetic-study',
        'identity':copy.deepcopy(evaluation['identity']),'policy_digest':policy_digest(),
        'created_at':now.isoformat(),'expires_at':(now+timedelta(days=1)).isoformat(),
        'evaluations':[copy.deepcopy(evaluation)],'capacity':limit,
        'independence':{'schema_version':'reviewed-case-independence/1','reviewed_by':'parent:independence-parent',
            'review_evidence':{'path':str(path.parent/'independence.json'),'sha256':ref('synthetic-placeholder')},
            'cases':[{'case_ref':row['case_ref'],'cluster_id':row['cluster_id'],
                      'source_problem_ref':ref('problem-'+row['cluster_id']),
                      'root_cause_ref':ref('cause-'+row['cluster_id'])} for row in evaluation['cases']]},
        'segments':[{'segment_id':'segment-1','ledger_path':str(path),
                     'host_session_ref':ref('desktop-session'),'trial_refs':sorted(trials),'capacity':copy.deepcopy(limit)}]}


def plan_value(n=2):
    experiment=fx.experiment(n)
    keys=('identity','scenario','rubric_ref','minimum_pass_bp','baseline_profile','comparisons',
          'family_intervals','case_plan','repetitions','protocol_ref')
    return {'schema_version':'routing-evaluation/1',**{key:copy.deepcopy(experiment[key]) for key in keys},
            'cases':[{key:row[key] for key in ('case_id','cluster_id','prompt_ref','gold_ref','clean','critical','case_ref')}
                     for row in experiment['samples'][:n]],'costs':fx.costs(experiment)}


class StudyContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'segment.jsonl'
        self.study=study_value(plan_value(),self.path)

    def tearDown(self):self.temp.cleanup()

    def test_every_case_profile_and_repetition_is_preallocated(self):
        study=validate_study(self.study)
        self.assertEqual(4,len(planned_trials(study['evaluations'])))
        invalid=copy.deepcopy(study)
        invalid['segments'][0]['trial_refs'].pop()
        with self.assertRaisesRegex(RoutingError,'UNALLOCATED'):
            validate_study(invalid)

    def test_root_case_and_trial_aliases_cannot_multiply_evidence(self):
        duplicate=copy.deepcopy(self.study)
        duplicate['segments'][0]['trial_refs'].append(duplicate['segments'][0]['trial_refs'][0])
        with self.assertRaisesRegex(RoutingError,'ALLOCATION'):
            validate_study(duplicate)
        for name in ('source_problem_ref','root_cause_ref'):
            invalid=copy.deepcopy(self.study)
            invalid['independence']['cases'][1][name]=invalid['independence']['cases'][0][name]
            with self.subTest(name=name),self.assertRaisesRegex(RoutingError,'CLUSTER_ALIAS'):
                validate_study(invalid)

    def test_new_segments_cannot_reset_the_total_resource_ceiling(self):
        study=copy.deepcopy(self.study)
        original=study['segments'][0]
        second=copy.deepcopy(original)
        second.update(segment_id='segment-2',ledger_path=str(self.path.with_name('second.jsonl')),
                      host_session_ref=ref('second-root'),trial_refs=original['trial_refs'][2:])
        original['trial_refs']=original['trial_refs'][:2]
        study['segments'].append(second)
        with self.assertRaisesRegex(RoutingError,'AGGREGATE_CAPACITY'):
            validate_study(study)
        study['capacity']=add_vectors(*(s['capacity'] for s in study['segments']))
        validate_study(study)
        study['segments'][1]['host_session_ref']=study['segments'][0]['host_session_ref']
        with self.assertRaisesRegex(RoutingError,'SEGMENT_REUSED'):
            validate_study(study)

    def test_frozen_native_evaluation_binds_the_exact_study(self):
        study=validate_study(self.study)
        plan=bind_evaluation(study,study['evaluations'][0]['protocol_ref'])
        self.assertTrue(all(c['source_ref']==ref(study) for c in plan['costs']))
        self.assertNotEqual(plan['costs'],study['evaluations'][0]['costs'])
        self.assertEqual(plan['protocol_ref'],study['evaluations'][0]['protocol_ref'])

    def test_native_segment_size_is_bounded_before_dispatch(self):
        study=study_value(plan_value(33),self.path)
        with self.assertRaisesRegex(RoutingError,'SEGMENT_ALLOCATION'):
            validate_study(study)


class NativeStudyTests(unittest.TestCase):
    def setUp(self):
        self.fixture=native.NativeGradeTests(methodName='runTest')
        initialize=budget.initialize

        def prepare_study(path,**kwargs):
            path=Path(path)
            source=Path(kwargs['sources']['evaluation_costs'])
            evaluation=json.loads(source.read_text(encoding='utf8'))
            self.study=study_value(evaluation,path,kwargs['capacity'])
            evidence=path.parent/'independence.json'
            root=kwargs['root_binding']
            record_evidence(evidence,'synthetic-independence',Path(root['profile_path']),
                'independence-parent',Path(root['repo_path']),'review','Synthetic test-only case independence',
                'valid','parent-reviewed-case-independence','Fixture; not real model evidence.',
                ['independence:'+independence_scope(self.study)])
            self.study['independence']['review_evidence']['sha256']=file_reference(evidence)
            self.study['created_at']=utc_now()
            plan=bind_evaluation(self.study,evaluation['protocol_ref'])
            atomic_write_json(source,plan)
            kwargs['sources']['evaluation_ref']=ref(plan)
            for slot in kwargs['phase_plan']['slots']:
                slot['options']=[{'profile_id':cost['profile_id'],'qualification_ref':ref('evaluation-only'),
                    'cost_ref':ref(cost),'resources':resource_need(cost['profile_id'],cost['reserve_units'])}
                    for cost in plan['costs']]
            return initialize(path,**kwargs)

        with patch.object(budget,'initialize',prepare_study):
            self.fixture.setUp()
        self.path=self.fixture.path
        self.root=self.fixture.root
        self.sources=[]

    def tearDown(self):self.fixture.tearDown()

    def first(self):
        self.fixture.complete()
        record=self.fixture.record()
        self.sources.append({'ledger':str(self.path),'result':record['result_path'],
            'response':str(self.fixture.fixture.response),'gold':str(self.fixture.gold),'rubric':str(self.fixture.rubric),
            'transcript':str(self.fixture.fixture.f.transcript)})

    def next_trial(self,case_index,profile,number):
        transport=self.fixture.fixture
        holder=transport.f
        state=budget.read_budget(self.path)
        rid=next(rid for rid,a in state['reservations'].items() if a['permit_id']==holder.pid)
        previous=state['accepted_results'][rid]
        case=holder.f.evaluation['cases'][case_index]
        request=copy.deepcopy(holder.request)
        request.update(evaluation_case_ref=case['case_ref'],business_prompt_sha256=case['prompt_ref'][7:],
                       packet_sha256=trial_packet(case['case_ref'],profile,1),expected={})
        request['constraints']['allowed_profiles']=[profile]
        prompt=self.root/f'prompt-{number}.txt'
        prompt.write_bytes(json.dumps(f'synthetic-prompt-{case_index}').encode())
        request['context_bundle']=create_bundle(self.root/f'bundle-{number}.json',repo=holder.f.repo,
            business_prompt=prompt,packet_sha256=request['packet_sha256'],baseline_sha256=request['baseline_sha256'],artifacts={})
        budget.advance_evaluation(self.path,slot_id=request['slot_id'],previous_result_ref=previous['result_ref'],
                                  next_packet_sha256=request['packet_sha256'])
        selected=review.prepare(holder.review_dir,request,dispatch_key=f'eval_{number}',depth=1,
            snapshot_loader=holder.loader,transition={'reason':'EVALUATION_NEXT','prior_reservation_id':rid,
                                                     'prior_result_ref':previous['result_ref']})
        self.assertEqual('EVALUATION_SELECTED',selected['status'])
        holder.pid=selected['permit_id']
        holder.parent['tool_use_id']=f'spawn-{number}'
        holder.parent['tool_input']={**selected['request_parameters'],'task_name':f'eval_{number}',
                                    'fork_turns':'none','message':'opaque-data'}
        holder.child=f'12345678-1234-1234-1234-{number:012d}'
        holder.transcript=holder.transcript.with_name('rollout-'+holder.child+'.jsonl')
        holder.header['payload']['id']=holder.child
        holder.header['payload']['source']['subagent']['thread_spawn']['agent_path']=f'/root/eval_{number}'
        holder.transcript.write_text(json.dumps(holder.header)+'\n',encoding='utf8')
        holder.child_data.update(agent_id=holder.child,transcript_path=str(holder.transcript))
        transport.begin();transport.read();transport.final()
        review.record_semantic(holder.review_dir,holder.pid,transport.response)
        state=budget.read_budget(self.path)
        rid=next(rid for rid,a in state['reservations'].items() if a['permit_id']==holder.pid)
        gold=self.root/f'gold-{number}.json'
        gold.write_bytes(json.dumps(f'gold-{case_index}').encode())
        saved=record_trial(self.path,cwd=str(holder.f.repo),host_session_id='desktop-session',reservation_id=rid,
            repetition=1,response_path=transport.response,gold_path=gold,rubric_path=self.fixture.rubric,
            transcript_path=holder.transcript,
            grade={'passed':True,'false_block':False,'critical_failure':False,'boundary_failure':False})
        self.sources.append({'ledger':str(self.path),'result':saved['result_path'],'response':str(transport.response),
                             'gold':str(gold),'rubric':str(self.fixture.rubric),'transcript':str(holder.transcript)})

    def close(self):
        review.close(self.fixture.fixture.f.review_dir,conclusion='PASS')
        budget.close(self.path,outcome='PASS',evidence_ref=ref('synthetic-study-only'))

    def test_complete_native_shaped_study_and_omitted_grade_denominator(self):
        self.first()
        self.next_trial(0,'g6-sol-high',2)
        self.next_trial(1,'g6-sol-medium',3)
        self.next_trial(1,'g6-sol-high',4)
        self.close()
        report=audit_study(self.study,self.sources,now=utc_now())
        self.assertTrue(report['complete'])
        self.assertEqual(4,report['counts']['planned'])
        self.assertEqual(4,report['counts']['attempts'])
        self.assertEqual(4,report['counts']['graded'])
        self.assertEqual('UNKNOWN',report['billing'])
        self.assertFalse(report['qualification_granted'])
        missing=audit_study(self.study,self.sources[:-1],now=utc_now())
        self.assertFalse(missing['complete'])
        self.assertEqual(4,missing['counts']['attempts'])
        self.assertEqual(1,missing['counts']['ungraded_trials'])
        with self.assertRaisesRegex(RoutingError,'GRADE_DUPLICATE'):
            audit_study(self.study,self.sources+[self.sources[0]],now=utc_now())
        study_path=self.root/'study.json'
        trials_path=self.root/'trials.json'
        atomic_write_json(study_path,self.study)
        atomic_write_json(trials_path,{'trials':self.sources})
        source={'study':{'path':str(study_path),'sha256':file_reference(study_path)},
                'trials':{'path':str(trials_path),'sha256':file_reference(trials_path)},'audit_ref':ref(report)}
        plan=bind_evaluation(self.study,self.study['evaluations'][0]['protocol_ref'])
        experiment=assemble_experiment(plan,self.sources,experiment_id='synthetic-complete-study',
            issuer_task_id='independence-parent',issuer_baseline=repo_snapshot(self.fixture.fixture.f.f.repo)['sha256'],
            qualification_source=source)
        bundle=build_bundle(experiment,plan['costs'],bundle_id='synthetic-study-bundle',
                            created_at=utc_now(),expires_at=self.study['expires_at'])
        traces=budget.export_traces(self.path)
        validate_bundle(bundle,experiment,now=utc_now(),trace_loader=traces.__getitem__)
        self.assertFalse(any(card['qualified'] for card in bundle['qualification']))
        wrong_baseline=copy.deepcopy(experiment)
        wrong_baseline['issuer']['baseline_sha256']='0'*64
        with self.assertRaisesRegex(RoutingError,'STUDY_EXPERIMENT_BASELINE_CHANGED'):
            validate_bundle(bundle,wrong_baseline,now=utc_now(),trace_loader=traces.__getitem__)
        with self.assertRaisesRegex(RoutingError,'SOURCE_SUBSET'):
            assemble_experiment(plan,self.sources[:-1],experiment_id='synthetic-subset',
                issuer_task_id='independence-parent',issuer_baseline='a'*64,qualification_source=source)
        grade_path=Path(self.sources[0]['result'])
        original=grade_path.read_bytes()
        changed=json.loads(original)
        changed['grade']['passed']=False
        atomic_write_json(grade_path,changed)
        with self.assertRaisesRegex(RoutingError,'AUDIT_CHANGED'):
            validate_bundle(bundle,experiment,now=utc_now(),trace_loader=traces.__getitem__)
        grade_path.write_bytes(original)

    def test_partial_root_and_unstarted_plan_units_remain_visible(self):
        self.first()
        report=audit_study(self.study,[],now=utc_now())
        self.assertFalse(report['complete'])
        self.assertEqual(4,report['counts']['planned'])
        self.assertEqual(1,report['counts']['attempts'])
        self.assertEqual(3,report['counts']['missing_trials'])
        self.assertEqual(4,report['counts']['ungraded_trials'])

    def test_claimed_independence_and_changed_study_are_not_source_evidence(self):
        forged=copy.deepcopy(self.study)
        forged['independence']['review_evidence']['sha256']=ref('forged')
        with self.assertRaisesRegex(RoutingError,'INDEPENDENCE_EVIDENCE_INVALID'):
            audit_study(forged,[],now=utc_now())
        changed=copy.deepcopy(self.study)
        changed['study_id']='changed-after-budget-initialization'
        with self.assertRaisesRegex(RoutingError,'NATIVE_PLAN_BINDING'):
            audit_study(changed,[],now=utc_now())

    def test_missing_root_marks_resource_totals_incomplete(self):
        saved=self.path.with_suffix('.saved')
        self.assertTrue(self.path.resolve().is_relative_to(self.root.resolve()))
        self.assertTrue(saved.resolve().is_relative_to(self.root.resolve()))
        self.path.replace(saved)
        report=audit_study(self.study,[],now=utc_now())
        self.assertFalse(report['complete'])
        self.assertEqual(1,report['counts']['missing_segments'])
        self.assertEqual(4,report['counts']['missing_trials'])
        self.assertFalse(report['resources_complete'])


if __name__=='__main__':unittest.main()
