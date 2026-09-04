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
        cls.artifact = cls.root / "Codex-Skills-V7.4.3-zh-CN.zip"
        cls.build = cls.builder.build_release(cls.artifact, "zh-CN")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def evidence(self):
        digest = json.loads((ROOT / "PLUGIN_PAYLOAD_MANIFEST.json").read_text(encoding="utf-8"))["payload_digest"]
        package = {"ok": True, "version": "7.4.3"}
        witness = {"ok": True, "reproducible": True, "version": "7.4.3",
                   "artifact_sha256": hashlib.sha256(self.artifact.read_bytes()).hexdigest()}
        plugin = {"installed": [{"pluginId": "codex-cross-project-engineering-assistant@cp-assistant-local",
                                  "name": "codex-cross-project-engineering-assistant",
                                  "marketplaceName": "cp-assistant-local", "version": "7.4.3",
                                  "installed": True, "enabled": True}]}
        lifecycle = {"ok": True, "schema_version": "2.0", "project_id": "project-v65",
                     "repo_fingerprint": "sha256:" + "b" * 64,
                     "privacy": {"host_model_information_read": False,
                                 "host_model_information_exported": False},
                     "event_chain": {"valid": True, "head": "c" * 64}}
        gate = {"ok": True, "schema_version": "2.0", "dispatch_policy_status": "PASS",
                "automatic_ceiling_profile": "terra-high", "cases": [
                    {"case_id": "allow-low", "expected": "allow", "observed": "allow",
                     "exit_code": 0, "pass": True},
                    {"case_id": "deny-high", "expected": "deny", "observed": "deny",
                     "exit_code": 0, "pass": True}],
                "privacy": {"host_model_information_collected": False,
                            "host_model_information_exported": False}}
        host = {"codex_version": "codex-cli 0.153.2", "capability_profile": {"ok": True}}
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

    def test_unified_verifier_rejects_incomplete_dispatch_policy(self) -> None:
        evidence = list(self.evidence())
        evidence[4]["cases"][0]["observed"] = "deny"
        with self.assertRaises(self.verifier.VerificationError):
            self.verifier.verify_release(self.artifact, *evidence)


if __name__ == "__main__":
    unittest.main()
