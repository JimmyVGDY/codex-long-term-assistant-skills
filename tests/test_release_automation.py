#!/usr/bin/env python3
"""中文：回归验证 GitHub Release 自动化的版本、安全与双语边界。

English: Regress version, safety, and bilingual boundaries of GitHub Release automation.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import shutil
import unittest
from unittest import mock
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

    def test_release_commit_must_belong_to_origin_master(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-b", "master"], cwd=root, check=True,
                           capture_output=True, text=True, encoding="utf-8")
            subprocess.run(["git", "config", "user.name", "Release Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "release@example.invalid"], cwd=root, check=True)
            marker = root / "marker.txt"
            marker.write_text("master\n", encoding="utf-8")
            subprocess.run(["git", "add", "marker.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "master"], cwd=root, check=True,
                           capture_output=True, text=True, encoding="utf-8")
            master = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                                    capture_output=True, text=True, encoding="utf-8").stdout.strip()
            subprocess.run(["git", "update-ref", "refs/remotes/origin/master", master], cwd=root, check=True)
            self.assertEqual(master, release_workflow.verify_commit_on_master(root)["commit"])

            subprocess.run(["git", "switch", "-c", "feature"], cwd=root, check=True,
                           capture_output=True, text=True, encoding="utf-8")
            marker.write_text("feature\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-am", "feature"], cwd=root, check=True,
                           capture_output=True, text=True, encoding="utf-8")
            with self.assertRaises(release_workflow.ReleaseWorkflowError):
                release_workflow.verify_commit_on_master(root)

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
        metadata = release_workflow.release_metadata(ROOT, "v7.17.3")
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

    def _candidate(self, base):
        root, directory = base / "source", base / "release"
        root.mkdir()
        directory.mkdir()
        self._fixture(root)
        meta = release_workflow.release_metadata(root)
        for suffix, locale in (("zh", "zh-CN"), ("en", "en")):
            self._build_fixture(directory, meta, suffix, locale, locale.encode())
        (directory / meta["provenance"]).write_bytes(b'{"bundle":"new"}')
        release_workflow.write_release_notes(directory / meta["release_notes"], root)
        release_workflow.write_checksums(directory, directory / meta["checksums"], root)
        return root, directory, meta

    def _build_fixture(self, directory, meta, suffix, locale, raw):
        (directory / meta["archive_" + suffix]).write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        witness = dict(ok=True, reproducible=True, version=meta["version"], locale=locale,
                       artifact_sha256=digest, first_sha256=digest, second_sha256=digest, artifact_size=len(raw))
        (directory / meta["witness_" + suffix]).write_text(json.dumps(witness), encoding="utf-8")

    def test_downloaded_candidate_is_exact_and_bound_to_tagged_notes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, directory, meta = self._candidate(Path(temporary))
            self.assertTrue(release_workflow.verify_candidate(directory, root)["ok"])
            (directory / meta["release_notes"]).write_bytes(b"previous-release-notes\n")
            with self.assertRaisesRegex(release_workflow.ReleaseWorkflowError, "release notes"):
                release_workflow.verify_candidate(directory, root)
            release_workflow.write_release_notes(directory / meta["release_notes"], root)
            (directory / meta["archive_en"]).write_bytes(b"changed")
            with self.assertRaisesRegex(release_workflow.ReleaseWorkflowError, "checksum mismatch"):
                release_workflow.verify_candidate(directory, root)
            (directory / "unexpected.txt").touch()
            with self.assertRaisesRegex(release_workflow.ReleaseWorkflowError, "file set mismatch"):
                release_workflow.verify_candidate(directory, root)

    def test_platform_gate_checks_actual_archives_and_both_witnesses(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, windows, meta = self._candidate(base)
            linux = base / "linux"
            shutil.copytree(windows, linux)
            self.assertEqual(set(release_workflow.compare_platforms(windows, linux, root)), {"zh-CN", "en"})
            self._build_fixture(linux, meta, "en", "en", b"different bytes but locally reproducible")
            with self.assertRaisesRegex(release_workflow.ReleaseWorkflowError, "cross-platform digest mismatch: en"):
                release_workflow.compare_platforms(windows, linux, root)
            shutil.copyfile(windows / meta["archive_en"], linux / meta["archive_en"])
            with self.assertRaisesRegex(release_workflow.ReleaseWorkflowError, "witness"):
                release_workflow.compare_platforms(windows, linux, root)
            (linux / meta["witness_en"]).unlink()
            with self.assertRaisesRegex(release_workflow.ReleaseWorkflowError, "missing or unsafe build witness"):
                release_workflow.compare_platforms(windows, linux, root)

    def test_remote_preflight_reconciliation_and_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, directory, meta = self._candidate(Path(tmp))
            head, annotated = "a" * 40, "b" * 40
            tag, repo = meta["tag"], "example/project"
            assets = [{"id": i, "name": name, "state": "uploaded", "size": (directory/name).stat().st_size,
                       "digest": "sha256:" + release_workflow._sha256(directory/name)}
                      for i, name in enumerate(sorted(release_workflow._release_assets(meta)), 1)]
            inventory = {"ref": None, "release": None}
            current_assets = list(assets)
            remote_bytes = {p.name: p.read_bytes() for p in directory.iterdir()}
            signatures = []
            def command(argv, _root):
                if argv[:3] == ["gh", "api", "graphql"]:
                    self.assertIn("tagCommit { oid }", argv[argv.index("-f") + 1])
                    self.assertNotIn("targetCommitish", argv[argv.index("-f") + 1])
                    return json.dumps({"data": {"repository": inventory}})
                if argv[:3] == ["git", "rev-parse", "--verify"]:
                    if argv[-1] in ("HEAD^{commit}", annotated + "^{commit}"):
                        return head
                    return argv[-1].removesuffix("^{commit}")
                if argv[:2] == ["gh", "api"]:
                    self.assertIn(f"repos/{repo}/releases/123/assets?per_page=100", argv)
                    return json.dumps([current_assets[:3], current_assets[3:]])
                if argv[:3] == ["gh", "release", "download"]:
                    name = argv[argv.index("--pattern") + 1]
                    (Path(argv[argv.index("--dir") + 1]) / name).write_bytes(remote_bytes[name])
                    return ""
                if argv[:3] == ["gh", "attestation", "verify"]:
                    self.assertEqual(argv[argv.index("--source-digest") + 1], head)
                    self.assertEqual(argv[argv.index("--source-ref") + 1], "refs/tags/" + tag)
                    self.assertEqual(argv[argv.index("--signer-workflow") + 1], repo + "/.github/workflows/release.yml")
                    bundle = Path(argv[argv.index("--bundle") + 1])
                    if bundle.read_bytes() != b'{"bundle":"original"}':
                        raise release_workflow.ReleaseWorkflowError("invalid original signature")
                    signatures.append(argv[3])
                    return ""
                self.fail(argv)

            def inspect(tag_input=tag, **kwargs):
                return release_workflow.inspect_release(repo, tag_input, root=root, **kwargs)

            error = release_workflow.ReleaseWorkflowError
            with mock.patch.object(release_workflow, "_command", side_effect=command):
                self.assertEqual(inspect("")["status"], "absent")
                with self.assertRaisesRegex(error, "missing remote tag"):
                    inspect()
                inventory["ref"] = {"target": {"oid": annotated}}
                self.assertEqual(inspect()["status"], "absent")
                with self.assertRaisesRegex(error, "missing after draft"):
                    inspect(directory=directory, require_existing=True)
                inventory["release"] = {"tagName": tag, "databaseId": 123, "tagCommit": {"oid": head}}
                preflight = inspect()
                self.assertEqual(preflight["status"], "occupied")
                self.assertEqual(inspect(directory=directory, expected_id=123)["status"], "verified")
                inventory["release"]["tagCommit"] = {"oid": "c" * 40}
                with self.assertRaisesRegex(error, "different target commit"):
                    inspect()
                inventory["release"]["tagCommit"] = None
                self.assertEqual(inspect()["source_commit"], head)
                with self.assertRaisesRegex(error, "changed identity"):
                    inspect(expected_id=124)
                inventory["ref"]["target"]["oid"] = "c" * 40
                with self.assertRaisesRegex(error, "version occupied"):
                    inspect("")
                inventory["ref"]["target"]["oid"] = annotated
                current_assets.pop()
                with self.assertRaisesRegex(error, "missing="):
                    inspect()
                current_assets[:] = assets + [dict(assets[0], name="unexpected.zip")]
                with self.assertRaisesRegex(error, "extra="):
                    inspect(directory=directory)
                current_assets[:] = assets + [assets[0]]
                with self.assertRaisesRegex(error, "duplicate"):
                    inspect()
                current_assets[:] = [dict(a) for a in assets]
                current_assets[0]["state"] = "starter"
                with self.assertRaisesRegex(error, "incomplete"):
                    inspect()
                current_assets[0]["state"] = "uploaded"
                current_assets[0]["digest"] = "sha256:" + "0" * 64
                with self.assertRaisesRegex(error, "digest conflict"):
                    inspect(directory=directory)
                current_assets[0]["digest"] = None
                self.assertEqual(inspect(directory=directory)["status"], "verified")
                stable = release_workflow._remote_state
                snapshots = []
                def replaced(*args):
                    result = stable(*args)
                    snapshots.append(result)
                    if len(snapshots) == 1:
                        current_assets[0]["id"] += 100
                    return result
                with mock.patch.object(release_workflow, "_remote_state", side_effect=replaced):
                    with self.assertRaisesRegex(error, "changed during verification"):
                        inspect(directory=directory)
                self.assertEqual(len(snapshots), 2)
                with self.assertRaisesRegex(error, "changed since preflight"):
                    inspect(directory=directory, expected_id=123, expected_inventory=preflight["inventory_sha256"])
                remote_bytes[meta["provenance"]] = b'{"bundle":"original"}'
                expected = {a["name"]: hashlib.sha256(remote_bytes[a["name"]]).hexdigest() for a in assets
                            if a["name"] != meta["checksums"]}
                remote_bytes[meta["checksums"]] = release_workflow.checksum_bytes(expected)
                for a in current_assets:
                    data = remote_bytes[a["name"]]
                    a.update(digest="sha256:" + hashlib.sha256(data).hexdigest(), size=len(data))
                with self.assertRaisesRegex(error, "digest conflict"):
                    inspect(directory=directory)
                self.assertEqual(inspect(directory=directory, reuse_provenance=True)["status"], "verified")
                self.assertEqual(len(signatures), 2)
                remote_bytes[meta["provenance"]] = b"wrong signature"
                with self.assertRaisesRegex(error, "invalid original signature"):
                    inspect(directory=directory, reuse_provenance=True)
            with mock.patch.object(release_workflow, "_command", side_effect=error("GitHub unavailable")):
                with self.assertRaisesRegex(error, "GitHub unavailable"):
                    inspect()
            with mock.patch.object(release_workflow, "_command", return_value='{"data":{"repository":null}}'):
                with self.assertRaisesRegex(error, "repository"):
                    inspect()

    def test_job_condition_matrix_for_branch_tag_failure_and_cancellation(self):
        def boolean_value(node):
            if isinstance(node, ast.Constant) and type(node.value) is bool:
                return node.value
            if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
                values = [boolean_value(item) for item in node.values]
                return all(values) if isinstance(node.op, ast.And) else any(values)
            self.fail(f"Unsupported release guard: {ast.dump(node)}")

        def run_graph(path, ref_type, *, failure=None, cancelled=False):
            jobs = (ROOT / path).read_text(encoding="utf-8").split("\njobs:\n", 1)[1]
            states = {}
            for name, block in re.findall(r"^  ([\w-]+):\n((?:(?:    [^\n]*|)\n)+)", jobs + "\n", re.M):
                dependency = re.search(r"^    needs: (.+)$", block, re.M)
                needs = re.findall(r"[\w-]+", dependency[1]) if dependency else []
                guard = re.search(r"^    if: (.+)$", block, re.M)
                condition = guard[1].strip('"') if guard else "True"
                if condition == ">-":
                    condition = " ".join(re.match(r"(?:      [^\n]+\n)+", block[guard.end()+1:])[0].split())
                context = {"github.ref_type": ref_type, **{f"needs.{n}.result": states[n] for n in needs}}
                has_status_check = "cancelled()" in condition
                condition = re.sub(r"(github\.ref_type|needs\.[\w-]+\.result) (==|!=) '([\w-]+)'",
                                   lambda m: str((context[m[1]] == m[3]) == (m[2] == "==")), condition)
                condition = condition.replace("!cancelled()", str(not cancelled)).replace("&&", " and ").replace("||", " or ")
                enabled = boolean_value(ast.parse(condition, mode="eval").body)
                if not has_status_check:
                    enabled = enabled and not cancelled and all(states[n] == "success" for n in needs)
                states[name] = ("failure" if name == failure else "success") if enabled else "skipped"
            return states

        for path in (".github/workflows/release.yml", "locales/en/.github/workflows/release.yml"):
            with self.subTest(path=path):
                branch = run_graph(path, "branch")
                self.assertEqual(branch, {"preflight":"success", "tag-inventory":"skipped", "validate":"success",
                                          "platform-build":"success", "build":"success", "draft-release":"skipped"})
                self.assertTrue(all(s == "success" for s in run_graph(path, "tag").values()))
                for failed in ("preflight", "tag-inventory", "validate", "platform-build", "build"):
                    states = run_graph(path, "tag", failure=failed)
                    self.assertEqual(states[failed], "failure")
                    self.assertTrue(all(s == "skipped" for s in list(states.values())[list(states).index(failed)+1:]))
                self.assertTrue(all(s == "skipped" for s in run_graph(path, "tag", cancelled=True).values()))

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
        self.assertNotIn("gh release view", workflow)
        self.assertIn("--require-existing", workflow)
        self.assertIn('--expected-inventory "$EXPECTED_INVENTORY"', workflow)
        self.assertIn("--reuse-provenance", workflow)
        self.assertIn("steps.current.outputs.status == 'absent'", workflow)
        self.assertIn("matrix.os", workflow)
        self.assertLess(workflow.index("compare-platforms --directory"), workflow.index("uses: actions/attest@"))
        self.assertIn("if: github.ref_type == 'tag'", workflow)
        self.assertIn("verify-candidate --directory candidate", workflow)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("verify-master --commit", workflow)
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
            self.assertNotRegex(localized_workflow, r'run:.*\$\{\{[^\n]*github\.ref_name')
            self.assertIn('metadata --tag "$RELEASE_TAG"', localized_workflow)
            self.assertIn('platform-ubuntu-latest-', localized_workflow)
            self.assertIn('platform-windows-latest-', localized_workflow)

    def test_generated_release_body_contains_both_languages_without_relative_selector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "notes.md"
            release_workflow.write_release_notes(output)
            value = output.read_text(encoding="utf-8")
        self.assertIn("# V7.17.3 发行说明", value)
        self.assertIn("# V7.17.3 Release Notes", value)
        self.assertNotIn("English: [RELEASE_NOTES.en.md]", value)
        self.assertNotIn("Chinese: [RELEASE_NOTES.md]", value)


if __name__ == "__main__":
    unittest.main()
