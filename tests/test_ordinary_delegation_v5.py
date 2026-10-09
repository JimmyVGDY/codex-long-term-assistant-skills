"""中文：使用临时仓库和原生形状夹具，不构成真实模型资格。

English: Temporary repositories and native-shaped fixtures; no real model qualification.
"""
import copy
import hashlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
from cp_runtime import budget_v4, budget_v5 as budget, review_v5 as review
from cp_runtime import routing_hook_v5 as hook, routing_registry_v5 as registry
from cp_runtime.common import repo_snapshot
from cp_runtime.evidence import record_evidence
from cp_runtime.ordinary_delegation_v5 import record_result
from cp_runtime.ordinary_routing_v5 import CONTRACT, option
from cp_runtime.routing_context_contract import MODE_V2, create_bundle, digest, runtime
from cp_runtime.routing_context_v5 import loader
from cp_runtime.routing_contract import RoutingError, ref
import test_routing_v4_context as fixtures
from test_routing_v4_context import write
from test_routing_v4_selection_phase import slot


class OrdinaryDelegationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ContextTests(methodName='runTest')
        self.f.setUp()
        old = budget_v4.read_budget(self.f.path)
        self.path = self.f.root / 'ordinary-budget.jsonl'
        binding = {**old['root_binding'], 'schema_version': 'dispatch-root/3',
                   'context_runtime': runtime(ROOT / 'hooks/review_context_reader.py', Path(sys.executable),
                       transport_mode=MODE_V2, ordinary_contract=CONTRACT)}
        self.request = copy.deepcopy(self.f.request)
        self.request['scenario'].update(role='worker', phase='pre')
        self.request.update(schema_version='routing-request/2', slot_id='ordinary')
        self.request.pop('message_sha256')
        self.prompt = self.f.root / 'ordinary-prompt.txt'
        self.prompt.write_text('Update README.md; check the result and report what changed.', encoding='utf-8')
        self.request['business_prompt_sha256'] = digest(self.prompt.read_bytes())
        self.request['constraints']['allowed_profiles'] = ['g56-luna-medium']
        self.request['context_bundle'] = create_bundle(self.f.root / 'ordinary-bundle.json', repo=self.f.repo,
            business_prompt=self.prompt, packet_sha256=self.request['packet_sha256'],
            baseline_sha256=self.request['baseline_sha256'], artifacts={})
        requirement = self.f.root / 'ordinary-requirement.json'
        record_evidence(requirement, 'ordinary-scope', self.f.project.profile_path, self.f.identity['task_id'],
            self.f.repo, 'review', 'Ordinary scope fixture', 'valid', 'parent-reviewed-v4-requirements',
            'Fixture only', ['scenario:' + ref(self.request['scenario']), 'packet:' + self.request['packet_sha256'],
                             'independent-review-required'])
        evidence_ref = 'sha256:' + hashlib.sha256(requirement.read_bytes()).hexdigest()
        self.request['evidence']['refs'] = [evidence_ref]
        sources = {**old['sources'], 'evaluation_costs': '', 'evaluation_ref': '',
                   'evidence_paths': {evidence_ref: str(requirement)}}
        self.f.capability['available_profiles'] += ['g56-luna-low', 'g56-luna-medium', 'g56-terra-medium', 'g56-terra-high']
        write(self.f.cap_path, self.f.capability)
        phase_plan = copy.deepcopy(old['phase_plan'])
        phase_plan['slots'] = [slot('ordinary', [option('g56-luna-medium', self.request['scenario'])], role='worker', phase='pre')]
        budget.initialize(self.path, declared_identity={**old['identity'], 'budget_id': 'ordinary-test'},
            root_binding=binding, sources=sources, execution_mode='EVALUATION', capacity=old['capacity'],
            role_capacity={'reviewer': 50, 'worker': 50, 'explorer': 0},
            phase_capacity={'pre': 50, 'post': 50, 'repair': 0}, phase_plan=phase_plan, max_depth=1)
        self.loader = loader(cwd=str(self.f.repo), host_session_id='desktop-session')
        self.selected = budget.prepare(self.path, self.request, dispatch_key='ordinary_one', depth=1, snapshot_loader=self.loader)
        self.assertEqual('EVALUATION_SELECTED', self.selected['status'])
        self.pid = self.selected['permit_id']
        self.parent = {'hook_event_name': 'PreToolUse', 'session_id': 'desktop-session', 'cwd': str(self.f.repo),
            'tool_name': 'collaborationspawn_agent', 'tool_use_id': 'ordinary-spawn', 'tool_input': {
                **self.selected['request_parameters'], 'task_name': 'ordinary_one', 'fork_turns': 'none',
                'message': self.prompt.read_text(encoding='utf-8')}}
        self.child = '12345678-1234-1234-1234-123456789012'
        self.home = self.f.root / 'home'
        sessions = self.home / 'sessions'
        sessions.mkdir(parents=True)
        self.transcript = sessions / ('rollout-' + self.child + '.jsonl')
        self.header = {'type': 'session_meta', 'payload': {'id': self.child, 'cwd': str(self.f.repo),
            'source': {'subagent': {'thread_spawn': {'parent_thread_id': 'desktop-session', 'depth': 1,
                'agent_role': 'worker', 'agent_path': '/root/ordinary_one'}}}}}
        self.transcript.write_text(json.dumps(self.header) + '\n', encoding='utf-8')
        self.env = patch.dict(os.environ, {'CODEX_HOME': str(self.home), 'CP_ROUTING_BINDINGS_ROOT': str(self.f.root / 'bindings')})
        self.env.start()
        self.child_data = {'hook_event_name': 'SubagentStart', 'session_id': 'desktop-session', 'agent_id': self.child,
            'agent_type': 'worker', 'cwd': str(self.f.repo), 'transcript_path': str(self.transcript)}
        registry.bind(self.path, cwd=str(self.f.repo), host_session_id='desktop-session')

    def tearDown(self):
        if hasattr(self, 'env'):
            self.env.stop()
        self.f.tearDown()

    def reserve(self):
        return hook.pretool(self.path, self.parent, self.parent['tool_input'])

    def receipt(self):
        hook.lifecycle(self.path, {**self.parent, 'hook_event_name': 'PostToolUse',
            'tool_response': {'task_name': '/root/ordinary_one'}}, 'PostToolUse', args=self.parent['tool_input'])

    def start(self):
        return hook.lifecycle(self.path, self.child_data, 'SubagentStart')

    def finish(self, outcome='UNKNOWN', text='README.md updated and checked.'):
        self.response = self.f.root / 'ordinary-response.txt'
        self.response.write_text(text, encoding='utf-8')
        events = [{'type': 'event_msg', 'payload': {'type': 'task_started', 'turn_id': 'ordinary-turn'}},
                  {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant', 'phase': 'final_answer',
                    'content': [{'type': 'output_text', 'text': text}]}}]
        with self.transcript.open('a', encoding='utf-8') as stream:
            stream.write(''.join(json.dumps(event) + '\n' for event in events))
        hook.lifecycle(self.path, {**self.child_data, 'hook_event_name': 'SubagentStop',
            'agent_transcript_path': str(self.transcript), 'terminal_outcome': outcome}, 'SubagentStop')

    def validation(self, status='pass'):
        self.validation_path = self.f.root / 'ordinary-validation.json'
        rid = next(iter(budget.read_budget(self.path)['reservations']))
        record_evidence(self.validation_path, 'ordinary-validation', self.f.project.profile_path, self.f.identity['task_id'],
            self.f.repo, 'validation', 'Current parent task validation', 'valid', 'parent-ordinary-task-validation',
            'Synthetic validation only', ['ordinary-reservation:' + ref(rid), 'ordinary-verdict:' + status])
        return rid

    def result(self, status='pass'):
        rid = self.validation(status)
        return record_result(self.path, cwd=str(self.f.repo), host_session_id='desktop-session', reservation_id=rid,
                             response_path=self.response, validation_path=self.validation_path, status=status)

    def tool(self):
        return {**self.child_data, 'hook_event_name': 'PreToolUse', 'tool_name': 'apply_patch',
                'tool_use_id': 'ordinary-edit', 'tool_input': {'patch': 'ordinary edit fixture'}}

    def test_edit_and_native_text_completion_require_current_parent_validation(self):
        self.reserve(); self.receipt()
        self.assertEqual({}, self.start())
        self.assertEqual({}, hook.child_tool(self.path, self.tool()))
        (self.f.repo / 'README.md').write_text('Updated ordinary fixture\n', encoding='utf-8')
        self.finish()
        state = budget.read_budget(self.path)
        self.assertFalse(state['accepted_results'])
        self.assertFalse(state['ordinary_results'])
        with self.assertRaisesRegex(ValueError, 'UNFULFILLED_SCOPE'):
            budget.close(self.path, outcome='PASS', evidence_ref=ref('test'))
        state = self.result()
        self.assertEqual('SATISFIED', state['phase_plan']['slots'][0]['status'])
        self.assertFalse(state['context_deliveries'])
        self.assertFalse(state['accepted_results'])
        budget.close(self.path, outcome='PASS', evidence_ref=ref('test'))
        self.assertEqual({}, budget.export_traces(self.path))

    def test_unapproved_message_and_tools_before_creation_receipt_are_denied(self):
        with self.assertRaisesRegex(RoutingError, 'ORDINARY_MESSAGE_BINDING'):
            hook.pretool(self.path, self.parent, {**self.parent['tool_input'], 'message': 'Different task'})
        self.assertFalse(budget.read_budget(self.path)['reservations'])
        self.reserve(); self.start()
        with self.assertRaisesRegex(RoutingError, 'CREATION_RECEIPT_PENDING'):
            hook.child_tool(self.path, self.tool())
        self.receipt()
        self.assertEqual({}, hook.child_tool(self.path, self.tool()))
        with self.assertRaisesRegex(RoutingError, 'ROOT_BINDING|NESTED_CALLER'):
            hook.pretool(self.path, self.tool(), self.parent['tool_input'])

    def test_forged_response_and_stale_validation_do_not_complete_slot(self):
        self.reserve(); self.receipt(); self.start(); self.finish()
        rid = self.validation()
        self.response.write_text('Forged response', encoding='utf-8')
        with self.assertRaisesRegex(RoutingError, 'NATIVE_OUTPUT'):
            record_result(self.path, cwd=str(self.f.repo), host_session_id='desktop-session', reservation_id=rid,
                          response_path=self.response, validation_path=self.validation_path, status='pass')
        self.response.write_text('README.md updated and checked.', encoding='utf-8')
        (self.f.repo / 'README.md').write_text('Changed after validation\n', encoding='utf-8')
        with self.assertRaisesRegex(RoutingError, 'PARENT_VALIDATION_REQUIRED'):
            record_result(self.path, cwd=str(self.f.repo), host_session_id='desktop-session', reservation_id=rid,
                          response_path=self.response, validation_path=self.validation_path, status='pass')
        self.assertFalse(budget.read_budget(self.path)['ordinary_results'])

    def test_failed_host_cannot_be_promoted_and_incomplete_keeps_charge(self):
        self.reserve(); self.receipt(); self.start(); self.finish(outcome='FAILED', text='Unable to finish.')
        with self.assertRaisesRegex(RoutingError, 'HOST_CONFLICT'):
            self.result('pass')
        before = budget.read_budget(self.path)['capacity']['units']
        state = self.result('incomplete')
        self.assertEqual('PENDING', state['phase_plan']['slots'][0]['status'])
        self.assertEqual(before - 2, budget.snapshot_budget(state)['remaining']['units'])
        with self.assertRaisesRegex(RoutingError, 'UNFULFILLED_SCOPE'):
            budget.close(self.path, outcome='PASS', evidence_ref=ref('test'))
        budget.close(self.path, outcome='PARTIAL', evidence_ref=ref('test'))

    def test_delayed_receipt_and_duplicate_events_preserve_single_charge(self):
        self.reserve(); self.start(); self.finish()
        state = budget.read_budget(self.path)
        self.assertFalse(state['ordinary_results'])
        self.assertEqual(1, state['capacity']['attempts'] - budget.snapshot_budget(state)['remaining']['attempts'])
        self.receipt()
        rid = self.validation()
        self.assertEqual('COMPLETED', budget.read_budget(self.path)['reservations'][rid]['state'])
        self.start(); self.receipt()
        state = self.result()
        original = state['ordinary_results'][rid]
        again = record_result(self.path, cwd=str(self.f.repo), host_session_id='desktop-session', reservation_id=rid,
                              response_path=self.response, validation_path=self.validation_path, status='pass')
        self.assertEqual(state['sequence'], again['sequence'])
        self.assertEqual(original, again['ordinary_results'][rid])
        self.assertEqual(state['capacity']['units'] - 2, budget.snapshot_budget(again)['remaining']['units'])

    def test_retry_requires_new_evidence_and_keeps_both_attempts(self):
        self.reserve(); self.receipt(); self.start(); self.finish(text='Need another change.')
        state = self.result('incomplete')
        rid = next(iter(state['reservations']))
        transition = {'prior_reservation_id': rid, 'prior_result_ref': state['ordinary_results'][rid]['result_ref'],
                      'reason': 'NEW_EVIDENCE'}
        with self.assertRaisesRegex(RoutingError, 'REPEAT_REQUIRES_NEW_EVIDENCE'):
            budget.prepare(self.path, self.request, dispatch_key='retry_without_evidence', depth=1,
                           snapshot_loader=self.loader, transition=transition)
        additional = self.f.root / 'additional-requirement.json'
        record_evidence(additional, 'additional-ordinary-scope', self.f.project.profile_path, self.f.identity['task_id'],
            self.f.repo, 'review', 'New task requirement', 'valid', 'parent-reviewed-v4-requirements',
            'New independent scope fixture', ['scenario:' + ref(self.request['scenario']),
            'packet:' + self.request['packet_sha256'], 'independent-review-required'])
        evidence_ref = 'sha256:' + hashlib.sha256(additional.read_bytes()).hexdigest()
        budget.add_evidence_paths(self.path, {evidence_ref: str(additional)})
        new_request = copy.deepcopy(self.request)
        new_request['evidence']['refs'].append(evidence_ref)
        choice = budget.prepare(self.path, new_request, dispatch_key='ordinary_two', depth=1,
                                snapshot_loader=self.loader, transition=transition)
        self.assertEqual('EVALUATION_SELECTED', choice['status'])
        self.parent['tool_input'].update(task_name='ordinary_two')
        self.parent['tool_use_id'] = 'ordinary-spawn-two'
        self.child = '87654321-1234-1234-1234-123456789012'
        self.child_data['agent_id'] = self.child
        self.transcript = self.home / 'sessions' / ('rollout-' + self.child + '.jsonl')
        self.child_data['transcript_path'] = str(self.transcript)
        self.header['payload']['id'] = self.child
        self.header['payload']['source']['subagent']['thread_spawn']['agent_path'] = '/root/ordinary_two'
        self.transcript.write_text(json.dumps(self.header) + '\n', encoding='utf-8')
        self.reserve()
        hook.lifecycle(self.path, {**self.parent, 'hook_event_name': 'PostToolUse',
            'tool_response': {'task_name': '/root/ordinary_two'}}, 'PostToolUse', args=self.parent['tool_input'])
        self.start(); self.finish(text='Task completed after new evidence.')
        second = next(r for r in budget.read_budget(self.path)['reservations'] if r != rid)
        validation = self.f.root / 'retry-validation.json'
        record_evidence(validation, 'retry-validation', self.f.project.profile_path, self.f.identity['task_id'],
            self.f.repo, 'validation', 'Retry checked', 'valid', 'parent-ordinary-task-validation', 'Fixture only',
            ['ordinary-reservation:' + ref(second), 'ordinary-verdict:pass'])
        state = record_result(self.path, cwd=str(self.f.repo), host_session_id='desktop-session', reservation_id=second,
                              response_path=self.response, validation_path=validation, status='pass')
        self.assertEqual(2, len(state['reservations']))
        self.assertEqual([transition['prior_result_ref']], state['ordinary_results'][second]['supersedes'])
        self.assertEqual(state['capacity']['units'] - 4, budget.snapshot_budget(state)['remaining']['units'])
        repeated = record_result(self.path, cwd=str(self.f.repo), host_session_id='desktop-session', reservation_id=second,
                                 response_path=self.response, validation_path=validation, status='pass')
        self.assertEqual(state['sequence'], repeated['sequence'])
        budget.close(self.path, outcome='PASS', evidence_ref=ref('test'))

    def test_ordinary_task_cannot_use_reviewer_controller(self):
        directory = self.f.root / 'review'
        review.initialize(directory, ledger_path=self.path, boundary_id='ordinary-boundary')
        with self.assertRaisesRegex(RoutingError, 'REVIEWER_ROLE_REQUIRED'):
            review.prepare(directory, self.request, dispatch_key='wrong_controller', depth=1, snapshot_loader=self.loader)

    def test_internal_prepare_returns_only_the_approved_native_dispatch(self):
        from cp_runtime.routing_cli_v5 import main
        request_path = self.f.root / 'ordinary-request.json'
        write(request_path, self.request)
        args = ['routing-v5', 'ordinary-prepare', '--ledger', str(self.path), '--host-session-id', 'desktop-session',
                '--request', str(request_path), '--dispatch-key', 'ordinary_cli']
        captured = io.StringIO()
        with patch.object(sys, 'argv', args), patch('os.getcwd', return_value=str(self.f.repo)), redirect_stdout(captured):
            main()
        result = json.loads(captured.getvalue())
        self.assertEqual('EVALUATION_SELECTED', result['status'])
        self.assertEqual({**self.selected['request_parameters'], 'task_name': 'ordinary_cli', 'fork_turns': 'none',
                          'message': self.prompt.read_text(encoding='utf-8')}, result['request_parameters'])
        self.assertFalse(budget.read_budget(self.path)['reservations'])


if __name__ == '__main__':
    unittest.main()
