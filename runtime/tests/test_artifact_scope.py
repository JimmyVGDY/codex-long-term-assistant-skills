"""中文：真实临时仓库的产物边界和回执回归。
English: Artifact boundaries and receipt regressions using real temporary repositories.
"""
import json
import os
import re
import subprocess
import sys
import unittest
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_gate_hook as fixtures
import test_capability_store as store_fixtures
from cp_runtime import capability_artifacts as artifacts
from cp_runtime import capability_gate_hook as hook
from cp_runtime.capability_operation import CapabilityOperation
from cp_runtime.capability_operation_workflow import OperationWorkflow
from cp_runtime.capability_store import CapabilityError
from cp_runtime.capability_gate import GatePolicy
from cp_runtime.patch_intent import parse_apply_patch, PatchIntentError
from cp_runtime.patch_scope import classify_patch
from cp_runtime import patch_scope
from cp_runtime import capability_store as store_module
from cp_runtime.common import RuntimeContractError

ROOT = fixtures.ROOT


class ArtifactScopeTests(unittest.TestCase):
    tearDown = fixtures.CapabilityGateHookTests.tearDown
    canonical_patch = fixtures.CapabilityGateHookTests.canonical_patch
    invoke_gate = fixtures.CapabilityGateHookTests.invoke_gate

    def setUp(self):
        fixtures.CapabilityGateHookTests.setUp(self)
        self.policy.set_enabled(True, None)
        self.output = (self.base / "output").resolve()
        self.output.mkdir()
        self.environment = patch.dict(os.environ, {
            "CP_CAPABILITY_GATE_ROOT": str(self.gate_root),
            "CODEX_HOME": str(self.base / "codex"),
            "CODEX_THREAD_ID": "session"})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def call(self, command, call_id="artifact-a", event="PreToolUse", **extra):
        return hook.handle(ROOT, self.canonical_patch(call_id, event, command, **extra))["response"]

    def addition(self, path):
        return "*** Begin Patch\n*** Add File: " + str(path) + "\n+output\n*** End Patch\n"

    def request(self, command, call_id="unregistered"):
        denied = self.call(command, call_id)
        self.assertIn("ARTIFACT_SCOPE_UNREGISTERED", json.dumps(denied))
        return re.search(r"AR1-[0-9a-f]{16}-[0-9a-f]{32}", json.dumps(denied)).group(0)

    def register(self):
        self.request_ref = self.request(self.addition(self.output / "artifact.txt"))
        return artifacts.register_request(self.policy, ROOT, self.request_ref)

    def dispatched(self):
        command = self.canonical_patch()["tool_input"]["command"]
        first = self.call(command, "internal-a")
        ref = re.search(r"OP2-[0-9a-f]{16}-[0-9a-f]{32}", json.dumps(first)).group(0)
        operation = CapabilityOperation.open(self.policy, ref)
        OperationWorkflow(operation).prepare(ref, term="public")
        self.assertEqual({}, self.call(command, "internal-b"))
        return command, operation, ref

    def test_registration_requires_exact_native_request_without_environment_identity(self):
        missing = "AR1-" + "0" * 16 + "-" + "0" * 32
        with self.assertRaisesRegex(CapabilityError, "ARTIFACT_NATIVE_ORIGIN_REQUIRED"):
            artifacts.register_request(self.policy, ROOT, missing)
        request_ref = self.request(self.addition(self.output / "artifact.txt"))
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "other-session"}):
            value = artifacts.register_request(self.policy, ROOT, request_ref)
        self.assertEqual(request_ref, value["request_ref"])
        self.assertEqual(1, len(artifacts._session(self.policy, "session")["roots"]))
        self.assertFalse(artifacts._session_path(self.policy, "other-session").exists())

    def test_management_entry_registers_and_revokes_native_bound_scope(self):
        command = self.addition(self.output / "managed.txt")
        request_ref = self.request(command, "origin-only")
        for action in ("register", "revoke"):
            result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/cp-runtime.py"),
                "capability-task-artifact-" + action, "--profile", str(self.profile),
                "--repo-path", str(self.repo), "--gate-root", str(self.gate_root),
                "--request-ref", request_ref], capture_output=True, text=True,
                encoding="utf-8", timeout=15)
            self.assertEqual(0, result.returncode, result.stderr)
            value = json.loads(result.stdout)
            self.assertEqual("NONE", value["execution_authorization"])
            self.assertEqual("UNCHANGED", value["host_permissions"])
            self.assertEqual(1 if action == "register" else 0, len(value["roots"]))
        self.assertIn("ARTIFACT_SCOPE_UNREGISTERED", json.dumps(self.call(command, "after-revoke")))

    def test_git_ownership_read_failure_reports_host_context_without_weakening_identity(self):
        before = self.policy.read()
        with patch.object(store_module, "validate_binding", side_effect=RuntimeContractError("fixture binding read failed")):
            probe = subprocess.CompletedProcess(["git"], 128, b"", b"fatal: detected dubious ownership in repository")
            with patch.object(store_module.subprocess, "run", return_value=probe):
                with self.assertRaisesRegex(CapabilityError, "PROFILE_HOST_CONTEXT_REQUIRED"):
                    self.store._guard()
            probe = subprocess.CompletedProcess(["git"], 0, b"fixture-root", b"")
            with patch.object(store_module.subprocess, "run", return_value=probe):
                with self.assertRaisesRegex(CapabilityError, "PROFILE_BINDING_INVALID"):
                    self.store._guard()
        self.assertEqual(self.policy.read(), before)

    def test_request_replay_cannot_renew_or_redirect_and_revocation_is_terminal(self):
        initial = self.register()
        self.assertEqual(initial, artifacts.register_request(self.policy, ROOT, self.request_ref))
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/cp-runtime.py"),
            "capability-task-artifact-register", "--profile", str(self.profile),
            "--repo-path", str(self.repo), "--gate-root", str(self.gate_root),
            "--request-ref", self.request_ref, "--artifact-root", str(self.base)],
            capture_output=True, text=True, timeout=15)
        self.assertNotEqual(0, result.returncode)
        artifacts.register_request(self.policy, ROOT, self.request_ref, revoke=True)
        with self.assertRaisesRegex(CapabilityError, "ARTIFACT_REQUEST_REVOKED"):
            artifacts.register_request(self.policy, ROOT, self.request_ref)
        fresh = self.request(self.addition(self.output / "fresh.txt"), "new-request")
        with patch.object(artifacts, "datetime") as clock:
            clock.now.return_value = datetime.now(timezone.utc) + timedelta(minutes=6)
            with self.assertRaisesRegex(CapabilityError, "ARTIFACT_REQUEST_EXPIRED"):
                artifacts.register_request(self.policy, ROOT, fresh)

    def test_registered_output_is_neutral_without_allow_or_operation_pass(self):
        result = self.register()
        self.assertEqual("NONE", result["execution_authorization"])
        command = self.addition(self.output / "artifact.txt")
        self.assertEqual({}, self.call(command))
        (self.output / "artifact.txt").write_text("output", encoding="utf-8")
        self.assertEqual({}, self.call(command, event="PostToolUse", tool_response="Done!"))
        binding = artifacts.call_binding("session", "turn", "artifact-a")
        self.assertEqual("artifact", binding["kind"])
        self.assertIsNone(binding["operation_ref"])
        operation_root = self.profile.parent / "capability-operation"
        self.assertFalse(operation_root.exists())

    def test_external_update_delete_and_move_share_scope(self):
        self.register()
        source = self.output / "old.txt"
        source.write_text("old", encoding="utf-8")
        commands = [
            f"*** Begin Patch\n*** Update File: {source}\n@@\n-old\n+new\n*** End Patch",
            f"*** Begin Patch\n*** Delete File: {source}\n*** End Patch",
            f"*** Begin Patch\n*** Update File: {source}\n*** Move to: {self.output / 'moved.txt'}\n*** End Patch"]
        for i, command in enumerate(commands):
            self.assertEqual({}, self.call(command, "external-" + str(i)))

    def test_plan_attachment_in_chat_visualizations_with_missing_child_directory(self):
        chat_root = (self.base / "codex" / "visualizations" / "2026" / "10" / "15" / "chat-fixture").resolve()
        chat_root.mkdir(parents=True)
        target = chat_root / "plans" / "实施方案（附件）.md"
        command = self.addition(target)
        denied = self.call(command, "plan-origin")
        reason = denied["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("register_native_artifact_request", reason)
        self.assertNotIn("No current process PASS", reason)
        request_ref = re.search(r"AR1-[0-9a-f]{16}-[0-9a-f]{32}", reason).group(0)
        request = artifacts._request(self.policy, request_ref)
        self.assertEqual(str(chat_root), request["root"])
        self.assertFalse(target.parent.exists())
        artifacts.register_request(self.policy, ROOT, request_ref)
        self.assertEqual({}, self.call(command, "plan-write"))
        target.parent.mkdir()
        target.write_text("output\n", encoding="utf-8")
        self.assertEqual({}, self.call(command, "plan-write", "PostToolUse", tool_response="Done!"))
        self.assertEqual("output\n", target.read_text(encoding="utf-8"))
        self.assertTrue(self.policy.read()["enabled"])

    def test_sibling_mixed_and_cross_boundary_moves_are_denied(self):
        self.register()
        sibling_root = self.base.resolve() / "sibling-output"
        sibling_root.mkdir()
        sibling = sibling_root / "sibling.txt"
        self.assertIn("ARTIFACT_SCOPE_UNREGISTERED", json.dumps(self.call(self.addition(sibling))))
        mixed = self.addition(self.output / "artifact.txt").replace(
            "*** End Patch", "*** Add File: local.txt\n+local\n*** End Patch")
        self.assertIn("MIXED_PATH_SCOPE", json.dumps(self.call(mixed)))
        move = f"*** Begin Patch\n*** Update File: app.py\n*** Move to: {self.output / 'app.py'}\n*** End Patch"
        self.assertIn("MIXED_PATH_SCOPE", json.dumps(self.call(move)))

    def test_control_roots_git_roots_and_credentials_cannot_be_registered(self):
        self.register()
        gitroot = self.base.resolve() / "another-repo"
        (gitroot / ".git").mkdir(parents=True)
        credentials = self.base.resolve() / "secrets"
        credentials.mkdir()
        for root in (self.profile.parent, self.gate_root.resolve(), self.repo.resolve(),
                     self.base.resolve(), ROOT, gitroot, credentials):
            with self.subTest(root=root), self.assertRaises((CapabilityError, PatchIntentError)):
                artifacts.create_native_request(self.policy, ROOT, "session", "turn",
                    "denied-root", self.addition(root / "probe.txt"), [root / "probe.txt"], patch_scope.PathBudget())
        runtime = (self.base / "codex" / "runtime" / "output").resolve()
        runtime.mkdir(parents=True)
        with self.assertRaisesRegex(CapabilityError, "CONTROL_PATH_CONFLICT"):
            artifacts.create_native_request(self.policy, ROOT, "session", "turn",
                "denied-runtime", self.addition(runtime / "probe.txt"), [runtime / "probe.txt"], patch_scope.PathBudget())

    def test_new_nested_git_boundary_and_hardlink_are_denied(self):
        self.register()
        nested = self.output / "nested"
        (nested / ".git").mkdir(parents=True)
        self.assertIn("CROSS_REPO_PATH_CONFLICT",
                      json.dumps(self.call(self.addition(nested / "file.txt"))))
        target = self.output / "linked.txt"
        try:
            os.link(self.repo / "app.py", target)
        except OSError as exc:
            self.skipTest("hard links unavailable: " + type(exc).__name__)
        command = f"*** Begin Patch\n*** Update File: {target}\n@@\n-1\n+2\n*** End Patch"
        self.assertIn("HARDLINK_REJECTED", json.dumps(self.call(command)))
        self.assertEqual("def public():\n    return 1\n", (self.repo / "app.py").read_text())

    def test_link_or_reparse_component_is_rejected(self):
        self.register()
        target = self.output / "link"
        try:
            target.symlink_to(self.repo.resolve(), target_is_directory=True)
        except OSError:
            self.skipTest("native symlink creation unavailable")
        self.assertIn("LINK_REJECTED", json.dumps(self.call(self.addition(target / "file.txt"))))

    def test_replaced_expired_or_revoked_root_is_rejected(self):
        self.register()
        command = self.addition(self.output / "artifact.txt")
        with patch.object(artifacts, "datetime") as clock:
            clock.now.return_value = datetime.now(timezone.utc) + timedelta(days=1)
            self.assertIn("ARTIFACT_SCOPE_EXPIRED", json.dumps(self.call(command, "expired-output")))
        self.output.rename(self.output.with_name("previous-output"))
        self.output.mkdir()
        self.assertIn("ARTIFACT_SCOPE_CHANGED", json.dumps(self.call(command, "replaced-output")))
        artifacts.register_request(self.policy, ROOT, self.request_ref, revoke=True)
        self.assertIn("ARTIFACT_SCOPE_UNREGISTERED", json.dumps(self.call(command, "revoked-output")))

    def test_no_tool_input_or_top_level_allowlist_can_register_scope(self):
        command = self.addition(self.output / "file.txt")
        response = self.call(command, artifact_root=str(self.output), writable_roots=[str(self.output)])
        self.assertIn("ARTIFACT_SCOPE_UNREGISTERED", json.dumps(response))
        data = self.canonical_patch(command=command)
        data["tool_input"]["artifact_root"] = str(self.output)
        response = hook.handle(ROOT, data)["response"]
        self.assertIn("OP_CANONICAL_INPUT", json.dumps(response))

    def test_other_projects_control_state_is_protected(self):
        self.register()
        other = SimpleNamespace()
        store_fixtures.CapabilityStoreTests.setUp(other)
        try:
            policy = GatePolicy(other.store, self.gate_root.resolve())
            policy.set_enabled(True, None)
            with self.assertRaisesRegex(CapabilityError, "CONTROL_PATH_CONFLICT"):
                root = other.profile.parent.resolve()
                artifacts.create_native_request(self.policy, ROOT, "session", "turn",
                    "other-control", self.addition(root / "probe.txt"), [root / "probe.txt"], patch_scope.PathBudget())
            policy.set_enabled(False, 0)
            with self.assertRaisesRegex(CapabilityError, "CONTROL_PATH_CONFLICT"):
                root = other.profile.parent.resolve()
                artifacts.create_native_request(self.policy, ROOT, "session", "turn",
                    "other-control", self.addition(root / "probe.txt"), [root / "probe.txt"], patch_scope.PathBudget())
        finally:
            other.temp.cleanup()

    def test_corrupt_scope_and_unbounded_policy_directory_fail_closed(self):
        self.register()
        path = artifacts._session_path(self.policy, "session")
        original = path.read_bytes()
        path.write_bytes(original.replace(b'"roots":', b'"tampered":'))
        self.assertIn("GATE_RECORD_INVALID", json.dumps(self.call(self.addition(self.output / "a.txt"))))
        path.write_bytes(original)
        for i in range(150):
            (self.gate_root / ("unrelated-" + str(i))).write_text("x")
        self.assertIn("PATH_LOOKUP_LIMIT", json.dumps(self.call(self.addition(self.output / "a.txt"))))

    def test_historical_control_alias_does_not_block_unrelated_output_and_preserves_protection(self):
        other = SimpleNamespace()
        store_fixtures.CapabilityStoreTests.setUp(other)
        alias = other.profile.parent
        moved = (self.base / "migrated-control").resolve()
        try:
            policy = GatePolicy(other.store, self.gate_root.resolve())
            policy.set_enabled(True, None)
            policy.set_enabled(False, 0)
            self.assertTrue(alias.resolve().is_relative_to(other.base.resolve()))
            self.assertTrue(moved.resolve().is_relative_to(self.base.resolve()))
            alias.rename(moved)
            try:
                alias.symlink_to(moved.resolve(), target_is_directory=True)
            except OSError:
                self.skipTest("native control alias creation unavailable")
            self.register()
            self.assertEqual({}, self.call(self.addition(self.output / "safe.txt"), "safe-after-migration"))
            with self.assertRaisesRegex(CapabilityError, "CONTROL_PATH_CONFLICT"):
                target = moved / "protected.txt"
                artifacts.create_native_request(self.policy, ROOT, "session", "turn", "real-control",
                    self.addition(target), [target], patch_scope.PathBudget())
            self.assertIn("LINK_REJECTED", json.dumps(self.call(self.addition(alias / "protected.txt"), "alias-target")))
            alias.unlink()
            alias.symlink_to(self.output, target_is_directory=True)
            self.assertIn("CONTROL_PATH_CONFLICT", json.dumps(
                self.call(self.addition(self.output / "became-control.txt"), "retargeted-control")))
        finally:
            if alias.is_symlink():
                alias.unlink()
            other.temp.cleanup()

    def test_control_alias_resolution_is_bounded_and_cannot_admit_linked_write_targets(self):
        alias = self.output / "alias"
        try:
            alias.symlink_to(self.output, target_is_directory=True)
        except OSError:
            self.skipTest("native alias creation unavailable")
        budget = patch_scope.PathBudget()
        self.assertEqual((alias, self.output), budget.control_path(str(alias), self.repo))
        with self.assertRaisesRegex(PatchIntentError, "LINK_REJECTED"):
            budget.resolve(str(alias / "probe.txt"), self.repo)
        with patch.object(patch_scope.os, "readlink", return_value=str(alias)):
            with self.assertRaisesRegex(PatchIntentError, "CONTROL_ALIAS_LIMIT"):
                patch_scope.PathBudget().control_path(str(alias), self.repo)
        with patch.object(patch_scope.os, "readlink", return_value="//server/share"):
            with self.assertRaisesRegex(PatchIntentError, "CONTROL_ALIAS_NONLOCAL"):
                patch_scope.PathBudget().control_path(str(alias), self.repo)

    def test_remote_registered_scope_requires_no_network_probe_and_cannot_be_a_write_target(self):
        remote = "//wsl.localhost/SyntheticDistribution/home/project"
        budget = patch_scope.PathBudget()
        with patch.object(budget, "stat", side_effect=AssertionError("unexpected network lookup")):
            self.assertEqual((Path(remote), Path(remote)), budget.control_path(remote, self.repo))
        with self.assertRaisesRegex(PatchIntentError, "INVALID_PATH"):
            patch_scope.PathBudget().resolve(remote + "/file.txt", self.repo)
        for invalid in ("//?/C:/local", "//server/share/../control", "//server/share//control"):
            with self.subTest(invalid=invalid), self.assertRaises(PatchIntentError):
                patch_scope.PathBudget().control_path(invalid, self.repo)

    def test_reparse_attribute_rejection_without_privilege_dependency(self):
        candidate = self.output / "junction"
        actual = patch_scope.native_path
        def file_object(path):
            if path == candidate:
                return SimpleNamespace(lstat=lambda: SimpleNamespace(st_mode=0o40755, st_file_attributes=0x400))
            return actual(path)
        with patch.object(patch_scope, "native_path", side_effect=file_object):
            with self.assertRaisesRegex(PatchIntentError, "LINK_REJECTED"):
                classify_patch(self.addition(candidate / "a.txt"), self.repo.resolve(), self.repo.resolve())

    def test_relative_paths_use_native_subdirectory_for_sources_and_moves(self):
        sub = self.repo.resolve() / "nested"
        sub.mkdir()
        (sub / "app.py").write_bytes(b"nested\n")
        command = "*** Begin Patch\n*** Update File: app.py\n*** Move to: moved.py\n*** End Patch"
        intent = parse_apply_patch(command, self.repo, cwd=sub)
        self.assertEqual(["nested/app.py", "nested/moved.py"], intent["target_paths"])
        denied = self.call(command, "nested-a", cwd=str(sub))
        ref = re.search(r"OP2-[0-9a-f]{16}-[0-9a-f]{32}", json.dumps(denied)).group(0)
        operation = CapabilityOperation.open(self.policy, ref)
        self.assertEqual(intent["target_paths"], operation.check(ref)["targets"])

    def test_post_changed_to_external_command_converges_original_operation(self):
        command, operation, ref = self.dispatched()
        response = self.call(self.addition(self.output / "file.txt"), "internal-b",
                             "PostToolUse", tool_response="Done!")
        self.assertEqual("block", response["decision"])
        self.assertEqual("OUTCOME_UNKNOWN", operation.check(ref)["state"])

    def test_post_changed_to_unconfigured_cwd_converges_original_operation(self):
        command, operation, ref = self.dispatched()
        response = self.call(command, "internal-b", "PostToolUse",
                             cwd=str(self.output), tool_response="Done!")
        self.assertEqual("block", response["decision"])
        self.assertEqual("OUTCOME_UNKNOWN", operation.check(ref)["state"])

    def test_native_hook_process_preserves_neutral_output_contract(self):
        self.register()
        command = self.addition(self.output / "process.txt")
        self.assertEqual({}, self.invoke_gate("PreToolUse", tool_name="apply_patch",
                         tool_use_id="process-output", tool_input={"command": command}))
        self.assertEqual({}, self.invoke_gate("PostToolUse", tool_name="apply_patch",
                         tool_use_id="process-output", tool_input={"command": command},
                         tool_response="native execution still belongs to host"))

    def test_path_limits_and_ambiguous_forms_fail_closed(self):
        for value in ("../escape.txt", "nested/../escape.txt", "./file.txt", "~/file.txt",
                      "//server/share/file.txt", "C:relative.txt", "name.txt:stream", "space."):
            with self.subTest(value=value), self.assertRaises(PatchIntentError):
                classify_patch(self.addition(value), self.repo.resolve(), self.repo.resolve())
        with patch.object(patch_scope, "MAX_NODES", 1), self.assertRaisesRegex(PatchIntentError, "PATH_LOOKUP_LIMIT"):
            classify_patch(self.addition(self.output / "file.txt"), self.repo.resolve(), self.repo.resolve())
        with patch.object(patch_scope, "MAX_SECONDS", 0), self.assertRaisesRegex(PatchIntentError, "PATH_LOOKUP_LIMIT"):
            classify_patch(self.addition(self.output / "file.txt"), self.repo.resolve(), self.repo.resolve())
        excessive = "*** Begin Patch\n" + "".join(
            f"*** Add File: item-{i}.txt\n+x\n" for i in range(65)) + "*** End Patch"
        with self.assertRaisesRegex(PatchIntentError, "TOO_MANY_TARGETS"):
            classify_patch(excessive, self.repo.resolve(), self.repo.resolve())


if __name__ == "__main__":
    unittest.main()
