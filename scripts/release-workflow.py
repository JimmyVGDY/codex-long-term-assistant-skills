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
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PLACEHOLDER = "OWNER/REPOSITORY"
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
HAN_PATTERN = re.compile(r"[\u3400-\u9fff]")
RELEASE_NAME_MAX_CODEPOINTS = {"zh-CN": 30, "en": 80}
RELEASE_TITLE_MAX_CODEPOINTS = 125
RELEASE_TITLE_MAX_UTF8_BYTES = 200
GENERIC_RELEASE_NAMES = {
    "zh-CN": {"发行候选", "中英文发行候选"},
    "en": {"release candidate", "bilingual release candidate"},
}


class ReleaseWorkflowError(RuntimeError):
    """中文：表示发布输入、边界或受管产物不满足失败关闭条件。

    English: Report a release input, boundary, or managed-artifact fail-closed violation.
    """


def verify_commit_on_master(
    root: Path = ROOT,
    commit: str = "HEAD",
    master_ref: str = "origin/master",
) -> dict[str, str]:
    """中文：失败关闭地证明候选提交已经属于可信远端 master 历史。

    English: Fail closed unless the candidate commit belongs to trusted origin/master history.
    """
    root = root.resolve()

    def git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        if check and result.returncode:
            raise ReleaseWorkflowError(
                "release master binding is unavailable: %s" % " ".join(arguments)
            )
        return result

    commit_sha = git("rev-parse", "%s^{commit}" % commit).stdout.strip()
    master_sha = git("rev-parse", "%s^{commit}" % master_ref).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha) \
            or not re.fullmatch(r"[0-9a-f]{40}", master_sha):
        raise ReleaseWorkflowError("release master binding returned an invalid commit")
    if git("merge-base", "--is-ancestor", commit_sha, master_sha, check=False).returncode != 0:
        raise ReleaseWorkflowError("release commit is not contained in origin/master")
    return {"ok": "true", "commit": commit_sha, "master": master_sha}


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


def _release_name(value: Any, locale: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReleaseWorkflowError("%s release_name must be a non-empty trimmed string" % locale)
    if len(value) > RELEASE_NAME_MAX_CODEPOINTS[locale]:
        raise ReleaseWorkflowError("%s release_name is too long" % locale)
    if any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in value):
        raise ReleaseWorkflowError("%s release_name contains control characters" % locale)
    if value.casefold() in GENERIC_RELEASE_NAMES[locale]:
        raise ReleaseWorkflowError("%s release_name must describe this release" % locale)
    if locale == "zh-CN" and not HAN_PATTERN.search(value):
        raise ReleaseWorkflowError("zh-CN release_name must contain Chinese text")
    if locale == "en" and HAN_PATTERN.search(value):
        raise ReleaseWorkflowError("en release_name must not contain Chinese text")
    return value


def _release_title(version: str, chinese: str, english: str) -> str:
    value = "V%s | %s / %s" % (version, chinese, english)
    if len(value) > RELEASE_TITLE_MAX_CODEPOINTS \
            or len(value.encode("utf-8")) > RELEASE_TITLE_MAX_UTF8_BYTES:
        raise ReleaseWorkflowError("combined release title is too long")
    return value


def release_metadata(root: Path = ROOT, tag: str = "") -> dict[str, str]:
    root = root.resolve()
    manifest_path = root / "manifest.json"
    plugin_path = root / ".codex-plugin" / "plugin.json"
    localization_path = root / "locales" / "en" / "manifest-localization.json"
    for path in (manifest_path, plugin_path, localization_path):
        if not path.is_file() or _is_link(path):
            raise ReleaseWorkflowError("release metadata is missing or unsafe: %s" % path)
    manifest = _read_object(manifest_path)
    plugin = _read_object(plugin_path)
    localization = _read_object(localization_path)
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
    release_name_zh = _release_name(manifest.get("release_name"), "zh-CN")
    release_name_en = _release_name(localization.get("release_name"), "en")
    return {
        "version": version,
        "tag": expected_tag,
        "release_title": _release_title(version, release_name_zh, release_name_en),
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
    output.write_bytes(checksum_bytes({name: _sha256(directory / name) for name in subjects}))
    return {"ok": True, "version": metadata["version"], "files": subjects,
            "checksums": output.name}


def checksum_bytes(hashes: dict[str, str]) -> bytes:
    return "".join(f"{hashes[name]}  {name}\n" for name in sorted(hashes)).encode("utf-8")


def verify_build_witness(witness_path: Path, archive: Path, version: str, locale: str, digest: str) -> None:
    if not witness_path.is_file() or _is_link(witness_path):
        raise ReleaseWorkflowError("missing or unsafe build witness: %s" % witness_path)
    witness = _read_object(witness_path)
    if (witness.get("ok") is not True or witness.get("reproducible") is not True
            or witness.get("version") != version or witness.get("locale") != locale
            or any(witness.get(key) != digest for key in ("artifact_sha256", "first_sha256", "second_sha256"))
            or witness.get("artifact_size") != archive.stat().st_size):
        raise ReleaseWorkflowError(f"{locale} build witness does not match the archive: {witness_path}")


def compare_platforms(directory: Path, other_directory: Path, root: Path = ROOT) -> dict[str, str]:
    meta = release_metadata(root)
    hashes = {}
    for suffix, locale in (("zh", "zh-CN"), ("en", "en")):
        for folder in (directory, other_directory):
            archive = folder / meta["archive_" + suffix]
            if not archive.is_file() or _is_link(archive):
                raise ReleaseWorkflowError("missing or unsafe archive: %s" % archive)
            digest = _sha256(archive)
            verify_build_witness(folder / meta["witness_" + suffix], archive, meta["version"], locale, digest)
            if locale in hashes and hashes[locale] != digest:
                raise ReleaseWorkflowError(f"cross-platform digest mismatch: {locale}")
            hashes[locale] = digest
    return hashes


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
        verify_build_witness(directory / witness_name, directory / archive_name,
                             metadata["version"], locale, checksums[archive_name])
    if (directory / metadata["release_notes"]).read_bytes() != release_notes_bytes(root):
        raise ReleaseWorkflowError("candidate release notes differ from the tagged source")
    _read_object(directory / metadata["provenance"])
    return {
        "ok": True,
        "version": metadata["version"],
        "files": sorted(expected),
        "subjects": sorted(subjects),
    }


def release_notes_bytes(root: Path) -> bytes:
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
    return text.encode("utf-8")


def write_release_notes(output: Path, root: Path = ROOT) -> dict[str, str]:
    metadata = release_metadata(root)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(release_notes_bytes(root))
    return {"ok": True, "version": metadata["version"], "notes": output.name}


RELEASE_LOOKUP = """
query ReleaseState($owner:String!, $name:String!, $tag:String!, $ref:String!) {
  repository(owner:$owner, name:$name) {
    ref(qualifiedName:$ref) { target { oid } }
    release(tagName:$tag) { databaseId tagName tagCommit { oid } }
  }
}
"""


def _command(args: list[str], root: Path) -> str:
    result = subprocess.run(args, cwd=root, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=120)
    if result.returncode:
        raise ReleaseWorkflowError(f"{args[0]} {args[1]} failed: {result.stderr.strip()[:500]}")
    return result.stdout


def _release_assets(meta: dict[str, str]) -> set[str]:
    return {meta[key] for key in ("archive_zh", "archive_en", "witness_zh", "witness_en", "provenance", "checksums")}


def _remote_state(root: Path, repository: str, meta: dict[str, str], require_tag: bool) -> tuple[str, int, dict]:
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or any(part in {".", ".."} for part in repository.split("/"))):
        raise ReleaseWorkflowError("invalid release repository")
    owner, name = repository.split("/")
    tag = meta["tag"]
    reply = json.loads(_command(["gh", "api", "graphql", "-f", "query=" + RELEASE_LOOKUP,
                                 "-f", "owner=" + owner, "-f", "name=" + name, "-f", "tag=" + tag,
                                 "-f", "ref=refs/tags/" + tag], root))
    if not isinstance(reply, dict) or reply.get("errors") or not isinstance(reply.get("data"), dict):
        raise ReleaseWorkflowError("release lookup returned no reliable repository state")
    data = reply["data"].get("repository")
    if not isinstance(data, dict) or "ref" not in data or "release" not in data:
        raise ReleaseWorkflowError("release repository or lookup fields unavailable")
    commit = _command(["git", "rev-parse", "--verify", "HEAD^{commit}"], root).strip()
    if not re.fullmatch("[0-9a-f]{40}", commit):
        raise ReleaseWorkflowError("invalid checked-out commit")
    release, tag_ref = data["release"], data["ref"]
    if tag_ref is None:
        if require_tag or release is not None:
            raise ReleaseWorkflowError(f"missing remote tag for {tag}")
    else:
        target = tag_ref.get("target") if isinstance(tag_ref, dict) else None
        oid = target.get("oid") if isinstance(target, dict) else None
        if not isinstance(oid, str) or not re.fullmatch("[0-9a-f]{40}", oid):
            raise ReleaseWorkflowError("invalid remote tag object")
        tagged = _command(["git", "rev-parse", "--verify", oid + "^{commit}"], root).strip()
        if tagged != commit:
            raise ReleaseWorkflowError(f"version occupied: {tag} resolves to {tagged}, candidate is {commit}")
    if release is None:
        return commit, 0, {}
    if not isinstance(release, dict):
        raise ReleaseWorkflowError("invalid existing release record")
    release_id = release.get("databaseId")
    if release.get("tagName") != tag or type(release_id) is not int or release_id <= 0:
        raise ReleaseWorkflowError("invalid existing release identity")
    if "tagCommit" not in release:
        raise ReleaseWorkflowError("release commit lookup field unavailable")
    tag_commit = release["tagCommit"]
    if tag_commit is not None and (not isinstance(tag_commit, dict) or tag_commit.get("oid") != commit):
        raise ReleaseWorkflowError("existing release names a different target commit")
    pages = json.loads(_command(["gh", "api", "--paginate", "--slurp",
                                f"repos/{repository}/releases/{release_id}/assets?per_page=100"], root))
    if not isinstance(pages, list) or not pages or any(not isinstance(page, list) for page in pages):
        raise ReleaseWorkflowError("release asset listing unavailable")
    assets = {}
    for page in pages:
        for asset in page:
            if (not isinstance(asset, dict) or not isinstance(asset.get("name"), str)
                    or type(asset.get("id")) is not int or asset["id"] <= 0
                    or type(asset.get("size")) is not int or asset["size"] <= 0):
                raise ReleaseWorkflowError("invalid release attachment metadata")
            key = asset["name"]
            if key in assets or asset.get("state") != "uploaded":
                raise ReleaseWorkflowError(f"duplicate or incomplete release attachment: {key}")
            digest = asset.get("digest")
            if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest)):
                raise ReleaseWorkflowError(f"invalid remote digest for {key}")
            assets[key] = (asset["id"], asset["size"], digest)
    expected = _release_assets(meta)
    if assets.keys() != expected:
        raise ReleaseWorkflowError(f"incomplete or unexpected release attachments: missing={sorted(expected - assets.keys())} "
                                   f"extra={sorted(assets.keys() - expected)}")
    return commit, release_id, assets


def inspect_release(repository: str, tag: str = "", directory: Path | None = None, *,
                    expected_id: int = 0, expected_inventory: str = "", require_existing: bool = False,
                    reuse_provenance: bool = False, root: Path = ROOT) -> dict[str, str]:
    meta = release_metadata(root, tag)
    commit, release_id, assets = _remote_state(root, repository, meta, bool(tag))
    inventory = ""
    if release_id:
        bound = json.dumps([commit, release_id, assets], sort_keys=True, separators=(",", ":")).encode("utf-8")
        inventory = hashlib.sha256(bound).hexdigest()
    if expected_id and release_id != expected_id:
        raise ReleaseWorkflowError("previously observed release disappeared or changed identity")
    if expected_inventory and expected_inventory != inventory:
        raise ReleaseWorkflowError("release attachment inventory changed since preflight")
    if not release_id and require_existing:
        raise ReleaseWorkflowError("release missing after draft creation")
    status = "occupied" if release_id else "absent"
    if release_id and directory is not None:
        directory = directory.resolve()
        verify_candidate(directory, root)
        expected = {name: "sha256:" + _sha256(directory / name) for name in assets}
        sizes = {name: (directory / name).stat().st_size for name in assets}
        with tempfile.TemporaryDirectory() as scratch:
            tmp = Path(scratch)
            def download(name: str) -> Path:
                path = tmp / name
                if not path.exists():
                    _command(["gh", "release", "download", meta["tag"], "--repo", repository,
                              "--pattern", name, "--dir", str(tmp)], root)
                if not path.is_file() or _is_link(path):
                    raise ReleaseWorkflowError(f"missing or unsafe downloaded attachment: {name}")
                return path
            if reuse_provenance:
                # 中文：重签会产生新证明。用原签名核验同一提交和本次重建的两个包。
                # English: Verify the original signature against this commit and both rebuilt ZIPs.
                bundle = download(meta["provenance"])
                for key in ("archive_zh", "archive_en"):
                    _command(["gh", "attestation", "verify", str(directory / meta[key]), "--repo", repository,
                              "--bundle", str(bundle), "--source-digest", commit, "--source-ref", "refs/tags/" + meta["tag"],
                              "--signer-workflow", repository + "/.github/workflows/release.yml"], root)
                expected[meta["provenance"]] = "sha256:" + _sha256(bundle)
                subjects = {k: v.removeprefix("sha256:") for k, v in expected.items() if k != meta["checksums"]}
                sums = checksum_bytes(subjects)
                expected[meta["checksums"]] = "sha256:" + hashlib.sha256(sums).hexdigest()
                sizes[meta["checksums"]] = len(sums)
                sizes[meta["provenance"]] = bundle.stat().st_size
            for name, (_, size, digest) in assets.items():
                actual = digest if digest is not None else "sha256:" + _sha256(download(name))
                if actual != expected[name]:
                    raise ReleaseWorkflowError(f"release attachment digest conflict: {name}")
                if size != sizes[name]:
                    raise ReleaseWorkflowError(f"release attachment size conflict: {name}")
        if _remote_state(root, repository, meta, True) != (commit, release_id, assets):
            raise ReleaseWorkflowError("release identity or attachments changed during verification")
        status = "verified"
    return {"status": status, "release_id": str(release_id), "source_commit": commit, "inventory_sha256": inventory}


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
    compare_parser = subparsers.add_parser("compare-platforms")
    compare_parser.add_argument("--directory", type=Path, required=True)
    compare_parser.add_argument("--other-directory", type=Path, required=True)
    remote = subparsers.add_parser("remote-state")
    remote.add_argument("--repository", required=True)
    remote.add_argument("--tag", default="")
    remote.add_argument("--directory", type=Path)
    remote.add_argument("--expected-id", type=int, default=0)
    remote.add_argument("--expected-inventory", default="")
    remote.add_argument("--require-existing", action="store_true")
    remote.add_argument("--reuse-provenance", action="store_true")
    remote.add_argument("--format", choices=("json", "github"), default="json")
    master_parser = subparsers.add_parser("verify-master")
    master_parser.add_argument("--commit", default="HEAD")
    master_parser.add_argument("--master-ref", default="origin/master")
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
    elif arguments.command == "compare-platforms":
        print(json.dumps(compare_platforms(arguments.directory, arguments.other_directory), sort_keys=True))
    elif arguments.command == "remote-state":
        result = inspect_release(arguments.repository, arguments.tag, arguments.directory,
                                 expected_id=arguments.expected_id, expected_inventory=arguments.expected_inventory,
                                 require_existing=arguments.require_existing,
                                 reuse_provenance=arguments.reuse_provenance)
        print(_render_metadata(result, arguments.format), end="")
    elif arguments.command == "verify-master":
        result = verify_commit_on_master(commit=arguments.commit, master_ref=arguments.master_ref)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        result = write_release_notes(Path(arguments.output))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ReleaseWorkflowError, json.JSONDecodeError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=os.sys.stderr)
        raise SystemExit(2)
