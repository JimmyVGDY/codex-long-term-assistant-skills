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
        cls.temporary = tempfile.TemporaryDirectory(prefix="cp-v64-release-")
        cls.root = Path(cls.temporary.name)
        cls.builder = load_script("build_release_v64", "build-release.py")
        cls.verifier = load_script("verify_release_v64", "verify-release.py")
        cls.artifact = cls.root / "Codex-Skills-V6.4.zip"
        cls.build = cls.builder.build_release(ROOT, cls.artifact)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def evidence(self):
        digest = json.loads((ROOT / "PLUGIN_PAYLOAD_MANIFEST.json").read_text(encoding="utf-8"))["payload_digest"]
        package = {"ok": True, "version": "6.4.0"}
        witness = {"ok": True, "reproducible": True, "version": "6.4.0",
                   "artifact_sha256": hashlib.sha256(self.artifact.read_bytes()).hexdigest()}
        plugin = {"installed": [{"pluginId": "codex-cross-project-engineering-assistant@cp-assistant-local",
                                  "name": "codex-cross-project-engineering-assistant",
                                  "marketplaceName": "cp-assistant-local", "version": "6.4.0",
                                  "installed": True, "enabled": True}]}
        lifecycle = {"ok": True, "project_id": "project-v64", "repo_fingerprint": "sha256:" + "b" * 64,
                     "actual_subagent_models": ["gpt-5.6-luna"],
                     "event_chain": {"valid": True, "head": "c" * 64}}
        host = {"codex_version": "codex-cli 0.150.1", "capability_profile": {"ok": True}}
        report = {key: {"ok": True, "payload_digest": digest} for key in ("source", "marketplace", "cache")}
        return package, witness, plugin, lifecycle, host, report

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
        evidence[4]["capability_profile"] = {"ok": False}
        with self.assertRaises(self.verifier.VerificationError):
            self.verifier.verify_release(self.artifact, *evidence)


if __name__ == "__main__":
    unittest.main()
