"""中文：按摘要读取不可变模型目录，只连接受支持的决策算法。
English: Resolve immutable profile catalogs by digest and supported decision algorithm.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .routing_contract import exact, fail, integer, sha

LEGACY_ID = "desktop-g6-deterministic-v1"
LEGACY_SHA = "1593b5136a133b62b6a8973f1c5a29b798189a3ef2fe424a5aaed0fc87cdf70f"
LEGACY = "sha256:" + LEGACY_SHA
DATA = Path(__file__).parent / "data"
EFFORTS = ("low", "medium", "high")
ROLES = {"worker", "reviewer", "explorer"}
KINDS = {"lookup", "extraction", "mechanical", "ordinary", "unknown", "cross_domain_adjudication"}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail("CATALOG_DUPLICATE_FIELD")
        result[key] = value
    return result


def _key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", value):
        fail("CATALOG_IDENTIFIER")
    return value


@dataclass(frozen=True)
class Catalog:
    policy_id: str
    digest: str
    profiles: dict[str, dict]
    defaults: dict[str, str]
    role_order: dict[str, list[str]]
    family_rank: dict[str, int]
    limits: dict[str, int]

    def lookup(self, model: str, effort: str) -> str | None:
        return next(
            (
                key
                for key, item in self.profiles.items()
                if (item["model"], item["effort"]) == (model, effort)
            ),
            None,
        )

    def fit(self, profile: str, preferred: str, role: str) -> tuple:
        other, desired = self.profiles[profile], self.profiles[preferred]
        same_family = other["family"] == desired["family"]
        return (
            0 if same_family else 1,
            self.role_order[role].index(other["family"]) if not same_family else 0,
            abs(EFFORTS.index(other["effort"]) - EFFORTS.index(desired["effort"])),
        )

    def choose(self, candidates: list[str], preferred: str, role: str, latency: dict) -> str:
        tier = min(self.fit(p, preferred, role) for p in candidates)
        qualified = [p for p in candidates if self.fit(p, preferred, role) == tier]
        units = min(self.profiles[p]["planning_units"] for p in qualified)
        tied = [p for p in qualified if self.profiles[p]["planning_units"] == units]
        comparable = all(p in latency for p in tied)
        return min(tied, key=lambda p: (latency[p] if comparable else 0, self.profiles[p]["priority"]))


def _load(raw: bytes, row: dict) -> Catalog:
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if digest != "sha256:" + row["sha256"]:
        fail("CATALOG_DIGEST_MISMATCH")
    data = exact(
        json.loads(raw, object_pairs_hook=_unique),
        {
            "schema_version",
            "policy_id",
            "algorithm",
            "budget_policy_digest",
            "efforts",
            "concurrency_limits",
            "defaults",
            "role_order",
            "family_rank",
            "models",
        },
        "CATALOG_FIELDS",
    )
    if (
        data["schema_version"] != "desktop-model-catalog/1"
        or data["policy_id"] != row["policy_id"]
        or data["algorithm"] != row["algorithm"]
        or data["algorithm"] != "role-cost-v2"
        or data["budget_policy_digest"] != LEGACY
        or data["efforts"] != list(EFFORTS)
    ):
        fail("CATALOG_ALGORITHM")
    ranks = data["family_rank"]
    limits = data["concurrency_limits"]
    if (
        not isinstance(ranks, dict)
        or not ranks
        or len(ranks) > 32
        or not isinstance(limits, dict)
        or len(limits) > 16
        or "shared" in limits
    ):
        fail("CATALOG_LIMITS")
    for key, value in ranks.items():
        _key(key)
        integer(value, "CATALOG_FAMILY_RANK", maximum=32)
    for key, value in limits.items():
        _key(key)
        integer(value, "CATALOG_CONCURRENCY", minimum=1, maximum=32)
    roles = exact(data["role_order"], ROLES, "CATALOG_ROLE_ORDER")
    for order in roles.values():
        if not isinstance(order, list) or len(order) != len(ranks) or set(order) != set(ranks):
            fail("CATALOG_ROLE_ORDER")
    models = data["models"]
    if not isinstance(models, list) or not 1 <= len(models) <= 64:
        fail("CATALOG_MODEL_COUNT")
    profiles, tuples, priorities, model_ids = {}, set(), set(), set()
    for item in models:
        exact(
            item,
            {"id", "model", "family", "concurrency_group", "stage", "priority", "units"},
            "CATALOG_MODEL",
        )
        name = _key(item["model"])
        ident = _key(item["id"])
        priority = integer(item["priority"], "CATALOG_PRIORITY", maximum=255)
        if (
            priority in priorities
            or ident in model_ids
            or item["family"] not in ranks
            or item["concurrency_group"] not in {"shared", *limits}
            or item["stage"] not in {"approved", "pilot", "shadow"}
            or not isinstance(item["units"], dict)
            or not item["units"]
            or set(item["units"]) - set(EFFORTS)
        ):
            fail("CATALOG_MODEL_CONFLICT")
        priorities.add(priority)
        model_ids.add(ident)
        for effort, cost in item["units"].items():
            pid = ident + "-" + effort
            if (name, effort) in tuples or pid in profiles:
                fail("CATALOG_AMBIGUOUS_TUPLE")
            tuples.add((name, effort))
            profiles[pid] = {
                "profile_id": pid,
                "model": name,
                "effort": effort,
                "family": item["family"],
                "planning_units": integer(cost, "CATALOG_PLANNING_UNITS", minimum=1, maximum=1024),
                "group": item["concurrency_group"],
                "stage": item["stage"],
                "priority": priority * len(EFFORTS) + EFFORTS.index(effort),
            }
    defaults = exact(data["defaults"], KINDS, "CATALOG_DEFAULTS")
    if any(p not in profiles or profiles[p]["stage"] != "approved" for p in defaults.values()):
        fail("CATALOG_DEFAULT_PROFILE")
    return Catalog(data["policy_id"], digest, profiles, defaults, roles, ranks, limits)


@lru_cache(maxsize=1)
def entries() -> tuple[dict, ...]:
    value = json.loads((DATA / "desktop-policy-readers.json").read_bytes(), object_pairs_hook=_unique)
    exact(value, {"schema_version", "policies"}, "CATALOG_INDEX")
    if (
        value["schema_version"] != "desktop-policy-readers/1"
        or not isinstance(value["policies"], list)
        or len(value["policies"]) > 32
    ):
        fail("CATALOG_INDEX")
    ids, digests = {LEGACY_ID}, {LEGACY_SHA}
    for entry in value["policies"]:
        exact(entry, {"policy_id", "algorithm", "file", "sha256"}, "CATALOG_DESCRIPTOR")
        sha("sha256:" + entry["sha256"])
        _key(entry["policy_id"])
        if (
            entry["policy_id"] in ids
            or entry["sha256"] in digests
            or entry["algorithm"] != "role-cost-v2"
            or not re.fullmatch(r"desktop-model-catalog-[a-z0-9-]+\.json", entry["file"])
        ):
            fail("CATALOG_DESCRIPTOR_CONFLICT")
        ids.add(entry["policy_id"])
        digests.add(entry["sha256"])
    return tuple(value["policies"])


@lru_cache(maxsize=32)
def for_digest(digest: str | None) -> Catalog | None:
    if digest is None or digest == LEGACY:
        return None
    record = next((r for r in entries() if "sha256:" + r["sha256"] == digest), None)
    if record is None:
        fail("G6_ROOT_POLICY")
    return _load((DATA / record["file"]).read_bytes(), record)


def digest_for(policy_id: str) -> str:
    if policy_id == LEGACY_ID:
        return LEGACY
    for entry in entries():
        if entry["policy_id"] == policy_id:
            digest = "sha256:" + entry["sha256"]
            for_digest(digest)
            return digest
    fail("CATALOG_POLICY_UNKNOWN")


def policy_id(digest: str) -> str:
    catalog = for_digest(digest)
    return catalog.policy_id if catalog else LEGACY_ID


def reader_ids() -> tuple[str, ...]:
    return (LEGACY_ID, *(r["policy_id"] for r in entries()))


def reader_profiles(legacy_profiles) -> list[str]:
    names = set(legacy_profiles)
    for row in entries():
        names.update(for_digest("sha256:" + row["sha256"]).profiles)
    return sorted(names)
