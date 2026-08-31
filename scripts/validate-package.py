#!/usr/bin/env python3
from __future__ import annotations
import json,os,re,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;PLATFORM='codex';VERSION='4.1.0';errors=[]
def fail(x):errors.append(x);print('[FAIL]',x)
def run(cmd,env=None,cwd=None,expect=0):
 r=subprocess.run(cmd,env=env,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if r.returncode!=expect:fail('命令结果异常: '+' '.join(map(str,cmd))+'\n'+r.stdout+'\n'+r.stderr)
 return r
def rd(p):return p.read_text(encoding='utf-8-sig')
m=json.loads(rd(ROOT/'manifest.json'));skills={x['name'] for x in m['skills']}
if m.get('version')!=VERSION:fail('manifest version')
if len(skills)!=9:fail('Skill 数量')
for n in skills:
 p=ROOT/'skills'/n/'SKILL.md'
 if not p.is_file():fail('缺少 Skill '+n)
 if PLATFORM=='codex' and not (ROOT/'skills'/n/'agents/openai.yaml').is_file():fail('缺少 openai.yaml '+n)
for p in ROOT.rglob('*.md'):
 if len(re.findall(r'^```',rd(p),re.M))%2:fail('代码块未闭合 '+str(p.relative_to(ROOT)))
for p in ROOT.rglob('*.py'):
 try:compile(rd(p),str(p),'exec')
 except Exception as e:fail('Python 语法 '+str(p.relative_to(ROOT))+': '+str(e))
# Required V4.1 files
req=['skills/engineering-quality-delivery/scripts/execution_guard.py','skills/multi-agent-independent-review/scripts/review_packet.py','skills/multi-agent-independent-review/scripts/review_controller.py','scripts/package_manager.py','scripts/semantic-lint.py','docs/SUBAGENT_INDEPENDENT_CONTEXT.md','docs/V4_1_EXECUTION_ARCHITECTURE.md']
for x in req:
 if not (ROOT/x).is_file():fail('缺少 '+x)
# Progressive indexes should remain small
for rel in ['skills/java-backend-engineering/references/java-backend-rules.md','skills/python-backend-ai-engineering/references/python-backend-ai-rules.md','skills/data-middleware-ai-infrastructure/references/data-middleware-ai-infrastructure-rules.md','skills/engineering-quality-delivery/references/engineering-quality-delivery-workflow.md','skills/log-observability-analysis/references/log-observability-analysis-workflow.md','skills/long-running-task-memory/references/long-running-task-memory-rules.md','skills/multi-agent-independent-review/references/multi-agent-independent-review-workflow.md','skills/technical-document-writing/references/technical-document-writing-rules.md']:
 if sum(1 for _ in (ROOT/rel).open(encoding='utf-8'))>120:fail('索引过长 '+rel)
# Run unit tests
for test in [ROOT/'skills/frontend-engineering/tests/test_detect_frontend_stack.py',ROOT/'skills/engineering-quality-delivery/tests/test_execution_guard.py',ROOT/'skills/multi-agent-independent-review/tests/test_review_tools.py']:
 run([sys.executable,'-B',str(test)],env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
run([sys.executable,str(ROOT/'scripts/semantic-lint.py')])
# Package manager isolated test with dry-run, install, verify, doctor, restore
with tempfile.TemporaryDirectory(prefix='v41-install-') as td:
 home=Path(td)/'home';home.mkdir();env={**os.environ,'HOME':str(home)}
 env['CODEX_HOME']=str(home/'.codex')
 pm=ROOT/'scripts/package_manager.py'
 run([sys.executable,str(pm),'install','--dry-run'],env=env)
 run([sys.executable,str(pm),'install'],env=env)
 run([sys.executable,str(pm),'verify'],env=env)
 run([sys.executable,str(pm),'install'],env=env)
 run([sys.executable,str(pm),'verify'],env=env)
 run([sys.executable,str(pm),'doctor'],env=env)
 run([sys.executable,str(pm),'restore'],env=env)
# shell syntax
for p in ROOT.glob('scripts/*.sh'):run(['bash','-n',str(p)])
if any(ROOT.rglob('__pycache__')) or any(ROOT.rglob('*.pyc')):fail('包内 Python 缓存残留')
if errors:print('验证失败',len(errors));raise SystemExit(1)
print('验证通过。')
