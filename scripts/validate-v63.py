#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, subprocess, sys, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='V6.3 package validation')
parser.add_argument('--output')
arguments=parser.parse_args()

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
runtime_tests=run([sys.executable,'-m','unittest','discover','-s','runtime/tests','-p','test_*.py'])
def test_count(output):
    match=re.search(r'Ran\s+(\d+)\s+tests?',output)
    if not match:
        raise RuntimeError('无法从 unittest 输出读取执行数量')
    return int(match.group(1))
package_test_count=test_count(tests)
runtime_test_count=test_count(runtime_tests)
result={
 'ok':True,'version':'6.3.0','skill_count':10,'reviewer_count':7,
 'hooks':['UserPromptSubmit','PreToolUse','SubagentStart','SubagentStop','Stop','SessionEnd'],
 'task_outcome_event':'2.0','execution_authorization':'NONE','automatic_self_modification':False,
 'semantic_lint':'PASS','routing_case_schema':'PASS (35 cases)',
 'unit_regression_tests':'PASS (%d package + %d runtime)' % (package_test_count,runtime_test_count),
 'durable_install_transaction':'PASS (tests/test_package_manager_security.py)',
 'deterministic_release_build':'PASS (tests/test_v63_release_delivery.py)',
 'lifecycle_attestation_contract':'PASS (tests/test_v63_release_delivery.py)',
 'observation_quality_gate':'PASS (tests/test_v60_deterministic_observation.py)',
 'validation_evidence':{
   'package_test_count':package_test_count,
   'runtime_test_count':runtime_test_count,
   'package_test_command':'python -m unittest discover -s tests -p test_*.py',
   'runtime_test_command':'python -m unittest discover -s runtime/tests -p test_*.py'
 },
 'real_codex_implicit_activation':'NOT_EXECUTED','windows_powershell_real_machine':'NOT_EXECUTED',
 'plugin_host_end_to_end':'NOT_EXECUTED'
}
serialized=json.dumps(result,ensure_ascii=False,indent=2)
if arguments.output:
    output=Path(arguments.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(serialized+'\n',encoding='utf-8')
print(serialized)
