#!/usr/bin/env python3
from pathlib import Path
import json, subprocess, sys, tempfile
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/execution_guard.py'
def run(*a,cwd=None,ok=True):
 r=subprocess.run([sys.executable,str(SCRIPT),*a],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if ok and r.returncode: raise AssertionError(r.stdout+r.stderr)
 if not ok and r.returncode==0: raise AssertionError('expected failure')
 return r
with tempfile.TemporaryDirectory() as td:
 repo=Path(td)/'repo';state=Path(td)/'state';repo.mkdir();subprocess.run(['git','init','-q'],cwd=repo,check=True);subprocess.run(['git','config','user.email','a@b.c'],cwd=repo,check=True);subprocess.run(['git','config','user.name','t'],cwd=repo,check=True);(repo/'a.txt').write_text('a\n');subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','init'],cwd=repo,check=True)
 run('init','--state-dir',str(state),'--task-id','T1','--profile','STANDARD','--repo-path',str(repo))
 run('transition','--state-dir',str(state),'--to','PLAN');run('transition','--state-dir',str(state),'--to','IMPLEMENT');(repo/'a.txt').write_text('b\n');run('transition','--state-dir',str(state),'--to','VALIDATE')
 run('record-validation','--state-dir',str(state),'--name','unit','--status','valid','--command-or-packet','test')
 run('gate','--state-dir',str(state),'--name','targeted_validation');run('gate','--state-dir',str(state),'--name','git_diff_review')
 run('validate','--state-dir',str(state),'--require-gates')
 (repo/'a.txt').write_text('c\n');run('validate','--state-dir',str(state))
 data=json.loads((state/'execution-state.json').read_text());assert data['evidence']['validations']['unit']['status']=='stale'
 (repo/'new.py').write_text('first\n');run('record-validation','--state-dir',str(state),'--name','untracked','--status','valid','--command-or-packet','test')
 (repo/'new.py').write_text('second\n');run('validate','--state-dir',str(state))
 data=json.loads((state/'execution-state.json').read_text());assert data['evidence']['validations']['untracked']['status']=='stale'
print('execution_guard tests passed')
