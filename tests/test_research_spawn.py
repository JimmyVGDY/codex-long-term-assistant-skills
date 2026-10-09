"""中文：使用实际临时 V5 账本和原生形状头部，阶段授权使用模拟。

English: Actual temporary V5 journals and native-shaped headers; stage authority mocked.
"""
import json,sys,unittest,copy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import research_seed as seed,budget_v5 as budget,routing_hook_v5 as hook
from cp_runtime.routing_context_contract import runtime,MODE_V2,digest
from cp_runtime.routing_contract import ref
from cp_runtime.common import atomic_write_json
import test_routing_v5_context as fx

class SpawnIndexTests(unittest.TestCase):
    def setUp(self):
        self.f=fx.ContextV5Tests(methodName='runTest')
        with patch.object(fx,'runtime',lambda reader,python:runtime(reader,python,transport_mode=MODE_V2)):self.f.setUp()
        self.path=self.f.path;self.registry=self.f.f.root/'bindings';self.session='desktop-session'
        self.source={'path':str(self.f.f.root/'seed-definition.json'),'definition_ref':ref('stage-authority-mocked')}
        atomic_write_json(seed._head(self.session,self.registry),{'source':self.source})
        call={'dispatch_key':'eval_one','request_ref':ref(self.f.request),'profile_id':self.f.selected['approved_profile']}
        self.segment={'calls':[call]}
        self.dispatch=patch.object(seed,'assert_dispatch',side_effect=lambda *a,**k:({'source':self.source},{'repo_path':str(self.f.f.repo)},self.segment,k['state'] if k.get('state') is not None else budget.read_budget(self.path)))
        self.dispatch.start()
    def tearDown(self):self.dispatch.stop();self.f.tearDown()
    def reserve(self):
        data=self.f.parent;args=data['tool_input']
        def callback(recheck):
            return budget.approve_and_reserve(self.path,permit_id=self.f.pid,host_dispatch_id=data['tool_use_id'],model=args['model'],effort=args['reasoning_effort'],agent_type=args['agent_type'],transport_audit_sha256=digest(args['message'].encode()),snapshot_loader=self.f.loader,binding_guard=recheck)
        return seed.reserve(self.path,data,args,callback,directory=self.registry)
    def test_start_before_post_uses_real_header_and_unique_preindex(self):
        rid=self.reserve()['reservation_id']
        self.assertEqual(self.path,seed.event_path(self.f.child_data,directory=self.registry))
        self.f.start();self.assertNotIn(rid,budget.read_budget(self.path)['host_receipts'])
        self.f.receipt();state=budget.read_budget(self.path)
        self.assertEqual(ref(self.f.child),state['host_identity_links'][rid]['agent_ref']);self.assertIn(rid,state['host_receipts'])
    def test_post_loss_does_not_invent_receipt_and_real_post_recovers(self):
        rid=self.reserve()['reservation_id'];seed.event_path(self.f.child_data,directory=self.registry);self.f.start()
        self.assertEqual({},budget.read_budget(self.path)['host_receipts'])
        self.f.receipt();self.f.receipt()
        self.assertEqual(1,len(budget.read_budget(self.path)['host_receipts']))
    def test_unknown_path_cannot_fall_back_to_current_head(self):
        self.reserve();header=copy.deepcopy(self.f.header);header['payload']['source']['subagent']['thread_spawn']['agent_path']='/root/unknown'
        self.f.transcript.write_text(json.dumps(header)+'\n',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'UNKNOWN_CHILD'):seed.event_path(self.f.child_data,directory=self.registry)
    def test_same_path_second_child_is_rejected(self):
        self.reserve();seed.event_path(self.f.child_data,directory=self.registry)
        child='22345678-1234-1234-1234-123456789012';path=self.f.transcript.with_name('rollout-'+child+'.jsonl')
        header=copy.deepcopy(self.f.header);header['payload']['id']=child;path.write_text(json.dumps(header)+'\n',encoding='utf8')
        data={**self.f.child_data,'agent_id':child,'transcript_path':str(path)}
        with self.assertRaisesRegex(ValueError,'IMMUTABLE_CONFLICT'):seed.event_path(data,directory=self.registry)
    def test_index_write_failure_denies_spawn_and_retains_reservation(self):
        original=seed._immutable
        def write(path,value):
            if value.get('status')=='READY':raise OSError('index-injection')
            return original(path,value)
        with patch.object(seed,'_immutable',side_effect=write),self.assertRaisesRegex(OSError,'index-injection'):self.reserve()
        state=budget.read_budget(self.path);self.assertEqual(1,len(state['reservations']))
        with self.assertRaisesRegex(ValueError,'RECOVERY_REQUIRED'):self.reserve()
    def test_repeated_ready_spawn_denied_without_second_charge(self):
        self.reserve()
        with self.assertRaisesRegex(ValueError,'SPAWN_REPLAY'):self.reserve()
        self.assertEqual(1,len(budget.read_budget(self.path)['reservations']))
    def test_cwd_header_mismatch_is_not_index_authority(self):
        self.reserve();header=copy.deepcopy(self.f.header);header['payload']['cwd']=str(self.f.f.root)
        self.f.transcript.write_text(json.dumps(header)+'\n',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'CHILD_REPOSITORY'):seed.event_path(self.f.child_data,directory=self.registry)

if __name__=='__main__':unittest.main()
