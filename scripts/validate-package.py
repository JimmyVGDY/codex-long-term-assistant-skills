#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
PLATFORM="codex";VERSION="4.0.0";OLD="vue-frontend-engineering";NEW="frontend-engineering"
SKILLS={'python-backend-ai-engineering', 'technical-document-writing', 'log-observability-analysis', 'frontend-engineering', 'long-running-task-memory', 'java-backend-engineering', 'engineering-quality-delivery', 'multi-agent-independent-review', 'data-middleware-ai-infrastructure'};AGENT_FILES={'cp-review-performance-resources.toml', 'cp-review-compatibility-regression.toml', 'cp-review-functional-business.toml', 'cp-review-data-contract.toml', 'cp-review-test-delivery.toml', 'cp-review-state-concurrency.toml', 'cp-review-security-access.toml'}
REFS={"framework-detection-matrix.md","frontend-core-rules.md","frontend-security-runtime-rules.md","frontend-quality-performance-rules.md","vue-nuxt-rules.md","react-next-remix-rules.md","angular-rules.md","svelte-sveltekit-rules.md","other-modern-frameworks-rules.md","legacy-frontend-rules.md","microfrontend-monorepo-rules.md"}
ASSETS={"FRONTEND_STACK_PROFILE.template.md","FRONTEND_REVIEW_REPORT.template.md","FRONTEND_VALIDATION_MATRIX.template.md"}
errors=[]
def fail(x): errors.append(x);print('[FAIL]',x)
def ok(x): print('[OK]',x)
def rd(p): return p.read_text(encoding='utf-8-sig')
def run(cmd,env=None,cwd=None):
 r=subprocess.run(cmd,env=env,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if r.returncode: fail('命令失败: '+' '.join(map(str,cmd))+'\n'+r.stdout+'\n'+r.stderr)
 return r
m=json.loads(rd(ROOT/'manifest.json'))
if m.get('version')!=VERSION:fail('manifest version')
if {x['name'] for x in m.get('skills',[])}!=SKILLS:fail('Skill 清单')
if OLD not in m.get('deprecated_skills',[]):fail('deprecated_skills')
if (ROOT/'skills'/OLD).exists():fail('包内残留旧 Skill')
for n in SKILLS:
 f=ROOT/'skills'/n/'SKILL.md'
 if not f.is_file():fail('缺少 '+str(f));continue
 t=rd(f);mm=re.search(r'(?m)^name:\s*([^\n]+)',t)
 if not mm or mm.group(1).strip()!=n:fail('Skill name 不一致 '+n)
 if not re.search(r'(?m)^description:',t):fail('缺少 description '+n)
 if PLATFORM=='codex' and not (ROOT/'skills'/n/'agents/openai.yaml').is_file():fail('缺少 openai.yaml '+n)
fr=ROOT/'skills'/NEW
if {p.name for p in (fr/'references').glob('*.md')}!=REFS:fail('前端 references 不完整')
if {p.name for p in (fr/'assets/templates').glob('*.md')}!=ASSETS:fail('前端模板不完整')
for p in [fr/'scripts/detect_frontend_stack.py',fr/'tests/test_detect_frontend_stack.py']:
 try: compile(rd(p), str(p), 'exec')
 except Exception as e: fail('Python 语法: '+str(e))
test_env=os.environ.copy();test_env['PYTHONDONTWRITEBYTECODE']='1'
run([sys.executable,'-B',str(fr/'tests/test_detect_frontend_stack.py')],env=test_env)
if any(ROOT.rglob('__pycache__')) or any(ROOT.rglob('*.pyc')): fail('包内包含 Python 缓存文件')
# markdown fences and stale explicit calls
for p in ROOT.rglob('*.md'):
 t=rd(p)
 if len(re.findall(r'^```',t,re.M))%2:fail('代码块未闭合 '+str(p.relative_to(ROOT)))
 if OLD in t and p.name not in {'FRONTEND_SKILL_MIGRATION.md','FRONTEND_SKILL_V4_DESIGN.md','CHANGELOG.md','VALIDATION_REPORT.md','README.md'}:fail('非迁移文档残留旧名称 '+str(p.relative_to(ROOT)))
# routing
cases=json.loads(rd(ROOT/'tests/skill-routing-cases.json'))['cases']
if len(cases)<28:fail('路由用例不足')
for c in cases:
 vals=set(c.get('required',[])+c.get('optional',[])+c.get('forbidden',[]))
 if OLD in vals:fail('路由用例残留旧 Skill '+c['id'])
if not any(c['id']=='node-backend-not-frontend' and NEW in c['forbidden'] for c in cases):fail('缺少 Node 后端负向用例')
# shell syntax
for p in ROOT.glob('scripts/*.sh'): run(['bash','-n',str(p)])
# file-level agent check
for name in AGENT_FILES:
 folder='custom-agents'
 if not (ROOT/folder/name).is_file():fail('缺少 Reviewer '+name)
# isolated user install/upgrade/uninstall with old skill and third-party preservation
with tempfile.TemporaryDirectory(prefix='v4-install-') as td:
 home=Path(td)/'home';home.mkdir();env=os.environ.copy();env['HOME']=str(home)
 ch=home/'.codex';env['CODEX_HOME']=str(ch);sh=home/'.agents/skills';agents=ch/'agents'
 sh.mkdir(parents=True);agents.mkdir(parents=True)
 (sh/OLD).mkdir();(sh/OLD/'SKILL.md').write_text('old',encoding='utf-8')
 (sh/'third-party').mkdir();(sh/'third-party'/'SKILL.md').write_text('third',encoding='utf-8')
 run(['bash',str(ROOT/'scripts/install-user.sh'),'all'],env=env)
 run(['bash',str(ROOT/'scripts/verify-user-install.sh')],env=env)
 if (sh/OLD).exists():fail('升级未清理旧 Skill')
 if not (sh/NEW/'SKILL.md').is_file():fail('升级未安装新 Skill')
 if not (sh/'third-party'/'SKILL.md').is_file():fail('误删第三方 Skill')
 run(['bash',str(ROOT/'scripts/install-user.sh'),'all'],env=env)
 run(['bash',str(ROOT/'scripts/uninstall-user.sh'),'all'],env=env)
 if not (sh/'third-party').exists():fail('卸载误删第三方 Skill')
# repo install
with tempfile.TemporaryDirectory(prefix='v4-repo-') as td:
 repo=Path(td)/'repo';(repo/('.agents/skills')/OLD).mkdir(parents=True);(repo/('.agents/skills')/OLD/'SKILL.md').write_text('old',encoding='utf-8')
 run(['bash',str(ROOT/'scripts/install-repo-skills.sh'),str(repo)])
 if (repo/('.agents/skills')/OLD).exists():fail('仓库升级未清理旧 Skill')
 if not (repo/('.agents/skills')/NEW/'SKILL.md').is_file():fail('仓库未安装新 Skill')
print()
if errors: print('验证失败',len(errors));raise SystemExit(1)
print('验证通过。')
