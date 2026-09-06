"""中文：从已确认根因生成项目内待审回归候选，并关联后续收益证据。

English: Generate project-local regression candidates from confirmed causes and link subsequent benefit evidence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .artifacts import ArtifactError, MAX_BYTES, load, persist, seal
from .contracts import OptimizationProposal, sha256_hex
from .storage import safe_child
from .task_feedback import FEEDBACK_SCHEMA, _validate_report, finalized_reports


def create_candidates(project_dir: Path, proposal: OptimizationProposal) -> list[dict[str, str]]:
    if proposal.hypothesis is None:
        return []
    target = proposal.hypothesis["scope"]["metric_target"]
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for path, report in finalized_reports(project_dir):
        if report["root_cause_confirmed"] and target == "root_cause_id:" + report["root_cause_id"].lower():
            grouped.setdefault(report["root_cause_id"], []).append((path, report))
    references = []
    for root_cause, reports in grouped.items():
        categories = {report["failure_category"] for _, report in reports}
        kinds = ["NEGATIVE_TEST"]
        if "ROUTING" in categories:
            kinds.append("ROUTING_CASE")
        if categories & {"INPUT_CONTRACT", "ENVIRONMENT"}:
            kinds.append("PREFLIGHT_CHECK")
        evidence_refs = [{"path": path, "content_hash": report["content_hash"]} for path, report in reports]
        for kind in kinds:
            candidate_key = {"project_id": proposal.project_id, "proposal_hash": proposal.content_hash,
                             "root_cause_id": root_cause, "kind": kind, "source_refs": evidence_refs}
            candidate_id = "REG_" + sha256_hex(candidate_key)
            value = seal({"schema_version": "regression-candidate/1", "candidate_id": candidate_id,
                          **candidate_key, "proposal_id": proposal.proposal_id,
                          "repo_fingerprint": proposal.hypothesis["scope"]["repo_fingerprint"],
                          "target_resource": proposal.target_resource, "status": "PENDING_REVIEW",
                          "cases": [
                              {"condition": "REPRODUCE_CONFIRMED_ROOT_CAUSE", "root_cause_id": root_cause,
                               "expected": "DETECT_AND_REJECT" if kind != "ROUTING_CASE" else "SELECT_REQUIRED_DOMAIN"},
                              {"condition": "ADJACENT_VALID_CONTROL", "root_cause_id": root_cause,
                               "expected": "ACCEPT_WITHOUT_FALSE_POSITIVE" if kind != "ROUTING_CASE" else "DO_NOT_TRIGGER_UNRELATED_DOMAIN"}],
                          "implementation_requirements": ["MATERIALIZE_FIXTURE_IN_AUTHORIZED_TASK", "VERIFY_POSITIVE_AND_NEGATIVE_CASES"],
                          "execution_authorization": "NONE", "automatic_application": False})
            references.append(persist(project_dir, "evolution/regression-candidates/" + candidate_id + ".json", value))
    return references


def verify_candidate(project_dir: Path, reference: Mapping[str, str], proposal: OptimizationProposal) -> dict[str, Any]:
    value = load(project_dir, reference["path"], reference["content_hash"], "regression-candidate/1")
    if value["proposal_hash"] != proposal.content_hash or value["proposal_id"] != proposal.proposal_id or value["project_id"] != proposal.project_id:
        raise ArtifactError("REGRESSION_CANDIDATE_IDENTITY_MISMATCH")
    if proposal.hypothesis is None or value["repo_fingerprint"] != proposal.hypothesis["scope"]["repo_fingerprint"]:
        raise ArtifactError("REGRESSION_CANDIDATE_IDENTITY_MISMATCH")
    if not value["source_refs"]:
        raise ArtifactError("REGRESSION_ROOT_CAUSE_NOT_CONFIRMED")
    if value["automatic_application"] is not False or value["status"] != "PENDING_REVIEW":
        raise ArtifactError("REGRESSION_CANDIDATE_AUTHORITY_INVALID")
    for ref in value["source_refs"]:
        report = _validate_report(project_dir, load(project_dir, ref["path"], ref["content_hash"], FEEDBACK_SCHEMA))
        if not report["root_cause_confirmed"] or report["root_cause_id"] != value["root_cause_id"]:
            raise ArtifactError("REGRESSION_ROOT_CAUSE_NOT_CONFIRMED")
    return value


def record_followups(project_dir: Path, proposal: OptimizationProposal, report: Mapping[str, Any]) -> list[dict[str, str]]:
    root = safe_child(project_dir, "evolution", "regression-candidates")
    if not root.exists():
        return []
    references = []
    for index, path in enumerate(sorted(root.glob("*.json"))):
        if index >= 1000:
            raise ArtifactError("TOO_MANY_REGRESSION_CANDIDATES")
        relative = "evolution/regression-candidates/" + path.name
        value = load(project_dir, relative, schema="regression-candidate/1")
        if value["proposal_id"] != proposal.proposal_id:
            continue
        candidate_ref = {"path": relative, "content_hash": value["content_hash"]}
        verify_candidate(project_dir, candidate_ref, proposal)
        if report["metric"] != "failure_rate" or proposal.hypothesis["scope"]["metric_target"] != "root_cause_id:" + value["root_cause_id"].lower():
            raise ArtifactError("REGRESSION_FOLLOWUP_METRIC_MISMATCH")
        followup = _followup(proposal, report, candidate_ref)
        references.append(persist(project_dir, "evolution/regression-followups/" + followup["content_hash"] + ".json", followup))
    return references


def _followup(proposal: OptimizationProposal, report: Mapping[str, Any], candidate_ref: Mapping[str, str]) -> dict[str, Any]:
    return seal({"schema_version": "regression-followup/1", "candidate_ref": dict(candidate_ref),
                         "proposal_id": proposal.proposal_id, "project_id": proposal.project_id,
                         "benefit_report_ref": {"path": "evolution/benefit-reports/" + report["content_hash"] + ".json",
                                                "content_hash": report["content_hash"]},
                         "implementation_task_id": report["implementation_task_id"], "implementation_commit": report["implementation_commit"],
                         "baseline_recurrence_rate": report["baseline"], "observed_recurrence_rate": report["observed"],
                         "status": report["benefit_status"], "execution_authorization": "NONE"})


def verify_followups(project_dir: Path, views: Mapping[str, Any]) -> list[dict[str, Any]]:
    """中文：重放候选来源、独立实施绑定和真实观察窗口，不把引用存在视为收益通过。

    English: Replay candidate sources, implementation bindings and observation windows; reference existence alone is not benefit proof.
    """
    from .benefits import verify_benefit
    root = safe_child(project_dir, "evolution", "regression-followups")
    results = []
    total = 0
    for index, path in enumerate(sorted(root.glob("*.json"))):
        total += path.stat().st_size
        if index >= 1000 or total > MAX_BYTES:
            raise ArtifactError("REGRESSION_FOLLOWUP_LIMIT")
        value = load(project_dir, "evolution/regression-followups/" + path.name, schema="regression-followup/1")
        view = views.get(value["proposal_id"])
        if view is None or view.latest_benefit is None:
            raise ArtifactError("REGRESSION_FOLLOWUP_IMPLEMENTATION_MISSING")
        proposal, latest = view.proposal, view.latest_benefit
        candidate = verify_candidate(project_dir, value["candidate_ref"], proposal)
        report = verify_benefit(project_dir, value["benefit_report_ref"], proposal,
                                latest["implementation_task_id"], latest["git_baseline"], latest["implementation_commit"])
        if report["metric"] != "failure_rate" or proposal.hypothesis["scope"]["metric_target"] != "root_cause_id:" + candidate["root_cause_id"].lower():
            raise ArtifactError("REGRESSION_FOLLOWUP_METRIC_MISMATCH")
        if _followup(proposal, report, value["candidate_ref"]) != value:
            raise ArtifactError("REGRESSION_FOLLOWUP_RECOMPUTATION_MISMATCH")
        results.append(value)
    return results
