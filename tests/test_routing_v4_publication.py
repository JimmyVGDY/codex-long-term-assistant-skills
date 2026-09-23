"""中文：发行批准的一次消费与中断；宿主来源仅为合成夹具。

English: One-use publication approval and crash recovery with synthetic traces.
"""
from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import test_routing_v4_context as fixtures
import v4_fixtures as fx
from cp_runtime.approval import issue_approval, load_approval
from cp_runtime.common import RuntimeContractError, repo_snapshot
from cp_runtime.routing_contract import RoutingError
from cp_runtime.routing_cards import approval_binding_note, build_bundle, protocol_reference, publish_bundle, validate_bundle


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ContextTests(methodName="runTest")
        self.fixture.setUp()
        self.data = fx.experiment(2, origin="desktop-evaluation")
        self.data["identity"] = self.fixture.evaluation["identity"]
        self.data["issuer"]["baseline_sha256"] = repo_snapshot(self.fixture.repo)["sha256"]
        self.data["protocol_ref"] = protocol_reference(self.data)
        self.bundle = fx.bundle(self.data)
        self.approval = self.fixture.root / "approval.json"
        issue_approval(self.approval, "synthetic-card-publication", self.fixture.project.profile_path,
            self.data["issuer"]["task_id"], ["make-effective"], "local", self.fixture.repo, fx.EXPIRES,
            approved_by="synthetic-test-fixture", note=approval_binding_note(self.bundle, "project-bound-reuse"))

    def tearDown(self):
        self.fixture.tearDown()

    def publish(self, name):
        return publish_bundle(self.fixture.root / (name + ".json"), self.bundle, self.data,
            approval_path=self.approval, repo_path=self.fixture.repo, trace_loader=fx.trace_loader(self.data),
            publication_id=name, consumption="project-bound-reuse", now=fx.NOW)

    def test_two_outputs_cannot_consume_one_approval_twice(self):
        def run(name):
            try:
                return self.publish(name)["status"]
            except (RoutingError, RuntimeContractError):
                return "rejected"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(run, ["publication-one", "publication-two"]))
        self.assertCountEqual(["approved", "rejected"], outcomes)
        self.assertEqual("consumed", load_approval(self.approval)["status"])

    def test_interruption_after_consumption_does_not_restore_approval(self):
        with patch("cp_runtime.routing_cards.atomic_write_json", side_effect=OSError("synthetic interruption")):
            with self.assertRaises(OSError):
                self.publish("publication-one")
        self.assertFalse((self.fixture.root / "publication-one.json").exists())
        self.assertEqual("consumed", load_approval(self.approval)["status"])
        with self.assertRaisesRegex(RoutingError, "APPROVAL_INVALID"):
            self.publish("publication-one")

    def test_measured_label_without_attributable_billing_receipt_is_not_accepted(self):
        costs = fx.costs(self.data)
        for cost in costs:
            cost["measurement"] = "measured_codex_credits"
        bundle = build_bundle(self.data, costs, bundle_id="cost-source-missing",
                              created_at=fx.NOW, expires_at=fx.EXPIRES)
        with self.assertRaisesRegex(RoutingError, "MEASURED_COST_EVIDENCE_UNAVAILABLE"):
            validate_bundle(bundle, self.data, now=fx.NOW, trace_loader=fx.trace_loader(self.data))


if __name__ == "__main__":
    unittest.main()
