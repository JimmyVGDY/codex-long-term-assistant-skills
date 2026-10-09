"""中文：两个研究各含同宿主的两个段，不包含授权或模型调用。

English: Two studies/two same-host segments each; no authority or model calls.
"""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import research_documents as docs
from cp_runtime.qualification_study import planned_trials,validate_study
from cp_runtime.routing_contract import ref,add_vectors,policy_digest
from cp_runtime.routing_context_v4 import protocol_reference
import test_qualification_study as fixtures
class ResearchDocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.plans=[]
        for n in (1,2):
            evaluation=fixtures.plan_value();evaluation['rubric_ref']=ref(f'study-{n}-rubric')
            if n==2:evaluation['scenario']['phase']='repair'
            for cost in evaluation['costs']:cost['scenario_ref']=ref(evaluation['scenario'])
            evaluation['protocol_ref']=protocol_reference(evaluation)
            p=fixtures.study_value(evaluation,self.base/f's{n}-first.jsonl');p['schema_version']='research-study-plan/1';p['study_id']=f'study-{n}';trials=planned_trials(p['evaluations']);keys=sorted(trials)
            p['segments']=[]
            for ordinal in (1,2):
                selected=keys[(ordinal-1)*2:ordinal*2];p['segments'].append({'segment_id':f's{n}-seg{ordinal}','root_task_id':f'study-{n}-task-{ordinal}','ledger_path':str(self.base/f's{n}-{ordinal}.jsonl'),'host_session_ref':ref('one-real-shaped-host'),'trial_refs':selected,'capacity':add_vectors(*(trials[k]['resources'] for k in selected))})
            self.plans.append(p)
        first=self.plans[0];self.campaign={'schema_version':'research-campaign-plan/1','campaign_id':'dev-fixture','stage_id':'DEVELOPMENT_SCREEN','identity':first['identity'],'policy_digest':policy_digest(),'candidate_payload_digest':'a'*64,'host_session_ref':ref('one-real-shaped-host'),'runtime_ref':ref('runtime'),'created_at':first['created_at'],'expires_at':first['expires_at'],'predecessor':{'registry_path':str(self.base/'prior-root.json'),'registry_bytes_sha256':'b'*64,'ledger_path':str(self.base/'prior-ledger.jsonl'),'final_record_hash':'c'*64,'closed_outcome':'PARTIAL'},'studies':[{'study_id':p['study_id'],'study_plan_ref':ref(p)} for p in self.plans],'capacity':add_vectors(*(p['capacity'] for p in self.plans)),'comparison_scope':{'fixture':'source-binding only, never statistical authority'},'retry_policy':'NO_CREATED_TRIAL_REPLAY','historical_evidence_refs':[]}
        self.campaign['comparison_scope']={'schema_version':'research-comparison-scope/1','stage':'DEVELOPMENT_SCREEN','claim':'AUDIT_ONLY','cells':[{'role':p['evaluations'][0]['scenario']['role'],'phase':p['evaluations'][0]['scenario']['phase'],'scenario_ref':ref(p['evaluations'][0]['scenario']),'protocol_ref':p['evaluations'][0]['protocol_ref'],'profiles':[c['profile_id'] for c in p['evaluations'][0]['costs']]} for p in self.plans]}
        self.bindings=[];self.envelopes=[]
        for p in self.plans:
            bindings=[{'schema_version':'research-segment-binding/1','campaign_plan_ref':ref(self.campaign),'study_plan_ref':ref(p),**s} for s in p['segments']];self.bindings.extend(bindings)
            self.envelopes.append({'schema_version':'qualification-study/2','study_plan':self.put(p['study_id']+'.json',p),'segment_bindings':[self.put(b['segment_id']+'.json',b) for b in bindings]})
        self.manifest={'schema_version':'research-campaign-manifest/1','campaign_plan':self.put('campaign.json',self.campaign),'study_envelopes':[self.put(f'envelope-{i}.json',e) for i,e in enumerate(self.envelopes)]}
    def tearDown(self):self.temp.cleanup()
    def put(self,name,value):
        path=self.base/name;raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8');path.write_bytes(raw);return {'path':str(path),'canonical_ref':ref(value),'bytes_sha256':hashlib.sha256(raw).hexdigest()}
    def test_complete_acyclic_two_studies_each_two_same_host_segments(self):
        c,plans,envelopes,bindings=docs.read_manifest(self.manifest,complete_scope=False);self.assertEqual(2,len(plans));self.assertEqual(4,len(bindings));self.assertEqual(1,len({b['host_session_ref'] for b in bindings}));self.assertEqual(self.campaign,c)
        for p in plans:
            legacy={**copy.deepcopy(p),'schema_version':'qualification-study/1'}
            for s in legacy['segments']:s.pop('root_task_id')
            with self.assertRaisesRegex(ValueError,'SEGMENT_REUSED'):validate_study(legacy)
    def test_fixed_ancestor_rejects_input_capacity_host_and_binding_mutations(self):
        for mutation in ('source','capacity','trial','host'):
            plan=copy.deepcopy(self.plans[0]);binding=copy.deepcopy(self.bindings[0]);campaign=copy.deepcopy(self.campaign)
            if mutation=='source':plan['evaluations'][0]['costs'][0]['source_ref']=ref('changed-source')
            elif mutation=='capacity':plan['capacity']['units']+=1
            elif mutation=='trial':binding['trial_refs']=list(reversed(binding['trial_refs']))
            else:campaign['host_session_ref']=ref('wrong-host')
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):docs.validate_binding(binding,plan,campaign)
    def test_file_hash_and_order_and_unknown_fields_rejected(self):
        bad=copy.deepcopy(self.envelopes[0]);bad['segment_bindings'].reverse()
        with self.assertRaisesRegex(ValueError,'ORDER'):docs.read_study_envelope(bad,self.campaign)
        pointer=self.envelopes[0]['study_plan'];path=Path(pointer['path']);path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'CHANGED'):docs.read_study_envelope(self.envelopes[0],self.campaign)
        with self.assertRaises(ValueError):docs.validate_campaign({**self.campaign,'execution_authorization':'APPROVED'})
    def test_envelope_validates_shared_study_and_campaign_once(self):
        with mock.patch.object(docs,'validate_study_plan',wraps=docs.validate_study_plan) as study_check, \
             mock.patch.object(docs,'validate_campaign',wraps=docs.validate_campaign) as campaign_check:
            study,bindings=docs.read_study_envelope(self.envelopes[0],self.campaign)
        self.assertEqual(1,study_check.call_count)
        self.assertEqual(1,campaign_check.call_count)
        self.assertEqual(2,len(bindings))
        self.assertEqual(self.plans[0],study)
    def test_partial_document_graph_is_not_a_complete_research_consumer_input(self):
        with self.assertRaises(ValueError):docs.read_manifest(self.manifest)
if __name__=='__main__':unittest.main()
