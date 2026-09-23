"""中文：卡片来源/配对/发布边界，所有资料为隔离夹具。

English: Card provenance, pairing and publication boundaries in isolated fixtures.
"""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.common import atomic_write_json
from cp_runtime.routing_cards import (approval_binding_note, build_bundle, derived_cards,
    load_publication, publication_scope, revoke_publication, validate_bundle, validate_experiment)
from cp_runtime.routing_contract import RoutingError, ref
import v4_fixtures as fx


class CardTests(unittest.TestCase):
    def test_qualification_is_recomputed_and_synthetic_never_enters_production(self):
        data = fx.experiment()
        bundle = fx.bundle(data)
        self.assertTrue(all(row["qualified"] for row in bundle["qualification"]))
        with self.assertRaisesRegex(RoutingError, "NATIVE"):
            validate_bundle(bundle, data, now=fx.NOW, production=True)
        self.assertEqual(bundle, validate_bundle(bundle, data, now=fx.NOW, production=False))
        changed = copy.deepcopy(bundle)
        changed["qualification"][0]["independent_cases"] += 1
        with self.assertRaisesRegex(RoutingError, "RECOMPUTATION"):
            validate_bundle(changed, data, now=fx.NOW, production=False)

    def test_insufficient_samples_cannot_be_promoted_by_qualified_boolean(self):
        data = fx.experiment(5)
        value = fx.bundle(data)
        self.assertFalse(any(card["qualified"] for card in value["qualification"]))
        value["qualification"][0]["qualified"] = True
        with self.assertRaises(RoutingError):
            validate_bundle(value, data, now=fx.NOW, production=False)

    def test_native_receipt_must_bind_every_sample_dimension(self):
        data = fx.experiment(30, origin="desktop-evaluation")
        load = fx.trace_loader(data)
        self.assertEqual(data, validate_experiment(data, trace_loader=load, require_native=True))
        for field in ("task_ref", "call_ref", "response_ref", "receipt_ref", "profile_id", "host_surface"):
            def changed(reference, field=field):
                value = load(reference)
                value[field] = "foreign"
                return value
            with self.assertRaisesRegex(RoutingError, "BINDING"):
                validate_experiment(data, trace_loader=changed, require_native=True)

    def test_one_host_task_cannot_be_split_into_independent_clusters(self):
        data = fx.experiment(30)
        data["samples"][1]["task_ref"] = data["samples"][0]["task_ref"]
        with self.assertRaisesRegex(RoutingError, "CLUSTER_ALIAS"):
            validate_experiment(data)

    def test_pairing_requires_same_case_repetition_rubric_and_comparison_family(self):
        data = fx.experiment(30)
        data["samples"][-1]["gold_ref"] = ref("different-answer")
        with self.assertRaisesRegex(RoutingError, "PAIRED_CASE"):
            derived_cards(data)
        data = fx.experiment(30)
        data["family_intervals"] = 1
        with self.assertRaisesRegex(RoutingError, "FAMILY_MISMATCH"):
            validate_experiment(data)

    def test_duplicate_samples_and_weak_absolute_gate_reject(self):
        data = fx.experiment(30)
        data["samples"].append(copy.deepcopy(data["samples"][0]))
        with self.assertRaisesRegex(RoutingError, "DUPLICATE"):
            validate_experiment(data)
        data = fx.experiment(30)
        data["minimum_pass_bp"] = 1
        with self.assertRaises(RoutingError):
            validate_experiment(data)

    def test_critical_failure_cannot_be_offset_by_many_clean_passes(self):
        data = fx.experiment()
        row = data["samples"][-1]
        row.update(passed=False, critical_failure=True)
        qualification, _ = derived_cards(data)
        card = next(item for item in qualification if item["profile_id"] == row["profile_id"])
        self.assertFalse(card["qualified"])
        self.assertIn("CRITICAL_OR_BOUNDARY_FAILURE", card["reasons"])

    def test_critical_scope_requires_sentinel_coverage(self):
        data = fx.experiment(30)
        data["scenario"]["risk"] = 3
        for row in data["samples"]:
            row["critical"] = False
            row["case_ref"] = fx.case_reference(row)
        fx.refreeze_protocol(data)
        qualification, _ = derived_cards(data)
        self.assertTrue(all("CRITICAL_SENTINELS_MISSING" in card["reasons"] for card in qualification))

    def test_issuer_and_consumer_are_separate_and_revocation_invalidates_activation(self):
        data = fx.experiment()
        bundle = fx.bundle(data)
        value = {
            "schema_version": "routing-card-publication/1", "publication_id": "publication-one",
            "revision": 1, "identity": fx.IDENTITY, "bundle_ref": ref(bundle),
            "experiment_ref": ref(data), "issuer_task_id": "issuer-task",
            "issuer_baseline": "b" * 64, "approval_ref": ref("synthetic-approval"),
            "scope": publication_scope(bundle, "project-bound-reuse"), "status": "approved",
            "created_at": fx.NOW, "expires_at": fx.EXPIRES,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "publication.json"
            atomic_write_json(path, value, seal=True)
            current = load_publication(path, bundle=bundle, consumer_identity=fx.IDENTITY,
                                       consumer_task_id="different-consumer-task", now=fx.NOW)
            self.assertEqual("issuer-task", current["issuer_task_id"])
            with self.assertRaises(RoutingError):
                load_publication(path, bundle=bundle, consumer_identity={
                    **fx.IDENTITY, "project_id": "foreign-project"}, consumer_task_id="consumer", now=fx.NOW)
            revoke_publication(path, expected_revision=1, reason_ref=ref("withdrawn"))
            with self.assertRaises(RoutingError):
                load_publication(path, bundle=bundle, consumer_identity=fx.IDENTITY,
                                 consumer_task_id="consumer", now=fx.NOW)

    def test_approval_binding_covers_consumption_scope_and_bundle_bytes(self):
        value = fx.bundle(fx.experiment(30))
        self.assertNotEqual(approval_binding_note(value, "issuer-only"),
                            approval_binding_note(value, "project-bound-reuse"))
        changed = copy.deepcopy(value)
        changed["costs"][0]["reserve_units"] += 1
        self.assertNotEqual(approval_binding_note(value, "issuer-only"),
                            approval_binding_note(changed, "issuer-only"))


if __name__ == "__main__":
    unittest.main()
