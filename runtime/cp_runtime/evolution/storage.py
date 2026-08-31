"""受控自进化状态存储。

实现安全路径、原子写入、跨平台锁文件和追加式哈希链。任何格式损坏均失败关闭，
不会跳过坏行后继续形成优化结论。
"""
from __future__ import annotations

import json
import os
import stat
import tempfile
import time
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .contracts import ContractError, canonical_json, sha256_hex, to_primitive, utc_now_iso, validate_project_id
from .redaction import contains_obvious_secret, redact

ZERO_HASH = "0" * 64


class StorageError(RuntimeError):
    """状态存储、路径或哈希链异常。"""


@dataclass(frozen=True)
class JsonLineRecord:
    relative_path: str
    line_number: int
    payload: Mapping[str, Any]
    raw_hash: str


class FileLock:
    """使用 O_EXCL 创建锁文件，兼容 Windows 与 Linux。"""

    def __init__(self, target: Path, timeout_seconds: float = 10.0, stale_seconds: float = 300.0) -> None:
        self.lock_path = Path(str(target) + ".lock")
        self.timeout_seconds = timeout_seconds
        self.stale_seconds = stale_seconds
        self._fd: Optional[int] = None
        self._owner_token = secrets.token_hex(16)

    def __enter__(self) -> "FileLock":
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
                self._fd = os.open(str(self.lock_path), flags, 0o600)
                content = json.dumps({"pid": os.getpid(), "created_at": utc_now_iso(), "owner_token": self._owner_token}, ensure_ascii=False)
                os.write(self._fd, content.encode("utf-8"))
                os.fsync(self._fd)
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.lock_path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > self.stale_seconds:
                    try:
                        self.lock_path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise StorageError("获取锁超时: %s" % self.lock_path)
                time.sleep(0.05)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            finally:
                self._fd = None
        try:
            current = json.loads(self.lock_path.read_text(encoding="utf-8"))
            if current.get("owner_token") == self._owner_token:
                self.lock_path.unlink()
        except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
            pass


def _reject_symlink_components(path: Path, stop_at: Optional[Path] = None) -> None:
    current = path
    parts: List[Path] = []
    while True:
        parts.append(current)
        if stop_at is not None and current == stop_at:
            break
        if current.parent == current:
            break
        current = current.parent
    for item in reversed(parts):
        try:
            mode = item.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise StorageError("安全路径中不允许符号链接: %s" % item)


def resolve_project_dir(context_root: Path, project_id: str, create: bool = False) -> Path:
    validate_project_id(project_id)
    root = Path(context_root).expanduser().absolute()
    if root.exists() and not root.is_dir():
        raise StorageError("context_root 不是目录: %s" % root)
    if create:
        root.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(root)
    project_dir = root / project_id
    if create:
        project_dir.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(project_dir, root)
    root_resolved = root.resolve(strict=False)
    project_resolved = project_dir.resolve(strict=False)
    try:
        project_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise StorageError("项目目录越过 context_root") from exc
    return project_resolved


def safe_child(base: Path, *parts: str, create_parent: bool = False) -> Path:
    base = Path(base).absolute()
    candidate = base.joinpath(*parts)
    for part in parts:
        normalized = str(part).replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise StorageError("不安全的路径片段: %s" % part)
    if create_parent:
        candidate.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(candidate.parent, base)
    base_resolved = base.resolve(strict=False)
    candidate_resolved = candidate.resolve(strict=False)
    try:
        candidate_resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise StorageError("路径越过安全根目录: %s" % candidate) from exc
    return candidate_resolved


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except (OSError, AttributeError):
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write_text(path: Path, content: str, mode: int = 0o600) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(path.parent)
    if path.exists() and path.is_symlink():
        raise StorageError("拒绝覆盖符号链接: %s" % path)
    with FileLock(path):
        fd, temporary_name = tempfile.mkstemp(prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
        temporary = Path(temporary_name)
        try:
            os.chmod(temporary, mode)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary), str(path))
            _fsync_directory(path.parent)
        finally:
            if temporary.exists():
                temporary.unlink()


def atomic_write_json(path: Path, value: Any) -> None:
    safe_value = redact(to_primitive(value))
    if contains_obvious_secret(safe_value):
        raise StorageError("写入内容仍包含疑似敏感信息")
    content = json.dumps(safe_value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    atomic_write_text(path, content)



def exclusive_write_json(path: Path, value: Any) -> None:
    """只允许首次创建；存在同名快照时失败关闭，禁止静默覆盖。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(path.parent)
    payload = json.dumps(to_primitive(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise StorageError("不可变文件已存在，拒绝覆盖: %s" % path) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise

def read_json(path: Path, max_bytes: int = 20 * 1024 * 1024) -> Any:
    path = Path(path)
    if path.is_symlink():
        raise StorageError("拒绝读取符号链接: %s" % path)
    size = path.stat().st_size
    if size > max_bytes:
        raise StorageError("JSON 文件超过大小限制: %s" % path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StorageError("JSON 文件格式损坏: %s" % path) from exc


def read_jsonl(
    path: Path,
    relative_to: Optional[Path] = None,
    max_bytes: int = 20 * 1024 * 1024,
    max_records: int = 200000,
) -> List[JsonLineRecord]:
    path = Path(path)
    if path.is_symlink():
        raise StorageError("拒绝读取符号链接 JSONL: %s" % path)
    if not path.exists() or not path.is_file():
        raise StorageError("JSONL 文件不存在: %s" % path)
    if path.stat().st_size > max_bytes:
        raise StorageError("JSONL 文件超过大小限制: %s" % path)
    if relative_to is None:
        relative = path.name
    else:
        try:
            relative = path.resolve().relative_to(Path(relative_to).resolve()).as_posix()
        except ValueError as exc:
            raise StorageError("数据源不在项目上下文目录内: %s" % path) from exc
    records: List[JsonLineRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            if len(records) >= max_records:
                raise StorageError("JSONL 记录数超过限制: %s" % path)
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise StorageError("JSONL 第 %d 行损坏: %s" % (line_number, path)) from exc
            if not isinstance(payload, dict):
                raise StorageError("JSONL 第 %d 行必须是对象: %s" % (line_number, path))
            redacted_payload = redact(payload)
            records.append(JsonLineRecord(
                relative_path=relative,
                line_number=line_number,
                payload=redacted_payload,
                raw_hash=sha256_hex(redacted_payload),
            ))
    return records


def _chain_record(sequence: int, previous_hash: str, payload: Any, recorded_at: Optional[str] = None) -> Dict[str, Any]:
    timestamp = recorded_at or utc_now_iso()
    body: Dict[str, Any] = {
        "sequence": sequence,
        "previous_hash": previous_hash,
        "recorded_at": timestamp,
        "payload": redact(to_primitive(payload)),
    }
    body["record_hash"] = sha256_hex(body)
    return body


def verify_hash_chain(records: Sequence[Mapping[str, Any]]) -> None:
    previous_hash = ZERO_HASH
    for index, record in enumerate(records, start=1):
        if not isinstance(record, Mapping):
            raise StorageError("哈希链第 %d 条不是对象" % index)
        if record.get("sequence") != index:
            raise StorageError("哈希链 sequence 不连续，位置 %d" % index)
        if record.get("previous_hash") != previous_hash:
            raise StorageError("哈希链 previous_hash 不一致，位置 %d" % index)
        record_hash = record.get("record_hash")
        if not isinstance(record_hash, str) or len(record_hash) != 64:
            raise StorageError("哈希链 record_hash 非法，位置 %d" % index)
        body = {k: v for k, v in record.items() if k != "record_hash"}
        expected = sha256_hex(body)
        if expected != record_hash:
            raise StorageError("哈希链完整性失败，位置 %d" % index)
        previous_hash = record_hash


def read_hash_chain(path: Path, max_bytes: int = 20 * 1024 * 1024) -> List[Mapping[str, Any]]:
    if not Path(path).exists():
        return []
    rows = read_jsonl(path, max_bytes=max_bytes)
    records = [row.payload for row in rows]
    verify_hash_chain(records)
    return records


def append_hash_chain(path: Path, payload: Any) -> Mapping[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(path.parent)
    if path.exists() and path.is_symlink():
        raise StorageError("拒绝写入符号链接哈希链: %s" % path)
    with FileLock(path):
        if path.exists():
            rows = read_jsonl(path)
            existing = [row.payload for row in rows]
            verify_hash_chain(existing)
        else:
            existing = []
        previous_hash = existing[-1]["record_hash"] if existing else ZERO_HASH
        record = _chain_record(len(existing) + 1, previous_hash, payload)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        fd = os.open(str(path), flags, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        _fsync_directory(path.parent)
        return record
