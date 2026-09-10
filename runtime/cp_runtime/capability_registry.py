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
CANONICAL_NAMES = [
    "backend-engineering", "ai-engineering", "frontend-engineering", "data-middleware-infrastructure",
    "log-observability-analysis", "engineering-quality-delivery", "multi-agent-independent-review",
    "technical-document-writing", "long-running-task-memory", "controlled-evolution-governance",
    "project-identity-profile", "capability-index", "controlled-write-operation", "delegation-budget",
    "checkpoint-memory", "hooks-observation-queue", "feedback-finalization", "controlled-evolution",
    "independent-reviewers", "installer-lifecycle", "codex-compatibility", "onboarding", "docs-release",
    "diagnostics-inventory", "approval-evidence-finalization",
]
CANONICAL_ENTRYPOINTS = {
    "C01": ["skills/backend-engineering/SKILL.md"],
    "C02": ["skills/ai-engineering/SKILL.md"],
    "C03": ["skills/frontend-engineering/SKILL.md"],
    "C04": ["skills/data-middleware-infrastructure/SKILL.md"],
    "C05": ["skills/log-observability-analysis/SKILL.md"],
    "C06": ["skills/engineering-quality-delivery/SKILL.md"],
    "C07": ["skills/multi-agent-independent-review/SKILL.md"],
    "C08": ["skills/technical-document-writing/SKILL.md"],
    "C09": ["skills/long-running-task-memory/SKILL.md"],
    "C10": ["skills/controlled-evolution-governance/SKILL.md"],
    "C11": ["runtime/cp_runtime/project.py", "scripts/cp-runtime.py:project-*"],
    "C12": ["runtime/cp_runtime/capability_index.py", "runtime/cp_runtime/capability_store.py", "scripts/cp-runtime.py:capability-*"],
    "C13": ["runtime/cp_runtime/capability_gate.py", "runtime/cp_runtime/capability_operation.py", "runtime/cp_runtime/patch_intent.py", "hooks/cp_gate.py"],
    "C14": ["runtime/cp_runtime/delegation_budget.py", "scripts/delegation-budget.py"],
    "C15": ["skills/long-running-task-memory/scripts/checkpoint.py", "runtime/cp_runtime/memory.py"],
    "C16": ["hooks/hooks.json", "hooks/cp_hook.py", "hooks/cp_gate.py", "runtime/cp_runtime/seal_queue.py"],
    "C17": ["runtime/cp_runtime/feedback.py", "runtime/cp_runtime/finalization.py", "scripts/cp-runtime.py:feedback/finalize"],
    "C18": ["runtime/cp_runtime/evolution", "scripts/evolution.py"],
    "C19": ["custom-agents/*.toml", "skills/multi-agent-independent-review/scripts/review_controller.py", "skills/multi-agent-independent-review/scripts/review_packet.py"],
    "C20": ["scripts/package_manager.py", "scripts/install-user.ps1", "scripts/install-user.sh", "scripts/install-repo-skills.ps1", "scripts/install-repo-skills.sh"],
    "C21": ["config/codex-compatibility-v1.json", "scripts/codex-compatibility-matrix.py"],
    "C22": ["runtime/cp_runtime/onboarding.py", "runtime/cp_runtime/onboarding_cli.py"],
    "C23": ["scripts/documentation.py", "scripts/build-release.py", "scripts/release-attestation.py", ".github/workflows/release.yml"],
    "C24": ["scripts/package_manager.py:doctor", "scripts/package_manager.py:status", "scripts/package_manager.py:inventory"],
    "C25": ["runtime/cp_runtime/approval.py", "runtime/cp_runtime/evidence.py", "runtime/cp_runtime/finalization.py"],
}


def _registry_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_registry(path: Path) -> dict[str, Any]:
    """中文：读取严格的 25 项静态注册表。

    English: Load the strict static 25-entry registry.
    """
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
    for index, (expected_id, entry) in enumerate(zip(expected_ids, value["entries"])):
        fields(entry, required)
        require(entry["capability_id"] == expected_id, "REGISTRY_ID_ORDER")
        require(isinstance(entry["name"], str) and entry["name"] == CANONICAL_NAMES[index]
                and entry["name"] not in seen_names, "REGISTRY_NAME")
        seen_names.add(entry["name"])
        for key in ("entrypoints", "assisted_prerequisites", "full_prerequisites", "scope"):
            require(isinstance(entry[key], list) and entry[key] and len(entry[key]) == len(set(entry[key])), "REGISTRY_LIST")
            require(all(isinstance(item, str) and 0 < len(item) <= 256 for item in entry[key]), "REGISTRY_LIST")
        require(entry["default_mode"] == "AUTO" and entry["bootstrap_level"] == "BASIC", "REGISTRY_DEFAULT")
        require(entry["entrypoints"] == CANONICAL_ENTRYPOINTS[expected_id], "REGISTRY_ENTRYPOINT_MAPPING")
        require(entry["version"] in {REGISTRY_SCHEMA, "onboarding/1"}, "REGISTRY_VERSION")
        for key in ("persistence_policy", "consent_policy", "fallback", "risk_ref"):
            require(isinstance(entry[key], str) and 0 < len(entry[key]) <= 256, "REGISTRY_TEXT")
    result = copy.deepcopy(value)
    result["registry_digest"] = _registry_digest(value)
    repo_root = path.parent.parent if path.parent.name == "config" and (path.parent.parent / "manifest.json").is_file() else None
    if repo_root is not None:
        validate_registry_coverage(result, repo_root)
    return result


def validate_registry_coverage(registry: Mapping[str, Any], repo_root: Path) -> dict[str, Any]:
    """中文：核对规范入口、Manifest Skills、Reviewer、Hook 与公开 CLI 覆盖。

    English: Validate canonical entrypoints plus Manifest Skills, Reviewers, Hooks, and public CLI coverage.
    """
    root = safe_path(repo_root)
    manifest = json.loads(bounded_read(root / "manifest.json", 512 * 1024), object_pairs_hook=unique_json_object)
    entries = {entry["capability_id"]: entry for entry in registry["entries"]}
    require([item["name"] for item in manifest.get("skills", [])] == CANONICAL_NAMES[:10], "REGISTRY_SKILL_COVERAGE")
    reviewers = manifest.get("custom_agents", [])
    require(isinstance(reviewers, list) and len(reviewers) == 7, "REGISTRY_REVIEWER_COVERAGE")
    require(all((root / item["file"]).is_file() for item in reviewers), "REGISTRY_REVIEWER_COVERAGE")
    hooks = json.loads(bounded_read(root / "hooks" / "hooks.json", 256 * 1024), object_pairs_hook=unique_json_object)["hooks"]
    require(set(hooks) == {"UserPromptSubmit", "PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop", "Stop", "Interrupt", "SessionEnd"},
            "REGISTRY_HOOK_COVERAGE")
    for capability_id, expected in CANONICAL_ENTRYPOINTS.items():
        require(entries[capability_id]["entrypoints"] == expected, "REGISTRY_ENTRYPOINT_MAPPING")
        for entrypoint in expected:
            file_part = entrypoint.split(":", 1)[0]
            if "*" in file_part:
                require(bool(list(root.glob(file_part))), "REGISTRY_ENTRYPOINT_MISSING")
            else:
                require((root / file_part).exists(), "REGISTRY_ENTRYPOINT_MISSING")
    sources = "\n".join((root / path).read_text(encoding="utf-8") for path in (
        "runtime/cp_runtime/cli.py", "runtime/cp_runtime/capability_cli.py",
        "runtime/cp_runtime/capability_gate_cli.py", "runtime/cp_runtime/capability_registry_cli.py",
        "runtime/cp_runtime/onboarding_cli.py", "scripts/package_manager.py"))
    required_command_fragments = {"project-onboard", "capability-task-", "capability-registry",
                                  "onboarding-offer", 'subparsers.add_parser("capability-" + action)',
                                  'sub.add_parser("doctor")', 'sub.add_parser("status")',
                                  'sub.add_parser("inventory")', 'sub.add_parser("recover")'}
    require(all(fragment in sources for fragment in required_command_fragments), "REGISTRY_CLI_COVERAGE")
    return {"status": "VALID", "capability_count": 25, "skill_count": 10,
            "reviewer_count": 7, "hook_count": 8, "public_cli_families": len(required_command_fragments)}


def select_capability(registry: Mapping[str, Any], capability_id: str, prerequisites: Mapping[str, bool],
                      preference: Mapping[str, Any] | None = None, risk: str = "UNKNOWN",
                      statuses: Mapping[str, str] | None = None) -> dict[str, Any]:
    """中文：按偏好和前提计算档位；风险与授权始终独立。

    English: Select a level while keeping risk and authority separate.
    """
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
    """中文：读取安装器保存的惰性迁移计划；只接受无授权、无扫描同意的精确映射。

    English: Read an installer-recorded lazy migration only when it grants no authority or scan consent.
    """
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
    """中文：身份绑定、原子 CAS 的独立偏好文件；缺文件就是 AUTO 且不落盘。

    English: Identity-bound atomic preference storage; a missing file means AUTO without a write.
    """

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
