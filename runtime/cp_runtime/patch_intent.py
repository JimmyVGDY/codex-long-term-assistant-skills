"""中文：为 ``apply_patch`` 提供规范且不含正文的意图解析。

English: Canonical, content-free intent parsing for ``apply_patch``. The parser
deliberately does not retain patch hunks. It produces a small
pre-state snapshot which can be checked again immediately before dispatch.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any

from .capability_store import CapabilityError, relative_path, safe_path


MAX_COMMAND_BYTES = 1024 * 1024
MAX_TARGETS = 64
MAX_PATH_BYTES = 1024
MAX_FILE_BYTES = 8 * 1024 * 1024


class PatchIntentError(ValueError):
    """中文：稳定且不包含敏感内容的解析或重验错误。

    English: A stable, non-sensitive parser or revalidation error.
    """

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fail(code: str) -> None:
    raise PatchIntentError(code)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _file_digest(path: Path, expected: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            before_stamp = [int(before.st_dev), int(before.st_ino), int(before.st_mtime_ns), int(before.st_size)]
            expected_stamp = [expected.get("file_id", [None, None])[0], expected.get("file_id", [None, None])[1], expected.get("mtime_ns"), expected.get("size")]
            if before_stamp != expected_stamp:
                _fail("READ_CHANGED")
            if before.st_size > MAX_FILE_BYTES:
                _fail("TOO_LARGE")
            total = 0
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                total += len(chunk)
                if total > MAX_FILE_BYTES:
                    _fail("TOO_LARGE")
                digest.update(chunk)
            after = os.fstat(stream.fileno())
            after_stamp = [int(after.st_dev), int(after.st_ino), int(after.st_mtime_ns), int(after.st_size)]
            if after_stamp != before_stamp:
                _fail("READ_CHANGED")
    except OSError:
        _fail("PATH_UNREADABLE")
    return digest.hexdigest()


def _stat_record(path: Path, include_digest: bool = True) -> dict[str, Any]:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"exists": False}
    except OSError:
        _fail("PATH_UNREADABLE")
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        _fail("LINK_REJECTED")
    kind = "file" if stat.S_ISREG(info.st_mode) else "directory" if stat.S_ISDIR(info.st_mode) else "other"
    result: dict[str, Any] = {
        "exists": True,
        "kind": kind,
        "file_id": [int(info.st_dev), int(info.st_ino)],
        "mtime_ns": int(info.st_mtime_ns),
        "size": int(info.st_size),
    }
    if include_digest and kind == "file":
        result["sha256"] = _file_digest(path, result)
    return result


def _parent_chain(path: Path, root: Path) -> list[dict[str, Any]]:
    """中文：捕获每个存在或缺失的父路径组件，不保存正文。

    English: Capture every existing and missing parent component, without content.
    """
    try:
        rel = path.relative_to(root)
    except ValueError:
        _fail("PATH_ESCAPE")
    parts = rel.parts[:-1]
    chain: list[dict[str, Any]] = []
    current = root
    for part in parts:
        current = current / part
        item = _stat_record(current, include_digest=False)
        item["path"] = "/".join(current.relative_to(root).parts)
        chain.append(item)
    # 中文：包含根锚点，使根目录替换也可检测。
    # English: Include root as an anchor, so replacement of the root itself is visible.
    anchor = _stat_record(root, include_digest=False)
    anchor["path"] = "."
    return [anchor, *chain]


def _validate_path(value: Any, root: Path) -> tuple[str, Path]:
    if not isinstance(value, str):
        _fail("INVALID_PATH")
    if any(part == ".." for part in value.replace("\\", "/").split("/")):
        _fail("PATH_ESCAPE")
    try:
        relative_path(value)
    except CapabilityError as exc:
        _fail(exc.args[0] if exc.args and exc.args[0] in {"SENSITIVE_PATH", "LINK_REJECTED", "PATH_UNREADABLE"} else "INVALID_PATH")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeError:
        _fail("INVALID_PATH_ENCODING")
    if len(encoded) > MAX_PATH_BYTES:
        _fail("PATH_TOO_LONG")
    if value.startswith(("/", "\\")) or "\\" in value or ":" in value:
        _fail("INVALID_PATH")
    if PurePosixPath(value).is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        _fail("INVALID_PATH")
    candidate = root.joinpath(*value.split("/"))
    try:
        safe = safe_path(candidate)
        common = os.path.commonpath((os.path.normcase(str(root)), os.path.normcase(str(safe))))
    except CapabilityError as exc:
        _fail(exc.args[0] if exc.args and exc.args[0] in {"SENSITIVE_PATH", "LINK_REJECTED", "PATH_UNREADABLE"} else "INVALID_PATH")
    except ValueError:
        _fail("PATH_ESCAPE")
    if common != os.path.normcase(str(root)):
        _fail("PATH_ESCAPE")
    # 中文：safe_path 检查已有父级；末尾重读继续检测检查间父级消失。
    # English: safe_path checks existing ancestors; a final reread detects disappearance between checks.
    _parent_chain(safe, root)
    return value, safe


def _record(action: str, path_text: str, path: Path, root: Path, source_path: str | None = None) -> dict[str, Any]:
    state = _stat_record(path)
    if state.get("kind") == "directory":
        _fail("TARGET_DIRECTORY")
    chain = _parent_chain(path, root)
    return {
        "action": action,
        "path": path_text,
        **({"source_path": source_path} if source_path is not None else {}),
        "exists": bool(state["exists"]),
        "path_fingerprint": state,
        "parent_chain": chain,
        "parent_fingerprint": _digest(chain),
    }


def _move_record(source_text: str, source: Path, destination_text: str, destination: Path,
                 root: Path) -> dict[str, Any]:
    source_state = _stat_record(source)
    if not source_state["exists"]:
        _fail("SOURCE_MISSING")
    if source_state.get("kind") == "directory":
        _fail("SOURCE_DIRECTORY")
    source_chain = _parent_chain(source, root)
    destination_state = _stat_record(destination)
    if destination_state.get("kind") == "directory":
        _fail("TARGET_DIRECTORY")
    if destination_state.get("exists"):
        _fail("TARGET_EXISTS")
    destination_chain = _parent_chain(destination, root)
    return {
        "action": "Move",
        "path": destination_text,
        "source_path": source_text,
        "exists": bool(destination_state["exists"]),
        "path_fingerprint": destination_state,
        "parent_chain": destination_chain,
        "parent_fingerprint": _digest(destination_chain),
        "source_fingerprint": source_state,
        "source_parent_chain": source_chain,
        "source_parent_fingerprint": _digest(source_chain),
    }


def _add_target(records: list[dict[str, Any]], record: dict[str, Any], seen: set[str], keys: set[str]) -> None:
    paths = [record["path"]]
    if record.get("source_path") is not None:
        paths.append(record["source_path"])
    for path in paths:
        key = os.path.normcase(path.replace("/", os.sep))
        if key in keys:
            _fail("DUPLICATE_TARGET")
        keys.add(key)
        seen.add(path)
    if len(keys) > MAX_TARGETS:
        _fail("TOO_MANY_TARGETS")
    records.append(record)


def _parse_header(line: str) -> tuple[str, str] | None:
    for action in ("Add", "Delete", "Update"):
        prefix = f"*** {action} File: "
        if line.startswith(prefix):
            path = line[len(prefix):]
            if not path or path.endswith(" "):
                _fail("MALFORMED_MARKER")
            return action.upper(), path
    return None


def parse_apply_patch(command: str, repo_root: str | os.PathLike[str]) -> dict[str, Any]:
    if not isinstance(command, str):
        _fail("COMMAND_NOT_STRING")
    try:
        raw = command.encode("utf-8", errors="strict")
    except UnicodeError:
        _fail("COMMAND_INVALID_UTF8")
    if len(raw) > MAX_COMMAND_BYTES:
        _fail("COMMAND_TOO_LARGE")
    root = safe_path(Path(repo_root))
    if not root.is_dir():
        _fail("REPO_ROOT_INVALID")
    lines = command.splitlines()
    if not lines or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        _fail("MALFORMED_MARKER")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    keys: set[str] = set()
    i = 1
    while i < len(lines) - 1:
        parsed = _parse_header(lines[i])
        if parsed is None:
            _fail("MALFORMED_MARKER")
        action, source_text = parsed
        source_text, source = _validate_path(source_text, root)
        i += 1
        body: list[str] = []
        move_text: str | None = None
        while i < len(lines) - 1 and _parse_header(lines[i]) is None:
            line = lines[i]
            if action == "UPDATE" and line.startswith("*** Move to: "):
                if move_text is not None:
                    _fail("MALFORMED_MARKER")
                move_text, _ = _validate_path(line[len("*** Move to: "):], root)
            elif line.startswith("*** "):
                _fail("MALFORMED_MARKER")
            else:
                body.append(line)
            i += 1
        if action == "ADD" and any(not line.startswith("+") for line in body):
            _fail("MALFORMED_PATCH")
        if action == "DELETE" and body:
            _fail("MALFORMED_PATCH")
        if action == "UPDATE" and move_text is None and (not body or not any(line.startswith("@@") for line in body)):
            _fail("MALFORMED_PATCH")
        if action == "UPDATE" and move_text is not None:
            if body and not any(line.startswith("@@") for line in body):
                _fail("MALFORMED_PATCH")
            _, destination = _validate_path(move_text, root)
            _add_target(records, _move_record(source_text, source, move_text, destination, root), seen, keys)
        else:
            _, target = _validate_path(source_text, root)
            state = _stat_record(target, include_digest=False)
            if action == "ADD" and state["exists"]:
                _fail("TARGET_EXISTS")
            if action in {"DELETE", "UPDATE"} and not state["exists"]:
                _fail("TARGET_MISSING")
            _add_target(records, _record(action.title(), source_text, target, root), seen, keys)
    if not records:
        _fail("EMPTY_PATCH")
    target_paths = sorted(seen)
    scope_digest = _digest(target_paths)
    intent = {
        "tool_name": "apply_patch",
        "intent_sha256": "",
        "command_sha256": hashlib.sha256(raw).hexdigest(),
        "targets": records,
        "target_paths": target_paths,
        "scope_digest": scope_digest,
    }
    unsigned = dict(intent)
    unsigned["intent_sha256"] = ""
    intent["intent_sha256"] = _digest(unsigned)
    return intent


def revalidate_intent(intent: dict[str, Any], repo_root: str | os.PathLike[str]) -> bool:
    if not isinstance(intent, dict) or set(intent) != {"tool_name", "intent_sha256", "command_sha256", "targets", "target_paths", "scope_digest"} or intent.get("tool_name") != "apply_patch":
        _fail("INTENT_INVALID")
    try:
        if not isinstance(intent["targets"], list) or not 0 < len(intent["targets"]) <= MAX_TARGETS:
            _fail("INTENT_INVALID")
        for digest_name in ("intent_sha256", "command_sha256", "scope_digest"):
            value = intent.get(digest_name)
            if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                _fail("INTENT_INVALID")
        if not isinstance(intent["target_paths"], list) or len(intent["target_paths"]) > MAX_TARGETS:
            _fail("INTENT_INVALID")
        paths: list[str] = []
        for target in intent["targets"]:
            if not isinstance(target, dict):
                _fail("INTENT_INVALID")
            action = target.get("action")
            base = {"action", "path", "exists", "path_fingerprint", "parent_chain", "parent_fingerprint"}
            move = {"source_path", "source_fingerprint", "source_parent_chain", "source_parent_fingerprint"}
            expected_keys = base | move if action == "Move" else base
            if set(target) != expected_keys or action not in {"Add", "Delete", "Update", "Move"}:
                _fail("INTENT_INVALID")
            if (not isinstance(target.get("exists"), bool)
                    or not isinstance(target.get("path_fingerprint"), dict)
                    or target["exists"] != bool(target["path_fingerprint"].get("exists"))
                    or not isinstance(target.get("parent_chain"), list)
                    or target.get("parent_fingerprint") != _digest(target["parent_chain"])):
                _fail("INTENT_INVALID")
            if action == "Move" and (
                    not isinstance(target.get("source_fingerprint"), dict)
                    or not isinstance(target.get("source_parent_chain"), list)
                    or target.get("source_parent_fingerprint") != _digest(target["source_parent_chain"])):
                _fail("INTENT_INVALID")
            for name in ("path", "source_path"):
                if name in target:
                    value = target[name]
                    if not isinstance(value, str):
                        _fail("INTENT_INVALID")
                    try:
                        too_long = len(value.encode("utf-8", errors="strict")) > MAX_PATH_BYTES
                    except UnicodeError:
                        _fail("INTENT_INVALID")
                    if too_long:
                        _fail("INTENT_INVALID")
                    paths.append(value)
        if sorted(paths) != intent["target_paths"] or len({os.path.normcase(path) for path in paths}) != len(paths):
            _fail("INTENT_INVALID")
        if intent["scope_digest"] != _digest(intent["target_paths"]):
            _fail("INTENT_INVALID")
        unsigned = dict(intent)
        expected_intent = unsigned.pop("intent_sha256", None)
        if not isinstance(expected_intent, str) or _digest({**unsigned, "intent_sha256": ""}) != expected_intent:
            _fail("INTENT_INVALID")
        root = safe_path(Path(repo_root))
        for target in intent.get("targets", []):
            path_text = target["path"]
            _, path = _validate_path(path_text, root)
            if target.get("source_path") is not None:
                _, source = _validate_path(target["source_path"], root)
                # 中文：移动源由 source_path 表示，必须与原始源前态核对。
                # English: A move source uses source_path and must match its original pre-state.
                expected_source = target.get("source_fingerprint")
                if expected_source is None:
                    _fail("INTENT_INVALID")
                if _stat_record(source) != expected_source:
                    _fail("INTENT_STALE_FILE")
                source_chain = target.get("source_parent_chain")
                if source_chain is not None and _digest(source_chain) != _digest(_parent_chain(source, root)):
                    _fail("INTENT_STALE_PARENT")
            expected = target.get("path_fingerprint")
            if expected is None or _stat_record(path) != expected:
                _fail("INTENT_STALE_FILE")
            chain = target.get("parent_chain")
            if chain is None or _digest(chain) != _digest(_parent_chain(path, root)):
                _fail("INTENT_STALE_PARENT")
    except KeyError:
        _fail("INTENT_INVALID")
    return True
