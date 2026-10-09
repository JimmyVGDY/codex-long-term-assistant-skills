"""中文：合成边界测试，不调用模型、不使用宿主根或统计金标。

English: Synthetic boundary tests; no model calls, host roots or statistical gold.
"""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import research_seed as seed
from cp_runtime.research_bootstrap import deny_statistics
from cp_runtime.routing_contract import ref,policy_digest
from cp_runtime.common import atomic_write_json
from cp_runtime.approval import _approval_payload,load_approval

V=lambda n:{'units':n,'attempts':n,'astra_attempts':0,'astra_high_attempts':0}
NOW='2026-10-08T00:00:00+00:00';EXPIRES='2099-01-01T00:00:00+00:00'
REAL_ANCHOR=seed._anchor
class SeedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.repo=self.base/'repo';self.repo.mkdir()
        self.registry=self.base/'registry';self.registry.mkdir();self.session='real-shaped-fixture-session'
        self.runtime={'bootstrap_contract':seed.CONTRACT};self.identity={'project_id':'fixture','repo_fingerprint':ref('fixture-repo')}
        self.anchor=self.registry/'anchor.json';self.anchor.write_text('{}',encoding='utf8')
        self.approval=self.base/'approval.json';self.dir=self.base/'stage';self.dir.mkdir()
        self.plan={'schema_version':'bootstrap-review-plan/1','stage_id':'bootstrap-fixture','identity':self.identity,'policy_digest':policy_digest(),
          'host_session_ref':ref(self.session),'repo_path':str(self.repo),'candidate_payload_digest':ref('candidate')[7:],'installation':{},'runtime_ref':ref(self.runtime),
          'created_at':'2000-01-01T00:00:00+00:00','expires_at':EXPIRES,
          'predecessor':{'registry_path':str(self.anchor),'registry_bytes_sha256':hashlib.sha256(self.anchor.read_bytes()).hexdigest(),
            'ledger_path':str(self.base/'old.jsonl'),'final_record_hash':'a'*64,'closed_outcome':'PARTIAL'},
          'segments':[{'ordinal':i,'task_id':f'root{i}','ledger_path':str(self.base/f'budget{i}.jsonl'),'capacity':V(1),
           'calls':[{'dispatch_key':f'rs_fixture{i}','request_ref':ref(f'request{i}'),'review_material_ref':ref(f'material{i}'),
             'profile_id':'g6-luna-medium','cost':{'profile_id':'g6-luna-medium','scenario_ref':ref(f'scenario{i}'),'cost_basis':'bootstrap-call-cap','measurement':'declared_proxy','plan_cost':1,'reserve_units':1,'latency_ms':10000,'source_ref':ref(f'material{i}')}}]} for i in (1,2)],'capacity':V(2)}
        self.material=self.base/'code.txt';self.material.write_text('source',encoding='utf8')
        self.manifest={'schema_version':'bootstrap-material-manifest/1','plan_ref':ref(self.plan),'materials':[{'path':str(self.material),'bytes_sha256':hashlib.sha256(self.material.read_bytes()).hexdigest()}]}
        approval=_approval_payload('approval1','fixture','bootstrap-fixture',['make-effective'],'local','b'*64,EXPIRES,'explicit-user-approval',seed.approval_scope(ref(self.plan),ref(self.manifest),'bootstrap-fixture'),True)
        atomic_write_json(self.approval,approval,seal=True)
        self.grant={'schema_version':'research-stage-grant/1','grant_id':'grant1','campaign_plan_ref':ref(self.plan),
          'campaign_manifest_ref':ref(self.manifest),'identity':self.identity,'host_session_ref':ref(self.session),'stage_id':'bootstrap-fixture',
          'scope':'BOOTSTRAP_CODE_REVIEW_ONLY','capacity':V(2),'approved_at':'2000-01-01T00:00:00+00:00','expires_at':EXPIRES,
          'approval_source':{'path':str(self.approval),'immutable_fingerprint':seed.fingerprint(approval)}}
        self.definition={'schema_version':'bootstrap-stage-definition/1','plan':self.put('plan.json',self.plan),
          'manifest':self.put('manifest.json',self.manifest),'grant':self.put('grant.json',self.grant)}
        d=self.dir/'definition.json';atomic_write_json(d,self.definition)
        self.source={'path':str(d),'definition_ref':ref(self.definition)}
        self.states={}
        for s in self.plan['segments']:
            env=self.base/f'envelope{s["ordinal"]}.json';atomic_write_json(env,{'routing':{'research_seed':{'source':self.source,'ordinal':s['ordinal']}}})
            self.states[s['ledger_path']]={'execution_mode':'EVALUATION','sources':{'root_envelope':str(env)},
             'root_binding':{'context_runtime':self.runtime,'host_session_ref':ref(self.session)},
             'identity':{**self.identity,'task_id':s['task_id']},'capacity':s['capacity'],'max_depth':1,'closed':False,'permits':{}}
        self.patches=[patch.object(seed,'stable_repo_fingerprint',return_value=self.identity['repo_fingerprint']),
          patch('cp_runtime.seed_installation.verify_installation',return_value={'ok':True}),
          patch('cp_runtime.common.repo_snapshot',return_value={'sha256':'b'*64}),
          patch.object(seed,'_anchor',side_effect=self.anchor_check),patch.object(seed.budget,'read_budget',side_effect=lambda p:self.states[str(p)]),
          patch.object(seed.budget,'_read_events',return_value=[{'record_hash':'c'*64}])]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def anchor_check(self,*args,**kwargs):
        if hashlib.sha256(self.anchor.read_bytes()).hexdigest()!=self.plan['predecessor']['registry_bytes_sha256']:raise ValueError('SEED_ANCHOR_CHANGED')
    def put(self,name,value):
        p=self.dir/name;atomic_write_json(p,value)
        return {'path':str(p),'canonical_ref':ref(value),'bytes_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    def admitted(self):return seed.admit(self.source,cwd=str(self.repo),session=self.session,now=NOW,directory=self.registry)
    def advance(self,n=1,now=NOW):return seed.advance(self.source,ordinal=n,cwd=str(self.repo),session=self.session,now=now,directory=self.registry)
    def test_two_segments_consume_approval_once_and_never_rewrite_admitted(self):
        self.admitted();a=(self.dir/'seed-state/admitted.json').read_bytes();authority=self.approval.read_bytes()
        self.advance();self.states[self.plan['segments'][0]['ledger_path']]['closed']=True;self.advance(2)
        self.assertEqual(authority,self.approval.read_bytes());self.assertEqual(a,(self.dir/'seed-state/admitted.json').read_bytes())
        self.assertEqual(V(1),seed._read(self.dir/'seed-state/claim-2.json')['capacity'])
    def test_duplicate_commit_and_admission_are_idempotent(self):
        a=self.admitted();self.assertEqual(a,self.admitted());h=self.advance();self.assertEqual(h,self.advance())
    def test_rehashing_all_descendants_still_rejected_by_fixed_grant(self):
        changed=copy.deepcopy(self.plan);changed['candidate_payload_digest']=ref('different-candidate')[7:]
        m={**self.manifest,'plan_ref':ref(changed)}
        d={**self.definition,'plan':self.put('changed-plan.json',changed),'manifest':self.put('changed-manifest.json',m)}
        p=self.dir/'changed-definition.json';atomic_write_json(p,d)
        with self.assertRaisesRegex(ValueError,'FIXED_GRANT_SCOPE'):seed.definition({'path':str(p),'definition_ref':ref(d)})
    def test_second_segment_cannot_skip_active_predecessor(self):
        self.admitted();self.advance()
        with self.assertRaisesRegex(ValueError,'PREDECESSOR_ACTIVE'):self.advance(2)
    def test_concurrent_same_next_claim_returns_one_commit(self):
        self.admitted()
        with ThreadPoolExecutor(max_workers=2) as pool:heads=list(pool.map(lambda _:self.advance(),range(2)))
        self.assertEqual(heads[0],heads[1]);self.assertEqual(1,len(list((self.dir/'seed-state').glob('claim-*.json'))))
    def test_expiry_does_not_allow_new_claim_or_reserve(self):
        self.admitted()
        with self.assertRaisesRegex(ValueError,'EXPIRED'):self.advance(now='2100-01-01T00:00:00+00:00')
        self.assertFalse((self.dir/'seed-state/claim-1.json').exists())
    def test_consumed_admission_recovers_after_expiry_without_rewriting_fact(self):
        original=self.admitted();raw=(self.dir/'seed-state/admitted.json').read_bytes()
        restored=seed.admit(self.source,cwd=str(self.repo),session=self.session,now='2100-01-01T00:00:00+00:00',directory=self.registry)
        self.assertEqual(original,restored);self.assertEqual(raw,(self.dir/'seed-state/admitted.json').read_bytes())
        self.assertTrue((self.dir/'seed-state/suspended.json').exists())
    def test_revoked_consumed_admission_only_recovers_metadata(self):
        original=self.admitted();a=load_approval(self.approval);a['status']='revoked';atomic_write_json(self.approval,a,seal=True)
        self.assertEqual(original,self.admitted())
        with self.assertRaisesRegex(ValueError,'EXPIRED'):self.advance()
    def test_authority_baseline_changed_before_admission_is_denied(self):
        with patch('cp_runtime.common.repo_snapshot',return_value={'sha256':'d'*64}),self.assertRaisesRegex(ValueError,'AUTHORITY_BASELINE'):self.admitted()
        self.assertEqual('active',load_approval(self.approval)['status'])
    def test_changed_anchor_blocks_first_advance(self):
        self.admitted();self.anchor.write_text('changed',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'ANCHOR_CHANGED'):self.advance()
    def test_stage_scope_cannot_include_statistical_gold(self):
        p=copy.deepcopy(self.plan);p['clean']=True;d={**self.definition,'plan':self.put('gold-plan.json',p)}
        path=self.dir/'gold-definition.json';atomic_write_json(path,d)
        with self.assertRaisesRegex(ValueError,'PLAN_FIELDS'):seed.definition({'path':str(path),'definition_ref':ref(d)})
    def test_bootstrap_cannot_export_statistical_trace(self):
        with self.assertRaisesRegex(ValueError,'NO_STATISTICAL_GOLD'):deny_statistics(self.states[self.plan['segments'][0]['ledger_path']])
    def test_unique_names_have_host_limit_and_bind_ordinal(self):
        a=seed.task_name('x'*100,1,ref('request'));b=seed.task_name('x'*100,2,ref('request'))
        self.assertLessEqual(len(a),64);self.assertNotEqual(a,b)
    def test_wrong_actual_host_or_repository_fails_before_authority(self):
        with self.assertRaisesRegex(ValueError,'REAL_HOST'):seed.admit(self.source,cwd=str(self.repo),session='another',now=NOW,directory=self.registry)
        self.assertEqual('active',load_approval(self.approval)['status'])
    def test_head_commit_failure_recovers_same_claim_after_expiry(self):
        self.admitted();original=seed.atomic_write_json
        def write(path,value,*args,**kwargs):
            if path==seed._head(self.session,self.registry):raise OSError('head-injection')
            return original(path,value,*args,**kwargs)
        with patch.object(seed,'atomic_write_json',side_effect=write),self.assertRaisesRegex(OSError,'head-injection'):self.advance()
        before=(self.dir/'seed-state/claim-1.json').read_bytes();self.advance(now='2100-01-01T00:00:00+00:00')
        self.assertEqual(before,(self.dir/'seed-state/claim-1.json').read_bytes())
        with self.assertRaisesRegex(ValueError,'DISPATCH_DENIED'):seed.assert_dispatch(Path(self.plan['segments'][0]['ledger_path']),session=self.session,cwd=str(self.repo),now='2100-01-01T00:00:00+00:00',directory=self.registry)
    def test_claim_only_failure_closes_metadata_after_expiry_without_head_or_refund(self):
        self.admitted();original=seed._immutable
        def write(path,value):
            if path.name=='transition-1.json':raise OSError('transition-injection')
            return original(path,value)
        with patch.object(seed,'_immutable',side_effect=write),self.assertRaisesRegex(OSError,'transition-injection'):self.advance()
        claim=(self.dir/'seed-state/claim-1.json').read_bytes()
        result=self.advance(now='2100-01-01T00:00:00+00:00')
        self.assertEqual('SUSPENDED_NO_DISPATCH',result['outcome']);self.assertFalse(result['refund'])
        self.assertEqual(claim,(self.dir/'seed-state/claim-1.json').read_bytes());self.assertFalse(seed._head(self.session,self.registry).exists())
    def test_claim_only_revocation_closes_same_metadata(self):
        self.admitted();original=seed._immutable
        def write(path,value):
            if path.name=='transition-1.json':raise OSError('transition-injection')
            return original(path,value)
        with patch.object(seed,'_immutable',side_effect=write),self.assertRaises(OSError):self.advance()
        a=load_approval(self.approval);a['status']='revoked';atomic_write_json(self.approval,a,seal=True)
        first=self.advance();self.assertEqual(first,self.advance());self.assertFalse(first['refund'])
    def test_real_manifest_to_definition_to_admit_without_installation_mock(self):
        from cp_runtime.payload_integrity import iter_payload_files,write_manifest
        cache=self.base/'real-package';cache.mkdir()
        for relative,source in iter_payload_files(ROOT):
            target=cache/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
        manifest=write_manifest(cache,'fixture','0.0.1')
        self.plan['candidate_payload_digest']=manifest['payload_digest']
        self.plan['installation']={'payload_root':str(cache),'manifest_path':str(cache/'PLUGIN_PAYLOAD_MANIFEST.json'),
            'runtime_files':[{'package_path':row['path'],'live_path':str(ROOT/row['path'])} for row in manifest['files'] if row['path'].startswith(('runtime/cp_runtime/','hooks/'))]}
        self.manifest['plan_ref']=ref(self.plan)
        approval=_approval_payload('real-chain','fixture','bootstrap-fixture',['make-effective'],'local','b'*64,EXPIRES,'explicit-user-approval',seed.approval_scope(ref(self.plan),ref(self.manifest),'bootstrap-fixture'),True)
        atomic_write_json(self.approval,approval,seal=True)
        self.grant.update(campaign_plan_ref=ref(self.plan),campaign_manifest_ref=ref(self.manifest),approval_source={'path':str(self.approval),'immutable_fingerprint':seed.fingerprint(approval)})
        self.definition={'schema_version':'bootstrap-stage-definition/1','plan':self.put('plan.json',self.plan),'manifest':self.put('manifest.json',self.manifest),'grant':self.put('grant.json',self.grant)}
        path=self.dir/'definition.json';atomic_write_json(path,self.definition);self.source={'path':str(path),'definition_ref':ref(self.definition)}
        self.patches[1].stop()
        self.assertEqual(manifest['payload_digest'],seed.definition(self.source)[1]['candidate_payload_digest'])
        admitted=self.admitted();self.assertEqual(ref(self.plan),admitted['plan_ref']);self.assertEqual('consumed',load_approval(self.approval)['status'])
    def test_closed_head_archive_is_immutable_and_supports_explicit_future_anchor(self):
        self.admitted();head=self.advance()
        for state in self.states.values():state.update(closed=True,outcome='PARTIAL')
        archived=seed.archive_closed_head(self.session,directory=self.registry)
        self.assertEqual(head,seed._read(archived));self.assertEqual(head,seed._read(seed._head(self.session,self.registry)))
        future=copy.deepcopy(self.plan);future['predecessor']={'registry_path':str(archived),'registry_bytes_sha256':hashlib.sha256(archived.read_bytes()).hexdigest(),'ledger_path':head['ledger_path'],'final_record_hash':'c'*64,'closed_outcome':'PARTIAL'}
        self.states[head['ledger_path']]['outcome']='PARTIAL'
        REAL_ANCHOR(future,self.session,self.registry)
        altered=copy.deepcopy(future);altered['identity']['repo_fingerprint']=ref('another-repo')
        with self.assertRaisesRegex(ValueError,'ANCHOR_PROJECT'):REAL_ANCHOR(altered,self.session,self.registry)
    def test_open_head_cannot_be_archived_for_new_stage(self):
        self.admitted();self.advance()
        with self.assertRaisesRegex(ValueError,'PREDECESSOR_ACTIVE'):seed.archive_closed_head(self.session,directory=self.registry)
    def test_new_explicit_stage_advances_from_archived_closed_head(self):
        self.admitted();oldhead=self.advance()
        for state in self.states.values():state.update(closed=True,outcome='PARTIAL')
        archive=seed.archive_closed_head(self.session,directory=self.registry);archive_bytes=archive.read_bytes()
        newdir=self.base/'next-stage';newdir.mkdir();plan=copy.deepcopy(self.plan);plan['stage_id']='next-stage'
        plan['predecessor']={'registry_path':str(archive),'registry_bytes_sha256':hashlib.sha256(archive_bytes).hexdigest(),'ledger_path':oldhead['ledger_path'],'final_record_hash':'c'*64,'closed_outcome':'PARTIAL'}
        for i,s in enumerate(plan['segments'],3):s['task_id']=f'root{i}';s['ledger_path']=str(self.base/f'budget{i}.jsonl')
        material={**self.manifest,'plan_ref':ref(plan)};authority=newdir/'approval.json'
        a=_approval_payload('next-stage-approval','fixture','next-stage',['make-effective'],'local','b'*64,EXPIRES,'explicit-user-approval',seed.approval_scope(ref(plan),ref(material),'next-stage'),True);atomic_write_json(authority,a,seal=True)
        grant={**self.grant,'stage_id':'next-stage','campaign_plan_ref':ref(plan),'campaign_manifest_ref':ref(material),'approval_source':{'path':str(authority),'immutable_fingerprint':seed.fingerprint(a)}}
        def ptr(name,value):
            p=newdir/name;atomic_write_json(p,value);return {'path':str(p),'canonical_ref':ref(value),'bytes_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        definition={'schema_version':'bootstrap-stage-definition/1','plan':ptr('plan.json',plan),'manifest':ptr('materials.json',material),'grant':ptr('grant.json',grant)}
        path=newdir/'definition.json';atomic_write_json(path,definition);source={'path':str(path),'definition_ref':ref(definition)}
        for s in plan['segments']:
            env=newdir/f'envelope{s["ordinal"]}.json';atomic_write_json(env,{'routing':{'research_seed':{'source':source,'ordinal':s['ordinal']}}})
            self.states[s['ledger_path']]={**copy.deepcopy(self.states[oldhead['ledger_path']]),'closed':False,'sources':{'root_envelope':str(env)},'identity':{**self.identity,'task_id':s['task_id']}}
        with patch.object(seed,'_anchor',side_effect=REAL_ANCHOR):
            admitted=seed.admit(source,cwd=str(self.repo),session=self.session,now=NOW,directory=self.registry)
            head=seed.advance(source,ordinal=1,cwd=str(self.repo),session=self.session,now=NOW,directory=self.registry)
            approval_bytes=authority.read_bytes();head_bytes=seed._head(self.session,self.registry).read_bytes()
            recovered=seed.admit(source,cwd=str(self.repo),session=self.session,now=NOW,directory=self.registry)
            self.assertEqual(admitted,recovered);self.assertEqual(approval_bytes,authority.read_bytes());self.assertEqual(head_bytes,seed._head(self.session,self.registry).read_bytes())
        self.assertEqual(source,head['source']);self.assertEqual(archive_bytes,archive.read_bytes())
        self.assertEqual(oldhead,seed._read(archive));self.assertEqual('consumed',load_approval(authority)['status'])
    def test_second_segment_head_commit_interruption_blocks_stage_archive(self):
        self.admitted();self.advance();self.states[self.plan['segments'][0]['ledger_path']].update(closed=True,outcome='PARTIAL')
        original=seed.atomic_write_json
        def write(path,value,*args,**kwargs):
            if path==seed._head(self.session,self.registry):raise OSError('head-2-injection')
            return original(path,value,*args,**kwargs)
        with patch.object(seed,'atomic_write_json',side_effect=write),self.assertRaises(OSError):self.advance(2)
        with self.assertRaisesRegex(ValueError,'STAGE_NOT_TERMINAL'):seed.archive_closed_head(self.session,directory=self.registry)
        self.states[self.plan['segments'][1]['ledger_path']].update(closed=True,outcome='PARTIAL')
        with self.assertRaisesRegex(ValueError,'TRANSACTION_UNRESOLVED'):seed.archive_closed_head(self.session,directory=self.registry)
    def test_history_anchor_requires_matching_current_head(self):
        self.admitted();head=self.advance()
        for state in self.states.values():state.update(closed=True,outcome='PARTIAL')
        archive=seed.archive_closed_head(self.session,directory=self.registry);plan=copy.deepcopy(self.plan)
        plan['predecessor']={'registry_path':str(archive),'registry_bytes_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'ledger_path':head['ledger_path'],'final_record_hash':'c'*64,'closed_outcome':'PARTIAL'}
        seed._head(self.session,self.registry).unlink()
        with self.assertRaisesRegex(ValueError,'HISTORY_NOT_CURRENT_TIP'):REAL_ANCHOR(plan,self.session,self.registry)

if __name__=='__main__':unittest.main()
