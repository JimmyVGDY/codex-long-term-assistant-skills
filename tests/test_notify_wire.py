"""中文：使用临时账本和只追加的原生形状文件，不代表模型或宿主验收。

English: Temporary journals and append-stable native-shaped files; no model/host acceptance.
"""
import copy,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import notify_wire as wire,notify_delivery as old,budget_v5 as budget,review_v5 as review,research_seed as seed,spawn_recovery as recovery
from cp_runtime.context_tool_surface import reader_program,verify_trial_surface
from cp_runtime.routing_context_contract import validate_runtime
from cp_runtime.routing_contract import ref
from cp_runtime.common import atomic_write_json
import test_notify_delivery as nf
import test_routing_context_transport_v2 as tx
import test_research_spawn as sf
class WireIntegration(unittest.TestCase):
    def setUp(self):
        self.helper=nf.NotifyIntegratedTests(methodName='runTest')
        with patch.object(old,'CONTRACT',wire.CONTRACT):self.helper.setUp()
        self.f=self.helper.f;self.path=self.f.path
    def tearDown(self):self.helper.tearDown()
    def delivered(self):
        self.f.reserve();self.f.start();self.f.receipt();helper=tx.TransportV2Tests(methodName='runTest');helper.f=self.f;helper.path=self.path
        emitted,post=helper.read();grant_path=tx.hook._grant_path(self.path,'desktop-session',self.f.child);grant=json.loads(grant_path.read_text())
        state=budget.read_budget(self.path);rid=next(iter(state['reservations']));request=state['permits'][self.f.pid]['request'];program=reader_program(self.path,state,request,'desktop-session',self.f.child)
        events,final=nf.trace(grant['output'],old.binding_for(request),program,self.f.header);self.f.transcript.write_bytes(nf.encoded(events));response=self.f.f.root/'wire-final.json';response.write_text(old.canonical(final),encoding='utf8')
        return rid,grant,grant_path,events,response,program,post
    def test_reader_atomic_event_final_and_fresh_consumer(self):
        rid,g,gp,events,response,program,post=self.delivered();state=budget.read_budget(self.path)
        wire.validate_grant(g,old.binding_for(state['permits'][self.f.pid]['request']))
        self.assertIn(rid,state['context_deliveries']);self.assertIn(rid,state['context_wire_deliveries'])
        kinds=[e['event_type'] for e in budget._read_events(self.path)];self.assertEqual(1,kinds.count('CONTEXT_WIRE_DELIVERED'));self.assertNotIn('CONTEXT_DELIVERED',kinds)
        before=self.path.read_bytes();budget.context_wire_delivered(self.path,state['context_wire_deliveries'][rid]);self.assertEqual(before,self.path.read_bytes())
        self.f.stop();review.record_semantic(self.f.review_dir,self.f.pid,response)
        proof=verify_trial_surface(self.path,budget.read_budget(self.path),rid,self.f.transcript);self.assertEqual('desktop-tool-surface/3',proof['schema_version'])
        node=shutil.which('node')
        if node:
            shim='let calls=0;const sent=[];const tools={exec_command:async()=>{calls++;return {exit_code:0,output:'+json.dumps(g['wire'])+'}}};const notify=x=>sent.push(x);const text=x=>sent.push(x);(async()=>{'+program+';process.stdout.write(JSON.stringify({calls,sent}));})().catch(e=>{console.error(e);process.exit(1)});'
            path=self.f.f.root/'wire.cjs';path.write_text(shim,encoding='utf8');result=json.loads(subprocess.check_output([node,str(path)],text=True,encoding='utf8'))
            w=json.loads(g['wire']);self.assertEqual({'calls':1,'sent':[old.canonical(p) for p in w['notifications']]+[w['summary']]},result)
    def test_wrong_wire_raw_or_notification_cannot_pass(self):
        rid,g,gp,events,response,program,post=self.delivered();state=budget.read_budget(self.path);binding=old.binding_for(state['permits'][self.f.pid]['request'])
        for field in ('output_sha256','wire_sha256','wire_bytes','raw_bytes','delivery_contract'):
            bad=copy.deepcopy(g);bad[field]='f'*64 if 'sha256' in field else 1 if field.endswith('bytes') else 'same-call-notify/3'
            with self.subTest(field=field),self.assertRaises(ValueError):wire.validate_grant(bad,binding)
        bad=copy.deepcopy(g);w=json.loads(bad['wire']);w['raw_output_ref']=ref('wrong');bad['wire']=old.canonical(w)+'\n';bad['wire_sha256']=old.sha(bad['wire']);bad['wire_bytes']=len(bad['wire'].encode())
        with self.assertRaisesRegex(ValueError,'WIRE_RAW_BINDING'):wire.validate_grant(bad,binding)
        gp.write_text(json.dumps(bad),encoding='utf8')
        with self.assertRaises(ValueError):self.f.stop()
        self.assertNotIn(rid,budget.read_budget(self.path)['context_finals'])
    def test_wrong_call_old_event_and_changed_atomic_event_rejected(self):
        rid,g,gp,events,response,program,post=self.delivered();state=budget.read_budget(self.path);event=state['context_wire_deliveries'][rid]
        with self.assertRaises(ValueError):budget.context_wire_delivered(self.path,{**event,'wire_output_ref':ref('wrong')})
        isolated=copy.deepcopy(state);isolated['context_deliveries'].clear();isolated['context_wire_deliveries'].clear()
        with self.assertRaises(ValueError):budget._apply(isolated,{'event_type':'CONTEXT_WIRE_DELIVERED','data':{**event,'call_ref':ref('wrong')}})
        with self.assertRaisesRegex(ValueError,'ATOMIC_EVENT_REQUIRED'):budget._apply(isolated,{'event_type':'CONTEXT_DELIVERED','data':{'reservation_id':rid,'call_ref':event['call_ref'],'output_ref':event['raw_output_ref']}})
    def test_grant_saved_post_append_failure_recovers_same_bytes(self):
        self.f.reserve();self.f.start();self.f.receipt();helper=tx.TransportV2Tests(methodName='runTest');helper.f=self.f;helper.path=self.path;data=helper.tool()
        tx.hook.child_tool(self.path,data);gp=tx.hook._grant_path(self.path,'desktop-session',self.f.child);original=gp.read_bytes();emitted=json.loads(original)['wire'];post={**data,'hook_event_name':'PostToolUse','tool_response':emitted}
        with patch.object(budget,'context_wire_delivered',side_effect=OSError('injected before append')):
            with self.assertRaises(OSError):tx.hook.child_tool(self.path,post)
        state=budget.read_budget(self.path);self.assertFalse(state['context_deliveries']);tx.hook.child_tool(self.path,post);self.assertEqual(original,gp.read_bytes());self.assertTrue(budget.read_budget(self.path)['context_wire_deliveries'])
    def test_runtime_retains_evaluation_combination(self):
        rt=budget.read_budget(self.path)['root_binding']['context_runtime'];rt['evaluation_contract']='isolated-review-phases/1'
        from cp_runtime.routing_context_contract import ISOLATED_PHASES
        rt['evaluation_contract']=ISOLATED_PHASES;validate_runtime(rt)
class SpawnRecoveryIntegration(unittest.TestCase):
    def setUp(self):
        self.f=sf.SpawnIndexTests(methodName='runTest');self.f.setUp();self.context=self.f.f;self.path=self.f.path;self.session=self.f.session;self.args=self.context.parent['tool_input'];self.task='/root/'+self.args['task_name'];self.role=self.args['agent_type'];self.call_id=self.context.parent['tool_use_id']
        self.call={'type':'response_item','payload':{'type':'function_call','name':'collaboration.spawn_agent','call_id':self.call_id,'arguments':json.dumps(self.args)}}
        self.result={'type':'response_item','payload':{'type':'function_call_output','call_id':self.call_id,'output':json.dumps({'task_name':self.task})}}
        self.parent=self.context.home/'sessions'/('rollout-'+self.session+'.jsonl');header={'type':'session_meta','payload':{'id':self.session,'cwd':str(self.context.f.repo),'source':'cli'}}
        raws=[(json.dumps(v)+'\n').encode() for v in (header,self.call,self.result)];self.parent.write_bytes(b''.join(raws));self.rows={'call':{'offset':len(raws[0]),'length':len(raws[1])},'result':{'offset':len(raws[0])+len(raws[1]),'length':len(raws[2])}}
    def tearDown(self):self.f.tearDown()
    def original_intent(self,before_reserve=False):
        real=seed._immutable
        def fail_index(p,v):
            if v.get('status')=='READY':raise OSError('index failure')
            return real(p,v)
        with patch.object(seed,'_immutable',side_effect=fail_index):
            if before_reserve:
                with patch.object(budget,'approve_and_reserve',side_effect=OSError('before reserve')):
                    with self.assertRaises(OSError):self.f.reserve()
            else:
                with self.assertRaises(OSError):self.f.reserve()
        state=budget.read_budget(self.path);self.rid=next(iter(state['reservations']),None);self.permit=state['permits'][self.context.pid]
        self.segment={'ordinal':1,'ledger_path':str(self.path),'calls':[{'dispatch_key':self.args['task_name'],'request_ref':seed.request_core_ref(self.permit['request']),'profile_id':self.permit['selection']['approved_profile']}]}
        self.plan={'repo_path':str(self.context.f.repo),'host_session_ref':ref(self.session),'identity':{k:state['identity'][k] for k in ('project_id','repo_fingerprint')},'segments':[self.segment]}
        state_dir=seed._directory(self.f.source);state_dir.mkdir(exist_ok=True);atomic_write_json(state_dir/'admitted.json',{'plan_ref':ref(self.plan)})
    def recover(self,evidence):
        p=self.context.f.root/'recovery-evidence.json';atomic_write_json(p,evidence)
        with patch.object(seed,'definition',return_value=({},self.plan,{}, {},{})),patch.object(seed,'_segment_state',side_effect=lambda *a,**k:({}, {}, {},self.segment,budget.read_budget(self.path))):
            return seed.recover_spawn_intent(self.f.source,session=self.session,task_path=self.task,role=self.role,original_host_call_id=self.call_id,evidence_path=p,cwd=str(self.context.f.repo),directory=self.f.registry)
    def test_append_stable_created_recovery_only_metadata_and_replay(self):
        self.original_intent();e={'schema_version':'spawn-recovery-evidence/1','parent':recovery.capture_native_records(self.parent,self.rows),'child_path':str(self.context.transcript)}
        with self.parent.open('ab') as f:f.write((json.dumps({'type':'event_msg','payload':{'type':'later'}})+'\n').encode())
        before=budget._usage(budget.read_budget(self.path));r=self.recover(e);self.assertEqual('created',r['outcome']);self.assertFalse(r['spawn']);self.assertFalse(r['refund']);self.assertEqual(before['resources'],budget._usage(budget.read_budget(self.path))['resources'])
        self.assertEqual(r,self.recover(e))
        with self.assertRaisesRegex(ValueError,'SPAWN_REPLAY'):self.f.reserve()
        budget.record_observation(self.path,agent_id=self.context.child,phase='stop',outcome='UNKNOWN');budget.close(self.path,outcome='PARTIAL',evidence_ref=ref('recovery-then-closed'))
        sealed=self.path.read_bytes();self.assertEqual(r,self.recover(e));self.assertEqual(sealed,self.path.read_bytes())
    def test_wrong_interval_call_rewrite_replacement_and_truncate_rejected(self):
        e=recovery.capture_native_records(self.parent,self.rows);recovery.verify_native_records(e)
        bad=copy.deepcopy(e);bad['records']['call']['offset']+=1
        with self.assertRaises(ValueError):recovery.verify_native_records(bad)
        with self.assertRaisesRegex(ValueError,'CALL_BINDING'):recovery.classify(e,session=self.session,task_path=self.task,role=self.role,host_call_id='wrong',parameters_ref=ref(self.args),cwd=str(self.context.f.repo))
        raw=self.parent.read_bytes();self.parent.write_bytes(raw.replace(b'spawn-one',b'spawn-two'))
        with self.assertRaises(ValueError):recovery.verify_native_records(e)
        self.parent.write_bytes(raw);replacement=self.parent.with_suffix('.tmp');replacement.write_bytes(raw);replacement.replace(self.parent)
        with self.assertRaises(ValueError):recovery.verify_native_records(e)
        e=recovery.capture_native_records(self.parent,self.rows);self.parent.write_bytes(raw[:-1])
        with self.assertRaises(ValueError):recovery.verify_native_records(e)
    def test_only_call_or_error_stays_unknown_and_preserves_reservation(self):
        self.original_intent();e={'schema_version':'spawn-recovery-evidence/1','parent':recovery.capture_native_records(self.parent,{'call':self.rows['call']}),'child_path':''};r=self.recover(e)
        self.assertEqual('UNKNOWN',r['outcome']);self.assertNotIn(self.rid,budget.read_budget(self.path)['host_receipts'])
        with self.assertRaisesRegex(ValueError,'RECOVERY_REQUIRED'):self.f.reserve()
        self.result['payload']['output']='{"error":"could not start"}';header_raw=self.parent.read_bytes()[:self.rows['call']['offset']];call_raw=(json.dumps(self.call)+'\n').encode();result_raw=(json.dumps(self.result)+'\n').encode();self.parent.write_bytes(header_raw+call_raw+result_raw);rows={**self.rows,'result':{'offset':len(header_raw)+len(call_raw),'length':len(result_raw)}}
        status,_=recovery.classify(recovery.capture_native_records(self.parent,rows),session=self.session,task_path=self.task,role=self.role,host_call_id=self.call_id,parameters_ref=ref(self.args),cwd=str(self.context.f.repo));self.assertEqual('UNKNOWN',status)
        for value in ({'task_name':self.task,'error':'failed'},{'task_name':self.task,'child_uuid':'invented'}):
            self.result['payload']['output']=json.dumps(value);result_raw=(json.dumps(self.result)+'\n').encode();self.parent.write_bytes(header_raw+call_raw+result_raw);rows['result']['length']=len(result_raw)
            status,_=recovery.classify(recovery.capture_native_records(self.parent,rows),session=self.session,task_path=self.task,role=self.role,host_call_id=self.call_id,parameters_ref=ref(self.args),cwd=str(self.context.f.repo));self.assertEqual('UNKNOWN',status)
    def test_before_reservation_unknown_does_not_create_or_charge(self):
        self.original_intent(before_reserve=True);before=self.path.read_bytes();e={'schema_version':'spawn-recovery-evidence/1','parent':recovery.capture_native_records(self.parent,{'call':self.rows['call']}),'child_path':''}
        self.assertEqual('UNKNOWN',self.recover(e)['outcome']);self.assertEqual(before,self.path.read_bytes());self.assertFalse(budget.read_budget(self.path)['reservations'])
    def test_wrong_child_role_cannot_recover_created(self):
        self.original_intent();header=copy.deepcopy(self.context.header);header['payload']['source']['subagent']['thread_spawn']['agent_role']='cp_review_security_access';self.context.transcript.write_text(json.dumps(header)+'\n',encoding='utf8')
        e={'schema_version':'spawn-recovery-evidence/1','parent':recovery.capture_native_records(self.parent,self.rows),'child_path':str(self.context.transcript)}
        with self.assertRaisesRegex(ValueError,'CHILD_HEADER_IDENTITY'):self.recover(e)
        self.assertNotIn(self.rid,budget.read_budget(self.path)['host_receipts'])
if __name__=='__main__':unittest.main()
