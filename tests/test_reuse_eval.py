"""中文：验证样例隔离和真实行为判定，避免将静态检查误报为复用通过。

English: Verify fixture isolation and behavior checks without claiming semantic reuse from static checks.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('reuse_eval', ROOT / 'scripts/reuse-eval.py')
EVAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVAL)


class ReuseEvaluationTests(unittest.TestCase):
    def test_prepare_keeps_oracles_outside_workspace_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'run'
            EVAL.prepare('local-fix', output)
            workspace = output / 'workspace'
            self.assertFalse((workspace / 'acceptance.py').exists())
            initial = EVAL.snapshot(workspace)
            with self.assertRaises(ValueError):
                EVAL.prepare('local-fix', output)
            self.assertEqual(initial, EVAL.snapshot(workspace))

    def test_behavior_failure_then_repair_without_semantic_overclaim(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'run'
            EVAL.prepare('local-fix', output)
            self.assertFalse(EVAL.verify(output)['behavior_passed'])
            source = output / 'workspace/pagination.py'
            source.write_text(source.read_text().replace('max(1,', 'max(0,'), encoding='utf-8')
            result = EVAL.verify(output)
            self.assertTrue(result['behavior_passed'])
            self.assertEqual(result['semantic_reuse_review'], 'UNKNOWN')
            self.assertEqual(result['changed_files'], ['pagination.py'])
            self.assertFalse((output / 'workspace/acceptance.py').exists())
            saved = [json.loads(p.read_text()) for p in output.glob('behavior-result-*.json')]
            self.assertTrue(any(not r['behavior_passed'] for r in saved))
            self.assertTrue(any(r['behavior_passed'] for r in saved))
            for path in output.glob('behavior-result-*.json'):
                self.assertEqual(path.stem, 'behavior-result-' + EVAL.digest(path.read_bytes()))

    def test_shadowed_policy_cannot_pass_on_output_alone(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'run'
            EVAL.prepare('shared-extraction', output)
            for name in ('cart.py', 'quote.py'):
                source = output / 'workspace' / name
                original = source.read_text()
                source.write_text(original + '\n' + original.replace('6000', '5000'), encoding='utf-8')
            result = EVAL.verify(output)
            self.assertEqual(result['checks'][0]['exit_code'], 0)
            self.assertFalse(result['behavior_passed'])

    def test_changed_old_tests_cannot_pass_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'run'
            EVAL.prepare('local-fix', output)
            source = output / 'workspace/pagination.py'
            source.write_text(source.read_text().replace('max(1,', 'max(0,'), encoding='utf-8')
            (output / 'workspace/test_old.py').write_text('', encoding='utf-8')
            result = EVAL.verify(output)
            self.assertFalse(result['behavior_passed'])
            self.assertFalse(result['protected_inputs_intact'])

    def test_fixture_and_oracle_cases_match(self):
        cases = EVAL.catalog()
        oracles = json.loads((ROOT / 'tests/reuse-oracles.json').read_text())
        self.assertEqual(len({c['id'] for c in cases}), len(cases))
        self.assertEqual({c['id'] for c in cases}, set(oracles))
        for case in cases:
            if case['runtime'] == 'python':
                for name, text in case['files'].items():
                    if name.endswith('.py'):
                        compile(text, name, 'exec')
                compile(oracles[case['id']], case['id'], 'exec')

    def test_original_contracts_pass_but_unsolved_goals_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            for case in EVAL.catalog():
                with self.subTest(case=case['id']):
                    output = Path(temporary) / case['id']
                    EVAL.prepare(case['id'], output)
                    result = EVAL.verify(output)
                    self.assertEqual(result['checks'][0]['exit_code'], 0)
                    self.assertNotEqual(result['checks'][1]['exit_code'], 0)
                    self.assertFalse(result['behavior_passed'])


if __name__ == '__main__':
    unittest.main()
