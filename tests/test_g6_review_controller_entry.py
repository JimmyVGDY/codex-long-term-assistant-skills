"""中文：实际复审脚本默认使用 G6，并区分格式与原生证据。

English: Real review scripts default to G6 and distinguish schema from native evidence.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from cp_runtime import g6_review_controller as controller
from cp_runtime.common import atomic_write_json
from cp_runtime.routing_contract import ref

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "skills/multi-agent-independent-review/scripts"


class G6ReviewControllerEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.env = dict(os.environ, PYTHONUTF8="1")
        for command in [["init", "-q"], ["config", "user.name", "Test"],
                        ["config", "user.email", "test@example.invalid"]]:
            subprocess.run(["git", *command], cwd=self.repo, check=True, capture_output=True)
        (self.repo / "app.py").write_text("value = 1\n", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=self.repo, check=True, capture_output=True)
        (self.repo / "app.py").write_text("value = 2\n", encoding="utf8")
        self.packet, self.review = self.base / "packet", self.base / "review"

    def tool(self, name, *args, ok=True):
        result = subprocess.run([sys.executable, "-B", str(TOOLS / name), *map(str, args)],
                                cwd=self.repo, env=self.env, capture_output=True,
                                text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_default_packet_and_controller_need_no_legacy_scorecard(self):
        self.tool("review_packet.py", "create", "--repo-path", self.repo,
                  "--output-dir", self.packet, "--boundary-id", "scope")
        manifest = json.loads((self.packet / "manifest.json").read_text(encoding="utf8"))
        self.assertEqual(manifest["default_model_profile"], "g6-sol-medium")
        self.tool("review_controller.py", "init", "--review-dir", self.review,
                  "--repo-path", self.repo, "--boundary-id", "scope")
        self.tool("review_controller.py", "plan", "--review-dir", self.review,
                  "--phase", "post", "--packet-dir", self.packet)
        template = self.base / "report.json"
        self.tool("review_packet.py", "result-template", "--packet-dir", self.packet,
                  "--reviewer", "cp_review_functional_business", "--output", template)
        result = self.tool("review_packet.py", "validate-result", "--packet-dir", self.packet,
                           "--result-file", template)
        self.assertIn("SCHEMA_ONLY", result.stdout)
        self.tool("review_controller.py", "result", "--review-dir", self.review,
                  "--phase", "post", "--round", 1, "--reviewer", "cp_review_functional_business",
                  "--status", "incomplete", "--summary", "Limited material", "--result-file", template)
        state = json.loads((self.review / "review-state.json").read_text(encoding="utf8"))
        self.assertEqual(state["verification_state"], "UNVERIFIED")

    def test_malformed_result_does_not_corrupt_review_state(self):
        self.tool("review_controller.py", "init", "--review-dir", self.review,
                  "--repo-path", self.repo, "--boundary-id", "scope")
        before = (self.review / "review-state.json").read_bytes()
        report = self.base / "invalid.json"
        report.write_text("[]", encoding="utf8")
        self.tool("review_controller.py", "result", "--review-dir", self.review,
                  "--phase", "post", "--round", 1, "--reviewer", "cp_review_functional_business",
                  "--status", "incomplete", "--summary", "Malformed", "--result-file", report, ok=False)
        self.assertEqual((self.review / "review-state.json").read_bytes(), before)

    def test_merge_requires_every_planned_reviewer_and_current_assignment(self):
        reviewers = ["cp_review_security_access", "cp_review_data_contract"]
        self.tool("review_controller.py", "init", "--review-dir", self.review,
                  "--repo-path", self.repo, "--boundary-id", "scope")
        self.tool("review_controller.py", "plan", "--review-dir", self.review,
                  "--phase", "post", "--reviewers", ",".join(reviewers))
        path = self.review / "review-state.json"
        state = json.loads(path.read_text(encoding="utf8"))
        state.pop("integrity")
        assignment = {"phase": "post", "packet_sha256": "UNVERIFIED",
                      "packet_dir": str(self.packet), "decision_ref": ref("first")}
        row = {"verification_state": "NATIVE_REPORT_VERIFIED", "packet_current": True,
               "declared_status": "pass", "finding_refs": [], "assignment_ref": ref(assignment)}
        state["assignments"] = {role: dict(assignment) for role in reviewers}
        state["results"] = {reviewers[0]: dict(row)}
        atomic_write_json(path, state, seal=True)
        args = SimpleNamespace(command="merge", review_dir=str(self.review))
        with mock.patch.object(controller, "_packet_current", return_value=True):
            merged = controller.run(args)
            self.assertEqual(merged["verification_state"], "UNVERIFIED")
            merged["results"][reviewers[1]] = dict(row)
            atomic_write_json(path, merged, seal=True)
            self.assertEqual(controller.run(args)["verification_state"], "NATIVE_REPORTS_CURRENT")
            active = merged["plans"][merged["active_plan_key"]]
            merged["plans"]["focused"] = {**active, "reviewers": [reviewers[0]]}
            merged["active_plan_key"] = "focused"
            merged["results"][reviewers[1]]["declared_status"] = "blocking"
            atomic_write_json(path, merged, seal=True)
            focused = controller.run(args)
            self.assertEqual(focused["verification_state"], "NATIVE_REPORTS_CURRENT")
            self.assertFalse(focused["merge"]["reported_blockers"])
            self.assertIn(reviewers[1], focused["results"])
            merged["assignments"][reviewers[0]]["decision_ref"] = ref("replacement")
            atomic_write_json(path, merged, seal=True)
            self.assertEqual(controller.run(args)["verification_state"], "UNVERIFIED")

    def test_dispatch_uses_reactivated_plan_instead_of_latest_created_plan(self):
        reviewer = "cp_review_security_access"
        self.tool("review_controller.py", "init", "--review-dir", self.review,
                  "--repo-path", self.repo, "--boundary-id", "scope", "--host-session-id", "test-session")
        for packet in ["a" * 64, "b" * 64, "a" * 64]:
            self.tool("review_controller.py", "plan", "--review-dir", self.review,
                      "--phase", "post", "--reviewers", reviewer, "--packet-sha256", packet)
        args = SimpleNamespace(command="dispatch", review_dir=str(self.review), agent_type=reviewer,
                               reviewer=reviewer, phase="post", scope="Inspect changed files.", model_profile="")
        decision = {"decision_ref": ref("dispatch"), "next_action": "spawn_agent"}
        with mock.patch.object(controller, "preview", return_value=decision) as preview:
            value = controller.run(args)
        self.assertEqual(value["assignments"][reviewer]["packet_sha256"], "a" * 64)
        self.assertIn("packet_sha256=" + "a" * 64, preview.call_args.kwargs["message"])

    def test_utf8_boundary_does_not_exclude_untracked_text_snapshot(self):
        source = self.repo / "untracked.py"
        source.write_bytes(b"#" + b"a" * 8190 + "\u4e2d\n".encode("utf8"))
        self.tool("review_packet.py", "create", "--repo-path", self.repo,
                  "--output-dir", self.packet, "--boundary-id", "scope")
        manifest = json.loads((self.packet / "manifest.json").read_text(encoding="utf8"))
        entry = next(item for item in manifest["untracked_files"] if item["path"] == "untracked.py")
        self.assertTrue(entry["snapshot"], entry)
        self.assertEqual((self.packet / entry["snapshot"]).read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
