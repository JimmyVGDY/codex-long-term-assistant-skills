from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from cp_runtime.event_archive import archive_closed_segments, capacity_report, health_overview, verify_archive
from cp_runtime.event_v2 import OwnerTokenLock, append_event, event_segment_paths, make_event, read_event_chain, verify_event_chain
from cp_runtime.evolution.observation import ObservationError, observe_project
from cp_runtime.integrity import IntegrityError, init_keyring, rotate_key, seal_event_chain, verify_event_seals, verify_keyring
from cp_runtime.model_evidence import verify_hook_runtime_evidence
from cp_runtime.seal_queue import SealQueueError, enqueue_session_end, launch_worker, prepare_session_end, process_queue
from cp_runtime import seal_queue as seal_queue_module
from cp_runtime.atomic_io import replace_with_retry


def _event(path: str, index: int, project: str, repo: str) -> None:
    append_event(Path(path), make_event({"event_id": "EVT-%03d" % index, "event_type": "TURN_OPENED",
                                        "session_id": "S", "turn_id": "T-%d" % index,
                                        "task_id": "TASK-%d" % index, "project_id": project,
                                        "repo_fingerprint": repo}))


def _rotate(path: str) -> None:
    rotate_key("event-hmac", Path(path))


def _hold_lock(path: str, ready: multiprocessing.synchronize.Event) -> None:
    with OwnerTokenLock(Path(path), timeout=5):
        ready.set()
        time.sleep(60)


def _crash_rotate(path: str, point: str) -> None:
    os.environ["CP_ASSISTANT_TEST_KEYRING_HARD_CRASH_POINT"] = point
    rotate_key("event-hmac", Path(path))


def _crash_worker(queue: str, keyring: str, data_root: str, point: str) -> None:
    os.environ["CP_ASSISTANT_DATA"] = data_root
    os.environ["CP_ASSISTANT_TEST_SEAL_WORKER_HARD_CRASH_POINT"] = point
    process_queue(Path(queue), Path(keyring), 1)


def _archive_worker(event_file: str) -> None:
    archive_closed_segments(Path(event_file))


def _crash_seal(event_file: str, keyring: str, point: str) -> None:
    os.environ["CP_ASSISTANT_TEST_SEAL_HARD_CRASH_POINT"] = point
    seal_event_chain(Path(event_file), keyring_path=Path(keyring))


def _load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec); assert spec.loader
    spec.loader.exec_module(module); return module


def _load_hook(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "hooks" / "cp_hook.py")
    module = importlib.util.module_from_spec(spec); assert spec.loader
    spec.loader.exec_module(module); return module


class V66RuntimeDeepeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="cp-v66-")
        self.root = Path(self.temporary.name)
        self.project_id = "project-v66"
        self.repo = "sha256:" + "6" * 64
        self.data = self.root / "data"
        self.project = self.data / self.project_id
        self.event_file = self.project / "feedback" / "task-outcome-v2.jsonl"
        self.queue = self.project / "feedback" / "seal-queue"
        self.keyring = self.root / "keyring.json"
        init_keyring(self.keyring)
        self.original_data = os.environ.get("CP_ASSISTANT_DATA")
        os.environ["CP_ASSISTANT_DATA"] = str(self.data)

    def tearDown(self) -> None:
        if self.original_data is None:
            os.environ.pop("CP_ASSISTANT_DATA", None)
        else:
            os.environ["CP_ASSISTANT_DATA"] = self.original_data
        self.temporary.cleanup()

    def base_event(self, event_type: str, event_id: str, **extra):
        value = {"event_id": event_id, "event_type": event_type, "session_id": "S1",
                 "turn_id": "T1", "task_id": "TASK1", "project_id": self.project_id,
                 "repo_fingerprint": self.repo, "terminal_outcome": "UNKNOWN"}
        value.update(extra)
        return make_event(value)

    def test_host_attestation_requires_trust_anchor_binding_and_freshness(self) -> None:
        now = datetime.now(timezone.utc)
        data = {"hook_event_name": "SubagentStart", "session_id": "S", "turn_id": "T",
                "agent_id": "A", "actual_model": "gpt-5.6-luna", "actual_reasoning_effort": "low"}
        unsigned = {"schema_version": "1.0", "issuer": "codex-host", "attestation_id": "A" * 32,
                    "issued_at": (now - timedelta(seconds=1)).isoformat(),
                    "expires_at": (now + timedelta(seconds=30)).isoformat(),
                    "hook_event_name": "SubagentStart", "session_id": "S", "turn_id": "T",
                    "agent_id": "A", "actual_model": "gpt-5.6-luna", "actual_reasoning_effort": "low"}
        old = os.environ.pop("CP_ASSISTANT_HOST_ATTESTATION_KEY", None)
        try:
            data["host_runtime_attestation"] = dict(unsigned, signature="invalid")
            self.assertEqual("UNAVAILABLE", verify_hook_runtime_evidence(data, "SubagentStart", now)["status"])
            os.environ["CP_ASSISTANT_HOST_ATTESTATION_KEY"] = "host-test-anchor"
            signature = hmac.new(b"host-test-anchor", json.dumps(unsigned, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")).encode("utf-8"), hashlib.sha256).hexdigest()
            data["host_runtime_attestation"] = dict(unsigned, signature=signature)
            self.assertEqual("VERIFIED", verify_hook_runtime_evidence(data, "SubagentStart", now)["status"])
            changed = dict(data, actual_model="gpt-5.6-terra")
            self.assertEqual("UNAVAILABLE", verify_hook_runtime_evidence(changed, "SubagentStart", now)["status"])
            expired = dict(unsigned, issued_at=(now - timedelta(minutes=10)).isoformat(),
                           expires_at=(now - timedelta(minutes=9)).isoformat())
            expired["signature"] = hmac.new(b"host-test-anchor", json.dumps(expired, ensure_ascii=False,
                sort_keys=True, separators=(",", ":")).encode("utf-8"), hashlib.sha256).hexdigest()
            data["host_runtime_attestation"] = expired
            self.assertEqual("UNAVAILABLE", verify_hook_runtime_evidence(data, "SubagentStart", now)["status"])
        finally:
            if old is None: os.environ.pop("CP_ASSISTANT_HOST_ATTESTATION_KEY", None)
            else: os.environ["CP_ASSISTANT_HOST_ATTESTATION_KEY"] = old

    def test_model_switch_without_fresh_attestation_never_reuses_prior_runtime_evidence(self) -> None:
        now = datetime.now(timezone.utc)
        previous = {"hook_event_name": "SubagentStart", "session_id": "S", "turn_id": "T1",
                    "agent_id": "A", "actual_model": "gpt-5.6-luna",
                    "actual_reasoning_effort": "low"}
        switched = dict(previous, turn_id="T2", actual_model="gpt-6-astra")
        self.assertEqual("UNAVAILABLE", verify_hook_runtime_evidence(previous, "SubagentStart", now)["status"])
        result = verify_hook_runtime_evidence(switched, "SubagentStart", now)
        self.assertEqual("UNAVAILABLE", result["status"])
        self.assertNotEqual("VERIFIED", result["status"])

    def test_true_spawn_multiprocess_append_and_rotate(self) -> None:
        context = multiprocessing.get_context("spawn")
        processes = [context.Process(target=_event, args=(str(self.event_file), i, self.project_id, self.repo))
                     for i in range(8)]
        for process in processes: process.start()
        for process in processes: process.join(20); self.assertEqual(0, process.exitcode)
        self.assertEqual(8, verify_event_chain(self.event_file)["record_count"])
        rotations = [context.Process(target=_rotate, args=(str(self.keyring),)) for _ in range(3)]
        for process in rotations: process.start()
        for process in rotations: process.join(20); self.assertEqual(0, process.exitcode)
        state = verify_keyring(self.keyring)
        self.assertEqual(4, state["purposes"]["event-hmac"]["key_count"])
        self.assertEqual(1, state["purposes"]["event-hmac"]["statuses"].count("ACTIVE"))

    def test_force_termination_releases_native_lock(self) -> None:
        context = multiprocessing.get_context("spawn")
        ready = context.Event()
        process = context.Process(target=_hold_lock, args=(str(self.event_file), ready))
        process.start(); self.assertTrue(ready.wait(10))
        process.terminate(); process.join(10); self.assertIsNotNone(process.exitcode)
        started = time.perf_counter()
        with OwnerTokenLock(self.event_file, timeout=1):
            pass
        self.assertLess(time.perf_counter() - started, 1.0)

    def test_power_loss_rotation_points_leave_old_or_new_valid_keyring(self) -> None:
        context = multiprocessing.get_context("spawn")
        for point in ("AFTER_TEMP_FSYNC", "BEFORE_REPLACE", "AFTER_REPLACE"):
            process = context.Process(target=_crash_rotate, args=(str(self.keyring), point))
            process.start(); process.join(20)
            self.assertEqual(93, process.exitcode)
            state = verify_keyring(self.keyring)
            self.assertEqual(1, state["purposes"]["event-hmac"]["statuses"].count("ACTIVE"))

    def test_power_loss_seal_publish_leaves_old_or_new_valid_chain(self) -> None:
        append_event(self.event_file, self.base_event("TURN_OPENED", "SEAL-BASE"))
        seal_event_chain(self.event_file, keyring_path=self.keyring)
        append_event(self.event_file, self.base_event("TASK_COMPLETED", "SEAL-NEXT"))
        context = multiprocessing.get_context("spawn")
        for point in ("AFTER_TEMP_FSYNC", "BEFORE_REPLACE", "AFTER_REPLACE"):
            process = context.Process(target=_crash_seal,
                args=(str(self.event_file), str(self.keyring), point))
            process.start(); process.join(20)
            self.assertEqual(95, process.exitcode, point)
            state = verify_event_seals(self.event_file, keyring_path=self.keyring)
            self.assertIn(state["seal_status"],
                          {"SEALED_CURRENT", "VALID_SEALED_PREFIX_WITH_UNSEALED_TAIL"})

    def test_signed_queue_recovers_crash_after_append_without_duplicate_event(self) -> None:
        append_event(self.event_file, self.base_event("TURN_OPENED", "OPEN"))
        session_end = self.base_event("SESSION_ENDED", "END", task_id="S1")
        queued = enqueue_session_end(self.queue, session_end, self.keyring)
        self.assertTrue(queued["enqueued"])
        context = multiprocessing.get_context("spawn")
        crashed = context.Process(target=_crash_worker,
                                  args=(str(self.queue), str(self.keyring), str(self.data), "AFTER_APPEND"))
        crashed.start(); crashed.join(20); self.assertEqual(94, crashed.exitcode)
        report = process_queue(self.queue, self.keyring, 5)
        self.assertTrue(report["ok"]); self.assertEqual(1, report["completed"])
        chain = verify_event_chain(self.event_file)
        self.assertEqual(2, chain["record_count"])
        self.assertEqual("SEALED_CURRENT", verify_event_seals(self.event_file, keyring_path=self.keyring)["seal_status"])
        self.assertEqual(1, len(list((self.queue / "done").glob("job-*.json"))))

    def test_worker_recovers_each_claim_seal_and_ack_crash_boundary(self) -> None:
        context = multiprocessing.get_context("spawn")
        original_data = os.environ.get("CP_ASSISTANT_DATA")
        try:
            for index, point in enumerate(("AFTER_CLAIM", "AFTER_SEAL", "BEFORE_ACK")):
                data = self.root / ("fault-data-%d" % index); project_id = "fault-project-%d" % index
                project = data / project_id; event_file = project / "feedback" / "task-outcome-v2.jsonl"
                queue = project / "feedback" / "seal-queue"; keyring = self.root / ("fault-keyring-%d.json" % index)
                init_keyring(keyring); os.environ["CP_ASSISTANT_DATA"] = str(data)
                append_event(event_file, make_event({"event_id": "OPEN-%d" % index, "event_type": "TURN_OPENED",
                    "session_id": "S", "turn_id": "T", "task_id": "T", "project_id": project_id,
                    "repo_fingerprint": self.repo}))
                end = make_event({"event_id": "END-%d" % index, "event_type": "SESSION_ENDED",
                    "session_id": "S", "turn_id": "T", "task_id": "S", "project_id": project_id,
                    "repo_fingerprint": self.repo})
                enqueue_session_end(queue, end, keyring)
                crashed = context.Process(target=_crash_worker,
                    args=(str(queue), str(keyring), str(data), point))
                crashed.start(); crashed.join(20); self.assertEqual(94, crashed.exitcode, point)
                report = process_queue(queue, keyring, 5)
                self.assertTrue(report["ok"], (point, report))
                self.assertEqual(2, verify_event_chain(event_file)["record_count"], point)
                self.assertEqual("SEALED_CURRENT", verify_event_seals(event_file, keyring_path=keyring)["seal_status"])
                self.assertEqual(1, len(list((queue / "done").glob("job-*.json"))), point)
        finally:
            if original_data is None: os.environ.pop("CP_ASSISTANT_DATA", None)
            else: os.environ["CP_ASSISTANT_DATA"] = original_data

    def test_running_job_recovery_rejects_reused_pid_identity(self) -> None:
        enqueue_session_end(self.queue, self.base_event("SESSION_ENDED", "PID-REUSE", task_id="S1"), self.keyring)
        pending = next((self.queue / "pending").glob("job-*.json"))
        job = seal_queue_module._load(pending)
        job.update(state="running", attempt=1, lease_epoch=1,
                   lease_pid=os.getpid(), lease_process_identity="windows-filetime:old")
        seal_queue_module._atomic_json(pending, seal_queue_module._resign(job, self.keyring))
        running = self.queue / "running" / pending.name
        os.replace(pending, running)
        with mock.patch.object(seal_queue_module, "_pid_alive", return_value=True), \
             mock.patch.object(seal_queue_module, "_process_identity", side_effect=lambda pid: (
                 "windows-filetime:new" if pid == os.getpid() else "windows-filetime:worker")):
            report = process_queue(self.queue, self.keyring, 2)
        self.assertTrue(report["ok"])
        self.assertEqual(1, len(list((self.queue / "done").glob("job-*.json"))))

    def test_session_end_enqueue_is_bounded_and_worker_seals_later(self) -> None:
        for index in range(20):
            append_event(self.event_file, self.base_event("TURN_OPENED", "B-%d" % index,
                                                          turn_id="T-%d" % index, task_id="T-%d" % index))
        started = time.perf_counter()
        enqueue_session_end(self.queue, self.base_event("SESSION_ENDED", "END-BOUND", task_id="S1"), self.keyring)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 1.0)
        self.assertEqual(20, verify_event_chain(self.event_file)["record_count"])
        self.assertTrue(process_queue(self.queue, self.keyring)["ok"])
        self.assertEqual(21, verify_event_chain(self.event_file)["record_count"])

    def test_session_end_hook_only_dispatches_and_worker_deduplicates_terminal_identity(self) -> None:
        hook = _load_hook("cp_hook_session_end_v741")
        event = self.base_event("SESSION_ENDED", "RANDOM-SOURCE-ID", task_id="S1")
        event.pop("event_id")
        with mock.patch.object(hook, "append_event", side_effect=AssertionError("Hook must not persist SessionEnd")) as append, \
             mock.patch.object(hook, "launch_worker") as launch:
            hook._enqueue_and_launch(self.event_file, event)
            hook._enqueue_and_launch(self.event_file, event)
        append.assert_not_called()
        self.assertFalse(self.event_file.exists())
        self.assertEqual(2, launch.call_count)
        dispatched = launch.call_args.kwargs["bootstrap_event"]
        self.assertRegex(dispatched["event_id"], r"^EVT_[0-9a-f]{32}$")
        self.assertEqual(dispatched["event_id"], launch.call_args_list[0].kwargs["bootstrap_event"]["event_id"])

        prepared = prepare_session_end(self.queue, dispatched, self.keyring)
        replay = prepare_session_end(self.queue, dispatched, self.keyring)
        self.assertTrue(prepared["enqueued"])
        self.assertFalse(replay["enqueued"])
        self.assertEqual(1, verify_event_chain(self.event_file)["record_count"])

        legacy = self.base_event("SESSION_ENDED", "LEGACY-RANDOM-ID", task_id="LEGACY")
        append_event(self.event_file, legacy)
        replay = dict(legacy); replay.pop("event_id")
        identity = {key: str(replay.get(key) or "") for key in (
            "event_type", "session_id", "turn_id", "task_id", "project_id", "repo_fingerprint")}
        replay["event_id"] = "EVT_" + hashlib.sha256(json.dumps(
            identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()[:32]
        prepared_legacy = prepare_session_end(self.queue, replay, self.keyring)
        self.assertEqual(2, verify_event_chain(self.event_file)["record_count"])
        legacy_job = next(path for path in (self.queue / "pending").glob("job-*.json")
                          if json.loads(path.read_text(encoding="utf-8"))["event"]["task_id"] == "LEGACY")
        self.assertEqual("LEGACY-RANDOM-ID", json.loads(legacy_job.read_text(encoding="utf-8"))["event"]["event_id"])
        self.assertTrue(prepared_legacy["enqueued"])

        failed = self.base_event("SESSION_ENDED", "LAUNCH-FAIL", task_id="FAIL")
        with mock.patch.object(hook, "launch_worker", side_effect=OSError("launch failed")), \
             mock.patch.object(hook, "_session_end_diagnostic") as diagnostic:
            hook._enqueue_and_launch(self.event_file, failed)
        diagnostic.assert_called_once_with(failed, "SEAL_WORKER_LAUNCH_FAILED")

    def test_session_end_rejects_missing_stable_identity_and_unsealed_chain_is_not_observed(self) -> None:
        hook = _load_hook("cp_hook_session_end_identity")
        with mock.patch.object(hook, "_session_end_diagnostic") as diagnostic:
            self.assertIsNone(hook._event({"hook_event_name": "SessionEnd", "cwd": str(self.root)}))
        self.assertEqual("SESSION_END_IDENTITY_UNAVAILABLE", diagnostic.call_args.args[1])

        append_event(self.event_file, self.base_event("TURN_OPENED", "OPEN"))
        terminal = self.base_event("SESSION_ENDED", "SEALED-END")
        terminal["metadata"] = {"seal_required": True}
        append_event(self.event_file, terminal)
        with mock.patch.dict(os.environ, {"CP_ASSISTANT_KEYRING_PATH": str(self.keyring)}):
            with self.assertRaisesRegex(ObservationError, "未封印尾部"):
                observe_project(self.project_id, self.project)
            seal_event_chain(self.event_file, keyring_path=self.keyring)
            self.assertEqual(self.project_id, observe_project(self.project_id, self.project).project_id)

    def test_all_session_end_queue_and_worker_entries_reject_empty_stable_identity(self) -> None:
        empty = self.base_event("SESSION_ENDED", "EMPTY-IDENTITY", session_id="", turn_id="", task_id="")
        for operation in (
            lambda: enqueue_session_end(self.queue, empty, self.keyring),
            lambda: prepare_session_end(self.queue, empty, self.keyring),
            lambda: launch_worker(ROOT, self.queue, self.keyring, bootstrap_event=empty),
        ):
            with self.assertRaisesRegex(SealQueueError, "SESSION_END_IDENTITY_UNAVAILABLE"):
                operation()
        encoded = base64.urlsafe_b64encode(json.dumps(
            empty, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).decode("ascii")
        result = subprocess.run([
            sys.executable, str(ROOT / "hooks" / "seal_worker.py"), "--queue", str(self.queue),
            "--keyring", str(self.keyring), "--max-jobs", "1", "--bootstrap-event-b64", encoded,
        ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        self.assertEqual(2, result.returncode)
        self.assertEqual("SESSION_END_IDENTITY_UNAVAILABLE", json.loads(result.stderr.strip())["error_code"])
        self.assertFalse(self.event_file.exists())
        self.assertFalse(any(self.queue.rglob("job-*.json")))

    def test_detached_worker_bootstrap_requeues_v2_identity_and_seals_existing_event(self) -> None:
        terminal = self.base_event("SESSION_ENDED", "BOOTSTRAP-END")
        terminal["metadata"] = {"seal_required": True}
        stored = append_event(self.event_file, terminal)
        old_wait = os.environ.get("CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS")
        os.environ["CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS"] = "2500"
        try:
            launched = launch_worker(ROOT, self.queue, self.keyring, bootstrap_event=stored)
        finally:
            if old_wait is None: os.environ.pop("CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS", None)
            else: os.environ["CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS"] = old_wait
        self.assertEqual("EXITED", launched["test_wait_status"])
        self.assertEqual(0, launched["worker_exit_code"])
        self.assertEqual(1, verify_event_chain(self.event_file)["record_count"])
        self.assertEqual("SEALED_CURRENT", verify_event_seals(self.event_file, keyring_path=self.keyring)["seal_status"])
        done = next((self.queue / "done").glob("job-*.json"))
        self.assertEqual(2, json.loads(done.read_text(encoding="utf-8"))["identity_version"])

    def test_worker_bootstrap_uses_bounded_argument_without_synchronous_pipe_io(self) -> None:
        terminal = self.base_event("SESSION_ENDED", "BOOTSTRAP-ARG")
        process = mock.Mock(pid=4321)
        with mock.patch.object(seal_queue_module.subprocess, "Popen", return_value=process) as popen, \
             mock.patch.dict(os.environ, {"CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS": "0"}):
            result = launch_worker(ROOT, self.queue, self.keyring, bootstrap_event=terminal)
        self.assertEqual(4321, result["worker_pid"])
        command = popen.call_args.args[0]
        self.assertNotIn("--bootstrap-stdin", command)
        marker = command.index("--bootstrap-event-b64")
        decoded = base64.b64decode(command[marker + 1].encode("ascii"), altchars=b"-_", validate=True)
        self.assertEqual(terminal, json.loads(decoded.decode("utf-8")))
        self.assertIs(seal_queue_module.subprocess.DEVNULL, popen.call_args.kwargs["stdin"])

    def test_v2_job_identity_recovers_a_preupgrade_done_job_without_duplicate_terminal_event(self) -> None:
        legacy = self.base_event("SESSION_ENDED", "LEGACY-UPGRADE-END")
        digest = seal_queue_module._job_digest(legacy, 1)
        _ring, secret, key_id = seal_queue_module.active_secret("event-hmac", self.keyring)
        for state in seal_queue_module.JOB_STATES:
            (self.queue / state).mkdir(parents=True, exist_ok=True)
        job = {
            "schema_version": seal_queue_module.JOB_SCHEMA,
            "job_id": digest, "idempotency_key": digest, "state": "pending",
            "attempt": 0, "lease_epoch": 0, "lease_pid": 0, "lease_process_identity": "",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "project_id": self.project_id, "repo_fingerprint": self.repo,
            "event_file": self.event_file.name, "event": legacy, "error_code": "NONE",
        }
        pending = self.queue / "pending" / ("job-" + digest + ".json")
        seal_queue_module._atomic_json(pending, seal_queue_module._sign(job, secret, key_id))
        self.assertTrue(process_queue(self.queue, self.keyring)["ok"])
        self.assertEqual(1, verify_event_chain(self.event_file)["record_count"])

        hook = _load_hook("cp_hook_session_end_upgrade")
        replay = dict(legacy); replay.pop("event_id")
        with mock.patch.object(hook, "launch_worker") as dispatch:
            hook._enqueue_and_launch(self.event_file, replay)
        stored = dispatch.call_args.kwargs["bootstrap_event"]
        self.assertRegex(stored["event_id"], r"^EVT_[0-9a-f]{32}$")
        self.assertEqual(1, verify_event_chain(self.event_file)["record_count"])

        old_wait = os.environ.get("CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS")
        os.environ["CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS"] = "2500"
        try:
            launched = launch_worker(ROOT, self.queue, self.keyring, bootstrap_event=stored)
        finally:
            if old_wait is None: os.environ.pop("CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS", None)
            else: os.environ["CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS"] = old_wait
        self.assertEqual(0, launched["worker_exit_code"])
        self.assertEqual(1, verify_event_chain(self.event_file)["record_count"])
        self.assertEqual("LEGACY-UPGRADE-END", read_event_chain(self.event_file)["events"][0]["event_id"])
        jobs = [json.loads(path.read_text(encoding="utf-8")) for path in (self.queue / "done").glob("job-*.json")]
        self.assertEqual({1, 2}, {int(job.get("identity_version", 1)) for job in jobs})
        self.assertEqual("SEALED_CURRENT", verify_event_seals(self.event_file, keyring_path=self.keyring)["seal_status"])

    def test_windows_atomic_replace_retries_only_transient_sharing_failures(self) -> None:
        source = self.root / "atomic.tmp"; target = self.root / "atomic.json"
        source.write_text("stable", encoding="utf-8")
        transient = OSError("sharing violation"); transient.winerror = 32
        real_replace = os.replace
        calls = []

        def flaky_replace(left, right):
            calls.append((left, right))
            if len(calls) < 3:
                raise transient
            return real_replace(left, right)

        with mock.patch("cp_runtime.atomic_io.os.name", "nt"), \
             mock.patch("cp_runtime.atomic_io.os.replace", side_effect=flaky_replace):
            replace_with_retry(source, target, timeout=0.2)
        self.assertEqual("stable", target.read_text(encoding="utf-8"))
        self.assertEqual(3, len(calls))

        denied = self.root / "denied.tmp"; denied.write_text("blocked", encoding="utf-8")
        permanent = OSError("permanent"); permanent.winerror = 87
        with mock.patch("cp_runtime.atomic_io.os.name", "nt"), \
             mock.patch("cp_runtime.atomic_io.os.replace", side_effect=permanent):
            with self.assertRaises(OSError):
                replace_with_retry(denied, target, timeout=0.2)

    def test_non_destructive_archive_capacity_and_privacy_health(self) -> None:
        previous = os.environ.get("CP_ASSISTANT_EVENT_SEGMENT_BYTES")
        os.environ["CP_ASSISTANT_EVENT_SEGMENT_BYTES"] = "256"
        try:
            for index in range(6):
                append_event(self.event_file, self.base_event("TURN_OPENED", "ARC-%d" % index,
                    turn_id="T-%d" % index, task_id="T-%d" % index,
                    metadata={"note": "SENSITIVE_SENTINEL_PROMPT_BODY"}))
        finally:
            if previous is None: os.environ.pop("CP_ASSISTANT_EVENT_SEGMENT_BYTES", None)
            else: os.environ["CP_ASSISTANT_EVENT_SEGMENT_BYTES"] = previous
        before = verify_event_chain(self.event_file)["head_hash"]
        self.assertGreater(len(event_segment_paths(self.event_file)), 0)
        archived = archive_closed_segments(self.event_file)
        self.assertTrue(archived["created"]); self.assertTrue(verify_archive(self.event_file)["ok"])
        self.assertEqual(before, verify_event_chain(self.event_file)["head_hash"])
        self.assertFalse(capacity_report(self.project)["automatic_deletion"])
        health = health_overview(self.data, self.keyring)
        rendered = json.dumps(health, ensure_ascii=False)
        self.assertNotIn("SENSITIVE_SENTINEL", rendered)
        self.assertFalse(health["privacy"]["raw_project_id"])

    def test_queue_and_health_reject_lexical_reparse_boundaries(self) -> None:
        real_project = self.data / "real-project"
        real_queue = real_project / "feedback" / "seal-queue"
        real_queue.mkdir(parents=True)
        self.queue.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.queue.symlink_to(real_queue, target_is_directory=True)
        except OSError as exc:
            if os.name != "nt":
                self.skipTest("directory symlink unavailable: %s" % exc)
            junction = subprocess.run(
                'cmd.exe /d /c mklink /J "%s" "%s"' % (self.queue, real_queue),
                text=True, capture_output=True)
            if junction.returncode != 0:
                self.skipTest("directory reparse creation unavailable: %s" % junction.stderr)
        with self.assertRaisesRegex(Exception, "QUEUE_REPARSE_REJECTED"):
            enqueue_session_end(self.queue, self.base_event("SESSION_ENDED", "REPARSE", task_id="S1"), self.keyring)
        health = health_overview(self.data, self.keyring)
        project = next(item for item in health["projects"]
                       if item["project_ref"] == "sha256:" + hashlib.sha256(
                           self.project_id.encode("utf-8")).hexdigest())
        self.assertEqual("PROJECT_REPARSE_REJECTED", project["error_code"])

    def test_health_overview_isolates_one_malformed_segment_project(self) -> None:
        append_event(self.event_file, self.base_event("TURN_OPENED", "HEALTH-GOOD"))
        malformed = self.data / "malformed-project" / "feedback"
        malformed.mkdir(parents=True)
        (malformed / "task-outcome-v2.segment-000002.jsonl").write_text("{}\n", encoding="utf-8")
        report = health_overview(self.data, self.keyring)
        self.assertEqual(2, report["project_count"])
        by_ref = {item["project_ref"]: item for item in report["projects"]}
        malformed_ref = "sha256:" + hashlib.sha256(b"malformed-project").hexdigest()
        good_ref = "sha256:" + hashlib.sha256(self.project_id.encode("utf-8")).hexdigest()
        self.assertEqual("PROJECT_HEALTH_VALIDATION_FAILED", by_ref[malformed_ref]["error_code"])
        self.assertEqual("VALID", by_ref[good_ref]["chain_status"])

    def test_windows_hook_commands_quote_space_path_and_session_failure_is_explicit(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows command contract")
        plugin = self.root / "plugin root with spaces"
        shutil.copytree(ROOT / "hooks", plugin / "hooks")
        shutil.copytree(ROOT / "runtime", plugin / "runtime")
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        env = dict(os.environ, PLUGIN_ROOT=str(plugin), CP_ASSISTANT_DATA=str(self.data),
                   CP_ASSISTANT_KEYRING_PATH=str(self.keyring),
                   CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS="2000")
        for hook_name, entries in hooks.items():
            command = entries[0]["hooks"][0]["commandWindows"]
            self.assertIn('"%PLUGIN_ROOT%\\hooks\\cp_hook.cmd"', command)
            payload = {"hook_event_name": hook_name, "session_id": "S-HOOK",
                       "turn_id": "T-HOOK", "cwd": str(self.root)}
            if hook_name == "PreToolUse":
                payload.update(tool_name="Agent", tool_input={"model": "gpt-5.6-luna",
                                                               "reasoning_effort": "low"})
            result = subprocess.run(command, input=json.dumps(payload), text=True,
                                    encoding="utf-8", errors="replace", capture_output=True,
                                    env=env, shell=True, timeout=10)
            self.assertEqual(0, result.returncode, (hook_name, result.stderr))
        failure_env = dict(env, CP_ASSISTANT_SEAL_QUEUE_MAX_JOBS="0")
        command = hooks["SessionEnd"][0]["hooks"][0]["commandWindows"]
        payload = {"hook_event_name": "SessionEnd", "session_id": "S-FAIL",
                   "turn_id": "T-FAIL", "cwd": str(self.root)}
        started = time.perf_counter()
        failed = subprocess.run(command, input=json.dumps(payload), text=True,
                                encoding="utf-8", errors="replace", capture_output=True,
                                env=failure_env, shell=True, timeout=3)
        self.assertLess(time.perf_counter() - started, 3.0)
        self.assertEqual(0, failed.returncode)
        diagnostic = json.loads(failed.stderr.strip().splitlines()[-1])
        self.assertEqual("DEFERRED_OBSERVATION_FAILED", diagnostic["status"])
        self.assertFalse(diagnostic["contains_event_body"])

    def test_archive_serializes_with_a_spawn_writer_and_preserves_canonical_chain(self) -> None:
        previous = os.environ.get("CP_ASSISTANT_EVENT_SEGMENT_BYTES")
        os.environ["CP_ASSISTANT_EVENT_SEGMENT_BYTES"] = "256"
        try:
            for index in range(4):
                append_event(self.event_file, self.base_event("TURN_OPENED", "BASE-%d" % index,
                    turn_id="B-%d" % index, task_id="B-%d" % index))
            context = multiprocessing.get_context("spawn")
            archiver = context.Process(target=_archive_worker, args=(str(self.event_file),))
            writer = context.Process(target=_event, args=(str(self.event_file), 99, self.project_id, self.repo))
            archiver.start(); writer.start(); archiver.join(20); writer.join(20)
            self.assertEqual(0, archiver.exitcode); self.assertEqual(0, writer.exitcode)
        finally:
            if previous is None: os.environ.pop("CP_ASSISTANT_EVENT_SEGMENT_BYTES", None)
            else: os.environ["CP_ASSISTANT_EVENT_SEGMENT_BYTES"] = previous
        self.assertEqual(5, verify_event_chain(self.event_file)["record_count"])
        self.assertTrue(verify_archive(self.event_file)["ok"])

    def test_tampered_queue_job_is_dead_lettered_without_event_append(self) -> None:
        enqueue_session_end(self.queue, self.base_event("SESSION_ENDED", "TAMPER", task_id="S1"), self.keyring)
        pending = next((self.queue / "pending").glob("job-*.json"))
        value = json.loads(pending.read_text(encoding="utf-8")); value["repo_fingerprint"] = "sha256:" + "0" * 64
        pending.write_text(json.dumps(value), encoding="utf-8")
        report = process_queue(self.queue, self.keyring, 1)
        self.assertFalse(report["ok"]); self.assertEqual(1, report["dead_letter"])
        self.assertFalse(self.event_file.exists())

    def test_reviewer_calibration_v2_tracks_difficulty_clusters_reasons_and_evidence(self) -> None:
        source = self.project / "review" / "review-results.jsonl"; source.parent.mkdir(parents=True)
        rows = []
        for index in range(5):
            rows.append({"record_id": "R%d" % index, "task_id": "TASK-%d" % index,
                         "timestamp": (datetime(2026, 8, 1 + index, tzinfo=timezone.utc)).isoformat(),
                         "reviewer_results": [{"reviewer": "r1", "result_id": "RR-%d" % index,
                             "task_difficulty": "HIGH" if index > 1 else "MEDIUM", "accepted": 1,
                             "rejected": 0, "duration_ms": 10, "cost_units": 1,
                             "findings": [{"severity": "HIGH", "root_cause_group": "shared-root",
                                 "disposition": "REGRESSION_PREVENTED", "adoption_reason": "REGRESSION_PREVENTION",
                                 "regression_prevented": True,
                                 "regression_evidence": ["tests/test_shared_regression.py"]}]}]})
        source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        stats = observe_project(self.project_id, self.project).metrics["reviewer_stats"]["r1"]
        self.assertEqual({"HIGH": 3, "MEDIUM": 2}, stats["task_difficulty_distribution"])
        self.assertEqual(1, stats["finding_cluster_count"])
        self.assertEqual(4, stats["duplicate_cluster_finding_count"])
        self.assertEqual(5, stats["adoption_reasons"]["REGRESSION_PREVENTION"])
        self.assertEqual(1.0, stats["regression_prevention_evidence_rate"])

    def test_requested_model_policy_report_is_separate_from_runtime_evidence(self) -> None:
        module = _load_script("model_gate_v66", "model-gate-acceptance.py")
        report = module.evaluate()
        self.assertEqual("PASS", report["requested_model_policy"])
        self.assertEqual("NOT_EVALUATED", report["runtime_model_evidence"])


if __name__ == "__main__":
    unittest.main()
