"""中文：路由卡片的统计来源、发布批准与消费绑定。

English: Routing cards bind immutable experiment results and separate issuer
approval from consumer activation. Hash integrity is not an OS trust boundary.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable, Mapping

from .approval import check_approval, consume_approval, load_approval
from .common import atomic_write_json, read_json, repo_snapshot, require_external_state
from .event_v2 import OwnerTokenLock, stable_repo_fingerprint
from .routing_contract import (
    ALGORITHM_ID, HOST_SURFACE, POLICY_ID, RoutingError, assert_current_window, boolean,
    exact, fail, hex_digest, identifier, identity, integer, policy, policy_digest,
    profile_spec, ref, scenario, sha,
)
from .routing_statistics import paired_quality

EXPERIMENT_FIELDS = {"schema_version", "experiment_id", "identity", "origin", "issuer",
                     "scenario", "rubric_ref", "minimum_pass_bp", "baseline_profile",
                     "comparisons", "family_intervals", "case_plan", "repetitions",
                     "protocol_ref", "samples", "finalizer"}
SAMPLE_FIELDS = {"sample_id", "cluster_id", "case_id", "repetition", "profile_id",
                 "passed", "clean", "critical", "false_block", "critical_failure", "boundary_failure",
                 "task_ref", "call_ref", "receipt_ref", "response_ref", "gold_ref",
                 "prompt_ref", "case_ref", "cost_units", "latency_ms"}
COST_FIELDS = {"profile_id", "scenario_ref", "cost_basis", "plan_cost", "reserve_units",
               "latency_ms", "measurement", "source_ref"}
BUNDLE_FIELDS = {"schema_version", "bundle_id", "identity", "policy_id", "policy_digest",
                 "algorithm_id", "origin", "created_at", "expires_at", "experiment_ref",
                 "qualification", "gains", "costs"}
PUBLICATION_FIELDS = {"schema_version", "publication_id", "revision", "identity", "bundle_ref",
                      "experiment_ref", "issuer_task_id", "issuer_baseline", "approval_ref",
                      "scope", "status", "created_at", "expires_at"}
TRACE_FIELDS = {"schema_version", "host_surface", "identity", "task_ref", "call_ref",
                "receipt_ref", "response_ref", "profile_id", "outcome", "source",
                "prompt_ref", "case_ref", "scenario_ref", "protocol_ref"}


def protocol_reference(value: Mapping[str, Any]) -> str:
    profiles = sorted({name for pair in value["comparisons"] for name in pair.values()})
    return ref({"identity": value["identity"], "scenario_ref": ref(scenario(value["scenario"])),
                "profiles": profiles, "case_plan": sorted(value["case_plan"]),
                "repetitions": value["repetitions"], "rubric_ref": value["rubric_ref"],
                "comparisons": sorted(value["comparisons"], key=ref),
                "baseline_profile": value["baseline_profile"], "minimum_pass_bp": value["minimum_pass_bp"],
                "family_intervals": value["family_intervals"], "policy_digest": policy_digest()})


def validate_experiment(value: Any, *, trace_loader: Callable[[str], Mapping[str, Any]] | None = None,
                        require_native: bool = False) -> dict[str, Any]:
    exact(value, EXPERIMENT_FIELDS, "EXPERIMENT_FIELDS")
    if value["schema_version"] != "routing-experiment/1":
        fail("EXPERIMENT_VERSION")
    identifier(value["experiment_id"])
    expected_identity = identity(value["identity"])
    experiment_scenario = scenario(value["scenario"])
    sha(value["rubric_ref"])
    if value["origin"] not in {"synthetic", "desktop-evaluation"}:
        fail("EXPERIMENT_ORIGIN")
    if require_native and (value["origin"] != "desktop-evaluation" or trace_loader is None):
        fail("PRODUCTION_REQUIRES_NATIVE_EVALUATION")
    issuer = exact(value["issuer"], {"task_id", "baseline_sha256"}, "EXPERIMENT_ISSUER")
    identifier(issuer["task_id"]); hex_digest(issuer["baseline_sha256"])
    if value["finalizer"] != "parent:" + issuer["task_id"]:
        fail("EXPERIMENT_PARENT_FINALIZER_REQUIRED")
    integer(value["minimum_pass_bp"], "EXPERIMENT_ABSOLUTE_QUALITY",
            minimum=policy()["thresholds"]["absolute_quality_floor_bp"], maximum=10000)
    baseline = value["baseline_profile"]
    profile_spec(baseline)
    pairs = value["comparisons"]
    if not isinstance(pairs, list) or not pairs or len(pairs) > 153:
        fail("EXPERIMENT_COMPARISON_LIMIT")
    seen_pairs: set[tuple[str, str]] = set()
    for pair in pairs:
        exact(pair, {"anchor", "challenger"}, "EXPERIMENT_PAIR_FIELDS")
        for name in pair.values():
            profile_spec(name)
        key = pair["anchor"], pair["challenger"]
        if key[0] == key[1] or key in seen_pairs:
            fail("EXPERIMENT_PAIR_DUPLICATE")
        seen_pairs.add(key)
    # 中文：质量与干净对照误阻断各使用两个不一致事件比例。
    # English: Two discordant proportions for quality and two for clean false blocks.
    if value["family_intervals"] != 4 * len(pairs):
        fail("EXPERIMENT_COMPARISON_FAMILY_MISMATCH")
    case_plan = value["case_plan"]
    if not isinstance(case_plan, list) or not case_plan or len(case_plan) > 10000 \
            or len(case_plan) != len(set(case_plan)):
        fail("EXPERIMENT_CASE_PLAN")
    for case_ref in case_plan:
        sha(case_ref)
    integer(value["repetitions"], "EXPERIMENT_REPETITIONS", minimum=1, maximum=20)
    planned_profiles = {name for pair in pairs for name in pair.values()}
    expected_count = len(case_plan) * len(planned_profiles) * value["repetitions"]
    if expected_count > policy()["limits"]["max_cases"] or value["protocol_ref"] != protocol_reference(value):
        fail("EXPERIMENT_PROTOCOL_BINDING")
    rows = value["samples"]
    if not isinstance(rows, list) or not rows or len(rows) > policy()["limits"]["max_cases"]:
        fail("EXPERIMENT_SAMPLE_LIMIT")
    ids: set[str] = set()
    repetitions: set[tuple[str, str, str, int]] = set()
    tasks: dict[tuple[str, str], str] = {}
    trace_cache: dict[str, Mapping[str, Any]] = {}
    observed_cases: set[tuple[str, str, int]] = set()
    used_receipts: set[str] = set()
    used_calls: set[str] = set()
    for row in rows:
        exact(row, SAMPLE_FIELDS, "SAMPLE_FIELDS")
        for key in ("sample_id", "cluster_id", "case_id"):
            identifier(row[key], "SAMPLE_IDENTIFIER")
        if row["sample_id"] in ids:
            fail("SAMPLE_DUPLICATE_ID")
        ids.add(row["sample_id"])
        profile_spec(row["profile_id"])
        integer(row["repetition"], "SAMPLE_REPETITION", minimum=1, maximum=20)
        rep = row["profile_id"], row["cluster_id"], row["case_id"], row["repetition"]
        if rep in repetitions:
            fail("SAMPLE_DUPLICATE_REPETITION")
        repetitions.add(rep)
        for key in ("passed", "clean", "critical", "false_block", "critical_failure", "boundary_failure"):
            boolean(row[key], "SAMPLE_BOOLEAN")
        if row["critical_failure"] and not row["critical"]:
            fail("CRITICAL_FAILURE_WITHOUT_SENTINEL")
        if row["false_block"] and not row["clean"]:
            fail("FALSE_BLOCK_REQUIRES_CLEAN_CONTROL")
        if row["passed"] and (row["false_block"] or row["critical_failure"] or row["boundary_failure"]):
            fail("SAMPLE_PASS_CONTRADICTS_FAILURE")
        for key in ("task_ref", "call_ref", "receipt_ref", "response_ref", "gold_ref", "prompt_ref", "case_ref"):
            sha(row[key], "SAMPLE_REFERENCE")
        if row["receipt_ref"] in used_receipts or row["call_ref"] in used_calls:
            fail("SAMPLE_NATIVE_TRIAL_REUSED")
        used_receipts.add(row["receipt_ref"]); used_calls.add(row["call_ref"])
        case = {key: row[key] for key in ("case_id", "cluster_id", "prompt_ref", "gold_ref", "clean", "critical")}
        if row["case_ref"] != ref(case):
            fail("PAIRED_CASE_MANIFEST_MISMATCH")
        trial = row["profile_id"], row["case_ref"], row["repetition"]
        if trial in observed_cases or row["profile_id"] not in planned_profiles \
                or row["case_ref"] not in case_plan or row["repetition"] > value["repetitions"]:
            fail("EXPERIMENT_TRIAL_NOT_IN_PLAN")
        observed_cases.add(trial)
        integer(row["cost_units"], "SAMPLE_COST")
        integer(row["latency_ms"], "SAMPLE_DURATION", maximum=604800000)
        task_key = row["profile_id"], row["task_ref"]
        if task_key in tasks and tasks[task_key] != row["cluster_id"]:
            fail("INDEPENDENT_CLUSTER_ALIAS")
        tasks[task_key] = row["cluster_id"]
        if require_native:
            if row["receipt_ref"] not in trace_cache:
                trace_cache[row["receipt_ref"]] = trace_loader(row["receipt_ref"])  # type: ignore[misc]
            trace = exact(trace_cache[row["receipt_ref"]], TRACE_FIELDS, "NATIVE_TRACE_FIELDS")
            if trace["schema_version"] != "desktop-evaluation-trace/1" \
                    or trace["source"] != "verified-host-receipt" \
                    or trace["host_surface"] != HOST_SURFACE or trace["identity"] != expected_identity \
                    or trace["scenario_ref"] != ref(experiment_scenario) \
                    or trace["protocol_ref"] != value["protocol_ref"] \
                    or trace["outcome"] != "COMPLETED" \
                    or any(trace[key] != row[key] for key in
                           ("task_ref", "call_ref", "receipt_ref", "response_ref", "profile_id", "prompt_ref", "case_ref")):
                fail("NATIVE_TRACE_BINDING_MISMATCH")
    present = {row["profile_id"] for row in rows}
    if baseline not in present or any(not set(pair.values()).issubset(present) for pair in pairs):
        fail("EXPERIMENT_COMPARISON_SAMPLES_MISSING")
    if len(observed_cases) != expected_count:
        fail("EXPERIMENT_PLANNED_TRIALS_MISSING")
    normalized = copy.deepcopy(value)
    normalized["scenario"] = experiment_scenario
    return normalized


def _clusters(experiment: Mapping[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, list[Mapping[str, Any]]]] = {}
    for row in experiment["samples"]:
        grouped.setdefault(row["profile_id"], {}).setdefault(row["cluster_id"], []).append(row)
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for profile_id, clusters in grouped.items():
        output[profile_id] = {}
        for cluster, rows in clusters.items():
            signatures = sorted((row["case_id"], row["repetition"], row["gold_ref"], row["clean"]) for row in rows)
            output[profile_id][cluster] = {
                "passed": all(row["passed"] for row in rows),
                "clean": all(row["clean"] for row in rows),
                "false_block": any(row["false_block"] for row in rows),
                "critical": any(row["critical"] for row in rows),
                "critical_failure": any(row["critical_failure"] or row["boundary_failure"] for row in rows),
                "signature": signatures,
            }
    return output


def derived_cards(experiment: Mapping[str, Any]) -> tuple[list[dict], list[dict]]:
    """中文：从配对案例机械重算，不消费模型自报分数。

    English: Derive cards from paired outcomes, never caller-provided scores.
    """
    experiment = validate_experiment(experiment)
    grouped = _clusters(experiment)
    thresholds = policy()["thresholds"]
    qualifications: list[dict] = []
    gains: list[dict] = []
    for pair in experiment["comparisons"]:
        anchor, challenger = pair["anchor"], pair["challenger"]
        a, b = grouped[anchor], grouped[challenger]
        if set(a) != set(b) or any(a[key]["signature"] != b[key]["signature"] for key in a):
            fail("PAIRED_CASE_OR_RUBRIC_MISMATCH")
        keys = sorted(a)
        quality = paired_quality([a[key]["passed"] for key in keys],
                                 [b[key]["passed"] for key in keys],
                                 family_intervals=experiment["family_intervals"])
        clean = [key for key in keys if a[key]["clean"] and b[key]["clean"]]
        false_blocks = paired_quality([a[key]["false_block"] for key in clean],
                                      [b[key]["false_block"] for key in clean],
                                      family_intervals=experiment["family_intervals"]) if clean else None
        gains.append({
            "anchor": anchor, "challenger": challenger, "scenario_ref": ref(experiment["scenario"]),
            "experiment_ref": ref(experiment), "quality": quality, "false_blocks": false_blocks,
            "critical_failures": sum(b[key]["critical_failure"] for key in keys),
        })
    for profile_id, rows in sorted(grouped.items()):
        n = len(rows)
        reasons: list[str] = []
        if n < thresholds["min_independent_cases"]:
            reasons.append("INDEPENDENT_SAMPLES_INSUFFICIENT")
        if sum(row["passed"] for row in rows.values()) * 10000 < experiment["minimum_pass_bp"] * n:
            reasons.append("ABSOLUTE_QUALITY_NOT_MET")
        if any(row["critical_failure"] for row in rows.values()):
            reasons.append("CRITICAL_OR_BOUNDARY_FAILURE")
        if not any(row["clean"] for row in rows.values()):
            reasons.append("CLEAN_CONTROLS_MISSING")
        if experiment["scenario"]["risk"] >= 2 and not any(row["critical"] for row in rows.values()):
            reasons.append("CRITICAL_SENTINELS_MISSING")
        if profile_id != experiment["baseline_profile"]:
            comparison = next((item for item in gains if item["anchor"] == experiment["baseline_profile"]
                               and item["challenger"] == profile_id), None)
            if not comparison:
                reasons.append("BASELINE_COMPARISON_MISSING")
            else:
                if comparison["quality"]["lower_delta_bp"] < -thresholds["noninferiority_margin_bp"]:
                    reasons.append("NONINFERIORITY_NOT_ESTABLISHED")
                if not comparison["false_blocks"] or comparison["false_blocks"]["upper_delta_bp"] \
                        > thresholds["false_block_margin_bp"]:
                    reasons.append("FALSE_BLOCK_MARGIN_NOT_ESTABLISHED")
        qualifications.append({
            "profile_id": profile_id, "scenario_ref": ref(experiment["scenario"]),
            "experiment_ref": ref(experiment), "independent_cases": n,
            "qualified": not reasons, "reasons": reasons,
        })
    return qualifications, gains


def validate_cost(value: Any, *, scenario_ref: str) -> dict[str, Any]:
    exact(value, COST_FIELDS, "COST_CARD_FIELDS")
    profile_spec(value["profile_id"])
    if value["scenario_ref"] != scenario_ref:
        fail("COST_SCENARIO_MISMATCH")
    identifier(value["cost_basis"], "COST_BASIS")
    for key in ("plan_cost", "reserve_units", "latency_ms"):
        integer(value[key], "COST_CARD_VALUE", minimum=1)
    if value["measurement"] not in {"measured_codex_credits", "declared_proxy"}:
        fail("COST_MEASUREMENT_INVALID")
    sha(value["source_ref"])
    return copy.deepcopy(value)


def build_bundle(experiment: Mapping[str, Any], costs: list[dict], *, bundle_id: str,
                 created_at: str, expires_at: str) -> dict[str, Any]:
    experiment = validate_experiment(experiment)
    qualification, gains = derived_cards(experiment)
    if not isinstance(costs, list) or not costs or len(costs) > 18:
        fail("COST_CARD_LIMIT")
    normalized = [validate_cost(value, scenario_ref=ref(experiment["scenario"])) for value in costs]
    if len({item["profile_id"] for item in normalized}) != len(normalized) \
            or len({item["cost_basis"] for item in normalized}) != 1:
        fail("COST_CARD_DUPLICATE_OR_MIXED_BASIS")
    value = {
        "schema_version": "routing-card-bundle/1", "bundle_id": identifier(bundle_id),
        "identity": dict(experiment["identity"]), "policy_id": POLICY_ID, "policy_digest": policy_digest(),
        "algorithm_id": ALGORITHM_ID, "origin": experiment["origin"],
        "created_at": created_at, "expires_at": expires_at, "experiment_ref": ref(experiment),
        "qualification": qualification, "gains": gains, "costs": sorted(normalized, key=lambda row: row["profile_id"]),
    }
    assert_current_window(value, created_at)
    return value


def validate_bundle(bundle: Any, experiment: Mapping[str, Any], *, now: str,
                    trace_loader: Callable[[str], Mapping[str, Any]] | None = None,
                    production: bool = True) -> dict[str, Any]:
    exact(bundle, BUNDLE_FIELDS, "BUNDLE_FIELDS")
    experiment = validate_experiment(experiment, trace_loader=trace_loader, require_native=production)
    rebuilt = build_bundle(experiment, bundle["costs"], bundle_id=bundle["bundle_id"],
                           created_at=bundle["created_at"], expires_at=bundle["expires_at"])
    if bundle != rebuilt:
        fail("CARD_RECOMPUTATION_MISMATCH")
    if production and any(card["measurement"] == "measured_codex_credits" for card in bundle["costs"]):
        # 中文：当前没有可归属的桌面单次计费回执；标签与摘要不能证明实际费用。
        # English: The Desktop adapter currently has no attributable per-call billing
        # receipt. A label and content hash alone cannot prove measured spend.
        fail("MEASURED_COST_EVIDENCE_UNAVAILABLE")
    assert_current_window(bundle, now)
    return rebuilt


def publication_scope(bundle: Mapping[str, Any], consumption: str) -> dict[str, Any]:
    if consumption not in {"issuer-only", "project-bound-reuse"}:
        fail("PUBLICATION_CONSUMPTION_SCOPE")
    return {"consumption": consumption, "policy_id": bundle["policy_id"],
            "policy_digest": bundle["policy_digest"], "algorithm_id": bundle["algorithm_id"],
            "scenario_refs": sorted({card["scenario_ref"] for card in bundle["qualification"]})}


def approval_binding_note(bundle: Mapping[str, Any], consumption: str) -> str:
    return "routing-card-publication:" + ref({"bundle_ref": ref(bundle),
                                            "scope": publication_scope(bundle, consumption)})


def publish_bundle(publication_path: Path, bundle: Mapping[str, Any], experiment: Mapping[str, Any], *,
                   approval_path: Path, repo_path: Path, trace_loader: Callable[[str], Mapping[str, Any]],
                   publication_id: str, consumption: str, now: str) -> dict[str, Any]:
    """中文：发行批准只消费一次；后续根按 scope 激活，不重消费旧批准。

    English: Consume issuer approval once; later roots activate its precise scope.
    """
    experiment = validate_experiment(experiment, trace_loader=trace_loader, require_native=True)
    bundle = validate_bundle(bundle, experiment, now=now, trace_loader=trace_loader)
    snapshot = repo_snapshot(repo_path)
    require_external_state(publication_path.resolve(), repo_path.resolve())
    if stable_repo_fingerprint(str(repo_path)) != bundle["identity"]["repo_fingerprint"]:
        fail("PUBLICATION_REPOSITORY_MISMATCH")
    issuer = experiment["issuer"]
    if snapshot["sha256"] != issuer["baseline_sha256"]:
        fail("ISSUER_BASELINE_CHANGED")
    approval = load_approval(approval_path)
    if approval.get("one_time") is not True:
        fail("PUBLICATION_APPROVAL_ONE_TIME_REQUIRED")
    if approval["note"] != approval_binding_note(bundle, consumption):
        fail("PUBLICATION_APPROVAL_SCOPE_MISMATCH")
    checked = check_approval(approval_path, bundle["identity"]["project_id"], issuer["task_id"],
                             "make-effective", "local", snapshot["sha256"])
    if not checked.valid:
        fail("PUBLICATION_APPROVAL_INVALID")
    value = {
        "schema_version": "routing-card-publication/1", "publication_id": identifier(publication_id),
        "revision": 1, "identity": dict(bundle["identity"]), "bundle_ref": ref(bundle),
        "experiment_ref": ref(experiment), "issuer_task_id": issuer["task_id"],
        "issuer_baseline": issuer["baseline_sha256"], "approval_ref": ref(approval),
        "scope": publication_scope(bundle, consumption), "status": "approved",
        "created_at": now, "expires_at": bundle["expires_at"],
    }
    # 中文：批准和发布分属两个文件；消费后中断不会重新授予权限。
    # English: Workflow approval and publication are two files. A crash after consumption
    # never auto-reissues authority: retry requires a separately issued approval.
    with OwnerTokenLock(publication_path, timeout=2):
        if publication_path.exists():
            fail("PUBLICATION_ALREADY_EXISTS")
        with OwnerTokenLock(approval_path, timeout=2):
            if load_approval(approval_path) != approval:
                fail("PUBLICATION_APPROVAL_CHANGED")
            consume_approval(approval_path, bundle["identity"]["project_id"], issuer["task_id"],
                             "make-effective", "local", snapshot["sha256"])
            atomic_write_json(publication_path, value, seal=True)
    return value


def load_publication(path: Path, *, bundle: Mapping[str, Any], consumer_identity: Mapping[str, Any],
                     consumer_task_id: str, now: str, expected_revision: int | None = None) -> dict[str, Any]:
    value = read_json(path, verify=True, label="Routing publication")
    value.pop("integrity")
    exact(value, PUBLICATION_FIELDS, "PUBLICATION_FIELDS")
    if value["schema_version"] != "routing-card-publication/1" or value["status"] != "approved" \
            or value["identity"] != identity(dict(consumer_identity)) or value["bundle_ref"] != ref(bundle) \
            or value["experiment_ref"] != bundle["experiment_ref"]:
        fail("PUBLICATION_BINDING_OR_STATUS")
    integer(value["revision"], "PUBLICATION_REVISION", minimum=1)
    if expected_revision is not None and value["revision"] != expected_revision:
        fail("PUBLICATION_REVISION_CHANGED")
    if value["scope"] != publication_scope(bundle, value["scope"].get("consumption", "")):
        fail("PUBLICATION_SCOPE_CHANGED")
    if value["scope"]["consumption"] == "issuer-only" and value["issuer_task_id"] != consumer_task_id:
        fail("PUBLICATION_ISSUER_ONLY")
    assert_current_window(value, now)
    return value


def revoke_publication(path: Path, *, expected_revision: int, reason_ref: str) -> dict[str, Any]:
    sha(reason_ref)
    with OwnerTokenLock(path, timeout=2):
        value = read_json(path, verify=True, label="Routing publication")
        value.pop("integrity")
        exact(value, PUBLICATION_FIELDS, "PUBLICATION_FIELDS")
        if value["revision"] != expected_revision or value["status"] != "approved":
            fail("PUBLICATION_REVOCATION_CONFLICT")
        value["revision"] += 1
        value["status"] = "revoked"
        # 中文：原因与原批准绑定，不扩大稳定文档字段集。
        # English: The reason is bound without broadening the stable document field set.
        value["approval_ref"] = ref({"prior_approval_ref": value["approval_ref"], "revocation_ref": reason_ref})
        atomic_write_json(path, value, seal=True)
        return value
