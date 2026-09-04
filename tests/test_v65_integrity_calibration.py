from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.event_v2 import append_event  # noqa: E402
from cp_runtime.integrity import (IntegrityError, init_keyring, rotate_key, seal_event_chain,
                                  verify_event_seals, verify_keyring)  # noqa: E402
from cp_runtime.evolution.observation import observe_project  # noqa: E402


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V65IntegrityCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="cp-v65-")
        self.root = Path(self.temp.name)
        self.keyring = self.root / "keyring.json"
        init_keyring(self.keyring)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def event(self, index: int) -> dict:
        return {"event_id": "EVT-%d" % index, "event_type": "TURN_OPENED",
                "session_id": "S", "turn_id": "T", "task_id": "TASK",
                "project_id": "project-v65", "repo_fingerprint": "sha256:" + "a" * 64}

    def test_key_rotation_and_mixed_v65_writer_keep_chain_verifiable(self) -> None:
        event_file = self.root / "task-outcome-v2.jsonl"
        append_event(event_file, self.event(1))
        first = seal_event_chain(event_file, keyring_path=self.keyring)
        self.assertEqual("SEALED_CURRENT", first["seal_status"])
        first_key = first["key_ids"][0]
        append_event(event_file, self.event(2))
        tail = verify_event_seals(event_file, keyring_path=self.keyring)
        self.assertEqual("VALID_SEALED_PREFIX_WITH_UNSEALED_TAIL", tail["seal_status"])
        rotate_key("event-hmac", self.keyring)
        current = seal_event_chain(event_file, keyring_path=self.keyring)
        self.assertEqual("SEALED_CURRENT", current["seal_status"])
        self.assertEqual(2, len(current["key_ids"]))
        self.assertIn(first_key, current["key_ids"])
        verify_keyring(self.keyring)

    def test_concurrent_init_and_rotations_preserve_every_key(self) -> None:
        another = self.root / "concurrent-keyring.json"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: init_keyring(another), range(2)))
        self.assertEqual(results[0]["binding_id"], results[1]["binding_id"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _index: rotate_key("event-hmac", another), range(2)))
        status = verify_keyring(another)
        self.assertEqual(3, status["purposes"]["event-hmac"]["key_count"])
        self.assertEqual(1, status["purposes"]["event-hmac"]["statuses"].count("ACTIVE"))

    def test_rotate_racing_with_seal_keeps_issued_key_verifiable(self) -> None:
        event_file = self.root / "racing-events.jsonl"
        append_event(event_file, self.event(1))
        with ThreadPoolExecutor(max_workers=2) as pool:
            seal_future = pool.submit(seal_event_chain, event_file, None, self.keyring)
            rotate_future = pool.submit(rotate_key, "event-hmac", self.keyring)
            seal_future.result(); rotate_future.result()
        self.assertEqual("SEALED_CURRENT", verify_event_seals(event_file, keyring_path=self.keyring)["seal_status"])

    def test_seal_tamper_and_host_binding_mismatch_fail(self) -> None:
        event_file = self.root / "events.jsonl"
        append_event(event_file, self.event(1))
        seal_event_chain(event_file, keyring_path=self.keyring)
        seal_file = Path(str(event_file) + ".seals.jsonl")
        record = json.loads(seal_file.read_text(encoding="utf-8"))
        record["event_chain_head"] = "f" * 64
        seal_file.write_text(json.dumps(record) + "\n", encoding="utf-8")
        with self.assertRaises(IntegrityError):
            verify_event_seals(event_file, keyring_path=self.keyring)
        value = json.loads(self.keyring.read_text(encoding="utf-8"))
        value["binding_id"] = "sha256:" + "0" * 64
        self.keyring.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(IntegrityError):
            verify_keyring(self.keyring)

    def test_lifecycle_module_has_no_host_model_reader(self) -> None:
        lifecycle = load_script("lifecycle_v65", "lifecycle-acceptance.py")
        self.assertFalse(hasattr(lifecycle, "_model_evidence"))
        self.assertFalse(hasattr(lifecycle, "load_host_session_facts"))

    def test_release_attestation_key_rotation_verifies_old_and_new_signatures(self) -> None:
        attestation_module = load_script("release_attestation_v65", "release-attestation.py")
        artifact = self.root / "Codex-Skills-V6.6.zip"
        artifact.write_bytes(b"v65-artifact")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        plugin = self.root / "plugin.json"
        plugin.write_text(json.dumps({"installed": [{
            "pluginId": "codex-cross-project-engineering-assistant@cp-assistant-local",
            "version": "7.4.5", "installed": True, "enabled": True}]}), encoding="utf-8")
        event_file = self.root / "attestation-events.jsonl"
        append_event(event_file, self.event(99))
        seal_state = seal_event_chain(event_file, keyring_path=self.keyring)
        lifecycle = self.root / "lifecycle.json"
        lifecycle.write_text(json.dumps({"ok": True, "schema_version": "2.0", "project_id": "project-v65",
            "repo_fingerprint": "sha256:" + "a" * 64,
            "required_sequence": ["TURN_OPENED", "SUBAGENT_STARTED", "SUBAGENT_STOPPED",
                                  "TASK_COMPLETED", "SESSION_ENDED"],
            "schema_version": "2.0",
            "privacy": {"host_model_information_read": False,
                        "host_model_information_exported": False},
            "event_chain": {"valid": True, "seal_status": "SEALED_CURRENT",
                            "head": seal_state["event_chain_head"]}}), encoding="utf-8")
        validation = self.root / "validation.json"; validation.write_text('{"ok":true}', encoding="utf-8")
        witness = self.root / "witness.json"; witness.write_text(json.dumps({
            "ok": True, "reproducible": True, "artifact_sha256": digest}), encoding="utf-8")
        unified = self.root / "unified.json"; unified.write_text(json.dumps({
            "ok": True, "version": "7.4.5", "artifact_sha256": digest,
            "status": {name: "PASS" for name in ("package", "artifact", "host", "plugin", "lifecycle", "dispatch_policy", "payload")}}), encoding="utf-8")
        dispatch_policy = self.root / "dispatch-policy.json"; dispatch_policy.write_text(json.dumps({
            "ok": True, "schema_version": "2.0", "dispatch_policy_status": "PASS",
            "automatic_ceiling_profile": "terra-high", "cases": [
                {"case_id": "allow-low", "expected": "allow", "observed": "allow",
                 "exit_code": 0, "pass": True},
                {"case_id": "deny-high", "expected": "deny", "observed": "deny",
                 "exit_code": 0, "pass": True}],
            "privacy": {"host_model_information_collected": False,
                        "host_model_information_exported": False}}), encoding="utf-8")
        version = self.root / "version.txt"; version.write_text("codex-cli 0.153.3\n", encoding="utf-8")
        args = (artifact, plugin, lifecycle, validation, witness, unified, version)
        first = attestation_module.create_attestation(*args, keyring_path=self.keyring,
                                                       event_file_path=event_file,
                                                       dispatch_policy_report_path=dispatch_policy)
        first_path = self.root / "attestation-first.json"
        first_path.write_text(json.dumps(first), encoding="utf-8")
        first_key = first["integrity"]["hmac_key_id"]
        original_lifecycle = lifecycle.read_text(encoding="utf-8")
        forged = json.loads(original_lifecycle)
        forged["event_chain"]["head"] = "f" * 64
        lifecycle.write_text(json.dumps(forged), encoding="utf-8")
        with self.assertRaises(attestation_module.AttestationError):
            attestation_module.create_attestation(*args, keyring_path=self.keyring,
                                                   event_file_path=event_file,
                                                   dispatch_policy_report_path=dispatch_policy)
        lifecycle.write_text(original_lifecycle, encoding="utf-8")
        rotate_key("release-attestation", self.keyring)
        second = attestation_module.create_attestation(*args, keyring_path=self.keyring,
                                                        event_file_path=event_file,
                                                        dispatch_policy_report_path=dispatch_policy)
        second_path = self.root / "attestation-second.json"
        second_path.write_text(json.dumps(second), encoding="utf-8")
        self.assertNotEqual(first_key, second["integrity"]["hmac_key_id"])
        self.assertTrue(attestation_module.verify_attestation(first_path, artifact, self.keyring,
                                                               event_file)["hmac_verified"])
        self.assertTrue(attestation_module.verify_attestation(second_path, artifact, self.keyring,
                                                               event_file)["hmac_verified"])

    def test_reviewer_result_replay_is_deduplicated_and_conflict_fails_closed(self) -> None:
        project = self.root / "project-v65"
        source = project / "review" / "review-results.jsonl"
        source.parent.mkdir(parents=True)
        base = {"record_id": "R1", "task_id": "T1", "timestamp": datetime.now(timezone.utc).isoformat(),
                "reviewer_results": [{"reviewer": "r1", "result_id": "RESULT-1", "accepted": 1,
                                      "rejected": 0, "duration_ms": 10, "cost_units": 1}]}
        replay = dict(base, record_id="R2")
        conflict = {"record_id": "R3", "task_id": "T1", "timestamp": base["timestamp"],
                    "reviewer_results": [{"reviewer": "r1", "result_id": "RESULT-1", "accepted": 0,
                                          "rejected": 1, "duration_ms": 10, "cost_units": 1}]}
        source.write_text("".join(json.dumps(row) + "\n" for row in (base, replay, conflict)), encoding="utf-8")
        snapshot = observe_project("project-v65", project)
        stats = snapshot.metrics["reviewer_stats"]["r1"]
        self.assertEqual(1, stats["invocations"])
        self.assertEqual(1, stats["duplicate_result_count"])
        self.assertEqual(1, stats["conflicting_result_count"])
        self.assertEqual("CONFLICT", stats["calibration_status"])
        self.assertFalse(stats["sample_sufficient"])


if __name__ == "__main__":
    unittest.main()
