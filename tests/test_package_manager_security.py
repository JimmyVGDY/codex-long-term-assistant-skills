#!/usr/bin/env python3
"""V6 installer security and scope smoke tests."""
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

class PackageManagerV6Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='cp-v6-pm-')
        self.home=Path(self.tmp.name)/'home'; self.home.mkdir()
        self.codex=self.home/'.codex'
        self.env={**os.environ,'HOME':str(self.home),'CODEX_HOME':str(self.codex),'PYTHONDONTWRITEBYTECODE':'1'}
    def tearDown(self): self.tmp.cleanup()

    def test_standalone_install_verify_uninstall(self):
        run(['install','--scope','user','--mode','standalone','--dry-run'],self.env)
        run(['install','--scope','user','--mode','standalone'],self.env)
        run(['verify','--scope','user','--mode','standalone'],self.env)
        self.assertTrue((self.home/'.agents'/'skills'/'controlled-evolution-governance'/'SKILL.md').is_file())
        hooks=json.loads((self.codex/'hooks.json').read_text(encoding='utf-8'))
        self.assertIn('PreToolUse',hooks['hooks'])
        run(['uninstall','--scope','user','--mode','standalone'],self.env)
        self.assertFalse((self.home/'.agents'/'skills'/'controlled-evolution-governance').exists())

    def test_plugin_install_verify(self):
        run(['install','--scope','user','--mode','plugin'],self.env)
        run(['verify','--scope','user','--mode','plugin'],self.env)
        p=self.home/'.agents'/'plugins'/'cp-assistant-marketplace'/'plugins'/'codex-cross-project-engineering-assistant'
        self.assertTrue((p/'.codex-plugin'/'plugin.json').is_file())
        self.assertTrue((p/'hooks'/'hooks.json').is_file())

    def test_source_and_symlink_targets_rejected(self):
        bad={**self.env,'CODEX_HOME':str(ROOT)}
        r=run(['install','--scope','user','--mode','standalone','--dry-run'],bad,2)
        self.assertIn('危险目录',r.stderr)
        self.codex.mkdir(parents=True)
        outside=self.home/'outside'; outside.mkdir()
        (self.codex/'agents').symlink_to(outside,target_is_directory=True)
        r=run(['install','--scope','user','--mode','standalone'],self.env,2)
        self.assertTrue('符号链接' in r.stderr or 'Reparse' in r.stderr)

if __name__=='__main__': unittest.main()
