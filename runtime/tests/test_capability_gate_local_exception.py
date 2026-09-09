"""中文：冷索引例外、范围升级和旧回执失效回归。

English: Regression coverage for cold exceptions, scope upgrades, and legacy receipts.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_gate_workflow as fixtures
from cp_runtime import capability_gate_workflow as workflow_module
from cp_runtime.capability_store import CapabilityError


class CapabilityGateLocalExceptionTests(unittest.TestCase):
    setUp = fixtures.CapabilityGateWorkflowTests.setUp
    tearDown = fixtures.CapabilityGateWorkflowTests.tearDown
    workflow = fixtures.CapabilityGateWorkflowTests.workflow
    choices = fixtures.CapabilityGateWorkflowTests.choices
    edit = fixtures.CapabilityGateWorkflowTests.edit

    def add_helper(self):
        (self.repo / "helper.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
        fixtures.fixtures.git(self.repo, "add", ".")
        fixtures.fixtures.git(self.repo, "commit", "-qm", "helper baseline")

    def test_multifile_local_declaration_scans_originals_and_finishes_with_index(self):
        self.add_helper()
        flow = self.workflow()
        prepared = flow.prepare(["app.py", "helper.py"], "public helper", initial_scan_required=False,
                                local_only_reason="Small renderer and caller change")
        receipt = flow._preparation(prepared["state"])
        self.assertTrue(receipt["initial_scan_required"])
        self.assertTrue(receipt["initial_scan_completed"])
        self.assertEqual({"app.py", "helper.py"}, {e["path"] for e in self.store.read()["entries"]})
        self.edit()
        self.assertEqual("PASS", flow.finish(self.choices(prepared))["state"]["phase"])
        self.assertTrue(flow.check()["valid"])

    def test_unchanged_scope_expansion_scans_entire_accumulated_scope(self):
        self.add_helper()
        flow = self.workflow()
        flow.prepare(["app.py"], "public", initial_scan_required=False, local_only_reason="Local fix")
        self.assertFalse(self.store.current.exists())
        prepared = flow.prepare(["helper.py"], "helper", initial_scan_required=False, local_only_reason="Small expansion")
        self.assertEqual({"app.py", "helper.py"}, set(flow._preparation(prepared["state"])["files"]))
        self.assertEqual({"app.py", "helper.py"}, {e["path"] for e in self.store.read()["entries"]})

    def test_scope_expansion_after_prior_edit_cannot_retroactively_scan(self):
        self.add_helper()
        flow = self.workflow()
        first = flow.prepare(["app.py"], "public", initial_scan_required=False, local_only_reason="Local fix")
        self.edit()
        with self.assertRaisesRegex(CapabilityError, "GATE_MODIFIED_BEFORE_PREPARE"):
            flow.prepare(["helper.py"], "helper", initial_scan_required=False, local_only_reason="Small expansion")
        self.assertEqual(first["state"], flow.task.read())
        self.assertFalse(self.store.current.exists())

    def test_new_file_cannot_claim_single_existing_file_exception(self):
        flow = self.workflow()
        with self.assertRaisesRegex(CapabilityError, "GATE_PARTIAL_COVERAGE"):
            flow.prepare(["new.py"], "new", initial_scan_required=False, local_only_reason="Small new file")
        self.assertFalse(self.store.current.exists())
        self.assertEqual("NEW", flow.task.read()["phase"])

    def test_existing_and_new_file_scan_then_register_new_source_on_finish(self):
        flow = self.workflow()
        prepared = flow.prepare(["app.py", "new.py"], "public", initial_scan_required=False,
                                local_only_reason="Small addition")
        self.assertTrue(flow._preparation(prepared["state"])["initial_scan_completed"])
        (self.repo / "new.py").write_text("def added():\n    return 3\n", encoding="utf-8")
        self.assertEqual("PASS", flow.finish(self.choices(prepared))["state"]["phase"])
        self.assertIn("new.py", {e["path"] for e in self.store.read()["entries"]})

    def test_late_index_cannot_relabel_edited_cold_preparation_as_hot(self):
        self.add_helper()
        flow = self.workflow()
        first = flow.prepare(["app.py"], "public", initial_scan_required=False, local_only_reason="Local fix")
        self.edit()
        workflow_module.scan(self.store, ["app.py", "helper.py"])
        index_before = self.store.current.read_bytes()
        with self.assertRaisesRegex(CapabilityError, "GATE_MODIFIED_BEFORE_PREPARE"):
            flow.prepare(["app.py"], "public", initial_scan_required=False, local_only_reason="Repeat local fix")
        self.assertEqual(first["state"], flow.task.read())
        self.assertEqual(index_before, self.store.current.read_bytes())

    def test_late_index_does_not_validate_legacy_multifile_preparation(self):
        self.add_helper()
        flow = self.workflow()
        self.legacy_multifile_preparation(flow)
        self.edit()
        workflow_module.scan(self.store, ["app.py", "helper.py"])
        with self.assertRaisesRegex(CapabilityError, "GATE_INITIAL_SCAN_REQUIRED"):
            flow.finish([])
        with patch.object(workflow_module, "_cold_local_only", return_value=True):
            flow.finish([])
        checked = flow.check()
        self.assertFalse(checked["valid"])
        self.assertEqual(["INITIAL_SCAN_NOT_PROVEN"], checked["state"]["reason_codes"])

    def legacy_multifile_preparation(self, flow):
        # 中文：仅在构造旧版本回执时替换例外谓词，实际核验使用当前实现。
        # English: Substitute the predicate only while constructing a legacy receipt, not while validating it.
        with patch.object(workflow_module, "_cold_local_only", return_value=True):
            return flow.prepare(["app.py", "helper.py"], "public", initial_scan_required=False,
                                local_only_reason="Legacy multifile exemption")

    def test_legacy_multifile_pass_is_invalidated_with_specific_reason(self):
        self.add_helper()
        flow = self.workflow()
        self.legacy_multifile_preparation(flow)
        self.edit()
        with patch.object(workflow_module, "_cold_local_only", return_value=True):
            self.assertEqual("PASS", flow.finish([])["state"]["phase"])
        checked = flow.check()
        self.assertFalse(checked["valid"])
        self.assertEqual("BLOCKED", checked["state"]["phase"])
        self.assertEqual(["INITIAL_SCAN_NOT_PROVEN"], checked["state"]["reason_codes"])
        self.assertFalse(self.store.current.exists())

    def test_legacy_preparation_cannot_issue_a_new_no_index_pass(self):
        self.add_helper()
        flow = self.workflow()
        self.legacy_multifile_preparation(flow)
        self.edit()
        before = flow.task.read()
        with self.assertRaisesRegex(CapabilityError, "GATE_INITIAL_SCAN_REQUIRED"):
            flow.finish([])
        result = flow.record_failure("GATE_INITIAL_SCAN_REQUIRED", before["revision"])
        self.assertEqual("BLOCKED", result["phase"])
        self.assertEqual(["INITIAL_SCAN_NOT_PROVEN"], result["reason_codes"])


if __name__ == "__main__":
    unittest.main()
