"""中文：验证 S1/S3/S4 回归边界，不实际安装或调用模型。

English: S1/S3/S4 regression boundaries; no actual installation or model calls.
"""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import research_seed as seed,routing_hook_v5 as hook
from cp_runtime.seed_installation import verify_installation
from cp_runtime.payload_integrity import write_manifest,load_manifest,PAYLOAD_ROOTS,iter_payload_files
from cp_runtime.routing_contract import ref

class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'cache';self.root.mkdir();self.live=Path(self.temp.name)/'live';self.live.mkdir()
        for name in PAYLOAD_ROOTS:(self.root/name).mkdir(parents=True,exist_ok=True)
        names=['runtime/cp_runtime/'+n+'.py' for n in ('research_seed','research_bootstrap','seed_installation','routing_registry_v5','routing_hook_v5','budget_v5')]+['hooks/cp_hook.py']
        self.rows=[]
        for i,name in enumerate(names):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#fixture '+name,encoding='utf8')
            live=self.live/f'{i}.py';live.write_bytes(p.read_bytes());self.rows.append({'package_path':name,'live_path':str(live)})
        manifest=write_manifest(self.root,'fixture','0.0.1')
        self.plan={'candidate_payload_digest':manifest['payload_digest'],'installation':{'payload_root':str(self.root),'manifest_path':str(self.root/'PLUGIN_PAYLOAD_MANIFEST.json'),'runtime_files':self.rows}}
    def tearDown(self):self.temp.cleanup()
    def test_actual_installed_digest_mismatch_is_denied(self):
        self.plan['candidate_payload_digest']=ref('wrong')
        with self.assertRaisesRegex(ValueError,'INSTALLED_PAYLOAD_MISMATCH'):verify_installation(self.plan)
    def test_same_manifest_declaration_with_live_controller_drift_is_denied(self):
        Path(self.rows[0]['live_path']).write_text('# drift',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'LIVE_CONTROLLER_CHANGED'):verify_installation(self.plan)
    def test_correct_unused_copy_cannot_replace_loaded_module_source(self):
        with self.assertRaisesRegex(ValueError,'LOADED_CONTROLLER_SOURCE'):verify_installation(self.plan)
    def test_exact_package_and_loaded_controller_files_verify(self):
        for relative,source in iter_payload_files(ROOT):
            target=self.root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
        manifest=write_manifest(self.root,'fixture','0.0.1')
        rows=[{'package_path':row['path'],'live_path':str(ROOT/row['path'])} for row in manifest['files'] if row['path'].startswith(('runtime/cp_runtime/','hooks/'))]
        self.plan['candidate_payload_digest']=manifest['payload_digest'];self.plan['installation']['runtime_files']=rows
        self.assertTrue(verify_installation(self.plan)['ok'])

class ClosedEventTests(unittest.TestCase):
    def test_non_dispatch_parent_posts_remain_neutral_without_budget_read(self):
        for tool in ('Bash','exec_command','read_file'):
            data={'hook_event_name':'PostToolUse','session_id':'parent','tool_name':tool,'tool_use_id':'ordinary'}
            with patch.object(seed,'closed_duplicate',side_effect=AssertionError('must not classify ordinary POST')):
                self.assertEqual({},hook.lifecycle(Path('unused'),data,'PostToolUse'))
    def test_unknown_closed_spawn_still_conflicts(self):
        state={'closed':True,'root_binding':{'context_runtime':{'bootstrap_contract':seed.CONTRACT}},'host_dispatches':{},'host_identity_links':{}}
        with patch.object(seed.budget,'read_budget',return_value=state),self.assertRaisesRegex(ValueError,'CLOSED_EVENT_CONFLICT'):
            hook.lifecycle(Path('unused'),{'hook_event_name':'PostToolUse','session_id':'parent','tool_name':'collaborationspawn_agent','tool_use_id':'unknown'},'PostToolUse')
    def stop(self,outcome):
        child='child';proof={'header_ref':ref('header'),'turn_ref':ref('turn'),'response_ref':ref('text')}
        state={'closed':True,'root_binding':{'context_runtime':{'bootstrap_contract':seed.CONTRACT},'repo_path':'fixture'},
          'sources':{'root_envelope':'fixture'},'host_identity_links':{'rid':{'agent_ref':ref(child)}},
          'permits':{'permit':{'dispatch_ref':ref('task'),'role':'cp_review_security_access'}},
          'reservations':{'rid':{'permit_id':'permit'}},'context_raw_finals':{'rid':proof},'host_observations':{ref(child):{'stop':'PASS'}}}
        data={'hook_event_name':'SubagentStop','agent_id':child,'session_id':'parent','terminal_outcome':outcome}
        with patch.object(seed.budget,'read_budget',return_value=state),patch.object(seed,'_read',return_value={'routing':{'research_seed':{'source':{},'ordinal':1}}}),patch.object(seed,'_segment_state',return_value=(None,None,None,{'calls':[{'dispatch_key':'task'}]},state)),patch('cp_runtime.routing_hook_v5._transcript_path',return_value=Path('fixture')),patch('cp_runtime.context_final_v2.read_bound_transcript',return_value=(b'fixture',{})),patch('cp_runtime.context_final_v2.extract_final',return_value=('same final',proof)):
            return seed.closed_duplicate(Path('fixture'),data)
    def test_exact_same_stop_is_idempotent(self):self.assertTrue(self.stop('PASS'))
    def test_same_text_different_outcomes_conflict(self):
        for outcome in ('FAILED','CANCELLED','UNKNOWN'):
            with self.subTest(outcome=outcome),self.assertRaisesRegex(ValueError,'OBSERVATION_CONFLICT'):self.stop(outcome)

if __name__=='__main__':unittest.main()
