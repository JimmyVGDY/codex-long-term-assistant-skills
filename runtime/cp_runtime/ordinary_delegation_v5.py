"""中文：普通委派的原生完成与显式父级验证，不引入复审语义。

English: Native ordinary completion and explicit parent validation, without review semantics.
"""
from pathlib import Path
from . import budget_v5 as budget
from .common import repo_snapshot,verify_record
from .context_final_v2 import extract_final,read_bound_transcript
from .evidence import check_evidence
from .ordinary_routing_v5 import enabled
from .routing_context_v5 import verify_root
from .routing_contract import fail,read_document,ref

def attest_final(path,data):
    from .routing_hook_v5 import _bind_child,_transcript_path,_header_from_bytes
    state,rid,permit=_bind_child(path,data,require_receipt=False)
    if not enabled(state['root_binding']['context_runtime'],permit['role']):fail('ORDINARY_CONTRACT_REQUIRED')
    raw,binding=read_bound_transcript(_transcript_path(data))
    header=_header_from_bytes(data,state,raw.splitlines()[0],binding)
    if ref(header)!=state['host_identity_links'][rid]['proof_ref']:fail('ORDINARY_FINAL_FILE_BINDING')
    _,proof=extract_final(raw,child_id=data['agent_id'],root_id=data['session_id'],
        task_path=header['task_path'],role=permit['role'],repo_path=state['root_binding']['repo_path'])
    return budget.ordinary_final_attested(path,{'reservation_id':rid,'agent_ref':ref(data['agent_id']),
        'header_link_ref':ref(header),**proof})

def record_result(path: Path,*,cwd: str,host_session_id: str,reservation_id: str,
                  response_path: Path,validation_path: Path,status: str) -> dict:
    state=budget.read_budget(path)
    verify_root(state,cwd=cwd,host_session_id=host_session_id)
    attempt=state['reservations'].get(reservation_id)
    if not attempt or not enabled(state['root_binding']['context_runtime'],state['permits'][attempt['permit_id']]['role']):
        fail('ORDINARY_RESULT_ROLE')
    from .routing_evaluation_v4 import file_reference
    response_ref=file_reference(response_path)
    if state['ordinary_finals'].get(reservation_id,{}).get('response_ref')!=response_ref:
        fail('ORDINARY_RESULT_NATIVE_OUTPUT')
    if status not in {'pass','incomplete'}:fail('ORDINARY_RESULT_STATUS')
    evidence,evidence_ref=read_document(validation_path)
    verify_record(evidence,'ordinary task validation')
    checked=check_evidence(validation_path,Path(cwd),state['identity']['project_id'],state['identity']['task_id'])
    required={'ordinary-reservation:'+ref(reservation_id),'ordinary-verdict:'+status}
    if not checked.valid or evidence.get('kind')!='validation' or evidence.get('source')!='parent-ordinary-task-validation' \
            or not required.issubset(set(evidence.get('scope_refs',[]))):
        fail('ORDINARY_PARENT_VALIDATION_REQUIRED')
    permit=state['permits'][attempt['permit_id']]
    resolved={x for r in state['ordinary_results'].values() for x in r['supersedes']}
    supersedes=[r['result_ref'] for rid,r in state['ordinary_results'].items()
        if state['permits'][state['reservations'][rid]['permit_id']]['slot_id']==permit['slot_id']
        and r['status']=='incomplete' and r['result_ref'] not in resolved]
    previous=state['ordinary_results'].get(reservation_id)
    if previous:supersedes=previous['supersedes']
    value={'reservation_id':reservation_id,'response_ref':response_ref,'validation_ref':evidence_ref,
           'after_baseline_sha256':repo_snapshot(Path(cwd))['sha256'],'status':status,'supersedes':supersedes}
    value['result_ref']=ref(value)
    return budget.ordinary_result_accepted(path,value)
