"""中文：固定夹具仅在原哈希和精确注释位置匹配时使用英文配对。

English: Frozen fixtures use companion prose only for their exact hash and comment location.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "tests/fixtures/review-workflow-v2/optional-identities.py"
sys.path.insert(0, str(ROOT / "scripts"))


def load_audit():
    spec = importlib.util.spec_from_file_location("fixture_localization_audit", ROOT / "scripts/localization-audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrozenFixtureLocalizationTests(unittest.TestCase):
    def check_fixture(self, relative, content):
        module = load_audit()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            with patch.object(module, "ROOT", root):
                return module.audit_python(target, target.read_text(encoding="utf-8"))

    def test_original_bytes_have_exact_companion(self):
        self.assertEqual([], self.check_fixture(RELATIVE, (ROOT / RELATIVE).read_bytes()))

    def test_changed_fixture_is_not_exempt(self):
        findings = self.check_fixture(RELATIVE, (ROOT / RELATIVE).read_bytes() + b"\n")
        self.assertIn("FROZEN_FIXTURE_SOURCE_CHANGED", {item["code"] for item in findings})
        self.assertIn("COMMENT_BLOCK_NOT_BILINGUAL", {item["code"] for item in findings})

    def test_same_bytes_at_another_path_are_not_exempt(self):
        findings = self.check_fixture("ordinary.py", (ROOT / RELATIVE).read_bytes())
        self.assertIn("COMMENT_BLOCK_NOT_BILINGUAL", {item["code"] for item in findings})


if __name__ == "__main__":
    unittest.main()
