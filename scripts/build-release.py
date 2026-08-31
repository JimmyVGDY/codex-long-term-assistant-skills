#!/usr/bin/env python3
"""中文：构建并验证字节级可复现的 V6.6.1 语言发行包。

English: Build and verify byte-reproducible V6.6.1 locale-specific archives.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from payload_integrity import write_manifest as write_payload_manifest

ROOT = Path(__file__).resolve().parents[1]
VERSION = "6.6.1"
PACKAGE = "codex-cross-project-engineering-assistant"
SUPPORTED_LOCALES = ("zh-CN", "en")
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)
EXCLUDED_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", "locales", "dist"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip"}
EXCLUDED_NAMES = {"cp-assistant-v6.lock"}
CHECKSUM_FILE = "CHECKSUMS.sha256"


class BuildError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        return os.name == "nt" and bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, OSError):
        return False


def _included(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES or path.name in EXCLUDED_NAMES or path.name.endswith(".en.md"):
        return False
    if _is_link(path):
        raise BuildError("release source contains a link or reparse point: %s" % relative.as_posix())
    return path.is_file()


def release_files(root: Path, include_checksums: bool = True) -> List[Path]:
    files = [path for path in root.rglob("*") if _included(path, root)]
    if not include_checksums:
        files = [path for path in files if path.name != CHECKSUM_FILE]
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def write_checksums(root: Path) -> None:
    lines = [
        "%s  %s" % (sha256_file(path), path.relative_to(root).as_posix())
        for path in release_files(root, include_checksums=False)
    ]
    (root / CHECKSUM_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _copy_source(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=False)
    for path in release_files(source):
        relative = path.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)


def _apply_overlay(staging: Path, locale: str) -> None:
    locale_path = staging / "config" / "locale.json"
    locale_path.parent.mkdir(parents=True, exist_ok=True)
    locale_path.write_text(json.dumps({"schema_version": 1, "locale": locale}, indent=2) + "\n", encoding="utf-8")
    if locale == "zh-CN":
        return
    localized_history = ROOT / "RECONSTRUCTED_HISTORY.en.md"
    if localized_history.is_file():
        (staging / "RECONSTRUCTED_HISTORY.zh-CN.md").unlink(missing_ok=True)
        shutil.copyfile(localized_history, staging / "RECONSTRUCTED_HISTORY.en.md")
    overlay = ROOT / "locales" / locale
    if not overlay.is_dir() or _is_link(overlay):
        raise BuildError("locale overlay is missing or unsafe: %s" % locale)
    for source in sorted(overlay.rglob("*")):
        if _is_link(source):
            raise BuildError("locale overlay contains a link: %s" % source.relative_to(overlay).as_posix())
        if not source.is_file() or source.name in {"manifest-localization.json", "HUMAN_REVIEWED.txt"}:
            continue
        relative = source.relative_to(overlay)
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    localization = json.loads((overlay / "manifest-localization.json").read_text(encoding="utf-8"))
    manifest_path = staging / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in ("release_name", "generated_for"):
        manifest[key] = localization[key]
    localized_skills = localization.get("skills") or {}
    for skill in manifest.get("skills", []):
        values = localized_skills.get(skill.get("name"))
        if not isinstance(values, dict):
            raise BuildError("missing manifest localization for skill: %s" % skill.get("name"))
        skill.update(display_name=values["display_name"], description=values["description"])
    localized_agents = localization.get("custom_agents") or {}
    for agent in manifest.get("custom_agents", []):
        scope = localized_agents.get(agent.get("name"))
        if not isinstance(scope, str) or not scope:
            raise BuildError("missing manifest localization for reviewer: %s" % agent.get("name"))
        agent["scope"] = scope
    manifest["review_isolation_levels"] = localization["review_isolation_levels"]
    manifest["breaking_changes"] = localization["breaking_changes"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _prepare_staging(locale: str, parent: Path) -> Path:
    if locale not in SUPPORTED_LOCALES:
        raise BuildError("unsupported locale: %s" % locale)
    staging = parent / ("Codex-Skills-V6.6.1-" + locale)
    _copy_source(ROOT, staging)
    _apply_overlay(staging, locale)
    manifest = json.loads((staging / "manifest.json").read_text(encoding="utf-8-sig"))
    plugin = json.loads((staging / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8-sig"))
    if manifest.get("version") != VERSION or plugin.get("version") != VERSION:
        raise BuildError("manifest and Plugin versions must be %s" % VERSION)
    write_payload_manifest(staging, PACKAGE, VERSION)
    write_checksums(staging)
    return staging


def _file_mode(path: Path) -> int:
    return 0o755 if path.suffix.lower() in {".py", ".ps1", ".sh", ".cmd"} else 0o644


def build_release(output: Path, locale: str) -> Dict[str, Any]:
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise BuildError("release output must stay outside the package source")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cp-v661-build-") as temporary_dir:
        staging = _prepare_staging(locale, Path(temporary_dir))
        files = release_files(staging)
        fd, temporary_name = tempfile.mkstemp(prefix=output.name + ".tmp-", dir=str(output.parent))
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9,
                                 strict_timestamps=True) as archive:
                for path in files:
                    relative = path.relative_to(staging).as_posix()
                    info = zipfile.ZipInfo("%s/%s" % (staging.name, relative), FIXED_ZIP_TIME)
                    info.create_system = 3
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = (_file_mode(path) & 0xFFFF) << 16
                    info.flag_bits |= 0x800
                    archive.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED, compresslevel=9)
            with zipfile.ZipFile(temporary, "r") as archive:
                failed = archive.testzip()
                if failed:
                    raise BuildError("ZIP CRC verification failed: %s" % failed)
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    return {"ok": True, "version": VERSION, "locale": locale, "artifact": output.name,
            "artifact_sha256": sha256_file(output), "artifact_size": output.stat().st_size,
            "file_count": len(files), "fixed_zip_time": "2020-01-01T00:00:00Z"}


def verify_release(archive_path: Path, locale: str | None = None) -> Dict[str, Any]:
    archive_path = archive_path.resolve()
    with zipfile.ZipFile(archive_path, "r") as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        roots = {name.split("/", 1)[0] for name in names if "/" in name}
        if len(roots) != 1:
            raise BuildError("ZIP must contain exactly one package root")
        root = next(iter(roots))
        observed_locale = root.removeprefix("Codex-Skills-V6.6.1-")
        if observed_locale not in SUPPORTED_LOCALES or (locale and observed_locale != locale):
            raise BuildError("ZIP locale root is inconsistent")
        if names != sorted(names):
            raise BuildError("ZIP entries are not sorted")
        if any("__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in names):
            raise BuildError("ZIP contains runtime cache files")
        if any("../" in name or name.startswith(("/", "\\")) for name in names):
            raise BuildError("ZIP contains an unsafe path")
        if any(entry.date_time != FIXED_ZIP_TIME for entry in entries):
            raise BuildError("ZIP timestamps are not normalized")
        if any(not name.startswith(root + "/") for name in names):
            raise BuildError("ZIP root directory is inconsistent")
        failed = archive.testzip()
        if failed:
            raise BuildError("ZIP CRC verification failed: %s" % failed)
    return {"ok": True, "version": VERSION, "locale": observed_locale,
            "artifact": archive_path.name, "artifact_sha256": sha256_file(archive_path),
            "entry_count": len(names), "metadata_normalized": True}


def reproducible_build(output: Path, witness: Path, locale: str) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cp-v661-repro-") as temporary:
        first = Path(temporary) / "first.zip"
        second = Path(temporary) / "second.zip"
        a = build_release(first, locale)
        b = build_release(second, locale)
        if first.read_bytes() != second.read_bytes():
            raise BuildError("two clean builds are not byte-identical")
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(first, output)
    verified = verify_release(output, locale)
    report = {"ok": True, "reproducible": True, "version": VERSION, "locale": locale,
              "first_sha256": a["artifact_sha256"], "second_sha256": b["artifact_sha256"],
              "artifact_sha256": verified["artifact_sha256"], "artifact_size": output.stat().st_size,
              "entry_count": verified["entry_count"], "fixed_zip_time": "2020-01-01T00:00:00Z"}
    witness.parent.mkdir(parents=True, exist_ok=True)
    witness.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.6.1 deterministic bilingual release builder")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--locale", choices=SUPPORTED_LOCALES, required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--archive", required=True)
    verify_parser.add_argument("--locale", choices=SUPPORTED_LOCALES)
    reproducible_parser = subparsers.add_parser("reproducible")
    reproducible_parser.add_argument("--output", required=True)
    reproducible_parser.add_argument("--witness", required=True)
    reproducible_parser.add_argument("--locale", choices=SUPPORTED_LOCALES, required=True)
    arguments = parser.parse_args()
    if arguments.command == "build":
        result = build_release(Path(arguments.output), arguments.locale)
    elif arguments.command == "verify":
        result = verify_release(Path(arguments.archive), arguments.locale)
    else:
        result = reproducible_build(Path(arguments.output), Path(arguments.witness), arguments.locale)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (BuildError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=os.sys.stderr)
        raise SystemExit(2)
