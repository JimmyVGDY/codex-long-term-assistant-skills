"""中文：综合通知传输的合成验证，不涉及原生模型或资格。

English: Synthetic integrated notify transport; no native models or qualification.
"""
import copy,json,sys,unittest,subprocess,tempfile,shutil
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import notify_delivery as notify,budget_v5 as budget,review_v5 as review
from cp_runtime import routing_hook_v5 as hook
from cp_runtime.routing_context_contract import runtime,create_bundle,MODE_V2,CONTEXT_64K,validate_runtime
from cp_runtime.context_tool_surface import reader_program,verify_trial_surface
from cp_runtime.routing_contract import ref
import test_routing_v5_context as fx
import test_routing_context_transport_v2 as tx
import v4_fixtures as vf

def trace(raw,binding,program,header=None):
    parts,summary=notify.construct(raw,binding);head=header or {'type':'session_meta','payload':{}}
    events=[head,{'type':'event_msg','payload':{'type':'task_started','turn_id':'turn-1'}},
      {'type':'response_item','payload':{'type':'custom_tool_call','name':'exec','call_id':'notify-cell','input':program}},
      {'type':'response_item','payload':{'type':'custom_tool_call_output','call_id':'notify-cell','output':[{'type':'input_text','text':'Script completed\nWall time 0.1 seconds\nOutput:\n'},{'type':'input_text','text':notify.canonical(summary)}]},'metadata':{'fallback_token_limit_override':12000}}]
    for part in parts+[notify.completion(summary)]:events.append({'type':'response_item','payload':{'type':'custom_tool_call_output','name':'exec','call_id':'notify-cell','output':notify.canonical(part)},'metadata':{'fallback_token_limit_override':12000}})
    final={'status':'pass','findings':[],'checked_scope':['fixture source'],'unverified_items':[],'summary':'synthetic review','context_receipt':notify.completion(summary)['context_receipt']}
    events.append({'type':'response_item','payload':{'type':'message','role':'assistant','phase':'final_answer','content':[{'type':'output_text','text':notify.canonical(final)}]}})
    return events,final
def encoded(events):return ('\n'.join(json.dumps(e,ensure_ascii=False) for e in events)+'\n').encode('utf8')

class NotifyPureTests(unittest.TestCase):
    def setUp(self):
        self.raw=notify.canonical({'schema_version':'context-reader-output/1','context_receipt':'0'*64,'context':{'business_prompt':'汉😀\\\"\n'*2000}})+'\n'
        self.binding={'bundle_ref':ref('bundle'),'packet_sha256':'1'*64,'baseline_sha256':'2'*64};self.program='approved-program'
        self.events,self.final=trace(self.raw,self.binding,self.program)
    def test_full_utf8_set_summary_first_receipt_and_budgets(self):
        p=notify.inspect_raw(encoded(self.events),self.program,self.binding,'sha256:'+notify.sha(self.raw));notify.validate_proof(p)
        self.assertEqual('desktop-tool-surface/2',p['schema_version']);self.assertTrue(all(b<28000 for b in p['payload_bytes']))
    def test_missing_duplicate_reorder_early_or_bad_metadata_denied(self):
        for case in ('missing','duplicate','reorder','completion_early','final_early','metadata_missing','small_budget','wrong_receipt','wrong_call','extra_tool','program'):
            e=copy.deepcopy(self.events)
            if case=='missing':del e[4]
            elif case=='duplicate':e.insert(4,copy.deepcopy(e[4]))
            elif case=='reorder':e[4],e[5]=e[5],e[4]
            elif case=='completion_early':e.insert(4,e.pop(-2))
            elif case=='final_early':e.insert(4,e.pop(-1))
            elif case=='metadata_missing':e[4].pop('metadata')
            elif case=='small_budget':e[4]['metadata']['fallback_token_limit_override']=1
            elif case=='wrong_receipt':e[-1]['payload']['content'][0]['text']=notify.canonical({**self.final,'context_receipt':'f'*64})
            elif case=='wrong_call':e[4]['payload']['call_id']='foreign'
            elif case=='extra_tool':e.insert(4,{'type':'response_item','payload':{'type':'function_call','name':'other'}})
            else:e[2]['payload']['input']+=' extra'
            with self.subTest(case=case),self.assertRaises((ValueError,KeyError,TypeError)):notify.inspect_raw(encoded(e),self.program,self.binding,'sha256:'+notify.sha(self.raw))
    def test_raw_reference_change_denied(self):
        with self.assertRaisesRegex(ValueError,'RAW_DELIVERY_MISMATCH'):notify.inspect_raw(encoded(self.events),self.program,self.binding,ref('different'))
    def test_notify_semantics_require_receipt_only_when_opted_in(self):
        from cp_runtime.review_vector_transport import decode
        state={'root_binding':{'context_runtime':{'delivery_contract':notify.CONTRACT}}}
        self.assertNotIn('context_receipt',decode(state,{},self.final))
        with self.assertRaisesRegex(ValueError,'MODEL_FIELDS'):decode(state,{}, {k:v for k,v in self.final.items() if k!='context_receipt'})
        with self.assertRaisesRegex(ValueError,'SEMANTIC_FIELDS'):decode({'root_binding':{'context_runtime':{}}},{},self.final)
    def test_import_has_no_workflow_or_filesystem_side_effect(self):
        import importlib
        with patch('pathlib.Path.mkdir',side_effect=AssertionError('no mkdir')):importlib.reload(notify)
    def test_actual_fixed_reader_program_notify_construction_in_node_shim(self):
        node=shutil.which('node')
        if node is None:self.skipTest('Node.js is unavailable for the fixed JavaScript program integration')
        from cp_runtime.desktop_context_call import reader_call
        base=reader_call(python_path=str(Path(sys.executable)),reader_path=str(ROOT/'hooks/review_context_reader.py'),grant_path=str(ROOT/'tests'/'fixture-grant.json'),recovery=True,expected_output_chars=len(self.raw.encode('utf-16-le'))//2,output_limit=65536,output_tokens=50000)['javascript']
        code=notify.reader_program(base,self.binding)
        shim='let calls=0;const notifications=[];let summary;global.tools={exec_command:async()=>{calls++;return {exit_code:0,output:'+json.dumps(self.raw)+'};}};global.notify=v=>notifications.push(v);global.text=v=>{summary=v;};(async()=>{'+code+';process.stdout.write(JSON.stringify({calls,notifications,summary}));})();'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'shim.cjs';path.write_text(shim,encoding='utf8')
            result=subprocess.run([node,str(path)],capture_output=True,text=True,encoding='utf8',timeout=10,check=True)
        observed=json.loads(result.stdout);parts,summary=notify.construct(self.raw,self.binding)
        self.assertEqual(1,observed['calls']);self.assertEqual([notify.canonical(p) for p in parts]+[notify.canonical(notify.completion(summary))],observed['notifications']);self.assertEqual(summary,observed['summary'])

class NotifyIntegratedTests(unittest.TestCase):
    def setUp(self):
        self.f=fx.ContextV5Tests(methodName='runTest')
        def rt(reader,python):
            value=runtime(reader,python,transport_mode=MODE_V2,context_profile=CONTEXT_64K);value['delivery_contract']=notify.CONTRACT;return value
        def bundle(*a,**k):return create_bundle(*a,**{**k,'context_profile':CONTEXT_64K})
        with patch.object(fx,'runtime',rt),patch.object(fx,'create_bundle',bundle),patch.dict(vf.SCENARIO,{'context_bucket':'bounded-review-64k','tools_profile':'desktop-context-reader-64k-v1'}):self.f.setUp()
        self.path=self.f.path
    def tearDown(self):self.f.tearDown()
    def delivered(self):
        self.f.reserve();self.f.start();self.f.receipt()
        helper=tx.TransportV2Tests(methodName='runTest');helper.f=self.f;helper.path=self.path
        text,_=helper.read();state=budget.read_budget(self.path);rid=next(iter(state['reservations']))
        request=state['permits'][self.f.pid]['request'];program=reader_program(self.path,state,request,'desktop-session',self.f.child)
        events,final=trace(text,notify.binding_for(request),program,self.f.header)
        self.f.transcript.write_bytes(encoded(events));response=self.f.f.root/'notify-final.json';response.write_text(notify.canonical(final),encoding='utf8')
        return rid,events,response
    def test_full_actual_temporary_journal_final_result_and_downstream_surface(self):
        rid,events,response=self.delivered();self.f.stop();state=budget.read_budget(self.path)
        self.assertIn(rid,state['context_notify_finals']);self.assertEqual('pass',state['context_finals'][rid]['semantic_status'])
        review.record_semantic(self.f.review_dir,self.f.pid,response)
        proof=verify_trial_surface(self.path,budget.read_budget(self.path),rid,self.f.transcript)
        self.assertEqual('desktop-tool-surface/2',proof['schema_version'])
    def test_missing_notification_cannot_attest_semantics_or_pass_review(self):
        rid,events,response=self.delivered();del events[4];self.f.transcript.write_bytes(encoded(events))
        with self.assertRaises(ValueError):self.f.stop()
        state=budget.read_budget(self.path);self.assertIn(rid,state['context_raw_finals']);self.assertNotIn(rid,state.get('context_notify_finals',{}));self.assertNotIn(rid,state['context_finals'])
        with self.assertRaises(ValueError):review.record_semantic(self.f.review_dir,self.f.pid,response)
        review.record_failure_accounting(self.f.review_dir,self.f.pid,evidence_ref=ref('missing-notify'));review.close(self.f.review_dir,conclusion='PARTIAL')
    def test_notify_event_rejected_without_optin(self):
        state=budget.read_budget(self.path);state['root_binding']['context_runtime'].pop('delivery_contract')
        with self.assertRaisesRegex(ValueError,'OPT_IN_REQUIRED'):budget._apply(state,{'event_type':'CONTEXT_NOTIFY_ATTESTED','data':{}})
    def test_notify_runtime_requires_exact_v2_large_profile(self):
        state=budget.read_budget(self.path);runtime_value=state['root_binding']['context_runtime'];runtime_value.pop('context_profile')
        with self.assertRaisesRegex(ValueError,'NOTIFY_DELIVERY_CONTRACT'):validate_runtime(runtime_value)

if __name__=='__main__':unittest.main()
