#!/usr/bin/env python3
"""V6.2 installer security and scope smoke tests."""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile, unittest
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


class PackageManagerV62Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='cp-v62-pm-')
        self.home=Path(self.tmp.name)/'home'; self.home.mkdir()
        self.codex=self.home/'.codex'
        self.bin=Path(self.tmp.name)/'bin'; self.bin.mkdir()
        fake=self.bin/'fake_codex.py'
        fake.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
home=Path(os.environ.get('CODEX_HOME') or '.')
state=home/'fake-codex-plugin-state.json'
args=sys.argv[1:]
if args == ['--version']:
    print('codex-cli 0.150.1'); raise SystemExit(0)
if args[:3] == ['plugin','marketplace','add']:
    print('marketplace added'); raise SystemExit(0)
if args[:3] == ['plugin','marketplace','remove']:
    print('marketplace removed'); raise SystemExit(0)
if args[:2] == ['plugin','add']:
    home.mkdir(parents=True,exist_ok=True)
    state.write_text(json.dumps({'installed':True}),encoding='utf-8')
    print('plugin added'); raise SystemExit(0)
if args[:2] == ['plugin','remove']:
    state.unlink(missing_ok=True)
    print('plugin removed'); raise SystemExit(0)
if args == ['plugin','list','--json']:
    installed=[]
    if state.exists():
        installed=[{'pluginId':'codex-cross-project-engineering-assistant@cp-assistant-local','name':'codex-cross-project-engineering-assistant','marketplaceName':'cp-assistant-local','version':'6.2.0','installed':True,'enabled':True}]
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
        # First uninstall restores the first V6.2 installation; the second
        # returns the isolated HOME to its original empty state.
        run(['uninstall','--scope','user','--mode','plugin'],env)
        run(['uninstall','--scope','user','--mode','plugin'],env)
        self.assertFalse(io_path(long_home/'.agents'/'plugins'/'cp-assistant-marketplace').exists())

if __name__=='__main__':
    unittest.main()
