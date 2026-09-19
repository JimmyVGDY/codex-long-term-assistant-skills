"""中文：把委派根身份绑定到现有项目与任务信封。

English: Verify delegation roots against the existing project and task envelope.
No host identity is invented; callers pass the actual host session identifier.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .dispatch_policy import LEGACY_POLICY_ID, DispatchPolicyError, _unique_object, digest, policy, policy_digest, resolve_evidence, score_review
from .event_v3 import stable_repo_fingerprint
from .project import validate_binding
from .common import repo_snapshot

ROOT_BINDING_FIELDS = {"schema_version", "repo_path", "profile_path", "profile_binding_sha256",
                       "envelope_identity_ref", "host_session_ref", "reviewer_policy_id", "reviewer_policy_digest"}


def read_request_document(path: Path) -> tuple[dict[str, Any], str]:
    with Path(path).open("rb") as handle:
        raw = handle.read(1048577)
    if len(raw) > 1048576:
        raise DispatchPolicyError("DISPATCH_REQUEST_TOO_LARGE")
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise DispatchPolicyError("DISPATCH_REQUEST_OBJECT_REQUIRED")
    return value, "sha256:" + hashlib.sha256(raw).hexdigest()


def read_request_json(path: Path) -> dict[str, Any]:
    return read_request_document(path)[0]


def build_root_binding(envelope_path: Path, host_session_id: str) -> tuple[dict[str, str], dict[str, Any]]:
    if not isinstance(host_session_id, str) or not host_session_id.strip():
        raise DispatchPolicyError("HOST_ROOT_SESSION_MISSING")
    path = Path(envelope_path).expanduser().resolve()
    envelope = read_request_json(path)
    if envelope.get("schema_version") not in {4, 5}:
        raise DispatchPolicyError("DISPATCH_ENVELOPE_SCHEMA")
    project = envelope.get("project", {})
    if project.get("binding_status") != "BOUND" or not envelope.get("task_id"):
        raise DispatchPolicyError("DISPATCH_ENVELOPE_UNBOUND")
    repo = Path(envelope["repo_path"]).resolve()
    binding = validate_binding(Path(project["profile_path"]), repo, project["project_id"],
                               Path(project["state_path"]) if project.get("state_path") else None)
    if binding.profile_sha256 != project.get("profile_sha256"):
        raise DispatchPolicyError("DISPATCH_PROJECT_BINDING_CHANGED")
    identity = {"task_id": envelope["task_id"], "project_id": project["project_id"],
                "repo_fingerprint": stable_repo_fingerprint(str(repo))}
    selection_policy = envelope.get("routing", {}).get("reviewer_policy")
    if selection_policy is None and envelope["schema_version"] == 4:
        selection_policy = {"policy_id": LEGACY_POLICY_ID, "policy_digest": policy_digest(LEGACY_POLICY_ID)}
    if not isinstance(selection_policy, dict) or not selection_policy.get("policy_digest"):
        raise DispatchPolicyError("DISPATCH_ENVELOPE_POLICY_MISSING")
    policy(selection_policy["policy_id"], selection_policy["policy_digest"])
    # 中文：只冻结身份；阶段和验证记录更新不会无故换根。
    # English: Freeze identity, not mutable phase/counter/validation fields.
    projection = {**identity, "repo_path": str(repo), "profile_binding_sha256": binding.profile_sha256,
                  "reviewer_policy_id": selection_policy["policy_id"], "reviewer_policy_digest": selection_policy["policy_digest"]}
    return identity, {
        "schema_version": "dispatch-root/1", "repo_path": str(repo),
        "profile_path": str(Path(project["profile_path"]).resolve()),
        "profile_binding_sha256": binding.profile_sha256,
        "reviewer_policy_id": selection_policy["policy_id"], "reviewer_policy_digest": selection_policy["policy_digest"],
        "envelope_identity_ref": digest(projection),
        "host_session_ref": "sha256:" + hashlib.sha256(host_session_id.strip().encode("utf-8")).hexdigest(),
    }


def verify_root_binding(bound: Mapping[str, Any], identity: Mapping[str, str], *,
                        envelope_path: Path, cwd: str, host_session_id: str) -> None:
    if set(bound) != ROOT_BINDING_FIELDS:
        raise DispatchPolicyError("DISPATCH_ROOT_BINDING_FIELDS")
    observed_identity, observed_binding = build_root_binding(envelope_path, host_session_id)
    if any(identity.get(key) != value for key, value in observed_identity.items()) or dict(bound) != observed_binding:
        raise DispatchPolicyError("DISPATCH_ROOT_IDENTITY_MISMATCH")
    if Path(cwd).resolve() != Path(bound["repo_path"]).resolve() \
            or stable_repo_fingerprint(cwd) != identity["repo_fingerprint"]:
        raise DispatchPolicyError("DISPATCH_CURRENT_REPOSITORY_MISMATCH")


def prepare_review_selection(budget: Mapping[str, Any], request: Mapping[str, Any],
                             assignment: Mapping[str, Any], *, envelope_path: Path,
                             cwd: str, host_session_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """中文：发放前从真实 Evidence 重算；拒绝调用者提交的总分和来源自述。

    English: Resolve real Evidence before issuing a decision; never accept submitted totals/proofs.
    """
    verify_root_binding(budget["root_binding"], budget["identity"], envelope_path=envelope_path,
                        cwd=cwd, host_session_id=host_session_id)
    if not isinstance(request, Mapping) or set(request) - {
            "reviewer_budget", "requirement_profiles", "evidence_items", "evidence_paths"}:
        raise DispatchPolicyError("SELECTION_REQUEST_FIELDS")
    if not isinstance(assignment, Mapping) or set(assignment) - {
            "reviewer", "agent_type", "boundary_id", "phase", "round", "packet_sha256", "acceptable_profiles"}:
        raise DispatchPolicyError("REVIEW_ASSIGNMENT_FIELDS")
    required = {"reviewer", "agent_type", "boundary_id", "phase", "round", "packet_sha256"}
    if not required.issubset(assignment):
        raise DispatchPolicyError("REVIEW_ASSIGNMENT_FIELDS")
    snapshot = repo_snapshot(Path(cwd))
    context = {key: budget["identity"][key] for key in ("project_id", "task_id", "repo_fingerprint")}
    context.update(packet_sha256=assignment["packet_sha256"], baseline_sha256=snapshot["sha256"])
    paths = request.get("evidence_paths", {})
    if not isinstance(paths, Mapping):
        raise DispatchPolicyError("SELECTION_EVIDENCE_PATHS")
    proofs = resolve_evidence(paths, context, Path(cwd))
    selection = score_review(agent_type=assignment["agent_type"], context=context,
                             reviewer_budget=request.get("reviewer_budget", "economy"),
                             evidence_items=request.get("evidence_items", []), proofs=proofs,
                             requirements=request.get("requirement_profiles"), policy_id=budget["policy_id"])
    completed = dict(assignment)
    completed.setdefault("acceptable_profiles", [selection["approved_profile"]])
    return selection, completed
