"""中文：桌面管理组件与任务运行契约分离，不以独立 CLI 版本准入。

English: Separate Desktop management component and runtime contracts.
Documented support never substitutes for native acceptance on the actual host.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from codex_compatibility import CompatibilityError, canonical_digest

SCHEMA = "desktop-host-contract/1"
COMMANDS = {"marketplace_add", "marketplace_remove", "plugin_add", "plugin_remove"}
BINDING_FIELDS = {"codex_version", "executable_path", "executable_sha256", "registry_schema",
                  "registry_digest", "marketplace_profile", "plugin_cli_profile", "plugin_json_profile",
                  "hook_profile", "apply_patch_result_profile", "commands", "plugin_list_contract", "capability_digest"}
VERSION = re.compile(r"^codex-cli (\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)$")


def component_path(codex_home: Path) -> Path | None:
    declared = os.environ.get("CP_ASSISTANT_DESKTOP_COMPONENT", "").strip()
    candidate = Path(declared).expanduser() if declared else (
        codex_home / "plugins" / ".plugin-appserver" / ("codex.exe" if os.name == "nt" else "codex"))
    if candidate.is_file():
        return candidate.resolve()
    if declared:
        raise CompatibilityError("DESKTOP_COMPONENT_NOT_FOUND")
    return None


def parse_component_version(output: str) -> str:
    matched = VERSION.fullmatch(output) if isinstance(output, str) else None
    if not matched:
        raise CompatibilityError("DESKTOP_COMPONENT_VERSION_FORMAT")
    return matched.group(1)


def load_contract(path: Path) -> dict[str, Any]:
    from cp_runtime.routing_contract import exact, read_document, sha
    value, _ = read_document(path)
    exact(value, {"schema_version", "host_surface", "management_version_is_runtime_version",
                  "native_acceptance_required", "source", "management", "runtime", "wire_profiles"},
          "DESKTOP_CONTRACT_FIELDS")
    if value["schema_version"] != SCHEMA or value["host_surface"] != "codex-desktop" \
            or value["management_version_is_runtime_version"] is not False \
            or value["native_acceptance_required"] is not True:
        raise CompatibilityError("DESKTOP_CONTRACT_IDENTITY")
    source = exact(value["source"], {"url", "checked_on", "evidence", "assertions"}, "DESKTOP_CONTRACT_SOURCE")
    if source["url"] != "https://learn.chatgpt.com/docs/hooks" or source["evidence"] != "OFFICIAL_DOCS_CURRENT" \
            or set(source["assertions"]) != {"ASYNC_COMMAND_HOOKS", "APPLY_PATCH_PRE_POST", "TOOL_USE_ID", "TOOL_RESPONSE"}:
        raise CompatibilityError("DESKTOP_DOCUMENTED_CONTRACT_REQUIRED")
    management = exact(value["management"], {"marketplace_profile", "plugin_cli_profile", "plugin_json_profile",
                                             "commands"}, "DESKTOP_MANAGEMENT_FIELDS")
    exact(management["commands"], COMMANDS, "DESKTOP_COMMAND_FIELDS")
    for digest in management["commands"].values():
        sha("sha256:" + str(digest), "DESKTOP_COMMAND_DIGEST")
    exact(value["runtime"], {"hook_profile", "apply_patch_result_profile", "native_async_user_prompt_submit",
                             "native_apply_patch_operation"}, "DESKTOP_RUNTIME_FIELDS")
    exact(value["wire_profiles"], {"marketplace", "plugin_cli", "plugin_json"}, "DESKTOP_WIRE_PROFILES")
    for group in value["wire_profiles"]:
        if management[group + "_profile"] not in value["wire_profiles"][group]:
            raise CompatibilityError("DESKTOP_WIRE_PROFILE_MISSING")
    return value


def profile(contract: Mapping[str, Any], version: str) -> dict[str, Any]:
    parse_component_version("codex-cli " + version)
    management = contract["management"]
    return {"version": version, "registry_digest": canonical_digest(contract),
            **{key: management[key] for key in ("marketplace_profile", "plugin_cli_profile", "plugin_json_profile")},
            **copy.deepcopy(contract["runtime"]),
            "probe_evidence": {key + "_help_sha256": value for key, value in management["commands"].items()}}


def valid_binding(binding: Any, contract: Mapping[str, Any]) -> bool:
    if not isinstance(binding, dict) or set(binding) != BINDING_FIELDS:
        return False
    try:
        expected = profile(contract, binding["codex_version"])
        if binding["registry_schema"] != SCHEMA or binding["registry_digest"] != canonical_digest(contract) \
                or binding["plugin_list_contract"] is not True \
                or not isinstance(binding["executable_path"], str) or not binding["executable_path"] \
                or not re.fullmatch(r"[a-f0-9]{64}", binding["executable_sha256"]):
            return False
        for key in ("marketplace_profile", "plugin_cli_profile", "plugin_json_profile", "hook_profile", "apply_patch_result_profile"):
            if binding[key] != expected[key]:
                return False
        if set(binding["commands"]) != COMMANDS:
            return False
        for key, command in binding["commands"].items():
            if command != {"ok": True, "sha256": contract["management"]["commands"][key]}:
                return False
        payload = {key: value for key, value in binding.items() if key != "capability_digest"}
        return binding["capability_digest"] == canonical_digest(payload)
    except (KeyError, TypeError, ValueError):
        return False


def verified_capability(capability: Any, contract: Mapping[str, Any]) -> bool:
    return isinstance(capability, dict) and capability.get("ok") is True and valid_binding(
        {key: capability.get(key) for key in BINDING_FIELDS}, contract)
