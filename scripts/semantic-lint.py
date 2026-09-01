#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
errors=[]
manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
if manifest.get('version')!='7.0.0': errors.append('manifest 版本不是 7.0.0')
if manifest.get('user_skills_target')!='$HOME/.agents/skills': errors.append('账户 Skill 目标不是 $HOME/.agents/skills')
plugin=json.loads((ROOT/'.codex-plugin'/'plugin.json').read_text(encoding='utf-8'))
if plugin.get('version')!='7.0.0': errors.append('Plugin 版本不一致')
if manifest.get('default_locale')!='zh-CN' or manifest.get('supported_locales')!=['zh-CN','en']:
    errors.append('双语发行声明无效')
for previous in ('6.1.0','6.2.0','6.3.0','6.4.0','6.5.0','6.6.0','6.6.1'):
    if previous not in manifest.get('upgrade_from',[]): errors.append('缺少 %s -> V7.0.0 升级声明' % previous)
hooks=json.loads((ROOT/'hooks'/'hooks.json').read_text(encoding='utf-8')).get('hooks',{})
required={'UserPromptSubmit','PreToolUse','SubagentStart','SubagentStop','Stop','SessionEnd'}
if not required.issubset(hooks): errors.append('生命周期 Hooks 不完整')
if not (ROOT/'hooks'/'cp_hook.cmd').is_file(): errors.append('缺少 Windows Hook 启动器')
for hook_name in required:
    entries=hooks.get(hook_name) or []
    commands=[hook.get('commandWindows','') for entry in entries for hook in (entry.get('hooks') or []) if isinstance(hook,dict)]
    if not any('cp_hook.cmd' in command for command in commands): errors.append('Windows Hook 启动命令缺失: '+hook_name)
    quoted_prefix='cmd.exe /d /c ""%PLUGIN_ROOT%\\hooks\\cp_hook.cmd" '
    if not any(command.startswith(quoted_prefix) and command.endswith('"') for command in commands): errors.append('Windows Hook 必须完整引用 Plugin 启动路径: '+hook_name)
skills=[x['name'] for x in manifest.get('skills',[])]
if len(skills)!=10 or len(set(skills))!=10: errors.append('V7 应包含 10 个唯一 Skill')
primary={'backend-engineering','frontend-engineering','ai-engineering','data-middleware-infrastructure'}
if not primary.issubset(skills): errors.append('V7 四主领域 Skill 不完整')
legacy={'java-backend-engineering','python-backend-ai-engineering','data-middleware-ai-infrastructure'}
if legacy.intersection(skills): errors.append('V7 Manifest 仍包含旧领域 Skill')
for name in skills:
    p=ROOT/'skills'/name/'SKILL.md'
    if not p.is_file(): errors.append('缺少 Skill: '+name)
    elif '---' not in p.read_text(encoding='utf-8')[:20]: errors.append('Skill frontmatter 缺失: '+name)
    english=ROOT/'locales'/'en'/'skills'/name/'SKILL.md'
    if not english.is_file() or '---' not in english.read_text(encoding='utf-8')[:20]:
        errors.append('英文 Skill 入口缺失: '+name)
for name in legacy:
    if (ROOT/'skills'/name).exists() or (ROOT/'locales'/'en'/'skills'/name).exists():
        errors.append('源码残留旧 Skill: '+name)
if not (ROOT/'skills'/'controlled-evolution-governance'/'SKILL.md').is_file(): errors.append('缺少受控演进治理 Skill')
global_text=(ROOT/'global'/'AGENTS.md').read_text(encoding='utf-8')
for phrase in ('project_id + repo_fingerprint','execution_authorization=NONE','gpt-5.6-terra + high','TaskOutcomeEvent V2'):
    if phrase not in global_text: errors.append('全局规则缺少: '+phrase)
manager=(ROOT/'scripts'/'package_manager.py').read_text(encoding='utf-8')
for phrase in ('user_skills_home','plugin_marketplace_root','reject_link_ancestors','--scope','standalone','recover','transaction'):
    if phrase not in manager: errors.append('安装器缺少: '+phrase)
for release_script in ('build-release.py','lifecycle-acceptance.py','model-gate-acceptance.py','seal-worker.py','event-archive.py','release-attestation.py','verify-release.py','payload-integrity.py','validate-v70.py'):
    if not (ROOT/'scripts'/release_script).is_file(): errors.append('缺少 V7.0 发布证明脚本: '+release_script)
payload=json.loads((ROOT/'PLUGIN_PAYLOAD_MANIFEST.json').read_text(encoding='utf-8'))
if payload.get('version')!='7.0.0' or payload.get('file_count',0)<1: errors.append('Plugin payload manifest 无效')
english_reviewers=ROOT/'locales'/'en'/'custom-agents'
for reviewer in manifest.get('custom_agents',[]):
    candidate=english_reviewers/Path(reviewer['file']).name
    if not candidate.is_file():
        errors.append('英文 Reviewer 缺失: '+reviewer['name']); continue
    value=tomllib.loads(candidate.read_text(encoding='utf-8'))
    if 'model' in value or 'model_reasoning_effort' in value:
        errors.append('英文 Reviewer 写死模型: '+reviewer['name'])
for primary in ('README.md','CHANGELOG.md','global/AGENTS.md','docs/USER_GUIDE_V7.0.md',
                'docs/INSTALLATION_RECOVERY.md','docs/CODEX_CONFIG_GUIDE.md',
                'docs/releases/v7.0.0/RELEASE_NOTES.md',
                'docs/releases/v7.0.0/VALIDATION_REPORT.md',
                'docs/releases/v7.0.0/AUDIT_REPORT.md'):
    if not (ROOT/'locales'/'en'/primary).is_file(): errors.append('英文主界面缺失: '+primary)
text_extensions={'.md','.json','.toml','.yaml','.py','.ps1','.sh','.cmd'}
banned_natural_language={
    '\u7528\u6237',
    '\u8981\u6c42',
    '\u4f60',
    '\u6211\u4eec',
    'Jim'+'my',
    '\u8c01\u8c01\u8c01',
    'C:\\'+'Users\\HP',
}
excluded_brand='clau'+'de'
neutral_language_exclusions={Path('locales/en/runtime-strings.json')}
url_pattern=re.compile(r'https?://[^\s\)\]\}>"\']+',re.IGNORECASE)
for path in ROOT.rglob('*'):
    if not path.is_file() or path.suffix not in text_extensions:
        continue
    text=path.read_text(encoding='utf-8')
    if excluded_brand in path.as_posix().lower() or excluded_brand in text.lower():
        errors.append('Codex 发行命中无关品牌: '+str(path.relative_to(ROOT)))
    relative=path.relative_to(ROOT)
    if relative not in neutral_language_exclusions:
        neutral_text=url_pattern.sub('',text)
        for phrase in banned_natural_language:
            if phrase in neutral_text:
                errors.append('中性语言门禁命中 %s: %s' % (phrase.encode('unicode_escape').decode('ascii'),relative))
if errors:
    for e in errors: print('[FAIL]',e)
    raise SystemExit(1)
print('[OK] V7.0.0 语义校验通过：四主领域、双语发行、10 Skills、7 Reviewers、旧 Skill 清理、Plugin/Hooks、payload 身份、延迟封印、模型上限和受控演进边界一致')
