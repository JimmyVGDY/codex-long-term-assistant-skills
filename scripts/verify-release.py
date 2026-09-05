#!/usr/bin/env python3
"""中文：失败关闭的 V7.4.6 端到端发行验证器。

English: Fail-closed V7.4.6 end-to-end release verifier.
"""
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

VERSION = "7.4.6"
TARGET_CODEX_VERSION = "0.153.4"
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
    with tempfile.TemporaryDirectory(prefix="cp-v743-verify-") as temporary:
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
        valid_roots = {"Codex-Skills-V%s-zh-CN" % VERSION, "Codex-Skills-V%s-en" % VERSION}
        if len(children) != 1 or children[0].name not in valid_roots:
            raise VerificationError("artifact 根目录不是受支持的 V%s 语言包" % VERSION)
        package_root = children[0]
        try:
            manifest = load_manifest(package_root / MANIFEST_NAME)
            report = verify_payload(package_root, manifest, package=PACKAGE, version=VERSION)
            report["locale"] = package_root.name.removeprefix("Codex-Skills-V%s-" % VERSION)
            return report
        except PayloadIntegrityError as exc:
            raise VerificationError("artifact payload 身份失败: %s" % exc) from exc


def _verify_dispatch_policy(report: Mapping[str, Any]) -> Dict[str, Any]:
    if (
        report.get("ok") is not True
        or report.get("schema_version") != "2.0"
        or report.get("dispatch_policy_status") != "PASS"
        or report.get("automatic_ceiling_profile") != "terra-high"
    ):
        raise VerificationError("派发策略门禁报告无效")
    rows = report.get("cases")
    if not isinstance(rows, list) or not rows:
        raise VerificationError("派发策略门禁 cases 无效")
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("pass") is not True or row.get("exit_code") != 0:
            raise VerificationError("派发策略门禁存在失败用例")
        case_id = str(row.get("case_id") or "")
        if not case_id or case_id in ids or row.get("observed") != row.get("expected"):
            raise VerificationError("派发策略门禁用例无效或冲突")
        ids.add(case_id)
        prohibited = {"model", "reasoning_effort", "actual" + "_model", "runtime" + "_model"}
        if prohibited.intersection(row):
            raise VerificationError("派发策略证据包含宿主模型身份字段")
    privacy = report.get("privacy") or {}
    if privacy.get("host_model_information_collected") is not False \
            or privacy.get("host_model_information_exported") is not False:
        raise VerificationError("派发策略报告的模型身份隐私声明无效")
    return {"automatic_ceiling_profile": "terra-high", "required_cases": len(rows)}


def verify_release(
    artifact: Path,
    package_validation: Mapping[str, Any],
    witness: Mapping[str, Any],
    plugin_list: Mapping[str, Any],
    lifecycle: Mapping[str, Any],
    dispatch_policy_report: Mapping[str, Any],
    codex_evidence: Mapping[str, Any],
    payload_report: Mapping[str, Any],
) -> Dict[str, Any]:
    artifact = artifact.resolve()
    if not artifact.is_file():
        raise VerificationError("artifact 不存在")
    artifact_hash = _sha256(artifact)
    artifact_payload = _artifact_payload(artifact)
    if package_validation.get("ok") is not True or package_validation.get("version") != VERSION:
        raise VerificationError("包内验证未证明 V%s PASS" % VERSION)
    if not (
        witness.get("ok") is True
        and witness.get("reproducible") is True
        and witness.get("version") == VERSION
        and witness.get("artifact_sha256") == artifact_hash
    ):
        raise VerificationError("确定性构建证明与 artifact 不一致")

    installed = plugin_list.get("installed")
    if not isinstance(installed, list):
        raise VerificationError("Plugin list schema 无效")
    matches = [
        item
        for item in installed
        if isinstance(item, dict)
        and (
            item.get("pluginId") == PLUGIN_ID
            or (item.get("name") == PACKAGE and item.get("marketplaceName") == MARKETPLACE)
        )
    ]
    if not (
        len(matches) == 1
        and matches[0].get("installed") is True
        and matches[0].get("enabled") is True
        and str(matches[0].get("version") or "") == VERSION
    ):
        raise VerificationError("Plugin 未精确证明 installed/enabled/version=%s" % VERSION)

    lifecycle_ok = (
        lifecycle.get("ok") is True
        and lifecycle.get("schema_version") == "2.0"
        and (lifecycle.get("event_chain") or {}).get("valid") is True
    )
    project_id = str(lifecycle.get("project_id") or "")
    repo_fingerprint = str(lifecycle.get("repo_fingerprint") or "")
    if not lifecycle_ok or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", project_id) \
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", repo_fingerprint):
        raise VerificationError("生命周期或项目双重绑定证据无效")
    privacy = lifecycle.get("privacy") or {}
    if privacy.get("host_model_information_read") is not False \
            or privacy.get("host_model_information_exported") is not False:
        raise VerificationError("生命周期模型身份隐私声明无效")
    dispatch_policy = _verify_dispatch_policy(dispatch_policy_report)

    version_text = str(codex_evidence.get("codex_version") or "")
    capability = codex_evidence.get("capability_profile") or {}
    if not (
        re.search(r"(?:^|\s)%s(?:\s|$)" % re.escape(TARGET_CODEX_VERSION), version_text)
        and capability.get("ok") is True
    ):
        raise VerificationError("Codex %s 或 Plugin capability 未证明" % TARGET_CODEX_VERSION)
    reports = [payload_report.get(name) for name in ("source", "marketplace", "cache")]
    if not all(isinstance(item, dict) and item.get("ok") is True for item in reports):
        raise VerificationError("安装 payload 报告不完整")
    digests = {str(item.get("payload_digest") or "") for item in reports if isinstance(item, dict)}
    digests.add(str(artifact_payload.get("payload_digest") or ""))
    if len(digests) != 1 or "" in digests:
        raise VerificationError("ZIP/源/Marketplace/cache payload digest 不一致")

    return {
        "ok": True,
        "schema_version": 2,
        "version": VERSION,
        "artifact_sha256": artifact_hash,
        "payload_digest": artifact_payload["payload_digest"],
        "project_id": project_id,
        "repo_fingerprint": repo_fingerprint,
        "status": {
            "package": "PASS",
            "artifact": "PASS",
            "host": "PASS",
            "plugin": "PASS",
            "lifecycle": "PASS",
            "dispatch_policy": "PASS",
            "payload": "PASS",
        },
        "privacy": {
            "host_model_information_read": False,
            "host_model_information_exported": False,
        },
        "evidence": {
            "plugin": matches[0],
            "codex_version": version_text,
            "event_chain_head": (lifecycle.get("event_chain") or {}).get("head"),
            "dispatch_policy": dispatch_policy,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V7.4.6 端到端发行验证")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--package-validation", required=True)
    parser.add_argument("--build-witness", required=True)
    parser.add_argument("--plugin-list", required=True)
    parser.add_argument("--lifecycle", required=True)
    parser.add_argument("--dispatch-policy-report", required=True)
    parser.add_argument("--codex-evidence", required=True)
    parser.add_argument("--payload-report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    try:
        result = verify_release(
            Path(args.artifact),
            _load(Path(args.package_validation), "package-validation"),
            _load(Path(args.build_witness), "build-witness"),
            _load(Path(args.plugin_list), "plugin-list"),
            _load(Path(args.lifecycle), "lifecycle"),
            _load(Path(args.dispatch_policy_report), "dispatch-policy-report"),
            _load(Path(args.codex_evidence), "codex-evidence"),
            _load(Path(args.payload_report), "payload-report"),
        )
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
