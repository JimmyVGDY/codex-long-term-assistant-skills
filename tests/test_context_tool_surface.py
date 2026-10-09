"""中文：验证宿主与本地工具来源，不宣称通用安全沙箱保证。

English: Hosted/local tool provenance tests, not a universal security-sandbox claim.
"""
import copy
import json
import hashlib
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime.context_tool_surface import inspect_tools, inspect_command_output
from cp_runtime.routing_contract import RoutingError


class ToolSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.program='exact controller program'
        self.events=[
            {'type':'session_meta','payload':{}},
            {'type':'event_msg','payload':{'type':'task_started','turn_id':'turn-one'}},
            {'type':'response_item','payload':{'type':'custom_tool_call','name':'exec','call_id':'code-one','input':self.program}},
            {'type':'response_item','payload':{'type':'custom_tool_call_output','call_id':'code-one','output':'reader result'}},
            {'type':'response_item','payload':{'type':'message','role':'assistant','phase':'final_answer','content':[]}}]

    def inspect(self,events=None):
        raw=('\n'.join(json.dumps(e) for e in (events or self.events))+'\n').encode()
        return inspect_tools(raw,self.program)

    def test_one_controller_program_and_paired_output_are_observed_only(self):
        result=self.inspect()
        self.assertEqual(1,result['code_mode_calls'])
        self.assertEqual('logical-readonly',result['isolation_claim'])
        self.assertEqual('observed-bounded-reader',result['coverage'])

    def test_hosted_tools_and_unknown_native_tool_types_reject(self):
        for kind in ('web_search_call','function_call','computer_call','image_generation_call','unknown_future_tool'):
            events=copy.deepcopy(self.events)
            events.insert(3,{'type':'response_item','payload':{'type':kind}})
            with self.subTest(kind=kind),self.assertRaisesRegex(RoutingError,'UNAPPROVED_SURFACE'):
                self.inspect(events)

    def test_code_mode_cannot_append_hidden_mcp_or_shell_work(self):
        events=copy.deepcopy(self.events)
        events[2]['payload']['input']+='\nawait tools.other_tool({});'
        with self.assertRaisesRegex(RoutingError,'UNAPPROVED_PROGRAM'):self.inspect(events)
        events=copy.deepcopy(self.events)
        events[2]['payload']['name']='another_namespace_exec'
        with self.assertRaisesRegex(RoutingError,'UNAPPROVED_PROGRAM'):self.inspect(events)

    def test_repeated_program_missing_response_and_out_of_order_are_rejected(self):
        variants=[self.events[:3]+self.events[4:],self.events[:4]+[self.events[2]]+self.events[4:]]
        changed=copy.deepcopy(self.events);changed[3]['payload']['call_id']='foreign';variants.append(changed)
        changed=copy.deepcopy(self.events);changed[2],changed[3]=changed[3],changed[2];variants.append(changed)
        for events in variants:
            with self.assertRaisesRegex(RoutingError,'CALL_SET_INCOMPLETE'):self.inspect(events)

    def test_normal_appended_usage_is_not_an_extra_tool(self):
        self.events.append({'type':'token_usage_record','payload':{'usage':{}}})
        self.assertEqual(1,self.inspect()['code_mode_calls'])

    def test_outer_newline_is_accepted_without_normalizing_program_tokens(self):
        self.events[2]['payload']['input']=' \n'+self.program+'\r\n'
        self.assertEqual(1,self.inspect()['code_mode_calls'])
        self.events[2]['payload']['input']=self.program.replace('controller','controller  ')
        with self.assertRaisesRegex(RoutingError,'UNAPPROVED_PROGRAM'):self.inspect()

    def test_outer_code_mode_truncation_cannot_hide_behind_inner_delivery(self):
        delivered='{"context":"complete material"}\n'
        expected='sha256:'+hashlib.sha256(delivered.encode()).hexdigest()
        blocks=[{'type':'input_text','text':'Script completed\nWall time 0.1 seconds\nOutput:\n'},
                {'type':'input_text','text':json.dumps({'exit_code':0,'output':delivered})}]
        self.events[3]['payload']['output']=blocks
        def verify():
            raw=('\n'.join(json.dumps(e) for e in self.events)+'\n').encode()
            return inspect_tools(raw,self.program,expected_delivery_ref=expected)
        self.assertEqual(expected,verify()['visible_delivery_ref'])
        blocks[1]['text']=json.dumps({'exit_code':0,'output':delivered[:-5]})
        with self.assertRaisesRegex(RoutingError,'VISIBLE_DELIVERY_MISMATCH'):verify()
        blocks[0]['text']='Script completed; output truncated'
        with self.assertRaisesRegex(RoutingError,'VISIBLE_OUTPUT_SHAPE'):verify()


class CommandOutputProofTests(unittest.TestCase):
    def setUp(self):
        self.command="& 'C:/runtime/python.exe' -I -B 'C:/runtime/reader.py' 'C:/state/grant.json'"
        self.repo=str(ROOT)
        self.output='{"context":"'+('complete material '*2400)+'"}\n'
        self.preview='Warning: truncated output (original token count: 10330)\nTotal output lines: 1\n\n'+self.output[:50]+'...'
        self.event={'type':'event_msg','payload':{'type':'item_completed','thread_id':'child-one',
            'turn_id':'turn-one','started_at_ms':1001,'completed_at_ms':1010,'item':{
                'type':'CommandExecution','id':'exec-one','source':'unified_exec_startup',
                'status':'completed','exit_code':0,'cwd':self.repo,
                'command':['C:/runtime/pwsh.exe','-Command',self.command],
                'stdout':self.output,'aggregated_output':self.output,'stderr':'','formatted_output':self.preview}}}
        self.events=[{'type':'session_meta','payload':{}},
            {'type':'event_msg','payload':{'type':'task_started','turn_id':'turn-one'}},self.event]

    def inspect(self,events=None,response=None,max_elapsed_ms=5000):
        raw=('\n'.join(json.dumps(e) for e in (events or self.events))+'\n').encode()
        return inspect_command_output(raw,call_id='exec-one',child_id='child-one',command=self.command,
            repo_path=self.repo,expected=self.output,response=self.preview if response is None else response,
            first_ms=1000,max_elapsed_ms=max_elapsed_ms)

    def test_full_native_bytes_can_verify_a_clipped_hook_preview(self):
        result=self.inspect()
        self.assertEqual('sha256:'+hashlib.sha256(self.output.encode()).hexdigest(),result['output_ref'])
        self.assertEqual(result,self.inspect(response={'exit_code':0,'output':self.preview}))
        self.event['payload']['item']['cwd']=ROOT.resolve().as_uri()
        self.assertEqual(result['output_ref'],self.inspect()['output_ref'])
        self.event['payload']['completed_at_ms']=7047
        with self.assertRaisesRegex(RoutingError,'COMMAND_TIME'):self.inspect()
        self.assertEqual(result['output_ref'],self.inspect(max_elapsed_ms=15000)['output_ref'])

    def test_wrong_call_turn_child_directory_and_command_are_rejected(self):
        mutations=[('payload','thread_id','foreign'),('payload','turn_id','foreign'),
                   ('item','id','exec-foreign'),('item','cwd',str(ROOT.parent)),
                   ('item','source','another-host-path'),('item','exit_code',1),
                   ('item','command',['C:/runtime/pwsh.exe','-Command',self.command+'; another-command'])]
        for target,key,value in mutations:
            events=copy.deepcopy(self.events)
            place=events[-1]['payload'] if target=='payload' else events[-1]['payload']['item']
            place[key]=value
            with self.subTest(key=key),self.assertRaises(RoutingError):self.inspect(events)

    def test_output_preview_and_time_cannot_be_substituted(self):
        for field in ('stdout','aggregated_output','stderr','formatted_output'):
            events=copy.deepcopy(self.events)
            events[-1]['payload']['item'][field]+='changed'
            with self.subTest(field=field),self.assertRaisesRegex(RoutingError,'COMMAND_OUTPUT'):
                self.inspect(events)
        self.event['payload']['completed_at_ms']=6001
        with self.assertRaisesRegex(RoutingError,'COMMAND_TIME'):self.inspect()
        self.event['payload']['completed_at_ms']=16001
        with self.assertRaisesRegex(RoutingError,'COMMAND_TIME'):self.inspect(max_elapsed_ms=15000)

    def test_duplicates_and_unknown_preview_shapes_fail_closed(self):
        with self.assertRaisesRegex(RoutingError,'EVENT_AMBIGUOUS'):
            self.inspect(self.events+[copy.deepcopy(self.event)])
        with self.assertRaisesRegex(RoutingError,'COMMAND_PREVIEW'):
            self.inspect(response='a different truncation message')
        with self.assertRaisesRegex(RoutingError,'COMMAND_RESPONSE'):
            self.inspect(response={'exit_code':False,'output':self.preview})

    def test_inner_proof_does_not_authorize_truncated_model_visible_output(self):
        proof=self.inspect()
        events=[self.events[0],self.events[1],
            {'type':'response_item','payload':{'type':'custom_tool_call','name':'exec','call_id':'code-one','input':'program'}},
            self.event,
            {'type':'response_item','payload':{'type':'custom_tool_call_output','call_id':'code-one','output':[
                {'type':'input_text','text':'Script completed\nWall time 0.1 seconds\nOutput:\n'},
                {'type':'input_text','text':json.dumps({'exit_code':0,'output':self.preview})}]}},
            {'type':'response_item','payload':{'type':'message','role':'assistant','phase':'final_answer','content':[]}}]
        raw=('\n'.join(json.dumps(e) for e in events)+'\n').encode()
        with self.assertRaisesRegex(RoutingError,'VISIBLE_DELIVERY_MISMATCH'):
            inspect_tools(raw,'program',expected_delivery_ref=proof['output_ref'])


if __name__=='__main__':unittest.main()
