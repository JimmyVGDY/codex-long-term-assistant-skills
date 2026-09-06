"""中文：有界、不可变且绑定项目的演进产物。

English: Bounded, immutable, project-bound evolution artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

from ..common import atomic_write_json, verify_record
from ..event_v3 import OwnerTokenLock, repo_fingerprint_for_identity, stable_repo_fingerprint
from .contracts import canonical_json, parse_iso_datetime, sha256_hex, utc_now_iso
from .storage import read_json, safe_child

MAX_BYTES = 20 * 1024 * 1024
MAX_ARTIFACT_BYTES = 1024 * 1024
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
HASH = re.compile(r"^[0-9a-f]{64}$")


class ArtifactError(ValueError):
    pass


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ArtifactError("INVALID_IDENTIFIER")
    return value


def seal(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    value.pop("content_hash", None)
    value["content_hash"] = sha256_hex(value)
    return value


def verify(value: Mapping[str, Any], schema: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("content_hash") != seal(value)["content_hash"]:
        raise ArtifactError("ARTIFACT_INTEGRITY_FAILURE")
    if schema and value.get("schema_version") != schema:
        raise ArtifactError("UNSUPPORTED_ARTIFACT_SCHEMA")
    if value.get("execution_authorization") != "NONE":
        raise ArtifactError("ARTIFACT_EXECUTION_AUTHORIZATION")
    return dict(value)


def load(root: Path, relative: str, content_hash: str | None = None, schema: str | None = None) -> dict[str, Any]:
    path = safe_child(root, relative)
    if path.is_symlink():
        raise ArtifactError("ARTIFACT_SYMLINK")
    value = verify(read_json(path, max_bytes=MAX_ARTIFACT_BYTES), schema)
    if content_hash is not None and value["content_hash"] != content_hash:
        raise ArtifactError("ARTIFACT_REFERENCE_MISMATCH")
    return value


def persist(root: Path, relative: str, value: Mapping[str, Any]) -> dict[str, str]:
    verified = verify(dict(value))
    if len(canonical_json(verified).encode("utf-8")) > MAX_ARTIFACT_BYTES:
        raise ArtifactError("ARTIFACT_TOO_LARGE")
    path = safe_child(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=2):
        if path.exists():
            if load(root, relative) != verified:
                raise ArtifactError("IMMUTABLE_ARTIFACT_CONFLICT")
        else:
            atomic_write_json(path, verified)
    return {"path": relative, "content_hash": verified["content_hash"]}


def project_identity(project_dir: Path, *, verify_live: bool = True) -> dict[str, str]:
    profile_path = safe_child(project_dir, "project-profile.json")
    profile = read_json(profile_path, max_bytes=MAX_ARTIFACT_BYTES)
    verify_record(profile, "project-profile")
    project_id = profile_path.parent.name
    if profile.get("project_id") != project_id:
        raise ArtifactError("PROJECT_IDENTITY_MISMATCH")
    identity = profile.get("identity") or {}
    if not identity.get("repo_path"):
        raise ArtifactError("PROJECT_IDENTITY_MISSING")
    root = str(Path(identity["repo_path"]).expanduser().resolve())
    fingerprint = repo_fingerprint_for_identity(root, str(identity.get("remote_origin") or ""))
    if verify_live and stable_repo_fingerprint(root) != fingerprint:
        raise ArtifactError("REPO_IDENTITY_MISMATCH")
    return {"project_id": project_id, "repo_fingerprint": fingerprint, "worktree_root": root}


def _git_bytes(repo: Path, arguments: list[str], timeout: float = 2) -> bytes:
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(["git", *arguments], cwd=repo, stdout=output, stderr=subprocess.DEVNULL, timeout=timeout)
        if result.returncode:
            raise ArtifactError("WORKTREE_GIT_UNAVAILABLE")
        if output.tell() > MAX_BYTES:
            raise ArtifactError("WORKTREE_TOO_LARGE")
        output.seek(0)
        return output.read()


def worktree_fingerprint(repo: Path, *, time_budget_seconds: float = 10) -> str:
    """中文：有界核对内容，临时差异不进入观察记录。

    English: Verify bounded content without retaining temporary diffs in observation records.
    """
    digest = hashlib.sha256()
    deadline = time.monotonic() + time_budget_seconds
    def remaining() -> float:
        value = deadline - time.monotonic()
        if value <= 0:
            raise ArtifactError("WORKTREE_TIME_BUDGET_EXHAUSTED")
        return min(2, value)
    for args in (["rev-parse", "HEAD"], ["status", "--porcelain=v1", "-z"],
                 ["diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD"]):
        digest.update(_git_bytes(repo, args, remaining()))
        digest.update(b"\0")
    names = sorted(filter(None, _git_bytes(repo, ["ls-files", "--others", "--exclude-standard", "-z"], remaining()).split(b"\0")))
    if len(names) > 1000:
        raise ArtifactError("WORKTREE_TOO_MANY_FILES")
    total = 0
    for name in names:
        remaining()
        path = repo / os.fsdecode(name)
        digest.update(name + b"\0")
        if path.is_symlink():
            content = os.fsencode(os.readlink(path))
        else:
            total += path.stat().st_size
            if total > MAX_BYTES:
                raise ArtifactError("WORKTREE_TOO_LARGE")
            content = path.read_bytes()
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()
