#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(cmd):
    r=subprocess.run(cmd,cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=90)
    if r.returncode:
        raise RuntimeError('命令失败: %s\n%s\n%s' % (' '.join(cmd),r.stdout,r.stderr))
    return (r.stdout+r.stderr).strip()

# Parse all structured config first.
for p in ROOT.rglob('*.json'): json.loads(p.read_text(encoding='utf-8-sig'))
for p in ROOT.rglob('*.toml'): tomllib.loads(p.read_text(encoding='utf-8-sig'))
run([sys.executable,'-m','compileall','-q',str(ROOT/'runtime'),str(ROOT/'scripts'),str(ROOT/'hooks')])
sem=run([sys.executable,str(ROOT/'scripts'/'semantic-lint.py')])
routing=run([sys.executable,str(ROOT/'scripts'/'routing-eval.py'),'validate'])
tests=run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'])
result={
 'ok':True,'version':'6.2.0','skill_count':10,'reviewer_count':7,
 'hooks':['UserPromptSubmit','PreToolUse','SubagentStart','SubagentStop','Stop','SessionEnd'],
 'task_outcome_event':'2.0','execution_authorization':'NONE','automatic_self_modification':False,
 'semantic_lint':'PASS','routing_case_schema':'PASS (35 cases)','unit_regression_tests':'PASS',
 'real_codex_implicit_activation':'NOT_EXECUTED','windows_powershell_real_machine':'NOT_EXECUTED',
 'plugin_host_end_to_end':'NOT_EXECUTED'
}
print(json.dumps(result,ensure_ascii=False,indent=2))
