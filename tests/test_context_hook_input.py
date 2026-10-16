"""中文：大工具结果不得误拦主任务；English: scope the real Hook before child limits."""
from __future__ import annotations

import json
import importlib.util
import io
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 2 * 1024 * 1024
sys.path.insert(0, str(ROOT / 'runtime'))
from cp_runtime import context_hook_input as reader

hook_spec = importlib.util.spec_from_file_location("context_owner_retry_fixture", ROOT / "hooks/cp_context.py")
owner_hook = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(owner_hook)


class ContextHookInputTests(unittest.TestCase):
    def test_one_transient_owner_lock_timeout_recovers_same_call(self):
        data = {"agent_id": "fixture-child"}
        owner = ("new", Path("fixture-ledger"))
        with patch.object(owner_hook, "g6_route", side_effect=[TimeoutError("busy"), owner]) as route:
            self.assertEqual(owner_hook._g6_owner(data), owner)
            self.assertEqual(route.call_count, 2)
            self.assertTrue(all(call.args == (data,) for call in route.call_args_list))

    def test_owner_retry_is_bounded_and_does_not_hide_identity_or_permission_errors(self):
        with patch.object(owner_hook, "g6_route", side_effect=TimeoutError("busy")) as route:
            with self.assertRaisesRegex(TimeoutError, "G6_CONTEXT_LOCK_BUSY"):
                owner_hook._g6_owner({"agent_id": "fixture-child"})
            self.assertEqual(route.call_count, 2)
        for error in (ValueError("TASK_IDENTITY_CONFLICT"), PermissionError("fixture denial")):
            with patch.object(owner_hook, "g6_route", side_effect=error) as route:
                with self.assertRaises(type(error)):
                    owner_hook._g6_owner({"agent_id": "fixture-child"})
                self.assertEqual(route.call_count, 1)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = dict(os.environ, CODEX_HOME=self.temp.name)

    def invoke(self, raw, event='PostToolUse'):
        run = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'hooks/cp_context.py'), event],
                             input=raw, capture_output=True, env=self.env, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stderr, b'')
        return json.loads(run.stdout)

    def payload(self, event, size, **metadata):
        field = 'tool_input' if event == 'PreToolUse' else 'tool_response'
        data = {'hook_event_name': event, 'tool_name': 'view_image',
                field: {'content': [{'type': 'image', 'data': ''}]}, **metadata}
        overhead = len(json.dumps(data).encode())
        data[field]['content'][0]['data'] = 'A' * (size - overhead)
        raw = json.dumps(data).encode()
        self.assertEqual(len(raw), size)
        return raw

    def test_parent_exact_byte_boundary_is_neutral_in_both_phases(self):
        for event in ('PreToolUse', 'PostToolUse'):
            for size in (LIMIT - 1, LIMIT, LIMIT + 1):
                with self.subTest(event=event, size=size):
                    self.assertEqual(self.invoke(self.payload(event, size), event), {})

    def test_large_image_parent_with_late_metadata_is_neutral(self):
        raw = self.payload('PostToolUse', 8 * 1024 * 1024,
                           agent_id=None, session_id='unregistered-parent')
        self.assertEqual(self.invoke(raw), {})

    def test_large_child_still_observes_existing_limit_even_when_identity_is_last(self):
        for event in ('PreToolUse', 'PostToolUse'):
            response = self.invoke(self.payload(event, LIMIT + 4096,
                                   agent_id='child', session_id='parent'), event)
            if event == 'PreToolUse':
                self.assertEqual(response['hookSpecificOutput']['permissionDecision'], 'deny')
                self.assertIn('V5_HOOK_SIZE', response['hookSpecificOutput']['permissionDecisionReason'])
            else:
                self.assertNotIn('decision', response)
                self.assertIn('Context audit was not verified', response['hookSpecificOutput']['additionalContext'])
                self.assertIn('continue unaffected work', response['hookSpecificOutput']['additionalContext'])

    def test_alias_after_large_body_cannot_hide_a_child(self):
        for metadata in ({'agentId': 'hidden-child'}, {'agent_id': '', 'agentId': 'child'},
                         {'agent_id': None, 'agentId': 'child'}):
            with self.subTest(metadata=metadata):
                response = self.invoke(self.payload('PreToolUse', LIMIT + 1000, **metadata), 'PreToolUse')
                self.assertEqual(response['hookSpecificOutput']['permissionDecision'], 'deny')
                self.assertIn('V5_CHILD_ALIAS_CONFLICT',
                              response['hookSpecificOutput']['permissionDecisionReason'])

    def test_truncated_or_duplicated_envelope_never_becomes_neutral(self):
        raw = self.payload('PostToolUse', LIMIT + 1000)
        for changed in (raw[:-1], raw + b'{}', raw[:-1] + b',"agent_id":"","agent_id":"child"}',
                        raw[:-1] + b',"agent_id":"","agent_\\u0069d":"child"}'):
            response = self.invoke(changed, 'PreToolUse')
            self.assertEqual(response['hookSpecificOutput']['permissionDecision'], 'deny')


class StreamingEnvelopeTests(unittest.TestCase):
    def parse(self, raw):
        with patch.object(reader, 'INPUT_LIMIT', 1), patch.object(reader, 'CHUNK_BYTES', 3):
            return reader.read_context_input(io.BytesIO(raw))

    def test_body_strings_and_nested_identity_are_not_authority(self):
        data = {'tool_response': {'agent_id': 'not-the-caller',
                'text': '"},"agent_id":"injected"', 'unicode': '汉字😀\\\t\n'},
                'agent_id': None, 'agentId': None}
        for ascii_only in (True, False):
            self.assertEqual(self.parse(json.dumps(data, ensure_ascii=ascii_only).encode()), {})
        self.assertEqual(self.parse(b'\xef\xbb\xbf' + json.dumps(data).encode()), {})

    def test_valid_json_shapes_match_standard_decoder(self):
        rng = random.Random(391)
        def value(depth=0):
            leaves = [None, True, False, 0, -12, 0.125, 1e20, '', '\\"\r\t汉😀']
            if depth == 3 or rng.randrange(3) == 0:
                return rng.choice(leaves)
            if rng.randrange(2):
                return [value(depth + 1) for _ in range(rng.randrange(4))]
            return {str(i): value(depth + 1) for i in range(rng.randrange(4))}
        for _ in range(150):
            self.assertEqual(self.parse(json.dumps({'tool_response': value()}, ensure_ascii=False).encode()), {})

    def test_invalid_json_escapes_numbers_and_nested_duplicates_fail(self):
        values = [b'{"x":"\\q"}', b'{"x":"\\uGGGG"}', b'{"x":"unterminated}',
                  b'{"x":"\x00"}', b'{"x":"\xff"}', b'{"x":"\xe4\xb8"}',
                  b'{"x":[1,]}', b'{"x":{"a":1,}}', b'{"x":00}', b'{"x":+1}',
                  b'{"x":1.}', b'{"x":.1}', b'{"x":1e}', b'{"x":NaN}', b'{"x":Infinity}',
                  b'{"x":tru}', b'{"x":true false}', b'{"x":}', b'{"x":1}junk',
                  b'{"x":{"a":1,"\\u0061":2}}', b'{"x":[}', b'{"x" 1}', b'[]', b'null']
        for raw in values:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.parse(raw)

    def test_identity_types_aliases_and_late_children_fail_closed(self):
        cases = [{'agent_id': value} for value in (False, 0, [], {})]
        cases += [{'agentId': value} for value in (False, 0, [], {}, 'child')]
        cases += [{'agent_id': 'child'}, {'agent_id': 'child', 'agentId': 'other'}]
        for metadata in cases:
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                self.parse(json.dumps({'tool_response': 'x', **metadata}).encode())
        for metadata in ({}, {'agent_id': ''}, {'agent_id': None}, {'agent_id': '', 'agentId': ''}):
            self.assertEqual(self.parse(json.dumps({'x': 1, **metadata}).encode()), {})

    def test_depth_nodes_keys_metadata_and_scalar_limits(self):
        cases = [('MAX_DEPTH', 3, b'{"x":[[[[]]]]}'),
                 ('MAX_NODES', 3, b'{"x":[0,0,0]}'),
                 ('MAX_KEY_CHARS', 5, b'{"aaa":0,"bbb":0}'),
                 ('MAX_STRING_CHARS', 3, b'{"abcd":0}')]
        for name, maximum, raw in cases:
            with self.subTest(name=name), patch.object(reader, name, maximum), self.assertRaises(ValueError):
                self.parse(raw)
        with self.assertRaisesRegex(ValueError, 'METADATA_SIZE'):
            self.parse(json.dumps({'agent_id': 'x' * (reader.MAX_STRING_CHARS + 1)}).encode())
        with self.assertRaisesRegex(ValueError, 'STRUCTURE_LIMIT'):
            self.parse(b'{"x":' + b'1' * 4097 + b'}')

    def test_transport_limit_and_deadline_bound_the_complete_scan(self):
        with patch.object(reader, 'TRANSPORT_LIMIT', 24), self.assertRaisesRegex(ValueError, 'TRANSPORT_SIZE'):
            self.parse(b'{"x":"' + b'A' * 30 + b'"}')
        with patch.object(reader, 'MAX_SECONDS', -1), self.assertRaisesRegex(ValueError, 'HOOK_TIME'):
            self.parse(b'{"x":0}')

    def test_long_ignored_string_and_whitespace_do_not_consume_metadata_budget(self):
        with patch.object(reader, 'MAX_STRING_CHARS', 4):
            self.assertEqual(self.parse(b' ' * 1000 + b'{"x":"' + b'A' * 10000 + b'"}' + b'\n' * 1000), {})

    def test_small_child_payload_is_preserved_byte_for_byte_semantically(self):
        data = {'agent_id': 'child', 'agentId': 'child', 'tool_input': {'cmd': 'echo 1'},
                'tool_response': {'exit_code': 0, 'output': 'unmodified'}}
        self.assertEqual(reader.read_context_input(io.BytesIO(json.dumps(data).encode())), data)


if __name__ == '__main__':
    unittest.main()
