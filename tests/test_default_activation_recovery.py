"""中文：失败注入仅限临时夹具，不构成真实资格。

English: Failure injection is confined to temporary fixtures; no real qualification.
"""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import desktop_default_activation as activation
from cp_runtime.approval import load_approval,issue_approval
from cp_runtime.common import atomic_write_json,utc_now
from cp_runtime.routing_contract import RoutingError,ref
import test_desktop_default_activation as fixtures
import test_context_protocol_v2 as final_fixtures
from cp_runtime.context_final_v2 import extract_final


class ActivationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ActivationTests(methodName='runTest');self.f.setUp()

    def tearDown(self):self.f.tearDown()

    def interrupt(self,target):
        source=self.f.prepare()
        activation.verify_installation(source,repo_path=self.f.repo,now=utc_now())
        approval=self.f.approve(source)
        write=activation.atomic_write_json
        def fail(path,value,**kwargs):
            if (target=='pointer' and Path(path)==self.f.pointer) or (
                    target=='state' and Path(path)==Path(source['path']) and value.get('status')=='ACTIVE'):
                raise OSError('synthetic commit interruption')
            return write(path,value,**kwargs)
        with patch.object(activation,'atomic_write_json',fail),self.assertRaises(OSError):
            activation.activate(source,pointer_path=self.f.pointer,approval_path=approval,
                repo_path=self.f.repo,task_id='activation-task',now=utc_now())
        self.assertEqual('consumed',load_approval(approval)['status'])
        self.assertFalse(self.f.pointer.exists())
        return source,approval

    def test_pointer_failure_recovers_without_reconsuming_approval(self):
        source,approval=self.interrupt('pointer')
        original=load_approval(approval)['consumed_at']
        activation.activate(source,pointer_path=self.f.pointer,approval_path=approval,
            repo_path=self.f.repo,task_id='activation-task',now=utc_now())
        self.assertEqual(original,load_approval(approval)['consumed_at'])
        self.assertEqual(3,len(activation._read(source)['history']))
        self.assertEqual('reviewer-matrix-v4',activation.resolve_default(self.f.pointer,
            expected_identity=self.f.identity,task_id='new-task',now=utc_now())['policy_id'])

    def test_consumed_before_active_write_is_recoverable(self):
        source,approval=self.interrupt('state')
        self.assertEqual('INSTALLED_VERIFIED',activation._read(source)['status'])
        activation.activate(source,pointer_path=self.f.pointer,approval_path=approval,
            repo_path=self.f.repo,task_id='activation-task',now=utc_now())
        self.assertEqual('ACTIVE',activation._read(source)['status'])

    def test_recovery_rejects_another_approval_and_preserves_it(self):
        source,_=self.interrupt('pointer')
        other=self.f.root/'other-approval.json'
        issue_approval(other,'other',self.f.project.profile_path,'activation-task',['make-effective'],
            'local',self.f.repo,self.f.expires,note=activation.approval_note(source))
        with self.assertRaisesRegex(RoutingError,'INTENT_CONFLICT'):
            activation.activate(source,pointer_path=self.f.pointer,approval_path=other,
                repo_path=self.f.repo,task_id='activation-task',now=utc_now())
        self.assertEqual('active',load_approval(other)['status'])

    def test_recovery_cannot_overwrite_a_different_current_pointer(self):
        source,approval=self.interrupt('pointer')
        changed={'schema_version':'desktop-default-pointer/1','identity':self.f.identity,
            'source':{'path':str(self.f.root/'other.json'),'definition_ref':ref('other')}}
        atomic_write_json(self.f.pointer,changed,seal=True)
        before=self.f.pointer.read_bytes()
        with self.assertRaisesRegex(RoutingError,'POINTER_COMMIT_CONFLICT'):
            activation.activate(source,pointer_path=self.f.pointer,approval_path=approval,
                repo_path=self.f.repo,task_id='activation-task',now=utc_now())
        self.assertEqual(before,self.f.pointer.read_bytes())

    def test_explicit_rollback_recovers_both_missing_pointer_states(self):
        for target in ('state','pointer'):
            with self.subTest(target=target):
                if target=='pointer':
                    self.f.tearDown();self.f=fixtures.ActivationTests(methodName='runTest');self.f.setUp()
                source,_=self.interrupt(target)
                reason=ref('explicit fixture rollback')
                approval=self.f.root/'rollback.json'
                issue_approval(approval,'rollback',self.f.project.profile_path,'rollback-task',
                    ['make-effective'],'local',self.f.repo,self.f.expires,
                    note='desktop-default-restore-legacy:'+ref({'source':source,'reason_ref':reason}))
                activation.restore_legacy(source,approval_path=approval,repo_path=self.f.repo,
                    task_id='rollback-task',reason_ref=reason,now=utc_now())
                self.assertEqual('reviewer-matrix-v3',activation.resolve_default(self.f.pointer,
                    expected_identity=self.f.identity,task_id='next-task',now=utc_now())['policy_id'])

    def test_rollback_pointer_write_failure_retries_same_consumed_approval(self):
        source,_=self.interrupt('pointer')
        reason=ref('fixture rollback pointer failure')
        approval=self.f.root/'rollback-pointer.json'
        issue_approval(approval,'rollback-pointer',self.f.project.profile_path,'rollback-task',
            ['make-effective'],'local',self.f.repo,self.f.expires,
            note='desktop-default-restore-legacy:'+ref({'source':source,'reason_ref':reason}))
        write=activation.atomic_write_json
        def fail(path,value,**kwargs):
            if Path(path)==self.f.pointer:raise OSError('synthetic rollback pointer failure')
            return write(path,value,**kwargs)
        with patch.object(activation,'atomic_write_json',fail),self.assertRaises(OSError):
            activation.restore_legacy(source,approval_path=approval,repo_path=self.f.repo,
                task_id='rollback-task',reason_ref=reason,now=utc_now())
        before=load_approval(approval)['consumed_at'];history=activation._read(source)['history']
        activation.restore_legacy(source,approval_path=approval,repo_path=self.f.repo,
            task_id='rollback-task',reason_ref=reason,now=utc_now())
        self.assertEqual(before,load_approval(approval)['consumed_at'])
        self.assertEqual(history,activation._read(source)['history'])
        self.assertEqual('reviewer-matrix-v3',activation.resolve_default(self.f.pointer,
            expected_identity=self.f.identity,task_id='next-task',now=utc_now())['policy_id'])

    def test_legacy_scoped_definition_cannot_newly_activate_default(self):
        old=copy.deepcopy(self.f.definition)
        old['schema_version']='desktop-default-activation/1';old.pop('qualification_plan')
        with self.assertRaisesRegex(RoutingError,'COMPLETE_PLAN_REQUIRED'):
            activation.prepare(self.f.root/'legacy.json',old,repo_path=self.f.repo,
                task_id='activation-task',now=utc_now())


class FinalMetadataTests(unittest.TestCase):
    def setUp(self):
        self.f=final_fixtures.NativeFinalTests(methodName='runTest');self.f.setUp()

    def test_known_metadata_preserves_every_original_byte_and_stays_non_json(self):
        suffix='<oai-mem-citation>\n<citation_entries>\nMEMORY.md:1-2|note=[test]\n</citation_entries>\n<rollout_ids>\n</rollout_ids>\n</oai-mem-citation>'
        original=self.f.text+'\n\n'+suffix
        self.f.events[-1]['payload']['content'][0]['text']=original
        self.f.events.append({'type':'event_msg','payload':{'type':'task_complete','turn_id':'turn-1',
            'last_agent_message':self.f.text+'\n\n'}})
        text,proof=extract_final(self.f.raw(),**self.f.binding)
        self.assertEqual(original,text)
        self.assertEqual(ref(original) != ref(self.f.text),True)
        with self.assertRaises(json.JSONDecodeError):json.loads(text)
        altered=original.replace('MEMORY.md:1-2','MEMORY.md:3-4')
        self.f.events[2]['payload']['content'][0]['text']=altered
        self.assertNotEqual(proof['response_ref'],extract_final(self.f.raw(),**self.f.binding)[1]['response_ref'])

    def test_semantic_changes_and_unknown_or_duplicate_suffix_are_denied(self):
        suffix='<oai-mem-citation><citation_entries></citation_entries><rollout_ids></rollout_ids></oai-mem-citation>'
        for tail in (suffix+' changed',suffix+suffix,'arbitrary trailing text'):
            with self.subTest(tail=tail):
                events=copy.deepcopy(self.f.events)
                events[-1]['payload']['content'][0]['text']=self.f.text+tail
                events.append({'type':'event_msg','payload':{'type':'task_complete','turn_id':'turn-1','last_agent_message':self.f.text}})
                with self.assertRaisesRegex(ValueError,'COMPLETION_CONFLICT'):extract_final(self.f.raw(events),**self.f.binding)
        events=copy.deepcopy(self.f.events)
        events[-1]['payload']['content'][0]['text']=self.f.text.replace('pass','blocking')+suffix
        events.append({'type':'event_msg','payload':{'type':'task_complete','turn_id':'turn-1','last_agent_message':self.f.text}})
        with self.assertRaisesRegex(ValueError,'COMPLETION_CONFLICT'):extract_final(self.f.raw(events),**self.f.binding)


if __name__=='__main__':unittest.main()
