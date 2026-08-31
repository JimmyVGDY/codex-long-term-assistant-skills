#!/usr/bin/env python3
"""Deterministic Plugin payload manifest and verifier."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, Mapping

PAYLOAD_ROOTS = (".codex-plugin", "skills", "hooks", "runtime")
MANIFEST_NAME = "PLUGIN_PAYLOAD_MANIFEST.json"
SCHEMA_VERSION = 1


class PayloadIntegrityError(RuntimeError):
    pass


def _io_path(path: Path) -> Path:
    absolute = str(path.absolute())
    if os.name != "nt" or absolute.startswith("\\\\?\\"):
        return Path(absolute)
    return Path("\\\\?\\" + absolute)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_relative(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise PayloadIntegrityError("非法 payload 相对路径: %s" % value)
    if path.parts[0] not in PAYLOAD_ROOTS:
        raise PayloadIntegrityError("路径不属于受管 payload 根: %s" % value)
    return path.as_posix()


def _is_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT) if os.name == "nt" else False
    except (AttributeError, OSError):
        return False


def iter_payload_files(root: Path) -> Iterable[tuple[str, Path]]:
    root = root.resolve()
    io_root = _io_path(root)
    for name in PAYLOAD_ROOTS:
        base = io_root / name
        if not base.is_dir() or _is_link(base):
            raise PayloadIntegrityError("payload 根缺失或为链接: %s" % base)
        for path in sorted(base.rglob("*"), key=lambda item: item.as_posix()):
            if "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".pyo"}:
                continue
            if _is_link(path):
                raise PayloadIntegrityError("payload 含链接/Reparse Point: %s" % path)
            if path.is_file():
                relative = _validate_relative(path.relative_to(io_root).as_posix())
                yield relative, path


def build_manifest(root: Path, package: str, version: str) -> Dict[str, Any]:
    entries = [{"path": relative, "sha256": _sha256(path), "size": path.stat().st_size}
               for relative, path in iter_payload_files(root)]
    projection = [{"path": item["path"], "sha256": item["sha256"], "size": item["size"]}
                  for item in entries]
    return {
        "schema_version": SCHEMA_VERSION,
        "package": package,
        "version": version,
        "payload_roots": list(PAYLOAD_ROOTS),
        "file_count": len(entries),
        "payload_digest": hashlib.sha256(_canonical(projection)).hexdigest(),
        "files": entries,
    }


def load_manifest(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(_io_path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PayloadIntegrityError("payload manifest 无法读取: %s" % path) from exc
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise PayloadIntegrityError("payload manifest schema 未知")
    files = value.get("files")
    if not isinstance(files, list) or value.get("payload_roots") != list(PAYLOAD_ROOTS):
        raise PayloadIntegrityError("payload manifest 结构无效")
    seen = set()
    for item in files:
        if not isinstance(item, dict):
            raise PayloadIntegrityError("payload manifest file 项无效")
        relative = _validate_relative(str(item.get("path") or ""))
        if relative in seen:
            raise PayloadIntegrityError("payload manifest 路径重复: %s" % relative)
        seen.add(relative)
        if not isinstance(item.get("size"), int) or not isinstance(item.get("sha256"), str):
            raise PayloadIntegrityError("payload manifest 哈希项无效: %s" % relative)
    return value


def verify_payload(root: Path, manifest: Mapping[str, Any], *, package: str | None = None,
                   version: str | None = None) -> Dict[str, Any]:
    if package is not None and manifest.get("package") != package:
        raise PayloadIntegrityError("payload package 不匹配")
    if version is not None and manifest.get("version") != version:
        raise PayloadIntegrityError("payload version 不匹配")
    actual = build_manifest(root, str(manifest.get("package") or ""), str(manifest.get("version") or ""))
    expected_entries = manifest.get("files")
    if actual["files"] != expected_entries:
        expected = {str(item.get("path")): item for item in expected_entries if isinstance(item, dict)}
        observed = {str(item.get("path")): item for item in actual["files"]}
        missing = sorted(set(expected) - set(observed))
        unexpected = sorted(set(observed) - set(expected))
        changed = sorted(path for path in set(expected) & set(observed) if expected[path] != observed[path])
        raise PayloadIntegrityError("payload 不一致 missing=%s unexpected=%s changed=%s" %
                                    (missing[:10], unexpected[:10], changed[:10]))
    if actual["payload_digest"] != manifest.get("payload_digest") or actual["file_count"] != manifest.get("file_count"):
        raise PayloadIntegrityError("payload canonical digest 或文件数不匹配")
    return {"ok": True, "root": str(root.resolve()), "package": manifest.get("package"),
            "version": manifest.get("version"), "file_count": actual["file_count"],
            "payload_digest": actual["payload_digest"]}


def write_manifest(root: Path, package: str, version: str, output: Path | None = None) -> Dict[str, Any]:
    value = build_manifest(root, package, version)
    target = output or root / MANIFEST_NAME
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.6 Plugin payload 身份工具")
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--root", required=True)
    generate.add_argument("--package", required=True)
    generate.add_argument("--version", required=True)
    generate.add_argument("--output")
    verify = sub.add_parser("verify")
    verify.add_argument("--root", required=True)
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--package")
    verify.add_argument("--version")
    args = parser.parse_args()
    try:
        if args.command == "generate":
            result = write_manifest(Path(args.root), args.package, args.version,
                                    Path(args.output) if args.output else None)
        else:
            result = verify_payload(Path(args.root), load_manifest(Path(args.manifest)),
                                    package=args.package, version=args.version)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except PayloadIntegrityError as exc:
        print("[FAIL] %s" % exc, file=os.sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
