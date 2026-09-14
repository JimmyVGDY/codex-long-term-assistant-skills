from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from cp_runtime.evidence import record_evidence
from cp_runtime.common import seal_record
from cp_runtime.project import onboard_project
from cp_runtime.resume import build_resume_view, render_resume_text


class ResumeViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="resume-view-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.context = self.root / "context"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Resume Test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "resume@example.invalid"], cwd=self.repo, check=True)
        (self.repo / "app.py").write_text("print('v1')\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=self.repo, check=True)
        self.binding = onboard_project(self.repo, "PROJECT-RESUME", "Resume", self.context)
        (self.context / "CURRENT_TASK.md").write_text(
            "# 当前任务\n\n- 任务标识：TASK-RESUME\n- 当前阶段：IMPLEMENT\n- 当前状态：进行中\n",
            encoding="utf-8",
        )
        (self.context / "PROGRESS.md").write_text(
            "# 进度\n\n### CP-20260914-001\n\n"
            "- 所属任务 / 阶段：TASK-RESUME / IMPLEMENT\n"
            "- 节点状态：已完成\n"
            "- 工作区指纹：old-md-fingerprint\n\n"
            "#### 实际完成\n\n- 完成初始实现\n\n"
            "#### 下一步唯一行动\n\n- 执行定向验证\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_profile_and_markdown_resume_is_current_and_read_only(self) -> None:
        before = sorted(path.relative_to(self.context).as_posix() for path in self.context.rglob("*"))
        view = build_resume_view(self.repo, self.binding.profile_path, self.binding.state_path,
                                 checkpoint_dir=self.context)
        after = sorted(path.relative_to(self.context).as_posix() for path in self.context.rglob("*"))
        self.assertEqual(before, after)
        self.assertEqual("CURRENT", view["overall"])
        self.assertEqual("TASK-RESUME", view["task"]["task_id"])
        self.assertEqual("CP-20260914-001", view["checkpoint"]["id"])
        self.assertIn("执行定向验证", render_resume_text(view))

    def test_evidence_is_checked_once_and_becomes_stale_after_repo_change(self) -> None:
        evidence = self.context / "validation.json"
        record_evidence(
            evidence, "EV-RESUME-001", self.binding.profile_path, "TASK-RESUME", self.repo,
            "validation", "targeted", "valid", "python -m unittest", "passed",
        )
        current = build_resume_view(self.repo, self.binding.profile_path, self.binding.state_path,
                                    task_id="TASK-RESUME", checkpoint_dir=self.context,
                                    evidence_paths=[evidence])
        self.assertEqual("CURRENT", current["evidence"][0]["freshness"])
        (self.repo / "app.py").write_text("print('v2')\n", encoding="utf-8")
        stale = build_resume_view(self.repo, self.binding.profile_path, self.binding.state_path,
                                  task_id="TASK-RESUME", checkpoint_dir=self.context,
                                  evidence_paths=[evidence])
        self.assertEqual("STALE", stale["overall"])
        self.assertEqual("STALE", stale["evidence"][0]["freshness"])
        self.assertTrue(any(item.startswith("仓库基线已变化") for item in stale["blockers"]))

    def test_explicit_task_id_selects_matching_recent_checkpoint(self) -> None:
        (self.context / "CURRENT_TASK.md").write_text("# 当前任务\n", encoding="utf-8")
        (self.context / "PROGRESS.md").write_text(
            "### CP-A\n\n- 所属任务 / 阶段：TASK-A / IMPLEMENT\n- 节点状态：已完成\n\n"
            "#### 实际完成\n\n- A 完成\n\n#### 下一步唯一行动\n\n- A 下一步\n\n"
            "### CP-B\n\n- 所属任务 / 阶段：TASK-B / IMPLEMENT\n- 节点状态：已完成\n\n"
            "#### 实际完成\n\n- B 完成\n\n#### 下一步唯一行动\n\n- B 下一步\n",
            encoding="utf-8",
        )
        view = build_resume_view(self.repo, task_id="TASK-A", checkpoint_dir=self.context)
        self.assertEqual("TASK-A", view["task"]["task_id"])
        self.assertEqual("CP-A", view["checkpoint"]["id"])

    def test_evidence_identity_mismatch_is_not_current(self) -> None:
        evidence = self.context / "mismatch.json"
        record_evidence(
            evidence, "EV-RESUME-002", self.binding.profile_path, "TASK-RESUME", self.repo,
            "validation", "targeted", "valid", "python -m unittest", "passed",
        )
        value = json.loads(evidence.read_text(encoding="utf-8"))
        value["task_id"] = "OTHER-TASK"
        evidence.write_text(json.dumps(seal_record({key: item for key, item in value.items()
                                                     if key != "integrity"}), ensure_ascii=False), encoding="utf-8")
        view = build_resume_view(self.repo, self.binding.profile_path, self.binding.state_path,
                                 task_id="TASK-RESUME", checkpoint_dir=self.context,
                                 evidence_paths=[evidence])
        self.assertEqual("INVALID", view["evidence"][0]["freshness"])
        self.assertTrue(view["blockers"])
        self.assertNotEqual("CURRENT", view["overall"])

    def test_detached_head_still_has_complete_snapshot(self) -> None:
        subprocess.run(["git", "checkout", "--detach", "-q", "HEAD"], cwd=self.repo, check=True)
        view = build_resume_view(self.repo, self.binding.profile_path, self.binding.state_path,
                                 checkpoint_dir=self.context)
        self.assertTrue(view["repository"]["complete"])
        self.assertEqual("DETACHED", view["repository"]["branch"])

    def test_markdown_only_mode_does_not_create_profile_or_state(self) -> None:
        view = build_resume_view(self.repo, checkpoint_dir=self.context)
        self.assertIsNone(view["project"])
        self.assertEqual("PARTIAL", view["overall"])
        self.assertEqual("UNKNOWN", view["repository"]["status"])

    def test_cli_invalid_state_without_profile_returns_contract_error(self) -> None:
        entry = Path(__file__).resolve().parents[2] / "scripts" / "cp-runtime.py"
        result = subprocess.run(
            [sys.executable, str(entry), "project-resume", "--repo-path", str(self.repo),
             "--state", str(self.context / "project-state.json")],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("STATE_REQUIRES_PROFILE", result.stderr)
