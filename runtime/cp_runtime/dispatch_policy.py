"""中文：冻结的派发策略与从 Luna 起算的确定性证据评分。

English: Versioned dispatch contracts and deterministic Luna-first scoring.
Proxy units govern allocation; they do not rank model quality or claim prices.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

LEGACY_POLICY_ID = "four-tier-v1"
PREVIOUS_POLICY_ID = "reviewer-matrix-v2"
CURRENT_POLICY_ID = "reviewer-matrix-v3"
V4_POLICY_ID = "reviewer-matrix-v4"
POLICY_FILES = {
    LEGACY_POLICY_ID: "dispatch-policy-v1.json",
    PREVIOUS_POLICY_ID: "dispatch-policy-v2.json",
    CURRENT_POLICY_ID: "dispatch-policy-v3.json",
    V4_POLICY_ID: "dispatch-policy-v4.json",
}
CONTEXT_FIELDS = {"project_id", "task_id", "repo_fingerprint", "packet_sha256", "baseline_sha256"}
ATOM_FIELDS = {"evidence_ref", "correlation_ref", "dimension", "level"}
PROOF_FIELDS = {"evidence_ref", "context", "status", "source", "prior_result_ref", "prior_attempt_ref"}
SHA_REF = re.compile(r"^sha256:[a-f0-9]{64}$")
SHA_HEX = re.compile(r"^[a-f0-9]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_DELEGATION_TOOL_ALIASES = {
    prefix + name: name
    for name in ("spawn_agent", "followup_task", "send_message", "send_input", "resume_agent")
    for prefix in ("collaboration.", "collaboration")
}


def delegation_tool_name(value: Any) -> str:
    """中文：只归一化桌面委派工具的明确命名形式，不按后缀识别其他工具。

    English: Normalize explicit Desktop delegation names, never arbitrary suffixes.
    """
    name = str(value or "").lower()
    return _DELEGATION_TOOL_ALIASES.get(name, name)


class DispatchPolicyError(ValueError):
    """中文：派发策略拒绝；English: fail-closed dispatch contract error."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DispatchPolicyError("POLICY_DUPLICATE_KEY")
        result[key] = value
    return result


@lru_cache(maxsize=4)
def _policy_bytes(policy_id: str) -> bytes:
    if policy_id == V4_POLICY_ID:
        from .routing_contract import policy as v4_policy
        return canonical_json(v4_policy()).encode("utf-8")
    filename = POLICY_FILES.get(policy_id)
    if filename is None:
        raise DispatchPolicyError("POLICY_VERSION_UNSUPPORTED")
    with (Path(__file__).parent / "data" / filename).open("rb") as handle:
        raw = handle.read(65537)
    if len(raw) > 65536:
        raise DispatchPolicyError("POLICY_RESOURCE_TOO_LARGE")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError) as exc:
        raise DispatchPolicyError("POLICY_RESOURCE_INVALID") from exc
    if value.get("schema_version") != 1 or value.get("policy_id") != policy_id:
        raise DispatchPolicyError("POLICY_RESOURCE_IDENTITY")
    profiles = value.get("profiles", {})
    costs: set[int] = set()
    for name, spec in profiles.items():
        if set(spec) != {"family", "model", "effort", "units"}:
            raise DispatchPolicyError("POLICY_PROFILE_FIELDS")
        family, effort, units = spec["family"], spec["effort"], spec["units"]
        model = "gpt-6-astra" if family == "astra" else "gpt-5.6-" + str(family)
        if family not in {"luna", "terra", "sol", "astra"} or effort not in {"low", "medium", "high"} \
                or name != family + "-" + effort or spec["model"] != model \
                or type(units) is not int or not 1 <= units <= 1000 or units in costs:
            raise DispatchPolicyError("POLICY_PROFILE_INVALID_OR_AMBIGUOUS")
        costs.add(units)
    if not profiles or set(value.get("role_profiles", {})) != {"reviewer", "worker", "explorer"}:
        raise DispatchPolicyError("POLICY_ROLE_MATRIX_INVALID")
    for allowed in value["role_profiles"].values():
        if not allowed or len(allowed) != len(set(allowed)) or not set(allowed).issubset(profiles):
            raise DispatchPolicyError("POLICY_ROLE_MATRIX_INVALID")
    if len(value.get("reviewer_roles", [])) != len(set(value.get("reviewer_roles", []))):
        raise DispatchPolicyError("POLICY_REVIEWER_DUPLICATE")
    pair_ids: set[str] = set()
    for pair in value.get("comparison_pairs", []):
        if set(pair) != {"id", "profiles"} or pair["id"] in pair_ids \
                or len(pair["profiles"]) != 2 or len(set(pair["profiles"])) != 2 \
                or not set(pair["profiles"]).issubset(profiles):
            raise DispatchPolicyError("POLICY_COMPARISON_INVALID")
        pair_ids.add(pair["id"])
    return canonical_json(value).encode("utf-8")


def policy(policy_id: str = CURRENT_POLICY_ID, expected_digest: str = "") -> dict[str, Any]:
    """中文：每次返回独立副本；English: do not expose mutable cached policy state."""
    raw = _policy_bytes(policy_id)
    if expected_digest and expected_digest != "sha256:" + hashlib.sha256(raw).hexdigest():
        raise DispatchPolicyError("POLICY_DIGEST_MISMATCH")
    return json.loads(raw)


def policy_digest(policy_id: str = CURRENT_POLICY_ID) -> str:
    return "sha256:" + hashlib.sha256(_policy_bytes(policy_id)).hexdigest()


def profile_spec(profile: str, policy_id: str = CURRENT_POLICY_ID) -> dict[str, Any]:
    try:
        return policy(policy_id)["profiles"][profile]
    except (KeyError, TypeError) as exc:
        raise DispatchPolicyError("PROFILE_UNKNOWN") from exc


def profile_weights(policy_id: str = CURRENT_POLICY_ID) -> dict[str, int]:
    if policy_id == V4_POLICY_ID:
        raise DispatchPolicyError("V4_COSTS_REQUIRE_SCENARIO_CARDS")
    return {name: item["units"] for name, item in policy(policy_id)["profiles"].items()}


def role_for(agent_type: str, *, allow_generic_reviewer: bool = False,
             policy_id: str = CURRENT_POLICY_ID) -> str:
    if not isinstance(agent_type, str):
        raise DispatchPolicyError("ROLE_UNKNOWN")
    role = agent_type.strip().lower()
    if role in policy(policy_id)["reviewer_roles"]:
        return "reviewer"
    if allow_generic_reviewer and role in {"reviewer", "review"}:
        return "reviewer"
    if role in {"worker", "explorer"}:
        return role
    if role in {"", "default"}:
        return "worker"
    raise DispatchPolicyError("ROLE_UNKNOWN")


def allowed_profiles(agent_type: str, policy_id: str = CURRENT_POLICY_ID, *,
                     allow_generic_reviewer: bool = False) -> list[str]:
    role = role_for(agent_type, allow_generic_reviewer=allow_generic_reviewer, policy_id=policy_id)
    return list(policy(policy_id)["role_profiles"][role])


def requirement_profiles(agent_type: str, requested: Iterable[str] | None = None,
                         policy_id: str = CURRENT_POLICY_ID, *, allow_generic_reviewer: bool = False) -> list[str]:
    allowed = allowed_profiles(agent_type, policy_id, allow_generic_reviewer=allow_generic_reviewer)
    selected = allowed if requested is None else list(requested)
    if not selected or len(selected) > len(allowed) or any(not isinstance(item, str) for item in selected) \
            or len(selected) != len(set(selected)) or not set(selected).issubset(allowed):
        raise DispatchPolicyError("REQUIREMENT_PROFILES_INVALID")
    return sorted(selected)


def is_premium(profile: str, policy_id: str = CURRENT_POLICY_ID) -> bool:
    if policy_id == V4_POLICY_ID:
        return profile_spec(profile, policy_id)["resource_group"] == "astra"
    return profile_spec(profile, policy_id)["family"] in {"sol", "astra"}


def resolve_request(model: str, effort: str, default_profile: str, agent_type: str,
                    policy_id: str = CURRENT_POLICY_ID) -> tuple[str, str]:
    """中文：只解释请求，不推断执行型号；English: resolve a request, never host identity."""
    if policy_id == V4_POLICY_ID:
        from .routing_contract import resolve_request as v4_resolve
        return v4_resolve(model, effort, agent_type), "explicit-request"
    if not isinstance(model, str) or not isinstance(effort, str):
        raise DispatchPolicyError("REQUEST_INVALID")
    model, effort = model.strip().lower(), effort.strip().lower()
    allowed = allowed_profiles(agent_type, policy_id)
    if not model and not effort:
        if default_profile not in allowed or is_premium(default_profile, policy_id):
            raise DispatchPolicyError("IMPLICIT_PREMIUM_OR_INVALID_DEFAULT")
        return default_profile, "policy-default"
    if not model or not effort:
        raise DispatchPolicyError("REQUEST_TUPLE_INCOMPLETE")
    for name in allowed:
        spec = profile_spec(name, policy_id)
        if (spec["model"], spec["effort"]) == (model, effort):
            return name, "explicit-request"
    raise DispatchPolicyError("REQUEST_PROFILE_NOT_ALLOWED")


def legacy_minimum_profiles(minimum: str) -> list[str]:
    order = policy(LEGACY_POLICY_ID)["legacy_order"]
    if minimum not in order:
        raise DispatchPolicyError("LEGACY_MINIMUM_PROFILE_UNKNOWN")
    return order[order.index(minimum):]


def validate_context(context: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(context, Mapping) or set(context) != CONTEXT_FIELDS:
        raise DispatchPolicyError("SCORE_CONTEXT_FIELDS")
    result = dict(context)
    if any(not isinstance(value, str) for value in result.values()) \
            or any(not IDENTIFIER.fullmatch(result[key]) for key in ("project_id", "task_id")) \
            or not SHA_REF.fullmatch(result["repo_fingerprint"]) \
            or any(not SHA_HEX.fullmatch(result[key]) for key in ("packet_sha256", "baseline_sha256")):
        raise DispatchPolicyError("SCORE_CONTEXT_INVALID")
    return result


def _score_review(*, select_awards: Any, agent_type: str, context: Mapping[str, Any], reviewer_budget: str = "economy",
                 evidence_items: Iterable[Mapping[str, str]] = (), proofs: Mapping[str, Any] | None = None,
                 requirements: Iterable[str] | None = None, policy_id: str = CURRENT_POLICY_ID) -> dict[str, Any]:
    """中文：从已核验来源快照重算，不接收提交的总分。

    English: Recompute from verified provenance snapshots. Issuers must build the
    proof index with resolve_evidence; replay verifies frozen snapshots, not live files.
    """
    contract = policy(policy_id)
    if "scoring" not in contract:
        raise DispatchPolicyError("LEGACY_POLICY_HAS_NO_SCORECARD")
    config = contract["scoring"]
    bound_context = validate_context(context)
    if not isinstance(agent_type, str) or not agent_type.strip() or agent_type.strip().lower() == "default":
        raise DispatchPolicyError("SCORE_ROLE_REQUIRED")
    candidates = requirement_profiles(agent_type, requirements, policy_id)
    if reviewer_budget not in config["mode_points"]:
        raise DispatchPolicyError("REVIEW_BUDGET_UNKNOWN")
    items = list(evidence_items)
    if len(items) > config["max_evidence_items"]:
        raise DispatchPolicyError("SCORE_EVIDENCE_LIMIT")
    atoms: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, Mapping) or set(item) != ATOM_FIELDS or any(not isinstance(v, str) for v in item.values()):
            raise DispatchPolicyError("SCORE_ATOM_FIELDS")
        if not SHA_REF.fullmatch(item["evidence_ref"]) or not SHA_REF.fullmatch(item["correlation_ref"]) \
                or item["dimension"] not in config["dimensions"] \
                or item["level"] not in config["dimensions"][item["dimension"]]:
            raise DispatchPolicyError("SCORE_ATOM_INVALID")
        atoms.append(dict(item))
    # 中文：完全重复先折叠；English: exact duplicates have no effect, including ordering.
    atoms = [json.loads(item) for item in sorted({canonical_json(atom) for atom in atoms})]
    proof_index: dict[str, Any] = {}
    if proofs is not None and not isinstance(proofs, Mapping):
        raise DispatchPolicyError("SCORE_PROOF_FIELDS")
    for ref, proof in (proofs or {}).items():
        if ref not in {atom["evidence_ref"] for atom in atoms}:
            raise DispatchPolicyError("SCORE_UNREFERENCED_PROOF")
        if not isinstance(proof, Mapping) or set(proof) != PROOF_FIELDS or proof["evidence_ref"] != ref:
            raise DispatchPolicyError("SCORE_PROOF_FIELDS")
        validate_context(proof["context"])
        if proof["status"] not in {"valid", "stale", "unknown", "failed", "blocked"} \
                or proof["source"] != "verified-evidence-record" \
                or any(proof[key] and not SHA_REF.fullmatch(proof[key]) for key in ("prior_result_ref", "prior_attempt_ref")):
            raise DispatchPolicyError("SCORE_PROOF_INVALID")
        proof_index[ref] = dict(proof)
    parent = list(range(len(atoms)))
    reasons: dict[int, str] = {}
    for index, atom in enumerate(atoms):
        proof = proof_index.get(atom["evidence_ref"])
        if not proof:
            reasons[index] = "EVIDENCE_MISSING"
        elif proof["status"] != "valid":
            reasons[index] = "EVIDENCE_NOT_CURRENT_VALID"
        elif proof["context"] != bound_context:
            reasons[index] = "EVIDENCE_CONTEXT_MISMATCH"
        elif atom["dimension"] == "prior_inconclusive" and not (proof["prior_result_ref"] and proof["prior_attempt_ref"]):
            reasons[index] = "PRIOR_RESULT_BINDING_MISSING"

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    # 中文：同证据或同根因的传递闭包只计一次；English: transitive groups prevent alias splitting.
    seen: dict[tuple[str, str], int] = {}
    for index, atom in enumerate(atoms):
        if index in reasons:
            continue
        for key in ("evidence_ref", "correlation_ref"):
            identity = (key, atom[key])
            if identity in seen:
                parent[find(index)] = find(seen[identity])
            else:
                seen[identity] = index
    priorities = {name: index for index, name in enumerate(config["dimension_priority"])}

    def award_key(atom: Mapping[str, str]) -> tuple[Any, ...]:
        return (-config["dimensions"][atom["dimension"]][atom["level"]], priorities[atom["dimension"]],
                atom["level"], atom["evidence_ref"], atom["correlation_ref"])

    groups: dict[int, list[dict[str, str]]] = {}
    exclusions: list[dict[str, Any]] = []
    for index, atom in enumerate(atoms):
        reason = reasons.get(index, "")
        if reason:
            exclusions.append({**atom, "reason": reason, "points": 0})
        else:
            groups.setdefault(find(index), []).append(atom)
    awards, selection_exclusions = select_awards(groups, config, award_key)
    exclusions.extend(selection_exclusions)
    earned = min(config["max_units"], config["base_units"] + config["mode_points"][reviewer_budget]
                 + sum(item["points"] for item in awards))
    affordable = [name for name in candidates if contract["profiles"][name]["units"] <= earned]
    if not affordable:
        raise DispatchPolicyError("SCORE_BELOW_QUALITY_REQUIREMENT")
    selected = max(affordable, key=lambda name: contract["profiles"][name]["units"])
    return {
        "schema_version": "selection-scorecard/1", "policy_id": policy_id,
        "policy_digest": policy_digest(policy_id), "formula_version": config["formula_version"],
        "agent_type": agent_type.strip().lower(), "context": bound_context,
        "reviewer_budget": reviewer_budget, "requirement_profiles": candidates,
        "evidence_items": atoms, "proofs": proof_index,
        "awards": sorted(awards, key=canonical_json), "exclusions": sorted(exclusions, key=canonical_json),
        "base_units": config["base_units"], "mode_points": config["mode_points"][reviewer_budget],
        "earned_budget": earned, "approved_profile": selected,
        "cost_basis_units": contract["profiles"][selected]["units"],
    }


def _select_awards_v1(groups: Mapping[int, list[dict[str, str]]], config: Mapping[str, Any],
                      award_key: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """中文：保留旧贪心选择以重放 luna-evidence-v1。

    English: Frozen greedy selection for luna-evidence-v1 replay."""
    exclusions: list[dict[str, Any]] = []
    surviving: list[dict[str, str]] = []
    for group in groups.values():
        ranked = sorted(group, key=award_key)
        surviving.append(ranked[0])
        exclusions.extend({**atom, "reason": "CORRELATED_EVIDENCE", "points": 0} for atom in ranked[1:])
    awards: list[dict[str, Any]] = []
    dimensions: set[str] = set()
    for atom in sorted(surviving, key=award_key):
        if atom["dimension"] in dimensions:
            exclusions.append({**atom, "reason": "DIMENSION_CAP", "points": 0})
        else:
            dimensions.add(atom["dimension"])
            awards.append({**atom, "points": config["dimensions"][atom["dimension"]][atom["level"]]})
    return awards, exclusions


def _select_awards_v2(groups: Mapping[int, list[dict[str, str]]], config: Mapping[str, Any],
                      award_key: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """中文：联合求最优解，每个关联组和维度至多取一项，最多 32 个掩码。

    English: Joint optimum: one atom per connected group and per dimension, at most 32 masks."""
    bits = {name: 1 << index for index, name in enumerate(config["dimension_priority"])}

    def solution_key(solution: tuple[int, tuple[dict[str, str], ...]]) -> tuple[Any, ...]:
        # 中文：比较完整规范解，避免局部选择依赖输入顺序。
        # English: Compare the whole canonical solution, never an input-order-dependent local winner.
        return (-solution[0], tuple(award_key(atom) for atom in solution[1]))

    states: dict[int, tuple[int, tuple[dict[str, str], ...]]] = {0: (0, ())}
    for group in groups.values():
        next_states = dict(states)  # 中文：跳过此组始终可行。 English: Skipping this group is always feasible.
        for mask, (total, selected) in states.items():
            for atom in group:
                bit = bits[atom["dimension"]]
                if mask & bit:
                    continue
                candidate = (total + config["dimensions"][atom["dimension"]][atom["level"]],
                             tuple(sorted((*selected, atom), key=award_key)))
                target = mask | bit
                if target not in next_states or solution_key(candidate) < solution_key(next_states[target]):
                    next_states[target] = candidate
        states = next_states
    _total, selected = min(states.values(), key=solution_key)
    selected_keys = {canonical_json(atom) for atom in selected}
    awards = [{**atom, "points": config["dimensions"][atom["dimension"]][atom["level"]]} for atom in selected]
    exclusions = []
    for group in groups.values():
        occupied = any(canonical_json(atom) in selected_keys for atom in group)
        for atom in group:
            if canonical_json(atom) not in selected_keys:
                exclusions.append({**atom, "reason": "CORRELATED_EVIDENCE" if occupied else "DIMENSION_CAP", "points": 0})
    return awards, exclusions


def _score_review_v1(**kwargs: Any) -> dict[str, Any]:
    return _score_review(select_awards=_select_awards_v1, **kwargs)


def _score_review_v2(**kwargs: Any) -> dict[str, Any]:
    return _score_review(select_awards=_select_awards_v2, **kwargs)


def score_review(*, agent_type: str, context: Mapping[str, Any], reviewer_budget: str = "economy",
                 evidence_items: Iterable[Mapping[str, str]] = (), proofs: Mapping[str, Any] | None = None,
                 requirements: Iterable[str] | None = None, policy_id: str = CURRENT_POLICY_ID) -> dict[str, Any]:
    """中文：按公式版本选解释器，未来算法不得改写旧样本含义。

    English: Dispatch frozen evaluators by version instead of reinterpreting old scorecards.
    """
    formula = policy(policy_id).get("scoring", {}).get("formula_version")
    evaluator = {"luna-evidence-v1": _score_review_v1, "luna-evidence-v2": _score_review_v2}.get(formula)
    if evaluator is None:
        raise DispatchPolicyError("SCORE_FORMULA_UNSUPPORTED")
    return evaluator(agent_type=agent_type, context=context, reviewer_budget=reviewer_budget,
                     evidence_items=evidence_items, proofs=proofs, requirements=requirements, policy_id=policy_id)


def validate_scorecard(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        policy(value["policy_id"], value["policy_digest"])
        computed = score_review(agent_type=value["agent_type"], context=value["context"],
                                reviewer_budget=value["reviewer_budget"], evidence_items=value["evidence_items"],
                                proofs=value["proofs"], requirements=value["requirement_profiles"],
                                policy_id=value["policy_id"])
    except (KeyError, TypeError) as exc:
        raise DispatchPolicyError("SCORECARD_FIELDS") from exc
    if canonical_json(computed) != canonical_json(value):
        raise DispatchPolicyError("SCORECARD_RECOMPUTATION_MISMATCH")
    return computed


def resolve_evidence(paths: Mapping[str, str], context: Mapping[str, str], repo_path: Path) -> dict[str, Any]:
    """中文：复用 Evidence 完整性/仓库快照，单次读仓库，不持久化正文。

    English: Resolve bounded Evidence files into minimal provenance; snapshot the repo once.
    """
    from .common import repo_snapshot, verify_record
    from .evidence import SCHEMA as EVIDENCE_SCHEMA
    from .event_v3 import stable_repo_fingerprint

    expected = validate_context(context)
    if len(paths) > policy()["scoring"]["max_evidence_items"]:
        raise DispatchPolicyError("SCORE_EVIDENCE_LIMIT")
    snapshot = repo_snapshot(repo_path)
    current_fingerprint = stable_repo_fingerprint(str(repo_path))
    if current_fingerprint != expected["repo_fingerprint"] or snapshot["sha256"] != expected["baseline_sha256"]:
        raise DispatchPolicyError("SCORE_BASELINE_STALE")
    result: dict[str, Any] = {}
    for ref, filename in paths.items():
        if not SHA_REF.fullmatch(ref):
            raise DispatchPolicyError("SCORE_EVIDENCE_REF_INVALID")
        path = Path(filename)
        if not path.is_file():
            continue
        if path.stat().st_size > 262144:
            raise DispatchPolicyError("SCORE_EVIDENCE_TOO_LARGE")
        with path.open("rb") as handle:
            raw = handle.read(262145)
        if len(raw) > 262144:
            raise DispatchPolicyError("SCORE_EVIDENCE_TOO_LARGE")
        if "sha256:" + hashlib.sha256(raw).hexdigest() != ref:
            raise DispatchPolicyError("SCORE_EVIDENCE_HASH_MISMATCH")
        # 中文：校验刚才哈希的同一份字节，避免二次读取窗口。
        # English: validate the exact bytes hashed above, without a second file read.
        record = json.loads(raw, object_pairs_hook=_unique_object)
        if not isinstance(record, dict) or record.get("schema_version") != EVIDENCE_SCHEMA:
            raise DispatchPolicyError("SCORE_EVIDENCE_SCHEMA")
        verify_record(record, "Score Evidence")
        baseline = record.get("baseline", {})
        refs = record.get("scope_refs", [])
        same_repo = Path(baseline.get("repo_path", "")).resolve() == Path(snapshot["repo_path"]).resolve()
        proof_context = dict(expected)
        proof_context.update(project_id=record["project_id"], task_id=record["task_id"],
                             baseline_sha256=baseline.get("sha256", "0" * 64))
        valid_packet = "packet:" + expected["packet_sha256"] in refs
        if not valid_packet:
            proof_context["packet_sha256"] = "0" * 64
        status = record.get("status", "unknown")
        if not same_repo or baseline.get("sha256") != snapshot["sha256"]:
            status = "stale"
        result[ref] = {
            "evidence_ref": ref, "context": proof_context, "status": status,
            "source": "verified-evidence-record",
            "prior_result_ref": next((item[7:] for item in refs if item.startswith("result:sha256:")), ""),
            "prior_attempt_ref": next((item[8:] for item in refs if item.startswith("attempt:sha256:")), ""),
        }
    return result
