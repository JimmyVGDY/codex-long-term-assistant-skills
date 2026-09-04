#!/usr/bin/env python3
"""中文：V6.6 安装器安全与作用域冒烟测试。

English: V6.6 installer security and scope smoke tests.
"""
from __future__ import annotations
import importlib.util, json, os, shutil, subprocess, sys, tempfile, time, unittest
from unittest import mock
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANAGER=ROOT/'scripts'/'package_manager.py'
sys.path.insert(0,str(ROOT/'scripts'))
SPEC=importlib.util.spec_from_file_location('package_manager_under_test',MANAGER)
assert SPEC and SPEC.loader
package_manager=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_manager)


def io_path(path: Path) -> Path:
    absolute=str(path.absolute())
    if os.name != 'nt' or absolute.startswith('\\\\?\\'):
        return Path(absolute)
    return Path('\\\\?\\'+absolute)


def run(args, env, expected=0):
    r=subprocess.run([sys.executable,'-B',str(MANAGER),*args],env=env,text=True,encoding='utf-8',capture_output=True,timeout=30)
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
import base64, json, os, shutil, sys, zlib
from pathlib import Path
def io_path(path):
    absolute=str(path.absolute())
    return Path((r'\\\\?' + os.sep + absolute) if os.name=='nt' and not absolute.startswith(r'\\\\?') else absolute)
home=Path(os.environ.get('CODEX_HOME') or '.')
state=home/'fake-codex-plugin-state.json'
market_file=home/'fake-codex-marketplace-path.txt'
args=sys.argv[1:]
help_fixture=json.loads(Path(os.environ['FAKE_CODEX_CONTRACT_FIXTURE']).read_text(encoding='utf-8'))
def emit_help(name):
    fixture_name=name
    if os.environ.get('FAKE_CODEX_VERSION') == 'codex-cli 0.152.1' and name + '_0_152_1' in help_fixture:
        fixture_name=name + '_0_152_1'
    text=zlib.decompress(base64.b64decode(help_fixture[fixture_name])).decode('utf-8')
    if os.environ.get('FAKE_HELP_DRIFT') == name: text += '\\nfuture option'
    print(text,end='')
if args == ['--version']:
    print(os.environ.get('FAKE_CODEX_VERSION', 'codex-cli 0.153.2')); raise SystemExit(0)
if args[:3] == ['plugin','marketplace','add']:
    if len(args) > 3 and args[3] == '--help': emit_help('marketplace_add'); raise SystemExit(0)
    if len(args) > 3 and args[3] != '--help': market_file.write_text(args[3],encoding='utf-8')
    print('marketplace added'); raise SystemExit(0)
if args[:3] == ['plugin','marketplace','remove']:
    if len(args) > 3 and args[3] == '--help': emit_help('marketplace_remove'); raise SystemExit(0)
    print('marketplace removed'); raise SystemExit(0)
if args[:2] == ['plugin','add']:
    if len(args) > 2 and args[2] == '--help': emit_help('plugin_add'); raise SystemExit(0)
    home.mkdir(parents=True,exist_ok=True)
    state.write_text(json.dumps({'installed':True}),encoding='utf-8')
    version=os.environ.get('FAKE_PLUGIN_VERSION','7.4.3')
    source=Path(market_file.read_text(encoding='utf-8'))/'plugins'/'codex-cross-project-engineering-assistant'
    cache=home/'plugins'/'cache'/'cp-assistant-local'/'codex-cross-project-engineering-assistant'/version
    if io_path(cache).exists(): shutil.rmtree(io_path(cache))
    shutil.copytree(io_path(source),io_path(cache))
    print('plugin added'); raise SystemExit(0)
if args[:2] == ['plugin','remove']:
    if len(args) > 2 and args[2] == '--help': emit_help('plugin_remove'); raise SystemExit(0)
    state.unlink(missing_ok=True)
    print('plugin removed'); raise SystemExit(0)
if args == ['plugin','list','--json']:
    if os.environ.get('FAKE_LIST_INVALID_UNTIL_MARKETPLACE_ADD') == '1' and not market_file.exists():
        print('configured marketplace manifest is invalid',file=sys.stderr); raise SystemExit(2)
    installed=[]
    if state.exists():
        installed=[{'pluginId':'codex-cross-project-engineering-assistant@cp-assistant-local','name':'codex-cross-project-engineering-assistant','marketplaceName':'cp-assistant-local','version':os.environ.get('FAKE_PLUGIN_VERSION','7.4.3'),'installed':True,'enabled':True,'installPolicy':'AVAILABLE','authPolicy':'ON_INSTALL'}]
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
            'PYTHONIOENCODING':'utf-8',
            'FAKE_CODEX_CONTRACT_FIXTURE':str(ROOT/'tests'/'fixtures'/'codex-cli-help-v1.json'),
            'PATH':str(self.bin)+os.pathsep+os.environ.get('PATH','')
        }

    def assert_installed_tools_run(self):
        for name in ('cp-runtime.py','evolution.py'):
            tool=self.codex/'tools'/name
            self.assertTrue(tool.is_file(),name)
            result=subprocess.run(
                [sys.executable,'-B',str(tool),'--help'],
                env=self.env,text=True,encoding='utf-8',capture_output=True,timeout=30,
            )
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)

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
        self.assert_installed_tools_run()
        self.assertTrue((self.home/'.agents'/'skills'/'controlled-evolution-governance'/'SKILL.md').is_file())
        hooks=json.loads((self.codex/'hooks.json').read_text(encoding='utf-8'))
        self.assertIn('PreToolUse',hooks['hooks'])
        self.assertEqual(hooks['hooks']['SessionEnd'][0]['hooks'][0]['timeout'],3)
        run(['uninstall','--scope','user','--mode','standalone'],self.env)
        self.assertFalse((self.home/'.agents'/'skills'/'controlled-evolution-governance').exists())

    def test_v71_upgrade_removes_only_declared_legacy_skills(self):
        skills_home=self.home/'.agents'/'skills'
        legacy=(
            'java-backend-engineering',
            'python-backend-ai-engineering',
            'data-middleware-ai-infrastructure',
            'vue-frontend-engineering',
        )
        for name in legacy:
            target=skills_home/name
            target.mkdir(parents=True,exist_ok=True)
            (target/'SKILL.md').write_text('legacy',encoding='utf-8')
        unknown=skills_home/'user-owned-skill'
        unknown.mkdir(parents=True)
        (unknown/'SKILL.md').write_text('keep',encoding='utf-8')

        run(['install','--scope','user','--mode','standalone'],self.env)
        run(['verify','--scope','user','--mode','standalone'],self.env)

        for name in legacy:
            self.assertFalse((skills_home/name).exists())
        self.assertEqual('keep',(unknown/'SKILL.md').read_text(encoding='utf-8'))
        self.assertTrue((skills_home/'backend-engineering'/'SKILL.md').is_file())
        self.assertTrue((skills_home/'ai-engineering'/'SKILL.md').is_file())

    def test_manifest_skill_directory_names_fail_closed_before_account_io(self):
        skills_home=self.home/'.agents'/'skills'
        sentinel=self.home/'outside-sentinel.txt'
        sentinel.write_text('keep',encoding='utf-8')
        invalid_names=('../outside','/outside','C:\\outside','..','nested/name','nested\\name')
        for invalid in invalid_names:
            with self.subTest(name=invalid):
                manifest_path=Path(self.tmp.name)/('manifest-'+str(len(invalid))+'.json')
                manifest_path.write_text(json.dumps({
                    'skills':[{'name':'backend-engineering'}],
                    'deprecated_skills':[invalid],
                }),encoding='utf-8')
                with mock.patch.object(package_manager,'MANIFEST_PATH',manifest_path), \
                     mock.patch.object(package_manager,'codex_home',return_value=self.codex), \
                     mock.patch.object(package_manager,'user_skills_home',return_value=skills_home):
                    with self.assertRaises(package_manager.InstallError):
                        package_manager.install_user('standalone',True,False)
                self.assertEqual('keep',sentinel.read_text(encoding='utf-8'))
                self.assertFalse((self.home/'outside').exists())

    def test_plugin_install_verify_uninstall(self):
        run(['install','--scope','user','--mode','plugin'],self.env)
        run(['verify','--scope','user','--mode','plugin'],self.env)
        self.assert_installed_tools_run()
        p=self.home/'.agents'/'plugins'/'cp-assistant-marketplace'/'plugins'/'codex-cross-project-engineering-assistant'
        self.assertTrue((p/'.codex-plugin'/'plugin.json').is_file())
        self.assertTrue((p/'hooks'/'hooks.json').is_file())
        self.assertTrue((self.codex/'fake-codex-plugin-state.json').is_file())
        state=json.loads((self.codex/'cp-assistant-v6-state.json').read_text(encoding='utf-8'))
        self.assertEqual(3,state['schema_version'])
        self.assertEqual('HOST_COMPATIBLE',state['compatibility_status'])
        self.assertEqual(1,state['compatibility_snapshot']['schema_version'])
        run(['uninstall','--scope','user','--mode','plugin'],self.env)
        self.assertFalse((self.codex/'tools'/'cp-runtime.py').exists())
        self.assertFalse((self.codex/'tools'/'evolution.py').exists())

    def test_plugin_payload_excludes_python_bytecode(self):
        source=Path(self.tmp.name)/'payload-source'
        target=Path(self.tmp.name)/'payload-target'
        cache=source/'__pycache__'
        cache.mkdir(parents=True)
        (source/'current.py').write_text('CURRENT = True\n',encoding='utf-8')
        (cache/'removed.cpython-313.pyc').write_bytes(b'stale-bytecode')
        (source/'legacy.pyc').write_bytes(b'stale-bytecode')
        (source/'legacy.pyo').write_bytes(b'stale-bytecode')

        package_manager._copy_plugin_payload_tree(source,target)

        self.assertTrue((target/'current.py').is_file())
        self.assertFalse((target/'__pycache__').exists())
        self.assertFalse((target/'legacy.pyc').exists())
        self.assertFalse((target/'legacy.pyo').exists())

    def test_windows_hook_uses_consistent_crlf_bytes(self):
        launcher=(ROOT/'hooks'/'cp_hook.cmd').read_bytes()
        self.assertGreater(launcher.count(b'\r\n'),0)
        self.assertNotIn(b'\n',launcher.replace(b'\r\n',b''))

    def test_plugin_tools_prefer_versioned_cache_over_stale_standalone_runtime(self):
        stale_runtime=self.codex/'runtime'/'cp_runtime'
        (stale_runtime/'evolution').mkdir(parents=True)
        (stale_runtime/'__init__.py').write_text('',encoding='utf-8')
        (stale_runtime/'evolution'/'__init__.py').write_text('',encoding='utf-8')
        (stale_runtime/'cli.py').write_text(
            "raise RuntimeError('STALE_RUNTIME_SELECTED')\n",encoding='utf-8'
        )
        (stale_runtime/'evolution'/'cli.py').write_text(
            "raise RuntimeError('STALE_RUNTIME_SELECTED')\n",encoding='utf-8'
        )

        run(['install','--scope','user','--mode','plugin'],self.env)
        run(['verify','--scope','user','--mode','plugin'],self.env)
        self.assert_installed_tools_run()

    def test_plugin_tools_fail_closed_when_state_or_bound_cache_is_unavailable(self):
        stale_runtime=self.codex/'runtime'/'cp_runtime'
        (stale_runtime/'evolution').mkdir(parents=True)
        (stale_runtime/'__init__.py').write_text('',encoding='utf-8')
        (stale_runtime/'evolution'/'__init__.py').write_text('',encoding='utf-8')
        (stale_runtime/'cli.py').write_text(
            "raise RuntimeError('STALE_RUNTIME_SELECTED')\n",encoding='utf-8'
        )
        (stale_runtime/'evolution'/'cli.py').write_text(
            "raise RuntimeError('STALE_RUNTIME_SELECTED')\n",encoding='utf-8'
        )
        run(['install','--scope','user','--mode','plugin'],self.env)
        state_path=self.codex/'cp-assistant-v6-state.json'
        state_bytes=state_path.read_bytes()
        cache=self.codex/'plugins'/'cache'/'cp-assistant-local'/'codex-cross-project-engineering-assistant'/'7.4.3'

        def assert_tools_fail_closed():
            for name in ('cp-runtime.py','evolution.py'):
                result=subprocess.run(
                    [sys.executable,'-B',str(self.codex/'tools'/name),'--help'],
                    env=self.env,text=True,encoding='utf-8',capture_output=True,timeout=30,
                )
                self.assertNotEqual(0,result.returncode,result.stdout+result.stderr)
                self.assertNotIn('STALE_RUNTIME_SELECTED',result.stdout+result.stderr)

        state_path.unlink()
        assert_tools_fail_closed()
        state_path.write_bytes(state_bytes)
        state_path.write_text('{broken json',encoding='utf-8')
        assert_tools_fail_closed()
        state_path.write_bytes(state_bytes)
        shutil.rmtree(io_path(cache))
        assert_tools_fail_closed()

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
            'interface':{'displayName':'Codex Cross Project Assistant Local','theme':'user-owned'},
            'external_metadata':{'preserve':True},
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
        self.assertEqual({'name':'local-user'},current['owner'])
        self.assertEqual(
            {'displayName':'Codex Cross Project Assistant Local Package','theme':'user-owned'},
            current['interface'],
        )
        self.assertEqual({'preserve':True},current['external_metadata'])
        entry=next(item for item in current['plugins'] if item['name']=='codex-cross-project-engineering-assistant')
        self.assertEqual('AVAILABLE',entry['policy']['installation'])
        self.assertEqual('ON_INSTALL',entry['policy']['authentication'])
        self.assertEqual('Productivity',entry['category'])
        run(['verify','--scope','user','--mode','plugin'],env)

    def test_v73_invalid_marketplace_is_repaired_before_force_upgrade(self):
        self.codex.mkdir(parents=True,exist_ok=True)
        state={
            'schema_version':2,
            'package':'codex-cross-project-engineering-assistant',
            'version':'7.3.0',
            'scope':'user',
            'mode':'plugin',
            'backup':'v73-backup',
            'managed_hashes':{},
        }
        (self.codex/'cp-assistant-v6-state.json').write_text(json.dumps(state),encoding='utf-8')
        manifest=self.home/'.agents'/'plugins'/'cp-assistant-marketplace'/'.agents'/'plugins'/'marketplace.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({
            'name':'cp-assistant-local',
            'plugins':[{
                'name':'codex-cross-project-engineering-assistant',
                'source':{'source':'local','path':'./plugins/codex-cross-project-engineering-assistant'},
                'description':'v7.3 without required interface',
            }],
        }),encoding='utf-8')
        env={**self.env,'FAKE_LIST_INVALID_UNTIL_MARKETPLACE_ADD':'1'}
        run(['install','--scope','user','--mode','plugin','--force'],env)
        current=json.loads(manifest.read_text(encoding='utf-8'))
        self.assertEqual({'displayName':'Codex Cross Project Assistant Local Package'},current['interface'])
        run(['verify','--scope','user','--mode','plugin'],env)

    def test_v72_invalid_marketplace_is_repaired_before_force_upgrade(self):
        self.codex.mkdir(parents=True,exist_ok=True)
        state={
            'schema_version':2,
            'package':'codex-cross-project-engineering-assistant',
            'version':'7.2.0',
            'scope':'user',
            'mode':'plugin',
            'backup':'v72-backup',
            'managed_hashes':{},
        }
        (self.codex/'cp-assistant-v6-state.json').write_text(json.dumps(state),encoding='utf-8')
        manifest=self.home/'.agents'/'plugins'/'cp-assistant-marketplace'/'.agents'/'plugins'/'marketplace.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({
            'name':'cp-assistant-local',
            'plugins':[{
                'name':'codex-cross-project-engineering-assistant',
                'source':{'source':'local','path':'./plugins/codex-cross-project-engineering-assistant'},
                'description':'v7.2 without required interface',
            }],
        }),encoding='utf-8')
        env={**self.env,'FAKE_LIST_INVALID_UNTIL_MARKETPLACE_ADD':'1'}
        run(['install','--scope','user','--mode','plugin','--force'],env)
        current=json.loads(manifest.read_text(encoding='utf-8'))
        self.assertEqual({'displayName':'Codex Cross Project Assistant Local Package'},current['interface'])
        run(['verify','--scope','user','--mode','plugin'],env)

    def test_plugin_install_rejects_wrong_registered_version(self):
        env={**self.env,'FAKE_PLUGIN_VERSION':'6.2.0'}
        result=run(['install','--scope','user','--mode','plugin'],env,2)
        self.assertIn('version=7.4.3',result.stderr)
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
        self.assertEqual(data['target_codex'],'0.153.2')
        self.assertEqual(
            ['0.153.2','0.153.1','0.153.0','0.152.1','0.152.0','0.151.0',
             '0.150.1','0.150.0','0.149.1','0.149.0','0.148.0'],
            data['supported_codex_versions'],
        )
        self.assertIn('0.153.2',data['codex_version'])

    def test_crash_journal_recovers_and_status_is_json(self):
        crashed={**self.env, 'CP_ASSISTANT_TEST_CRASH_STAGE':'APPLYING'}
        run(['install','--scope','user','--mode','standalone'],crashed,2)
        journal=self.codex/'cp-assistant-v6-transaction.json'
        self.assertTrue(journal.is_file())
        run(['doctor','--recover'],self.env)
        self.assertFalse(journal.exists())
        status=json.loads(run(['status','--json'],self.env).stdout)
        self.assertEqual('7.4.3',status['version'])
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
        bad={**self.env, 'FAKE_CODEX_VERSION':'codex-cli 0.145.0'}
        result=run(['install','--scope','user','--mode','plugin'],bad,2)
        self.assertIn('0.148.0',result.stderr)

    def test_plugin_host_previous_stable_version_is_supported(self):
        previous={**self.env, 'FAKE_CODEX_VERSION':'codex-cli 0.152.1'}
        run(['install','--scope','user','--mode','plugin'],previous)
        run(['verify','--scope','user','--mode','plugin'],previous)

    def test_plugin_host_help_digest_drift_fails_before_account_write(self):
        drifted={**self.env, 'FAKE_HELP_DRIFT':'plugin_add'}
        result=run(['install','--scope','user','--mode','plugin'],drifted,2)
        self.assertIn('摘要与冻结兼容注册表不一致',result.stderr)
        self.assertFalse((self.codex/'cp-assistant-v6-state.json').exists())

    def test_plugin_verify_detects_supported_host_version_drift(self):
        run(['install','--scope','user','--mode','plugin'],self.env)
        drifted={**self.env, 'FAKE_CODEX_VERSION':'codex-cli 0.152.1'}
        result=run(['verify','--scope','user','--mode','plugin'],drifted,1)
        self.assertIn('HOST_DRIFT_REINSTALL_REQUIRED',result.stdout)

    def test_plugin_verify_rejects_self_consistent_but_unknown_host_binding_fields(self):
        run(['install','--scope','user','--mode','plugin'],self.env)
        state_path=self.codex/'cp-assistant-v6-state.json'
        state=json.loads(state_path.read_text(encoding='utf-8'))
        binding=state['compatibility_snapshot']['host_binding']
        binding['unknown_future_field']='must-not-be-trusted'
        state['compatibility_snapshot']['host_binding_digest']=package_manager.canonical_digest(binding)
        state_path.write_text(json.dumps(state),encoding='utf-8')
        result=run(['verify','--scope','user','--mode','plugin'],self.env,1)
        self.assertIn('COMPATIBILITY_SNAPSHOT_INVALID',result.stdout)

    def test_plugin_verify_rejects_snapshot_payload_identity_mismatch(self):
        run(['install','--scope','user','--mode','plugin'],self.env)
        state_path=self.codex/'cp-assistant-v6-state.json'
        state=json.loads(state_path.read_text(encoding='utf-8'))
        state['compatibility_snapshot']['payload_digest']='0'*64
        state_path.write_text(json.dumps(state),encoding='utf-8')
        result=run(['verify','--scope','user','--mode','plugin'],self.env,1)
        self.assertIn('COMPATIBILITY_SNAPSHOT_INVALID',result.stdout)

    def test_legacy_state_cannot_claim_host_compatibility(self):
        status=package_manager._host_compatibility_status({'schema_version':2})
        self.assertEqual({'status':'LEGACY_HOST_PROFILE_UNKNOWN','compatible':False},status)

    def test_marketplace_merge_rejects_duplicate_target_entries(self):
        existing={'plugins':[{'name':package_manager.PACKAGE},{'name':package_manager.PACKAGE}]}
        with self.assertRaisesRegex(package_manager.InstallError,'重复'):
            package_manager._merged_marketplace_manifest(existing)

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
        self.assertFalse((ROOT/'cp-assistant-v6.lock').exists())
        self.assertFalse((ROOT/'cp-assistant-v6-transaction.json').exists())
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
