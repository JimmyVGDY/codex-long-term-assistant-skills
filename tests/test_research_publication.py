"""中文：在临时环境真实消费审批，将矩阵统计隔离为前置条件。

English: Real temporary approval consumption; matrix statistics isolated as a precondition.
"""
import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import research_publication as pub
from cp_runtime.approval import issue_approval,load_approval
from cp_runtime.common import repo_snapshot,atomic_write_json
from cp_runtime.routing_contract import ref
import test_routing_v4_context as fixture
class PublicationTransactionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.ContextTests(methodName='runTest');self.f.setUp();self.source={'schema_version':'research-matrix-source/1','confirmation':{'manifest':{'path':'unused','sha256':ref('unused')}},'development':{}};self.path=self.f.root/'publication.json';self.approval=self.f.root/'matrix-approval.json';self.task='confirmation-stage';profile=Path(self.f.project.profile_path);identity=json.loads(profile.read_text(encoding='utf8'));self.matrix={'identity':{'project_id':identity['project_id'],'repo_fingerprint':self.f.identity['repo_fingerprint']},'candidate_payload_digest':'a'*64,'claim':'ALL_REQUIRED_NO_SIMULTANEOUS_CI','qualified':True}
        issue_approval(self.approval,'matrix-publish',profile,self.task,['make-effective'],'local',self.f.repo,(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),approved_by='test-user',note='research-matrix-publication:'+ref({'matrix_ref':ref(self.matrix),'source_ref':ref(self.source)}))
        self.patches=[patch.object(pub,'qualify_matrix',return_value=self.matrix),patch.object(pub,'_file',return_value={}),patch.object(pub,'read_manifest',return_value=({'stage_id':self.task,'identity':self.matrix['identity']},[],[],[]))]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.f.tearDown()
    def publish(self):return pub.publish_matrix(self.path,self.source,approval_path=self.approval,repo_path=self.f.repo,now=datetime.now(timezone.utc).isoformat())
    def test_forged_same_matrix_without_authority_rejected_and_success_replayed(self):
        bare={'schema_version':'research-matrix-publication/1','matrix_ref':ref(self.matrix),'source_ref':ref(self.source),'identity':self.matrix['identity'],'candidate_payload_digest':'a'*64,'claim':self.matrix['claim']}
        with self.assertRaises(ValueError):pub.verify_matrix_publication(bare,self.source,now=datetime.now(timezone.utc).isoformat())
        first=self.publish();before=self.path.read_bytes();authority=self.approval.read_bytes();self.assertEqual(first,self.publish());self.assertEqual(before,self.path.read_bytes());self.assertEqual(authority,self.approval.read_bytes())
        pub.verify_matrix_publication(first,self.source,now=datetime.now(timezone.utc).isoformat())
        real=load_approval(self.approval)
        for field,bad_value in (('project_id','wrong-project'),('task_id','wrong-task'),('environment','production'),('one_time',False),('baseline_sha256','f'*64)):
            bad={**real,field:bad_value}
            with self.subTest(field=field),patch('cp_runtime.approval.load_approval',return_value=bad),self.assertRaisesRegex(ValueError,'SCOPE_MISMATCH'):
                pub.verify_matrix_publication(first,self.source,now=datetime.now(timezone.utc).isoformat())
    def test_consumed_before_file_write_recovers_without_second_consumption(self):
        import cp_runtime.common as common
        original=common.atomic_write_json
        def fail_publication(path,value,*a,**k):
            if Path(path)==self.path:raise OSError('after consume')
            return original(path,value,*a,**k)
        with patch.object(common,'atomic_write_json',side_effect=fail_publication):
            with self.assertRaises(OSError):self.publish()
        self.assertTrue(load_approval(self.approval)['consumed_at']);before=self.approval.read_bytes();self.publish();self.assertEqual(before,self.approval.read_bytes())
    def test_unconsumed_intent_cannot_resume_after_repository_baseline_changes(self):
        with patch('cp_runtime.approval.consume_approval',side_effect=OSError('before consume')):
            with self.assertRaises(OSError):self.publish()
        self.assertTrue(self.path.with_suffix('.publication-intent.json').exists())
        self.assertFalse(self.path.exists())
        self.assertEqual('active',load_approval(self.approval)['status'])
        (self.f.repo/'README.md').write_text('Changed after publication intent.\n',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'BASELINE_STALE'):self.publish()
        self.assertEqual('active',load_approval(self.approval)['status'])
        self.assertFalse(self.path.exists())
if __name__=='__main__':unittest.main()
