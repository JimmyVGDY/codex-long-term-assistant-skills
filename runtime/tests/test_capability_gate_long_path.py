"""中文：超过Windows传统路径长度的真实外部索引和任务回执必须可恢复。

English: Real external indexes and task receipts beyond legacy Windows path lengths remain recoverable.
"""
import os
from pathlib import Path
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
import test_capability_gate_workflow as workflow_fixtures
from cp_runtime.atomic_io import native_path
from cp_runtime.capability_gate import GatePolicy, GateTask
from cp_runtime.capability_gate_workflow import GateWorkflow
from cp_runtime.capability_store import CapabilityStore


@unittest.skipUnless(os.name == "nt", "Windows native path regression")
class CapabilityGateLongPathTests(unittest.TestCase):
    def setUp(self):
        fixtures.CapabilityStoreTests.setUp(self)
        deep = self.base / ("external-context-" + "x" * 55) / ("project-" + "y" * 22)
        self.assertLess(len(str(deep / "project-profile.json")), 250)
        deep.mkdir(parents=True)
        for name in ("project-profile.json", "project-state.json"):
            shutil.copyfile(self.profile.with_name(name), deep / name)
        self.profile = deep / "project-profile.json"
        self.store = CapabilityStore(self.profile, self.repo)
        self.policy = GatePolicy(self.store, self.base / "gate-config")
        self.policy.set_enabled(True, None)
        self.task = GateTask(self.policy, "long-session", "long-turn")
        self.assertGreater(len(str(self.task.path)), 300)
        self.flow = GateWorkflow(self.task)

    tearDown = workflow_fixtures.CapabilityGateWorkflowTests.tearDown
    choices = workflow_fixtures.CapabilityGateWorkflowTests.choices

    def test_network_path_conversion_preserves_share_and_is_idempotent(self):
        share = Path(r"\\server\share\external-index\state.json")
        converted = native_path(share)
        self.assertEqual(r"\\?\UNC\server\share\external-index\state.json", str(converted))
        self.assertEqual(converted, native_path(converted))

    def test_deep_origin_scan_finish_reopen_and_cancel_preserve_state(self):
        self.flow.begin()
        prepared = self.flow.prepare(["app.py"], "public")
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")
        self.assertEqual("PASS", self.flow.finish(self.choices(prepared))["state"]["phase"])
        reopened = GateWorkflow(GateTask(GatePolicy(CapabilityStore(self.profile, self.repo), self.policy.root),
                                        "long-session", "long-turn"))
        self.assertTrue(reopened.check()["valid"])
        self.assertTrue(native_path(self.store.current).is_file())
        self.assertEqual("CANCELLED", reopened.task.cancel()["phase"])
        self.assertFalse(reopened.check()["valid"])

    def test_deep_readonly_receipt_is_no_change_and_replay_is_idempotent(self):
        baseline = self.flow.begin()
        self.assertEqual(baseline, self.flow.begin())
        self.assertEqual("NO_CHANGE", self.flow.no_change()["phase"])
        self.assertTrue(self.flow.check()["valid"])
        self.assertFalse(native_path(self.store.current).exists())


if __name__ == "__main__":
    unittest.main()
