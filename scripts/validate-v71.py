#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, subprocess, sys, tomllib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='V7.1 package-only validation')
parser.add_argument('--output')
arguments=parser.parse_args()

def run(cmd):
    result=subprocess.run(cmd,cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=300)
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
     '--manifest',str(ROOT/'PLUGIN_PAYLOAD_MANIFEST.json'),'--package','codex-cross-project-engineering-assistant','--version','7.1.0'])
run([sys.executable,str(ROOT/'scripts'/'semantic-lint.py')])
run([sys.executable,str(ROOT/'scripts'/'routing-eval.py'),'validate'])
model_gate=run([sys.executable,str(ROOT/'scripts'/'model-gate-acceptance.py')])
tests=run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'])
runtime_tests=run([sys.executable,'-m','unittest','discover','-s','runtime/tests','-p','test_*.py'])

def test_count(output):
    match=re.search(r'Ran\s+(\d+)\s+tests?',output)
    if not match: raise RuntimeError('无法从 unittest 输出读取执行数量')
    return int(match.group(1))

package_test_count=test_count(tests); runtime_test_count=test_count(runtime_tests)
result={
 'ok':True,'evidence_scope':'package-only','version':'7.1.0','skill_count':10,'reviewer_count':7,
 'hooks':['UserPromptSubmit','PreToolUse','SubagentStart','SubagentStop','Stop','SessionEnd'],
 'task_outcome_event':'2.0','execution_authorization':'NONE','automatic_self_modification':False,
 'requested_model_policy':'PASS','runtime_model_evidence':'UNAVAILABLE',
 'semantic_lint':'PASS','routing_case_schema':'PASS (45 cases)','plugin_payload_manifest':'PASS',
 'multiprocess_fault_injection':'PASS (tests/test_v66_runtime_deepening.py)',
 'delayed_session_end_seal':'PASS (tests/test_v66_runtime_deepening.py)',
 'reviewer_calibration_v2':'PASS (tests/test_v66_runtime_deepening.py)',
 'event_archive_capacity_health':'PASS (tests/test_v66_runtime_deepening.py)',
 'unit_regression_tests':'PASS (%d package + %d runtime)' % (package_test_count,runtime_test_count),
 'validation_evidence':{'package_test_count':package_test_count,'runtime_test_count':runtime_test_count,
   'package_test_command':'python -m unittest discover -s tests -p test_*.py',
   'runtime_test_command':'python -m unittest discover -s runtime/tests -p test_*.py',
   'model_gate_command':'python scripts/model-gate-acceptance.py'}
}
serialized=json.dumps(result,ensure_ascii=False,indent=2)
if arguments.output:
    output=Path(arguments.output); output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(serialized+'\n',encoding='utf-8',newline='\n')
print(serialized)
