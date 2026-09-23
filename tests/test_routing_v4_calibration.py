"""中文：合成账本下的历史观察读回；不构成模型质量证据。

English: Historical-source verification with synthetic model observations.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import test_routing_v4_budget as budget_fixtures
from cp_runtime import budget_v4, calibration_v4 as calibration, review_v4
from cp_runtime.common import atomic_write_json, repo_snapshot
from cp_runtime.routing_contract import RoutingError, ref


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = budget_fixtures.BudgetFixture(self.root)
        self.fixture.init()
        repo = self.fixture.repo
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
        (repo / "README.md").write_text("Synthetic calibration fixture", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture", "-c",
                        "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                        "commit", "-qm", "fixture"], check=True, capture_output=True)
        directory = self.root / "review"
        review_v4.initialize(directory, ledger_path=self.fixture.path, boundary_id="synthetic-review")
        selected = review_v4.prepare(directory, self.fixture.request, dispatch_key="sample-one", depth=1,
                                      snapshot_loader=self.fixture.load)
        attempt = self.fixture.complete(selected)
        value = review_v4.result_template(directory, selected["permit_id"])
        value.update(status="pass", summary="Synthetic result", checked_scope=["Synthetic scenario"])
        self.result_path = self.root / "result.json"
        self.result_path.write_text(json.dumps(value), encoding="utf-8")
        result_ref = "sha256:" + hashlib.sha256(self.result_path.read_bytes()).hexdigest()
        budget_v4.accept_result(self.fixture.path, reservation_id=attempt["reservation_id"],
                                 result_ref=result_ref, status="pass", response_ref=ref("synthetic-response"),
                                 baseline_sha256=value["baseline_sha256"])
        self.sample = calibration.pending_sample(self.fixture.path, attempt["reservation_id"],
                         self.result_path, {name: 0 for name in calibration.METRICS})
        evidence_path = self.root / "evidence.json"
        self.evidence = {
            "schema_version": 1, "evidence_id": "synthetic-observation", "status": "valid", "kind": "review",
            "project_id": self.sample["identity"]["project_id"], "task_id": self.sample["identity"]["task_id"],
            "source": "parent-finalized-v4-review", "baseline": repo_snapshot(repo),
            "scope_refs": ["result:" + result_ref, "reservation:" + ref(attempt["reservation_id"]),
                           "metrics:" + ref(self.sample["metrics"]), "scenario:" + self.sample["scenario_ref"]],
        }
        atomic_write_json(evidence_path, self.evidence, seal=True)
        evidence_ref = "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        self.source = {"ledger_path": self.fixture.path, "result_path": self.result_path,
                       "evidence_paths": {evidence_ref: str(evidence_path)}}

    def tearDown(self):
        self.temp.cleanup()

    def finalize(self):
        return calibration.finalize_sample(self.sample, **self.source,
                                            finalized_by="parent:" + self.sample["identity"]["task_id"])

    def test_report_reloads_sources_and_deduplicates_without_promoting_qualification(self):
        final = self.finalize()
        sources = {final["record_id"]: self.source}
        report = calibration.observation_report([final, final], sources=sources)
        self.assertEqual(1, report["cohorts"][0]["sample_count"])
        self.assertEqual(1, report["cohorts"][0]["independent_tasks"])
        self.assertEqual("NONE", report["execution_authorization"])
        (self.fixture.repo / "README.md").write_text("Later implementation", encoding="utf-8")
        self.assertEqual(report, calibration.observation_report([final], sources=sources))
        with self.assertRaisesRegex(RoutingError, "NOT_CURRENT"):
            self.finalize()

    def test_forged_finalized_flag_or_changed_metrics_cannot_enter_report(self):
        final = self.finalize()
        changed = copy.deepcopy(final)
        changed["metrics"]["duration_ms"] = 1
        with self.assertRaisesRegex(RoutingError, "EVIDENCE_BINDING"):
            calibration.observation_report([changed], sources={final["record_id"]: self.source})
        changed = {**final, "reserved_units": 0}
        with self.assertRaisesRegex(RoutingError, "RECOMPUTATION"):
            calibration.observation_report([changed], sources={final["record_id"]: self.source})
        with self.assertRaisesRegex(RoutingError, "SOURCE_REQUIRED"):
            calibration.observation_report([final], sources={})

    def test_source_mutation_or_foreign_identity_is_rejected(self):
        final = self.finalize()
        evidence_path = Path(next(iter(self.source["evidence_paths"].values())))
        self.evidence["project_id"] = "foreign-project"
        atomic_write_json(evidence_path, self.evidence, seal=True)
        with self.assertRaisesRegex(RoutingError, "EVIDENCE_BINDING"):
            calibration.observation_report([final], sources={final["record_id"]: self.source})


if __name__ == "__main__":
    unittest.main()
