from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_release_v661", ROOT / "scripts" / "build-release.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V661BilingualReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="cp-v661-bilingual-")
        cls.root = Path(cls.temporary.name)
        cls.builder = _load_builder()
        cls.archives = {}
        cls.reports = {}
        for locale in ("zh-CN", "en"):
            archive = cls.root / ("Codex-Skills-V6.6.1-%s.zip" % locale)
            witness = cls.root / ("witness-%s.json" % locale)
            cls.reports[locale] = cls.builder.reproducible_build(archive, witness, locale)
            cls.archives[locale] = archive
        cls.english_root = cls.root / "english-extracted"
        with zipfile.ZipFile(cls.archives["en"]) as archive:
            archive.extractall(cls.english_root)
        cls.english_root = cls.english_root / "Codex-Skills-V6.6.1-en"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _entries(self, locale: str):
        root = "Codex-Skills-V6.6.1-%s/" % locale
        with zipfile.ZipFile(self.archives[locale]) as archive:
            return root, {name.removeprefix(root): archive.read(name) for name in archive.namelist()}

    def test_two_archives_are_reproducible_distinct_and_locale_bound(self) -> None:
        self.assertTrue(self.reports["zh-CN"]["reproducible"])
        self.assertTrue(self.reports["en"]["reproducible"])
        self.assertNotEqual(self.reports["zh-CN"]["artifact_sha256"], self.reports["en"]["artifact_sha256"])
        for locale in ("zh-CN", "en"):
            report = self.builder.verify_release(self.archives[locale], locale)
            self.assertEqual(locale, report["locale"])
            _, entries = self._entries(locale)
            self.assertEqual(locale, json.loads(entries["config/locale.json"])["locale"])
            self.assertEqual("6.6.1", json.loads(entries["manifest.json"])["version"])
            self.assertEqual("6.6.1", json.loads(entries[".codex-plugin/plugin.json"])["version"])

    def test_both_archives_contain_ten_skills_and_seven_model_neutral_reviewers(self) -> None:
        for locale in ("zh-CN", "en"):
            _, entries = self._entries(locale)
            manifest = json.loads(entries["manifest.json"])
            self.assertEqual(10, len(manifest["skills"]))
            self.assertEqual(7, len(manifest["custom_agents"]))
            for skill in manifest["skills"]:
                text = entries["skills/%s/SKILL.md" % skill["name"]].decode("utf-8")
                self.assertTrue(text.startswith("---\n"))
            for reviewer in manifest["custom_agents"]:
                value = tomllib.loads(entries[reviewer["file"]].decode("utf-8"))
                self.assertNotIn("model", value)
                self.assertNotIn("model_reasoning_effort", value)

    def test_english_primary_surfaces_are_english_and_overlay_sources_are_not_shipped(self) -> None:
        _, entries = self._entries("en")
        primary = ["README.md", "global/AGENTS.md", "RELEASE_NOTES_V6.6.1.md",
                   "docs/USER_GUIDE_V6.6.1.md", "docs/INSTALLATION_RECOVERY.md",
                   "docs/CODEX_CONFIG_GUIDE.md", ".codex-plugin/plugin.json"]
        primary.extend("skills/%s/SKILL.md" % item["name"] for item in json.loads(entries["manifest.json"])["skills"])
        primary.extend(item["file"] for item in json.loads(entries["manifest.json"])["custom_agents"])
        for path in primary:
            text = entries[path].decode("utf-8")
            self.assertIsNone(re.search(r"[\u4e00-\u9fff]", text), path)
        self.assertFalse(any(path.startswith("locales/") for path in entries))

    def test_archives_exclude_unrelated_brand_and_personal_paths(self) -> None:
        text_suffixes = {".md", ".json", ".toml", ".yaml", ".yml", ".py", ".ps1", ".sh", ".cmd", ".txt"}
        for locale in ("zh-CN", "en"):
            _, entries = self._entries(locale)
            for path, body in entries.items():
                excluded_brand = "clau" + "de"
                self.assertNotIn(excluded_brand, path.lower())
                if Path(path).suffix.lower() in text_suffixes:
                    text = body.decode("utf-8-sig", errors="replace").lower()
                    self.assertNotIn(excluded_brand, text, path)
                    self.assertNotIn("c:\\users\\hp", text, path)

    def test_english_hook_returns_english_model_gate_reason(self) -> None:
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent",
                   "tool_input": {"model": "gpt-5.6-sol", "reasoning_effort": "high"}}
        environment = dict(os.environ, PLUGIN_ROOT=str(self.english_root))
        result = subprocess.run(
            [sys.executable, str(self.english_root / "hooks" / "cp_hook.py"), "PreToolUse"],
            input=json.dumps(payload), text=True, encoding="utf-8", capture_output=True,
            env=environment, timeout=10)
        self.assertEqual(0, result.returncode)
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIsNone(re.search(r"[\u4e00-\u9fff]", reason))
        self.assertIn("Terra High", reason)


if __name__ == "__main__":
    unittest.main()
