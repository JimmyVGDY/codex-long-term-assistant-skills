#!/usr/bin/env python3
"""Build and verify a byte-reproducible V6.5 release archive."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

from payload_integrity import write_manifest as write_payload_manifest

ROOT = Path(__file__).resolve().parents[1]
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)
EXCLUDED_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
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


def _included(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.name in EXCLUDED_NAMES:
        return False
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
    target = root / CHECKSUM_FILE
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _file_mode(path: Path) -> int:
    return 0o755 if path.suffix.lower() in {".py", ".ps1", ".sh", ".cmd"} else 0o644


def build_release(root: Path, output: Path) -> Dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
    if manifest.get("version") != "6.5.0":
        raise BuildError("manifest version must be 6.5.0")
    if output == root or root in output.parents:
        raise BuildError("release output must stay outside the package source")
    write_payload_manifest(root, "codex-cross-project-engineering-assistant", "6.5.0")
    write_checksums(root)
    files = release_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=output.name + ".tmp-", dir=str(output.parent))
    os.close(fd)
    temporary = Path(temporary_name)
    package_root = "Codex-Skills-V6.5"
    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as archive:
            for path in files:
                relative = path.relative_to(root).as_posix()
                info = zipfile.ZipInfo("%s/%s" % (package_root, relative), FIXED_ZIP_TIME)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (_file_mode(path) & 0xFFFF) << 16
                info.flag_bits |= 0x800
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(temporary, "r") as archive:
            failed = archive.testzip()
            if failed:
                raise BuildError("ZIP CRC verification failed: %s" % failed)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "ok": True,
        "version": "6.5.0",
        "artifact": output.name,
        "artifact_sha256": sha256_file(output),
        "artifact_size": output.stat().st_size,
        "file_count": len(files),
        "fixed_zip_time": "2020-01-01T00:00:00Z",
    }


def verify_release(archive_path: Path) -> Dict[str, Any]:
    archive_path = archive_path.resolve()
    with zipfile.ZipFile(archive_path, "r") as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if names != sorted(names):
            raise BuildError("ZIP entries are not sorted")
        if any("__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in names):
            raise BuildError("ZIP contains runtime cache files")
        if any("../" in name or name.startswith(("/", "\\")) for name in names):
            raise BuildError("ZIP contains an unsafe path")
        if any(entry.date_time != FIXED_ZIP_TIME for entry in entries):
            raise BuildError("ZIP timestamps are not normalized")
        if any(not name.startswith("Codex-Skills-V6.5/") for name in names):
            raise BuildError("ZIP root directory is inconsistent")
        failed = archive.testzip()
        if failed:
            raise BuildError("ZIP CRC verification failed: %s" % failed)
    return {
        "ok": True,
        "artifact": archive_path.name,
        "artifact_sha256": sha256_file(archive_path),
        "entry_count": len(names),
        "metadata_normalized": True,
    }


def reproducible_build(root: Path, output: Path, witness: Path) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cp-v65-repro-") as temporary:
        first = Path(temporary) / "first.zip"
        second = Path(temporary) / "second.zip"
        a = build_release(root, first)
        b = build_release(root, second)
        if first.read_bytes() != second.read_bytes():
            raise BuildError("two clean builds are not byte-identical")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(first.read_bytes())
    verified = verify_release(output)
    report = {
        "ok": True,
        "reproducible": True,
        "version": "6.5.0",
        "first_sha256": a["artifact_sha256"],
        "second_sha256": b["artifact_sha256"],
        "artifact_sha256": verified["artifact_sha256"],
        "artifact_size": output.stat().st_size,
        "entry_count": verified["entry_count"],
        "fixed_zip_time": "2020-01-01T00:00:00Z",
    }
    witness.parent.mkdir(parents=True, exist_ok=True)
    witness.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.5 deterministic release builder")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--output", required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--archive", required=True)
    reproducible_parser = subparsers.add_parser("reproducible")
    reproducible_parser.add_argument("--output", required=True)
    reproducible_parser.add_argument("--witness", required=True)
    arguments = parser.parse_args()
    if arguments.command == "build":
        result = build_release(ROOT, Path(arguments.output))
    elif arguments.command == "verify":
        result = verify_release(Path(arguments.archive))
    else:
        result = reproducible_build(ROOT, Path(arguments.output), Path(arguments.witness))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except BuildError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=os.sys.stderr)
        raise SystemExit(2)
