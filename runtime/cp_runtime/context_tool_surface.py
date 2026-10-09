"""中文：核对真实使用的工具面；English: observed provenance, not OS isolation.

Hosted tools do not share the local PreToolUse path. Reject their use from a
bounded review's evidence even when no local hook saw the call. This cannot
undo a tool side effect and must never be advertised as a universal sandbox.
"""
from __future__ import annotations
from .notify_delivery import binding_for as notify_binding

import json
import hashlib
import re
from pathlib import Path, PureWindowsPath

from .common import canonical_json
from .context_final_v2 import MAX_TRANSCRIPT_BYTES, extract_final, read_bound_transcript
from .desktop_context_call import reader_call
from .routing_context_contract import MODE_V2, context_limits, load_bundle
from .routing_contract import _object, _constant, fail, identifier, ref


def inspect_command_output(raw: bytes, *, call_id: str, child_id: str, command: str,
                           repo_path: str, expected: str, response, first_ms: int,
                           max_elapsed_ms: int = 5000) -> dict:
    """中文：Hook 预览被截断时，验证观察到的 Desktop 命令事件。这只证明内部命令输出；最终代码模式输出仍需由 inspect_tools 核验精确程序和完整可见字节。
    
    English: Verify the observed Desktop command event when its hook preview is clipped.
    
    This proves the inner command output only. The final code-mode output still
    needs inspect_tools, including its exact program and full visible bytes.
    """
    from .path_identity import path_aliases
    from .context_recovery_v2 import MAX_ELAPSED_MS, RESEARCH_MAX_ELAPSED_MS
    identifier(call_id);identifier(child_id)
    if max_elapsed_ms not in {MAX_ELAPSED_MS, RESEARCH_MAX_ELAPSED_MS}:
        fail('CONTEXT_V2_COMMAND_DEADLINE_CONTRACT')
    preview=response
    if isinstance(response,dict):
        if type(response.get('exit_code')) is not int or response['exit_code']!=0:
            fail('CONTEXT_V2_COMMAND_RESPONSE')
        preview=response.get('output')
    if not isinstance(preview,str) or not re.match(
            r'^Warning: truncated output \(original token count: [1-9][0-9]*\)\nTotal output lines: [1-9][0-9]*\n\n',preview):
        fail('CONTEXT_V2_COMMAND_PREVIEW')
    if not raw or len(raw)>MAX_TRANSCRIPT_BYTES or not raw.endswith(b'\n'):
        fail('CONTEXT_V2_COMMAND_TRANSCRIPT')
    lines=raw.splitlines()
    if len(lines)>4096 or any(len(line)>2*1024*1024 for line in lines):
        fail('CONTEXT_V2_COMMAND_TRANSCRIPT')
    try:
        events=[json.loads(line,object_pairs_hook=_object,parse_constant=_constant) for line in lines]
        turns=[(i,e['payload']) for i,e in enumerate(events) if e.get('type')=='event_msg'
               and e.get('payload',{}).get('type')=='task_started']
        matches=[(i,e['payload']) for i,e in enumerate(events) if e.get('type')=='event_msg'
                 and e.get('payload',{}).get('type')=='item_completed'
                 and e['payload'].get('item',{}).get('type')=='CommandExecution'
                 and e['payload']['item'].get('id')==call_id]
        if len(turns)!=1 or len(matches)!=1 or turns[0][0]>=matches[0][0]:
            fail('CONTEXT_V2_COMMAND_EVENT_AMBIGUOUS')
        event=matches[0][1];item=event['item'];argv=item.get('command')
        locations={spelling for path in path_aliases(Path(repo_path))
                   for spelling in (str(path),path.as_posix(),path.as_uri())}
        if event.get('thread_id')!=child_id or event.get('turn_id')!=turns[0][1].get('turn_id') \
                or item.get('source')!='unified_exec_startup' or item.get('status')!='completed' \
                or type(item.get('exit_code')) is not int or item['exit_code']!=0 \
                or item.get('cwd') not in locations \
                or not isinstance(argv,list) or len(argv)!=3 or any(not isinstance(a,str) for a in argv) \
                or not PureWindowsPath(argv[0]).is_absolute() \
                or PureWindowsPath(argv[0]).name.lower() not in {'pwsh.exe','powershell.exe'} \
                or argv[1:]!=['-Command',command]:
            fail('CONTEXT_V2_COMMAND_BINDING')
        started,completed=event.get('started_at_ms'),event.get('completed_at_ms')
        if any(type(v) is not int or not 0<=v<=2**53-1 for v in (first_ms,started,completed)) \
                or not first_ms<=started<=completed<=first_ms+max_elapsed_ms:
            fail('CONTEXT_V2_COMMAND_TIME')
        if item.get('stdout')!=expected or item.get('aggregated_output')!=expected \
                or item.get('stderr')!='' or item.get('formatted_output')!=preview:
            fail('CONTEXT_V2_COMMAND_OUTPUT')
        return {'schema_version':'desktop-command-output-proof/1','call_ref':ref(call_id),
                'completion_ref':ref(event),'turn_ref':ref(event['turn_id']),
                'output_ref':'sha256:'+hashlib.sha256(expected.encode('utf8')).hexdigest()}
    except (KeyError,TypeError,AttributeError,UnicodeError,json.JSONDecodeError) as exc:
        raise ValueError('CONTEXT_V2_COMMAND_SHAPE') from exc


def verify_command_output(state, data, reservation_id: str, *, command: str, expected: str) -> dict:
    """中文：使用宿主原始提供的路径，以及子任务启动时绑定的文件节点身份。
    
    English: Use the original host-supplied path and the inode linked at child start.
    """
    from .routing_hook_v5 import _transcript_path, _header_from_bytes
    raw,binding=read_bound_transcript(_transcript_path(data))
    linked=_header_from_bytes(data,state,raw.splitlines()[0],binding)
    if ref(linked)!=state['host_identity_links'][reservation_id]['proof_ref']:
        fail('CONTEXT_V2_COMMAND_FILE_BINDING')
    from .context_recovery_v2 import deadline_for_runtime
    return inspect_command_output(raw,call_id=data['tool_use_id'],child_id=data['agent_id'],
        command=command,repo_path=state['root_binding']['repo_path'],expected=expected,
        response=data.get('tool_response'),first_ms=state['context_recovery'][reservation_id]['first_ms'],
        max_elapsed_ms=deadline_for_runtime(state['root_binding']['context_runtime']))


def reader_program(ledger_path, state, request, session_id, child_id) -> str:
    from .routing_hook_v5 import _grant_path
    runtime=state['root_binding']['context_runtime']
    if runtime['transport_mode'] != MODE_V2:
        fail('CONTEXT_TOOLS_V2_REQUIRED')
    sample=canonical_json({'schema_version':'context-reader-output/1','context_receipt':'0'*64,
                           'context':load_bundle(request,runtime)})+'\n'
    _,limit,tokens=context_limits(runtime)
    from . import notify_wire
    wire=notify_wire.enabled(state)
    if wire:sample=notify_wire.pack(sample,notify_binding(request));limit=notify_wire.MAX_WIRE
    base=reader_call(python_path=runtime['python_path'],reader_path=runtime['reader_path'],
        grant_path=str(_grant_path(ledger_path,session_id,child_id)),recovery=True,
        expected_output_chars=len(sample.encode('utf-16-le'))//2,output_limit=limit,output_tokens=tokens,delivery_contract=notify_wire.CONTRACT if wire else None)['javascript']
    from .notify_delivery import enabled,reader_program as notify_program,binding_for
    return notify_wire.reader_program(base) if wire else notify_program(base,binding_for(request)) if enabled(state) else base


def inspect_tools(raw: bytes, expected_program: str, *, expected_delivery_ref: str | None = None) -> dict:
    if not raw or len(raw)>MAX_TRANSCRIPT_BYTES or not raw.endswith(b'\n'):
        fail('CONTEXT_TOOLS_TRANSCRIPT_BOUND')
    lines=raw.splitlines()
    if len(lines)>4096 or any(len(line)>2*1024*1024 for line in lines):
        fail('CONTEXT_TOOLS_TRANSCRIPT_BOUND')
    calls,outputs,starts,finals=[],[],[],[]
    try:
        for index,line in enumerate(lines):
            event=json.loads(line,object_pairs_hook=_object,parse_constant=_constant)
            payload=event.get('payload',{})
            if event.get('type')=='event_msg' and payload.get('type')=='task_started':
                starts.append(index)
            if event.get('type')!='response_item':
                continue
            kind=payload.get('type')
            if kind=='message' and payload.get('role')=='assistant' and payload.get('phase')=='final_answer':
                finals.append(index)
            if kind=='custom_tool_call':
                program=payload.get('input')
                # 中文：Desktop 可追加末尾换行；只忽略外层 ASCII 空白，每个词元、字符串和操作仍须精确一致。
                # English: Desktop may append a final newline. Only outer ASCII spacing
                # is ignored; every token/string/operation remains exact.
                if payload.get('name')!='exec' or not isinstance(program,str) \
                        or program.strip(' \t\r\n')!=expected_program.strip(' \t\r\n'):
                    fail('CONTEXT_TOOLS_UNAPPROVED_PROGRAM')
                calls.append((index,identifier(payload.get('call_id')),ref(program)))
            elif kind=='custom_tool_call_output':
                outputs.append((index,identifier(payload.get('call_id')),ref(payload),payload.get('output')))
            elif kind not in {'message','agent_message','reasoning'}:
                fail('CONTEXT_TOOLS_UNAPPROVED_SURFACE')
        if len(calls)!=1 or len(outputs)!=1 or len(starts)!=1 or len(finals)!=1 \
                or calls[0][1]!=outputs[0][1] or not starts[0]<calls[0][0]<outputs[0][0]<finals[0]:
            fail('CONTEXT_TOOLS_CALL_SET_INCOMPLETE')
        if expected_delivery_ref is not None:
            blocks=outputs[0][3]
            if not isinstance(blocks,list) or len(blocks)!=2 \
                    or any(not isinstance(b,dict) or set(b)!={'type','text'} or b['type']!='input_text'
                           or not isinstance(b['text'],str) for b in blocks) \
                    or not re.fullmatch(r'Script completed\nWall time [0-9.]+ seconds\nOutput:\n',blocks[0]['text']):
                fail('CONTEXT_TOOLS_VISIBLE_OUTPUT_SHAPE')
            visible=json.loads(blocks[1]['text'],object_pairs_hook=_object,parse_constant=_constant)
            if not isinstance(visible,dict) or type(visible.get('exit_code')) is not int \
                    or visible['exit_code']!=0 or not isinstance(visible.get('output'),str) \
                    or 'sha256:'+hashlib.sha256(visible['output'].encode('utf8')).hexdigest()!=expected_delivery_ref:
                fail('CONTEXT_TOOLS_VISIBLE_DELIVERY_MISMATCH')
        return {'schema_version':'desktop-tool-surface/1','program_ref':ref(expected_program),
                'observed_program_ref':calls[0][2],
                'call_ref':ref(calls[0][1]),'output_ref':outputs[0][2],'code_mode_calls':1,
                'visible_delivery_ref':expected_delivery_ref or '',
                'coverage':'observed-bounded-reader','isolation_claim':'logical-readonly'}
    except (KeyError,TypeError,AttributeError,UnicodeError,json.JSONDecodeError) as exc:
        raise ValueError('CONTEXT_TOOLS_TRANSCRIPT_SHAPE') from exc


def verify_trial_surface(ledger_path: Path, state, reservation_id: str, transcript: Path) -> dict:
    """中文：一并重读原文件身份、最终回答和实际工具使用记录。
    
    English: Re-read original file identity, final answer and actual tool use together.
    """
    from . import budget_v5 as budget
    from .routing_hook_v5 import _header_from_bytes
    raw,binding=read_bound_transcript(transcript)
    try:
        first=raw.splitlines()[0]
        header=json.loads(first,object_pairs_hook=_object,parse_constant=_constant)
        meta=header['payload'];spawn=meta['source']['subagent']['thread_spawn']
        child=identifier(meta['id']);session=identifier(spawn['parent_thread_id'])
        permit=state['permits'][state['reservations'][reservation_id]['permit_id']]
        if ref(child)!=budget.effective_agent_ref(state,reservation_id) \
                or ref(session)!=state['root_binding']['host_session_ref'] \
                or ref(spawn['agent_path'].rsplit('/',1)[-1])!=permit['dispatch_ref']:
            fail('CONTEXT_TOOLS_NATIVE_IDENTITY')
        linked=_header_from_bytes({'session_id':session,'agent_id':child,'agent_type':permit['role']},
                                   state,first,binding)
        final=state.get('context_raw_finals',{}).get(reservation_id) or state['context_finals'].get(reservation_id,{})
        if ref(linked)!=state['host_identity_links'][reservation_id]['proof_ref'] \
                or ref(linked)!=final.get('header_link_ref'):
            fail('CONTEXT_TOOLS_NATIVE_FILE_BINDING')
        _,proof=extract_final(raw,child_id=child,root_id=session,task_path=spawn['agent_path'],
                              role=permit['role'],repo_path=state['root_binding']['repo_path'])
        if any(final.get(key)!=value for key,value in proof.items()):
            fail('CONTEXT_TOOLS_NATIVE_FINAL_CHANGED')
        from .notify_delivery import enabled,inspect_raw,binding_for
        if enabled(state):
            from . import notify_wire
            if notify_wire.enabled(state):
                from .routing_hook_v5 import _grant_path
                proof=notify_wire.inspect_delivery(raw,reader_program(ledger_path,state,permit['request'],session,child),permit['request'],state,reservation_id,_grant_path(ledger_path,session,child))
            else:proof=inspect_raw(raw,reader_program(ledger_path,state,permit['request'],session,child),binding_for(permit['request']),state['context_deliveries'][reservation_id]['output_ref'])
            recorded=state.get('context_notify_finals',{}).get(reservation_id)
            if not recorded or recorded['visible_proof']!=proof or recorded['response_ref']!=final['response_ref']:fail('NOTIFY_ATTESTATION_CHANGED')
            return proof
        return inspect_tools(raw,reader_program(ledger_path,state,permit['request'],session,child),
                             expected_delivery_ref=state['context_deliveries'][reservation_id]['output_ref'])
    except (KeyError,TypeError,AttributeError,IndexError) as exc:
        raise ValueError('CONTEXT_TOOLS_NATIVE_SHAPE') from exc
