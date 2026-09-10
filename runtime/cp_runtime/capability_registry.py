"""中文：AUTO 能力注册、功能级降级与仓库外偏好；从不授予受保护动作权限。

English: AUTO capability registry, per-feature degradation, and external preferences; never action authorization.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .atomic_io import native_path
from .capability_gate import _write, worktree_key
from .capability_store import CapabilityError, CapabilityStore, bounded_read, fields, integer, require, safe_path, unique_json_object
from .common import RuntimeContractError, canonical_json, require_external_state, verify_record
from .event_v3 import OwnerTokenLock

REGISTRY_SCHEMA = "capability-registry/1"
PREFERENCE_SCHEMA = "capability-preferences/1"
PREFERENCE_LIMIT = 128 * 1024
LEVELS = ("OFF", "BASIC", "ASSISTED", "FULL")
MODES = ("AUTO", "OFF")
RISKS = ("LIGHT", "STANDARD", "STRICT", "UNKNOWN")
LEGACY_MIGRATIONS = {
    "DEFAULT_OFF": ("AUTO", "BASIC"),
    "USER_OFF": ("OFF", None),
    "UNKNOWN_OFF": ("OFF", None),
    "LEGACY_ON": ("AUTO", "BASIC"),
}


def _registry_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_registry(path: Path) -> dict[str, Any]:
    """读取严格的 25 项静态注册表。 English: Load the strict static 25-entry registry."""
    try:
        value = json.loads(bounded_read(path, 512 * 1024), object_pairs_hook=unique_json_object)
    except (ValueError, UnicodeError, RecursionError, OSError):
        raise CapabilityError("REGISTRY_INVALID_JSON") from None
    fields(value, {"schema_version", "entries"})
    require(value["schema_version"] == REGISTRY_SCHEMA and isinstance(value["entries"], list), "REGISTRY_SCHEMA")
    require(len(value["entries"]) == 25, "REGISTRY_COUNT")
    expected_ids = ["C%02d" % number for number in range(1, 26)]
    required = {"capability_id", "name", "entrypoints", "default_mode", "bootstrap_level",
                "assisted_prerequisites", "full_prerequisites", "persistence_policy",
                "consent_policy", "fallback", "risk_ref", "scope", "version"}
    seen_names: set[str] = set()
    for expected_id, entry in zip(expected_ids, value["entries"]):
        fields(entry, required)
        require(entry["capability_id"] == expected_id, "REGISTRY_ID_ORDER")
        require(isinstance(entry["name"], str) and entry["name"] and entry["name"] not in seen_names, "REGISTRY_NAME")
        seen_names.add(entry["name"])
        for key in ("entrypoints", "assisted_prerequisites", "full_prerequisites", "scope"):
            require(isinstance(entry[key], list) and entry[key] and len(entry[key]) == len(set(entry[key])), "REGISTRY_LIST")
            require(all(isinstance(item, str) and 0 < len(item) <= 256 for item in entry[key]), "REGISTRY_LIST")
        require(entry["default_mode"] == "AUTO" and entry["bootstrap_level"] == "BASIC", "REGISTRY_DEFAULT")
        require(entry["version"] in {REGISTRY_SCHEMA, "onboarding/1"}, "REGISTRY_VERSION")
        for key in ("persistence_policy", "consent_policy", "fallback", "risk_ref"):
            require(isinstance(entry[key], str) and 0 < len(entry[key]) <= 256, "REGISTRY_TEXT")
    result = copy.deepcopy(value)
    result["registry_digest"] = _registry_digest(value)
    return result


def select_capability(registry: Mapping[str, Any], capability_id: str, prerequisites: Mapping[str, bool],
                      preference: Mapping[str, Any] | None = None, risk: str = "UNKNOWN",
                      statuses: Mapping[str, str] | None = None) -> dict[str, Any]:
    """按偏好和前提计算档位；风险与授权始终独立。 English: Select a level while keeping risk and authority separate."""
    require(risk in RISKS, "REGISTRY_RISK")
    entry = next((item for item in registry["entries"] if item["capability_id"] == capability_id), None)
    require(entry is not None, "REGISTRY_CAPABILITY_UNKNOWN")
    pref = dict(preference or {})
    mode = pref.get("configured_mode", entry["default_mode"])
    maximum = pref.get("max_level")
    require(mode in MODES and (maximum is None or maximum in LEVELS[1:]), "PREFERENCE_VALUE")
    available = {str(key): value is True for key, value in prerequisites.items()}
    missing_assisted = [name for name in entry["assisted_prerequisites"] if not available.get(name, False)]
    missing_full = [name for name in entry["full_prerequisites"] if not available.get(name, False)]
    if mode == "OFF":
        effective, reason = "OFF", "EXPLICIT_OFF"
    else:
        effective = "BASIC"
        if not missing_assisted:
            effective = "ASSISTED"
            if not missing_full:
                effective = "FULL"
        if maximum is not None and LEVELS.index(effective) > LEVELS.index(maximum):
            effective = maximum
            reason = "MAX_LEVEL_" + maximum
        elif effective == "FULL":
            reason = "FULL_AVAILABLE"
        elif effective == "BASIC" and not missing_assisted:
            reason = "AUTO_BASIC"
        elif missing_assisted or missing_full:
            reason = "PREREQUISITE_DEGRADED"
        else:
            reason = "AUTO_BASIC"
    state = dict(statuses or {})
    return {
        "capability_id": capability_id,
        "configured_mode": mode,
        "max_level": maximum,
        "effective_level": effective,
        "risk": risk,
        "missing_prerequisites": sorted(set(missing_assisted + missing_full)),
        "coverage": state.get("coverage", "UNKNOWN"),
        "review_status": state.get("review_status", "NOT_REQUIRED"),
        "persistence_status": state.get("persistence_status", "NOT_REQUESTED"),
        "action_status": "NOT_AUTHORIZED",
        "reason_codes": [reason],
        "registry_digest": registry["registry_digest"],
        "authorization": False,
    }


def migrate_legacy_classification(classification: str) -> dict[str, Any]:
    require(classification in LEGACY_MIGRATIONS, "LEGACY_CLASSIFICATION_UNKNOWN")
    mode, maximum = LEGACY_MIGRATIONS[classification]
    return {"configured_mode": mode, "max_level": maximum, "source": classification,
            "authorization": False, "scan_consent": False}


def read_install_migration(path: Path) -> dict[str, Any]:
    """读取安装器保存的惰性迁移计划；只接受无授权、无扫描同意的精确映射。"""
    try:
        value = json.loads(bounded_read(path, 256 * 1024), object_pairs_hook=unique_json_object)
        record = value["preference_migration"]
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, RecursionError):
        raise CapabilityError("MIGRATION_RECORD_INVALID") from None
    required = {"schema_version", "classification", "evidence", "configured_mode", "max_level",
                "authorization", "scan_consent", "gate_policy_excluded", "gate_task_excluded",
                "operation_v2_excluded", "application"}
    fields(record, required)
    expected = migrate_legacy_classification(record["classification"])
    require(record["schema_version"] == "capability-preference-migration/1"
            and record["configured_mode"] == expected["configured_mode"]
            and record["max_level"] == expected["max_level"]
            and record["authorization"] is False and record["scan_consent"] is False
            and record["gate_policy_excluded"] is True and record["gate_task_excluded"] is True
            and record["operation_v2_excluded"] is True
            and record["application"] == "PROJECT_LAZY_CAS_AFTER_IDENTITY_BINDING", "MIGRATION_RECORD_INVALID")
    return copy.deepcopy(record)


class PreferenceStore:
    """身份绑定、原子 CAS 的独立偏好文件；缺文件就是 AUTO 且不落盘。"""

    def __init__(self, profile_path: Path, repo_path: Path):
        self.store = CapabilityStore(profile_path, repo_path)
        self.root = safe_path(profile_path.parent / "capability-preferences" / worktree_key(repo_path))
        require_external_state(self.root, repo_path)
        self.path = self.root / "preferences.json"

    def _validate(self, value: dict[str, Any]) -> None:
        fields(value, {"schema_version", "revision", "identity", "preferences", "integrity"})
        require(value["schema_version"] == PREFERENCE_SCHEMA and value["identity"] == self.store.identity, "PREFERENCE_SCHEMA")
        integer(value["revision"], 2**63 - 1)
        require(isinstance(value["preferences"], dict) and len(value["preferences"]) <= 25, "PREFERENCE_SCHEMA")
        for capability_id, preference in value["preferences"].items():
            require(capability_id in {"C%02d" % number for number in range(1, 26)}, "PREFERENCE_CAPABILITY")
            fields(preference, {"configured_mode", "max_level", "source"})
            require(preference["configured_mode"] in MODES, "PREFERENCE_VALUE")
            require(preference["max_level"] is None or preference["max_level"] in LEVELS[1:], "PREFERENCE_VALUE")
            require(preference["source"] in {"USER", *LEGACY_MIGRATIONS}, "PREFERENCE_SOURCE")

    def read(self) -> dict[str, Any] | None:
        self.store._guard()
        if not native_path(self.path).exists():
            return None
        try:
            value = json.loads(bounded_read(native_path(self.path), PREFERENCE_LIMIT), object_pairs_hook=unique_json_object)
            fields(value.get("integrity"), {"algorithm", "sha256"})
            verify_record(value, "CapabilityPreferences")
            self._validate(value)
        except (ValueError, UnicodeError, RecursionError, RuntimeContractError, OSError):
            raise CapabilityError("PREFERENCE_RECORD_INVALID") from None
        self.store._guard()
        return value

    def preference(self, capability_id: str) -> dict[str, Any] | None:
        current = self.read()
        return copy.deepcopy(current["preferences"].get(capability_id)) if current else None

    def set_preference(self, capability_id: str, configured_mode: str, max_level: str | None,
                       expected_revision: int | None, source: str = "USER") -> dict[str, Any]:
        require(capability_id in {"C%02d" % number for number in range(1, 26)}, "PREFERENCE_CAPABILITY")
        require(configured_mode in MODES and (max_level is None or max_level in LEVELS[1:]), "PREFERENCE_VALUE")
        require(source in {"USER", *LEGACY_MIGRATIONS}, "PREFERENCE_SOURCE")
        if expected_revision is not None:
            integer(expected_revision, 2**63 - 2)
        with OwnerTokenLock(self.path):
            current = self.read()
            require((current is None and expected_revision is None)
                    or (current is not None and current["revision"] == expected_revision), "PREFERENCE_REVISION_CONFLICT")
            preference = {"configured_mode": configured_mode, "max_level": max_level, "source": source}
            if current is not None and current["preferences"].get(capability_id) == preference:
                return current
            preferences = copy.deepcopy(current["preferences"] if current else {})
            preferences[capability_id] = preference
            value = {"schema_version": PREFERENCE_SCHEMA,
                     "revision": current["revision"] + 1 if current else 0,
                     "identity": copy.deepcopy(self.store.identity), "preferences": preferences}
            result = _write(self.path, value, PREFERENCE_LIMIT)
            self._validate(result)
            self.store._guard()
            return result
