from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V64ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="cp-v65-release-")
        cls.root = Path(cls.temporary.name)
        cls.builder = load_script("build_release_v65", "build-release.py")
        cls.verifier = load_script("verify_release_v65", "verify-release.py")
        cls.artifact = cls.root / "Codex-Skills-V7.0.0-zh-CN.zip"
        cls.build = cls.builder.build_release(cls.artifact, "zh-CN")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def evidence(self):
        digest = json.loads((ROOT / "PLUGIN_PAYLOAD_MANIFEST.json").read_text(encoding="utf-8"))["payload_digest"]
        package = {"ok": True, "version": "7.0.0"}
        witness = {"ok": True, "reproducible": True, "version": "7.0.0",
                   "artifact_sha256": hashlib.sha256(self.artifact.read_bytes()).hexdigest()}
        plugin = {"installed": [{"pluginId": "codex-cross-project-engineering-assistant@cp-assistant-local",
                                  "name": "codex-cross-project-engineering-assistant",
                                  "marketplaceName": "cp-assistant-local", "version": "7.0.0",
                                  "installed": True, "enabled": True}]}
        lifecycle = {"ok": True, "project_id": "project-v65", "repo_fingerprint": "sha256:" + "b" * 64,
                     "requested_model_policy": "PASS", "runtime_model_evidence": "UNAVAILABLE",
                     "diagnostic_model_observation": "gpt-5.6-luna / low",
                     "actual_subagent_models": [],
                     "subagent_model_evidence": {"status": "NOT_REQUESTED", "host_session_match": True,
                                                  "host_session_trust_level": "DIAGNOSTIC"},
                     "event_chain": {"valid": True, "head": "c" * 64}}
        gate = {"ok": True, "requested_model_policy": "PASS", "automatic_ceiling": "gpt-5.6-terra + high", "cases": [
            {"model": model, "reasoning_effort": effort, "actual": actual,
             "expected": actual, "returncode": 0, "pass": True}
            for model, effort, actual in (
                ("gpt-5.6-luna", "low", "allow"),
                ("gpt-5.6-luna", "medium", "allow"),
                ("gpt-5.6-terra", "medium", "allow"),
                ("gpt-5.6-terra", "high", "allow"),
                ("gpt-5.6-terra", "xhigh", "deny"),
                ("gpt-5.6-sol", "low", "deny"),
            )]}
        host = {"codex_version": "codex-cli 0.150.1", "capability_profile": {"ok": True}}
        report = {key: {"ok": True, "payload_digest": digest} for key in ("source", "marketplace", "cache")}
        return package, witness, plugin, lifecycle, gate, host, report

    def test_unified_verifier_derives_all_pass_states(self) -> None:
        result = self.verifier.verify_release(self.artifact, *self.evidence())
        self.assertTrue(result["ok"])
        self.assertEqual({"PASS"}, set(result["status"].values()))

    def test_unified_verifier_rejects_wrong_payload_and_missing_host_capability(self) -> None:
        evidence = list(self.evidence())
        evidence[-1]["cache"]["payload_digest"] = "0" * 64
        with self.assertRaises(self.verifier.VerificationError):
            self.verifier.verify_release(self.artifact, *evidence)
        evidence = list(self.evidence())
        evidence[5]["capability_profile"] = {"ok": False}
        with self.assertRaises(self.verifier.VerificationError):
            self.verifier.verify_release(self.artifact, *evidence)

    def test_unified_verifier_rejects_incomplete_model_gate(self) -> None:
        evidence = list(self.evidence())
        evidence[4]["cases"] = [row for row in evidence[4]["cases"]
                                if row["reasoning_effort"] != "xhigh"]
        with self.assertRaises(self.verifier.VerificationError):
            self.verifier.verify_release(self.artifact, *evidence)


if __name__ == "__main__":
    unittest.main()
