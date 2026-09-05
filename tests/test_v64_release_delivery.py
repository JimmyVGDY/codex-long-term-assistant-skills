from __future__ import annotations

import hashlib
import json
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
VERSION = "7.4.6"
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.event_v3 import append_event, make_event, project_id_for, stable_repo_fingerprint


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
            "rc=%d expected=%d\nstdout=%s\nstderr=%s"
            % (result.returncode, expected, result.stdout, result.stderr)
        )
    return result


def dispatch_policy_report() -> dict:
    return {
        "ok": True,
        "schema_version": "2.0",
        "dispatch_policy_status": "PASS",
        "automatic_ceiling_profile": "terra-high",
        "cases": [
            {"case_id": "allow-low", "expected": "allow", "observed": "allow", "exit_code": 0, "pass": True},
            {"case_id": "deny-high", "expected": "deny", "observed": "deny", "exit_code": 0, "pass": True},
        ],
        "privacy": {
            "host_model_information_collected": False,
            "host_model_information_exported": False,
        },
    }


class V64ReleaseDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cp-v743-release-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def lifecycle_evidence(self, event_file: Path, *, invalid_order: bool = False) -> tuple[dict, str, str, str]:
        session = "session-secret"
        parent = "parent-task-secret"
        child = "child-task-secret"
        fingerprint = stable_repo_fingerprint(str(self.root))
        project = project_id_for(fingerprint, str(self.root))
        sequence = [
            ("TURN_OPENED", parent),
            ("SUBAGENT_STARTED", child),
            ("TASK_COMPLETED", parent),
            ("SUBAGENT_STOPPED", child),
            ("SESSION_ENDED", session),
        ] if invalid_order else [
            ("TURN_OPENED", parent),
            ("SUBAGENT_STARTED", child),
            ("SUBAGENT_STOPPED", child),
            ("TASK_COMPLETED", parent),
            ("SESSION_ENDED", session),
        ]
        for index, (event_type, task_id) in enumerate(sequence):
            append_event(event_file, make_event({
                "event_id": "EVENT-%d" % index,
                "event_type": event_type,
                "session_id": session,
                "turn_id": parent if task_id == parent else child,
                "task_id": task_id,
                "project_id": project,
                "repo_fingerprint": fingerprint,
                "terminal_outcome": "PASS" if event_type == "TASK_COMPLETED" else "UNKNOWN",
                "actual_model": "untrusted-host-value",
                "actual_reasoning_effort": "untrusted-host-value",
                "metadata": {"nested": {"runtime_model": "untrusted-host-value"}},
            }))
        output = self.root / ("invalid-life.json" if invalid_order else "life.json")
        result = run_script(
            LIFECYCLE,
            [
                "--event-file", str(event_file), "--session-id", session,
                "--project-id", project, "--repo-fingerprint", fingerprint,
                "--output", str(output),
            ],
            expected=2 if invalid_order else 0,
        )
        return (json.loads(result.stdout) if not invalid_order else {}, session, parent, child)

    def test_release_build_is_byte_reproducible_and_normalized(self):
        artifact = self.root / ("Codex-Skills-V%s-zh-CN.zip" % VERSION)
        witness = self.root / "deterministic-build.json"
        result = run_script(BUILD, ["reproducible", "--locale", "zh-CN",
                                    "--output", str(artifact), "--witness", str(witness)])
        report = json.loads(result.stdout)
        self.assertTrue(report["reproducible"])
        self.assertEqual(report["first_sha256"], report["second_sha256"])
        verify = run_script(BUILD, ["verify", "--locale", "zh-CN", "--archive", str(artifact)])
        self.assertTrue(json.loads(verify.stdout)["metadata_normalized"])

    def test_lifecycle_report_ignores_host_model_identity_and_redacts_raw_ids(self):
        event_file = self.root / "task-outcome-v3.jsonl"
        report, session, parent, child = self.lifecycle_evidence(event_file)
        raw_events = event_file.read_text(encoding="utf-8")
        rendered = json.dumps(report, ensure_ascii=False)
        for prohibited in ("actual_model", "actual_reasoning_effort", "runtime_model", "untrusted-host-value"):
            self.assertNotIn(prohibited, raw_events)
            self.assertNotIn(prohibited, rendered)
        for identifier in (session, parent, child):
            self.assertNotIn(identifier, rendered)
        self.assertEqual("2.0", report["schema_version"])
        self.assertFalse(report["privacy"]["host_model_information_read"])

    def test_lifecycle_rejects_child_stop_after_parent_completion(self):
        self.lifecycle_evidence(self.root / "invalid-lifecycle.jsonl", invalid_order=True)

    def test_attestation_v2_binds_artifact_dispatch_policy_and_privacy(self):
        artifact = self.root / "artifact.zip"
        artifact.write_bytes(b"artifact-v743")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        evidence = {
            "plugin.json": {"installed": [{
                "pluginId": "codex-cross-project-engineering-assistant@cp-assistant-local",
                "version": VERSION, "installed": True, "enabled": True,
            }]},
            "life.json": {
                "ok": True, "schema_version": "2.0", "project_id": "project-neutral",
                "repo_fingerprint": "sha256:" + "a" * 64,
                "required_sequence": ["TURN_OPENED", "SUBAGENT_STARTED", "SUBAGENT_STOPPED", "TASK_COMPLETED", "SESSION_ENDED"],
                "privacy": {"host_model_information_read": False, "host_model_information_exported": False},
                "event_chain": {"valid": True, "seal_status": "SEALED_CURRENT", "hmac_verified": True},
            },
            "validation.json": {"ok": True},
            "witness.json": {"ok": True, "reproducible": True, "artifact_sha256": digest},
            "unified.json": {
                "ok": True, "version": VERSION, "artifact_sha256": digest,
                "status": {key: "PASS" for key in (
                    "package", "artifact", "host", "plugin", "lifecycle", "dispatch_policy", "payload"
                )},
            },
            "dispatch.json": dispatch_policy_report(),
        }
        for name, value in evidence.items():
            (self.root / name).write_text(json.dumps(value), encoding="utf-8")
        version = self.root / "version.txt"
        version.write_text("codex-cli 0.153.4\n", encoding="utf-8")
        attestation = self.root / "attestation.json"
        environment = {**os.environ, "CP_ASSISTANT_ATTESTATION_HMAC_KEY": "test-key-v743"}
        run_script(ATTEST, [
            "create", "--artifact", str(artifact), "--plugin-list", str(self.root / "plugin.json"),
            "--lifecycle-report", str(self.root / "life.json"),
            "--package-validation", str(self.root / "validation.json"),
            "--deterministic-witness", str(self.root / "witness.json"),
            "--unified-verification", str(self.root / "unified.json"),
            "--dispatch-policy-report", str(self.root / "dispatch.json"),
            "--codex-version-evidence", str(version), "--output", str(attestation),
        ], environment)
        payload = json.loads(attestation.read_text(encoding="utf-8"))
        self.assertEqual("2.0", payload["schema_version"])
        self.assertEqual("PASS", payload["validation"]["dispatch_policy"])
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("actual_subagent_models", serialized)
        self.assertNotIn("runtime_model", serialized)
        verified = run_script(
            ATTEST, ["verify", "--attestation", str(attestation), "--artifact", str(artifact)], environment
        )
        self.assertTrue(json.loads(verified.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
