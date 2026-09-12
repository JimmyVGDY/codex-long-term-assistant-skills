#!/usr/bin/env python3
"""中文：下载固定的官方 Codex 包并校验两种登记摘要。

English: Download one frozen official Codex tarball and verify both registered digests.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from codex_compatibility import (  # noqa: E402
    CompatibilityError, load_registry, profile_for_version, verify_artifact_file,
)

MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_SOURCE_BYTES = 2 * 1024 * 1024
OFFICIAL_REPOSITORY = "https://github.com/openai/codex"
SOURCE_ASSERTIONS = {
    "USER_PROMPT_SUBMIT_EVENT": "UserPromptSubmit",
    "ASYNC_FIELD_PARSED": "let runs_async",
    "ASYNC_PROPAGATED_TO_COMMAND_HANDLER": "r#async: runs_async",
}
OPERATION_SOURCE_ASSERTIONS = {
    "PRE_TOOL_USE_INPUT": "struct PreToolUseCommandInput",
    "POST_TOOL_USE_INPUT": "struct PostToolUseCommandInput",
    "TOOL_USE_ID": "pub tool_use_id: String",
    "TOOL_RESPONSE": "pub tool_response: Value",
    "POST_TOOL_BLOCK_OUTPUT": "struct PostToolUseCommandOutputWire",
}
RESULT_SOURCE_ASSERTIONS = {
    "APPLY_PATCH_OUTPUT_ON_SUCCESS": "ApplyPatchToolOutput::from_text(content)",
    "POST_TOOL_PAYLOAD_FROM_RESULT": "result.post_tool_use_response",
    "POST_TOOL_RESPONSE_STRING": "Some(JsonValue::String(self.text.clone()))",
}


def _read_url(url: str, limit: int) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "codex-long-term-assistant-skills/7.9.0"},
    )
    chunks: list[bytes] = []
    total = 0
    with urllib.request.urlopen(request, timeout=120) as response:
        while True:
            chunk = response.read(min(1024 * 1024, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > limit:
                raise CompatibilityError("Codex 官方源码证据超过大小上限")
    return b"".join(chunks)


def _official_tag_commit(tag: str) -> str:
    ref_url = "https://api.github.com/repos/openai/codex/git/ref/tags/" + tag
    try:
        current = json.loads(_read_url(ref_url, MAX_SOURCE_BYTES).decode("utf-8"))["object"]
        for _ in range(3):
            object_type = current.get("type")
            object_sha = current.get("sha")
            if object_type == "commit" and isinstance(object_sha, str):
                return object_sha
            if object_type != "tag" or not isinstance(object_sha, str):
                break
            tag_url = "https://api.github.com/repos/openai/codex/git/tags/" + object_sha
            current = json.loads(_read_url(tag_url, MAX_SOURCE_BYTES).decode("utf-8"))["object"]
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompatibilityError("Codex 官方 tag 证据无效") from exc
    raise CompatibilityError("Codex 官方 tag 未解析到 commit")


def verify_native_async_sources() -> dict:
    registry = load_registry(ROOT / "config" / "codex-compatibility-v1.json", "7.9.0")
    verified = []
    for item in registry["versions"]:
        version = item["version"]
        evidence = item["native_async_user_prompt_submit"]
        if evidence["status"] != "SUPPORTED" or evidence["repository"] != OFFICIAL_REPOSITORY:
            raise CompatibilityError("Codex native async 官方源码证据未声明支持")
        resolved_commit = _official_tag_commit(evidence["tag"])
        if not hmac.compare_digest(resolved_commit, evidence["commit_sha"]):
            raise CompatibilityError("Codex native async tag 与 commit 不匹配")
        source_url = (
            "https://raw.githubusercontent.com/openai/codex/"
            + evidence["commit_sha"] + "/" + evidence["source_path"]
        )
        source = _read_url(source_url, MAX_SOURCE_BYTES)
        source_digest = hashlib.sha256(source).hexdigest()
        if not hmac.compare_digest(source_digest, evidence["source_sha256"]):
            raise CompatibilityError("Codex native async 官方源码摘要不匹配")
        try:
            source_text = source.decode("utf-8")
        except UnicodeError as exc:
            raise CompatibilityError("Codex native async 官方源码不是 UTF-8") from exc
        expected_assertions = set(evidence["verified_assertions"])
        observed_assertions = {
            name for name, marker in SOURCE_ASSERTIONS.items() if marker in source_text
        }
        if observed_assertions != expected_assertions:
            raise CompatibilityError("Codex native async 官方源码断言不匹配")
        verified.append({
            "version": version,
            "tag": evidence["tag"],
            "commit_sha": resolved_commit,
            "source_path": evidence["source_path"],
            "source_sha256": source_digest,
            "source_size": len(source),
            "verified_assertions": sorted(observed_assertions),
        })
        operation = item["native_apply_patch_operation"]
        if operation["status"] != "SUPPORTED" or operation["repository"] != OFFICIAL_REPOSITORY:
            raise CompatibilityError("Codex apply_patch operation 官方源码证据未声明支持")
        if (operation["tag"] != evidence["tag"]
                or operation["commit_sha"] != resolved_commit):
            raise CompatibilityError("Codex apply_patch operation tag 与 commit 不匹配")
        operation_url = (
            "https://raw.githubusercontent.com/openai/codex/"
            + operation["commit_sha"] + "/" + operation["source_path"]
        )
        operation_source = _read_url(operation_url, MAX_SOURCE_BYTES)
        operation_digest = hashlib.sha256(operation_source).hexdigest()
        if not hmac.compare_digest(operation_digest, operation["source_sha256"]):
            raise CompatibilityError("Codex apply_patch operation 官方源码摘要不匹配")
        try:
            operation_text = operation_source.decode("utf-8")
        except UnicodeError as exc:
            raise CompatibilityError("Codex apply_patch operation 官方源码不是 UTF-8") from exc
        observed_operation = {
            name for name, marker in OPERATION_SOURCE_ASSERTIONS.items()
            if marker in operation_text
        }
        if observed_operation != set(operation["verified_assertions"]):
            raise CompatibilityError("Codex apply_patch operation 官方源码断言不匹配")
        verified[-1]["apply_patch_operation"] = {
            "source_path": operation["source_path"],
            "source_sha256": operation_digest,
            "source_size": len(operation_source),
            "verified_assertions": sorted(observed_operation),
        }
        result_profile = registry["profiles"]["apply_patch_result"][
            item["apply_patch_result_profile"]
        ]
        result_sources = {}
        result_text = ""
        for kind in ("handler", "context"):
            source_path = result_profile[kind + "_path"]
            source_url = (
                "https://raw.githubusercontent.com/openai/codex/"
                + operation["commit_sha"] + "/" + source_path
            )
            result_source = _read_url(source_url, MAX_SOURCE_BYTES)
            result_digest = hashlib.sha256(result_source).hexdigest()
            if not hmac.compare_digest(result_digest, result_profile[kind + "_sha256"]):
                raise CompatibilityError("Codex apply_patch 结果合同官方源码摘要不匹配")
            try:
                result_text += result_source.decode("utf-8")
            except UnicodeError as exc:
                raise CompatibilityError("Codex apply_patch 结果合同官方源码不是 UTF-8") from exc
            result_sources[kind] = {
                "source_path": source_path,
                "source_sha256": result_digest,
                "source_size": len(result_source),
            }
        observed_result = {
            name for name, marker in RESULT_SOURCE_ASSERTIONS.items()
            if marker in result_text
        }
        if observed_result != set(result_profile["verified_assertions"]):
            raise CompatibilityError("Codex apply_patch 结果合同官方源码断言不匹配")
        verified[-1]["apply_patch_result"] = {
            "profile": item["apply_patch_result_profile"],
            "sources": result_sources,
            "verified_assertions": sorted(observed_result),
        }
    return {"status": "PASS", "repository": OFFICIAL_REPOSITORY, "verified_versions": verified}


def _write_external_report(path: Path, payload: dict) -> None:
    target = path.resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise CompatibilityError("官方源码证据报告必须写到仓库外")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=target.name + ".", suffix=".tmp", dir=target.parent,
            mode="w", encoding="utf-8", newline="\n", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def download(version: str, output: Path) -> dict:
    registry = load_registry(ROOT / "config" / "codex-compatibility-v1.json", "7.9.0")
    profile = profile_for_version(registry, version)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=output.name + ".", suffix=".tmp", dir=output.parent, delete=False,
        ) as handle:
            temporary = Path(handle.name)
            request = urllib.request.Request(
                profile["artifact"]["tarball"],
                headers={"User-Agent": "codex-long-term-assistant-skills/7.9.0"},
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_ARTIFACT_BYTES:
                        raise CompatibilityError("Codex 固定制品超过大小上限")
                    handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        report = verify_artifact_file(registry, version, temporary)
        os.replace(temporary, output)
        report["path"] = str(output)
        return report
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version")
    parser.add_argument("--output")
    parser.add_argument("--verify-native-async-sources", action="store_true")
    parser.add_argument("--report-output")
    args = parser.parse_args()
    try:
        if args.verify_native_async_sources:
            if args.version or args.output:
                raise CompatibilityError("官方源码证据复核不能同时下载 npm 制品")
            report = verify_native_async_sources()
        else:
            if not args.version or not args.output:
                raise CompatibilityError("下载固定制品必须同时提供 --version 与 --output")
            report = download(args.version, Path(args.output))
        payload = {"ok": True, **report}
        if args.report_output:
            _write_external_report(Path(args.report_output), payload)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
