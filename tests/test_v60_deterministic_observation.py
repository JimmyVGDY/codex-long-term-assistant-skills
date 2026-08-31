from __future__ import annotations
import json, os, subprocess, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime.event_v2 import EventContractError, aggregate_by_task, append_event, make_event, verify_event_chain
from cp_runtime.evolution.contracts import SelfObservationSnapshot, DecisionType, ProposalStatus
from cp_runtime.evolution.observation import observe_project, ObservationError
from cp_runtime.evolution.storage import exclusive_write_json, StorageError
from cp_runtime.evolution.service import ControlledEvolutionService
from cp_runtime.evolution.registry import ProposalRegistry

class V60DeterministicObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='cp-v60-')
        self.root=Path(self.tmp.name)
        self.project_id='project-alpha'
        self.project_dir=self.root/self.project_id; self.project_dir.mkdir(parents=True)
    def tearDown(self): self.tmp.cleanup()

    def event(self, **kw):
        base={
            'event_type':'TASK_COMPLETED','session_id':'S1','turn_id':'T1','task_id':'TASK-1',
            'project_id':self.project_id,'repo_fingerprint':'sha256:'+'a'*64,'terminal_outcome':'PASS'
        }
        base.update(kw); return make_event(base)

    def write_jsonl(self, rel, rows):
        p=self.project_dir/rel; p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8'); return p

    def test_event_v2_rejects_negative_counts_and_cross_project(self):
        with self.assertRaises(EventContractError): self.event(repair_rounds=-1)
        a=self.event(event_id='E1')
        b=dict(self.event(event_id='E2')); b['project_id']='project-beta'
        with self.assertRaises(EventContractError): aggregate_by_task([a,b],self.project_id,'sha256:'+'a'*64)

    def test_event_chain_hmac_and_dedup_aggregation(self):
        p=self.root/'events.jsonl'; key='test-key'
        a=self.event(event_id='E1',event_type='SUBAGENT_STARTED',terminal_outcome='UNKNOWN')
        b=self.event(event_id='E2',event_type='TASK_COMPLETED',terminal_outcome='FAILED',blocking_findings=1)
        append_event(p,a,key); append_event(p,b,key)
        result=verify_event_chain(p,key); self.assertEqual(2,result['record_count'])
        agg=aggregate_by_task([a,a,b],self.project_id,'sha256:'+'a'*64)
        self.assertEqual(1,agg['TASK-1']['actual_reviewers'])
        self.assertEqual('FAILED',agg['TASK-1']['terminal_outcome'])

    def test_status_plan_not_counted_as_failure_and_reviewer_detail_not_double_counted(self):
        rows=[]
        for i in range(5):
            rows.append({'record_id':f'R{i}','task_id':f'TASK-{i}','timestamp':datetime(2026,8,1,tzinfo=timezone.utc).isoformat(),
                         'status':'PLAN','reviewer_results':[{'reviewer':'r1','blocking_findings':1,'nonblocking_findings':1,
                         'findings':[{'severity':'HIGH'},{'severity':'LOW'}]}]})
        self.write_jsonl('review/review-results.jsonl',rows)
        snap=observe_project(self.project_id,self.project_dir)
        self.assertEqual(0,snap.metrics['known_outcome_count'])
        self.assertNotIn('outcome:plan',snap.metrics['failure_patterns'])
        stats=snap.metrics['reviewer_stats']['r1']
        self.assertEqual(5,stats['blocking_findings']); self.assertEqual(5,stats['nonblocking_findings'])

    def test_v2_project_and_repo_isolation(self):
        wrong=self.event(event_id='E9'); wrong['project_id']='project-beta'
        self.write_jsonl('feedback/task-outcome-v2.jsonl',[wrong])
        with self.assertRaises(ObservationError): observe_project(self.project_id,self.project_dir)

    def test_snapshot_unique_and_exclusive(self):
        kwargs=dict(project_id=self.project_id,source_files=['feedback/a.jsonl'],record_count=1,task_count=1,metrics={'policy_version':'v6.0-default-1'},signals=[],warnings=[],observed_at='2026-08-27T00:00:00+00:00')
        a=SelfObservationSnapshot.create(**kwargs); b=SelfObservationSnapshot.create(**kwargs)
        self.assertNotEqual(a.snapshot_id,b.snapshot_id); self.assertEqual(a.source_digest,b.source_digest)
        path=self.root/'snapshot.json'; exclusive_write_json(path,a)
        with self.assertRaises(StorageError): exclusive_write_json(path,b)

    def test_hook_blocks_sol_and_allows_terra_high(self):
        hook=ROOT/'hooks'/'cp_hook.py'
        env={**os.environ,'CP_ASSISTANT_DATA':str(self.root/'hook-data'),'PYTHONDONTWRITEBYTECODE':'1'}
        bad={'hook_event_name':'PreToolUse','tool_name':'spawn_agent','tool_input':{'model':'gpt-5.6-sol','reasoning_effort':'medium'},'cwd':str(self.root)}
        r=subprocess.run([sys.executable,str(hook)],input=json.dumps(bad),text=True,encoding='utf-8',capture_output=True,env=env,timeout=10)
        self.assertEqual(0,r.returncode); self.assertIn('permissionDecision',r.stdout); self.assertIn('deny',r.stdout)
        good={'hook_event_name':'PreToolUse','tool_name':'spawn_agent','tool_input':{'model':'gpt-5.6-terra','reasoning_effort':'high'},'cwd':str(self.root)}
        r=subprocess.run([sys.executable,str(hook)],input=json.dumps(good),text=True,encoding='utf-8',capture_output=True,env=env,timeout=10)
        self.assertEqual('',r.stdout.strip())

    def test_hook_rejects_above_ceiling_and_unknown_explicit_models(self):
        hook=ROOT/'hooks'/'cp_hook.py'
        env={**os.environ,'CP_ASSISTANT_DATA':str(self.root/'hook-gate-data'),'PYTHONDONTWRITEBYTECODE':'1'}
        denied=[
            ('gpt-5.6-terra','xhigh'),
            ('gpt-5.6-terra','max'),
            ('gpt-5.6-sol','low'),
            ('gpt-5.6-unknown','high'),
            ('gpt-5.7-terra','high'),
        ]
        for model, effort in denied:
            payload={'hook_event_name':'PreToolUse','tool_name':'spawn_agent','tool_input':{'model':model,'reasoning_effort':effort},'cwd':str(self.root)}
            r=subprocess.run([sys.executable,str(hook),'PreToolUse'],input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,env=env,timeout=10)
            self.assertEqual(0,r.returncode,(model,effort,r.stderr))
            self.assertIn('"permissionDecision": "deny"',r.stdout,(model,effort,r.stdout))
        for model, effort in [('gpt-5.6-luna','low'),('gpt-5.6-luna','medium'),('gpt-5.6-terra','medium'),('gpt-5.6-terra','high')]:
            payload={'hook_event_name':'PreToolUse','tool_name':'spawn_agent','tool_input':{'model':model,'reasoning_effort':effort},'cwd':str(self.root)}
            r=subprocess.run([sys.executable,str(hook),'PreToolUse'],input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,env=env,timeout=10)
            self.assertEqual(0,r.returncode,(model,effort,r.stderr))
            self.assertEqual('',r.stdout.strip(),(model,effort,r.stdout))

    def test_stop_accepts_utf8_and_recovers_truncated_non_ascii_message(self):
        hook=ROOT/'hooks'/'cp_hook.py'
        data_root=self.root/'hook-stop-data'
        env={**os.environ,'CP_ASSISTANT_DATA':str(data_root),'PYTHONDONTWRITEBYTECODE':'1'}
        base={'hook_event_name':'Stop','cwd':str(self.root),'session_id':'S-UTF8','turn_id':'T-UTF8','task_id':'TASK-UTF8'}
        valid={**base,'last_assistant_message':'中文完成'}
        r=subprocess.run([sys.executable,str(hook),'Stop'],input=json.dumps(valid,ensure_ascii=False).encode('utf-8'),capture_output=True,env=env,timeout=10)
        self.assertEqual(0,r.returncode,r.stderr.decode('utf-8',errors='replace'))
        self.assertEqual('{}',r.stdout.decode('utf-8').strip())
        truncated_base={**base,'session_id':'S-TRUNCATED','turn_id':'T-TRUNCATED','task_id':'TASK-TRUNCATED'}
        malformed=json.dumps(truncated_base,ensure_ascii=False)[:-1].encode('utf-8')+b',"last_assistant_message":"\xe4\xb8'
        r=subprocess.run([sys.executable,str(hook),'Stop'],input=malformed,capture_output=True,env=env,timeout=10)
        self.assertEqual(0,r.returncode,r.stderr.decode('utf-8',errors='replace'))
        self.assertEqual('{}',r.stdout.decode('utf-8').strip())
        event_files=list(data_root.rglob('task-outcome-v2.jsonl'))
        self.assertEqual(1,len(event_files),event_files)
        events=[json.loads(line) for line in event_files[0].read_text(encoding='utf-8').splitlines() if line.strip()]
        self.assertEqual(['S-UTF8','S-TRUNCATED'],[event['session_id'] for event in events])
        self.assertTrue(all(event['event_type']=='TASK_COMPLETED' for event in events))
        verify_event_chain(event_files[0])

    def test_windows_hook_launcher_and_manifest_contract(self):
        launcher=(ROOT/'hooks'/'cp_hook.cmd').read_text(encoding='utf-8')
        self.assertNotIn('python3.exe',launcher.lower())
        self.assertIn('python.exe',launcher.lower())
        self.assertIn('py.exe',launcher.lower())
        hooks=json.loads((ROOT/'hooks'/'hooks.json').read_text(encoding='utf-8'))['hooks']
        expected={'UserPromptSubmit','PreToolUse','SubagentStart','SubagentStop','Stop','SessionEnd'}
        self.assertEqual(expected,set(hooks))
        for event in expected:
            command=hooks[event][0]['hooks'][0]['commandWindows']
            self.assertEqual(f'cmd.exe /d /c %PLUGIN_ROOT%\\hooks\\cp_hook.cmd {event}',command)
        self.assertEqual(3,hooks['SessionEnd'][0]['hooks'][0]['timeout'])

    def test_proposal_lifecycle_requires_accept_task_baseline_validation_and_close(self):
        start=datetime(2026,7,1,tzinfo=timezone.utc)
        rows=[]
        for i in range(6):
            rows.append({'record_id':f'F{i}','task_id':f'TASK-{i}','timestamp':(start+timedelta(days=i)).isoformat(),
                         'failure_code':'E_TIMEOUT','quality_outcome':'failed','repair_rounds':2})
        self.write_jsonl('feedback/execution-feedback.jsonl',rows)
        service=ControlledEvolutionService(self.root,self.project_id)
        result=service.run(dry_run=False); self.assertTrue(result['proposals'])
        reg=ProposalRegistry(self.project_dir/'evolution',self.project_id); view=reg.list()[0]
        view=reg.decide(view.proposal.proposal_id,DecisionType.ACCEPT,'actor-1','确认该提案证据充分，但所有实施动作仍需独立任务与验证。')
        self.assertEqual(ProposalStatus.ACCEPTED,view.current_status)
        view=reg.link_implementation(view.proposal.proposal_id,'actor-1','TASK-IMPLEMENT-1','baseline-sha')
        self.assertEqual(ProposalStatus.IMPLEMENTATION_LINKED,view.current_status)
        view=reg.record_validation(view.proposal.proposal_id,'actor-1','commit-sha',['evidence://targeted-test-pass'])
        self.assertEqual(ProposalStatus.VALIDATION_RECORDED,view.current_status)
        view=reg.close(view.proposal.proposal_id,'actor-1','PASS')
        self.assertEqual(ProposalStatus.CLOSED,view.current_status)

if __name__=='__main__': unittest.main()
