#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
errors=[]
manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
if manifest.get('version')!='6.0.0': errors.append('manifest 版本不是 6.0.0')
if manifest.get('user_skills_target')!='$HOME/.agents/skills': errors.append('用户 Skill 目标不是 $HOME/.agents/skills')
plugin=json.loads((ROOT/'.codex-plugin'/'plugin.json').read_text(encoding='utf-8'))
if plugin.get('version')!='6.0.0': errors.append('Plugin 版本不一致')
hooks=json.loads((ROOT/'hooks'/'hooks.json').read_text(encoding='utf-8')).get('hooks',{})
required={'UserPromptSubmit','PreToolUse','SubagentStart','SubagentStop','Stop','SessionEnd'}
if not required.issubset(hooks): errors.append('生命周期 Hooks 不完整')
skills=[x['name'] for x in manifest.get('skills',[])]
if len(skills)!=10 or len(set(skills))!=10: errors.append('V6 应包含 10 个唯一 Skill')
for name in skills:
    p=ROOT/'skills'/name/'SKILL.md'
    if not p.is_file(): errors.append('缺少 Skill: '+name)
    elif '---' not in p.read_text(encoding='utf-8')[:20]: errors.append('Skill frontmatter 缺失: '+name)
if not (ROOT/'skills'/'controlled-evolution-governance'/'SKILL.md').is_file(): errors.append('缺少受控演进治理 Skill')
global_text=(ROOT/'global'/'AGENTS.md').read_text(encoding='utf-8')
for phrase in ('project_id + repo_fingerprint','execution_authorization=NONE','gpt-5.6-terra + high','TaskOutcomeEvent V2'):
    if phrase not in global_text: errors.append('全局规则缺少: '+phrase)
manager=(ROOT/'scripts'/'package_manager.py').read_text(encoding='utf-8')
for phrase in ('user_skills_home','plugin_marketplace_root','reject_link_ancestors','--scope','standalone'):
    if phrase not in manager: errors.append('安装器缺少: '+phrase)
if errors:
    for e in errors: print('[FAIL]',e)
    raise SystemExit(1)
print('[OK] V6 语义校验通过：10 Skills、Plugin/Hooks、官方用户 Skill 目录、模型上限和受控演进边界一致')
