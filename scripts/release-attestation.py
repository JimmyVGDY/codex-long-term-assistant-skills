#!/usr/bin/env python3
"""Create and verify a privacy-bounded V6.4 release attestation."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

PACKAGE = "codex-cross-project-engineering-assistant"
MARKETPLACE = "cp-assistant-local"
VERSION = "6.4.0"
PLUGIN_ID = "%s@%s" % (PACKAGE, MARKETPLACE)


class AttestationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_object(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise AttestationError("evidence file must contain a JSON object: %s" % path.name)
    return value


def _is_reparse(path: Path) -> bool:
    try:
        value = path.lstat()
    except OSError:
        return False
    return stat.S_ISLNK(value.st_mode) or bool(getattr(value, "st_file_attributes", 0) & 0x400)


def _plugin_item(plugin_list: Mapping[str, Any]) -> Dict[str, Any]:
    for item in plugin_list.get("installed", []) if isinstance(plugin_list.get("installed"), list) else []:
        if not isinstance(item, dict):
            continue
        if item.get("pluginId") == PLUGIN_ID:
            if not bool(item.get("installed")) or not bool(item.get("enabled")) or item.get("version") != VERSION:
                raise AttestationError("Plugin readback does not prove installed/enabled/version=6.4.0")
            return item
    raise AttestationError("target Plugin was not found in Codex readback")


def _luna_model_proven(lifecycle: Mapping[str, Any]) -> bool:
    if "gpt-5.6-luna" in lifecycle.get("actual_subagent_models", []):
        return True
    evidence = lifecycle.get("subagent_model_evidence") or {}
    return isinstance(evidence, dict) and evidence.get("status") == "PASS" \
        and evidence.get("expected_model") == "gpt-5.6-luna" \
        and evidence.get("actual_model_fact_preserved") is True \
        and (evidence.get("hook_payload_match") is True or evidence.get("host_session_match") is True)


def _codex_version(version_evidence: Path | None = None) -> str:
    if version_evidence is not None:
        value = version_evidence.read_text(encoding="utf-8-sig").strip()
        if not re.search(r"(?:^|\s)0\.150\.1(?:\s|$)", value):
            raise AttestationError("observed Codex version is not 0.150.1")
        return value
    result = subprocess.run(["codex", "--version"], text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30)
    if result.returncode != 0:
        raise AttestationError("codex --version failed")
    value = (result.stdout or result.stderr or "").strip()
    if not re.search(r"(?:^|\s)0\.150\.1(?:\s|$)", value):
        raise AttestationError("observed Codex version is not 0.150.1")
    return value


def create_attestation(
    artifact: Path,
    plugin_list_path: Path,
    lifecycle_report_path: Path,
    package_validation_path: Path,
    deterministic_witness_path: Path,
    unified_verification_path: Path,
    codex_version_evidence_path: Path | None = None,
) -> Dict[str, Any]:
    plugin_item = _plugin_item(_load_object(plugin_list_path))
    lifecycle = _load_object(lifecycle_report_path)
    validation = _load_object(package_validation_path)
    reproducibility = _load_object(deterministic_witness_path)
    unified = _load_object(unified_verification_path)
    if lifecycle.get("ok") is not True or lifecycle.get("event_chain", {}).get("valid") is not True:
        raise AttestationError("lifecycle evidence is not valid")
    if validation.get("ok") is not True:
        raise AttestationError("package validation evidence is not valid")
    if reproducibility.get("reproducible") is not True:
        raise AttestationError("deterministic build evidence is not valid")
    artifact_sha256 = sha256_file(artifact)
    if reproducibility.get("artifact_sha256") != artifact_sha256:
        raise AttestationError("deterministic build evidence is not bound to the target artifact")
    if unified.get("ok") is not True or unified.get("version") != VERSION \
            or unified.get("artifact_sha256") != artifact_sha256 \
            or set((unified.get("status") or {}).values()) != {"PASS"}:
        raise AttestationError("unified release verification is not valid or not artifact-bound")
    if lifecycle.get("required_sequence") != [
        "TURN_OPENED", "SUBAGENT_STARTED", "SUBAGENT_STOPPED", "TASK_COMPLETED", "SESSION_ENDED"
    ]:
        raise AttestationError("lifecycle evidence does not contain the complete required sequence")
    if not lifecycle.get("project_id") or not lifecycle.get("repo_fingerprint"):
        raise AttestationError("lifecycle evidence lacks project/repository binding")
    if not _luna_model_proven(lifecycle):
        raise AttestationError("lifecycle evidence lacks proven Luna subagent model evidence")
    evidence_paths = {
        "plugin_list": plugin_list_path,
        "lifecycle": lifecycle_report_path,
        "package_validation": package_validation_path,
        "deterministic_build": deterministic_witness_path,
        "unified_verification": unified_verification_path,
    }
    if codex_version_evidence_path is not None:
        evidence_paths["codex_version"] = codex_version_evidence_path
    attestation: Dict[str, Any] = {
        "schema_version": "1.0",
        "package": PACKAGE,
        "version": VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact": {
            "name": artifact.name,
            "sha256": artifact_sha256,
            "size": artifact.stat().st_size,
        },
        "host": {
            "os": platform.system(),
            "codex_version": _codex_version(codex_version_evidence_path),
            "python_version": platform.python_version(),
        },
        "plugin": {
            "plugin_id": PLUGIN_ID,
            "marketplace": MARKETPLACE,
            "installed": True,
            "enabled": True,
            "version": plugin_item.get("version"),
        },
        "lifecycle": {
            "project_id": lifecycle.get("project_id"),
            "repo_fingerprint": lifecycle.get("repo_fingerprint"),
            "required_sequence": lifecycle.get("required_sequence"),
            "event_chain_valid": True,
            "actual_subagent_models": lifecycle.get("actual_subagent_models", []),
            "subagent_model_evidence": lifecycle.get("subagent_model_evidence", {}),
            "raw_identifiers_exported": False,
        },
        "validation": {
            "package_validation": "PASS",
            "deterministic_build": "PASS",
            "plugin_host_end_to_end": "PASS",
            "real_lifecycle": "PASS",
            "unified_release_verification": "PASS",
            "payload_identity": "PASS",
        },
        "security": {
            "execution_authorization": "NONE",
            "automatic_agent_ceiling": "gpt-5.6-terra + high",
            "prompt_or_response_exported": False,
            "absolute_evidence_paths_exported": False,
        },
        "evidence": {
            name: {"name": path.name, "sha256": sha256_file(path)}
            for name, path in sorted(evidence_paths.items())
        },
    }
    attestation["integrity"] = {"sha256": hashlib.sha256(_canonical(attestation)).hexdigest()}
    key = os.environ.get("CP_ASSISTANT_ATTESTATION_HMAC_KEY")
    if key:
        attestation["integrity"]["hmac_sha256"] = hmac.new(key.encode("utf-8"), _canonical(attestation), hashlib.sha256).hexdigest()
    return attestation


def verify_attestation(attestation_path: Path, artifact: Path) -> Dict[str, Any]:
    attestation = _load_object(attestation_path)
    integrity = attestation.get("integrity")
    if not isinstance(integrity, dict):
        raise AttestationError("attestation integrity block is missing")
    unsigned = dict(attestation)
    unsigned.pop("integrity", None)
    expected = hashlib.sha256(_canonical(unsigned)).hexdigest()
    if not hmac.compare_digest(str(integrity.get("sha256") or ""), expected):
        raise AttestationError("attestation content hash mismatch")
    key = os.environ.get("CP_ASSISTANT_ATTESTATION_HMAC_KEY")
    if key:
        hmac_value = integrity.get("hmac_sha256")
        if not hmac_value:
            raise AttestationError("attestation HMAC is required by the active environment")
        signed = dict(unsigned)
        signed["integrity"] = {"sha256": expected}
        actual_hmac = hmac.new(key.encode("utf-8"), _canonical(signed), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(hmac_value), actual_hmac):
            raise AttestationError("attestation HMAC mismatch")
    artifact_block = attestation.get("artifact") or {}
    if artifact_block.get("name") != artifact.name or artifact_block.get("sha256") != sha256_file(artifact):
        raise AttestationError("artifact does not match attestation")
    if artifact_block.get("size") != artifact.stat().st_size:
        raise AttestationError("artifact size does not match attestation")
    if attestation.get("version") != VERSION:
        raise AttestationError("attestation version mismatch")
    plugin = attestation.get("plugin") or {}
    if not (plugin.get("installed") is True and plugin.get("enabled") is True and plugin.get("version") == VERSION):
        raise AttestationError("attested Plugin state is incomplete")
    for name, record in (attestation.get("evidence") or {}).items():
        if not isinstance(record, dict):
            raise AttestationError("invalid evidence record: %s" % name)
        evidence_name = str(record.get("name") or "")
        if not evidence_name or Path(evidence_name).name != evidence_name:
            raise AttestationError("unsafe evidence name: %s" % name)
        evidence_path = attestation_path.parent / evidence_name
        if _is_reparse(evidence_path) or evidence_path.resolve().parent != attestation_path.parent.resolve():
            raise AttestationError("unsafe evidence path: %s" % name)
        if not evidence_path.is_file() or sha256_file(evidence_path) != record.get("sha256"):
            raise AttestationError("evidence hash mismatch: %s" % name)
    return {
        "ok": True,
        "artifact_sha256": artifact_block["sha256"],
        "plugin_version": plugin["version"],
        "codex_version": (attestation.get("host") or {}).get("codex_version"),
        "evidence_count": len(attestation.get("evidence") or {}),
        "hmac_verified": bool(key),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.4 release attestation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--artifact", required=True)
    create_parser.add_argument("--plugin-list", required=True)
    create_parser.add_argument("--lifecycle-report", required=True)
    create_parser.add_argument("--package-validation", required=True)
    create_parser.add_argument("--deterministic-witness", required=True)
    create_parser.add_argument("--unified-verification", required=True)
    create_parser.add_argument("--codex-version-evidence")
    create_parser.add_argument("--output", required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--attestation", required=True)
    verify_parser.add_argument("--artifact", required=True)
    arguments = parser.parse_args()
    if arguments.command == "create":
        result = create_attestation(
            Path(arguments.artifact),
            Path(arguments.plugin_list),
            Path(arguments.lifecycle_report),
            Path(arguments.package_validation),
            Path(arguments.deterministic_witness),
            Path(arguments.unified_verification),
            Path(arguments.codex_version_evidence) if arguments.codex_version_evidence else None,
        )
        output = Path(arguments.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    else:
        result = verify_attestation(Path(arguments.attestation), Path(arguments.artifact))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except AttestationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
