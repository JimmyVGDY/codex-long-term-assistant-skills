"""中文：用真实检查点写入器验证恢复、身份、读取预算和旧格式。

English: Validate recovery, identity, budgets, and legacy records using the real writer.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
ROOT = RUNTIME_ROOT.parent
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from cp_runtime.common import RuntimeContractError, repo_snapshot, seal_record
from cp_runtime.evidence import record_evidence
from cp_runtime.project import onboard_project
from cp_runtime.resume import build_resume_view, render_resume_text
from cp_runtime.resume_snapshot import bounded_repo_snapshot


class ResumeViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="resume-view-")
        self.root = Path(self.temp.name)
        self.repo, self.context = self.root / "repo", self.root / "context"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Resume Test")
        self.git("config", "user.email", "resume@example.invalid")
        (self.repo / "app.py").write_text("print('v1')\n", encoding="utf-8")
        self.git("add", "app.py")
        self.git("commit", "-qm", "initial")
        self.binding = onboard_project(self.repo, "PROJECT-RESUME", "Resume", self.context)
        writer = ROOT / "skills" / "long-running-task-memory" / "scripts" / "checkpoint.py"
        for arguments in (
            ["init", "--project-dir", str(self.context), "--task-id", "TASK-RESUME", "--repo-path", str(self.repo)],
            ["append", "--project-dir", str(self.context), "--task-id", "TASK-RESUME",
             "--node-type", "implementation", "--stage", "IMPLEMENT", "--summary", "完成初始实现",
             "--next-action", "执行定向验证", "--repo-path", str(self.repo)],
        ):
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(writer), *arguments],
                                    capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        progress = (self.context / "PROGRESS.md").read_text(encoding="utf-8")
        self.checkpoint_id = re.search(r"(?m)^### (CP-\d{8}-\d{3,})", progress)[1]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *arguments) -> None:
        subprocess.run(["git", *arguments], cwd=self.repo, check=True, capture_output=True)

    def view(self, **kwargs):
        options = dict(profile_path=self.binding.profile_path, state_path=self.binding.state_path,
                       checkpoint_dir=self.context)
        options.update(kwargs)
        return build_resume_view(self.repo, **options)

    def evidence(self, name="validation.json"):
        path = self.context / name
        record_evidence(path, "EV-RESUME-001", self.binding.profile_path, "TASK-RESUME", self.repo,
                        "validation", "targeted", "valid", "python -m unittest", "passed")
        return path

    def mutate(self, name, old, new):
        path = self.context / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def fingerprints(self):
        return {path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.root.rglob("*") if path.is_file()}

    def test_profile_and_markdown_resume_is_current_and_read_only(self):
        before = self.fingerprints()
        view = self.view()
        self.assertEqual(before, self.fingerprints())
        self.assertEqual("CURRENT", view["overall"])
        self.assertEqual("TASK-RESUME", view["task"]["task_id"])
        self.assertEqual(self.checkpoint_id, view["checkpoint"]["id"])
        self.assertIn("执行定向验证", render_resume_text(view))
        self.assertEqual("NOT_PROVIDED", view["coverage"]["evidence_state"])

    def test_evidence_uses_checkpoint_task_when_state_task_is_empty(self):
        view = self.view(evidence_paths=[self.evidence()])
        self.assertEqual("CURRENT", view["evidence"][0]["freshness"])

    def test_evidence_becomes_stale_after_repo_change(self):
        evidence = self.evidence()
        self.assertEqual("CURRENT", self.view(evidence_paths=[evidence])["evidence"][0]["freshness"])
        (self.repo / "app.py").write_text("print('v2')\n", encoding="utf-8")
        stale = self.view(evidence_paths=[evidence])
        self.assertEqual("STALE", stale["overall"])
        self.assertEqual("STALE", stale["evidence"][0]["freshness"])

    def test_dirty_content_change_is_detected_with_identical_git_status(self):
        (self.repo / "app.py").write_text("print('v2')\n", encoding="utf-8")
        evidence = self.evidence()
        (self.repo / "app.py").write_text("print('v3')\n", encoding="utf-8")
        self.assertEqual("STALE", self.view(evidence_paths=[evidence])["evidence"][0]["freshness"])

    def test_unused_textconv_configuration_preserves_legacy_dirty_digest(self):
        self.git("config", "diff.uxunused.textconv", "must-not-be-invoked")
        (self.repo / "app.py").write_text("print('changed')\n", encoding="utf-8")
        value = bounded_repo_snapshot(self.repo)
        self.assertTrue(value["complete"], value["limitations"])
        self.assertEqual(repo_snapshot(self.repo)["sha256"], value["sha256"])

    def test_applicable_textconv_is_not_executed_or_compared_as_complete(self):
        marker = self.root / "converter-ran"
        converter = self.root / "converter.py"
        converter.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('ran')\n", encoding="utf-8")
        self.git("config", "diff.uxfixture.textconv", '"' + sys.executable.replace('\\', '/') + '" "' + converter.as_posix() + '"')
        (self.repo / ".gitattributes").write_text("app.py diff=uxfixture\n", encoding="utf-8")
        (self.repo / "app.py").write_text("print('changed')\n", encoding="utf-8")
        value = bounded_repo_snapshot(self.repo)
        self.assertFalse(value["complete"])
        self.assertIn("EXTERNAL_DIFF_FILTER_NOT_EVALUATED", value["limitations"])
        self.assertIsNone(value["sha256"])
        self.assertFalse(marker.exists())

    def test_explicit_task_cannot_select_a_different_latest_checkpoint(self):
        self.mutate("PROGRESS.md", "TASK-RESUME / IMPLEMENT", "OTHER-TASK / IMPLEMENT")
        with self.assertRaisesRegex(RuntimeContractError, "CHECKPOINT_TASK_CONFLICT"):
            self.view(task_id="TASK-RESUME")

    def test_current_checkpoint_reference_must_match_progress(self):
        self.mutate("CURRENT_TASK.md", self.checkpoint_id, "CP-20000101-999")
        with self.assertRaisesRegex(RuntimeContractError, "REFERENCE_CONFLICT"):
            self.view()

    def test_checkpoint_state_versions_must_match(self):
        self.mutate("CURRENT_TASK.md", "- 状态版本：1", "- 状态版本：999")
        with self.assertRaisesRegex(RuntimeContractError, "VERSION_CONFLICT"):
            self.view()

    def test_checkpoint_cannot_refer_to_another_repository(self):
        other = self.root / "other"
        other.mkdir()
        self.mutate("CURRENT_TASK.md", str(self.repo.resolve()), str(other.resolve()))
        with self.assertRaisesRegex(RuntimeContractError, "REPOSITORY_CONFLICT"):
            self.view()

    def test_missing_current_markers_fail_closed(self):
        self.mutate("CURRENT_TASK.md", "<!-- live-task-state:end -->", "")
        with self.assertRaisesRegex(RuntimeContractError, "MARKERS_INVALID"):
            self.view()

    def test_explicit_evidence_identity_conflict_is_an_error(self):
        path = self.evidence()
        value = json.loads(path.read_text(encoding="utf-8"))
        value["task_id"] = "OTHER-TASK"
        path.write_text(json.dumps(seal_record({key: item for key, item in value.items()
                                              if key != "integrity"})), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeContractError, "EVIDENCE_TASK_CONFLICT"):
            self.view(evidence_paths=[path])

    def test_evidence_alias_is_rejected_before_resolve(self):
        path = self.evidence()
        alias = self.context / "alias.json"
        try:
            alias.symlink_to(path)
        except OSError:
            self.skipTest("Host cannot create symbolic links")
        with self.assertRaisesRegex(RuntimeContractError, "LINK_REJECTED"):
            self.view(evidence_paths=[alias])

    def test_profile_alias_is_rejected_before_resolve(self):
        alias = self.context / "profile-alias.json"
        try:
            alias.symlink_to(self.binding.profile_path)
        except OSError:
            self.skipTest("Host cannot create symbolic links")
        with self.assertRaisesRegex(RuntimeContractError, "LINK_REJECTED"):
            self.view(profile_path=alias)

    def test_aggregate_text_budget_returns_partial(self):
        template_path = self.evidence()
        value = json.loads(template_path.read_text(encoding="utf-8"))
        value.pop("integrity")
        value["padding"] = "x" * 150000
        content = json.dumps(seal_record(value))
        evidence = []
        for number in range(20):
            path = self.context / ("large-%d.json" % number)
            path.write_text(content, encoding="utf-8")
            evidence.append(path)
        view = self.view(evidence_paths=evidence)
        self.assertEqual("PARTIAL", view["overall"])
        self.assertIn("TEXT_BUDGET_EXCEEDED", view["limitations"])
        self.assertLess(view["coverage"]["evidence_checked"], 20)
        self.assertEqual(20, view["coverage"]["evidence_requested"])
        self.assertLessEqual(view["coverage"]["text_bytes_read"], 2 * 1024 * 1024)

    def test_requested_evidence_count_is_not_truncated(self):
        evidence = self.evidence()
        view = self.view(evidence_paths=[evidence] * 21)
        self.assertEqual((21, 20), (view["coverage"]["evidence_requested"], view["coverage"]["evidence_checked"]))
        self.assertEqual("PARTIAL", view["overall"])

    def test_expired_query_budget_is_partial_not_schema_failure(self):
        with mock.patch("cp_runtime.resume.QUERY_TIMEOUT_SECONDS", 0):
            view = self.view()
        self.assertEqual("PARTIAL", view["overall"])
        self.assertIn("RESUME_TIMEOUT", view["limitations"])

    def test_sampled_untracked_content_never_yields_complete_snapshot(self):
        with (self.repo / "large.bin").open("wb") as stream:
            stream.seek(4 * 1024 * 1024)
            stream.write(b"x")
        view = self.view()
        self.assertFalse(view["repository"]["complete"])
        self.assertIsNone(view["repository"]["current_sha256"])
        self.assertIn("UNTRACKED_SAMPLED_CONTENT", view["limitations"])

    def test_bounded_snapshot_matches_legacy_algorithm_for_complete_data(self):
        (self.repo / "new.txt").write_bytes(b"small untracked contents")
        old = repo_snapshot(self.repo)
        current = bounded_repo_snapshot(self.repo)
        self.assertTrue(current["complete"], current)
        self.assertEqual(old["sha256"], current["sha256"])

    def test_detached_head_still_has_complete_snapshot(self):
        self.git("checkout", "--detach", "-q", "HEAD")
        view = self.view()
        self.assertTrue(view["repository"]["complete"], view)
        self.assertEqual("DETACHED", view["repository"]["branch"])

    def test_markdown_only_keeps_content_freshness_unknown(self):
        before = self.fingerprints()
        view = build_resume_view(self.repo, checkpoint_dir=self.context)
        self.assertEqual(before, self.fingerprints())
        self.assertIsNone(view["project"])
        self.assertEqual("PARTIAL", view["overall"])
        self.assertEqual("UNKNOWN", view["repository"]["status"])

    def test_cli_invalid_json_query_has_structured_error_and_exit_two(self):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(ROOT / "scripts" / "cp-runtime.py"),
             "project-resume", "--repo-path", str(self.repo), "--state", str(self.context / "project-state.json"), "--json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(2, result.returncode)
        value = json.loads(result.stdout)
        self.assertEqual("ERROR", value["overall"])
        self.assertEqual("resume-view/1", value["schema"])
        self.assertIn("STATE_REQUIRES_PROFILE", value["blockers"][0])
