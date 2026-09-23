"""中文：V4 观察样本独立分组；不自动修改选型或预算。

English: V4 observations stay in versioned cohorts and never alter routing.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from . import budget_v4
from .review_v4 import expected_result, validate_result
from .common import verify_record
from .evidence import check_evidence
from .routing_contract import exact, fail, integer, read_document, ref, sha

METRICS = {"accepted_findings", "repaired_findings", "duplicate_findings",
           "missed_findings", "regressions_prevented", "duration_ms"}
SAMPLE_FIELDS = {"schema_version", "record_id", "identity", "reservation_id", "result_ref",
                 "policy_id", "policy_digest", "profile_id", "scenario_ref", "phase",
                 "cost_basis", "reserved_units", "qualification_ref", "gain_ref", "cost_ref",
                 "metrics", "source", "finalized", "finalizer", "evidence_refs"}


def pending_sample(ledger_path: Path, reservation_id: str, result_path: Path,
                   metrics: Mapping[str, Any]) -> dict[str, Any]:
    ledger = budget_v4.read_budget(ledger_path)
    if ledger["execution_mode"] != "PRODUCTION":
        fail("EVALUATION_SAMPLES_REQUIRE_SEPARATE_EXPERIMENT_REPORT")
    reservation = ledger["reservations"].get(reservation_id)
    accepted = ledger["accepted_results"].get(reservation_id)
    if not reservation or reservation["state"] != "COMPLETED" or not accepted:
        fail("V4_SAMPLE_REQUIRES_ACCEPTED_RESULT")
    payload, result_ref = read_document(result_path)
    if result_ref != accepted["result_ref"] or payload.get("schema_version") != 6:
        fail("V4_SAMPLE_RESULT_BINDING")
    validate_result(payload, expected_result(ledger, reservation["permit_id"],
                                            isolation_level=payload.get("isolation_level", "")))
    if payload["status"] != accepted["status"] or payload["supersedes"] != accepted["supersedes"]:
        fail("V4_SAMPLE_RESULT_BINDING")
    exact(dict(metrics), METRICS, "V4_SAMPLE_METRICS")
    for name, value in metrics.items():
        integer(value, "V4_SAMPLE_METRIC", maximum=604800000 if name == "duration_ms" else 1000)
    if metrics["accepted_findings"] > len(payload["findings"]) \
            or metrics["repaired_findings"] > metrics["accepted_findings"] \
            or metrics["duplicate_findings"] + metrics["accepted_findings"] > len(payload["findings"]):
        fail("V4_SAMPLE_FINDING_COUNTS")
    permit = ledger["permits"][reservation["permit_id"]]
    choice = permit["selection"]
    return {
        "schema_version": "4.0", "record_id": "DCS4_" + ref({
            "identity": ledger["identity"], "reservation_id": reservation_id, "result_ref": result_ref})[7:],
        "identity": ledger["identity"], "reservation_id": reservation_id, "result_ref": result_ref,
        "policy_id": choice["policy_id"], "policy_digest": choice["policy_digest"],
        "profile_id": choice["approved_profile"], "scenario_ref": choice["scenario_ref"],
        "phase": permit["request"]["scenario"]["phase"], "cost_basis": choice["cost_basis"],
        "reserved_units": choice["reserve_units"], "qualification_ref": choice["qualification_ref"],
        "gain_ref": choice["gain_ref"], "cost_ref": choice["cost_ref"], "metrics": dict(metrics),
        "source": "parent-observation", "finalized": False, "finalizer": "", "evidence_refs": [],
    }


def finalize_sample(sample: Mapping[str, Any], *, ledger_path: Path, result_path: Path,
                    evidence_paths: Mapping[str, str], finalized_by: str) -> dict[str, Any]:
    exact(dict(sample), SAMPLE_FIELDS, "V4_SAMPLE_FIELDS")
    if sample["finalized"] is not False or sample["source"] != "parent-observation" \
            or finalized_by != "parent:" + sample["identity"]["task_id"]:
        fail("V4_SAMPLE_PARENT_FINALIZATION")
    rebuilt = pending_sample(ledger_path, sample["reservation_id"], result_path, sample["metrics"])
    if rebuilt != sample:
        fail("V4_SAMPLE_RECOMPUTATION")
    _verify_evidence(sample, ledger_path=ledger_path, evidence_paths=evidence_paths, current=True)
    result = copy.deepcopy(dict(sample))
    result.update(finalized=True, finalizer=finalized_by, evidence_refs=sorted(evidence_paths))
    return result


def _verify_evidence(sample: Mapping[str, Any], *, ledger_path: Path,
                     evidence_paths: Mapping[str, str], current: bool) -> None:
    ledger = budget_v4.read_budget(ledger_path)
    if not evidence_paths or len(evidence_paths) > 8:
        fail("V4_SAMPLE_EVIDENCE_REQUIRED")
    expected_scope = {"result:" + sample["result_ref"], "reservation:" + ref(sample["reservation_id"]),
                      "metrics:" + ref(sample["metrics"]), "scenario:" + sample["scenario_ref"]}
    for evidence_ref, path in evidence_paths.items():
        record, observed_ref = read_document(Path(path))
        verify_record(record, "V4 calibration Evidence")
        if observed_ref != sha(evidence_ref) or record.get("source") != "parent-finalized-v4-review" \
                or not expected_scope.issubset(set(record.get("scope_refs", []))) \
                or record.get("schema_version") != 1 or record.get("status") != "valid" \
                or record.get("project_id") != sample["identity"]["project_id"] \
                or record.get("task_id") != sample["identity"]["task_id"]:
            fail("V4_SAMPLE_EVIDENCE_BINDING")
        baseline = record.get("baseline", {})
        if not baseline.get("repo_path") or Path(baseline["repo_path"]).resolve() != \
                Path(ledger["root_binding"]["repo_path"]).resolve():
            fail("V4_SAMPLE_EVIDENCE_REPO")
        sha("sha256:" + str(baseline.get("sha256", "")), "V4_SAMPLE_EVIDENCE_BASELINE")
        if current:
            checked = check_evidence(Path(path), Path(ledger["root_binding"]["repo_path"]),
                                     sample["identity"]["project_id"], sample["identity"]["task_id"])
            if not checked.valid:
                fail("V4_SAMPLE_EVIDENCE_NOT_CURRENT")


def verify_finalized_sample(sample: Mapping[str, Any], *, ledger_path: Path, result_path: Path,
                            evidence_paths: Mapping[str, str]) -> dict[str, Any]:
    """中文：读回历史来源，不把旧观察当作当前基线验收。

    English: Verify historical sources without asserting current-code readiness.
    """
    exact(dict(sample), SAMPLE_FIELDS, "V4_SAMPLE_FIELDS")
    if sample["schema_version"] != "4.0" or sample["finalized"] is not True \
            or sample["finalizer"] != "parent:" + sample["identity"]["task_id"] \
            or sample["evidence_refs"] != sorted(evidence_paths):
        fail("V4_SAMPLE_NOT_FINALIZED")
    expected = pending_sample(ledger_path, sample["reservation_id"], result_path, sample["metrics"])
    expected.update(finalized=True, finalizer=sample["finalizer"], evidence_refs=sorted(evidence_paths))
    if expected != sample:
        fail("V4_SAMPLE_RECOMPUTATION")
    _verify_evidence(sample, ledger_path=ledger_path, evidence_paths=evidence_paths, current=False)
    return copy.deepcopy(dict(sample))


def observation_report(samples: list[Mapping[str, Any]], *, sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(samples, list) or len(samples) > 10000:
        fail("V4_SAMPLE_REPORT_LIMIT")
    cohorts: dict[tuple, dict[str, Any]] = {}
    seen: dict[str, str] = {}
    for sample in samples:
        exact(dict(sample), SAMPLE_FIELDS, "V4_SAMPLE_FIELDS")
        source = sources.get(sample["record_id"])
        exact(source, {"ledger_path", "result_path", "evidence_paths"}, "V4_SAMPLE_SOURCE_REQUIRED")
        verify_finalized_sample(sample, ledger_path=Path(source["ledger_path"]),
                                result_path=Path(source["result_path"]), evidence_paths=source["evidence_paths"])
        sample_ref = ref(sample)
        if sample["record_id"] in seen and seen[sample["record_id"]] != sample_ref:
            fail("V4_SAMPLE_DUPLICATE_CONFLICT")
        if sample["record_id"] in seen:
            continue
        seen[sample["record_id"]] = sample_ref
        key = (sample["identity"]["project_id"], sample["identity"]["repo_fingerprint"],
               sample["policy_id"], sample["policy_digest"], sample["scenario_ref"], sample["cost_basis"],
               sample["phase"], sample["profile_id"])
        row = cohorts.setdefault(key, {"key": list(key), "tasks": set(), "sample_count": 0, "reserved_units": 0})
        row["tasks"].add(sample["identity"]["task_id"])
        row["sample_count"] += 1
        row["reserved_units"] += sample["reserved_units"]
    rows = [{**row, "tasks": sorted(row["tasks"]), "independent_tasks": len(row["tasks"])}
            for _, row in sorted(cohorts.items())]
    return {"schema_version": "routing-observation/1", "cohorts": rows,
            "recommendation": "NO_AUTOMATIC_POLICY_CHANGE", "execution_authorization": "NONE",
            "limitation": "Historical observations do not establish current-code readiness, qualification or paired gain."}
