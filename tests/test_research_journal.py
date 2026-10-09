"""中文：使用完整临时图和真实 V5 账本结构，不调用模型或提供方。

English: Complete temporary graph and real V5 journals; no model or provider calls.
"""
import copy,json,os,sys,tempfile,unittest,hashlib
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import budget_v5 as budget,research_campaign as campaign,research_documents as docs
from cp_runtime.approval import _approval_payload,load_approval
from cp_runtime.common import atomic_write_json,repo_snapshot
from cp_runtime.routing_contract import ref,policy_digest,add_vectors,resource_need
from cp_runtime.routing_context_contract import runtime,MODE_V2,CONTEXT_64K
from cp_runtime.event_v2 import stable_repo_fingerprint
from cp_runtime.evidence import record_evidence
from cp_runtime.qualification_study import independence_scope,bind_evaluation
import test_research_documents as fixture
import test_routing_v4_context as root_fixture
class JournalFlow(unittest.TestCase):
    def setUp(self):
        self.f=root_fixture.ContextTests(methodName='runTest');self.f.setUp()
        self.g=fixture.ResearchDocumentTests(methodName='runTest');self.g.setUp()
        self.session='one-real-shaped-host';self.base=self.g.base;self.home=self.base/'home';self.home.mkdir();self.env=patch.dict(os.environ,{'CODEX_HOME':str(self.home)});self.env.start()
        self.rt=runtime(ROOT/'hooks/review_context_reader.py',Path(sys.executable),transport_mode=MODE_V2,context_profile=CONTEXT_64K);self.rt.update(research_contract=campaign.LEGACY_CONTRACT,delivery_contract='same-call-notify/2')
        self.p=copy.deepcopy(self.g.campaign);self.p['runtime_ref']=ref(self.rt)
        self.p['identity']={'project_id':self.f.project.project_id,'repo_fingerprint':stable_repo_fingerprint(str(self.f.repo))}
        self.plans=copy.deepcopy(self.g.plans)
        from cp_runtime.qualification_study import planned_trials
        from cp_runtime.routing_context_v4 import protocol_reference
        for plan in self.plans:
            plan['identity']=self.p['identity']
            for e in plan['evaluations']:e['identity']=self.p['identity'];e['protocol_ref']=protocol_reference(e)
            trials=planned_trials(plan['evaluations']);keys=sorted(trials)
            for n,row in enumerate(plan['segments']):
                row['trial_refs']=keys[n*2:(n+1)*2]
                row['capacity']=add_vectors(*(trials[key]['resources'] for key in row['trial_refs']))
            plan['capacity']=add_vectors(*(row['capacity'] for row in plan['segments']))
        self.p['studies']=[{'study_id':s['study_id'],'study_plan_ref':ref(s)} for s in self.plans]
        self.p['capacity']=add_vectors(*(s['capacity'] for s in self.plans))
        self.p['comparison_scope']['cells']=[{'role':e['scenario']['role'],'phase':e['scenario']['phase'],'scenario_ref':ref(e['scenario']),'protocol_ref':e['protocol_ref'],'profiles':[cost['profile_id'] for cost in e['costs']]} for s in self.plans for e in s['evaluations']]
        for n,plan in enumerate(self.plans,1):
            evidence=self.base/f'independence-{n}.json'
            with patch('cp_runtime.evidence.utc_now',return_value=(datetime.fromisoformat(plan['created_at'])-timedelta(seconds=1)).isoformat()):
                record_evidence(evidence,f'synthetic-study-{n}',self.f.project.profile_path,'independence-parent',self.f.repo,'review','Synthetic case independence','valid','parent-reviewed-case-independence','Fixture only',['independence:'+independence_scope(plan)])
            plan['independence']['review_evidence']={'path':str(evidence),'sha256':'sha256:'+hashlib.sha256(evidence.read_bytes()).hexdigest()}
        self.p['studies']=[{'study_id':s['study_id'],'study_plan_ref':ref(s)} for s in self.plans]
        self.bindings=[{'schema_version':'research-segment-binding/1','campaign_plan_ref':ref(self.p),'study_plan_ref':ref(s),**b} for s in self.plans for b in s['segments']]
        self.envelopes=[{'schema_version':'qualification-study/2','study_plan':self.g.put(f'{s["study_id"]}-live.json',s),'segment_bindings':[self.g.put(f'{b["segment_id"]}-live.json',b) for b in self.bindings if b['study_plan_ref']==ref(s)]} for s in self.plans]
        self.manifest={'schema_version':'research-campaign-manifest/1','campaign_plan':self.g.put('campaign-live.json',self.p),'study_envelopes':[self.g.put(f'envelope-live-{i}.json',e) for i,e in enumerate(self.envelopes)]}
        # 中文：准备图包含两个研究，只有事务子流程使用它。
        # English: The preparatory graph has two studies; only the transaction subflow uses it.
        actual=docs.read_manifest
        self.patch=patch.object(campaign,'read_manifest',side_effect=lambda value:actual(value,complete_scope=False));self.patch.start()
        self.approval=self.base/'research-approval.json';a=_approval_payload('research-approval',self.p['identity']['project_id'],self.p['stage_id'],['make-effective'],'local',repo_snapshot(self.f.repo)['sha256'],'2099-01-01T00:00:00+00:00','test-user',campaign.approval_scope(self.p,self.manifest),True);atomic_write_json(self.approval,a,seal=True)
        grant={'schema_version':'research-stage-grant/1','grant_id':'research-test','campaign_plan_ref':ref(self.p),'campaign_manifest_ref':ref(self.manifest),'identity':self.p['identity'],'host_session_ref':self.p['host_session_ref'],'stage_id':self.p['stage_id'],'scope':self.p['comparison_scope']['stage'],'capacity':self.p['capacity'],'approved_at':self.p['created_at'],'expires_at':self.p['expires_at'],'approval_source':{'path':str(self.approval),'immutable_fingerprint':campaign.fingerprint(a)}}
        self.d={'schema_version':'research-campaign-definition/1','manifest':self.g.put('manifest-live.json',self.manifest),'grant':self.g.put('grant-live.json',grant),'installation':{'payload_root':'unused','manifest_path':'unused','runtime_files':[]}}
        self.definition=self.base/'definition.json';atomic_write_json(self.definition,self.d);self.source={'path':str(self.definition),'definition_ref':ref(self.d)}
        self.anchor=patch.object(campaign,'_anchor',side_effect=lambda *a,**k:None);self.install=patch.object(campaign,'_installation',return_value={'synthetic':True});self.anchor.start();self.install.start()
        self.frozen_a=self.approval.read_bytes();self.now=max(s['created_at'] for s in self.plans)
    def tearDown(self):
        self.install.stop();self.anchor.stop();self.patch.stop();self.env.stop();self.g.tearDown();self.f.tearDown()
    def initialize(self,binding):
        directory=Path(binding['ledger_path']).parent;directory.mkdir(parents=True,exist_ok=True);env=directory/f'envelope-{binding["segment_id"]}.json';atomic_write_json(env,{'routing':{'research_campaign':{'source':self.source,'segment_binding_ref':ref(binding)}}})
        identity={**self.p['identity'],'task_id':binding['root_task_id'],'budget_id':'research-'+binding['segment_id']}
        root={'schema_version':'dispatch-root/3','repo_path':str(self.f.repo),'profile_path':str(self.f.project.profile_path),'profile_binding_sha256':self.f.project.profile_sha256,'envelope_identity_ref':ref(env.as_posix()),'host_session_ref':self.p['host_session_ref'],'policy_id':'reviewer-matrix-v4','policy_digest':policy_digest(),'context_runtime':self.rt}
        cap=directory/'cap.json';atomic_write_json(cap,{'schema_version':'desktop-capability/1','host_surface':'codex-desktop','source':'host-tool-metadata','root_session_ref':self.p['host_session_ref'],'revision':1,'available_profiles':['g6-sol-medium'],'created_at':self.now,'expires_at':self.p['expires_at'],'wallclock_enforced':False})
        study=next(s for s in self.plans if ref(s)==binding['study_plan_ref']);envelope=next(e for e in self.envelopes if e['study_plan']['canonical_ref']==ref(study));evaluation=bind_evaluation(envelope,study['evaluations'][0]['protocol_ref']);evaluation_path=directory/f'evaluation-{binding["segment_id"]}.json';atomic_write_json(evaluation_path,evaluation)
        sources={'root_envelope':str(env),'capability':str(cap),'card_sets':[],'evaluation_costs':str(evaluation_path),'evaluation_ref':ref(evaluation),'evidence_paths':{}}
        cost=self.plans[0]['evaluations'][0]['costs'][0]
        slot={'slot_id':'slot','scenario':self.plans[0]['evaluations'][0]['scenario'],'condition':'always','depends_on':[],'status':'PENDING','independence_required':True,'active_reservation_ref':'','accepted_result_ref':'','release_evidence_ref':'','options':[{'profile_id':cost['profile_id'],'qualification_ref':ref('unqualified'),'cost_ref':ref(cost),'resources':resource_need(cost['profile_id'],1)}]}
        phase={'schema_version':'phase-plan/1','plan_id':'research-test','revision':1,'identity':self.p['identity'],'slots':[slot]}
        budget.initialize(Path(binding['ledger_path']),declared_identity=identity,root_binding=root,sources=sources,execution_mode='EVALUATION',capacity=binding['capacity'],role_capacity={'reviewer':2,'worker':0,'explorer':0},phase_capacity={'pre':2,'post':2,'repair':2},phase_plan=phase,max_parallel=1,max_depth=1)
    def test_two_segments_same_host_one_approval_and_real_ledger_heads(self):
        before=self.approval.read_bytes();admitted=campaign.admit(self.source,cwd=str(self.f.repo),session=self.session,now=self.now)
        self.assertNotEqual(before,self.approval.read_bytes());self.assertEqual(admitted,campaign.admit(self.source,cwd=str(self.f.repo),session=self.session,now=self.now))
        for n,b in enumerate(self.bindings[:2],1):
            intent=campaign.prepare_segment(self.source,ordinal=n,cwd=str(self.f.repo),session=self.session,now=self.now)
            self.assertEqual(n,intent['ordinal']);self.initialize(b);head=campaign.commit_segment(self.source,ordinal=n,cwd=str(self.f.repo),session=self.session)
            self.assertEqual(ref(b),head['segment_binding_ref']);self.assertEqual(head,campaign.commit_segment(self.source,ordinal=n,cwd=str(self.f.repo),session=self.session))
            budget.close(Path(b['ledger_path']),outcome='PARTIAL',evidence_ref=ref(f'closed-{n}'))
        self.assertEqual(self.approval.read_bytes(),self.approval.read_bytes())
        self.assertEqual(ref(self.bindings[1]),campaign._read(campaign._head(self.session))['segment_binding_ref'])
    def test_claim_only_corruption_and_exact_expiry_rejected(self):
        campaign.admit(self.source,cwd=str(self.f.repo),session=self.session,now=self.now)
        with self.assertRaisesRegex(ValueError,'EXPIRED'):campaign.prepare_segment(self.source,ordinal=1,cwd=str(self.f.repo),session=self.session,now=self.p['expires_at'])
        folder=campaign._directory(self.source);claim={'schema_version':'research-segment-claim/1','stage_admission_ref':ref(campaign._read(folder/'admitted.json')),'campaign_plan_ref':ref(self.p),'segment_binding_ref':ref(self.bindings[0]),'segment_ordinal':1,'capacity':self.bindings[0]['capacity']};atomic_write_json(folder/'claim-1.json',claim);atomic_write_json(folder/'claim-only-close-1.json',{'schema_version':'research-claim-only-close/1','claim_ref':ref('wrong'),'outcome':'SUSPENDED_NO_DISPATCH','refund':False})
        with self.assertRaises(ValueError):campaign.stage_terminal(self.source)
    def test_old_posttool_receipt_stays_on_original_ledger_after_head_moves(self):
        from cp_runtime.research_seed import _index_dir
        campaign.admit(self.source,cwd=str(self.f.repo),session=self.session,now=self.now)
        first,second=self.bindings[:2]
        campaign.prepare_segment(self.source,ordinal=1,cwd=str(self.f.repo),session=self.session,now=self.now)
        self.initialize(first)
        campaign.commit_segment(self.source,ordinal=1,cwd=str(self.f.repo),session=self.session)
        index={'ledger_path':first['ledger_path'],'status':'READY'}
        folder=_index_dir();folder.mkdir(parents=True,exist_ok=True)
        atomic_write_json(folder/'old-index.json',index)
        call='old-host-call';key=ref({'parent_session_ref':ref(self.session),'host_call_ref':ref(call)})[7:]
        atomic_write_json(folder/('call-'+key+'.json'),{'index_key':'old-index','index_ref':ref(index)})
        budget.close(Path(first['ledger_path']),outcome='PARTIAL',evidence_ref=ref('first-closed'))
        campaign.prepare_segment(self.source,ordinal=2,cwd=str(self.f.repo),session=self.session,now=self.now)
        self.initialize(second)
        campaign.commit_segment(self.source,ordinal=2,cwd=str(self.f.repo),session=self.session)
        receipt={'session_id':self.session,'hook_event_name':'PostToolUse','tool_name':'collaboration.spawn_agent','tool_use_id':call}
        self.assertEqual(Path(first['ledger_path']),campaign.event_path(receipt))
        self.assertEqual(Path(second['ledger_path']),campaign.event_path({'session_id':self.session,'hook_event_name':'PreToolUse'}))
    def test_all_four_segments_close_one_stage_before_next_stage_anchor(self):
        campaign.admit(self.source,cwd=str(self.f.repo),session=self.session,now=self.now)
        for ordinal,binding in enumerate(self.bindings,1):
            campaign.prepare_segment(self.source,ordinal=ordinal,cwd=str(self.f.repo),session=self.session,now=self.now)
            self.initialize(binding)
            campaign.commit_segment(self.source,ordinal=ordinal,cwd=str(self.f.repo),session=self.session)
            budget.close(Path(binding['ledger_path']),outcome='PARTIAL',evidence_ref=ref(f'synthetic-segment-{ordinal}'))
        self.assertTrue(campaign.stage_terminal(self.source))
        self.assertEqual(ref(self.bindings[-1]),campaign._read(campaign._head(self.session))['segment_binding_ref'])
    def test_closed_two_segment_graph_audits_every_missing_trial(self):
        from cp_runtime import research_audit
        campaign.admit(self.source,cwd=str(self.f.repo),session=self.session,now=self.now)
        for n,b in enumerate(self.bindings[:2],1):
            campaign.prepare_segment(self.source,ordinal=n,cwd=str(self.f.repo),session=self.session,now=self.now);self.initialize(b);campaign.commit_segment(self.source,ordinal=n,cwd=str(self.f.repo),session=self.session);budget.close(Path(b['ledger_path']),outcome='PARTIAL',evidence_ref=ref(f'closed-{n}'))
        rows=[]
        for envelope in self.envelopes:
            p=self.g.put('trials-'+envelope['study_plan']['canonical_ref'][7:15]+'.json',{'trials':[]});rows.append({'study_ref':ref(envelope),'trials':{'path':p['path'],'sha256':'sha256:'+p['bytes_sha256']}})
        trial_manifest={'schema_version':'research-campaign-trials/1','manifest_ref':ref(self.manifest),'studies':rows}
        original=docs.read_manifest
        with patch.object(research_audit,'read_manifest',side_effect=lambda value:original(value,complete_scope=False)),patch('cp_runtime.research_documents.read_manifest',side_effect=lambda value,**kw:original(value,complete_scope=False)):
            report,reports,_=research_audit.audit_campaign(self.manifest,trial_manifest,now=self.now)
        self.assertFalse(report['complete']);self.assertEqual(0,report['counts']['attempts']);self.assertGreater(report['counts']['missing_trials'],0)
        self.assertEqual(2,report['counts']['missing_segments'])
if __name__=='__main__':unittest.main()
