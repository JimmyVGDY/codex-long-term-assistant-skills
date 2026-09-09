"""中文：变更后维护、语义证据失效和JSON入口一致性。 English: Post-change maintenance, semantic evidence invalidation, and consistent JSON boundaries."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
from cp_runtime import capability_cli, capability_index as index
from cp_runtime.capability_store import CapabilityError


class CapabilityMaintenanceTests(unittest.TestCase):
    setUp = fixtures.CapabilityStoreTests.setUp
    tearDown = fixtures.CapabilityStoreTests.tearDown

    def _repeat_is_noop(self):
        before = self.store.current.read_bytes()
        with patch('cp_runtime.capability_store.atomic_write_bytes', side_effect=AssertionError('Unexpected write')):
            result = index.scan(self.store, ['app.py'])
        self.assertFalse(result['changed'])
        self.assertEqual(before, self.store.current.read_bytes())

    def test_changed_source_rescan_is_current_and_repeating_is_noop(self):
        index.scan(self.store, ['app.py'])
        (self.repo / 'app.py').write_text('def public():\n    return 2\n', encoding='utf-8')
        index.scan(self.store, ['app.py'])
        self.assertEqual('matched', self.store.read()['entries'][0]['freshness'])
        self.assertFalse(index.query(self.store, 'public')['candidates'][0]['current_check']['semantic_reuse_approved'])
        self._repeat_is_noop()

    def test_changed_context_rescan_repeating_is_noop(self):
        index.scan(self.store, ['app.py'])
        (self.repo / 'pyproject.toml').write_text('[project]\nname="example"\n', encoding='utf-8')
        index.scan(self.store, ['app.py'])
        self._repeat_is_noop()

    def test_rescan_refreshes_declaration_kind_and_preserves_manual_context(self):
        cases = [
            ('app.py', 'def Public():\n    return 1\n', 'class Public:\n    pass\n', 'function', 'class'),
            ('view.tsx', 'export const Public = () => null;\n', 'export function Public() { return null; }\n', 'component', 'function'),
        ]
        for path, before, after, old_kind, new_kind in cases:
            with self.subTest(path=path):
                source = self.repo / path
                source.write_text(before, encoding='utf-8')
                index.scan(self.store, [path])
                record = self.store.read()
                entry = next(e for e in record['entries'] if e['path'] == path)
                self.assertEqual(old_kind, entry['kind'])
                entry['summary'] = '公开入口的已登记职责'
                entry['boundaries'] = ['仅限当前模块']
                entry['verification']['evidence'] = ['old-contract-check']
                index.register(self.store, entry, record['revision'])
                source.write_text(after, encoding='utf-8')
                index.scan(self.store, [path])
                updated = next(e for e in self.store.read()['entries'] if e['id'] == entry['id'])
                self.assertEqual(new_kind, updated['kind'])
                self.assertEqual(entry['summary'], updated['summary'])
                self.assertEqual(entry['boundaries'], updated['boundaries'])
                self.assertEqual([], updated['verification']['evidence'])
                self.assertFalse(index.query(self.store, 'Public')['candidates'][0]['current_check']['semantic_reuse_approved'])
                before_repeat = self.store.current.read_bytes()
                with patch('cp_runtime.capability_store.atomic_write_bytes', side_effect=AssertionError('Unexpected write')):
                    self.assertFalse(index.scan(self.store, [path])['changed'])
                self.assertEqual(before_repeat, self.store.current.read_bytes())

    def test_rescan_preserves_explicit_service_or_adapter_role(self):
        for role in ('service', 'adapter'):
            with self.subTest(role=role):
                source = self.repo / 'app.py'
                source.write_text('def public():\n    return 1\n', encoding='utf-8')
                index.scan(self.store, ['app.py'])
                record = self.store.read()
                entry = record['entries'][0]
                entry['kind'] = role
                index.register(self.store, entry, record['revision'])
                source.write_text('class public:\n    pass\n', encoding='utf-8')
                index.scan(self.store, ['app.py'])
                self.assertEqual(role, self.store.read()['entries'][0]['kind'])

    def test_changed_source_invalidates_old_semantic_evidence(self):
        index.scan(self.store, ['app.py'])
        record = self.store.read()
        entry = record['entries'][0]
        entry['verification']['scope'] = '已核验旧输入返回值'
        entry['verification']['evidence'] = ['test-old-contract']
        index.register(self.store, entry, record['revision'])
        (self.repo / 'app.py').write_text('def public():\n    return 3\n', encoding='utf-8')
        index.scan(self.store, ['app.py'])
        result = self.store.read()['entries'][0]
        self.assertEqual([], result['verification']['evidence'])
        self.assertIsNone(result['verification']['recorded_at'])
        self._repeat_is_noop()

    def test_changed_caller_is_not_approved_by_source_only_rescan(self):
        caller = self.repo / 'caller.py'
        caller.write_text('from app import public\n', encoding='utf-8')
        index.scan(self.store, ['app.py'])
        record = self.store.read()
        entry = record['entries'][0]
        entry['references']['callers'] = [{'path': 'caller.py', 'sha256': hashlib.sha256(caller.read_bytes()).hexdigest()}]
        index.register(self.store, entry, record['revision'])
        caller.write_text('from app import public\nvalue=public()\n', encoding='utf-8')
        index.scan(self.store, ['app.py'])
        self.assertEqual('recheck', self.store.read()['entries'][0]['freshness'])
        self._repeat_is_noop()

    def test_register_rejects_duplicate_fields_without_writing(self):
        index.scan(self.store, ['app.py'])
        record = self.store.read()
        entry_path = self.base / 'entry.json'
        entry_path.write_text('{"summary":"ambiguous",' + json.dumps(record['entries'][0])[1:], encoding='utf-8')
        before = self.store.current.read_bytes()
        with self.assertRaisesRegex(CapabilityError, 'DUPLICATE_FIELD'):
            capability_cli.run(SimpleNamespace(profile=str(self.profile), repo_path=str(self.repo), index_root=None,
                capability_action='register', entry=str(entry_path), expected_revision=record['revision']))
        self.assertEqual(before, self.store.current.read_bytes())

    def test_recovery_rejects_ambiguous_or_unknown_headers_without_writing(self):
        index.scan(self.store, ['app.py'])
        (self.repo / 'app.py').write_text('def public():\n    return 2\n', encoding='utf-8')
        index.scan(self.store, ['app.py'])
        original = self.store.current.read_bytes()
        previous = self.store.previous.read_bytes()
        boolean_header = json.loads(original)
        boolean_header['schema_version'] = True
        cases = [
            (b'{"schema_version":2,' + original[1:], 'DUPLICATE_FIELD'),
            (b'{"identity":{},' + original[1:], 'DUPLICATE_FIELD'),
            (json.dumps(boolean_header).encode('utf-8'), 'UNKNOWN_SCHEMA'),
        ]
        for raw, reason in cases:
            with self.subTest(reason=reason):
                self.store.current.write_bytes(raw)
                with self.assertRaisesRegex(CapabilityError, reason):
                    self.store.recover(hashlib.sha256(raw).hexdigest())
                self.assertEqual(raw, self.store.current.read_bytes())
                self.assertEqual(previous, self.store.previous.read_bytes())
                self.assertEqual([], list(self.store.root.glob('index.recovery-*.bin')))

    def test_missing_and_invalidated_results_distinguish_required_maintenance(self):
        missing = index.query(self.store, 'public')
        self.assertEqual('INDEX_MISSING', missing['reason'])
        self.assertEqual('NOT_INITIALIZED', missing['maintenance']['state'])
        self.assertEqual('capability-scan', missing['maintenance']['next_operation'])
        self.assertFalse(self.store.current.exists())
        scanned = index.scan(self.store, ['app.py'])
        invalidated = index.invalidate(self.store, ['app.py'], scanned['revision'])
        self.assertEqual('INVALIDATED_NOT_UPDATED', invalidated['maintenance']['state'])
        self.assertEqual('capability-scan', invalidated['maintenance']['next_operation'])
        self.assertEqual('recheck', self.store.read()['entries'][0]['freshness'])


if __name__ == '__main__':
    unittest.main()
