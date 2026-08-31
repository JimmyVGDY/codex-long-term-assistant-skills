#!/usr/bin/env python3
"""Fail-closed V6.4 end-to-end release verifier."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Mapping

from payload_integrity import MANIFEST_NAME, PayloadIntegrityError, load_manifest, verify_payload

VERSION = "6.4.0"
PACKAGE = "codex-cross-project-engineering-assistant"
MARKETPLACE = "cp-assistant-local"
PLUGIN_ID = PACKAGE + "@" + MARKETPLACE


class VerificationError(RuntimeError):
    pass


def _load(path: Path, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError("%s 证据无法读取: %s" % (label, path)) from exc
    if not isinstance(value, dict):
        raise VerificationError("%s 证据必须为 JSON 对象" % label)
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_payload(artifact: Path) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cp-v64-verify-") as temporary:
        root = Path(temporary)
        try:
            with zipfile.ZipFile(artifact, "r") as archive:
                names = archive.namelist()
                if not names or any(".." in Path(name).parts or name.startswith(("/", "\\")) for name in names):
                    raise VerificationError("artifact ZIP 路径不安全")
                archive.extractall(root)
        except (OSError, zipfile.BadZipFile) as exc:
            raise VerificationError("artifact 不是有效 ZIP") from exc
        children = [item for item in root.iterdir() if item.is_dir()]
        if len(children) != 1 or children[0].name != "Codex-Skills-V6.4":
            raise VerificationError("artifact 根目录不是 Codex-Skills-V6.4")
        package_root = children[0]
        try:
            manifest = load_manifest(package_root / MANIFEST_NAME)
            return verify_payload(package_root, manifest, package=PACKAGE, version=VERSION)
        except PayloadIntegrityError as exc:
            raise VerificationError("artifact payload 身份失败: %s" % exc) from exc


def _luna_model_proven(lifecycle: Mapping[str, Any]) -> bool:
    if "gpt-5.6-luna" in lifecycle.get("actual_subagent_models", []):
        return True
    evidence = lifecycle.get("subagent_model_evidence") or {}
    return isinstance(evidence, dict) and evidence.get("status") == "PASS" \
        and evidence.get("expected_model") == "gpt-5.6-luna" \
        and evidence.get("actual_model_fact_preserved") is True \
        and (evidence.get("hook_payload_match") is True or evidence.get("host_session_match") is True)


def verify_release(artifact: Path, package_validation: Mapping[str, Any], witness: Mapping[str, Any],
                   plugin_list: Mapping[str, Any], lifecycle: Mapping[str, Any],
                   codex_evidence: Mapping[str, Any], payload_report: Mapping[str, Any]) -> Dict[str, Any]:
    artifact = artifact.resolve()
    if not artifact.is_file():
        raise VerificationError("artifact 不存在")
    artifact_hash = _sha256(artifact)
    artifact_payload = _artifact_payload(artifact)
    package_ok = package_validation.get("ok") is True and package_validation.get("version") == VERSION
    if not package_ok:
        raise VerificationError("包内验证未证明 V6.4 PASS")
    artifact_ok = (witness.get("ok") is True and witness.get("reproducible") is True
                   and witness.get("version") == VERSION and witness.get("artifact_sha256") == artifact_hash)
    if not artifact_ok:
        raise VerificationError("确定性构建证明与 artifact 不一致")
    installed = plugin_list.get("installed")
    if not isinstance(installed, list):
        raise VerificationError("Plugin list schema 无效")
    matches = [item for item in installed if isinstance(item, dict)
               and (item.get("pluginId") == PLUGIN_ID or
                    (item.get("name") == PACKAGE and item.get("marketplaceName") == MARKETPLACE))]
    plugin_ok = len(matches) == 1 and matches[0].get("installed") is True and matches[0].get("enabled") is True \
        and str(matches[0].get("version") or "") == VERSION
    if not plugin_ok:
        raise VerificationError("Plugin 未精确证明 installed/enabled/version=6.4.0")
    lifecycle_ok = lifecycle.get("ok") is True and (lifecycle.get("event_chain") or {}).get("valid") is True
    project_id = str(lifecycle.get("project_id") or "")
    repo_fingerprint = str(lifecycle.get("repo_fingerprint") or "")
    if not lifecycle_ok or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", project_id) \
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", repo_fingerprint):
        raise VerificationError("生命周期或项目双重绑定证据无效")
    if not _luna_model_proven(lifecycle):
        raise VerificationError("生命周期未证明 Luna Reviewer 模型事实")
    version_text = str(codex_evidence.get("codex_version") or "")
    capability = codex_evidence.get("capability_profile") or {}
    host_ok = bool(re.search(r"(?:^|\s)0\.150\.1(?:\s|$)", version_text)) and capability.get("ok") is True
    if not host_ok:
        raise VerificationError("Codex 0.150.1 或 Plugin capability 未证明")
    reports = [payload_report.get(name) for name in ("source", "marketplace", "cache")]
    if not all(isinstance(item, dict) and item.get("ok") is True for item in reports):
        raise VerificationError("安装 payload 报告不完整")
    digests = {str(item.get("payload_digest") or "") for item in reports if isinstance(item, dict)}
    digests.add(str(artifact_payload.get("payload_digest") or ""))
    payload_ok = len(digests) == 1 and "" not in digests
    if not payload_ok:
        raise VerificationError("ZIP/源/Marketplace/cache payload digest 不一致")
    return {
        "ok": True,
        "schema_version": 1,
        "version": VERSION,
        "artifact_sha256": artifact_hash,
        "payload_digest": artifact_payload["payload_digest"],
        "project_id": project_id,
        "repo_fingerprint": repo_fingerprint,
        "status": {"package": "PASS", "artifact": "PASS", "host": "PASS", "plugin": "PASS",
                   "lifecycle": "PASS", "payload": "PASS"},
        "evidence": {"plugin": matches[0], "codex_version": version_text,
                     "event_chain_head": (lifecycle.get("event_chain") or {}).get("head"),
                     "subagent_model_evidence": lifecycle.get("subagent_model_evidence") or {
                         "actual_subagent_models": lifecycle.get("actual_subagent_models", [])
                     }},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.4 端到端发行验证")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--package-validation", required=True)
    parser.add_argument("--build-witness", required=True)
    parser.add_argument("--plugin-list", required=True)
    parser.add_argument("--lifecycle", required=True)
    parser.add_argument("--codex-evidence", required=True)
    parser.add_argument("--payload-report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    try:
        result = verify_release(
            Path(args.artifact), _load(Path(args.package_validation), "package-validation"),
            _load(Path(args.build_witness), "build-witness"), _load(Path(args.plugin_list), "plugin-list"),
            _load(Path(args.lifecycle), "lifecycle"), _load(Path(args.codex_evidence), "codex-evidence"),
            _load(Path(args.payload_report), "payload-report"))
    except VerificationError as exc:
        result = {"ok": False, "version": VERSION, "error": str(exc)}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
