"""中文：使用原生形状的临时证据，不做真实调用或重判历史。

English: Native-shaped temporary evidence; no actual calls or historical regrading.
"""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import budget_v5 as budget,research_negative as negative
from cp_runtime.routing_contract import ref
from cp_runtime.context_tool_surface import verify_trial_surface
import test_notify_wire as wire
import test_notify_delivery as fixture
class ResearchNegativeTests(unittest.TestCase):
    def setUp(self):self.f=wire.WireIntegration(methodName='runTest');self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def test_boundary_violation_and_bad_or_absent_final_remains_negative(self):
        rid,grant,gp,events,response,program,post=self.f.delivered();extra={'type':'response_item','payload':{'type':'function_call','name':'send_message','call_id':'extra-call','arguments':'{"target":"/root","message":"forbidden"}'}}
        events.insert(len(events)-1,extra);events[-1]['payload']['content'][0]['text']='not-valid-json';self.f.f.transcript.write_bytes(fixture.encoded(events))
        from cp_runtime import routing_hook_v5 as hook
        forbidden={**self.f.f.child_data,'hook_event_name':'PreToolUse','tool_name':'send_message','tool_use_id':'extra-call','tool_input':{'target':'/root','message':'forbidden'}}
        with self.assertRaises(ValueError):hook.child_tool(self.f.path,forbidden)
        with self.assertRaises(ValueError):self.f.f.stop()
        state=budget.read_budget(self.f.path)
        with self.assertRaises(ValueError):verify_trial_surface(self.f.path,state,rid,self.f.f.transcript)
        # 中文：仅模拟新研究门禁，原账本和证据从不改写。
        # English: Only the new research gate is simulated; original journal/evidence is never rewritten.
        state['root_binding']['context_runtime']['research_contract']='desktop-research-campaign/1'
        proof=negative.boundary_proof(self.f.path,state,rid,self.f.f.transcript);self.assertFalse(proof['passed']);self.assertTrue(proof['boundary_failure']);self.assertFalse(proof['positive_attestation'])
        original=self.f.f.transcript.read_bytes()
        with self.f.f.transcript.open('ab') as stream:stream.write((json.dumps({'type':'event_msg','payload':{'type':'task_complete'}})+'\n'+json.dumps(events[-1])+'\n').encode('utf8'))
        self.assertEqual(proof,negative.boundary_proof(self.f.path,state,rid,self.f.f.transcript,prefix_bytes=proof['prefix_bytes']))
        self.f.f.transcript.write_bytes(original.replace(b'not-valid-json',b'new-valid-json'))
        changed=negative.boundary_proof(self.f.path,state,rid,self.f.f.transcript,prefix_bytes=proof['prefix_bytes']);self.assertNotEqual(ref(proof),ref(changed))
        self.f.f.transcript.write_bytes(original)
        events.pop();self.f.f.transcript.write_bytes(fixture.encoded(events));proof=negative.boundary_proof(self.f.path,state,rid,self.f.f.transcript);self.assertIsNone(proof['native_final']);self.assertFalse(proof['positive_attestation'])
        missing=copy.deepcopy(events);del missing[4];self.f.f.transcript.write_bytes(fixture.encoded(missing))
        with self.assertRaises(ValueError):negative.boundary_proof(self.f.path,state,rid,self.f.f.transcript)
    def test_negative_grade_and_trace_consume_closed_v5_journal(self):
        """中文：在合成账本上集成消费者，原生准入另行验证。
        
        English: Consumer integration on a synthetic journal; native admission is separate.
        """
        from unittest.mock import patch
        from cp_runtime import review_v5 as review,routing_evaluation_v5 as evaluation
        from cp_runtime.common import canonical_json,atomic_write_bytes
        rid,grant,gp,events,response,program,post=self.f.delivered()
        events.insert(len(events)-1,{'type':'response_item','payload':{'type':'function_call','name':'send_message','call_id':'extra-call','arguments':'{}'}})
        events.pop()
        self.f.f.transcript.write_bytes(fixture.encoded(events))
        from cp_runtime import routing_hook_v5 as hook
        forbidden={**self.f.f.child_data,'hook_event_name':'PreToolUse','tool_name':'send_message','tool_use_id':'extra-call','tool_input':{}}
        with self.assertRaises(ValueError):hook.child_tool(self.f.path,forbidden)
        with self.assertRaises(ValueError):self.f.f.stop()
        review.record_failure_accounting(self.f.f.review_dir,self.f.f.pid,evidence_ref=ref('negative-fixture'))
        review.close(self.f.f.review_dir,conclusion='PARTIAL')
        budget.close(self.f.path,outcome='PARTIAL',evidence_ref=ref('closed-negative-fixture'))
        original=budget._read_events(self.f.path);rebased=[]
        for old in original:
            data=copy.deepcopy(old['data'])
            if old['event_type']=='INITIALIZED':data['root_binding']['context_runtime']['research_contract']='desktop-research-campaign/1'
            state=budget.replay(rebased) if rebased else None
            rebased.append(budget._event(state,old['identity'],old['event_type'],data))
            budget.replay(rebased)
        atomic_write_bytes(self.f.path,(''.join(canonical_json(e)+'\n' for e in rebased)).encode())
        state=budget.read_budget(self.f.path)
        permit=state['permits'][state['reservations'][rid]['permit_id']]
        from cp_runtime.routing_context_v4 import read_evaluation
        plan=read_evaluation(state,case_ref=permit['request']['evaluation_case_ref'])
        case=next(c for c in plan['cases'] if c['case_ref']==permit['request']['evaluation_case_ref'])
        def material(*args,**kwargs):return plan,case,permit,None
        with patch.object(negative,'_material',side_effect=material):
            result=negative.record_negative(self.f.path,reservation_id=rid,response_path=None,gold_path=None,rubric_path=None,transcript_path=self.f.f.transcript,repetition=1,cwd=str(self.f.f.f.repo))
            source={'ledger':str(self.f.path),'result':result['result_path'],'response':'','gold':'','rubric':'','transcript':str(self.f.f.transcript)}
            sample,trace,_=evaluation.read_trial(source)
        self.assertFalse(sample['passed']);self.assertTrue(sample['boundary_failure'])
        self.assertEqual('desktop-evaluation-trace/5',trace['schema_version'])
        self.assertTrue(trace['negative_verified'])
if __name__=='__main__':unittest.main()
