#!/usr/bin/env python3
"""中文：准备独立复用样例并验证实际行为；语义复用判断交给审查者。

English: Prepare independent reuse fixtures and verify behavior; reviewers judge semantic reuse.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ('backend-engineering', 'frontend-engineering', 'engineering-quality-delivery')


def catalog():
    return json.loads((ROOT / 'tests/reuse-fixtures.json').read_text(encoding='utf-8'))['cases']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(path):
    return {p.relative_to(path).as_posix(): digest(p.read_bytes())
            for p in sorted(path.rglob('*')) if p.is_file()
            and not any(part in ('.git', '__pycache__') for part in p.relative_to(path).parts)}


def prepare(case_id, output, baseline=None, locale='zh-CN'):
    output = Path(output).resolve()
    if output == ROOT or output.is_relative_to(ROOT) or output.exists():
        raise ValueError('Output must be a new directory outside the source repository')
    case = next(c for c in catalog() if c['id'] == case_id)
    output.mkdir(parents=True)
    workspace = output / 'workspace'
    workspace.mkdir()
    for relative, content in case['files'].items():
        path = workspace / relative
        if not path.resolve().is_relative_to(workspace):
            raise ValueError('Fixture path escapes workspace')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    prefix = '' if locale == 'zh-CN' else 'locales/en/'
    for name in SKILLS:
        source = prefix + 'skills/' + name
        target = workspace / '.agents/skills' / name
        if baseline:
            names = subprocess.check_output(
                ['git', 'ls-tree', '-r', '--name-only', baseline, '--', source], cwd=ROOT,
                text=True, encoding='utf-8').splitlines()
            if not names:
                raise ValueError('Baseline skill is missing: ' + source)
            for item in names:
                if '/tests/' in item or '/__pycache__/' in item:
                    continue
                path = target / Path(item).relative_to(source)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(subprocess.check_output(['git', 'show', baseline + ':' + item], cwd=ROOT))
        else:
            shutil.copytree(ROOT / source, target, ignore=shutil.ignore_patterns('__pycache__', 'tests'))
    (workspace / 'AGENTS.md').write_text(
        'Use applicable repository skills from .agents/skills. Work only in this fixture workspace. '
        'Do not read sibling workspaces or evaluator files. Preserve existing tests. '
        'Do not commit, access the network, install packages, or delegate. '
        'Use the installed Python or Node runtime for local checks.\n', encoding='utf-8')
    manifest = {'case': case_id, 'runtime': case['runtime'], 'baseline': baseline,
                'locale': locale, 'task': case['task'], 'initial_files': snapshot(workspace)}
    (output / 'input-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (output / 'prompt.txt').write_text(case['task'], encoding='utf-8')
    return {'workspace': str(workspace), 'prompt_file': str(output / 'prompt.txt'),
            'file_count': len(manifest['initial_files'])}


def verify(output):
    output = Path(output).resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        raise ValueError('Evidence must remain outside source repository')
    manifest = json.loads((output / 'input-manifest.json').read_text(encoding='utf-8'))
    workspace = output / 'workspace'
    case = next(c for c in catalog() if c['id'] == manifest['case'])
    oracles = json.loads((ROOT / 'tests/reuse-oracles.json').read_text(encoding='utf-8'))
    current = snapshot(workspace)
    protected = [name for name in manifest['initial_files']
                 if name.startswith('.agents/') or name in ('AGENTS.md', 'test_old.py', 'old.test.mjs')]
    intact = all(current.get(name) == manifest['initial_files'][name] for name in protected)
    # 中文：在独立副本加入隐藏断言，避免污染下一次回放或被执行者改写。
    # English: Add hidden assertions in a separate copy, avoiding replay contamination or agent edits.
    results = []
    with tempfile.TemporaryDirectory(prefix='cp-reuse-verify-') as temporary:
        check = Path(temporary) / 'fixture'
        shutil.copytree(workspace, check, ignore=shutil.ignore_patterns('.agents', '__pycache__', '.git'))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
        if case['runtime'] == 'node':
            node = shutil.which('node')
            if not node:
                raise RuntimeError('Node runtime unavailable')
            (check / 'acceptance.mjs').write_text(oracles[case['id']], encoding='utf-8')
            commands = [[node, 'old.test.mjs'], [node, 'acceptance.mjs']]
            commands.extend([node, '--check', str(p)] for p in sorted(check.rglob('*.mjs')))
        else:
            (check / 'acceptance.py').write_text(oracles[case['id']], encoding='utf-8')
            commands = [[sys.executable, '-m', 'unittest', 'discover', '-p', 'test_old.py'],
                        [sys.executable, 'acceptance.py']]
        for command in commands:
            started = time.monotonic()
            result = subprocess.run(command, cwd=check, env=env, capture_output=True,
                                    text=True, encoding='utf-8', errors='replace', timeout=60)
            results.append({'exit_code': result.returncode,
                            'elapsed_seconds': round(time.monotonic() - started, 3),
                            'output': (result.stdout + result.stderr)[-4000:]})
    report = {'case': case['id'], 'protected_inputs_intact': intact,
              'behavior_passed': intact and all(r['exit_code'] == 0 for r in results),
              'oracle_sha256': digest(oracles[case['id']].encode('utf-8')),
              'input_manifest_sha256': digest((output / 'input-manifest.json').read_bytes()),
              'semantic_reuse_review': 'UNKNOWN', 'checks': results,
              'changed_files': sorted(k for k in current if current[k] != manifest['initial_files'].get(k)),
              'deleted_files': sorted(set(manifest['initial_files']) - set(current)),
              'final_files': current}
    serialized = json.dumps(report, indent=2).encode('utf-8')
    immutable = output / ('behavior-result-' + digest(serialized) + '.json')
    if not immutable.exists():
        with immutable.open('xb') as handle:
            handle.write(serialized)
    (output / 'behavior-result.json').write_bytes(serialized)
    return report


def main():
    parser = argparse.ArgumentParser(description='Prepare or verify isolated component reuse fixtures')
    sub = parser.add_subparsers(dest='command', required=True)
    stage = sub.add_parser('prepare')
    stage.add_argument('--case', required=True, choices=[c['id'] for c in catalog()])
    stage.add_argument('--output', required=True)
    stage.add_argument('--baseline')
    stage.add_argument('--locale', choices=('zh-CN', 'en'), default='zh-CN')
    check = sub.add_parser('verify')
    check.add_argument('--output', required=True)
    args = parser.parse_args()
    result = (prepare(args.case, args.output, args.baseline, args.locale)
              if args.command == 'prepare' else verify(args.output))
    summary = (result if args.command == 'prepare' else
               {key: result[key] for key in ('case', 'protected_inputs_intact', 'behavior_passed',
                                            'semantic_reuse_review', 'changed_files', 'deleted_files')})
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if args.command == 'verify' and not result['behavior_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
