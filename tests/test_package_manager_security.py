#!/usr/bin/env python3
"""V6.1 installer security and scope smoke tests."""
from __future__ import annotations
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANAGER=ROOT/'scripts'/'package_manager.py'


def run(args, env, expected=0):
    r=subprocess.run([sys.executable,'-B',str(MANAGER),*args],env=env,text=True,capture_output=True,timeout=30)
    if r.returncode!=expected:
        raise AssertionError(f'rc={r.returncode}, expected={expected}\nstdout={r.stdout}\nstderr={r.stderr}')
    return r


class PackageManagerV61Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='cp-v61-pm-')
        self.home=Path(self.tmp.name)/'home'; self.home.mkdir()
        self.codex=self.home/'.codex'
        self.bin=Path(self.tmp.name)/'bin'; self.bin.mkdir()
        fake=self.bin/'codex'
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
        installed=[{'pluginId':'codex-cross-project-engineering-assistant@cp-assistant-local','name':'codex-cross-project-engineering-assistant','marketplaceName':'cp-assistant-local','version':'6.1.0','installed':True,'enabled':True}]
    print(json.dumps({'installed':installed,'available':[]})); raise SystemExit(0)
print('unsupported fake codex args: '+repr(args),file=sys.stderr); raise SystemExit(2)
""",encoding='utf-8')
        fake.chmod(0o755)
        self.env={
            **os.environ,
            'HOME':str(self.home),
            'CODEX_HOME':str(self.codex),
            'PYTHONDONTWRITEBYTECODE':'1',
            'PATH':str(self.bin)+os.pathsep+os.environ.get('PATH','')
        }

    def tearDown(self):
        self.tmp.cleanup()

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
        (self.codex/'agents').symlink_to(outside,target_is_directory=True)
        r=run(['install','--scope','user','--mode','standalone'],self.env,2)
        self.assertTrue('符号链接' in r.stderr or 'Reparse' in r.stderr)

if __name__=='__main__':
    unittest.main()
