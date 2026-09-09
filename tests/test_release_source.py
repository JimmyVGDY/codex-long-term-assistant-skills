from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_source as source


class ReleaseSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cp-source-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic source test")
        self.git("config", "user.email", "synthetic@example.invalid")
        for name in source.REQUIRED:
            self.put(name, "{}\n" if name.endswith(".json") else "# synthetic\n")
        self.put(".gitignore", ".vscode/\n*.zip\n*.tmp\n")
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic baseline")

    def git(self, *args):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        return subprocess.run(["git", "-C", str(self.root), *args], env=env, check=True,
                              capture_output=True, timeout=30).stdout

    def put(self, name, text):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def capture(self, name="snapshot", **kwargs):
        target = self.base / name
        return source.capture(self.root, target, **kwargs), target

    def test_ignored_and_unrelated_untracked_files_do_not_change_capture(self):
        before, _ = self.capture()
        self.put(".vscode/settings.json", '{"synthetic":true}')
        self.put("old.zip", "old artifact")
        self.put("scratch.tmp", "temporary")
        self.put("scratch.txt", "unrelated")
        after, target = self.capture("after")
        self.assertEqual(before, after)
        self.assertFalse((target / ".vscode").exists())

    def test_new_required_input_must_be_staged_then_is_included(self):
        self.put("scripts/new_module.py", "ANSWER = 42\n")
        with self.assertRaisesRegex(source.SourceError, "untracked source input"):
            self.capture()
        self.git("add", "scripts/new_module.py")
        _, target = self.capture()
        self.assertEqual("ANSWER = 42\n", (target / "scripts/new_module.py").read_text())

    def test_tracked_worktree_bytes_are_used_and_formal_capture_requires_clean(self):
        self.put("scripts/build-release.py", "# changed candidate\n")
        _, target = self.capture()
        self.assertEqual("# changed candidate\n", (target / "scripts/build-release.py").read_text())
        with self.assertRaisesRegex(source.SourceError, "clean tracked"):
            self.capture("formal", require_clean=True)

    def test_missing_tracked_or_declared_source_fails(self):
        (self.root / "hooks/hooks.json").unlink()
        with self.assertRaises(OSError):
            self.capture()
        self.git("rm", "hooks/hooks.json")
        with self.assertRaisesRegex(source.SourceError, "required source input"):
            self.capture()

    def test_gitless_requires_manifest_and_never_discovers_outer_git(self):
        nested = self.root / "nested"
        nested.mkdir()
        with mock.patch.object(source, "_git", side_effect=AssertionError("outer Git used")):
            with self.assertRaisesRegex(source.SourceError, "requires SOURCE_MANIFEST"):
                source.capture(nested, self.base / "result")

    def test_valid_snapshot_ignores_unlisted_overlay_and_preserves_digest(self):
        manifest, snapshot = self.capture()
        injected = snapshot / "locales/en/scripts/unlisted.py"
        injected.parent.mkdir(parents=True)
        injected.write_text("unlisted = True\n")
        copied = self.base / "second"
        result = source.capture(snapshot, copied)
        self.assertEqual(manifest, result)
        self.assertFalse((copied / "locales/en/scripts/unlisted.py").exists())

    def test_snapshot_rejects_tampered_or_missing_listed_file(self):
        _, snapshot = self.capture()
        path = snapshot / "scripts/build-release.py"
        path.write_text("tampered\n")
        with self.assertRaisesRegex(source.SourceError, "content mismatch"):
            source.capture(snapshot, self.base / "second")
        path.unlink()
        with self.assertRaises(OSError):
            source.capture(snapshot, self.base / "second")
        self.assertFalse((self.base / "second").exists())

    def test_manifest_duplicate_keys_and_bad_digest_fail(self):
        _, snapshot = self.capture()
        path = snapshot / source.MANIFEST_NAME
        saved = path.read_text(encoding="utf-8")
        path.write_text(saved.replace('"schema_version":1', '"schema_version":1,"schema_version":1'))
        with self.assertRaisesRegex(source.SourceError, "duplicate"):
            source.capture(snapshot, self.base / "second")
        data = json.loads(saved)
        data["content_digest"] = "0" * 64
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(source.SourceError, "digest"):
            source.capture(snapshot, self.base / "second")

    def test_unsafe_paths_and_windows_collisions_fail(self):
        for value in (".", "../escape", "a/../b", "a//b", "a/./b", "/root", "C:/a",
                      "a\\b", "a:stream", "NUL.txt", "foo.", "foo "):
            with self.subTest(value=value), self.assertRaises(source.SourceError):
                source.relative_path(value)
        for values in (["a", "a"], ["A", "a"], ["a", "a/b"], ["a/b", "a"], ["A/b", "a/c"]):
            with self.subTest(values=values), self.assertRaises(source.SourceError):
                source._paths(values)

    def test_link_ancestor_is_rejected(self):
        target = self.base / "outside"
        target.mkdir()
        (target / "file.py").write_text("value = 1\n")
        link = self.root / "linked"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation unavailable")
        with self.assertRaisesRegex(source.SourceError, "link/reparse"):
            source._read(link / "file.py")

    def test_change_after_capture_fails_without_publishing_partial_snapshot(self):
        original = source._read
        changed = False

        def racing_read(path, *args):
            nonlocal changed
            data = original(path, *args)
            if path == self.root / "scripts/build-release.py" and not changed:
                changed = True
                path.write_text("# changed while capturing\n")
            return data

        with mock.patch.object(source, "_read", side_effect=racing_read):
            with self.assertRaisesRegex(source.SourceError, "changed after capture"):
                self.capture()
        self.assertFalse((self.base / "snapshot").exists())

    def test_index_change_during_capture_fails(self):
        original = source._git_state
        calls = 0

        def racing_state(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.put("scripts/new.py", "# newly tracked\n")
                self.git("add", "scripts/new.py")
            return original(*args)

        with mock.patch.object(source, "_git_state", side_effect=racing_state):
            with self.assertRaisesRegex(source.SourceError, "set changed"):
                self.capture()

    def test_git_output_limit_stops_stdout_and_stderr_producers(self):
        popen = subprocess.Popen
        for channel in ("stdout", "stderr"):
            def producer(*args, **kwargs):
                return popen([sys.executable, "-c", "import sys; sys.%s.write('x' * 131072)" % channel],
                             **kwargs)
            with self.subTest(channel=channel), mock.patch.object(source, "MAX_LIST_BYTES", 1024), \
                    mock.patch.object(source.subprocess, "Popen", side_effect=producer):
                with self.assertRaisesRegex(source.SourceError, "output limit"):
                    source._git(self.root, "ls-files")

    def test_malformed_package_declarations_fail_without_publishing_snapshot(self):
        for manifest in ([], {"skills": {}}, {"skills": [None]}, {"skills": [{}]},
                         {"skills": [{"name": "../escape"}]}, {"custom_agents": "invalid"},
                         {"custom_agents": [{}]}, {"custom_agents": [{"file": None}]}):
            with self.subTest(manifest=manifest):
                self.put("manifest.json", json.dumps(manifest))
                with self.assertRaisesRegex(source.SourceError, "invalid package manifest"):
                    self.capture()
                self.assertFalse((self.base / "snapshot").exists())


class SnapshotBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="cp-snapshot-build-")
        cls.base = Path(cls.temp.name)
        cls.snapshot = cls.base / "source"
        source.capture(ROOT, cls.snapshot)
        spec = importlib.util.spec_from_file_location("snapshot_builder", ROOT / "scripts/build-release.py")
        cls.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.builder)
        cls.builder.ROOT = cls.snapshot

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_both_locales_build_from_explicit_snapshot_without_provenance_input_in_package(self):
        injected = self.snapshot / "locales/en/docs/unlisted.md"
        injected.write_text("synthetic unlisted content", encoding="utf-8")
        for locale in ("zh-CN", "en"):
            archive = self.base / (locale + ".zip")
            self.builder.build_release(archive, locale)
            with zipfile.ZipFile(archive) as opened:
                names = opened.namelist()
                self.assertFalse(any(name.endswith(source.MANIFEST_NAME) for name in names))
                self.assertFalse(any(name.endswith("unlisted.md") for name in names))
                self.assertTrue(any(name.endswith("scripts/release_source.py") for name in names))

    def test_runtime_mapping_unsafe_or_missing_target_fails(self):
        overlay = self.snapshot / "locales/en"
        mapping = self.builder.load_mapping(overlay / "runtime-strings.json")
        for name in ("../escape.py", "scripts/absent.py"):
            modified = dict(mapping, files={**mapping["files"], name: {}})
            with tempfile.TemporaryDirectory() as temporary:
                staging = Path(temporary) / "staged"
                self.builder._copy_source(self.snapshot, staging)
                with mock.patch.object(self.builder, "load_mapping", return_value=modified):
                    with self.assertRaises((source.SourceError, self.builder.BuildError)):
                        self.builder._apply_overlay(staging, "en", self.snapshot)


if __name__ == "__main__":
    unittest.main()
