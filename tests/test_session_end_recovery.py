from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import traceback
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from cp_runtime.event_v3 import make_event, verify_event_chain
from cp_runtime.integrity import init_keyring, verify_event_seals
from cp_runtime import seal_queue


class SessionEndRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="cp-session-end-recovery-")
        self.root = Path(self.temporary.name)
        self.primary = self.root / "primary"
        self.project_id = "session-end-recovery"
        self.repo = "sha256:" + "a" * 64
        self.queue = self.primary / self.project_id / "feedback" / "seal-queue-v3"
        self.previous = {name: os.environ.get(name) for name in ("CP_ASSISTANT_DATA", "TEMP", "TMP")}
        os.environ.update({"CP_ASSISTANT_DATA": str(self.primary), "TEMP": str(self.root), "TMP": str(self.root)})
        self.secret_patch = mock.patch.multiple(
            seal_queue,
            active_secret=mock.Mock(return_value=({}, b"x" * 32, "test-key")),
            secret_by_id=mock.Mock(return_value=({}, b"x" * 32)),
            seal_event_chain=mock.Mock(return_value={"seal_status": "SEALED_CURRENT", "sealed_record_count": 1}),
        )
        self.secret_patch.start()

    def tearDown(self) -> None:
        self.secret_patch.stop()
        for name, value in self.previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.temporary.cleanup()

    def event(self, suffix: str = "one") -> dict[str, object]:
        return make_event({
            "event_type": "SESSION_ENDED", "event_id": "END-" + suffix,
            "session_id": "session-" + suffix, "turn_id": "turn-" + suffix,
            "task_id": "task-" + suffix, "project_id": self.project_id,
            "repo_fingerprint": self.repo, "terminal_outcome": "UNKNOWN",
            "metadata": {"seal_required": True},
        })

    @property
    def fallback_root(self) -> Path:
        return self.root / seal_queue.TEMPORARY_V7_NAME / "project-context"

    def recovery_paths(self) -> tuple[Path, Path, Path]:
        return seal_queue._recovery_paths(self.fallback_root, self.project_id)

    def receipt_path(self, root: Path, event: dict[str, object]) -> Path:
        return seal_queue._receipt_path(root, event)

    def test_preappend_permission_failure_uses_v7_and_pins_later_events(self) -> None:
        original = seal_queue._preappend_boundary

        def deny_primary(event_path: Path) -> None:
            if self.primary in event_path.parents:
                raise seal_queue._PreAppendPermissionDenied()
            original(event_path)

        event = self.event()
        with mock.patch.object(seal_queue, "_preappend_boundary", side_effect=deny_primary):
            result = seal_queue.prepare_session_end_with_recovery(self.queue, event)
        fallback_queue = self.fallback_root / self.project_id / "feedback" / "seal-queue-v3"
        self.assertEqual(str(fallback_queue), result["queue"])
        self.assertEqual(1, verify_event_chain(fallback_queue.parent / "task-outcome-v3.jsonl")["record_count"])
        route, _receipt_directory, _guard = self.recovery_paths()
        receipt = self.receipt_path(self.fallback_root, event)
        self.assertTrue(route.exists())
        self.assertEqual("PENDING_SEAL", json.loads(receipt.read_text(encoding="utf-8"))["recovery_status"])
        self.assertEqual(fallback_queue.parent / "task-outcome-v3.jsonl",
                         seal_queue.resolve_event_path({**event, "event_type": "TURN_OPENED"}, self.queue))
        seal_queue.process_queue(fallback_queue, max_jobs=1)
        self.assertEqual("SEALED_CURRENT", json.loads(receipt.read_text(encoding="utf-8"))["recovery_status"])

    def test_append_attempt_permission_never_replays_to_fallback(self) -> None:
        event = self.event("append")
        with mock.patch.object(seal_queue, "append_event", side_effect=PermissionError("append denied")):
            with self.assertRaises(PermissionError):
                seal_queue.prepare_session_end_with_recovery(self.queue, event)
        self.assertFalse((self.fallback_root / self.project_id / "feedback" / "task-outcome-v3.jsonl").exists())
        receipt = self.receipt_path(self.primary, event)
        self.assertEqual("APPEND_OR_LATER", json.loads(receipt.read_text(encoding="utf-8"))["stage"])

    def test_enqueue_and_seal_failures_keep_the_original_chain(self) -> None:
        event = self.event("enqueue")
        with mock.patch.object(seal_queue, "enqueue_session_end", side_effect=PermissionError("enqueue denied")):
            with self.assertRaises(PermissionError):
                seal_queue.prepare_session_end_with_recovery(self.queue, event)
        primary_event = self.queue.parent / "task-outcome-v3.jsonl"
        self.assertEqual(1, verify_event_chain(primary_event)["record_count"])
        self.assertFalse((self.fallback_root / self.project_id / "feedback" / "task-outcome-v3.jsonl").exists())

        queued = seal_queue.enqueue_session_end(self.queue, self.event("seal"))
        self.assertTrue(queued["enqueued"])
        with mock.patch.object(seal_queue, "seal_event_chain", side_effect=PermissionError("seal denied")):
            for _ in range(3):
                report = seal_queue.process_queue(self.queue, max_jobs=1)
        self.assertFalse(report["ok"])
        receipt = self.receipt_path(self.primary, self.event("seal"))
        self.assertEqual("QUEUED_APPEND_OR_SEAL", json.loads(receipt.read_text(encoding="utf-8"))["stage"])
        self.assertFalse((self.fallback_root / self.project_id / "feedback" / "task-outcome-v3.jsonl").exists())

    def test_concurrent_duplicate_preappend_recovery_creates_one_terminal_event(self) -> None:
        original = seal_queue._preappend_boundary

        def deny_primary(event_path: Path) -> None:
            if self.primary in event_path.parents:
                raise seal_queue._PreAppendPermissionDenied()
            original(event_path)

        event = self.event("duplicate")
        reports: list[dict[str, object]] = []
        failures: list[str] = []

        def run() -> None:
            try:
                reports.append(seal_queue.prepare_session_end_with_recovery(self.queue, event))
            # 中文：把两个线程的失败完整堆栈一并交给下方断言。
            # English: Preserve both full failure traces for the assertion below.
            except BaseException:
                failures.append(traceback.format_exc())

        with mock.patch.object(seal_queue, "_preappend_boundary", side_effect=deny_primary):
            threads = [threading.Thread(target=run), threading.Thread(target=run)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(10)
        self.assertFalse(failures, "\n".join(failures))
        self.assertEqual(2, len(reports))
        fallback_event = self.fallback_root / self.project_id / "feedback" / "task-outcome-v3.jsonl"
        self.assertEqual(1, verify_event_chain(fallback_event)["record_count"])

    def test_dual_histories_remain_separate_after_the_project_pin(self) -> None:
        primary_event = self.queue.parent / "task-outcome-v3.jsonl"
        seal_queue.append_event(primary_event, make_event({
            "event_type": "TURN_OPENED", "event_id": "PRIMARY-OPEN", "session_id": "primary",
            "turn_id": "primary", "task_id": "primary", "project_id": self.project_id,
            "repo_fingerprint": self.repo,
        }))
        original = seal_queue._preappend_boundary

        def deny_primary(event_path: Path) -> None:
            if self.primary in event_path.parents:
                raise seal_queue._PreAppendPermissionDenied()
            original(event_path)

        with mock.patch.object(seal_queue, "_preappend_boundary", side_effect=deny_primary):
            seal_queue.prepare_session_end_with_recovery(self.queue, self.event("dual-history"))
        fallback_event = self.fallback_root / self.project_id / "feedback" / "task-outcome-v3.jsonl"
        self.assertEqual(1, verify_event_chain(primary_event)["record_count"])
        self.assertEqual(1, verify_event_chain(fallback_event)["record_count"])

    def test_running_job_recovers_after_worker_restart_without_a_duplicate(self) -> None:
        event = self.event("restart")
        seal_queue.prepare_session_end_with_recovery(self.queue, event)
        pending = next((self.queue / "pending").glob("job-*.json"))
        job = seal_queue._load(pending)
        job.update(state="running", attempt=1, lease_epoch=1, lease_pid=999999,
                   lease_process_identity="proc-start:stale")
        seal_queue._atomic_json(pending, seal_queue._resign(job, None))
        running = self.queue / "running" / pending.name
        os.replace(pending, running)
        report = seal_queue.process_queue(self.queue, max_jobs=2)
        self.assertTrue(report["ok"])
        self.assertEqual(1, verify_event_chain(self.queue.parent / "task-outcome-v3.jsonl")["record_count"])
        self.assertEqual(1, len(list((self.queue / "done").glob("job-*.json"))))

    def test_both_roots_denied_is_explicit_and_legacy_v6_queue_still_works(self) -> None:
        event = self.event("both-denied")
        with mock.patch.object(seal_queue, "_preappend_boundary", side_effect=seal_queue._PreAppendPermissionDenied()):
            with self.assertRaisesRegex(seal_queue.SealQueueError, "SESSION_END_FALLBACK_UNAVAILABLE"):
                seal_queue.prepare_session_end_with_recovery(self.queue, event)

        legacy = self.root / seal_queue.TEMPORARY_V6_NAME / "project-context" / self.project_id / "feedback" / "seal-queue-v3"
        result = seal_queue.prepare_session_end_with_recovery(legacy, self.event("legacy"))
        self.assertEqual(str(legacy), result["queue"])
        self.assertEqual(1, verify_event_chain(legacy.parent / "task-outcome-v3.jsonl")["record_count"])

    def test_invalid_route_is_not_an_alternate_root_recovery(self) -> None:
        route, _receipt, _guard = self.recovery_paths()
        route.parent.mkdir(parents=True)
        route.write_text("{not-json", encoding="utf-8")
        with self.assertRaisesRegex(seal_queue.SealQueueError, "RECOVERY_ROUTE_INVALID"):
            seal_queue.prepare_session_end_with_recovery(self.queue, self.event("invalid-route"))
        self.assertFalse((self.fallback_root / self.project_id / "feedback" / "task-outcome-v3.jsonl").exists())

    def test_route_read_is_bounded_and_rejects_intermediate_reparse(self) -> None:
        route, _receipts, _guard = self.recovery_paths()
        route.parent.mkdir(parents=True)
        route.write_bytes(b" " * (seal_queue.RECOVERY_RECORD_MAX_BYTES + 1))
        with self.assertRaisesRegex(seal_queue.SealQueueError, "RECOVERY_ROUTE_INVALID"):
            seal_queue.prepare_session_end_with_recovery(self.queue, self.event("oversized-route"))
        with mock.patch.object(seal_queue, "_is_reparse", side_effect=lambda path: path.name == "feedback"):
            with self.assertRaisesRegex(seal_queue.SealQueueError, "RECOVERY_PATH_UNSAFE"):
                seal_queue.prepare_session_end_with_recovery(self.queue, self.event("reparse-route"))

    def test_distinct_failure_identities_keep_distinct_bounded_receipts(self) -> None:
        first, second = self.event("receipt-one"), self.event("receipt-two")
        with mock.patch.object(seal_queue, "append_event", side_effect=PermissionError("append denied")):
            for event in (first, second):
                with self.assertRaises(PermissionError):
                    seal_queue.prepare_session_end_with_recovery(self.queue, event)
        first_path = self.receipt_path(self.primary, first)
        second_path = self.receipt_path(self.primary, second)
        self.assertNotEqual(first_path, second_path)
        self.assertTrue(first_path.exists())
        self.assertTrue(second_path.exists())

    def test_root_role_collision_rejects_equal_and_nested_configured_data_roots(self) -> None:
        roots = (
            self.root,
            self.fallback_root,
            self.fallback_root / "nested",
            self.root / seal_queue.TEMPORARY_V6_NAME / "project-context",
        )
        for configured in roots:
            with mock.patch.dict(os.environ, {"CP_ASSISTANT_DATA": str(configured)}):
                with self.assertRaisesRegex(seal_queue.SealQueueError, "RECOVERY_ROOT_ROLE_COLLISION"):
                    seal_queue._managed_roots()

    def test_recovery_reenqueues_original_chain_event_without_reappend(self) -> None:
        event = self.event("recover")
        with mock.patch.object(seal_queue, "enqueue_session_end", side_effect=PermissionError("enqueue denied")):
            with self.assertRaises(PermissionError):
                seal_queue.prepare_session_end_with_recovery(self.queue, event)
        recovered = seal_queue.recover_pending_session_end(self.queue)
        self.assertEqual(1, recovered["enqueued"])
        self.assertEqual(1, verify_event_chain(self.queue.parent / "task-outcome-v3.jsonl")["record_count"])

    def test_recovery_receipt_tampering_never_creates_a_job(self) -> None:
        event = self.event("tamper-receipt")
        event_path = self.queue.parent / "task-outcome-v3.jsonl"
        stored = seal_queue.append_event(event_path, event)
        receipt_path = self.receipt_path(self.primary, stored)
        for field, value in (
            ("identity_ref", "sha256:" + "0" * 64),
            ("repo_fingerprint", "sha256:" + "1" * 64),
            ("stage", "SEALED"),
            ("recovery_status", "PENDING_SEAL"),
            ("record_hash", "0" * 64),
            ("receipt_hmac_sha256", "0" * 64),
        ):
            seal_queue._write_recovery_receipt(self.primary, stored, original_root=self.primary,
                                               stage="ENQUEUE_FAILED_AFTER_APPEND",
                                               error_category="WORKER_OPERATION_FAILED",
                                               status="ORIGINAL_CHAIN_RECOVERY_REQUIRED", record=stored)
            value_before = json.loads(receipt_path.read_text(encoding="utf-8"))
            value_before[field] = value
            receipt_path.write_text(json.dumps(value_before), encoding="utf-8")
            with self.assertRaises(seal_queue.SealQueueError):
                seal_queue.recover_pending_session_end(self.queue)
            self.assertFalse(any(self.queue.rglob("job-*.json")))
        seal_queue._write_recovery_receipt(self.primary, stored, original_root=self.primary,
                                           stage="ENQUEUE_FAILED_AFTER_APPEND",
                                           error_category="WORKER_OPERATION_FAILED",
                                           status="ORIGINAL_CHAIN_RECOVERY_REQUIRED", record=stored)
        renamed = receipt_path.with_name("receipt-" + "f" * 64 + ".json")
        receipt_path.rename(renamed)
        with self.assertRaisesRegex(seal_queue.SealQueueError, "RECOVERY_RECEIPT_FILENAME_INVALID"):
            seal_queue.recover_pending_session_end(self.queue)
        self.assertFalse(any(self.queue.rglob("job-*.json")))

    def test_untrusted_keyless_diagnostic_is_never_promoted_to_recovery(self) -> None:
        event = self.event("keyless")
        event_path = self.queue.parent / "feedback" / "task-outcome-v3.jsonl"
        stored = seal_queue.append_event(event_path, event)
        with mock.patch.object(seal_queue, "active_secret", side_effect=RuntimeError("key unavailable")):
            seal_queue._write_recovery_receipt(self.primary, stored, original_root=self.primary,
                                               stage="ENQUEUE_FAILED_AFTER_APPEND",
                                               error_category="WORKER_OPERATION_FAILED",
                                               status="ORIGINAL_CHAIN_RECOVERY_REQUIRED", record=stored)
        receipt = json.loads(self.receipt_path(self.primary, stored).read_text(encoding="utf-8"))
        self.assertEqual("DIAGNOSTIC_ONLY", receipt["recovery_eligibility"])
        self.assertEqual("TRUSTED_BOOTSTRAP_REQUIRED", receipt["recovery_status"])
        self.assertEqual(0, seal_queue.recover_pending_session_end(self.queue)["enqueued"])
        self.assertFalse(any(self.queue.rglob("job-*.json")))

    def test_worker_recover_pending_reuses_original_event_with_an_isolated_keyring(self) -> None:
        event = self.event("worker-recover")
        event_path = self.queue.parent / "task-outcome-v3.jsonl"
        stored = seal_queue.append_event(event_path, event)
        keyring = self.root / "worker-keyring.json"
        init_keyring(keyring)
        self.secret_patch.stop()
        try:
            seal_queue._write_recovery_receipt(self.primary, stored, original_root=self.primary,
                                               stage="ENQUEUE_FAILED_AFTER_APPEND",
                                               error_category="WORKER_OPERATION_FAILED",
                                               status="ORIGINAL_CHAIN_RECOVERY_REQUIRED",
                                               record=stored, keyring_path=keyring)
        finally:
            self.secret_patch.start()
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(self.root / "worker-codex-home")
        completed = subprocess.run([
            sys.executable, "-B", str(ROOT / "hooks" / "seal_worker.py"), "--queue", str(self.queue),
            "--keyring", str(keyring), "--recover-pending", "--max-jobs", "2",
        ], env=environment, text=True, capture_output=True, timeout=15)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(1, json.loads(completed.stdout)["recovery"]["enqueued"])
        self.assertEqual(1, verify_event_chain(event_path)["record_count"])
        self.assertEqual("SEALED_CURRENT", verify_event_seals(event_path, keyring_path=keyring)["seal_status"])

    def test_hook_startup_failure_stays_nonblocking_and_never_persists_in_parent(self) -> None:
        spec = importlib.util.spec_from_file_location("cp_hook_session_end_recovery", ROOT / "hooks" / "cp_hook.py")
        hook = importlib.util.module_from_spec(spec); assert spec.loader
        spec.loader.exec_module(hook)
        event = self.event("launch")
        event_path = self.queue.parent / "task-outcome-v3.jsonl"
        with mock.patch.object(hook, "launch_worker", side_effect=OSError("launch denied")), \
             mock.patch.object(hook, "_session_end_diagnostic") as diagnostic, \
             mock.patch.object(hook, "append_event", side_effect=AssertionError("parent must not append")):
            hook._enqueue_and_launch(event_path, event)
        diagnostic.assert_called_once_with(event, "SEAL_WORKER_LAUNCH_FAILED")
        self.assertFalse(event_path.exists())

    def test_hook_uses_the_single_source_identity_helper(self) -> None:
        spec = importlib.util.spec_from_file_location("cp_hook_identity_helper", ROOT / "hooks" / "cp_hook.py")
        hook = importlib.util.module_from_spec(spec); assert spec.loader
        spec.loader.exec_module(hook)
        with mock.patch.object(hook, "project_identity_for", return_value=(self.repo, self.project_id)) as identity, \
             mock.patch.object(hook, "stable_repo_fingerprint", side_effect=AssertionError("legacy double lookup")), \
             mock.patch.object(hook, "project_id_for", side_effect=AssertionError("legacy double lookup")):
            event = hook._event({"hook_event_name": "Stop", "cwd": str(self.root), "session_id": "S", "turn_id": "T"})
        self.assertEqual(self.repo, event["repo_fingerprint"])
        self.assertEqual(self.project_id, event["project_id"])
        identity.assert_called_once_with(str(self.root))

    def test_hook_regular_lifecycle_uses_the_root_selection_append_entrypoint(self) -> None:
        spec = importlib.util.spec_from_file_location("cp_hook_lifecycle_selection", ROOT / "hooks" / "cp_hook.py")
        hook = importlib.util.module_from_spec(spec); assert spec.loader
        spec.loader.exec_module(hook)
        event = self.event("regular-lifecycle") | {"event_type": "TURN_OPENED"}
        with mock.patch.object(hook, "_event", return_value=event), \
             mock.patch.object(hook, "append_lifecycle_event") as append, \
             mock.patch.object(hook, "append_event", side_effect=AssertionError("bypasses root selection")):
            hook._observe({"hook_event_name": "UserPromptSubmit"})
        append.assert_called_once()

    def test_real_worker_subprocess_writes_a_body_free_original_chain_receipt(self) -> None:
        # 中文：故意不提供可用密钥环，子进程追加后在入队阶段失败。
        # English: No usable keyring is provided: the child appends, then enqueue fails.
        event = self.event("subprocess")
        encoded = base64.urlsafe_b64encode(json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")).decode("ascii")
        environment = os.environ.copy()
        environment.pop("CP_ASSISTANT_KEYRING_PATH", None)
        environment["CODEX_HOME"] = str(self.root / "worker-codex-home")
        completed = subprocess.run([
            sys.executable, "-B", str(ROOT / "hooks" / "seal_worker.py"), "--queue", str(self.queue),
            "--bootstrap-event-b64", encoded, "--max-jobs", "1",
        ], env=environment, text=True, capture_output=True, timeout=15)
        self.assertNotEqual(0, completed.returncode)
        receipt = self.receipt_path(self.primary, event)
        value = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual("TRUSTED_BOOTSTRAP_REQUIRED", value["recovery_status"])
        self.assertNotIn("session-subprocess", json.dumps(value))
