"""中文：V4 路由的有界数据契约与显式模型目录。

English: Bounded V4 routing contracts and explicit request-model catalog.
Catalog membership grants neither quality qualification nor dispatch authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from .common import canonical_json, parse_iso

POLICY_ID = "reviewer-matrix-v4"
ALGORITHM_ID = "quality-gain-routing-v1"
HOST_SURFACE = "codex-desktop"
SHA = re.compile(r"^sha256:[0-9a-f]{64}$")
HEX = re.compile(r"^[0-9a-f]{64}$")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
EFFORTS = ("low", "medium", "high")
PHASES = {"pre", "post", "repair"}
TAGS = {"mechanical", "bounded_logic", "multi_step_logic", "cross_contract", "cross_domain", "adjudication"}
VECTOR_KEYS = ("units", "attempts", "astra_attempts", "astra_high_attempts")
MODELS = {
    "g56-luna": "gpt-5.6-luna", "g56-terra": "gpt-5.6-terra", "g56-sol": "gpt-5.6-sol",
    "g6-luna": "gpt-6-luna", "g6-sol": "gpt-6-sol", "g6-astra": "gpt-6-astra",
}
IDENTITY_FIELDS = {"project_id", "repo_fingerprint"}
SCENARIO_FIELDS = {"role", "phase", "semantic", "reasoning", "risk", "tags",
                   "context_bucket", "tools_profile", "speed_mode", "prompt_sha256"}


class RoutingError(ValueError):
    """中文：固定原因码；English: errors contain no raw input or source content."""


def fail(code: str) -> None:
    raise RoutingError(code)


def ref(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def exact(value: Any, fields: set[str], code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        fail(code)
    return value


def integer(value: Any, code: str, minimum: int = 0, maximum: int = 1_000_000_000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        fail(code)
    return value


def boolean(value: Any, code: str) -> bool:
    if type(value) is not bool:
        fail(code)
    return value


def identifier(value: Any, code: str = "IDENTIFIER_INVALID") -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        fail(code)
    return value


def sha(value: Any, code: str = "SHA_REFERENCE_INVALID") -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        fail(code)
    return value


def hex_digest(value: Any, code: str = "HEX_DIGEST_INVALID") -> str:
    if not isinstance(value, str) or not HEX.fullmatch(value):
        fail(code)
    return value


def strings(value: Any, code: str, *, maximum: int = 64, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum or (not value and not allow_empty) \
            or any(not isinstance(item, str) or not item or len(item) > 160 for item in value) \
            or len(value) != len(set(value)):
        fail(code)
    return value


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _constant(_value: str) -> Any:
    fail("JSON_NONFINITE_NUMBER")


def read_document(path: Path, *, maximum: int = 1_048_576) -> tuple[dict[str, Any], str]:
    with path.open("rb") as handle:
        raw = handle.read(maximum + 1)
    if len(raw) > maximum:
        fail("DOCUMENT_TOO_LARGE")
    try:
        value = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, RoutingError):
            raise
        raise RoutingError("DOCUMENT_INVALID_JSON") from exc
    if not isinstance(value, dict):
        fail("DOCUMENT_OBJECT_REQUIRED")
    return value, "sha256:" + hashlib.sha256(raw).hexdigest()


def identity(value: Any) -> dict[str, str]:
    exact(value, IDENTITY_FIELDS, "IDENTITY_FIELDS")
    identifier(value["project_id"])
    sha(value["repo_fingerprint"])
    return dict(value)


def vector(value: Any) -> dict[str, int]:
    exact(value, set(VECTOR_KEYS), "RESOURCE_VECTOR_FIELDS")
    return {key: integer(value[key], "RESOURCE_VECTOR_VALUE") for key in VECTOR_KEYS}


def add_vectors(*values: Mapping[str, int]) -> dict[str, int]:
    return {key: sum(value[key] for value in values) for key in VECTOR_KEYS}


def fits(need: Mapping[str, int], capacity: Mapping[str, int]) -> bool:
    return all(need[key] <= capacity[key] for key in VECTOR_KEYS)


def phase_key(phase: str, review_kind: str = "initial") -> str:
    if not isinstance(phase, str) or not isinstance(review_kind, str) \
            or phase not in {"pre", "post"} or review_kind not in {"initial", "repair"} \
            or (phase == "pre" and review_kind == "repair"):
        fail("PHASE_KIND_INVALID")
    return "repair" if review_kind == "repair" else phase


def scenario(value: Any) -> dict[str, Any]:
    exact(value, SCENARIO_FIELDS, "SCENARIO_FIELDS")
    role_for(value["role"])
    if not isinstance(value["phase"], str) or value["phase"] not in PHASES:
        fail("SCENARIO_PHASE")
    for key in ("semantic", "reasoning", "risk"):
        integer(value[key], "SCENARIO_DIMENSION", maximum=3)
    if not set(strings(value["tags"], "SCENARIO_TAGS", allow_empty=False)).issubset(TAGS):
        fail("SCENARIO_TAGS")
    for key in ("context_bucket", "tools_profile", "speed_mode"):
        identifier(value[key], "SCENARIO_PROFILE")
    hex_digest(value["prompt_sha256"])
    result = copy.deepcopy(value)
    result["tags"] = sorted(result["tags"])
    return result


def assert_current_window(value: Mapping[str, Any], now: str) -> None:
    try:
        current, start, end = map(parse_iso, (now, value["created_at"], value["expires_at"]))
    except (ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
        raise RoutingError("TIME_WINDOW_INVALID") from exc
    if not start <= current < end:
        fail("SNAPSHOT_EXPIRED_OR_NOT_YET_VALID")


@lru_cache(maxsize=1)
def _policy_text() -> str:
    document, _ = read_document(Path(__file__).parent / "data" / "dispatch-policy-v4.json", maximum=65536)
    expected = {"schema_version", "policy_id", "algorithm_id", "host_surface", "cost_formula_version",
                "profiles", "reviewer_roles", "role_profiles", "thresholds", "limits", "activation"}
    exact(document, expected, "V4_POLICY_FIELDS")
    if document["schema_version"] != 2 or document["policy_id"] != POLICY_ID \
            or document["algorithm_id"] != ALGORITHM_ID or document["host_surface"] != HOST_SURFACE:
        fail("V4_POLICY_IDENTITY")
    expected_profiles = {prefix + "-" + effort for prefix in MODELS for effort in EFFORTS}
    if set(document["profiles"]) != expected_profiles:
        fail("V4_CATALOG_INCOMPLETE")
    for profile_id, spec in document["profiles"].items():
        exact(spec, {"model", "family", "generation", "effort", "lifecycle", "resource_group"},
              "V4_PROFILE_FIELDS")
        prefix, effort = profile_id.rsplit("-", 1)
        if spec["model"] != MODELS[prefix] or spec["effort"] != effort \
                or spec["generation"] != ("5.6" if prefix.startswith("g56-") else "6") \
                or spec["family"] != prefix.split("-", 1)[1] \
                or spec["resource_group"] != ("astra" if spec["family"] == "astra" else "ordinary") \
                or spec["lifecycle"] not in {"candidate", "compatibility", "evaluation"}:
            fail("V4_PROFILE_INVALID")
    exact(document["role_profiles"], {"reviewer", "worker", "explorer"}, "V4_ROLE_MATRIX")
    for profiles in document["role_profiles"].values():
        if not set(strings(profiles, "V4_ROLE_MATRIX", allow_empty=False)).issubset(expected_profiles):
            fail("V4_ROLE_MATRIX")
    roles = strings(document["reviewer_roles"], "V4_REVIEWER_ROLES", allow_empty=False)
    if len(roles) != 7 or any(not role.startswith("cp_review_") for role in roles):
        fail("V4_REVIEWER_ROLES")
    thresholds = document["thresholds"]
    exact(thresholds, {"min_independent_cases", "family_alpha_ppm", "noninferiority_margin_bp",
                      "absolute_quality_floor_bp",
                      "false_block_margin_bp", "material_quality_gain_bp", "near_best_gain_bp",
                      "material_cost_gain_bp", "balanced_cost_ratio", "balanced_latency_ratio"},
          "V4_THRESHOLD_FIELDS")
    for key, value in thresholds.items():
        if key.endswith("_ratio"):
            if not isinstance(value, list) or len(value) != 2:
                fail("V4_THRESHOLD_RATIO")
            for part in value:
                integer(part, "V4_THRESHOLD_RATIO", minimum=1, maximum=100)
        else:
            integer(value, "V4_THRESHOLD_VALUE", minimum=1, maximum=500000)
    exact(document["limits"], {"max_profiles", "max_astra_parallel", "max_slots", "max_search_states", "max_cards",
                              "max_cases", "max_repetitions", "max_ledger_records",
                              "max_document_bytes", "max_experiment_bytes", "max_ledger_bytes"}, "V4_LIMIT_FIELDS")
    for value in document["limits"].values():
        integer(value, "V4_LIMIT_VALUE", minimum=1, maximum=16_777_216)
    if document["limits"]["max_profiles"] != 18 or document["limits"]["max_astra_parallel"] != 1 or document["activation"] != {
        "production_requires_qualification": True, "synthetic_production_allowed": False,
        "legacy_policy_fallback": "explicit-before-root-initialization",
    }:
        fail("V4_ACTIVATION_CONTRACT")
    return canonical_json(document)


def policy() -> dict[str, Any]:
    return json.loads(_policy_text())


def policy_digest() -> str:
    return ref(policy())


@lru_cache(maxsize=18)
def _profile_text(profile_id: str) -> str:
    profiles = policy()["profiles"]
    if profile_id not in profiles:
        fail("PROFILE_UNKNOWN")
    return canonical_json(profiles[profile_id])


def profile_spec(profile_id: str) -> dict[str, Any]:
    if not isinstance(profile_id, str):
        fail("PROFILE_UNKNOWN")
    return json.loads(_profile_text(profile_id))


def role_for(agent_type: Any) -> str:
    if not isinstance(agent_type, str):
        fail("ROLE_UNKNOWN")
    if agent_type in policy()["reviewer_roles"]:
        return "reviewer"
    if agent_type in {"worker", "explorer"}:
        return str(agent_type)
    fail("ROLE_UNKNOWN")


def admitted(agent_type: str, execution_mode: str = "PRODUCTION") -> list[str]:
    role = role_for(agent_type)
    if execution_mode == "EVALUATION":
        if role != "reviewer":
            fail("EVALUATION_REQUIRES_REGISTERED_REVIEWER")
        return sorted(policy()["profiles"])
    if execution_mode != "PRODUCTION":
        fail("EXECUTION_MODE_INVALID")
    return list(policy()["role_profiles"][role])


def resolve_request(model: str, effort: str, agent_type: str, execution_mode: str = "PRODUCTION") -> str:
    if not isinstance(model, str) or not isinstance(effort, str) or not model or effort not in EFFORTS:
        fail("EXPLICIT_REQUEST_TUPLE_REQUIRED")
    for name in admitted(agent_type, execution_mode):
        spec = profile_spec(name)
        if (model, effort) == (spec["model"], spec["effort"]):
            return name
    fail("REQUEST_PROFILE_NOT_ALLOWED")


def resource_need(profile_id: str, reserved_units: int) -> dict[str, int]:
    spec = profile_spec(profile_id)
    astra = int(spec["resource_group"] == "astra")
    return {"units": integer(reserved_units, "RESERVATION_UNITS", minimum=1), "attempts": 1,
            "astra_attempts": astra, "astra_high_attempts": int(astra and spec["effort"] == "high")}
