from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build-release.py"
ATTEST = ROOT / "scripts" / "release-attestation.py"
LIFECYCLE = ROOT / "scripts" / "lifecycle-acceptance.py"
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.event_v2 import append_event, make_event, stable_repo_fingerprint, project_id_for


def run_script(script: Path, arguments: list[str], environment: dict[str, str] | None = None, expected: int = 0):
    effective_environment = dict(environment or os.environ)
    if "CP_ASSISTANT_KEYRING_PATH" not in effective_environment:
        effective_environment["CODEX_HOME"] = str(ROOT / ".isolated-test-codex-home")
    result = subprocess.run(
        [sys.executable, "-B", str(script), *arguments],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=effective_environment,
        timeout=120,
    )
    if result.returncode != expected:
        raise AssertionError(
            "rc=%d expected=%d\nstdout=%s\nstderr=%s" % (result.returncode, expected, result.stdout, result.stderr)
        )
    return result


class V64ReleaseDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cp-v65-release-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_release_build_is_byte_reproducible_and_normalized(self):
        artifact = self.root / "Codex-Skills-V7.3.0-zh-CN.zip"
        witness = self.root / "deterministic-build-v7.3.0-zh-CN.json"
        result = run_script(BUILD, ["reproducible", "--locale", "zh-CN",
                                    "--output", str(artifact), "--witness", str(witness)])
        report = json.loads(result.stdout)
        self.assertTrue(report["reproducible"])
        self.assertEqual(report["first_sha256"], report["second_sha256"])
        verify = run_script(BUILD, ["verify", "--locale", "zh-CN", "--archive", str(artifact)])
        self.assertTrue(json.loads(verify.stdout)["metadata_normalized"])

    def test_real_lifecycle_report_redacts_raw_identifiers(self):
        event_file = self.root / "task-outcome-v2.jsonl"
        session = "session-secret"
        parent = "parent-task-secret"
        child = "child-task-secret"
        fingerprint = stable_repo_fingerprint(str(self.root))
        project = project_id_for(fingerprint, str(self.root))
        sequence = [
            ("TURN_OPENED", parent, "gpt-5.6-sol"),
            ("SUBAGENT_STARTED", child, "gpt-5.6-luna"),
            ("SUBAGENT_STOPPED", child, "gpt-5.6-luna"),
            ("TASK_COMPLETED", parent, "gpt-5.6-sol"),
            ("SESSION_ENDED", session, ""),
        ]
        for index, (event_type, task_id, model) in enumerate(sequence):
            append_event(
                event_file,
                make_event(
                    {
                        "event_id": "EVENT-%d" % index,
                        "event_type": event_type,
                        "session_id": session,
                        "turn_id": parent if task_id == parent else child,
                        "task_id": task_id,
                        "project_id": project,
                        "repo_fingerprint": fingerprint,
                        "terminal_outcome": "PASS" if event_type == "TASK_COMPLETED" else "UNKNOWN",
                        "actual_model": model,
                    }
                ),
            )
        output = self.root / "lifecycle-report.json"
        result = run_script(
            LIFECYCLE,
            [
                "--event-file",
                str(event_file),
                "--session-id",
                session,
                "--project-id",
                project,
                "--repo-fingerprint",
                fingerprint,
                "--output",
                str(output),
            ],
        )
        report = json.loads(result.stdout)
        serialized = output.read_text(encoding="utf-8")
        self.assertTrue(report["event_chain"]["valid"])
        self.assertNotIn(session, serialized)
        self.assertNotIn(parent, serialized)
        self.assertNotIn(child, serialized)
        self.assertIn("gpt-5.6-luna", report["actual_subagent_models"])

    def test_lifecycle_rejects_host_only_model_proof_without_rewriting_hook_facts(self):
        event_file = self.root / "task-outcome-v2-unavailable.jsonl"
        session = "session-host-fact"
        parent = "parent-host-fact"
        child = "child-host-fact"
        fingerprint = stable_repo_fingerprint(str(self.root))
        project = project_id_for(fingerprint, str(self.root))
        sequence = [
            ("TURN_OPENED", parent),
            ("SUBAGENT_STARTED", child),
            ("SUBAGENT_STOPPED", child),
            ("TASK_COMPLETED", parent),
            ("SESSION_ENDED", session),
        ]
        for index, (event_type, task_id) in enumerate(sequence):
            append_event(event_file, make_event({
                "event_id": "HOST-%d" % index,
                "event_type": event_type,
                "session_id": session,
                "turn_id": task_id,
                "task_id": task_id,
                "project_id": project,
                "repo_fingerprint": fingerprint,
                "terminal_outcome": "PASS" if event_type == "TASK_COMPLETED" else "UNKNOWN",
            }))
        host_log = self.root / "subagent-rollout.jsonl"
        host_log.write_text("\n".join(json.dumps(record) for record in [
            {
                "type": "session_meta",
                "payload": {
                    "session_id": session,
                    "id": "child-thread",
                    "model": "gpt-5.6-luna",
                    "agent_role": "cp_review_test_delivery",
                    "source": {"subagent": {"thread_spawn": {"parent_thread_id": session}}},
                },
            },
            {
                "type": "turn_context",
                "payload": {"turn_id": child, "model": "gpt-5.6-luna", "effort": "low"},
            },
        ]) + "\n", encoding="utf-8")
        result = run_script(LIFECYCLE, [
            "--event-file", str(event_file),
            "--session-id", session,
            "--project-id", project,
            "--repo-fingerprint", fingerprint,
            "--expected-subagent-model", "gpt-5.6-luna",
            "--expected-reasoning-effort", "low",
            "--host-session-log", str(host_log),
            "--output", str(self.root / "host-model-report.json"),
        ])
        report = json.loads(result.stdout)
        self.assertEqual("UNAVAILABLE", report["runtime_model_evidence"])
        self.assertEqual("gpt-5.6-luna / low", report["diagnostic_model_observation"])

        result = run_script(LIFECYCLE, [
            "--event-file", str(event_file),
            "--session-id", session,
            "--project-id", project,
            "--repo-fingerprint", fingerprint,
            "--expected-subagent-model", "gpt-5.6-luna",
            "--output", str(self.root / "missing-model-report.json"),
        ])
        self.assertEqual("UNAVAILABLE", json.loads(result.stdout)["runtime_model_evidence"])

    def test_attestation_binds_artifact_and_all_evidence(self):
        artifact = self.root / "Codex-Skills-V6.6.zip"
        artifact.write_bytes(b"artifact-v65")
        evidence = {
            "plugin-list-v6.3.json": {
                "installed": [
                    {
                        "pluginId": "codex-cross-project-engineering-assistant@cp-assistant-local",
                        "version": "7.3.0",
                        "installed": True,
                        "enabled": True,
                    }
                ]
            },
            "lifecycle-acceptance-v6.3.json": {
                "ok": True,
                "project_id": "project-neutral",
                "repo_fingerprint": "sha256:" + "a" * 64,
                "required_sequence": [
                    "TURN_OPENED",
                    "SUBAGENT_STARTED",
                    "SUBAGENT_STOPPED",
                    "TASK_COMPLETED",
                    "SESSION_ENDED",
                ],
                "actual_subagent_models": ["gpt-5.6-luna"],
                "event_chain": {"valid": True, "seal_status": "SEALED_CURRENT", "hmac_verified": True},
            },
            "package-validation-v6.3.json": {"ok": True},
            "deterministic-build-v6.3.json": {
                "ok": True,
                "reproducible": True,
                "artifact_sha256": hashlib.sha256(b"artifact-v65").hexdigest(),
            },
            "release-verification-v6.4.json": {
                "ok": True, "version": "7.3.0",
                "artifact_sha256": hashlib.sha256(b"artifact-v65").hexdigest(),
                "status": {key: "PASS" for key in ("package", "artifact", "host", "plugin", "lifecycle", "payload")},
            },
        }
        for name, value in evidence.items():
            (self.root / name).write_text(json.dumps(value), encoding="utf-8")
        version_evidence = self.root / "codex-version-v6.3.txt"
        version_evidence.write_text("codex-cli 0.152.1\n", encoding="utf-8")
        environment = {**os.environ, "CP_ASSISTANT_ATTESTATION_HMAC_KEY": "legacy-release-test-key"}
        attestation = self.root / "release-attestation-v6.3.json"
        run_script(
            ATTEST,
            [
                "create",
                "--artifact",
                str(artifact),
                "--plugin-list",
                str(self.root / "plugin-list-v6.3.json"),
                "--lifecycle-report",
                str(self.root / "lifecycle-acceptance-v6.3.json"),
                "--package-validation",
                str(self.root / "package-validation-v6.3.json"),
                "--deterministic-witness",
                str(self.root / "deterministic-build-v6.3.json"),
                "--unified-verification",
                str(self.root / "release-verification-v6.4.json"),
                "--codex-version-evidence",
                str(version_evidence),
                "--output",
                str(attestation),
            ],
            environment,
        )
        verify = run_script(
            ATTEST,
            ["verify", "--attestation", str(attestation), "--artifact", str(artifact)],
            environment,
        )
        self.assertTrue(json.loads(verify.stdout)["ok"])
        validation_path = self.root / "package-validation-v6.3.json"
        validation_original = validation_path.read_text(encoding="utf-8")
        validation_path.write_text(json.dumps({"ok": False}), encoding="utf-8")
        run_script(
            ATTEST,
            ["verify", "--attestation", str(attestation), "--artifact", str(artifact)],
            environment,
            expected=2,
        )
        validation_path.write_text(validation_original, encoding="utf-8")
        artifact.write_bytes(b"tampered")
        run_script(
            ATTEST,
            ["verify", "--attestation", str(attestation), "--artifact", str(artifact)],
            environment,
            expected=2,
        )

    def test_attestation_rejects_witness_for_another_artifact(self):
        artifact = self.root / "Codex-Skills-V6.6.zip"
        artifact.write_bytes(b"artifact-v65")
        plugin = self.root / "plugin-list-v6.3.json"
        plugin.write_text(json.dumps({"installed": [{
            "pluginId": "codex-cross-project-engineering-assistant@cp-assistant-local",
            "version": "7.3.0", "installed": True, "enabled": True,
        }]}), encoding="utf-8")
        lifecycle = self.root / "lifecycle-acceptance-v6.3.json"
        lifecycle.write_text(json.dumps({
            "ok": True, "project_id": "project-neutral", "repo_fingerprint": "sha256:" + "a" * 64,
            "required_sequence": list(("TURN_OPENED", "SUBAGENT_STARTED", "SUBAGENT_STOPPED", "TASK_COMPLETED", "SESSION_ENDED")),
            "actual_subagent_models": ["gpt-5.6-luna"], "event_chain": {"valid": True, "seal_status": "SEALED_CURRENT", "hmac_verified": True},
        }), encoding="utf-8")
        validation = self.root / "package-validation-v6.3.json"
        validation.write_text(json.dumps({"ok": True}), encoding="utf-8")
        witness = self.root / "deterministic-build-v6.3.json"
        witness.write_text(json.dumps({"ok": True, "reproducible": True, "artifact_sha256": "0" * 64}), encoding="utf-8")
        version = self.root / "codex-version-v6.3.txt"
        version.write_text("codex-cli 0.152.1\n", encoding="utf-8")
        unified = self.root / "release-verification-v6.4.json"
        unified.write_text(json.dumps({"ok": True, "version": "7.3.0",
            "artifact_sha256": hashlib.sha256(b"artifact-v65").hexdigest(),
            "status": {key: "PASS" for key in ("package", "artifact", "host", "plugin", "lifecycle", "payload")}}), encoding="utf-8")
        result = run_script(ATTEST, [
            "create", "--artifact", str(artifact), "--plugin-list", str(plugin),
            "--lifecycle-report", str(lifecycle), "--package-validation", str(validation),
            "--deterministic-witness", str(witness), "--codex-version-evidence", str(version),
            "--unified-verification", str(unified),
            "--output", str(self.root / "attestation.json"),
        ], expected=2)
        self.assertIn("not bound", result.stderr)

    def test_attestation_hmac_and_unsafe_evidence_name_fail_closed(self):
        artifact = self.root / "Codex-Skills-V6.6.zip"; artifact.write_bytes(b"artifact-v65")
        plugin = self.root / "plugin.json"; plugin.write_text(json.dumps({"installed": [{
            "pluginId": "codex-cross-project-engineering-assistant@cp-assistant-local",
            "version": "7.3.0", "installed": True, "enabled": True,
        }]}), encoding="utf-8")
        lifecycle = self.root / "life.json"; lifecycle.write_text(json.dumps({
            "ok": True, "project_id": "project-neutral", "repo_fingerprint": "sha256:" + "a" * 64,
            "required_sequence": ["TURN_OPENED", "SUBAGENT_STARTED", "SUBAGENT_STOPPED", "TASK_COMPLETED", "SESSION_ENDED"],
            "actual_subagent_models": ["gpt-5.6-luna"], "event_chain": {"valid": True, "seal_status": "SEALED_CURRENT", "hmac_verified": True},
        }), encoding="utf-8")
        validation = self.root / "validation.json"; validation.write_text(json.dumps({"ok": True}), encoding="utf-8")
        witness = self.root / "witness.json"; witness.write_text(json.dumps({
            "ok": True, "reproducible": True, "artifact_sha256": hashlib.sha256(b"artifact-v65").hexdigest(),
        }), encoding="utf-8")
        version = self.root / "version.txt"; version.write_text("codex-cli 0.152.1\n", encoding="utf-8")
        unified = self.root / "unified.json"; unified.write_text(json.dumps({
            "ok": True, "version": "7.3.0", "artifact_sha256": hashlib.sha256(b"artifact-v65").hexdigest(),
            "status": {key: "PASS" for key in ("package", "artifact", "host", "plugin", "lifecycle", "payload")}
        }), encoding="utf-8")
        attestation = self.root / "attestation.json"
        good_env = {**os.environ, "CP_ASSISTANT_ATTESTATION_HMAC_KEY": "test-key-v65"}
        create_args = ["create", "--artifact", str(artifact), "--plugin-list", str(plugin),
                       "--lifecycle-report", str(lifecycle), "--package-validation", str(validation),
                       "--deterministic-witness", str(witness), "--codex-version-evidence", str(version),
                       "--unified-verification", str(unified),
                       "--output", str(attestation)]
        no_backend_env = dict(os.environ)
        no_backend_env.pop("CP_ASSISTANT_ATTESTATION_HMAC_KEY", None)
        no_backend_env["CODEX_HOME"] = str(self.root / "no-keyring-home")
        run_script(ATTEST, create_args, no_backend_env, expected=2)
        run_script(ATTEST, create_args, good_env)
        run_script(ATTEST, ["verify", "--attestation", str(attestation), "--artifact", str(artifact)], good_env)
        bad_env = {**good_env, "CP_ASSISTANT_ATTESTATION_HMAC_KEY": "wrong-key"}
        run_script(ATTEST, ["verify", "--attestation", str(attestation), "--artifact", str(artifact)], bad_env, expected=2)

        unsigned = json.loads(attestation.read_text(encoding="utf-8")); unsigned.pop("integrity")
        first_key = sorted(unsigned["evidence"])[0]
        unsigned["evidence"][first_key]["name"] = "../outside.json"
        unsigned["integrity"] = {"sha256": hashlib.sha256(json.dumps(
            unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()}
        unsafe = self.root / "unsafe-attestation.json"
        unsafe.write_text(json.dumps(unsigned), encoding="utf-8")
        no_hmac_env = dict(os.environ); no_hmac_env.pop("CP_ASSISTANT_ATTESTATION_HMAC_KEY", None)
        run_script(ATTEST, ["verify", "--attestation", str(unsafe), "--artifact", str(artifact)], no_hmac_env, expected=2)

    def test_lifecycle_rejects_child_stop_after_parent_completion(self):
        event_file = self.root / "invalid-lifecycle.jsonl"
        session = "session-invalid"; parent = "parent-invalid"; child = "child-invalid"
        fingerprint = stable_repo_fingerprint(str(self.root)); project = project_id_for(fingerprint, str(self.root))
        sequence = [
            ("TURN_OPENED", parent, "gpt-5.6-sol"),
            ("SUBAGENT_STARTED", child, "gpt-5.6-luna"),
            ("TASK_COMPLETED", parent, "gpt-5.6-sol"),
            ("SUBAGENT_STOPPED", child, "gpt-5.6-luna"),
            ("SESSION_ENDED", session, ""),
        ]
        for index, (event_type, task_id, model) in enumerate(sequence):
            append_event(event_file, make_event({
                "event_id": "BAD-%d" % index, "event_type": event_type, "session_id": session,
                "turn_id": task_id, "task_id": task_id, "project_id": project,
                "repo_fingerprint": fingerprint, "terminal_outcome": "PASS" if event_type == "TASK_COMPLETED" else "UNKNOWN",
                "actual_model": model,
            }))
        run_script(LIFECYCLE, ["--event-file", str(event_file), "--session-id", session,
                   "--project-id", project, "--repo-fingerprint", fingerprint,
                   "--output", str(self.root / "invalid-report.json")], expected=2)


if __name__ == "__main__":
    unittest.main()

