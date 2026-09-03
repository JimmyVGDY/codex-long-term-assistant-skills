#!/usr/bin/env python3
"""中文：失败关闭的 V7.4.1 端到端发行验证器。

English: Fail-closed V7.4.1 end-to-end release verifier.
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

VERSION = "7.4.1"
TARGET_CODEX_VERSION = "0.153.0"
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
    with tempfile.TemporaryDirectory(prefix="cp-v66-verify-") as temporary:
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


def _verify_model_gate(report: Mapping[str, Any]) -> Dict[str, Any]:
    if report.get("ok") is not True or report.get("requested_model_policy") != "PASS" \
            or report.get("automatic_ceiling") not in {"gpt-5.6-terra + high", "gpt-5.6-terra / high"}:
        raise VerificationError("自动模型门禁报告无效")
    if isinstance(report.get("allow_cases"), list) and isinstance(report.get("deny_cases"), list):
        allowed = {(str(row.get("model") or ""), str(row.get("reasoning_effort") or "")): not bool(row.get("denied"))
                   for row in report["allow_cases"] if isinstance(row, dict) and row.get("exit_code") == 0}
        denied = {(str(row.get("model") or ""), str(row.get("reasoning_effort") or "")): bool(row.get("denied"))
                  for row in report["deny_cases"] if isinstance(row, dict) and row.get("exit_code") == 0}
        required_allow = {("gpt-5.6-luna", "low"), ("gpt-5.6-luna", "medium"),
                          ("gpt-5.6-terra", "medium"), ("gpt-5.6-terra", "high")}
        required_deny = {("gpt-5.6-terra", "xhigh"), ("gpt-5.6-sol", "high")}
        if not all(allowed.get(key) is True for key in required_allow) or not all(denied.get(key) is True for key in required_deny):
            raise VerificationError("自动模型门禁未证明默认成本路线与 Terra High 上限")
        return {"automatic_ceiling": "gpt-5.6-terra / high",
                "requested_model_policy": "PASS", "required_cases": len(required_allow) + len(required_deny)}
    rows = report.get("cases")
    if not isinstance(rows, list):
        raise VerificationError("自动模型门禁 cases 无效")
    observed: Dict[tuple[str, str], str] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("pass") is not True or row.get("returncode") != 0:
            raise VerificationError("自动模型门禁存在失败用例")
        key = (str(row.get("model") or ""), str(row.get("reasoning_effort") or ""))
        actual = str(row.get("actual") or "")
        if actual not in {"allow", "deny"} or (key in observed and observed[key] != actual):
            raise VerificationError("自动模型门禁用例冲突")
        observed[key] = actual
    required = {
        ("gpt-5.6-luna", "low"): "allow",
        ("gpt-5.6-luna", "medium"): "allow",
        ("gpt-5.6-terra", "medium"): "allow",
        ("gpt-5.6-terra", "high"): "allow",
        ("gpt-5.6-terra", "xhigh"): "deny",
        ("gpt-5.6-sol", "low"): "deny",
    }
    if any(observed.get(key) != decision for key, decision in required.items()):
        raise VerificationError("自动模型门禁未证明默认成本路线与 Terra High 上限")
    return {"automatic_ceiling": report["automatic_ceiling"], "required_cases": len(required)}


def _legacy_luna_model_proven(lifecycle: Mapping[str, Any]) -> bool:
    if "gpt-5.6-luna" in lifecycle.get("actual_subagent_models", []):
        return True
    evidence = lifecycle.get("subagent_model_evidence") or {}
    return isinstance(evidence, dict) and evidence.get("status") == "PASS" \
        and evidence.get("expected_model") == "gpt-5.6-luna" \
        and evidence.get("actual_model_fact_preserved") is True \
        and evidence.get("hook_payload_match") is True


def verify_release(artifact: Path, package_validation: Mapping[str, Any], witness: Mapping[str, Any],
                   plugin_list: Mapping[str, Any], lifecycle: Mapping[str, Any],
                   model_gate_report: Mapping[str, Any] | None, codex_evidence: Mapping[str, Any],
                   payload_report: Mapping[str, Any]) -> Dict[str, Any]:
    artifact = artifact.resolve()
    if not artifact.is_file():
        raise VerificationError("artifact 不存在")
    artifact_hash = _sha256(artifact)
    artifact_payload = _artifact_payload(artifact)
    package_ok = package_validation.get("ok") is True and package_validation.get("version") == VERSION
    if not package_ok:
        raise VerificationError("包内验证未证明 V%s PASS" % VERSION)
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
        raise VerificationError("Plugin 未精确证明 installed/enabled/version=%s" % VERSION)
    lifecycle_ok = lifecycle.get("ok") is True and (lifecycle.get("event_chain") or {}).get("valid") is True
    project_id = str(lifecycle.get("project_id") or "")
    repo_fingerprint = str(lifecycle.get("repo_fingerprint") or "")
    if not lifecycle_ok or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", project_id) \
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", repo_fingerprint):
        raise VerificationError("生命周期或项目双重绑定证据无效")
    if lifecycle.get("requested_model_policy") != "PASS":
        raise VerificationError("生命周期未绑定 requested_model_policy=PASS")
    if lifecycle.get("runtime_model_evidence") not in {"VERIFIED", "UNAVAILABLE"}:
        raise VerificationError("runtime_model_evidence 口径无效")
    diagnostic = lifecycle.get("diagnostic_model_observation")
    if not isinstance(diagnostic, str) or not diagnostic:
        raise VerificationError("diagnostic_model_observation 缺失")
    if model_gate_report is not None:
        model_gate = _verify_model_gate(model_gate_report)
    elif _legacy_luna_model_proven(lifecycle):
        model_gate = {"automatic_ceiling": "legacy-lifecycle-model-proof", "required_cases": 0}
    else:
        raise VerificationError("缺少已安装模型门禁报告，且生命周期没有可信 Hook 模型事实")
    version_text = str(codex_evidence.get("codex_version") or "")
    capability = codex_evidence.get("capability_profile") or {}
    host_ok = bool(re.search(r"(?:^|\s)%s(?:\s|$)" % re.escape(TARGET_CODEX_VERSION),
                             version_text)) and capability.get("ok") is True
    if not host_ok:
        raise VerificationError("Codex %s 或 Plugin capability 未证明" % TARGET_CODEX_VERSION)
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
                   "lifecycle": "PASS", "model_gate": "PASS", "payload": "PASS"},
        "requested_model_policy": lifecycle["requested_model_policy"],
        "runtime_model_evidence": lifecycle["runtime_model_evidence"],
        "diagnostic_model_observation": lifecycle["diagnostic_model_observation"],
        "evidence": {"plugin": matches[0], "codex_version": version_text,
                     "event_chain_head": (lifecycle.get("event_chain") or {}).get("head"),
                     "model_gate": model_gate,
                     "subagent_model_evidence": lifecycle.get("subagent_model_evidence") or {
                         "actual_subagent_models": lifecycle.get("actual_subagent_models", [])
                     }},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V7.4 端到端发行验证")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--package-validation", required=True)
    parser.add_argument("--build-witness", required=True)
    parser.add_argument("--plugin-list", required=True)
    parser.add_argument("--lifecycle", required=True)
    parser.add_argument("--model-gate-report")
    parser.add_argument("--codex-evidence", required=True)
    parser.add_argument("--payload-report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    try:
        result = verify_release(
            Path(args.artifact), _load(Path(args.package_validation), "package-validation"),
            _load(Path(args.build_witness), "build-witness"), _load(Path(args.plugin_list), "plugin-list"),
            _load(Path(args.lifecycle), "lifecycle"),
            _load(Path(args.model_gate_report), "model-gate-report") if args.model_gate_report else None,
            _load(Path(args.codex_evidence), "codex-evidence"),
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
