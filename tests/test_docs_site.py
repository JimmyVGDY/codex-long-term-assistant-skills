from __future__ import annotations

import importlib.util
import json
import re
import struct
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    offset = 2
    start_of_frame = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset + 8 <= len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9}:
            continue
        length = int.from_bytes(data[offset:offset + 2], "big")
        if marker in start_of_frame:
            height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
            return width, height
        if length < 2:
            break
        offset += length
    raise AssertionError("JPEG dimensions were not found")


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
            self.assertTrue((output / "javascripts" / "repository-facts.js").is_file())
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
                output / "en" / "docs" / "USER_GUIDE_V7.0.md",
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
        self.assertIn("social-preview.jpg", root)
        self.assertIn("V7.0.0", root)
        self.assertNotIn("V6.6.1", root)
        self.assertIn("USER_GUIDE_V7.0", root)
        self.assertIn("/codex-long-term-assistant-skills/zh-CN/", root)
        self.assertIn("/codex-long-term-assistant-skills/en/", root)
        self.assertIn("V7.0.0", english_pair)
        self.assertNotIn("V6.6.1", english_pair)
        self.assertIn("USER_GUIDE_V7.0", english_pair)
        self.assertIsNone(re.search(r"[\u4e00-\u9fff]", english_pair))
        self.assertIn("@media (max-width: 640px)", stylesheet)
        self.assertIn(":focus-visible", stylesheet)
        self.assertIn("@media (prefers-reduced-motion: reduce)", stylesheet)

    def test_repository_facts_script_repairs_stale_release_version(self) -> None:
        script = (
            ROOT / ".github" / "docs-site" / "javascripts" / "repository-facts.js"
        ).read_text(encoding="utf-8")
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        expected = f'const RELEASE_VERSION = "v{manifest["version"]}";'
        self.assertIn(expected, script)
        self.assertIn('const SOURCE_CACHE_MARKER = "__source";', script)
        self.assertIn('const VERSION_SELECTOR = ".md-source__fact--version";', script)
        self.assertIn("sessionStorage.setItem", script)
        self.assertIn("new MutationObserver", script)
        self.assertNotIn("v6.6.1", script)

        for path in (
            ROOT / ".github" / "mkdocs.yml",
            ROOT / "locales" / "en" / ".github" / "mkdocs.yml",
        ):
            self.assertIn(
                "javascripts/repository-facts.js",
                path.read_text(encoding="utf-8"),
            )

    def test_v7_site_navigation_ci_and_security_metadata_are_current(self) -> None:
        navigation = (ROOT / ".github" / "mkdocs.yml").read_text(encoding="utf-8")
        localized_navigation = (
            ROOT / "locales" / "en" / ".github" / "mkdocs.yml"
        ).read_text(encoding="utf-8")
        for text in (navigation, localized_navigation):
            self.assertIn("USER_GUIDE_V7.0.md", text)
            self.assertIn("V7_DOMAIN_SKILL_ARCHITECTURE.md", text)
            self.assertIn("releases/v7.0.0/RELEASE_NOTES.md", text)

        for path in (
            ROOT / ".github" / "workflows" / "ci.yml",
            ROOT / "locales" / "en" / ".github" / "workflows" / "ci.yml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("release-workflow.py metadata --format github", text)
            self.assertIn("steps.metadata.outputs.archive_zh", text)
            self.assertNotIn("Codex-Skills-V6.6.1", text)

        for path in (
            ROOT / ".github" / "SECURITY.md",
            ROOT / ".github" / "SECURITY.en.md",
            ROOT / "locales" / "en" / ".github" / "SECURITY.md",
        ):
            self.assertIn("7.0.0", path.read_text(encoding="utf-8"))

    def test_social_preview_is_reusable_1280_by_640_and_below_one_megabyte(self) -> None:
        image = (ROOT / "docs" / "assets" / "social-preview.jpg").read_bytes()
        self.assertEqual(b"\xff\xd8", image[:2])
        self.assertEqual((1280, 640), _jpeg_dimensions(image))
        self.assertLess(len(image), 1_000_000)

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
