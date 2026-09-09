"""中文：项目能力事实索引：有界、身份绑定、可恢复的单协调者存储。 English: Bounded, identity-bound, recoverable coordinator-owned capability fact storage."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from collections import Counter
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from threading import get_ident
from typing import Any

from .atomic_io import native_path

from .common import (
    RuntimeContractError, atomic_write_bytes, canonical_json, require_external_state,
    optional_git_text, parse_iso, scan_sensitive_text, seal_record, verify_record,
)
from .event_v3 import OwnerTokenLock, repo_fingerprint_for_identity
from .project import validate_binding

MAX_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 2000
HASH = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
REASONS = {
    "UNSCANNED", "BUDGET", "UNSUPPORTED", "UNREADABLE", "TOO_LARGE",
    "SENSITIVE_CONTENT", "EXCLUDED", "CHANGED", "MISSING", "PARSE_ERROR", "DIRECTORY_BUDGET",
}
DENIED_PARTS = {".git", ".ssh", ".aws", ".azure", ".kube", "credentials", "secrets"}
DENIED_NAMES = {"credentials.json", "credentials.ini", "id_rsa", "id_ed25519", ".netrc", ".npmrc"}


class CapabilityError(RuntimeContractError):
    """中文：只暴露固定原因码，不把源内容或底层异常写入诊断。 English: Expose fixed reason codes without source content or underlying exception text."""


def require(condition: bool, code: str = "INVALID_SCHEMA") -> None:
    if not condition:
        raise CapabilityError(code)


def unique_json_object(pairs):
    """中文：所有JSON入口使用相同的重复字段拒绝规则。 English: Reject duplicate fields consistently at every JSON entry point."""
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_FIELD")
        result[key] = value
    return result


def safe_path(path: Path) -> Path:
    """中文：解析前拒绝各级链接及 Windows reparse point。 English: Reject ancestor links and Windows reparse points before resolving paths."""
    path = Path(os.path.abspath(path.expanduser()))
    for item in reversed((path, *path.parents)):
        try:
            info = native_path(item).lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise CapabilityError("PATH_UNREADABLE") from None
        require(not stat.S_ISLNK(info.st_mode) and not (
            getattr(info, "st_file_attributes", 0) & 0x400
        ), "LINK_REJECTED")
    return path.resolve()


def relative_path(value: Any) -> str:
    require(isinstance(value, str) and 0 < len(value) <= 1024, "INVALID_PATH")
    require("\\" not in value and ":" not in value and not any(ord(c) < 32 for c in value), "INVALID_PATH")
    parts = value.split("/")
    require(not PurePosixPath(value).is_absolute() and all(p not in {"", ".", ".."} for p in parts), "INVALID_PATH")
    lower = [p.lower() for p in parts]
    require(not any(p in DENIED_PARTS or p.startswith(".env") for p in lower), "SENSITIVE_PATH")
    require(lower[-1] not in DENIED_NAMES and Path(lower[-1]).suffix not in {".pem", ".key", ".p12", ".pfx"}, "SENSITIVE_PATH")
    text_field(value, 1024)
    return value


def text_field(value: Any, limit: int = 500) -> None:
    require(isinstance(value, str) and len(value) <= limit)
    require(not scan_sensitive_text([value]), "SENSITIVE_CONTENT")
    require(not re.search(r"-----BEGIN .*PRIVATE KEY|(?i:bearer)\s+\S{16,}", value), "SENSITIVE_CONTENT")
    for token in re.findall(r"[A-Za-z0-9_+/=-]{32,}", value):
        entropy = -sum((n / len(token)) * math.log2(n / len(token)) for n in Counter(token).values())
        require(entropy < 4.3, "SENSITIVE_CONTENT")


def fields(value: Any, names: set[str]) -> None:
    require(isinstance(value, dict) and set(value) == names)


def integer(value: Any, maximum: int) -> None:
    require(type(value) is int and 0 <= value <= maximum)


def hash_field(value: Any) -> None:
    require(isinstance(value, str) and HASH.fullmatch(value) is not None)


def time_field(value: Any) -> None:
    if value is not None:
        require(isinstance(value, str) and len(value) <= 64)
        try:
            parse_iso(value)
        except (ValueError, RuntimeContractError):
            raise CapabilityError("INVALID_TIMESTAMP") from None


def bounded_read(path: Path, limit: int = MAX_BYTES) -> bytes:
    path = safe_path(path)
    try:
        before = native_path(path).stat()
        require(stat.S_ISREG(before.st_mode), "NOT_REGULAR_FILE")
        require(before.st_size <= limit, "TOO_LARGE")
        with native_path(path).open("rb") as stream:
            opened = os.fstat(stream.fileno())
            require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), "READ_CHANGED")
            data = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        final = native_path(safe_path(path)).stat()
        require(len(data) <= limit, "TOO_LARGE")
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
        # 中文：Windows路径stat与句柄fstat的ctime口径可能不同；各自前后比较。 English: Windows path stat and handle fstat may use different ctime semantics; compare each API before and after.
        require(stamp(before) == stamp(opened) == stamp(after) == stamp(final)
                and before.st_ctime_ns == final.st_ctime_ns
                and opened.st_ctime_ns == after.st_ctime_ns, "READ_CHANGED")
        return data
    except OSError:
        raise CapabilityError("UNREADABLE") from None


def validate_payload(payload: Any) -> None:
    fields(payload, {"baseline", "coverage", "entries"})
    baseline = payload["baseline"]
    fields(baseline, {"head", "branch", "files"})
    require(isinstance(baseline["head"], str) and (baseline["head"] == "" or re.fullmatch(r"[0-9a-f]{40,64}", baseline["head"]) is not None))
    text_field(baseline["branch"], 256)
    require(isinstance(baseline["files"], dict) and len(baseline["files"]) <= MAX_ENTRIES)
    for path, digest in baseline["files"].items():
        relative_path(path)
        hash_field(digest)
    coverage = payload["coverage"]
    fields(coverage, {"scopes", "complete", "cursor", "limitations"})
    require(type(coverage["complete"]) is bool)
    require(isinstance(coverage["scopes"], list) and len(coverage["scopes"]) <= 128)
    for scope in coverage["scopes"]:
        if scope != ".":
            relative_path(scope)
    if coverage["cursor"] is not None:
        fields(coverage["cursor"], {"pending"})
        require(isinstance(coverage["cursor"]["pending"], list)
                and 0 < len(coverage["cursor"]["pending"]) <= MAX_ENTRIES)
        for pending in coverage["cursor"]["pending"]:
            if pending != ".":
                relative_path(pending)
    require(not coverage["complete"] or coverage["cursor"] is None)
    require(isinstance(coverage["limitations"], list) and len(coverage["limitations"]) <= MAX_ENTRIES)
    for item in coverage["limitations"]:
        fields(item, {"path", "reason"})
        # 中文：被排除秘密路径不持久化名称，只保留空定位和原因码。 English: Do not persist excluded secret-path names; retain only an empty location and reason code.
        if item["path"] is not None:
            relative_path(item["path"])
        require(isinstance(item["reason"], str) and item["reason"] in REASONS)
    entries = payload["entries"]
    require(isinstance(entries, list) and len(entries) <= MAX_ENTRIES)
    ids: set[str] = set()
    locators: set[tuple[str, str]] = set()
    for entry in entries:
        fields(entry, {"id", "kind", "path", "symbol", "summary", "keywords", "boundaries", "references", "file_sha256", "observed_baseline", "observed_at", "lifecycle", "freshness", "verification"})
        require(isinstance(entry["id"], str) and ID.fullmatch(entry["id"]) is not None and entry["id"] not in ids)
        require(not scan_sensitive_text([entry["id"]]), "SENSITIVE_CONTENT")
        ids.add(entry["id"])
        require(isinstance(entry["kind"], str) and entry["kind"] in {"function", "class", "component", "service", "adapter", "module"})
        relative_path(entry["path"])
        text_field(entry["symbol"], 256)
        locator = (entry["path"], entry["symbol"])
        require(locator not in locators, "DUPLICATE_LOCATOR")
        locators.add(locator)
        text_field(entry["summary"])
        for key in ("keywords", "boundaries"):
            require(isinstance(entry[key], list) and len(entry[key]) <= 10)
            for item in entry[key]:
                text_field(item, 128 if key == "keywords" else 500)
        fields(entry["references"], {"callers", "tests", "context"})
        for refs in entry["references"].values():
            require(isinstance(refs, list) and len(refs) <= 5)
            for ref in refs:
                fields(ref, {"path", "sha256"})
                relative_path(ref["path"])
                hash_field(ref["sha256"])
        if entry["file_sha256"] is not None:
            hash_field(entry["file_sha256"])
        fields(entry["observed_baseline"], {"head", "branch"})
        observed_head = entry["observed_baseline"]["head"]
        require(isinstance(observed_head, str) and (observed_head == "" or re.fullmatch(r"[0-9a-f]{40,64}", observed_head) is not None))
        text_field(entry["observed_baseline"]["branch"], 256)
        time_field(entry["observed_at"])
        require(isinstance(entry["lifecycle"], str) and entry["lifecycle"] in {"candidate", "active", "deprecated", "removed"})
        require(isinstance(entry["freshness"], str) and entry["freshness"] in {"matched", "recheck", "stale", "unknown"})
        require(entry["freshness"] != "matched" or entry["file_sha256"] is not None)
        fields(entry["verification"], {"scope", "evidence", "recorded_at"})
        time_field(entry["verification"]["recorded_at"])
        text_field(entry["verification"]["scope"])
        require(isinstance(entry["verification"]["evidence"], list) and len(entry["verification"]["evidence"]) <= 5)
        for ref in entry["verification"]["evidence"]:
            text_field(ref, 256)


def empty_payload() -> dict[str, Any]:
    return {"baseline": {"head": "", "branch": "", "files": {}},
            "coverage": {"scopes": [], "complete": False, "cursor": None,
                         "limitations": [{"path": None, "reason": "UNSCANNED"}]}, "entries": []}


class CapabilityStore:
    """中文：索引可失效和重建；不写 Profile、稳定记忆或业务文件。 English: Indexes can expire and be rebuilt; never write Profiles, stable memory, or business files."""

    def __init__(self, profile_path: Path, repo_path: Path, index_root: Path | None = None):
        require(index_root is None or index_root.expanduser().is_absolute(), "INVALID_INDEX_ROOT")
        self.profile_path = safe_path(profile_path)
        self.repo_path = safe_path(repo_path)
        worktree_id = hashlib.sha256(os.path.normcase(str(self.repo_path)).encode("utf-8")).hexdigest()
        container = safe_path(self.profile_path.parent / "capability-index")
        self.root = safe_path(index_root or container / worktree_id)
        # 中文：保留目录只容纳工作区索引，不能成为第二份并行快照。 English: The reserved container holds worktree indexes, never a parallel snapshot itself.
        require(self.root != container, "INDEX_ROOT_IS_CONTAINER_OMIT_OVERRIDE")
        require_external_state(self.root, self.repo_path)
        self.current = self.root / "index.json"
        self.previous = self.root / "index.previous.json"
        self.lock = OwnerTokenLock(self.current)
        self._identity_session = None
        self.identity = self._live_identity(worktree_id)

    def _live_identity(self, worktree_id: str) -> dict[str, str]:
        self._paths()
        # 中文：现有绑定读取器之前先执行体积和链接限制。 English: Enforce size and link limits before the existing binding reader.
        profile_raw = bounded_read(self.profile_path)
        state_path = self.profile_path.with_name("project-state.json")
        state_raw = bounded_read(state_path)
        if self._identity_session is not None:
            owner, expected_profile, expected_state = self._identity_session
            require(owner == get_ident() and profile_raw == expected_profile and state_raw == expected_state,
                    "IDENTITY_CHANGED")
            return dict(self.identity)
        try:
            binding = validate_binding(self.profile_path, self.repo_path)
        except (RuntimeContractError, OSError, ValueError, KeyError, TypeError):
            raise CapabilityError("PROFILE_BINDING_INVALID") from None
        require(profile_raw == bounded_read(self.profile_path) and state_raw == bounded_read(state_path), "IDENTITY_CHANGED")
        return {"project_id": binding.project_id,
                "repo_fingerprint": repo_fingerprint_for_identity(str(self.repo_path), optional_git_text(self.repo_path, ["config", "--get", "remote.origin.url"])),
                "profile_path": str(self.profile_path), "profile_binding": binding.profile_sha256,
                "worktree_root": str(self.repo_path), "worktree_id": worktree_id, "index_root": str(self.root)}

    def _paths(self) -> None:
        for path in (self.repo_path, self.profile_path, self.root, self.current, self.previous, self.lock.path):
            safe_path(path)

    def _guard(self) -> None:
        require(self._live_identity(self.identity["worktree_id"]) == self.identity, "IDENTITY_CHANGED")

    @contextmanager
    def bounded_identity_session(self):
        """中文：单次有超时的Hook内合并Git身份探测；返回响应前必须完成出口全检。

        English: Coalesce Git identity probes in one supervised Hook; full exit validation precedes its response.
        Profile/state bytes and path safety remain checked at every guard. No cache survives this scope,
        no other thread may use it, and persisted state still needs an independent completion check.
        """
        require(self._identity_session is None, "IDENTITY_SESSION_ACTIVE")
        profile = bounded_read(self.profile_path)
        state = bounded_read(self.profile_path.with_name("project-state.json"))
        self._guard()
        require(profile == bounded_read(self.profile_path)
                and state == bounded_read(self.profile_path.with_name("project-state.json")), "IDENTITY_CHANGED")
        self._identity_session = (get_ident(), profile, state)
        try:
            yield
        finally:
            self._identity_session = None
            self._guard()

    def _decode(self, raw: bytes) -> dict[str, Any]:
        try:
            value = json.loads(raw, object_pairs_hook=unique_json_object)
        except (ValueError, UnicodeError, RecursionError):
            raise CapabilityError("INVALID_JSON") from None
        fields(value, {"schema_version", "revision", "identity", "baseline", "coverage", "entries", "recovery_source", "integrity"})
        require(type(value["schema_version"]) is int and value["schema_version"] == 1, "UNKNOWN_SCHEMA")
        integer(value["revision"], 2**63 - 1)
        require(value["identity"] == self.identity, "IDENTITY_MISMATCH")
        fields(value["integrity"], {"algorithm", "sha256"})
        verify_record(value, "CapabilityIndex")
        if value["recovery_source"] is not None:
            require(value["recovery_source"] == "MISSING" or HASH.fullmatch(str(value["recovery_source"])) is not None)
        validate_payload(self.payload(value))
        return value

    @staticmethod
    def payload(value: dict[str, Any]) -> dict[str, Any]:
        return {key: value[key] for key in ("baseline", "coverage", "entries")}

    def read(self) -> dict[str, Any]:
        self._guard()
        require(native_path(self.current).exists(), "INDEX_MISSING")
        result = self._decode(bounded_read(self.current))
        self._guard()
        return result

    def _encode(self, payload: dict[str, Any], revision: int, recovery: str | None = None) -> bytes:
        validate_payload(payload)
        record = seal_record({"schema_version": 1, "revision": revision, "identity": self.identity,
                              **payload, "recovery_source": recovery})
        raw = (canonical_json(record) + "\n").encode("utf-8")
        require(len(raw) <= MAX_BYTES, "TOO_LARGE")
        self._decode(raw)
        return raw

    def commit(self, payload: dict[str, Any], expected_revision: int | None) -> dict[str, Any]:
        # 中文：序列化复制避免调用者在等待锁期间改动输入。 English: Copy through serialization so callers cannot mutate input while the lock is awaited.
        validate_payload(payload)
        try:
            candidate = json.loads(canonical_json(payload))
        except (ValueError, TypeError, RecursionError):
            raise CapabilityError("INVALID_SCHEMA") from None
        validate_payload(candidate)
        if expected_revision is not None:
            integer(expected_revision, 2**63 - 2)
        self._guard()
        with self.lock:
            self._guard()
            if expected_revision is None:
                require(not native_path(self.current).exists() and not native_path(self.previous).exists(), "ALREADY_EXISTS")
                raw = self._encode(candidate, 0)
            else:
                old_raw = bounded_read(self.current)
                old = self._decode(old_raw)
                require(old["revision"] == expected_revision, "REVISION_CONFLICT")
                if self.payload(old) == candidate:
                    return old
                raw = self._encode(candidate, expected_revision + 1)
                atomic_write_bytes(self.previous, old_raw)
                require(bounded_read(self.previous) == old_raw, "PREVIOUS_VERIFY_FAILED")
            self._paths()
            try:
                atomic_write_bytes(self.current, raw)
                require(bounded_read(self.current) == raw, "COMMIT_UNCERTAIN")
                self._guard()
            except (OSError, RuntimeContractError):
                raise CapabilityError("COMMIT_UNCERTAIN") from None
            return self._decode(raw)

    def recover(self, expected_current_sha256: str) -> dict[str, Any]:
        require(isinstance(expected_current_sha256, str) and (expected_current_sha256 == "MISSING" or HASH.fullmatch(expected_current_sha256) is not None))
        self._guard()
        with self.lock:
            self._guard()
            raw = bounded_read(self.current) if native_path(self.current).exists() else None
            actual = hashlib.sha256(raw).hexdigest() if raw is not None else "MISSING"
            require(actual == expected_current_sha256, "RECOVERY_CONFLICT")
            previous = self._decode(bounded_read(self.previous))
            if raw is not None:
                try:
                    header = json.loads(raw, object_pairs_hook=unique_json_object)
                except (ValueError, UnicodeError, RecursionError):
                    header = None
                if isinstance(header, dict):
                    require(type(header.get("schema_version")) is int and header["schema_version"] == 1, "UNKNOWN_SCHEMA")
                    require(header.get("identity") == self.identity, "IDENTITY_MISMATCH")
            try:
                current = self._decode(raw) if raw is not None else None
            except RuntimeContractError:
                current = None
            if current is not None:
                if current["recovery_source"] is not None and self.payload(current) == self.payload(previous):
                    return current
                require(previous["revision"] < current["revision"], "INVALID_RECOVERY_ORDER")
            if raw is not None:
                archive = self.root / ("index.recovery-" + actual + ".bin")
                safe_path(archive)
                if native_path(archive).exists():
                    require(bounded_read(archive) == raw, "RECOVERY_ARCHIVE_CONFLICT")
                else:
                    atomic_write_bytes(archive, raw)
                require(bounded_read(archive) == raw, "RECOVERY_ARCHIVE_CONFLICT")
            revision = max(previous["revision"] + 2, current["revision"] + 1 if current else 0)
            restored = self._encode(self.payload(previous), revision, actual)
            try:
                atomic_write_bytes(self.current, restored)
                require(bounded_read(self.current) == restored, "COMMIT_UNCERTAIN")
                self._guard()
            except (OSError, RuntimeContractError):
                raise CapabilityError("COMMIT_UNCERTAIN") from None
            return self._decode(restored)
