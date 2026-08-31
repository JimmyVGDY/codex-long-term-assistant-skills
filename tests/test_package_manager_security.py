#!/usr/bin/env python3
"""中文：V6.6 安装器安全与作用域冒烟测试。

English: V6.6 installer security and scope smoke tests.
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile, time, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANAGER=ROOT/'scripts'/'package_manager.py'


def io_path(path: Path) -> Path:
    absolute=str(path.absolute())
    if os.name != 'nt' or absolute.startswith('\\\\?\\'):
        return Path(absolute)
    return Path('\\\\?\\'+absolute)


def run(args, env, expected=0):
    r=subprocess.run([sys.executable,'-B',str(MANAGER),*args],env=env,text=True,capture_output=True,timeout=30)
    if r.returncode!=expected:
        raise AssertionError(f'rc={r.returncode}, expected={expected}\nstdout={r.stdout}\nstderr={r.stderr}')
    return r


class PackageManagerV64Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='cp-v63-pm-')
        self.home=Path(self.tmp.name)/'home'; self.home.mkdir()
        self.codex=self.home/'.codex'
        self.bin=Path(self.tmp.name)/'bin'; self.bin.mkdir()
        fake=self.bin/'fake_codex.py'
        fake.write_text("""#!/usr/bin/env python3
import json, os, shutil, sys
from pathlib import Path
def io_path(path):
    absolute=str(path.absolute())
    return Path((r'\\\\?' + os.sep + absolute) if os.name=='nt' and not absolute.startswith(r'\\\\?') else absolute)
home=Path(os.environ.get('CODEX_HOME') or '.')
state=home/'fake-codex-plugin-state.json'
market_file=home/'fake-codex-marketplace-path.txt'
args=sys.argv[1:]
if args == ['--version']:
    print(os.environ.get('FAKE_CODEX_VERSION', 'codex-cli 0.150.1')); raise SystemExit(0)
if args[:3] == ['plugin','marketplace','add']:
    if len(args) > 3 and args[3] != '--help': market_file.write_text(args[3],encoding='utf-8')
    print('marketplace added'); raise SystemExit(0)
if args[:3] == ['plugin','marketplace','remove']:
    print('marketplace removed'); raise SystemExit(0)
if args[:2] == ['plugin','add']:
    if len(args) > 2 and args[2] == '--help': print('plugin add help'); raise SystemExit(0)
    home.mkdir(parents=True,exist_ok=True)
    state.write_text(json.dumps({'installed':True}),encoding='utf-8')
    version=os.environ.get('FAKE_PLUGIN_VERSION','6.6.1')
    source=Path(market_file.read_text(encoding='utf-8'))/'plugins'/'codex-cross-project-engineering-assistant'
    cache=home/'plugins'/'cache'/'cp-assistant-local'/'codex-cross-project-engineering-assistant'/version
    if io_path(cache).exists(): shutil.rmtree(io_path(cache))
    shutil.copytree(io_path(source),io_path(cache))
    print('plugin added'); raise SystemExit(0)
if args[:2] == ['plugin','remove']:
    if len(args) > 2 and args[2] == '--help': print('plugin remove help'); raise SystemExit(0)
    state.unlink(missing_ok=True)
    print('plugin removed'); raise SystemExit(0)
if args == ['plugin','list','--json']:
    if os.environ.get('FAKE_LIST_INVALID_UNTIL_MARKETPLACE_ADD') == '1' and not market_file.exists():
        print('configured marketplace manifest is invalid',file=sys.stderr); raise SystemExit(2)
    installed=[]
    if state.exists():
        installed=[{'pluginId':'codex-cross-project-engineering-assistant@cp-assistant-local','name':'codex-cross-project-engineering-assistant','marketplaceName':'cp-assistant-local','version':os.environ.get('FAKE_PLUGIN_VERSION','6.6.1'),'installed':True,'enabled':True}]
    print(json.dumps({'installed':installed,'available':[]})); raise SystemExit(0)
print('unsupported fake codex args: '+repr(args),file=sys.stderr); raise SystemExit(2)
""",encoding='utf-8')
        fake.chmod(0o755)
        if os.name == 'nt':
            (self.bin/'codex.cmd').write_text(
                '@echo off\r\n"' + sys.executable + '" "%~dp0fake_codex.py" %*\r\n',
                encoding='utf-8',
            )
        else:
            (self.bin/'codex').write_text(fake.read_text(encoding='utf-8'),encoding='utf-8')
            (self.bin/'codex').chmod(0o755)
        self.env={
            **os.environ,
            'HOME':str(self.home),
            'USERPROFILE':str(self.home),
            'CODEX_HOME':str(self.codex),
            'PYTHONDONTWRITEBYTECODE':'1',
            'PATH':str(self.bin)+os.pathsep+os.environ.get('PATH','')
        }

    def tearDown(self):
        try:
            self.tmp.cleanup()
        except OSError:
            shutil.rmtree(io_path(Path(self.tmp.name)),ignore_errors=True)

    def test_standalone_install_verify_uninstall(self):
        run(['install','--scope','user','--mode','standalone','--dry-run'],self.env)
        run(['install','--scope','user','--mode','standalone'],self.env)
        self.assertFalse((self.codex/'cp-assistant-v6-transaction.json').exists())
        run(['verify','--scope','user','--mode','standalone'],self.env)
        self.assertTrue((self.home/'.agents'/'skills'/'controlled-evolution-governance'/'SKILL.md').is_file())
        hooks=json.loads((self.codex/'hooks.json').read_text(encoding='utf-8'))
        self.assertIn('PreToolUse',hooks['hooks'])
        self.assertEqual(hooks['hooks']['SessionEnd'][0]['hooks'][0]['timeout'],3)
        run(['uninstall','--scope','user','--mode','standalone'],self.env)
        self.assertFalse((self.home/'.agents'/'skills'/'controlled-evolution-governance').exists())

    def test_plugin_install_verify_uninstall(self):
        run(['install','--scope','user','--mode','plugin'],self.env)
        run(['verify','--scope','user','--mode','plugin'],self.env)
        p=self.home/'.agents'/'plugins'/'cp-assistant-marketplace'/'plugins'/'codex-cross-project-engineering-assistant'
        self.assertTrue((p/'.codex-plugin'/'plugin.json').is_file())
        self.assertTrue((p/'hooks'/'hooks.json').is_file())
        self.assertTrue((self.codex/'fake-codex-plugin-state.json').is_file())
        run(['uninstall','--scope','user','--mode','plugin'],self.env)

    def test_legacy_invalid_marketplace_is_canonicalized_before_activation(self):
        self.codex.mkdir(parents=True,exist_ok=True)
        state={
            'schema_version':1,
            'package':'codex-cross-project-engineering-assistant',
            'version':'6.3.0',
            'scope':'user',
            'mode':'plugin',
            'backup':'legacy-backup',
            'managed_hashes':{},
        }
        (self.codex/'cp-assistant-v6-state.json').write_text(json.dumps(state),encoding='utf-8')
        manifest=self.home/'.agents'/'plugins'/'cp-assistant-marketplace'/'.agents'/'plugins'/'marketplace.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({
            'name':'cp-assistant-local',
            'owner':{'name':'local-user'},
            'plugins':[{
                'name':'codex-cross-project-engineering-assistant',
                'source':{'source':'local','path':'./plugins/codex-cross-project-engineering-assistant'},
                'description':'legacy',
            }],
        }),encoding='utf-8')
        env={**self.env,'FAKE_LIST_INVALID_UNTIL_MARKETPLACE_ADD':'1'}
        run(['install','--scope','user','--mode','plugin','--dry-run'],env)
        run(['install','--scope','user','--mode','plugin'],env)
        current=json.loads(manifest.read_text(encoding='utf-8'))
        self.assertNotIn('owner',current)
        self.assertEqual('Codex Cross Project Assistant Local',current['interface']['displayName'])
        entry=next(item for item in current['plugins'] if item['name']=='codex-cross-project-engineering-assistant')
        self.assertEqual('AVAILABLE',entry['policy']['installation'])
        self.assertEqual('ON_INSTALL',entry['policy']['authentication'])
        self.assertEqual('Productivity',entry['category'])
        run(['verify','--scope','user','--mode','plugin'],env)

    def test_plugin_install_rejects_wrong_registered_version(self):
        env={**self.env,'FAKE_PLUGIN_VERSION':'6.2.0'}
        result=run(['install','--scope','user','--mode','plugin'],env,2)
        self.assertIn('version=6.6.1',result.stderr)
        self.assertFalse((self.codex/'cp-assistant-v6-transaction.json').exists())
        self.assertFalse((self.codex/'cp-assistant-v6-state.json').exists())
        self.assertFalse((self.codex/'fake-codex-plugin-state.json').exists())
        self.assertFalse((self.home/'.agents'/'plugins'/'cp-assistant-marketplace').exists())

    def test_uninstall_preserves_user_agents_and_hooks_edits(self):
        self.codex.mkdir(parents=True,exist_ok=True)
        agents=self.codex/'AGENTS.md'
        agents.write_text('# User rules before install\n',encoding='utf-8')
        hooks_path=self.codex/'hooks.json'
        hooks_path.write_text(json.dumps({
            'hooks': {
                'UserCustom': [{'hooks':[{'type':'command','command':'user-before.cmd'}]}]
            },
            'user_metadata': 'keep-me',
        }),encoding='utf-8')
        run(['install','--scope','user','--mode','standalone'],self.env)
        agents.write_text(agents.read_text(encoding='utf-8')+'\n# User rules during install\n',encoding='utf-8')
        current=json.loads(hooks_path.read_text(encoding='utf-8'))
        current['hooks']['UserDuring']=[{'hooks':[{'type':'command','command':'user-during.cmd'}]}]
        current['user_metadata']='changed-by-user'
        hooks_path.write_text(json.dumps(current),encoding='utf-8')
        run(['uninstall','--scope','user','--mode','standalone'],self.env)
        restored_agents=agents.read_text(encoding='utf-8')
        self.assertIn('# User rules before install',restored_agents)
        self.assertIn('# User rules during install',restored_agents)
        self.assertNotIn('CODEX-CROSS-PROJECT-ASSISTANT:BEGIN',restored_agents)
        restored_hooks=json.loads(hooks_path.read_text(encoding='utf-8'))
        self.assertIn('UserCustom',restored_hooks['hooks'])
        self.assertIn('UserDuring',restored_hooks['hooks'])
        self.assertEqual('changed-by-user',restored_hooks['user_metadata'])
        self.assertNotIn('SessionEnd',restored_hooks['hooks'])

    def test_upgrade_uninstall_restores_old_managed_fragments_and_keeps_marker_collision(self):
        self.codex.mkdir(parents=True,exist_ok=True)
        agents=self.codex/'AGENTS.md'
        agents.write_text(
            '# User before\n\n<!-- CODEX-CROSS-PROJECT-ASSISTANT:BEGIN -->\nOLD MANAGED BLOCK\n'
            '<!-- CODEX-CROSS-PROJECT-ASSISTANT:END -->\n',
            encoding='utf-8',
        )
        old_command='"python.exe" "'+str(self.codex/'cp-assistant-hooks'/'cp_hook.py')+'"'
        hooks_path=self.codex/'hooks.json'
        hooks_path.write_text(json.dumps({'hooks':{
            'Stop':[{'hooks':[{'type':'command','command':old_command}]}],
            'UserCollision':[{'hooks':[{'type':'command','command':'echo cp-assistant-hooks marker only'}]}],
        }}),encoding='utf-8')
        run(['install','--scope','user','--mode','standalone'],self.env)
        agents.write_text(agents.read_text(encoding='utf-8')+'\n# User during\n',encoding='utf-8')
        run(['uninstall','--scope','user','--mode','standalone'],self.env)
        restored_agents=agents.read_text(encoding='utf-8')
        self.assertIn('OLD MANAGED BLOCK',restored_agents)
        self.assertIn('# User before',restored_agents)
        self.assertIn('# User during',restored_agents)
        restored_hooks=json.loads(hooks_path.read_text(encoding='utf-8'))
        self.assertEqual(old_command,restored_hooks['hooks']['Stop'][0]['hooks'][0]['command'])
        self.assertEqual('echo cp-assistant-hooks marker only',restored_hooks['hooks']['UserCollision'][0]['hooks'][0]['command'])

    def test_malformed_hooks_fail_closed_without_overwrite(self):
        run(['install','--scope','user','--mode','standalone'],self.env)
        hooks_path=self.codex/'hooks.json'
        hooks_path.write_text('{ malformed user hooks',encoding='utf-8')
        result=run(['uninstall','--scope','user','--mode','standalone'],self.env,2)
        self.assertIn('拒绝覆盖外部文件',result.stderr)
        self.assertEqual('{ malformed user hooks',hooks_path.read_text(encoding='utf-8'))

    def test_doctor_reads_codex_version(self):
        r=run(['doctor'],self.env)
        data=json.loads(r.stdout)
        self.assertEqual(data['target_codex'],'0.150.1')
        self.assertIn('0.150.1',data['codex_version'])

    def test_crash_journal_recovers_and_status_is_json(self):
        crashed={**self.env, 'CP_ASSISTANT_TEST_CRASH_STAGE':'APPLYING'}
        run(['install','--scope','user','--mode','standalone'],crashed,2)
        journal=self.codex/'cp-assistant-v6-transaction.json'
        self.assertTrue(journal.is_file())
        run(['doctor','--recover'],self.env)
        self.assertFalse(journal.exists())
        status=json.loads(run(['status','--json'],self.env).stdout)
        self.assertEqual('6.6.1',status['version'])
        self.assertIn('live_transaction',status)

    def test_mode_switch_is_refused_without_force(self):
        run(['install','--scope','user','--mode','standalone'],self.env)
        result=run(['install','--scope','user','--mode','plugin'],self.env,2)
        self.assertIn('模式切换默认拒绝',result.stderr)

    def test_prepared_recovery_and_old_live_journal_rejection(self):
        crashed={**self.env, 'CP_ASSISTANT_TEST_CRASH_STAGE':'PREPARED'}
        run(['install','--scope','user','--mode','standalone'],crashed,2)
        blocked=run(['install','--scope','user','--mode','standalone'],self.env,2)
        self.assertIn('doctor --recover',blocked.stderr)
        run(['doctor','--recover'],self.env)
        self.assertFalse((self.codex/'cp-assistant-v6-transaction.json').exists())

    def test_uninstall_crash_recovers_installed_files(self):
        run(['install','--scope','user','--mode','standalone'],self.env)
        crashed={**self.env, 'CP_ASSISTANT_TEST_CRASH_STAGE':'APPLYING'}
        run(['uninstall','--scope','user','--mode','standalone'],crashed,2)
        run(['doctor','--recover'],self.env)
        run(['verify','--scope','user','--mode','standalone'],self.env)

    def test_uninstall_target_window_crash_rolls_back_partial_restore(self):
        run(['install','--scope','user','--mode','standalone'],self.env)
        crashed={**self.env,'CP_ASSISTANT_TEST_CRASH_AFTER_TARGET':'agent:cp-review-test-delivery.toml'}
        run(['uninstall','--scope','user','--mode','standalone'],crashed,2)
        self.assertTrue((self.codex/'cp-assistant-v6-transaction.json').is_file())
        run(['recover','--scope','user'],self.env)
        run(['verify','--scope','user','--mode','standalone'],self.env)
        self.assertFalse((self.codex/'cp-assistant-v6-transaction.json').exists())

    def test_plugin_host_unknown_version_fails_closed(self):
        bad={**self.env, 'FAKE_CODEX_VERSION':'codex-cli 0.151.0'}
        result=run(['install','--scope','user','--mode','plugin'],bad,2)
        self.assertIn('仅支持 Codex CLI 0.150.1',result.stderr)

    def test_plugin_crash_recovery_removes_new_activation(self):
        crashed={**self.env, 'CP_ASSISTANT_TEST_CRASH_STAGE':'ACTIVATING'}
        run(['install','--scope','user','--mode','plugin'],crashed,2)
        run(['doctor','--recover'],self.env)
        self.assertFalse((self.codex/'fake-codex-plugin-state.json').exists())

    def test_target_action_crash_has_durable_ownership_for_recovery(self):
        crashed={**self.env, 'CP_ASSISTANT_TEST_CRASH_AFTER_TARGET':'agent:cp-review-security-access.toml'}
        run(['install','--scope','user','--mode','standalone'],crashed,2)
        journal=json.loads((self.codex/'cp-assistant-v6-transaction.json').read_text(encoding='utf-8'))
        self.assertIn('agent:cp-review-security-access.toml',journal['applied_targets'])
        run(['doctor','--recover'],self.env)
        self.assertFalse((self.codex/'agents'/'cp-review-security-access.toml').exists())

    def test_plugin_uninstall_crash_restores_prior_activation(self):
        run(['install','--scope','user','--mode','plugin'],self.env)
        crashed={**self.env, 'CP_ASSISTANT_TEST_CRASH_AFTER_PLUGIN_DEACTIVATE':'1'}
        run(['uninstall','--scope','user','--mode','plugin'],crashed,2)
        run(['doctor','--recover'],self.env)
        self.assertTrue((self.codex/'fake-codex-plugin-state.json').exists())

    def test_plugin_marketplace_atomic_swap_crash_restores_previous_tree(self):
        run(['install','--scope','user','--mode','plugin'],self.env)
        market=self.home/'.agents'/'plugins'/'cp-assistant-marketplace'
        marker=market/'external-marker.txt'; marker.write_text('preserve-before-swap',encoding='utf-8')
        for stage in ('BEFORE_REPLACE','AFTER_REPLACE'):
            with self.subTest(stage=stage):
                crashed={**self.env,'CP_ASSISTANT_TEST_CRASH_PLUGIN_MARKETPLACE_STAGE':stage}
                run(['install','--scope','user','--mode','plugin'],crashed,2)
                run(['recover','--scope','user'],self.env)
                self.assertEqual('preserve-before-swap',marker.read_text(encoding='utf-8'))
                run(['verify','--scope','user','--mode','plugin'],self.env)

    def test_recovery_preserves_drift_and_requires_attention(self):
        crashed={**self.env, 'CP_ASSISTANT_TEST_CRASH_STAGE':'APPLYING'}
        run(['install','--scope','user','--mode','standalone'],crashed,2)
        agent=self.codex/'agents'/'cp-review-security-access.toml'
        agent.parent.mkdir(parents=True,exist_ok=True)
        agent.write_text('external drift',encoding='utf-8')
        result=run(['doctor','--recover'],self.env,2)
        self.assertIn('未知漂移',result.stderr)
        self.assertEqual('external drift',agent.read_text(encoding='utf-8'))

    def test_source_and_symlink_targets_rejected(self):
        bad={**self.env,'CODEX_HOME':str(ROOT)}
        r=run(['install','--scope','user','--mode','standalone','--dry-run'],bad,2)
        self.assertIn('危险目录',r.stderr)
        self.codex.mkdir(parents=True,exist_ok=True)
        outside=self.home/'outside'; outside.mkdir()
        if os.name == 'nt':
            made=subprocess.run(
                ['cmd.exe','/d','/c','mklink','/J',str(self.codex/'agents'),str(outside)],
                text=True,capture_output=True,
            )
            self.assertEqual(made.returncode,0,made.stdout+made.stderr)
        else:
            (self.codex/'agents').symlink_to(outside,target_is_directory=True)
        r=run(['install','--scope','user','--mode','standalone'],self.env,2)
        self.assertTrue('符号链接' in r.stderr or 'Reparse' in r.stderr)

    def test_real_process_hard_crash_boundaries_recover_prior_install(self):
        run(['install','--scope','user','--mode','plugin'],self.env)
        market=self.home/'.agents'/'plugins'/'cp-assistant-marketplace'
        unknown=market/'unknown-user-file.txt'
        unknown.write_text('preserve',encoding='utf-8')
        for point in ('PLUGIN:AFTER_ADD','PLUGIN:AFTER_CACHE_VERIFY','PLUGIN:AFTER_STATE_WRITE'):
            with self.subTest(point=point):
                env={**self.env,'CP_ASSISTANT_TEST_HARD_CRASH_POINT':point}
                run(['install','--scope','user','--mode','plugin'],env,91)
                self.assertTrue((self.codex/'cp-assistant-v6-transaction.json').is_file())
                run(['doctor','--recover'],self.env)
                self.assertEqual('preserve',unknown.read_text(encoding='utf-8'))
                run(['verify','--scope','user','--mode','plugin'],self.env)

    def test_second_process_is_rejected_while_scope_lock_is_live(self):
        code=(
            "import sys,time; sys.path.insert(0,r'%s'); "
            "import package_manager as p; "
            "\nwith p.scope_lock('user'):\n print('LOCKED',flush=True)\n time.sleep(5)" % str(ROOT/'scripts')
        )
        holder=subprocess.Popen([sys.executable,'-B','-c',code],env=self.env,text=True,
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            self.assertEqual('LOCKED',holder.stdout.readline().strip())
            blocked=run(['install','--scope','user','--mode','standalone'],self.env,2)
            self.assertIn('scope',blocked.stderr)
        finally:
            holder.terminate()
            holder.communicate(timeout=10)

    def test_nested_reparse_inside_managed_plugin_tree_is_rejected(self):
        run(['install','--scope','user','--mode','plugin'],self.env)
        external=Path(self.tmp.name)/'external-nested'; external.mkdir()
        (external/'sentinel.txt').write_text('keep',encoding='utf-8')
        link=self.home/'.agents'/'plugins'/'cp-assistant-marketplace'/'plugins'/'codex-cross-project-engineering-assistant'/'runtime'/'linked-external'
        if os.name == 'nt':
            created=subprocess.run(['cmd','/c','mklink','/J',str(link),str(external)],capture_output=True,text=True)
            if created.returncode != 0:
                self.skipTest('Junction creation unavailable: '+created.stderr)
        else:
            link.symlink_to(external,target_is_directory=True)
        try:
            failed=run(['install','--scope','user','--mode','plugin'],self.env,2)
            self.assertTrue('Reparse' in failed.stderr or '符号链接' in failed.stderr)
            self.assertEqual('keep',(external/'sentinel.txt').read_text(encoding='utf-8'))
        finally:
            if link.exists() or link.is_symlink():
                link.unlink() if link.is_symlink() else link.rmdir()

    @unittest.skipUnless(os.name == 'nt','Windows extended-length path regression')
    def test_plugin_reinstall_supports_long_windows_backup_paths(self):
        long_home=Path(self.tmp.name)/('long-home-'+'x'*72)/('nested-'+'y'*72)
        long_home.mkdir(parents=True)
        long_codex=long_home/'.codex'
        env={
            **self.env,
            'HOME':str(long_home),
            'USERPROFILE':str(long_home),
            'CODEX_HOME':str(long_codex),
        }
        run(['install','--scope','user','--mode','plugin'],env)
        run(['install','--scope','user','--mode','plugin'],env)
        run(['verify','--scope','user','--mode','plugin'],env)
        state=json.loads(io_path(long_codex/'cp-assistant-v6-state.json').read_text(encoding='utf-8'))
        backup=Path(state['backup'])
        self.assertTrue(io_path(backup/'backup-manifest.json').is_file())
        # 中文：第一次卸载恢复首个 V6.3 安装，第二次将隔离 HOME 恢复为空的初始状态。
        # English: The first uninstall restores the initial V6.3 installation; the second
        # English: returns the isolated HOME to its original empty state.
        run(['uninstall','--scope','user','--mode','plugin'],env)
        run(['uninstall','--scope','user','--mode','plugin'],env)
        self.assertFalse(io_path(long_home/'.agents'/'plugins'/'cp-assistant-marketplace').exists())

if __name__=='__main__':
    unittest.main()
