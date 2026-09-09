"""中文：捕获发行源码；无 Git 输入必须提供显式内容清单。

English: Capture release sources; Gitless inputs require an explicit content manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import threading
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_NAME = "SOURCE_MANIFEST.json"
MAX_FILES = 10000
MAX_LIST_BYTES = 16 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_SOURCE_BYTES = 256 * 1024 * 1024
SOURCE_ROOTS = {"scripts", "runtime", "hooks", "skills", "config", "custom-agents",
                "global", "tests", "locales", "docs", ".codex-plugin", ".agents", ".github"}
REQUIRED = {"manifest.json", ".codex-plugin/plugin.json", "scripts/build-release.py",
            "scripts/release_source.py", "scripts/payload_integrity.py",
            "scripts/runtime_localization.py", "hooks/hooks.json",
            "locales/en/manifest-localization.json", "locales/en/runtime-strings.json"}


class SourceError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SourceError("duplicate source manifest key: %s" % key)
        result[key] = value
    return result


def relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise SourceError("invalid source path")
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or path.as_posix() != value or any(
        part in {".", ".."} or part.endswith((".", " "))
        or re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", part)
        for part in path.parts
    ) or any(ord(char) < 32 or char in '\\:<>"|?*' for char in value):
        raise SourceError("unsafe source path: %s" % value)
    return value


def _io(path: Path) -> Path:
    name = str(path.absolute())
    return Path("\\\\?\\" + name) if os.name == "nt" and not name.startswith("\\\\?\\") else Path(name)


def _safe(path: Path, *, directory: bool = False) -> os.stat_result:
    path = _io(path)
    for ancestor in reversed((path, *path.parents)):
        info = ancestor.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise SourceError("source contains link/reparse point: %s" % path.name)
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise SourceError("source is not a regular %s: %s" % ("directory" if directory else "file", path.name))
    return info


def _identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _read(path: Path, limit: int = MAX_FILE_BYTES) -> bytes:
    before = _safe(path)
    if before.st_size > limit:
        raise SourceError("source file exceeds capture limit: %s" % path.name)
    with _io(path).open("rb") as stream:
        opened = os.fstat(stream.fileno())
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if len(data) > limit or _identity(before) != _identity(opened) or _identity(before) != _identity(after) \
            or _identity(before) != _identity(_safe(path)):
        raise SourceError("source changed during capture: %s" % path.name)
    return data


def _git(root: Path, *args: str) -> bytes:
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("GIT_")}
    environment.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    overflow = threading.Event()
    buffers = [bytearray(), bytearray()]
    try:
        process = subprocess.Popen(["git", "-c", "core.fsmonitor=false", "-C", str(root), *args],
                                   env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        raise SourceError("Git source discovery unavailable") from exc

    def drain(stream, buffer):
        try:
            while chunk := stream.read(8192):
                remaining = MAX_LIST_BYTES - len(buffer)
                buffer.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    overflow.set()
                    process.kill()
                    return
        finally:
            stream.close()

    readers = [threading.Thread(target=drain, args=(stream, buffer), daemon=True)
               for stream, buffer in zip((process.stdout, process.stderr), buffers)]
    for reader in readers:
        reader.start()
    try:
        code = process.wait(timeout=30)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait(timeout=5)
        raise SourceError("Git source discovery timed out") from exc
    finally:
        for reader in readers:
            reader.join(timeout=2)
    if overflow.is_set() or any(reader.is_alive() for reader in readers):
        raise SourceError("Git source discovery exceeded output limit or pipe deadline")
    if code:
        raise SourceError("Git source discovery failed")
    return bytes(buffers[0])


def _paths(values: list[str]) -> list[str]:
    if not values or len(values) > MAX_FILES:
        raise SourceError("source file count is outside capture limits")
    folded: set[str] = set()
    directories: set[str] = set()
    spelling: dict[str, str] = {}
    for value in values:
        relative_path(value)
        for item in (PurePosixPath(value), *PurePosixPath(value).parents):
            name = item.as_posix()
            if spelling.setdefault(name.casefold(), name) != name:
                raise SourceError("case-colliding source path: %s" % value)
        lowered = value.casefold()
        if lowered in folded or lowered in directories or any(
            parent.as_posix().casefold() in folded for parent in PurePosixPath(value).parents
        ):
            raise SourceError("duplicate/colliding source path: %s" % value)
        if value == MANIFEST_NAME or ".git" in PurePosixPath(value).parts:
            raise SourceError("source manifest cannot list itself or Git metadata")
        folded.add(lowered)
        directories.update(parent.as_posix().casefold() for parent in PurePosixPath(value).parents)
    return sorted(values)


def _git_state(root: Path, require_clean: bool) -> tuple[str, bytes, list[str]]:
    top = Path(_git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip())
    if top.resolve() != root.resolve():
        raise SourceError("Git root does not match source root")
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    listing = _git(root, "ls-files", "--stage", "-z")
    paths = []
    for row in listing.split(b"\0"):
        if not row:
            continue
        metadata, name = row.split(b"\t", 1)
        mode, _, stage = metadata.split()
        if mode not in {b"100644", b"100755"} or stage != b"0":
            raise SourceError("Git source contains a link, submodule or unmerged entry")
        paths.append(name.decode("utf-8"))
    for name in _git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
        if not name:
            continue
        value = name.decode("utf-8")
        if PurePosixPath(value).parts[0] in SOURCE_ROOTS or value.endswith((".py", ".ps1", ".sh", ".cmd")):
            raise SourceError("untracked source input; stage it before building: %s" % value)
    if require_clean and _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise SourceError("formal source capture requires a clean tracked worktree")
    return head, listing, _paths(paths)


def _digest(files: list[dict[str, Any]]) -> str:
    return hashlib.sha256(_canonical(files)).hexdigest()


def _load(root: Path) -> dict[str, Any]:
    if not (root / MANIFEST_NAME).exists():
        raise SourceError("Gitless input requires SOURCE_MANIFEST.json; use build-release.py snapshot from a Git checkout")
    manifest = json.loads(_read(root / MANIFEST_NAME, MAX_LIST_BYTES), object_pairs_hook=_unique)
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version", "source_head", "file_count", "content_digest", "files"
    } or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise SourceError("invalid source manifest schema")
    rows = manifest["files"]
    if not isinstance(rows, list) or not rows or len(rows) > MAX_FILES:
        raise SourceError("invalid source manifest file list")
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "size", "sha256"} \
                or type(row["size"]) is not int or not 0 <= row["size"] <= MAX_FILE_BYTES \
                or not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise SourceError("invalid source manifest file entry")
    if _paths([row["path"] for row in rows]) != [row["path"] for row in rows] \
            or type(manifest["file_count"]) is not int or manifest["file_count"] != len(rows) \
            or manifest["content_digest"] != _digest(rows) \
            or not isinstance(manifest["source_head"], str) \
            or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", manifest["source_head"]):
        raise SourceError("source manifest ordering, count or digest is invalid")
    return manifest


def _required(root: Path, paths: set[str]) -> None:
    if REQUIRED - paths:
        raise SourceError("required source input missing: %s" % sorted(REQUIRED - paths))
    manifest = json.loads(_read(root / "manifest.json"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("skills", []), list) \
            or not isinstance(manifest.get("custom_agents", []), list):
        raise SourceError("invalid package manifest source declarations")
    declared = set()
    for item in manifest.get("skills", []):
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) \
                or not re.fullmatch(r"[a-z][a-z0-9-]*", item["name"]):
            raise SourceError("invalid package manifest skill declaration")
        declared.add("skills/%s/SKILL.md" % item["name"])
    for item in manifest.get("custom_agents", []):
        if not isinstance(item, dict) or not isinstance(item.get("file"), str):
            raise SourceError("invalid package manifest agent declaration")
        declared.add(item["file"])
    for value in declared:
        relative_path(value)
    if declared - paths:
        raise SourceError("declared plugin input missing: %s" % sorted(declared - paths))


def capture(root: Path, destination: Path, *, require_clean: bool = False) -> dict[str, Any]:
    """中文：在外部新目录发布完整快照；失败时不留下可消费的半成品。

    English: Publish a complete external snapshot, leaving no consumable partial result.
    """
    root = root.absolute()
    _safe(root, directory=True)
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise SourceError("snapshot destination must not exist")
    if destination.resolve() == root.resolve() or root.resolve() in destination.resolve().parents:
        raise SourceError("snapshot destination must be outside the source")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _safe(destination.parent, directory=True)
    git_mode = (root / ".git").exists() or (root / ".git").is_symlink()
    state = _git_state(root, require_clean) if git_mode else None
    if not git_mode and require_clean:
        raise SourceError("clean commit provenance requires a Git checkout")
    original = _load(root) if not git_mode else None
    paths = state[2] if state else [row["path"] for row in original["files"]]
    expected = {row["path"]: row for row in original["files"]} if original else {}
    total = 0
    rows = []
    with tempfile.TemporaryDirectory(prefix=".source-capture-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "content"
        staged.mkdir()
        for name in paths:
            data = _read(root / name)
            total += len(data)
            if total > MAX_SOURCE_BYTES:
                raise SourceError("source capture exceeds byte limit")
            row = {"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            if original and row != expected[name]:
                raise SourceError("source manifest content mismatch: %s" % name)
            target = _io(staged / name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
            rows.append(row)
        _required(staged, set(paths))
        for row in rows:
            if hashlib.sha256(_read(root / row["path"])).hexdigest() != row["sha256"]:
                raise SourceError("source changed after capture: %s" % row["path"])
        if state and _git_state(root, require_clean) != state:
            raise SourceError("Git source set changed during capture")
        if original and _load(root) != original:
            raise SourceError("source manifest changed during capture")
        manifest = {"schema_version": 1, "source_head": state[0] if state else original["source_head"],
                    "file_count": len(rows), "content_digest": _digest(rows), "files": rows}
        (staged / MANIFEST_NAME).write_bytes(_canonical(manifest) + b"\n")
        _safe(destination.parent, directory=True)
        if destination.exists() or destination.is_symlink():
            raise SourceError("snapshot destination appeared during capture")
        staged.rename(destination)
    return manifest
