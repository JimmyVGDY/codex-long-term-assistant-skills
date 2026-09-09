"""中文：准备、采用过期候选、更新与回执失效的真实索引集成验证。

English: Real index integration for preparation, stale adoption, maintenance, and receipt invalidation.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
from cp_runtime import capability_gate_workflow as workflow_module
from cp_runtime.atomic_io import native_path
from cp_runtime.capability_gate import GatePolicy, GateTask
from cp_runtime.capability_gate_workflow import GateWorkflow
from cp_runtime.capability_index import scan
from cp_runtime.capability_store import CapabilityError


class CapabilityGateWorkflowTests(unittest.TestCase):
    setUp = fixtures.CapabilityStoreTests.setUp

    def tearDown(self):
        # 中文：只清理本测试创建的临时根；长路径回执不能让标准短路径清理漏文件。
        # English: Clean only this fixture's temporary root, including native long receipt paths.
        self.assertEqual(self.base.resolve(), Path(self.temp.name).resolve())
        self.assertEqual(self.base.parent.resolve(), Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.base.name.startswith("capability-store-"))
        self.temp.name = str(native_path(self.base))
        self.temp.cleanup()

    def workflow(self):
        policy = GatePolicy(self.store, self.base / "gate-config")
        policy.set_enabled(True, None)
        workflow = GateWorkflow(GateTask(policy, "session", "turn"))
        workflow.begin()
        return workflow

    def choices(self, prepared, choice="extend"):
        return [{"id": candidate["id"], "choice": choice, "reason": "Checked source and fixture callers"}
                for candidate in prepared["required_decisions"]]

    def edit(self):
        (self.repo / "app.py").write_text("def public():\n    return 2\n", encoding="utf-8")

    def test_cold_prepare_scans_before_change_and_finish_updates_current_source(self):
        flow = self.workflow()
        self.assertFalse(self.store.current.exists())
        prepared = flow.prepare(["app.py"], "public")
        before = self.store.read()["entries"][0]["file_sha256"]
        self.edit()
        finished = flow.finish(self.choices(prepared))
        self.assertEqual("PASS", finished["state"]["phase"])
        self.assertTrue(flow.check()["valid"])
        after = self.store.read()["entries"][0]["file_sha256"]
        self.assertNotEqual(before, after)
        self.assertEqual(hashlib.sha256((self.repo / "app.py").read_bytes()).hexdigest(), after)
        self.assertFalse(finished["semantic_reuse_approved"])

    def test_repeated_unchanged_prepare_and_begin_reuse_original_receipts(self):
        flow = self.workflow()
        first = flow.prepare(["app.py"], "public")
        state = flow.task.path.read_bytes()
        receipts = {p.name: native_path(p).read_bytes() for p in flow.receipts.iterdir()}
        self.assertEqual(first["state"], flow.begin())
        again = flow.prepare(["app.py"], "public")
        self.assertEqual(first["state"], again["state"])
        self.assertEqual(state, flow.task.path.read_bytes())
        self.assertEqual(receipts, {p.name: native_path(p).read_bytes() for p in flow.receipts.iterdir()})

    def test_unchanged_but_adopted_stale_source_is_refreshed_unused_source_is_not(self):
        helper = self.repo / "helper.py"
        unused = self.repo / "unused.py"
        helper.write_text("def helper():\n    return 1\n", encoding="utf-8")
        unused.write_text("def unused():\n    return 1\n", encoding="utf-8")
        fixtures.git(self.repo, "add", ".")
        fixtures.git(self.repo, "commit", "-qm", "helpers")
        scan(self.store, ["app.py", "helper.py", "unused.py"])
        helper.write_text("def helper():\n    return 2\n", encoding="utf-8")
        unused.write_text("def unused():\n    return 3\n", encoding="utf-8")
        flow = self.workflow()
        prepared = flow.prepare(["app.py"], "helper")
        self.assertEqual("stale", prepared["query"]["candidates"][0]["freshness"])
        self.edit()
        finished = flow.finish(self.choices(prepared, "reuse"))
        self.assertEqual("PASS", finished["state"]["phase"])
        entries = {e["path"]: e for e in self.store.read()["entries"]}
        self.assertEqual(hashlib.sha256(helper.read_bytes()).hexdigest(), entries["helper.py"]["file_sha256"])
        self.assertEqual("matched", entries["helper.py"]["freshness"])
        self.assertNotEqual(hashlib.sha256(unused.read_bytes()).hexdigest(), entries["unused.py"]["file_sha256"])
        self.assertEqual("recheck", entries["unused.py"]["freshness"])

    def test_missing_and_unknown_candidate_decisions_cannot_finish(self):
        flow = self.workflow()
        prepared = flow.prepare(["app.py"], "public")
        self.edit()
        with self.assertRaisesRegex(CapabilityError, "DECISIONS_MISSING"):
            flow.finish([])
        bad = self.choices(prepared)
        bad[0]["id"] = "invented"
        with self.assertRaisesRegex(CapabilityError, "CANDIDATE_UNKNOWN"):
            flow.finish(bad)
        self.assertEqual("PREPARED", flow.task.read()["phase"])

    def test_modification_before_preparation_or_outside_scope_is_rejected(self):
        flow = self.workflow()
        self.edit()
        with self.assertRaisesRegex(CapabilityError, "MODIFIED_BEFORE_PREPARE"):
            flow.prepare(["app.py"], "public")
        fixtures.git(self.repo, "restore", "app.py")
        prepared = flow.prepare(["app.py"], "public")
        (self.repo / "outside.py").write_text("outside scope", encoding="utf-8")
        with self.assertRaisesRegex(CapabilityError, "OUTSIDE_SCOPE"):
            flow.finish(self.choices(prepared))

    def test_post_finish_source_change_invalidates_receipt(self):
        flow = self.workflow()
        prepared = flow.prepare(["app.py"], "public")
        self.edit()
        flow.finish(self.choices(prepared))
        (self.repo / "app.py").write_text("def public():\n    return 3\n", encoding="utf-8")
        result = flow.check()
        self.assertFalse(result["valid"])
        self.assertEqual("BLOCKED", result["state"]["phase"])

    def test_post_finish_index_change_invalidates_receipt(self):
        flow = self.workflow()
        prepared = flow.prepare(["app.py"], "public")
        finished = flow.finish(self.choices(prepared, "unused"))
        self.assertEqual("NO_CHANGE", finished["state"]["phase"])
        payload = self.store.payload(self.store.read())
        payload["entries"][0]["summary"] = "New factual note"
        self.store.commit(payload, self.store.read()["revision"])
        self.assertFalse(flow.check()["valid"])

    def test_cancel_during_preparation_cannot_commit_prepared_or_pass(self):
        flow = self.workflow()
        original = workflow_module.scan
        def cancelling(*args, **kwargs):
            result = original(*args, **kwargs)
            flow.task.cancel()
            return result
        with patch.object(workflow_module, "scan", cancelling):
            with self.assertRaisesRegex(CapabilityError, "REVISION_CONFLICT"):
                flow.prepare(["app.py"], "public")
        self.assertEqual("CANCELLED", flow.task.read()["phase"])
        self.assertFalse(flow.check()["valid"])

    def test_simple_local_missing_index_does_not_force_index_creation(self):
        flow = self.workflow()
        prepared = flow.prepare(["app.py"], "public", initial_scan_required=False,
                                local_only_reason="Local implementation fix with unchanged public interface")
        self.assertEqual("INDEX_MISSING", prepared["query"]["reason"])
        self.edit()
        finished = flow.finish([])
        self.assertEqual("PASS", finished["state"]["phase"])
        self.assertFalse(self.store.current.exists())
        self.assertTrue(flow.check()["valid"])

    def test_oversized_context_never_produces_preparation_success(self):
        (self.repo / "package-lock.json").write_text("x" * (128 * 1024 + 1), encoding="utf-8")
        fixtures.git(self.repo, "add", ".")
        fixtures.git(self.repo, "commit", "-qm", "large context")
        flow = self.workflow()
        with self.assertRaisesRegex(CapabilityError, "PARTIAL_COVERAGE"):
            flow.prepare(["app.py"], "public")
        self.assertNotEqual("PASS", flow.task.read()["phase"])

    def test_arbitrary_finish_hash_cannot_supply_a_valid_receipt(self):
        flow = self.workflow()
        prepared = flow.prepare(["app.py"], "public")
        flow.task.finish("PASS", "a" * 64, prepared["state"]["revision"])
        self.assertFalse(flow.check()["valid"])
        self.assertEqual("BLOCKED", flow.task.read()["phase"])

    def test_later_query_preserves_earlier_candidate_decisions_and_observations(self):
        (self.repo / "helper.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
        fixtures.git(self.repo, "add", ".")
        fixtures.git(self.repo, "commit", "-qm", "helper")
        scan(self.store, ["app.py", "helper.py"])
        flow = self.workflow()
        first = flow.prepare(["app.py"], "public")
        second = flow.prepare(["app.py"], "helper")
        self.assertEqual(2, len(second["required_decisions"]))
        self.assertTrue({c["id"] for c in first["required_decisions"]}
                        <= {c["id"] for c in second["required_decisions"]})
        self.edit()
        with self.assertRaisesRegex(CapabilityError, "DECISIONS_MISSING"):
            flow.finish(self.choices(first))
        self.assertEqual("PASS", flow.finish(self.choices(second))["state"]["phase"])


if __name__ == "__main__":
    unittest.main()
