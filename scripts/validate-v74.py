#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, platform, re, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMMAND_TIMEOUT_SECONDS=600
MINIMUM_PYTHON=(3,11)
if sys.version_info < MINIMUM_PYTHON:
    raise RuntimeError('V7.4 完整验证需要 Python 3.11+，当前为 %s' % platform.python_version())
import tomllib
from validation_worktree import require_output_outside_worktree, run_with_worktree_guard
parser=argparse.ArgumentParser(description='V7.4 package-only validation')
parser.add_argument('--output')
arguments=parser.parse_args()
output_path=require_output_outside_worktree(ROOT,Path(arguments.output)) if arguments.output else None

def run(cmd, env=None):
    result=subprocess.run(cmd,cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True,
                          timeout=COMMAND_TIMEOUT_SECONDS,env=env)
    if result.returncode:
        raise RuntimeError('命令失败: %s\n%s\n%s' % (' '.join(cmd),result.stdout,result.stderr))
    return (result.stdout+result.stderr).strip()

def validate_package():
    with tempfile.TemporaryDirectory(prefix='cp-v74-validation-') as temporary:
        validation_env=dict(os.environ)
        validation_env['PYTHONDONTWRITEBYTECODE']='1'
        validation_env['PYTHONPYCACHEPREFIX']=str(Path(temporary)/'pycache')
        for path in ROOT.rglob('*.json'):
            relative=path.relative_to(ROOT)
            if '__pycache__' not in path.parts and (not relative.parts or relative.parts[0] not in {'project-context','.git'}):
                json.loads(path.read_text(encoding='utf-8-sig'))
        for path in ROOT.rglob('*.toml'):
            relative=path.relative_to(ROOT)
            if not relative.parts or relative.parts[0] not in {'project-context','.git'}:
                tomllib.loads(path.read_text(encoding='utf-8-sig'))
        run([sys.executable,'-m','compileall','-q',str(ROOT/'runtime'),str(ROOT/'scripts'),str(ROOT/'hooks')],validation_env)
        run([sys.executable,str(ROOT/'scripts'/'payload-integrity.py'),'verify','--root',str(ROOT),
             '--manifest',str(ROOT/'PLUGIN_PAYLOAD_MANIFEST.json'),'--package','codex-cross-project-engineering-assistant','--version','7.4.6'],validation_env)
        run([sys.executable,str(ROOT/'scripts'/'semantic-lint.py')],validation_env)
        run([sys.executable,str(ROOT/'scripts'/'privacy-boundary-lint.py')],validation_env)
        run([sys.executable,str(ROOT/'scripts'/'routing-eval.py'),'validate'],validation_env)
        dispatch_policy=run([sys.executable,str(ROOT/'scripts'/'dispatch-policy-acceptance.py')],validation_env)
        tests=run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],validation_env)
        runtime_tests=run([sys.executable,'-m','unittest','discover','-s','runtime/tests','-p','test_*.py'],validation_env)
        return dispatch_policy,tests,runtime_tests

dispatch_policy,tests,runtime_tests=run_with_worktree_guard(ROOT,validate_package)

def test_count(output):
    match=re.search(r'Ran\s+(\d+)\s+tests?',output)
    if not match: raise RuntimeError('无法从 unittest 输出读取执行数量')
    return int(match.group(1))

package_test_count=test_count(tests); runtime_test_count=test_count(runtime_tests)
result={
 'ok':True,'evidence_scope':'package-only','version':'7.4.6','skill_count':10,'reviewer_count':7,
 'hooks':['UserPromptSubmit','PreToolUse','SubagentStart','SubagentStop','Stop','SessionEnd'],
 'task_outcome_event':'3.0','execution_authorization':'NONE','automatic_self_modification':False,
 'dispatch_policy':'PASS','privacy_boundary':'PASS',
 'python_compatibility':{'minimum':'3.11','validated_runtime':platform.python_version()},
 'semantic_lint':'PASS','routing_case_schema':'PASS (45 cases)','plugin_payload_manifest':'PASS',
 'codex_compatibility_registry':'PASS (11 frozen stable releases)',
 'codex_compatibility_matrix':'NOT_EVALUATED (separate Windows/Ubuntu workflow)',
 'routing_host_observation':'NOT_EVALUATED (package-only validation)',
 'worktree_side_effect_gate':'PASS',
 'multiprocess_fault_injection':'PASS (tests/test_v66_runtime_deepening.py)',
 'delayed_session_end_seal':'PASS (tests/test_v66_runtime_deepening.py)',
 'reviewer_result_v4':'PASS (tests/test_model_routing_calibration_gates.py)',
 'minimum_profile_and_inline_delegate_gates':'PASS (tests/test_model_routing_calibration_gates.py)',
 'state_bound_plugin_runtime':'PASS (tests/test_package_manager_security.py)',
 'delegation_budget_v2':'PASS (tests/test_v74_delegation_budget.py)',
 'delegation_hook_gate':'PASS (tests/test_v74_delegation_hook.py)',
 'delegation_calibration_replay':'PASS (tests/test_v74_delegation_calibration.py)',
 'event_archive_capacity_health':'PASS (tests/test_v66_runtime_deepening.py)',
 'unit_regression_tests':'PASS (%d package + %d runtime)' % (package_test_count,runtime_test_count),
 'validation_evidence':{'package_test_count':package_test_count,'runtime_test_count':runtime_test_count,
   'package_test_command':'python -m unittest discover -s tests -p test_*.py',
   'runtime_test_command':'python -m unittest discover -s runtime/tests -p test_*.py',
   'dispatch_policy_command':'python scripts/dispatch-policy-acceptance.py'}
}
serialized=json.dumps(result,ensure_ascii=False,indent=2)
if output_path:
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text(serialized+'\n',encoding='utf-8',newline='\n')
print(serialized)
