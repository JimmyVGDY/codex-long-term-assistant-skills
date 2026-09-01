from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_docs_site", ROOT / "scripts" / "build-docs-site.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DocumentationSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = _load_builder()

    def test_site_source_contains_separate_chinese_and_english_documents(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cp-docs-site-") as temporary:
            output = Path(temporary) / "docs-source"
            report = self.builder.prepare(output)
            self.assertTrue(report["ok"])
            self.assertTrue((output / "index.md").is_file())
            self.assertTrue((output / "zh-CN" / "index.md").is_file())
            self.assertTrue((output / "en" / "index.md").is_file())
            self.assertTrue((output / "zh-CN" / "docs" / "INSTALLATION_RECOVERY.md").is_file())
            self.assertTrue((output / "en" / "docs" / "INSTALLATION_RECOVERY.md").is_file())
            self.assertTrue((output / "zh-CN" / "docs" / "history" / "GITHUB_RELEASES.md").is_file())
            self.assertTrue((output / "en" / "docs" / "history" / "GITHUB_RELEASES.md").is_file())
            self.assertTrue((output / "en" / "docs" / "releases" / "RELEASE_AUTOMATION.md").is_file())
            self.assertEqual(report["chinese_markdown"], report["english_markdown"])
            self.assertGreater(report["chinese_markdown"], 50)
            self.assertGreater(report["english_markdown"], 50)
            chinese_home = (output / "zh-CN" / "index.md").read_text(encoding="utf-8")
            english_home = (output / "en" / "index.md").read_text(encoding="utf-8")
            self.assertIn("Codex 跨项目长期技术助手", chinese_home)
            self.assertNotIn("README.en.md", chinese_home)
            self.assertNotIn("INSTALLATION_RECOVERY.en.md", english_home)
            self.assertIn(
                "https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/.github/",
                english_home,
            )

    def test_english_primary_pages_do_not_contain_chinese_prose(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cp-docs-english-") as temporary:
            output = Path(temporary) / "docs-source"
            self.builder.prepare(output)
            paths = [
                output / "en" / "index.md",
                output / "en" / "docs" / "README.md",
                output / "en" / "docs" / "INSTALLATION_RECOVERY.md",
                output / "en" / "docs" / "USER_GUIDE_V6.6.1.md",
                output / "en" / "docs" / "history" / "GITHUB_RELEASES.md",
                output / "en" / "docs" / "releases" / "RELEASE_AUTOMATION.md",
            ]
            for path in paths:
                text = path.read_text(encoding="utf-8-sig")
                self.assertIsNone(re.search(r"[\u4e00-\u9fff]", text), path)

    def test_root_landing_page_is_bilingual_responsive_and_accessible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cp-docs-landing-") as temporary:
            output = Path(temporary) / "docs-source"
            self.builder.prepare(output)
            root = (output / "index.md").read_text(encoding="utf-8")
        english_pair = (
            ROOT / ".github" / "docs-site" / "index.en.md"
        ).read_text(encoding="utf-8")
        stylesheet = (
            ROOT / ".github" / "docs-site" / "stylesheets" / "extra.css"
        ).read_text(encoding="utf-8")
        self.assertIn('class="landing-hero"', root)
        self.assertIn('lang="zh-CN"', root)
        self.assertIn('lang="en"', root)
        self.assertIn("10</strong><span>Skills", root)
        self.assertIn("2.0</strong><span>TaskOutcomeEvent", root)
        self.assertIn("social-preview.png", root)
        self.assertIn("/codex-long-term-assistant-skills/zh-CN/", root)
        self.assertIn("/codex-long-term-assistant-skills/en/", root)
        self.assertIsNone(re.search(r"[\u4e00-\u9fff]", english_pair))
        self.assertIn("@media (max-width: 640px)", stylesheet)
        self.assertIn(":focus-visible", stylesheet)
        self.assertIn("@media (prefers-reduced-motion: reduce)", stylesheet)

    def test_existing_nondefault_output_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cp-docs-boundary-") as temporary:
            output = Path(temporary) / "docs-source"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaises(self.builder.DocumentationBuildError):
                self.builder.prepare(output)
            self.assertEqual("keep", marker.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
