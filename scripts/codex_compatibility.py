#!/usr/bin/env python3
"""中文：Codex 稳定版兼容注册表与线协议适配器。

English: Codex stable-release compatibility registry and wire-contract adapters.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


class CompatibilityError(ValueError):
    """中文：兼容证据或宿主输出不可信时抛出。

    English: Raised when compatibility evidence or host output is not trustworthy.
    """


_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_VERSION_OUTPUT = re.compile(r"^codex-cli ((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")

_TOP_LEVEL = {"schema_version", "package_version", "window_policy", "profiles", "versions"}
_WINDOW_FIELDS = {
    "anchor", "preceding_stable_releases", "include_patch_releases",
    "include_prereleases", "frozen_at", "release_order_source",
    "frozen_release_order_sha256",
}
_PROFILE_GROUPS = {"marketplace", "plugin_cli", "plugin_json", "hook", "apply_patch_result"}
_VERSION_FIELDS = {
    "version", "stable_release_ordinal", "marketplace_profile", "plugin_cli_profile",
    "plugin_json_profile", "hook_profile", "native_async_user_prompt_submit",
    "native_apply_patch_operation", "apply_patch_result_profile", "artifact", "probe_evidence",
}
_ARTIFACT_FIELDS = {"tarball", "npm_integrity", "tarball_sha256"}
_EVIDENCE_FIELDS = {
    "version_output_sha256", "plugin_list_empty_sha256",
    "marketplace_add_help_sha256", "marketplace_remove_help_sha256",
    "plugin_add_help_sha256", "plugin_remove_help_sha256",
    "windows_cli_contract", "windows_isolated_plugin", "ubuntu_cli_contract",
    "synthetic_hook", "real_host",
}
_EVIDENCE_VALUES = {
    "CLI_CONTRACT_PASS", "ISOLATED_PLUGIN_PASS", "SYNTHETIC_HOOK_PASS",
    "REAL_HOST_PASS", "NOT_EVALUATED", "FAILED",
}
_HOOK_ALIAS_FIELDS = {
    "hook_event_name", "tool_name", "tool_input", "tool_use_id", "task_name",
    "agent_type", "model", "reasoning_effort", "reservation_id", "agent_id",
    "session_id", "turn_id", "task_id", "cwd", "terminal_outcome",
}
_ASYNC_SOURCE_FIELDS = {
    "status", "evidence", "registration", "repository", "tag", "commit_sha",
    "source_path", "source_sha256", "verified_assertions",
}
_ASYNC_ASSERTIONS = {
    "USER_PROMPT_SUBMIT_EVENT", "ASYNC_FIELD_PARSED", "ASYNC_PROPAGATED_TO_COMMAND_HANDLER",
}
_OPERATION_SOURCE_FIELDS = set(_ASYNC_SOURCE_FIELDS)
_OPERATION_ASSERTIONS = {
    "PRE_TOOL_USE_INPUT", "POST_TOOL_USE_INPUT", "TOOL_USE_ID", "TOOL_RESPONSE",
    "POST_TOOL_BLOCK_OUTPUT",
}
_RESULT_ASSERTIONS = {
    "APPLY_PATCH_OUTPUT_ON_SUCCESS", "POST_TOOL_PAYLOAD_FROM_RESULT",
    "POST_TOOL_RESPONSE_STRING",
}


def _require_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise CompatibilityError(f"{label} 必须是 JSON object")
    return value


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise CompatibilityError(f"{label} 字段不闭合: missing={missing}, unknown={unknown}")


def _require_string_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise CompatibilityError(f"{label} 必须是{'可为空的' if allow_empty else '非空'}字符串数组")
    if any(not isinstance(item, str) or not item for item in value) or len(value) != len(set(value)):
        raise CompatibilityError(f"{label} 含无效或重复字符串")
    return value


def _stable_tuple(version: str) -> tuple[int, int, int]:
    match = _SEMVER.fullmatch(version) if isinstance(version, str) else None
    if not match:
        raise CompatibilityError(f"不是稳定三段版本号: {version!r}")
    return tuple(int(part) for part in match.groups())


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_codex_version_output(output: str) -> str:
    """中文：仅接受精确的 Codex CLI 稳定版输出格式。

    English: Accept only the exact stable Codex CLI version wire format.
    """
    if not isinstance(output, str):
        raise CompatibilityError("Codex 版本输出必须是字符串")
    match = _VERSION_OUTPUT.fullmatch(output)
    if not match:
        raise CompatibilityError(f"Codex 版本输出格式未知: {output!r}")
    return match.group(1)


def _validate_profiles(profiles: Mapping[str, Any]) -> None:
    _require_exact_keys(profiles, _PROFILE_GROUPS, "profiles")
    expected_fields = {
        "marketplace": {
            "managed_top_level_fields", "managed_interface_fields",
            "display_name", "emit_owner",
        },
        "plugin_cli": {"required_commands", "remote_marketplace_available"},
        "plugin_json": {
            "top_level_fields", "required_target_fields", "optional_target_fields",
            "install_policies", "auth_policies",
        },
        "hook": {
            "events", "deny_wire_profile", "deny_wire_fields",
            "alias_conflict_policy", "historical_real_host_evidence", "aliases",
        },
        "apply_patch_result": {
            "handler_path", "handler_sha256", "context_path", "context_sha256",
            "verified_assertions",
        },
    }
    for group, profile_fields in expected_fields.items():
        declared = _require_object(profiles[group], f"profiles.{group}")
        if not declared:
            raise CompatibilityError(f"profiles.{group} 不能为空")
        for name, profile in declared.items():
            if not isinstance(name, str) or not name:
                raise CompatibilityError(f"profiles.{group} 含无效名称")
            item = _require_object(profile, f"profiles.{group}.{name}")
            _require_exact_keys(item, profile_fields, f"profiles.{group}.{name}")

    for name, profile in profiles["marketplace"].items():
        prefix = f"profiles.marketplace.{name}"
        if set(_require_string_list(profile["managed_top_level_fields"], f"{prefix}.managed_top_level_fields")) != {"name", "plugins"}:
            raise CompatibilityError(f"{prefix}.managed_top_level_fields 契约漂移")
        if set(_require_string_list(profile["managed_interface_fields"], f"{prefix}.managed_interface_fields")) != {"displayName"}:
            raise CompatibilityError(f"{prefix}.managed_interface_fields 契约漂移")
        if not isinstance(profile["display_name"], str) or not profile["display_name"]:
            raise CompatibilityError(f"{prefix}.display_name 无效")
        if type(profile["emit_owner"]) is not bool:
            raise CompatibilityError(f"{prefix}.emit_owner 必须是 boolean")

    required_commands = {"marketplace_add", "marketplace_remove", "plugin_add", "plugin_remove"}
    for name, profile in profiles["plugin_cli"].items():
        prefix = f"profiles.plugin_cli.{name}"
        if set(_require_string_list(profile["required_commands"], f"{prefix}.required_commands")) != required_commands:
            raise CompatibilityError(f"{prefix}.required_commands 契约漂移")
        if type(profile["remote_marketplace_available"]) is not bool:
            raise CompatibilityError(f"{prefix}.remote_marketplace_available 必须是 boolean")

    for name, profile in profiles["plugin_json"].items():
        prefix = f"profiles.plugin_json.{name}"
        top = set(_require_string_list(profile["top_level_fields"], f"{prefix}.top_level_fields"))
        required = set(_require_string_list(profile["required_target_fields"], f"{prefix}.required_target_fields"))
        optional = set(_require_string_list(
            profile["optional_target_fields"], f"{prefix}.optional_target_fields", allow_empty=True,
        ))
        if top != {"installed", "available"}:
            raise CompatibilityError(f"{prefix}.top_level_fields 契约漂移")
        identity = {"pluginId", "name", "marketplaceName", "version", "installed", "enabled", "installPolicy", "authPolicy"}
        if not identity.issubset(required) or required & optional:
            raise CompatibilityError(f"{prefix} 目标字段契约无效")
        _require_string_list(profile["install_policies"], f"{prefix}.install_policies")
        _require_string_list(profile["auth_policies"], f"{prefix}.auth_policies")

    for name, profile in profiles["hook"].items():
        prefix = f"profiles.hook.{name}"
        events = set(_require_string_list(profile["events"], f"{prefix}.events"))
        if events != {"UserPromptSubmit", "PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop", "Stop", "SessionEnd"}:
            raise CompatibilityError(f"{prefix}.events 契约漂移")
        if profile["deny_wire_profile"] != "hook-specific-output-v1":
            raise CompatibilityError(f"{prefix}.deny_wire_profile 契约漂移")
        deny_fields = set(_require_string_list(profile["deny_wire_fields"], f"{prefix}.deny_wire_fields"))
        if deny_fields != {"hookEventName", "permissionDecision", "permissionDecisionReason"}:
            raise CompatibilityError(f"{prefix}.deny_wire_fields 契约漂移")
        if profile["alias_conflict_policy"] != "deny-security-unavailable-observation":
            raise CompatibilityError(f"{prefix}.alias_conflict_policy 契约漂移")
        if profile["historical_real_host_evidence"] not in {"REAL_HOST_NOT_EVALUATED", "REAL_HOST_PASS"}:
            raise CompatibilityError(f"{prefix}.historical_real_host_evidence 无效")
        aliases = _require_object(profile["aliases"], f"profiles.hook.{name}.aliases")
        _require_exact_keys(aliases, _HOOK_ALIAS_FIELDS, f"profiles.hook.{name}.aliases")
        seen_aliases: set[str] = set()
        for semantic, names in aliases.items():
            if not isinstance(names, list) or not names or names[0] != semantic:
                raise CompatibilityError(f"hook alias {semantic} 必须以规范名开头")
            if any(not isinstance(alias, str) or not alias for alias in names) or len(names) != len(set(names)):
                raise CompatibilityError(f"hook alias {semantic} 含无效或重复名称")
            overlap = seen_aliases & set(names)
            if overlap:
                raise CompatibilityError(f"hook alias 在不同语义间重复: {sorted(overlap)}")
            seen_aliases.update(names)

    for name, profile in profiles["apply_patch_result"].items():
        prefix = f"profiles.apply_patch_result.{name}"
        if (profile["handler_path"] != "codex-rs/core/src/tools/handlers/apply_patch.rs"
                or profile["context_path"] != "codex-rs/core/src/tools/context.rs"
                or not isinstance(profile["handler_sha256"], str)
                or not _SHA256.fullmatch(profile["handler_sha256"])
                or not isinstance(profile["context_sha256"], str)
                or not _SHA256.fullmatch(profile["context_sha256"])
                or set(_require_string_list(profile["verified_assertions"],
                                            f"{prefix}.verified_assertions")) != _RESULT_ASSERTIONS):
            raise CompatibilityError(f"{prefix} apply_patch 结果来源证据无效")


def _validate_artifact(version: str, artifact: Mapping[str, Any]) -> None:
    _require_exact_keys(artifact, _ARTIFACT_FIELDS, f"artifact[{version}]")
    expected_url = f"https://registry.npmjs.org/@openai/codex/-/codex-{version}.tgz"
    if artifact["tarball"] != expected_url:
        raise CompatibilityError(f"{version} tarball URL 与官方固定格式不一致")
    integrity = artifact["npm_integrity"]
    if not isinstance(integrity, str) or not integrity.startswith("sha512-"):
        raise CompatibilityError(f"{version} npm_integrity 无效")
    try:
        decoded = base64.b64decode(integrity[7:], validate=True)
    except (ValueError, TypeError) as exc:
        raise CompatibilityError(f"{version} npm_integrity 不是合法 base64") from exc
    if len(decoded) != 64:
        raise CompatibilityError(f"{version} npm_integrity 不是 SHA-512")
    if not isinstance(artifact["tarball_sha256"], str) or not _SHA256.fullmatch(artifact["tarball_sha256"]):
        raise CompatibilityError(f"{version} tarball_sha256 无效")


def _validate_evidence(version: str, evidence: Mapping[str, Any]) -> None:
    _require_exact_keys(evidence, _EVIDENCE_FIELDS, f"probe_evidence[{version}]")
    for key in (
        "version_output_sha256", "plugin_list_empty_sha256",
        "marketplace_add_help_sha256", "marketplace_remove_help_sha256",
        "plugin_add_help_sha256", "plugin_remove_help_sha256",
    ):
        value = evidence[key]
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise CompatibilityError(f"{version} {key} 无效")
    for key in (
        "windows_cli_contract", "windows_isolated_plugin", "ubuntu_cli_contract",
        "synthetic_hook", "real_host",
    ):
        if evidence[key] not in _EVIDENCE_VALUES:
            raise CompatibilityError(f"{version} {key} 使用未知证据状态")


def validate_registry(registry: Mapping[str, Any], expected_package_version: Optional[str] = None) -> None:
    _require_exact_keys(registry, _TOP_LEVEL, "registry")
    if registry["schema_version"] != 1:
        raise CompatibilityError("仅支持 compatibility registry schema 1")
    package_version = registry["package_version"]
    _stable_tuple(package_version)
    if expected_package_version is not None and package_version != expected_package_version:
        raise CompatibilityError(
            f"registry package_version={package_version}，期望 {expected_package_version}",
        )

    window = _require_object(registry["window_policy"], "window_policy")
    _require_exact_keys(window, _WINDOW_FIELDS, "window_policy")
    anchor = window["anchor"]
    _stable_tuple(anchor)
    if type(window["preceding_stable_releases"]) is not int or window["preceding_stable_releases"] != 10:
        raise CompatibilityError("当前发行版必须固定前十个稳定发行版")
    if window["include_patch_releases"] is not True or window["include_prereleases"] is not False:
        raise CompatibilityError("稳定发行窗口策略无效")
    if not isinstance(window["frozen_at"], str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", window["frozen_at"]):
        raise CompatibilityError("window_policy.frozen_at 无效")
    if not isinstance(window["release_order_source"], str) or not window["release_order_source"].startswith("https://"):
        raise CompatibilityError("window_policy.release_order_source 必须是 HTTPS 来源")
    if not isinstance(window["frozen_release_order_sha256"], str) or not _SHA256.fullmatch(window["frozen_release_order_sha256"]):
        raise CompatibilityError("window_policy.frozen_release_order_sha256 无效")

    profiles = _require_object(registry["profiles"], "profiles")
    _validate_profiles(profiles)
    versions = registry["versions"]
    if not isinstance(versions, list) or len(versions) != 11:
        raise CompatibilityError("兼容窗口必须恰好包含当前版和前十个稳定发行版")

    seen: set[str] = set()
    referenced = {group: set() for group in _PROFILE_GROUPS}
    ordered: list[str] = []
    profile_field = {
        "marketplace": "marketplace_profile",
        "plugin_cli": "plugin_cli_profile",
        "plugin_json": "plugin_json_profile",
        "hook": "hook_profile",
        "apply_patch_result": "apply_patch_result_profile",
    }
    for index, raw in enumerate(versions):
        item = _require_object(raw, f"versions[{index}]")
        _require_exact_keys(item, _VERSION_FIELDS, f"versions[{index}]")
        version = item["version"]
        _stable_tuple(version)
        if type(item["stable_release_ordinal"]) is not int or item["stable_release_ordinal"] != index:
            raise CompatibilityError(f"{version} stable_release_ordinal 与冻结顺序不一致")
        if version in seen:
            raise CompatibilityError(f"重复版本: {version}")
        seen.add(version)
        ordered.append(version)
        for group, field in profile_field.items():
            name = item[field]
            if not isinstance(name, str) or name not in profiles[group]:
                raise CompatibilityError(f"{version} 引用了未知 {group} profile: {name!r}")
            referenced[group].add(name)
        async_capability = _require_object(
            item["native_async_user_prompt_submit"],
            f"versions[{index}].native_async_user_prompt_submit",
        )
        _require_exact_keys(
            async_capability,
            _ASYNC_SOURCE_FIELDS,
            f"versions[{index}].native_async_user_prompt_submit",
        )
        if async_capability["status"] not in {"SUPPORTED", "UNKNOWN"}:
            raise CompatibilityError(f"{version} native async status 无效")
        if async_capability["evidence"] not in {
            "OFFICIAL_SOURCE_TAG", "OFFICIAL_DOCS_CURRENT", "NOT_EVALUATED",
        }:
            raise CompatibilityError(f"{version} native async evidence 无效")
        if async_capability["registration"] != "OPTIONAL_USER_PROMPT_SUBMIT":
            raise CompatibilityError(f"{version} native async registration 策略无效")
        assertions = async_capability["verified_assertions"]
        if not isinstance(assertions, list) or any(not isinstance(value, str) for value in assertions):
            raise CompatibilityError(f"{version} native async assertions 无效")
        if async_capability["status"] == "SUPPORTED":
            if async_capability["evidence"] != "OFFICIAL_SOURCE_TAG":
                raise CompatibilityError(f"{version} 无充分证据声明支持 native async")
            if async_capability["repository"] != "https://github.com/openai/codex":
                raise CompatibilityError(f"{version} native async 官方仓库无效")
            if async_capability["tag"] != f"rust-v{version}":
                raise CompatibilityError(f"{version} native async tag 无效")
            if not isinstance(async_capability["commit_sha"], str) or not _GIT_SHA.fullmatch(async_capability["commit_sha"]):
                raise CompatibilityError(f"{version} native async commit 无效")
            if async_capability["source_path"] != "codex-rs/hooks/src/engine/discovery.rs":
                raise CompatibilityError(f"{version} native async 源码路径无效")
            if not isinstance(async_capability["source_sha256"], str) or not _SHA256.fullmatch(async_capability["source_sha256"]):
                raise CompatibilityError(f"{version} native async 源码摘要无效")
            if set(assertions) != _ASYNC_ASSERTIONS or len(assertions) != len(_ASYNC_ASSERTIONS):
                raise CompatibilityError(f"{version} native async 源码断言不完整")
        else:
            if async_capability["evidence"] != "NOT_EVALUATED":
                raise CompatibilityError(f"{version} 未知 native async 必须标记未评估")
            if any(async_capability[field] for field in ("repository", "tag", "commit_sha", "source_path", "source_sha256")) or assertions:
                raise CompatibilityError(f"{version} 未知 native async 不得携带已验证源码证据")
        operation_capability = _require_object(
            item["native_apply_patch_operation"],
            f"versions[{index}].native_apply_patch_operation",
        )
        _require_exact_keys(
            operation_capability,
            _OPERATION_SOURCE_FIELDS,
            f"versions[{index}].native_apply_patch_operation",
        )
        if operation_capability["status"] not in {"SUPPORTED", "UNKNOWN"}:
            raise CompatibilityError(f"{version} apply_patch operation status 无效")
        if operation_capability["evidence"] not in {"OFFICIAL_SOURCE_TAG", "NOT_EVALUATED"}:
            raise CompatibilityError(f"{version} apply_patch operation evidence 无效")
        if operation_capability["registration"] != "REQUIRED_APPLY_PATCH_PRE_POST":
            raise CompatibilityError(f"{version} apply_patch operation registration 无效")
        operation_assertions = operation_capability["verified_assertions"]
        if not isinstance(operation_assertions, list) or any(
                not isinstance(value, str) for value in operation_assertions):
            raise CompatibilityError(f"{version} apply_patch operation assertions 无效")
        if operation_capability["status"] == "SUPPORTED":
            if (operation_capability["evidence"] != "OFFICIAL_SOURCE_TAG"
                    or operation_capability["repository"] != "https://github.com/openai/codex"
                    or operation_capability["tag"] != f"rust-v{version}"
                    or not isinstance(operation_capability["commit_sha"], str)
                    or not _GIT_SHA.fullmatch(operation_capability["commit_sha"])
                    or operation_capability["source_path"] != "codex-rs/hooks/src/schema.rs"
                    or not isinstance(operation_capability["source_sha256"], str)
                    or not _SHA256.fullmatch(operation_capability["source_sha256"])
                    or set(operation_assertions) != _OPERATION_ASSERTIONS
                    or len(operation_assertions) != len(_OPERATION_ASSERTIONS)):
                raise CompatibilityError(f"{version} apply_patch operation 源码证据不完整")
        else:
            if operation_capability["evidence"] != "NOT_EVALUATED":
                raise CompatibilityError(f"{version} 未知 apply_patch operation 必须标记未评估")
            if (any(operation_capability[field] for field in
                    ("repository", "tag", "commit_sha", "source_path", "source_sha256"))
                    or operation_assertions):
                raise CompatibilityError(f"{version} 未知 apply_patch operation 不得携带源码证据")
        _validate_artifact(version, _require_object(item["artifact"], f"artifact[{version}]"))
        _validate_evidence(version, _require_object(item["probe_evidence"], f"probe_evidence[{version}]"))

    if ordered[0] != anchor:
        raise CompatibilityError("兼容窗口首项必须是 anchor")
    if ordered != sorted(ordered, key=_stable_tuple, reverse=True):
        raise CompatibilityError("兼容版本必须按稳定 SemVer 严格降序排列")
    if canonical_digest(ordered) != window["frozen_release_order_sha256"]:
        raise CompatibilityError("冻结稳定发行顺序摘要不一致")
    for group in _PROFILE_GROUPS:
        unused = set(profiles[group]) - referenced[group]
        if unused:
            raise CompatibilityError(f"profiles.{group} 存在未引用项: {sorted(unused)}")


def load_registry(path: Path, expected_package_version: Optional[str] = None) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompatibilityError(f"无法读取兼容注册表: {path}") from exc
    registry = dict(_require_object(value, "registry"))
    validate_registry(registry, expected_package_version)
    return registry


def profile_for_version(registry: Mapping[str, Any], version: str) -> Dict[str, Any]:
    validate_registry(registry)
    for item in registry["versions"]:
        if item["version"] == version:
            result = dict(item)
            result["registry_digest"] = canonical_digest(registry)
            return result
    raise CompatibilityError(f"Codex {version} 不在冻结兼容窗口内")


def verify_artifact_file(registry: Mapping[str, Any], version: str, path: Path) -> Dict[str, Any]:
    """中文：使用固定 SHA-256 与 npm SRI 双重校验官方 Codex 包。

    English: Verify an official Codex tarball against both frozen SHA-256 and npm SRI.
    """
    profile = profile_for_version(registry, version)
    artifact = profile["artifact"]
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise CompatibilityError(f"无法读取 Codex {version} 固定制品: {path}") from exc
    sha256 = hashlib.sha256(payload).hexdigest()
    sri = "sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode("ascii")
    if sha256 != artifact["tarball_sha256"] or sri != artifact["npm_integrity"]:
        raise CompatibilityError(f"Codex {version} 固定制品摘要不匹配")
    return {
        "version": version,
        "path": str(path.resolve()),
        "size": len(payload),
        "tarball_sha256": sha256,
        "npm_integrity": sri,
        "registry_digest": canonical_digest(registry),
    }


def normalize_plugin_list(
    payload: Any,
    package: str,
    marketplace: str,
    expected_version: Optional[str],
    profile: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    """中文：规范化唯一目标条目；不存在时返回 ``None``。

    English: Normalize one exact target item; return ``None`` when it is absent.
    """
    root = _require_object(payload, "plugin list")
    allowed_top = set(profile["top_level_fields"])
    _require_exact_keys(root, allowed_top, "plugin list")
    if allowed_top != {"installed", "available"}:
        raise CompatibilityError("plugin-list-v1 顶层契约漂移")
    for key in allowed_top:
        if not isinstance(root[key], list):
            raise CompatibilityError(f"plugin list.{key} 必须是 array")

    expected_id = f"{package}@{marketplace}"
    matches: list[Mapping[str, Any]] = []
    for collection in ("installed", "available"):
        for index, raw in enumerate(root[collection]):
            item = _require_object(raw, f"plugin list.{collection}[{index}]")
            plugin_id = item.get("pluginId")
            name = item.get("name")
            market = item.get("marketplaceName")
            by_id = plugin_id == expected_id
            by_pair = name == package and market == marketplace
            partial_identity = name == package or market == marketplace
            if by_id and (name != package or market != marketplace):
                raise CompatibilityError("目标 Plugin 的 pluginId/name/marketplaceName 冲突")
            if by_pair and plugin_id != expected_id:
                raise CompatibilityError("目标 Plugin 的规范身份与 pluginId 冲突")
            if partial_identity and not (by_id and by_pair):
                raise CompatibilityError("目标 Plugin 出现部分身份匹配")
            if by_id and by_pair:
                matches.append(item)
    if len(matches) > 1:
        raise CompatibilityError("目标 Plugin 身份重复")
    if not matches:
        return None

    item = matches[0]
    required = set(profile["required_target_fields"])
    optional = set(profile["optional_target_fields"])
    missing = required - set(item)
    unknown = set(item) - required - optional
    if missing or unknown:
        raise CompatibilityError(
            f"目标 Plugin 字段不闭合: missing={sorted(missing)}, unknown={sorted(unknown)}",
        )
    string_fields = {"pluginId", "name", "marketplaceName", "version", "installPolicy", "authPolicy"}
    if any(not isinstance(item[field], str) for field in string_fields):
        raise CompatibilityError("目标 Plugin 字符串字段类型错误")
    if not _SEMVER.fullmatch(item["version"]):
        raise CompatibilityError("目标 Plugin 版本不是稳定三段版本")
    if expected_version is not None and item["version"] != expected_version:
        raise CompatibilityError("目标 Plugin 版本不匹配或不是稳定三段版本")
    if item["installed"] is not True or item["enabled"] is not True:
        raise CompatibilityError("目标 Plugin 必须 installed=true 且 enabled=true")
    if item["installPolicy"] not in profile["install_policies"]:
        raise CompatibilityError("目标 Plugin installPolicy 未登记")
    if item["authPolicy"] not in profile["auth_policies"]:
        raise CompatibilityError("目标 Plugin authPolicy 未登记")
    for field in optional & set(item):
        if not isinstance(item[field], (str, dict)):
            raise CompatibilityError(f"目标 Plugin {field} 类型错误")
    return {
        "plugin_id": item["pluginId"],
        "name": item["name"],
        "marketplace_name": item["marketplaceName"],
        "version": item["version"],
        "installed": True,
        "enabled": True,
        "install_policy": item["installPolicy"],
        "auth_policy": item["authPolicy"],
    }
