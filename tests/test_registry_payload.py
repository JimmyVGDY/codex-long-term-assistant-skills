from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from payload_integrity import iter_payload_files


class RegistryPayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # 中文：仅复制发行 runtime；不带源码 config/scripts。
        # English: Copy only shipped runtime files; source config/scripts are absent.
        for relative, source in iter_payload_files(ROOT):
            if relative.startswith("runtime/"):
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)

    def invoke(self, *args):
        env = dict(os.environ, PYTHONPATH=str(self.root / "runtime"),
                   PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-B", "-m", "cp_runtime.cli",
                               "capability-registry", *args], cwd=self.root,
                              env=env, capture_output=True, text=True,
                              encoding="utf-8", timeout=20)

    def test_installed_payload_default_registry(self):
        result = self.invoke()
        self.assertEqual(0, result.returncode, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(["C%02d" % n for n in range(1, 26)],
                         [item["capability_id"] for item in value["entries"]])

    def test_bundled_registry_matches_authority(self):
        self.assertEqual((ROOT / "config/capability-registry-v1.json").read_bytes(),
                         (self.root / "runtime/cp_runtime/data/capability-registry-v1.json").read_bytes())

    def test_real_packager_default_registry(self):
        from package_manager import plugin_payload_source
        self.root = plugin_payload_source(self.root / "packaged")
        result = self.invoke()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(25, len(json.loads(result.stdout)["entries"]))

    def test_missing_bundled_registry_fails_closed(self):
        (self.root / "runtime/cp_runtime/data/capability-registry-v1.json").unlink()
        result = self.invoke()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("UNREADABLE", result.stderr)

    def test_distribution_manifest_is_not_a_source_checkout(self):
        shutil.copyfile(ROOT / "manifest.json", self.root / "manifest.json")
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/capability-registry-v1.json",
                        self.root / "config/capability-registry-v1.json")
        result = self.invoke()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(25, len(json.loads(result.stdout)["entries"]))

    def test_explicit_missing_registry_does_not_fallback(self):
        result = self.invoke("--registry", str(self.root / "missing.json"))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("UNREADABLE", result.stderr)

    def test_corrupt_bundled_registry_fails_closed(self):
        target = self.root / "runtime/cp_runtime/data/capability-registry-v1.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{", encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("REGISTRY_INVALID_JSON", result.stderr)


if __name__ == "__main__":
    unittest.main()