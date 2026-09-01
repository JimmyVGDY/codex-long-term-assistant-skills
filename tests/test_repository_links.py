from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_links", ROOT / "scripts" / "check-links.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checker = _load_checker()

    def test_repository_markdown_links_are_valid(self) -> None:
        report = self.checker.audit(self.checker.tracked_markdown())
        self.assertTrue(report["ok"], report["findings"][:20])
        self.assertGreaterEqual(report["markdown_files"], 300)
        self.assertGreater(report["link_count"], 100)

    def test_missing_target_and_anchor_are_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cp-link-audit-") as temporary:
            root = Path(temporary)
            source = root / "README.md"
            target = root / "guide.md"
            source.write_text("[missing](none.md)\n[anchor](guide.md#absent)\n", encoding="utf-8")
            target.write_text("# Present\n", encoding="utf-8")
            original = self.checker.ROOT
            self.checker.ROOT = root
            try:
                report = self.checker.audit([source])
            finally:
                self.checker.ROOT = original
        self.assertEqual(
            {"LOCAL_TARGET_MISSING", "LOCAL_ANCHOR_MISSING"},
            {row["code"] for row in report["findings"]},
        )

    def test_code_examples_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cp-link-code-") as temporary:
            root = Path(temporary)
            source = root / "README.md"
            source.write_text("```markdown\n[example](missing.md)\n```\n", encoding="utf-8")
            original = self.checker.ROOT
            self.checker.ROOT = root
            try:
                report = self.checker.audit([source])
            finally:
                self.checker.ROOT = original
        self.assertTrue(report["ok"], report["findings"])

    def test_repository_github_urls_map_to_local_files(self) -> None:
        value = (
            "https://github.com/example-owner/codex-long-term-assistant-skills/"
            "blob/main/.github/CONTRIBUTING.en.md"
        )
        self.assertEqual(".github/CONTRIBUTING.en.md", self.checker.repository_target(value))


if __name__ == "__main__":
    unittest.main()
