"""中文：Windows 同目录路径表示的预算与隔离回归。

English: Equivalent Windows root spellings must preserve budget identity and isolation.
All dispatch inputs below are synthetic fixtures, not native acceptance evidence.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import test_routing_v4_hook as hook_fixtures
import test_routing_v4_context as context_fixtures

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime import budget_v4
from cp_runtime import routing_registry_v4 as registry
from cp_runtime.common import RuntimeContractError, assert_managed_target, inside, require_external_state
from cp_runtime.event_v2 import stable_repo_fingerprint
from cp_runtime.path_identity import _alternate_windows_spelling, path_aliases, same_path
from cp_runtime.routing_context_v4 import verify_root
from cp_runtime.routing_contract import RoutingError, ref


def extended(path: Path) -> Path:
    return Path("\\\\?\\" + str(path.resolve()))


@unittest.skipUnless(os.name == "nt", "Requires real Windows namespace aliases")
class WindowsRootPathAliasTests(unittest.TestCase):
    def setUp(self):
        self.hook = hook_fixtures.V4HookTests(methodName="runTest")
        self.hook.setUp()
        self.fixture = self.hook.fixture
        self.directory = Path(self.hook.env["CP_ROUTING_BINDINGS_ROOT"])

    def tearDown(self):
        self.hook.tearDown()

    def bind(self):
        self.hook.bind_registry()

    def invoke(self, payload):
        outcome = subprocess.run(
            [sys.executable, "-B", str(ROOT / "hooks/cp_hook.py"), payload["hook_event_name"]],
            input=json.dumps(payload), cwd=self.fixture.repo, env=self.hook.env,
            text=True, encoding="utf-8", capture_output=True, timeout=20)
        self.assertEqual(0, outcome.returncode, outcome.stderr)
        self.assertNotIn("RECONCILIATION_FAILED", outcome.stderr)
        return json.loads(outcome.stdout) if outcome.stdout.strip() else {}

    def test_lookup_reuses_binding_without_rewriting_historical_fingerprint(self):
        self.bind()
        original = self.fixture.path.read_bytes()
        normal_fingerprint = stable_repo_fingerprint(str(self.fixture.repo))
        extended_fingerprint = stable_repo_fingerprint(str(extended(self.fixture.repo)))
        self.assertNotEqual(normal_fingerprint, extended_fingerprint)
        self.assertTrue(self.fixture.repo.samefile(extended(self.fixture.repo)))
        self.assertEqual(
            self.fixture.path.resolve(),
            registry.lookup(cwd=str(extended(self.fixture.repo)), host_session_id="desktop-session",
                            directory=self.directory))
        self.assertEqual(original, self.fixture.path.read_bytes())
        self.assertEqual(normal_fingerprint, stable_repo_fingerprint(str(self.fixture.repo)))
        self.assertEqual(extended_fingerprint, stable_repo_fingerprint(str(extended(self.fixture.repo))))

    def test_historical_extended_root_keeps_its_original_identity(self):
        original_builder = context_fixtures.build_root_binding

        def extended_binding(envelope, session):
            value = json.loads(envelope.read_text(encoding="utf-8"))
            value["repo_path"] = str(extended(Path(value["repo_path"])))
            context_fixtures.write(envelope, value)
            return original_builder(envelope, session)

        legacy = context_fixtures.ContextTests(methodName="runTest")
        with patch.object(context_fixtures, "build_root_binding", side_effect=extended_binding):
            legacy.setUp()
        try:
            self.assertTrue(legacy.binding["repo_path"].startswith("\\\\?\\"))
            output = budget_v4.prepare(legacy.path, legacy.request, dispatch_key="legacy-alias",
                                      depth=1, snapshot_loader=legacy.loader)
            self.assertEqual("EVALUATION_SELECTED", output["status"])
            before = legacy.path.read_bytes()
            directory = legacy.root / "bindings"
            registry.bind(legacy.path, cwd=str(legacy.repo), host_session_id="desktop-session",
                          directory=directory)
            self.assertEqual(legacy.path.resolve(), registry.lookup(
                cwd=str(legacy.repo), host_session_id="desktop-session", directory=directory))
            self.assertEqual(before, legacy.path.read_bytes())
            self.assertEqual(legacy.identity["repo_fingerprint"],
                             budget_v4.read_budget(legacy.path)["identity"]["repo_fingerprint"])
        finally:
            legacy.tearDown()

    def test_unproven_alias_cannot_gain_equivalence(self):
        with patch("cp_runtime.path_identity.os.path.samefile", return_value=False):
            self.assertEqual((self.fixture.repo.resolve(),), path_aliases(self.fixture.repo))
            self.assertFalse(same_path(self.fixture.repo, extended(self.fixture.repo)))
        with patch("cp_runtime.path_identity.os.path.samefile", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                same_path(self.fixture.repo, extended(self.fixture.repo))

    def test_unavailable_proof_does_not_look_unbound_or_external(self):
        self.bind()
        alias = extended(self.fixture.repo)
        with patch("cp_runtime.path_identity.os.path.samefile", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                registry.lookup(cwd=str(alias), host_session_id="desktop-session",
                                directory=self.directory)
            with self.assertRaises(PermissionError):
                require_external_state(alias / "new-state.json", self.fixture.repo)
            # 中文：普通路径的包含判断已足够，不额外探测别名。
            # English: Proven ordinary-path containment needs no alias probe.
            self.assertTrue(inside(self.fixture.repo / "new-state.json", self.fixture.repo))

    def test_managed_root_is_never_an_alias_replacement_target(self):
        for target, managed in ((extended(self.fixture.repo), self.fixture.repo),
                                (self.fixture.repo, extended(self.fixture.repo))):
            with self.assertRaises(RuntimeContractError):
                assert_managed_target(target, managed)

    def test_managed_new_child_remains_valid_under_both_spellings(self):
        child = self.fixture.repo / "new-child"
        self.assertFalse(child.exists())
        for target, managed in ((child, self.fixture.repo),
                                (extended(self.fixture.repo) / child.name, self.fixture.repo),
                                (child, extended(self.fixture.repo))):
            self.assertIsNone(assert_managed_target(target, managed))
        self.assertFalse(child.exists())

    def test_alias_bind_is_idempotent_and_uses_one_entry(self):
        self.bind()
        before = {p.name: p.read_bytes() for p in self.directory.glob("*.json")}
        registry.bind(self.fixture.path, cwd=str(extended(self.fixture.repo)),
                      host_session_id="desktop-session", directory=self.directory)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.glob("*.json")})

    def test_concurrent_alias_bind_still_creates_one_entry(self):
        def bind(cwd):
            return registry.bind(self.fixture.path, cwd=str(cwd), host_session_id="desktop-session",
                                 directory=self.directory)
        with ThreadPoolExecutor(max_workers=2) as workers:
            rows = list(workers.map(bind, (self.fixture.repo, extended(self.fixture.repo))))
        self.assertEqual(rows[0], rows[1])
        self.assertEqual(1, len(list(self.directory.glob("*.json"))))

    def test_alternate_binding_collision_fails_closed(self):
        self.bind()
        normal = registry._entry(str(self.fixture.repo), "desktop-session", self.directory)
        alternate = registry._entry(str(extended(self.fixture.repo)), "desktop-session", self.directory)
        self.assertNotEqual(normal, alternate)
        alternate.write_bytes(normal.read_bytes())
        with self.assertRaises(RoutingError):
            registry.lookup(cwd=str(self.fixture.repo), host_session_id="desktop-session",
                            directory=self.directory)

    def test_external_state_boundary_covers_both_namespace_spellings(self):
        not_created = self.fixture.repo / "must-not-be-created.json"
        extended_child = extended(self.fixture.repo) / not_created.name
        self.assertFalse(not_created.exists())
        for child, parent in ((not_created, extended(self.fixture.repo)),
                              (extended_child, self.fixture.repo)):
            self.assertTrue(inside(child, parent))
            with self.assertRaises(RuntimeContractError):
                require_external_state(child, parent)
        self.assertFalse(inside(self.fixture.root / "external.json", extended(self.fixture.repo)))

    def test_foreign_root_still_cannot_borrow_the_binding(self):
        self.bind()
        foreign = self.fixture.root / "foreign"
        foreign.mkdir()
        self.assertIsNone(registry.lookup(cwd=str(extended(foreign)), host_session_id="desktop-session",
                                        directory=self.directory))
        with self.assertRaisesRegex(RoutingError, "ROOT_BINDING"):
            verify_root(budget_v4.read_budget(self.fixture.path), cwd=str(extended(foreign)),
                        host_session_id="desktop-session")

    def test_retired_alias_keeps_the_closed_ledger_tombstone(self):
        self.bind()
        budget_v4.close(self.fixture.path, outcome="CANCELLED", evidence_ref=ref("synthetic-close"))
        registry.retire(cwd=str(extended(self.fixture.repo)), host_session_id="desktop-session",
                        directory=self.directory)
        self.assertEqual(
            self.fixture.path.resolve(),
            registry.lookup(cwd=str(extended(self.fixture.repo)), host_session_id="desktop-session",
                            directory=self.directory))
        self.assertTrue(budget_v4.read_budget(self.fixture.path)["closed"])

    def test_named_alias_reserves_and_accepts_task_tree_receipt(self):
        self.bind()
        payload = copy.deepcopy(self.hook.payload)
        payload.update(cwd=str(extended(self.fixture.repo)), tool_name="collaboration.spawn_agent")
        self.assertEqual({}, self.invoke(payload))
        state = budget_v4.read_budget(self.fixture.path)
        self.assertEqual(1, len(state["reservations"]))
        self.invoke({**payload, "hook_event_name": "PostToolUse",
                     "tool_response": {"task_name": "/root/eval_one"}})
        self.assertEqual(1, len(budget_v4.read_budget(self.fixture.path)["host_receipts"]))

    def test_equivalent_explicit_ledger_is_not_a_registry_conflict(self):
        self.bind()
        self.hook.env["CP_DELEGATION_BUDGET_PATH"] = str(extended(self.fixture.path))
        self.assertEqual({}, self.invoke(self.hook.payload))
        self.assertEqual(1, len(budget_v4.read_budget(self.fixture.path)["reservations"]))

    def assert_transcript_alias_link(self, extended_first):
        self.bind()
        agent_id, transcript, header = self.hook.desktop_identity()
        transcript.write_text(json.dumps(header) + "\nPRIVATE_BODY_MUST_NOT_BE_READ\n", encoding="utf-8")
        payload = copy.deepcopy(self.hook.payload)
        payload.update(cwd=str(extended(self.fixture.repo)), tool_name="collaboration.spawn_agent")
        self.assertEqual({}, self.invoke(payload))
        self.invoke({**payload, "hook_event_name": "PostToolUse",
                     "tool_response": {"task_name": "/root/eval_one"}})
        stop = {"hook_event_name": "SubagentStop", "session_id": "desktop-session",
                "cwd": str(extended(self.fixture.repo)), "agent_id": agent_id,
                "agent_type": self.hook.prepared["request_parameters"]["agent_type"],
                "agent_transcript_path": str(extended(transcript) if extended_first else transcript)}
        self.invoke(stop)
        before = budget_v4.read_budget(self.fixture.path)
        self.assertEqual(1, len(before["host_identity_links"]))
        self.assertEqual("COMPLETED", next(iter(before["reservations"].values()))["state"])
        self.invoke({**stop, "cwd": str(self.fixture.repo),
                     "agent_transcript_path": str(transcript if extended_first else extended(transcript))})
        after = budget_v4.read_budget(self.fixture.path)
        self.assertEqual(before["sequence"], after["sequence"])
        self.assertNotIn("PRIVATE_BODY_MUST_NOT_BE_READ", self.fixture.path.read_text(encoding="utf-8"))

    def test_transcript_namespace_alias_links_once_extended_first(self):
        self.assert_transcript_alias_link(True)

    def test_transcript_namespace_alias_links_once_ordinary_first(self):
        self.assert_transcript_alias_link(False)

    def test_concurrent_verified_proofs_are_compared_under_one_ledger_lock(self):
        self.bind()
        self.invoke(self.hook.payload)
        self.invoke({**self.hook.payload, "hook_event_name": "PostToolUse",
                     "tool_response": {"task_name": "/root/eval_one"}})
        state = budget_v4.read_budget(self.fixture.path)
        reservation = next(iter(state["reservations"]))
        role = self.hook.prepared["request_parameters"]["agent_type"]
        proofs = (ref("synthetic-normal-proof"), ref("synthetic-extended-proof"))
        barrier = threading.Barrier(2)

        def link(proof):
            barrier.wait(timeout=5)
            return budget_v4.link_host_identity(
                self.fixture.path, reservation_id=reservation, task_path="/root/eval_one",
                agent_id="same-agent", dispatch_key="eval_one", role=role,
                proof_ref=proof, verified_proof_aliases=proofs)

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(link, proofs))
        self.assertEqual(results[0]["sequence"], results[1]["sequence"])
        after = budget_v4.read_budget(self.fixture.path)
        self.assertEqual(state["sequence"] + 1, after["sequence"])
        self.assertEqual(1, len(after["host_identity_links"]))
        with self.assertRaisesRegex(RoutingError, "IDENTITY_LINK_CONFLICT"):
            budget_v4.link_host_identity(
                self.fixture.path, reservation_id=reservation, task_path="/root/eval_one",
                agent_id="different-agent", dispatch_key="eval_one", role=role,
                proof_ref=proofs[0], verified_proof_aliases=proofs)
        with self.assertRaisesRegex(RoutingError, "IDENTITY_PROOF_ALIASES"):
            budget_v4.link_host_identity(
                self.fixture.path, reservation_id=reservation, task_path="/root/eval_one",
                agent_id="same-agent", dispatch_key="eval_one", role=role,
                proof_ref=proofs[0], verified_proof_aliases=proofs + (ref("unrelated"),))


class WindowsNamespaceSyntaxTests(unittest.TestCase):
    def test_only_drive_and_unc_namespace_forms_are_candidates(self):
        cases = {
            "C:\\work\\repo": "\\\\?\\C:\\work\\repo",
            "\\\\?\\C:\\work\\repo": "C:\\work\\repo",
            "\\\\host\\share\\repo": "\\\\?\\UNC\\host\\share\\repo",
            "\\\\?\\UNC\\host\\share\\repo": "\\\\host\\share\\repo",
        }
        for given, expected in cases.items():
            with self.subTest(given=given):
                self.assertEqual(expected, _alternate_windows_spelling(given))
        for value in ("C:relative", "\\\\.\\pipe\\name", "\\\\?\\GLOBALROOT\\Device\\name",
                      "\\\\?\\Volume{value}\\repo", "/ordinary/posix/repo"):
            with self.subTest(value=value):
                self.assertIsNone(_alternate_windows_spelling(value))


if __name__ == "__main__":
    unittest.main()
