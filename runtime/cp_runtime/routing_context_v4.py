"""中文：桌面 V4 路由的项目、输入证据与已发布卡片适配。

English: Live binding, scoped Evidence and card publication adapters for Desktop.
Untrusted request JSON never supplies a prevalidated snapshot or qualification.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any, Mapping

from .common import repo_snapshot, require_external_state, verify_record
from .project import validate_binding
from .event_v2 import stable_repo_fingerprint
from .evidence import check_evidence
from .routing_contract import (
    ALGORITHM_ID, HOST_SURFACE, POLICY_ID, RoutingError, assert_current_window, exact, fail,
    identifier, identity, integer, policy, policy_digest, profile_spec, read_document,
    ref, scenario, sha, strings, hex_digest,
)
from .routing_cards import (
    load_publication, protocol_reference, validate_bundle, validate_cost, validate_experiment,
)
from .routing_v4 import combine_cards

EVALUATION_FIELDS = {"schema_version", "identity", "scenario", "rubric_ref", "minimum_pass_bp",
                     "baseline_profile", "comparisons", "family_intervals", "case_plan",
                     "repetitions", "protocol_ref", "cases", "costs"}
CASE_FIELDS = {"case_id", "cluster_id", "prompt_ref", "gold_ref", "clean", "critical", "case_ref"}


def build_root_binding(envelope_path: Path, host_session_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    identifier(host_session_id, "DESKTOP_ROOT_SESSION_REQUIRED")
    envelope, _ = read_document(envelope_path)
    if envelope.get("schema_version") not in {4, 5}:
        fail("V4_ENVELOPE_VERSION")
    project = envelope.get("project", {})
    if project.get("binding_status") != "BOUND":
        fail("V4_PROJECT_UNBOUND")
    repo = Path(envelope["repo_path"]).resolve()
    require_external_state(envelope_path.resolve(), repo)
    bound = validate_binding(Path(project["profile_path"]), repo, project["project_id"],
                             Path(project["state_path"]) if project.get("state_path") else None)
    if bound.profile_sha256 != project["profile_sha256"]:
        fail("V4_PROJECT_PROFILE_CHANGED")
    selection = envelope.get("routing", {}).get("reviewer_policy", {})
    if selection.get("policy_id") != POLICY_ID or selection.get("policy_digest") != policy_digest():
        fail("V4_ENVELOPE_POLICY_MISMATCH")
    declared_identity = {
        "task_id": identifier(envelope["task_id"]), "project_id": project["project_id"],
        "repo_fingerprint": stable_repo_fingerprint(str(repo)),
    }
    projection = {
        **declared_identity, "repo_path": str(repo), "profile_binding_sha256": bound.profile_sha256,
        "policy_id": POLICY_ID, "policy_digest": policy_digest(),
    }
    return declared_identity, {
        "schema_version": "dispatch-root/2", "repo_path": str(repo),
        "profile_path": str(Path(project["profile_path"]).resolve()),
        "profile_binding_sha256": bound.profile_sha256, "envelope_identity_ref": ref(projection),
        "host_session_ref": ref(host_session_id), "policy_id": POLICY_ID, "policy_digest": policy_digest(),
    }


def verify_root(state: Mapping[str, Any], *, cwd: str, host_session_id: str) -> None:
    from .path_identity import same_path
    declared, binding = build_root_binding(Path(state["sources"]["root_envelope"]), host_session_id)
    if any(state["identity"][key] != value for key, value in declared.items()) \
            or dict(state["root_binding"]) != binding \
            or not same_path(Path(cwd), Path(binding["repo_path"])):
        fail("V4_ROOT_BINDING_MISMATCH")


def add_current_evidence(ledger_path: Path, paths: list[Path], *, cwd: str, host_session_id: str) -> dict[str, Any]:
    from . import budget_v4
    state = budget_v4.read_budget(ledger_path)
    verify_root(state, cwd=cwd, host_session_id=host_session_id)
    if not paths or len(paths) > 24:
        fail("V4_EVIDENCE_ADDITIONS_REQUIRED")
    additions = {}
    scenarios = {"scenario:" + ref(slot["scenario"]) for slot in state["phase_plan"]["slots"]}
    for path in paths:
        require_external_state(path.resolve(), Path(cwd).resolve())
        record, evidence_ref = read_document(path)
        verify_record(record, "V4 scope Evidence")
        checked = check_evidence(path, Path(cwd), state["identity"]["project_id"], state["identity"]["task_id"])
        if not checked.valid or record.get("source") != "parent-reviewed-v4-requirements" \
                or not scenarios.intersection(record.get("scope_refs", [])):
            fail("V4_EVIDENCE_ADDITION_NOT_CURRENT_OR_SCOPED")
        additions[evidence_ref] = state["sources"]["evidence_paths"].get(evidence_ref, str(path.resolve()))
    return budget_v4.add_evidence_paths(ledger_path, additions)


def current_evidence_refs(state: Mapping[str, Any], *, scenario_ref: str, scope_ref: str) -> list[str]:
    refs = []
    for evidence_ref, source in state["sources"]["evidence_paths"].items():
        record, observed = read_document(Path(source))
        verify_record(record, "V4 scope Evidence")
        if observed != evidence_ref:
            fail("V4_REQUIREMENT_EVIDENCE_HASH")
        checked = check_evidence(Path(source), Path(state["root_binding"]["repo_path"]),
                                 state["identity"]["project_id"], state["identity"]["task_id"])
        if checked.valid and record.get("source") == "parent-reviewed-v4-requirements" \
                and {"scenario:" + scenario_ref, scope_ref}.issubset(record.get("scope_refs", [])):
            refs.append(evidence_ref)
    return sorted(refs)


def read_evaluations(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = state["sources"]
    if not source["evaluation_costs"] or not source["evaluation_ref"]:
        fail("EVALUATION_PROTOCOL_REQUIRED")
    value, _ = read_document(Path(source["evaluation_costs"]),
                             maximum=policy()["limits"]["max_experiment_bytes"])
    if ref(value) != source["evaluation_ref"] \
            or value.get("identity") != {key: state["identity"][key] for key in ("project_id", "repo_fingerprint")}:
        fail("EVALUATION_PROTOCOL_BINDING")
    if value.get("schema_version") == "routing-evaluation-suite/1":
        return validate_evaluation_suite(value)["evaluations"]
    return [validate_evaluation(value)]


def choose_evaluation(evaluations: list[dict[str, Any]], *, case_ref: str = "", case_id: str = "") -> dict[str, Any]:
    matches = [item for item in evaluations if any(
        (not case_ref or case["case_ref"] == case_ref) and (not case_id or case["case_id"] == case_id)
        for case in item["cases"])]
    if len(matches) != 1:
        fail("EVALUATION_CASE_MISSING_OR_AMBIGUOUS")
    return matches[0]


def read_evaluation(state: Mapping[str, Any], *, case_ref: str = "", case_id: str = "") -> dict[str, Any]:
    return choose_evaluation(read_evaluations(state), case_ref=case_ref, case_id=case_id)


def validate_evaluation_suite(value: Mapping[str, Any]) -> dict[str, Any]:
    exact(dict(value), {"schema_version", "identity", "evaluations", "planned_trials"}, "EVALUATION_SUITE_FIELDS")
    if value["schema_version"] != "routing-evaluation-suite/1":
        fail("EVALUATION_SUITE_VERSION")
    identity(value["identity"])
    items = value["evaluations"]
    if not isinstance(items, list) or not items or len(items) > policy()["limits"]["max_slots"]:
        fail("EVALUATION_SUITE_LIMIT")
    case_ids, case_refs, protocol_refs = set(), set(), set()
    costs: dict[tuple[str, str], str] = {}
    total = 0
    for raw in items:
        item = validate_evaluation(raw)
        if item["identity"] != value["identity"] or item["protocol_ref"] in protocol_refs:
            fail("EVALUATION_SUITE_IDENTITY_OR_DUPLICATE")
        protocol_refs.add(item["protocol_ref"])
        for case in item["cases"]:
            if case["case_id"] in case_ids or case["case_ref"] in case_refs:
                fail("EVALUATION_SUITE_CASE_AMBIGUOUS")
            case_ids.add(case["case_id"]); case_refs.add(case["case_ref"])
        profiles = {name for pair in item["comparisons"] for name in pair.values()}
        total += len(item["cases"]) * len(profiles) * item["repetitions"]
        for cost in item["costs"]:
            key = (cost["scenario_ref"], cost["profile_id"])
            if key in costs and costs[key] != ref(cost):
                fail("EVALUATION_SUITE_COST_CONFLICT")
            costs[key] = ref(cost)
    integer(value["planned_trials"], "EVALUATION_TRIAL_LIMIT", minimum=1,
            maximum=policy()["limits"]["max_cases"])
    if value["planned_trials"] != total:
        fail("EVALUATION_SUITE_TRIAL_COUNT")
    if len({cost["cost_basis"] for item in items for cost in item["costs"]}) != 1:
        fail("EVALUATION_SUITE_COST_BASIS")
    return copy.deepcopy(dict(value))


def validate_evaluation(value: Mapping[str, Any]) -> dict[str, Any]:
    exact(dict(value), EVALUATION_FIELDS, "EVALUATION_PROTOCOL_FIELDS")
    if value["schema_version"] != "routing-evaluation/1":
        fail("EVALUATION_PROTOCOL_VERSION")
    identity(value["identity"])
    scenario(value["scenario"]); sha(value["rubric_ref"])
    integer(value["minimum_pass_bp"], "EVALUATION_QUALITY_FLOOR",
            minimum=policy()["thresholds"]["absolute_quality_floor_bp"], maximum=10000)
    integer(value["repetitions"], "EVALUATION_REPETITIONS", minimum=1, maximum=20)
    pairs = value["comparisons"]
    if not isinstance(pairs, list) or not pairs or len(pairs) > 153:
        fail("EVALUATION_COMPARISON_LIMIT")
    pair_refs = set()
    profiles = set()
    for pair in pairs:
        exact(pair, {"anchor", "challenger"}, "EVALUATION_COMPARISON_FIELDS")
        for name in pair.values():
            profile_spec(name)
            profiles.add(name)
        if pair["anchor"] == pair["challenger"] or ref(pair) in pair_refs:
            fail("EVALUATION_COMPARISON_DUPLICATE")
        pair_refs.add(ref(pair))
    if value["baseline_profile"] not in profiles or type(value["family_intervals"]) is not int \
            or value["family_intervals"] != 4 * len(pairs):
        fail("EVALUATION_COMPARISON_FAMILY")
    if not isinstance(value["cases"], list) or not value["cases"] or len(value["cases"]) > 10000:
        fail("EVALUATION_CASE_LIMIT")
    refs: list[str] = []
    for case in value["cases"]:
        exact(case, CASE_FIELDS, "EVALUATION_CASE_FIELDS")
        if ref({key: case[key] for key in CASE_FIELDS if key != "case_ref"}) != case["case_ref"]:
            fail("EVALUATION_CASE_REFERENCE")
        for key in ("prompt_ref", "gold_ref", "case_ref"):
            sha(case[key])
        identifier(case["case_id"]); identifier(case["cluster_id"])
        if type(case["clean"]) is not bool or type(case["critical"]) is not bool:
            fail("EVALUATION_CASE_BOOLEAN")
        refs.append(case["case_ref"])
    if len(refs) != len(set(refs)) or sorted(refs) != sorted(value["case_plan"]):
        fail("EVALUATION_CASE_PLAN_MISMATCH")
    if len(refs) * len(profiles) * value["repetitions"] > policy()["limits"]["max_cases"]:
        fail("EVALUATION_TRIAL_LIMIT")
    if not isinstance(value["costs"], list) or len(value["costs"]) != len(profiles):
        fail("EVALUATION_COST_PROFILES")
    for cost in value["costs"]:
        validate_cost(cost, scenario_ref=ref(value["scenario"]))
    if {cost["profile_id"] for cost in value["costs"]} != profiles \
            or len({cost["cost_basis"] for cost in value["costs"]}) != 1 \
            or value["protocol_ref"] != protocol_reference(value):
        fail("EVALUATION_COST_OR_PROTOCOL_BINDING")
    return copy.deepcopy(dict(value))


def _trace_loader(paths: list[str]):
    cache: dict[str, Mapping[str, Any]] = {}
    loaded = False
    def load(receipt_ref: str):
        nonlocal loaded
        from .budget_v4 import export_traces
        if not loaded:
            for source in paths:
                records = export_traces(Path(source))
                if set(records).intersection(cache):
                    fail("NATIVE_RECEIPT_SOURCE_AMBIGUOUS_OR_MISSING")
                cache.update(records)
                if len(cache) > policy()["limits"]["max_cases"]:
                    fail("NATIVE_TRACE_INDEX_LIMIT")
            loaded = True
        if receipt_ref not in cache:
            fail("NATIVE_RECEIPT_SOURCE_AMBIGUOUS_OR_MISSING")
        return cache[receipt_ref]
    return load


def _requirement_evidence(state: Mapping[str, Any], request: Mapping[str, Any], *,
                          evaluation: Mapping[str, Any] | None) -> dict[str, Any]:
    references = request["evidence"]["refs"]
    ready = bool(references)
    inline, independent = False, False
    for evidence_ref in references:
        source = state["sources"]["evidence_paths"].get(evidence_ref)
        if not source:
            ready = False
            continue
        record, file_ref = read_document(Path(source))
        verify_record(record, "V4 scope Evidence")
        if file_ref != evidence_ref:
            fail("V4_REQUIREMENT_EVIDENCE_HASH")
        checked = check_evidence(Path(source), Path(state["root_binding"]["repo_path"]),
                                 state["identity"]["project_id"], state["identity"]["task_id"])
        scope = set(record.get("scope_refs", []))
        expected = {"scenario:" + ref(scenario(request["scenario"]))}
        expected.add("protocol:" + evaluation["protocol_ref"] if evaluation else
                     "packet:" + request["packet_sha256"])
        if not checked.valid or record.get("source") != "parent-reviewed-v4-requirements" \
                or not expected.issubset(scope):
            ready = False
        inline |= record.get("kind") == "validation" and "inline-sufficient" in scope
        independent |= "independent-review-required" in scope
    # 中文：登记复审默认独立；内联须有当前父级验证，且不适用于评测试验。
    # English: Registered review delegation defaults to independent; inline needs explicit,
    # current parent validation and never applies to evaluation trials.
    return {"ready": ready, "independence_required": independent or not inline,
            "inline_sufficient": inline and evaluation is None, "refs": list(references)}


def load_snapshot(state: Mapping[str, Any], request: Mapping[str, Any], now: str, *,
                  cwd: str, host_session_id: str) -> dict[str, Any]:
    """中文：真实入口只在这里装配已校验快照。

    English: Production adapters construct verified snapshots only through here.
    """
    verify_root(state, cwd=cwd, host_session_id=host_session_id)
    if repo_snapshot(Path(cwd))["sha256"] != request["baseline_sha256"]:
        fail("V4_REVIEW_BASELINE_CHANGED")
    from .budget_v4 import snapshot_budget, validate_sources
    sources = validate_sources(state["sources"])
    capability, _ = read_document(Path(sources["capability"]))
    if capability.get("host_surface") != HOST_SURFACE \
            or capability.get("root_session_ref") != state["root_binding"]["host_session_ref"]:
        fail("DESKTOP_CAPABILITY_ROOT_MISMATCH")
    assert_current_window(capability, now)
    expected_identity = {key: state["identity"][key] for key in ("project_id", "repo_fingerprint")}
    bundles, publications = [], []
    evaluation = None
    if state["execution_mode"] == "EVALUATION":
        evaluations = read_evaluations(state)
        evaluation = choose_evaluation(evaluations, case_ref=request["evaluation_case_ref"])
        if request["scenario"] != evaluation["scenario"]:
            fail("EVALUATION_SCENARIO_MISMATCH")
        case = next((item for item in evaluation["cases"] if item["case_ref"] == request["evaluation_case_ref"]), None)
        if not case or case["prompt_ref"] != "sha256:" + request["message_sha256"]:
            fail("EVALUATION_CASE_PROMPT_MISMATCH")
        expected_profiles = {name for pair in evaluation["comparisons"] for name in pair.values()}
        allowed = request["constraints"]["allowed_profiles"]
        if not isinstance(allowed, list) or len(allowed) != 1 or allowed[0] not in expected_profiles:
            fail("EVALUATION_PROFILE_NOT_IN_PLAN")
        cards = {"schema_version": "verified-card-set/1", "identity": expected_identity, "origin": "evaluation",
                 "bundle_refs": [sources["evaluation_ref"]], "publication_refs": [],
                 "qualification": [], "gains": [], "costs": list({
                     ref(cost): copy.deepcopy(cost) for item in evaluations for cost in item["costs"]}.values())}
    else:
        for source in sources["card_sets"]:
            bundle, _ = read_document(Path(source["bundle"]))
            experiment, _ = read_document(Path(source["experiment"]),
                                          maximum=policy()["limits"]["max_experiment_bytes"])
            if ref(bundle) != source["bundle_ref"] or ref(experiment) != source["experiment_ref"]:
                fail("V4_CARD_SOURCE_CHANGED")
            bundle = validate_bundle(bundle, experiment, now=now, trace_loader=_trace_loader(source["trace_ledgers"]))
            publication = load_publication(Path(source["publication"]), bundle=bundle,
                                           consumer_identity=expected_identity, consumer_task_id=state["identity"]["task_id"],
                                           now=now, expected_revision=source["publication_revision"])
            if ref(publication) != source["publication_ref"]:
                fail("V4_PUBLICATION_SOURCE_CHANGED")
            bundles.append(bundle); publications.append(ref(publication))
        cards = combine_cards(bundles, publications, declared_identity=expected_identity)
    verified_evidence = _requirement_evidence(state, request, evaluation=evaluation)
    if request["evidence"] != verified_evidence:
        fail("V4_REQUIREMENT_FLAGS_NOT_VERIFIED")
    return {
        "schema_version": "routing-input/1", "identity": expected_identity, "policy_digest": policy_digest(),
        "execution_mode": state["execution_mode"], "cards": cards, "capability": capability,
        "phase_plan": copy.deepcopy(state["phase_plan"]), "budget": snapshot_budget(state), "now": now,
    }


def loader(*, cwd: str, host_session_id: str):
    return lambda state, request, now: load_snapshot(state, request, now, cwd=cwd, host_session_id=host_session_id)
