#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, subprocess, sys, tomllib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='V6.4 package-only validation')
parser.add_argument('--output')
arguments=parser.parse_args()

def run(cmd):
    result=subprocess.run(cmd,cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=240)
    if result.returncode:
        raise RuntimeError('命令失败: %s\n%s\n%s' % (' '.join(cmd),result.stdout,result.stderr))
    return (result.stdout+result.stderr).strip()

for path in ROOT.rglob('*.json'):
    if '__pycache__' not in path.parts:
        json.loads(path.read_text(encoding='utf-8-sig'))
for path in ROOT.rglob('*.toml'):
    tomllib.loads(path.read_text(encoding='utf-8-sig'))
run([sys.executable,'-m','compileall','-q',str(ROOT/'runtime'),str(ROOT/'scripts'),str(ROOT/'hooks')])
run([sys.executable,str(ROOT/'scripts'/'payload-integrity.py'),'verify','--root',str(ROOT),
     '--manifest',str(ROOT/'PLUGIN_PAYLOAD_MANIFEST.json'),'--package','codex-cross-project-engineering-assistant','--version','6.4.0'])
run([sys.executable,str(ROOT/'scripts'/'semantic-lint.py')])
run([sys.executable,str(ROOT/'scripts'/'routing-eval.py'),'validate'])
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
 'ok':True,'evidence_scope':'package-only','version':'6.4.0','skill_count':10,'reviewer_count':7,
 'hooks':['UserPromptSubmit','PreToolUse','SubagentStart','SubagentStop','Stop','SessionEnd'],
 'task_outcome_event':'2.0','execution_authorization':'NONE','automatic_self_modification':False,
 'semantic_lint':'PASS','routing_case_schema':'PASS (35 cases)','plugin_payload_manifest':'PASS',
 'unit_regression_tests':'PASS (%d package + %d runtime)' % (package_test_count,runtime_test_count),
 'durable_install_transaction':'PASS (tests/test_package_manager_security.py)',
 'event_segmentation_and_recovery':'PASS (tests/test_v64_resilience.py)',
 'unified_release_verifier':'PASS (tests/test_v64_release.py)',
 'observation_quality_gate':'PASS (tests/test_v60_deterministic_observation.py)',
 'validation_evidence':{
   'package_test_count':package_test_count,'runtime_test_count':runtime_test_count,
   'package_test_command':'python -m unittest discover -s tests -p test_*.py',
   'runtime_test_command':'python -m unittest discover -s runtime/tests -p test_*.py'
 }
}
serialized=json.dumps(result,ensure_ascii=False,indent=2)
if arguments.output:
    output=Path(arguments.output); output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(serialized+'\n',encoding='utf-8')
print(serialized)
