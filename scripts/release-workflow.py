#!/usr/bin/env python3
"""中文：为 GitHub Release 工作流生成受约束的版本元数据、说明和校验和。

English: Generate constrained version metadata, notes, and checksums for GitHub Releases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PLACEHOLDER = "OWNER/REPOSITORY"
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ReleaseWorkflowError(RuntimeError):
    """中文：表示发布输入、边界或受管产物不满足失败关闭条件。

    English: Report a release input, boundary, or managed-artifact fail-closed violation.
    """


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ReleaseWorkflowError("JSON top level must be an object: %s" % path)
    return value


def _is_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        return os.name == "nt" and bool(
            path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        )
    except (AttributeError, OSError):
        return False


def release_metadata(root: Path = ROOT, tag: str = "") -> dict[str, str]:
    root = root.resolve()
    manifest = _read_object(root / "manifest.json")
    plugin = _read_object(root / ".codex-plugin" / "plugin.json")
    version = manifest.get("version")
    plugin_version = plugin.get("version")
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise ReleaseWorkflowError("manifest version must be semantic x.y.z")
    if plugin_version != version:
        raise ReleaseWorkflowError("manifest and Plugin versions do not match")
    expected_tag = "v" + version
    if tag and tag != expected_tag:
        raise ReleaseWorkflowError(
            "release tag %s does not match package version %s" % (tag, expected_tag)
        )
    notes_zh = root / "docs" / "releases" / expected_tag / "RELEASE_NOTES.md"
    notes_en = root / "docs" / "releases" / expected_tag / "RELEASE_NOTES.en.md"
    for path in (notes_zh, notes_en):
        if not path.is_file() or _is_link(path):
            raise ReleaseWorkflowError("release notes are missing or unsafe: %s" % path)
    return {
        "version": version,
        "tag": expected_tag,
        "archive_zh": "Codex-Skills-V%s-zh-CN.zip" % version,
        "archive_en": "Codex-Skills-V%s-en.zip" % version,
        "witness_zh": "witness-zh-CN.json",
        "witness_en": "witness-en.json",
        "provenance": "Codex-Skills-V%s-provenance.json" % version,
        "checksums": "SHA256SUMS.txt",
        "release_notes": "GITHUB_RELEASE_NOTES.md",
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(directory: Path, output: Path, root: Path = ROOT) -> dict[str, Any]:
    metadata = release_metadata(root)
    directory = directory.resolve()
    output = output.resolve()
    if output.parent != directory or not directory.is_dir() or _is_link(directory):
        raise ReleaseWorkflowError("checksum output must stay in a safe release directory")
    required = {
        metadata["archive_zh"], metadata["archive_en"],
        metadata["witness_zh"], metadata["witness_en"],
    }
    optional = {metadata["provenance"]}
    observed = {path.name for path in directory.iterdir() if path.is_file() and path != output}
    missing = sorted(required - observed)
    unknown = sorted(observed - required - optional - {metadata["release_notes"]})
    if missing or unknown:
        raise ReleaseWorkflowError(
            "release artifact set is incomplete or unknown: missing=%s unknown=%s"
            % (missing, unknown)
        )
    subjects = sorted(required | (observed & optional))
    for name in subjects:
        path = directory / name
        if _is_link(path):
            raise ReleaseWorkflowError("release artifact is a link: %s" % name)
    lines = ["%s  %s" % (_sha256(directory / name), name) for name in subjects]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return {"ok": True, "version": metadata["version"], "files": subjects,
            "checksums": output.name}


def verify_candidate(directory: Path, root: Path = ROOT) -> dict[str, Any]:
    """中文：在下载到发布之间重新绑定精确文件集、摘要与构建见证。

    English: Re-bind the exact file set, checksums, and build witnesses after download.
    """
    metadata = release_metadata(root)
    directory = directory.resolve()
    if not directory.is_dir() or _is_link(directory):
        raise ReleaseWorkflowError("release candidate directory is missing or unsafe")
    subjects = {
        metadata["archive_zh"], metadata["archive_en"],
        metadata["witness_zh"], metadata["witness_en"], metadata["provenance"],
    }
    expected = subjects | {metadata["checksums"], metadata["release_notes"]}
    children = list(directory.iterdir())
    unsafe = sorted(path.name for path in children if not path.is_file() or _is_link(path))
    observed = {path.name for path in children}
    if unsafe or observed != expected:
        raise ReleaseWorkflowError(
            "release candidate file set mismatch: missing=%s unknown=%s unsafe=%s"
            % (sorted(expected - observed), sorted(observed - expected), unsafe)
        )

    checksum_path = directory / metadata["checksums"]
    checksums: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8-sig").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]{0,191})", line)
        if not match or match.group(2) in checksums:
            raise ReleaseWorkflowError("SHA256SUMS.txt contains an invalid or duplicate entry")
        checksums[match.group(2)] = match.group(1)
    if set(checksums) != subjects:
        raise ReleaseWorkflowError("SHA256SUMS.txt does not cover the exact release subjects")
    for name, expected_digest in checksums.items():
        if _sha256(directory / name) != expected_digest:
            raise ReleaseWorkflowError("release candidate checksum mismatch: %s" % name)

    witness_pairs = (
        (metadata["witness_zh"], metadata["archive_zh"], "zh-CN"),
        (metadata["witness_en"], metadata["archive_en"], "en"),
    )
    for witness_name, archive_name, locale in witness_pairs:
        witness = _read_object(directory / witness_name)
        archive = directory / archive_name
        digest = checksums[archive_name]
        if witness.get("ok") is not True or witness.get("reproducible") is not True \
                or witness.get("version") != metadata["version"] or witness.get("locale") != locale \
                or witness.get("artifact_sha256") != digest \
                or witness.get("first_sha256") != digest or witness.get("second_sha256") != digest \
                or witness.get("artifact_size") != archive.stat().st_size:
            raise ReleaseWorkflowError("build witness is not bound to the archive: %s" % witness_name)
    _read_object(directory / metadata["provenance"])
    return {
        "ok": True,
        "version": metadata["version"],
        "files": sorted(expected),
        "subjects": sorted(subjects),
    }


def write_release_notes(output: Path, root: Path = ROOT) -> dict[str, str]:
    metadata = release_metadata(root)
    notes_root = root.resolve() / "docs" / "releases" / metadata["tag"]
    bodies: list[str] = []
    for name in ("RELEASE_NOTES.md", "RELEASE_NOTES.en.md"):
        lines = (notes_root / name).read_text(encoding="utf-8-sig").splitlines()
        if len(lines) >= 3 and lines[2].startswith(("English: ", "Chinese: ")):
            del lines[2]
        bodies.append("\n".join(lines).strip())
    chinese, english = bodies
    evidence = """## Artifact provenance

This page is created as a draft. Automation never publishes it or replaces an existing Release.

```shell
gh attestation verify Codex-Skills-V{version}-zh-CN.zip --repo {repository}
gh attestation verify Codex-Skills-V{version}-en.zip --repo {repository}
```

- `SHA256SUMS.txt`: downloadable artifact digests
- `witness-zh-CN.json`, `witness-en.json`: byte-reproducible build witnesses
- `Codex-Skills-V{version}-provenance.json`: signed attestation bundle
""".format(version=metadata["version"], repository=REPOSITORY_PLACEHOLDER)
    text = chinese + "\n\n---\n\n" + english + "\n\n---\n\n" + evidence
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8", newline="\n")
    return {"ok": True, "version": metadata["version"], "notes": output.name}


def _render_metadata(metadata: dict[str, str], output_format: str) -> str:
    if output_format == "github":
        return "\n".join("%s=%s" % (key, value) for key, value in metadata.items()) + "\n"
    return json.dumps({"ok": True, **metadata}, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Constrained bilingual GitHub Release helper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    metadata_parser = subparsers.add_parser("metadata")
    metadata_parser.add_argument("--tag", default="")
    metadata_parser.add_argument("--format", choices=("json", "github"), default="json")
    checksum_parser = subparsers.add_parser("checksums")
    checksum_parser.add_argument("--directory", required=True)
    checksum_parser.add_argument("--output", required=True)
    verify_parser = subparsers.add_parser("verify-candidate")
    verify_parser.add_argument("--directory", required=True)
    notes_parser = subparsers.add_parser("notes")
    notes_parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    if arguments.command == "metadata":
        print(_render_metadata(release_metadata(tag=arguments.tag), arguments.format), end="")
    elif arguments.command == "checksums":
        result = write_checksums(Path(arguments.directory), Path(arguments.output))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    elif arguments.command == "verify-candidate":
        result = verify_candidate(Path(arguments.directory))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        result = write_release_notes(Path(arguments.output))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ReleaseWorkflowError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=os.sys.stderr)
        raise SystemExit(2)
