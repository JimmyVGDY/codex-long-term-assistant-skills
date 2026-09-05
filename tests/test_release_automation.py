#!/usr/bin/env python3
"""中文：回归验证 GitHub Release 自动化的版本、安全与双语边界。

English: Regress version, safety, and bilingual boundaries of GitHub Release automation.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "release_workflow", ROOT / "scripts" / "release-workflow.py"
)
assert SPEC and SPEC.loader
release_workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_workflow)


class ReleaseAutomationTests(unittest.TestCase):
    def _fixture(
        self,
        root: Path,
        version: str = "6.6.1",
        plugin_version: str = "6.6.1",
        release_name_zh: object = "根任务预算治理",
        release_name_en: object = "Root-task budget governance",
    ) -> None:
        (root / ".codex-plugin").mkdir(parents=True)
        (root / "docs" / "releases" / ("v" + version)).mkdir(parents=True)
        (root / "locales" / "en").mkdir(parents=True)
        (root / "manifest.json").write_text(
            json.dumps({"version": version, "release_name": release_name_zh}), encoding="utf-8"
        )
        (root / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"version": plugin_version}), encoding="utf-8"
        )
        (root / "locales" / "en" / "manifest-localization.json").write_text(
            json.dumps({"release_name": release_name_en}), encoding="utf-8"
        )
        release_root = root / "docs" / "releases" / ("v" + version)
        (release_root / "RELEASE_NOTES.md").write_text("zh\n", encoding="utf-8")
        (release_root / "RELEASE_NOTES.en.md").write_text("en\n", encoding="utf-8")

    def test_metadata_requires_matching_manifest_plugin_and_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._fixture(root)
            metadata = release_workflow.release_metadata(root, "v6.6.1")
            self.assertEqual("6.6.1", metadata["version"])
            self.assertEqual("Codex-Skills-V6.6.1-en.zip", metadata["archive_en"])
            self.assertEqual(
                "V6.6.1 | 根任务预算治理 / Root-task budget governance",
                metadata["release_title"],
            )
            with self.assertRaises(release_workflow.ReleaseWorkflowError):
                release_workflow.release_metadata(root, "v6.6.0")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._fixture(root, plugin_version="6.6.0")
            with self.assertRaises(release_workflow.ReleaseWorkflowError):
                release_workflow.release_metadata(root)

    def test_metadata_rejects_unsafe_or_generic_release_names(self) -> None:
        cases = (
            ("", "Root-task budget governance"),
            (" 根任务预算治理", "Root-task budget governance"),
            ("根任务\n预算治理", "Root-task budget governance"),
            ("根任务\u200b预算治理", "Root-task budget governance"),
            ("中英文发行候选", "Root-task budget governance"),
            ("发" * 31, "Root-task budget governance"),
            ("根任务预算治理", ""),
            ("根任务预算治理", "Root-task budget governance\rrelease"),
            ("根任务预算治理", "Bilingual release candidate"),
            ("根任务预算治理", "中文标题"),
            ("根任务预算治理", "x" * 81),
            ("根任务预算治理", "🚀" * 60),
        )
        for release_name_zh, release_name_en in cases:
            with self.subTest(zh=release_name_zh, en=release_name_en):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    self._fixture(
                        root,
                        release_name_zh=release_name_zh,
                        release_name_en=release_name_en,
                    )
                    with self.assertRaises(release_workflow.ReleaseWorkflowError):
                        release_workflow.release_metadata(root)

    def test_metadata_accepts_release_name_length_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._fixture(
                root,
                release_name_zh="发" * 30,
                release_name_en="x" * 80,
            )
            metadata = release_workflow.release_metadata(root)
            self.assertEqual(
                "V6.6.1 | %s / %s" % ("发" * 30, "x" * 80),
                metadata["release_title"],
            )

    def test_github_metadata_keeps_shell_metacharacters_as_single_line_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._fixture(
                root,
                release_name_zh='标题=百分比%引号"反引号`美元$()',
                release_name_en='Title = 100% "quoted" `tick` $HOME $(noop)',
            )
            metadata = release_workflow.release_metadata(root)
            rendered = release_workflow._render_metadata(metadata, "github")
            self.assertEqual(
                "release_title=%s" % metadata["release_title"],
                next(
                    line for line in rendered.splitlines()
                    if line.startswith("release_title=")
                ),
            )
            self.assertEqual(len(metadata), len(rendered.splitlines()))

    def test_github_metadata_renders_release_title_as_one_line(self) -> None:
        metadata = release_workflow.release_metadata(ROOT, "v7.4.6")
        rendered = release_workflow._render_metadata(metadata, "github")
        expected = "release_title=%s" % metadata["release_title"]
        self.assertEqual(1, rendered.splitlines().count(expected))
        self.assertNotIn("\r", rendered)

    def test_checksums_are_bounded_complete_and_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            self._fixture(root)
            release = Path(temporary) / "release"
            release.mkdir()
            metadata = release_workflow.release_metadata(root)
            names = [metadata["archive_zh"], metadata["archive_en"],
                     metadata["witness_zh"], metadata["witness_en"], metadata["provenance"]]
            for index, name in enumerate(names):
                (release / name).write_bytes(("artifact-%d" % index).encode("utf-8"))
            (release / metadata["release_notes"]).write_text("notes\n", encoding="utf-8")
            output = release / metadata["checksums"]
            result = release_workflow.write_checksums(release, output, root)
            self.assertEqual(sorted(names), result["files"])
            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(sorted(names), [line.split("  ", 1)[1] for line in lines])
            expected = hashlib.sha256((release / sorted(names)[0]).read_bytes()).hexdigest()
            self.assertEqual(expected, lines[0].split("  ", 1)[0])

    def test_downloaded_candidate_is_exact_and_bound_to_checksums_and_witnesses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            self._fixture(root)
            release = Path(temporary) / "release"
            release.mkdir()
            metadata = release_workflow.release_metadata(root)
            archives = ((metadata["archive_zh"], metadata["witness_zh"], "zh-CN"),
                        (metadata["archive_en"], metadata["witness_en"], "en"))
            for index, (archive_name, witness_name, locale) in enumerate(archives):
                archive = release / archive_name
                archive.write_bytes(("archive-%d" % index).encode("utf-8"))
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                (release / witness_name).write_text(json.dumps({
                    "ok": True, "reproducible": True, "version": "6.6.1", "locale": locale,
                    "artifact_sha256": digest, "first_sha256": digest, "second_sha256": digest,
                    "artifact_size": archive.stat().st_size,
                }), encoding="utf-8")
            (release / metadata["provenance"]).write_text(json.dumps({"bundle": "fixture"}), encoding="utf-8")
            (release / metadata["release_notes"]).write_text("notes\n", encoding="utf-8")
            release_workflow.write_checksums(release, release / metadata["checksums"], root)
            result = release_workflow.verify_candidate(release, root)
            self.assertTrue(result["ok"])

            (release / metadata["archive_en"]).write_bytes(b"tampered")
            with self.assertRaises(release_workflow.ReleaseWorkflowError):
                release_workflow.verify_candidate(release, root)

    def test_downloaded_candidate_rejects_extra_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            self._fixture(root)
            release = Path(temporary) / "release"
            release.mkdir()
            metadata = release_workflow.release_metadata(root)
            for archive_name, witness_name, locale in (
                (metadata["archive_zh"], metadata["witness_zh"], "zh-CN"),
                (metadata["archive_en"], metadata["witness_en"], "en"),
            ):
                archive = release / archive_name
                archive.write_bytes(locale.encode("utf-8"))
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                (release / witness_name).write_text(json.dumps({
                    "ok": True, "reproducible": True, "version": "6.6.1", "locale": locale,
                    "artifact_sha256": digest, "first_sha256": digest, "second_sha256": digest,
                    "artifact_size": archive.stat().st_size,
                }), encoding="utf-8")
            (release / metadata["provenance"]).write_text("{}", encoding="utf-8")
            (release / metadata["release_notes"]).write_text("notes\n", encoding="utf-8")
            release_workflow.write_checksums(release, release / metadata["checksums"], root)
            (release / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(release_workflow.ReleaseWorkflowError):
                release_workflow.verify_candidate(release, root)

    def test_workflow_attests_artifacts_and_only_creates_a_draft(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        uses = re.findall(r"^\s*uses:\s*([^\s#]+)", workflow, re.MULTILINE)
        self.assertTrue(uses)
        self.assertTrue(all(
            re.fullmatch(r"actions/[A-Za-z0-9._-]+@[0-9a-f]{40}", item)
            or item == "./.github/workflows/codex-compatibility.yml"
            for item in uses
        ))
        self.assertIn("id-token: write", workflow)
        self.assertIn("attestations: write", workflow)
        self.assertIn("artifact-metadata: write", workflow)
        self.assertIn('- "v*.*.*"', workflow)
        self.assertIn("--draft", workflow)
        self.assertNotIn("--clobber", workflow)
        self.assertIn("Release already exists; no assets were replaced.", workflow)
        self.assertIn("if: github.ref_type == 'tag'", workflow)
        self.assertIn("verify-candidate --directory candidate", workflow)
        self.assertIn("gh attestation verify", workflow)
        self.assertNotIn("candidate/*.zip", workflow)
        self.assertNotIn("candidate/*.json", workflow)
        for relative in (
            ".github/workflows/release.yml",
            "locales/en/.github/workflows/release.yml",
        ):
            localized_workflow = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(
                "release_title: ${{ steps.metadata.outputs.release_title }}",
                localized_workflow,
            )
            self.assertIn(
                "RELEASE_TITLE: ${{ needs.build.outputs.release_title }}",
                localized_workflow,
            )
            self.assertIn('--title "$RELEASE_TITLE"', localized_workflow)
            self.assertNotIn("Bilingual release candidate", localized_workflow)
            self.assertNotIn('--title "${{', localized_workflow)

    def test_generated_release_body_contains_both_languages_without_relative_selector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "notes.md"
            release_workflow.write_release_notes(output)
            value = output.read_text(encoding="utf-8")
            self.assertIn("# V7.4.6 发行说明", value)
            self.assertIn("# V7.4.6 Release Notes", value)
            self.assertNotIn("English: [RELEASE_NOTES.en.md]", value)
            self.assertNotIn("Chinese: [RELEASE_NOTES.md]", value)


if __name__ == "__main__":
    unittest.main()
