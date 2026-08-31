"""Shared deterministic I/O, integrity and Git snapshot helpers."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

FULL_HASH_LIMIT = 4 * 1024 * 1024
SAMPLE_BYTES = 1024 * 1024
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SENSITIVE_PATTERNS = (
    ("OpenAI/API Key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Bearer Token", re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    ("Credential URI", re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/:]+:[^\s/@]+@")),
    ("Generic Secret", re.compile(r"(?i)\b(password|passwd|token|secret|access[_-]?key|secret[_-]?key)\b\s*[:=]\s*([^\s`]+)")),
)


class RuntimeContractError(RuntimeError):
    """A fail-closed contract violation."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise RuntimeContractError("时间必须包含时区")
    return parsed.astimezone(timezone.utc)


def validate_identifier(value: str, label: str) -> str:
    candidate = value.strip()
    if not ID_RE.fullmatch(candidate):
        raise RuntimeContractError(f"{label} 格式非法: {value!r}")
    return candidate


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record_without_integrity(value: Dict[str, Any]) -> Dict[str, Any]:
    copied = dict(value)
    copied.pop("integrity", None)
    return copied


def seal_record(value: Dict[str, Any]) -> Dict[str, Any]:
    sealed = record_without_integrity(value)
    sealed["integrity"] = {
        "algorithm": "sha256-canonical-json",
        "sha256": canonical_sha256(sealed),
    }
    return sealed


def verify_record(value: Dict[str, Any], label: str = "记录") -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "sha256-canonical-json":
        raise RuntimeContractError(label + "缺少受支持的完整性字段")
    expected = integrity.get("sha256")
    actual = canonical_sha256(record_without_integrity(value))
    if expected != actual:
        raise RuntimeContractError(label + "完整性校验失败")


def read_json(path: Path, verify: bool = False, label: str = "记录") -> Dict[str, Any]:
    if not path.is_file():
        raise RuntimeContractError(f"缺少文件: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeContractError(f"读取 JSON 失败 {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeContractError(f"JSON 顶层必须是对象: {path}")
    if verify:
        verify_record(value, label)
    return value


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        temp_path = Path(temp_name)
        if temp_path.exists():
            temp_path.unlink()


def atomic_write_text(path: Path, content: str) -> None:
    atomic_write_bytes(path, content.encode("utf-8"))


def atomic_write_json(path: Path, value: Dict[str, Any], seal: bool = False) -> Dict[str, Any]:
    final_value = seal_record(value) if seal else value
    text = json.dumps(final_value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_text(path, text)
    return final_value


def append_jsonl(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = canonical_json(value) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def require_external_state(path: Path, repo: Path, allow_inside_repo: bool = False) -> None:
    if inside(path, repo) and not allow_inside_repo:
        raise RuntimeContractError("项目治理状态默认必须保存在业务仓库外")


def resolve_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser().resolve() if configured else (Path.home() / ".codex").resolve()


def normalize_environment(value: str) -> str:
    aliases = {
        "dev": "nonproduction",
        "development": "nonproduction",
        "test": "nonproduction",
        "testing": "nonproduction",
        "staging": "nonproduction",
        "pre": "nonproduction",
        "prod": "production",
    }
    normalized = aliases.get(value.strip().lower(), value.strip().lower())
    if normalized not in {"local", "nonproduction", "production"}:
        raise RuntimeContractError("environment 仅允许 local/nonproduction/production")
    return normalized


def scan_sensitive_text(values: Sequence[str]) -> List[str]:
    findings: List[str] = []
    text = "\n".join(values)
    for name, pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            findings.append(name)
    return findings


def run_process(command: Sequence[str], cwd: Optional[Path] = None, allow_fail: bool = False) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode and not allow_fail:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeContractError("命令失败: {}\n{}".format(" ".join(command), stderr))
    return result


def git(repo: Path, args: Sequence[str], allow_fail: bool = False) -> bytes:
    return run_process(["git", *args], cwd=repo, allow_fail=allow_fail).stdout


def ensure_git_repo(repo: Path) -> Path:
    resolved = repo.expanduser().resolve()
    if not resolved.is_dir():
        raise RuntimeContractError("仓库目录不存在: " + str(resolved))
    result = run_process(["git", "rev-parse", "--show-toplevel"], cwd=resolved, allow_fail=True)
    if result.returncode:
        raise RuntimeContractError("目标目录不是 Git 仓库: " + str(resolved))
    root = Path(result.stdout.decode("utf-8", errors="surrogateescape").strip()).resolve()
    if root != resolved:
        resolved = root
    return resolved


def sampled_file_digest(path: Path) -> Tuple[str, str]:
    info = path.lstat()
    digest = hashlib.sha256()
    digest.update(str(info.st_mode).encode())
    digest.update(b"\0")
    digest.update(str(info.st_size).encode())
    digest.update(b"\0")
    if stat.S_ISLNK(info.st_mode):
        digest.update(os.readlink(path).encode(errors="surrogateescape"))
        return digest.hexdigest(), "symlink"
    if not stat.S_ISREG(info.st_mode):
        digest.update(str(info.st_mtime_ns).encode())
        return digest.hexdigest(), "metadata"
    with path.open("rb") as handle:
        if info.st_size <= FULL_HASH_LIMIT:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
            return digest.hexdigest(), "full"
        digest.update(handle.read(SAMPLE_BYTES))
        handle.seek(max(0, info.st_size - SAMPLE_BYTES))
        digest.update(handle.read(SAMPLE_BYTES))
        digest.update(str(info.st_mtime_ns).encode())
        return digest.hexdigest(), "sampled"


def untracked_fingerprint(repo: Path) -> Dict[str, Any]:
    raw = git(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    names = [item for item in raw.split(b"\0") if item]
    digest = hashlib.sha256()
    sampled_count = 0
    for raw_name in sorted(names):
        relative = raw_name.decode("utf-8", errors="surrogateescape")
        path = repo / relative
        digest.update(raw_name)
        digest.update(b"\0")
        if not path.exists() and not path.is_symlink():
            digest.update(b"missing")
            continue
        file_digest, mode = sampled_file_digest(path)
        if mode == "sampled":
            sampled_count += 1
        digest.update(mode.encode())
        digest.update(b":")
        digest.update(file_digest.encode())
        digest.update(b"\0")
    return {
        "sha256": digest.hexdigest(),
        "count": len(names),
        "sampled_count": sampled_count,
    }


def optional_git_text(repo: Path, args: Sequence[str]) -> str:
    result = run_process(["git", *args], cwd=repo, allow_fail=True)
    if result.returncode:
        return ""
    return result.stdout.decode("utf-8", errors="replace").strip()


def repo_snapshot(repo: Path) -> Dict[str, Any]:
    root = ensure_git_repo(repo)
    head = git(root, ["rev-parse", "HEAD"]).decode().strip()
    branch = optional_git_text(root, ["symbolic-ref", "--quiet", "--short", "HEAD"]) or "DETACHED"
    remote = optional_git_text(root, ["config", "--get", "remote.origin.url"])
    status_data = git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    diff_data = git(root, ["diff", "--binary", "--no-ext-diff", "HEAD", "--"])
    staged_data = git(root, ["diff", "--cached", "--binary", "--no-ext-diff", "HEAD", "--"])
    untracked = untracked_fingerprint(root)
    digest = hashlib.sha256()
    for part in (head.encode(), status_data, diff_data, staged_data, untracked["sha256"].encode()):
        digest.update(part)
        digest.update(b"\0")
    upstream_head = optional_git_text(root, ["rev-parse", "@{upstream}"])
    return {
        "repo_path": str(root),
        "remote_origin": remote,
        "branch": branch,
        "head": head,
        "upstream_head": upstream_head,
        "tracking_matches_head": bool(upstream_head and upstream_head == head),
        "clean": not bool(status_data),
        "sha256": digest.hexdigest(),
        "status_sha256": hashlib.sha256(status_data).hexdigest(),
        "diff_sha256": hashlib.sha256(diff_data).hexdigest(),
        "staged_sha256": hashlib.sha256(staged_data).hexdigest(),
        "untracked_sha256": untracked["sha256"],
        "untracked_count": untracked["count"],
        "untracked_sampled_count": untracked["sampled_count"],
        "captured_at": utc_now(),
    }


def tree_sha256(path: Path) -> str:
    root = path.resolve()
    digest = hashlib.sha256()
    if root.is_file():
        return file_sha256(root)
    for item in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        relative = item.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        if item.is_symlink():
            digest.update(b"L")
            digest.update(os.readlink(item).encode(errors="surrogateescape"))
        elif item.is_file():
            digest.update(b"F")
            digest.update(file_sha256(item).encode())
        elif item.is_dir():
            digest.update(b"D")
        digest.update(b"\0")
    return digest.hexdigest()


def assert_managed_target(target: Path, managed_root: Path) -> None:
    resolved_target = target.expanduser().resolve()
    resolved_root = managed_root.expanduser().resolve()
    if resolved_target == resolved_root:
        raise RuntimeContractError("禁止把受管根目录本身作为替换目标")
    if not inside(resolved_target, resolved_root):
        raise RuntimeContractError(f"目标路径越界: {resolved_target}")
