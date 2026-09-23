"""中文：持久、签名的 SessionEnd 追加与封印队列。

English: Durable, signed SessionEnd append-and-seal queue.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .event_v3 import OwnerTokenLock, append_event, canonical_json, make_event, read_event_chain, verify_event_chain
from .integrity import active_secret, seal_event_chain, secret_by_id
from .atomic_io import native_path, replace_with_retry
from .capability_store import CapabilityError, bounded_read, unique_json_object

JOB_SCHEMA = "1.0"
JOB_IDENTITY_VERSION = 2
JOB_STATES = ("pending", "running", "done", "dead-letter")
JOB_NAME = re.compile(r"^job-[0-9a-f]{64}\.json$")
BOOTSTRAP_EVENT_MAX_BYTES = 8192
RECOVERY_SCHEMA = "1.0"
RECOVERY_RECEIPT_SCHEMA = "2.0"
RECOVERY_ROUTE_NAME = "session-end-root-selection-v1.json"
RECOVERY_RECEIPT_DIRECTORY = "session-end-recovery-v1"
RECOVERY_GUARD_NAME = "session-end-root-selection-v1.guard"
TEMPORARY_V7_NAME = "codex-cp-assistant-v7"
TEMPORARY_V6_NAME = "codex-cp-assistant-v6"
RECOVERY_RECORD_MAX_BYTES = 4096
MAX_RECOVERY_RECEIPTS = 128


class SealQueueError(RuntimeError):
    pass


class _PreAppendPermissionDenied(PermissionError):
    """中文：在调用 append_event 前观察到的存储拒绝。

    English: A storage denial observed before append_event was called.
    """


class _EnqueueAfterAppendError(RuntimeError):
    def __init__(self, stored: Mapping[str, Any], cause: Exception):
        super().__init__("ENQUEUE_FAILED_AFTER_APPEND")
        self.stored = dict(stored)
        self.cause = cause


def _validate_session_end_event(event: Mapping[str, Any], *, bootstrap: bool = False) -> Dict[str, Any]:
    """中文：在每个队列入口校验终态事件及其稳定生命周期身份。

    English: Validate the terminal event and its stable lifecycle identity at every queue entry point.
    """
    validated = make_event(event)
    if validated["event_type"] != "SESSION_ENDED":
        raise SealQueueError("BOOTSTRAP_EVENT_TYPE_INVALID" if bootstrap else "JOB_EVENT_TYPE_INVALID")
    if not any(validated[key] for key in ("session_id", "turn_id", "task_id")):
        raise SealQueueError("SESSION_END_IDENTITY_UNAVAILABLE")
    return validated


def _codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME", "").strip()
    if os.name == "nt" and re.match(r"^/mnt/[A-Za-z](?:/|$)", raw):
        raw = raw[5].upper() + ":\\" + raw[7:].replace("/", "\\")
    return Path(raw).expanduser() if raw else Path.home() / ".codex"


def _paths_overlap(left: Path, right: Path) -> bool:
    left = Path(os.path.abspath(os.fspath(left)))
    right = Path(os.path.abspath(os.fspath(right)))
    return _lexical_relative(left, right) is not None or _lexical_relative(right, left) is not None


def _managed_roots() -> Dict[str, Path]:
    configured = os.environ.get("CP_ASSISTANT_DATA", "").strip()
    primary = Path(configured).expanduser() if configured else _codex_home() / "project-context"
    temporary = Path(os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir())
    roots = {
        "primary": primary,
        "temporary-v7": temporary / TEMPORARY_V7_NAME / "project-context",
        # 中文：保留 V6 仅为恢复既有队列；新的 fallback 永不以它为目标。
        # English: V6 is retained only so existing queues can recover. New fallback never targets it.
        "temporary-v6": temporary / TEMPORARY_V6_NAME / "project-context",
    }
    normalized = {name: Path(os.path.abspath(os.fspath(root))) for name, root in roots.items()}
    names = tuple(normalized)
    if any(_paths_overlap(normalized[left], normalized[right])
           for index, left in enumerate(names) for right in names[index + 1:]):
        raise SealQueueError("RECOVERY_ROOT_ROLE_COLLISION")
    return normalized


def _root_reference(root: Path) -> str:
    value = os.path.normcase(os.path.abspath(os.fspath(root)))
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _root_kind(root: Path) -> str:
    roots = _managed_roots()
    normalized = Path(os.path.abspath(os.fspath(root)))
    for name, candidate in roots.items():
        if normalized == candidate:
            return name
    raise SealQueueError("QUEUE_ROOT_UNMANAGED")


def _root_for_queue(queue: Path) -> Path:
    queue = Path(os.path.abspath(os.fspath(queue)))
    matches = [root for root in _managed_roots().values() if _lexical_relative(queue, root) is not None]
    if len(matches) != 1:
        raise SealQueueError("QUEUE_ROOT_UNMANAGED")
    return matches[0]


def _queue_for_root(root: Path, project_id: str) -> Path:
    return root / project_id / "feedback" / "seal-queue-v3"


def _recovery_paths(root: Path, project_id: str) -> tuple[Path, Path, Path]:
    feedback = root / project_id / "feedback"
    return feedback / RECOVERY_ROUTE_NAME, feedback / RECOVERY_RECEIPT_DIRECTORY, feedback / RECOVERY_GUARD_NAME


def _identity_reference(event: Mapping[str, Any]) -> str:
    identity = {key: str(event.get(key) or "") for key in (
        "event_type", "session_id", "turn_id", "task_id", "project_id", "repo_fingerprint",
    )}
    return "sha256:" + hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()


def _receipt_path(root: Path, event: Mapping[str, Any]) -> Path:
    _route, directory, _guard = _recovery_paths(root, str(event["project_id"]))
    return directory / ("receipt-" + _identity_reference(event).removeprefix("sha256:") + ".json")


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _lexical_relative(path: Path, root: Path) -> Optional[Path]:
    candidate = Path(os.path.abspath(os.fspath(path)))
    base = Path(os.path.abspath(os.fspath(root)))
    try:
        return candidate.relative_to(base)
    except ValueError:
        return None


def _validate_managed_path(root: Path, target: Path, *, reparse_code: str = "RECOVERY_PATH_UNSAFE") -> Path:
    """中文：在读写前拒绝每个受管祖先中的链接或重解析点。

    English: Reject a link/reparse point at every managed ancestor before it is read or written.
    """
    root = Path(os.path.abspath(os.fspath(root)))
    target = Path(os.path.abspath(os.fspath(target)))
    relative = _lexical_relative(target, root)
    if relative is None:
        raise SealQueueError("QUEUE_ROOT_UNMANAGED")
    current = root
    for part in ("", *relative.parts):
        if part:
            current = current / part
        if _is_reparse(current):
            raise SealQueueError(reparse_code)
    if not _inside(target, root):
        raise SealQueueError("QUEUE_ROOT_UNMANAGED")
    return target


def _bounded_directory_count(directory: Path) -> int:
    try:
        if not native_path(directory).exists():
            return 0
        records = list(native_path(directory).glob("receipt-*.json"))
    except OSError as exc:
        raise SealQueueError("RECOVERY_RECEIPT_UNREADABLE") from exc
    for record in records:
        if not re.fullmatch(r"receipt-[0-9a-f]{64}\.json", record.name) or _is_reparse(record):
            raise SealQueueError("RECOVERY_RECEIPT_UNSAFE")
    return len(records)


def _validate_queue(queue: Path, project_id: str) -> Path:
    queue = Path(queue)
    if queue.name != "seal-queue-v3" or queue.parent.name != "feedback" or queue.parent.parent.name != project_id:
        raise SealQueueError("QUEUE_PATH_INVALID")
    root = _root_for_queue(queue)
    queue = _validate_managed_path(root, queue, reparse_code="QUEUE_REPARSE_REJECTED")
    return _validate_managed_path(root, queue.parent / "task-outcome-v3.jsonl",
                                  reparse_code="EVENT_REPARSE_REJECTED")


def _read_route(event: Mapping[str, Any]) -> Optional[Path]:
    """中文：读取 v7 fallback pin，不把不可读 primary 当作不存在。

    English: Read the v7 fallback pin without treating an unreadable primary as absent.
    """
    fallback_root = _managed_roots()["temporary-v7"]
    route_path, _receipt_directory, _guard_path = _recovery_paths(fallback_root, str(event["project_id"]))
    try:
        _validate_managed_path(fallback_root, route_path)
        if not native_path(route_path).exists():
            return None
        value = _load_json(route_path, "RECOVERY_ROUTE_INVALID")
    except PermissionError as exc:
        raise SealQueueError("RECOVERY_ROUTE_UNREADABLE") from exc
    if value.get("schema_version") != RECOVERY_SCHEMA:
        raise SealQueueError("RECOVERY_ROUTE_INVALID")
    if value.get("project_id") != event["project_id"] or value.get("repo_fingerprint") != event["repo_fingerprint"]:
        raise SealQueueError("RECOVERY_ROUTE_IDENTITY_INVALID")
    if value.get("root_kind") != "temporary-v7" or value.get("root_ref") != _root_reference(fallback_root):
        raise SealQueueError("RECOVERY_ROUTE_INVALID")
    return _queue_for_root(fallback_root, str(event["project_id"]))


def _load_json(path: Path, error_code: str) -> Dict[str, Any]:
    try:
        value = json.loads(
            bounded_read(native_path(path), RECOVERY_RECORD_MAX_BYTES),
            object_pairs_hook=unique_json_object,
        )
    except (CapabilityError, OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise SealQueueError(error_code) from exc
    if not isinstance(value, dict):
        raise SealQueueError(error_code)
    return value


def _receipt_mac(payload: Mapping[str, Any], secret: bytes) -> str:
    return hmac.new(secret, canonical_json(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def _write_recovery_receipt(root: Path, event: Mapping[str, Any], *, original_root: Path,
                            stage: str, error_category: str, status: str,
                            record: Optional[Mapping[str, Any]] = None,
                            keyring_path: Optional[Path] = None) -> bool:
    """中文：仅持久化有界诊断；它绝不携带事件内容或异常文本。

    English: Persist only a bounded diagnostic; it never carries event content or exception text.
    """
    try:
        _kind = _root_kind(root)
        _route_path, receipt_directory, _guard_path = _recovery_paths(root, str(event["project_id"]))
        receipt_path = _receipt_path(root, event)
        _validate_managed_path(root, receipt_directory)
        _validate_managed_path(root, receipt_path)
        if not native_path(receipt_path).exists() and _bounded_directory_count(receipt_directory) >= MAX_RECOVERY_RECEIPTS:
            return False
        stored_hash = str((record or {}).get("record_hash") or "")
        payload: Dict[str, Any] = {
            "schema_version": RECOVERY_RECEIPT_SCHEMA,
            "identity_ref": _identity_reference(event),
            "project_id": event["project_id"],
            "repo_fingerprint": event["repo_fingerprint"],
            "original_root_ref": _root_reference(original_root),
            "stage": stage,
            "error_category": error_category,
            "recovery_status": status,
            "record_hash": stored_hash,
            "recovery_eligibility": "DIAGNOSTIC_ONLY",
            "key_id": "",
            "receipt_hmac_sha256": "",
        }
        if stored_hash and (stage == "ENQUEUE_FAILED_AFTER_APPEND" or status in {"PENDING_SEAL", "SEALED_CURRENT"}):
            try:
                _ring, secret, key_id = active_secret("event-hmac", keyring_path)
                payload.update(recovery_eligibility="AUTHENTICATED", key_id=key_id)
                payload["receipt_hmac_sha256"] = _receipt_mac(
                    {key: value for key, value in payload.items() if key != "receipt_hmac_sha256"}, secret
                )
            except Exception:
                payload.update(recovery_status="TRUSTED_BOOTSTRAP_REQUIRED",
                               error_category="KEYRING_UNAVAILABLE")
        _atomic_json(receipt_path, payload)
        return True
    except (OSError, PermissionError, SealQueueError):
        return False


def _receipt_exists(root: Path, event: Mapping[str, Any]) -> bool:
    try:
        path = _receipt_path(root, event)
        _validate_managed_path(root, path)
        return native_path(path).exists()
    except (OSError, SealQueueError):
        return False


def _pin_fallback_root(root: Path, event: Mapping[str, Any], original_root: Path) -> None:
    route_path = _recovery_paths(root, str(event["project_id"]))[0]
    _validate_managed_path(root, route_path)
    _atomic_json(route_path, {
        "schema_version": RECOVERY_SCHEMA,
        "project_id": event["project_id"],
        "repo_fingerprint": event["repo_fingerprint"],
        "root_kind": "temporary-v7",
        "root_ref": _root_reference(root),
        "original_root_ref": _root_reference(original_root),
        "identity_ref": _identity_reference(event),
    })


def _preappend_boundary(event_path: Path) -> None:
    """中文：在考虑权限 fallback 前证明尚未开始追加。

    English: Prove no append has started before a permission fallback is considered.
    """
    root = _root_for_queue(event_path.parent / "seal-queue-v3")
    event_path = _validate_managed_path(root, event_path)
    parent = native_path(event_path).parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise _PreAppendPermissionDenied() from exc
    try:
        native_path(event_path).stat()
    except FileNotFoundError:
        return
    # 中文：追加前既有链必须可读且有效；任何不确定性都留在该根目录。
    # English: An existing chain must be readable and valid before append. Any uncertainty stays on this root.
    try:
        verify_event_chain(event_path)
    except PermissionError as exc:
        raise SealQueueError("PRE_APPEND_HISTORY_UNREADABLE") from exc
    except Exception as exc:
        raise SealQueueError("PRE_APPEND_CHAIN_INVALID") from exc


def _prepare_at_queue(queue: Path, event: Mapping[str, Any], keyring_path: Optional[Path],
                      lock_timeout: float) -> Dict[str, Any]:
    validated = _validate_session_end_event(event)
    event_path = _validate_queue(Path(queue), validated["project_id"])
    _preappend_boundary(event_path)
    try:
        stored = append_event(
            event_path,
            validated,
            deduplicate_event_id=True,
            deduplicate_identity_fields=(
                "event_type", "session_id", "turn_id", "task_id", "project_id", "repo_fingerprint",
            ),
            lock_timeout=lock_timeout,
        )
    except Exception:
        # 中文：该边界刻意位于追加尝试之后；绝不将其重放到其他根目录。
        # English: This boundary is intentionally after the append attempt. Never replay it to another root.
        raise
    try:
        queued = enqueue_session_end(queue, stored, keyring_path)
    except Exception as exc:
        root = _root_for_queue(Path(queue))
        _write_recovery_receipt(root, stored, original_root=root,
                                stage="ENQUEUE_FAILED_AFTER_APPEND", error_category="WORKER_OPERATION_FAILED",
                                status="ORIGINAL_CHAIN_RECOVERY_REQUIRED", record=stored,
                                keyring_path=keyring_path)
        raise _EnqueueAfterAppendError(stored, exc) from exc
    return {**queued, "queue": str(queue), "_stored_event": stored}


def _prepared_result(result: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    public = dict(result)
    stored = public.pop("_stored_event")
    return public, stored


def resolve_event_path(event: Mapping[str, Any], preferred_queue: Optional[Path] = None) -> Path:
    """中文：为后续生命周期事件返回项目钉定的根，不合并历史。

    English: Return the project-pinned root for later lifecycle events without merging histories.
    """
    validated = make_event(event)
    original_root = _managed_roots()["primary"]
    if preferred_queue is not None:
        preferred_root = _root_for_queue(Path(preferred_queue))
        if _root_kind(preferred_root) != "primary":
            return _validate_queue(Path(preferred_queue), validated["project_id"])
        original_root = preferred_root
    try:
        selected = _read_route(validated)
    except Exception:
        _write_recovery_receipt(original_root, validated, original_root=original_root,
                                stage="ROUTE_SELECTION", error_category="UNSAFE_OR_NONPERMISSION",
                                status="ORIGINAL_CHAIN_RECOVERY_REQUIRED")
        raise
    queue = selected or _queue_for_root(_managed_roots()["primary"], validated["project_id"])
    return _validate_queue(queue, validated["project_id"])


def _selection_guard(root: Path, event: Mapping[str, Any], timeout: float) -> OwnerTokenLock:
    guard = _recovery_paths(root, str(event["project_id"]))[2]
    _validate_managed_path(root, guard)
    return OwnerTokenLock(guard, timeout=timeout)


def append_lifecycle_event(event: Mapping[str, Any], hmac_key: Optional[str] = None,
                           lock_timeout: float = 2.0) -> Dict[str, Any]:
    """中文：在与 SessionEnd 相同的根选择锁下追加非终态生命周期数据。

    English: Append non-terminal lifecycle data under the same root-selection lock as SessionEnd.
    """
    validated = make_event(event)
    roots = _managed_roots()
    primary_root, fallback_root = roots["primary"], roots["temporary-v7"]
    try:
        with _selection_guard(fallback_root, validated, lock_timeout):
            selected = _read_route(validated)
            queue = selected or _queue_for_root(primary_root, validated["project_id"])
            return append_event(_validate_queue(queue, validated["project_id"]), validated, hmac_key,
                                lock_timeout=lock_timeout)
    except Exception:
        _write_recovery_receipt(primary_root, validated, original_root=primary_root,
                                stage="LIFECYCLE_ROOT_SELECTION", error_category="ROOT_AMBIGUITY",
                                status="ORIGINAL_CHAIN_RECOVERY_REQUIRED")
        raise


def prepare_session_end_with_recovery(queue: Path, event: Mapping[str, Any],
                                      keyring_path: Optional[Path] = None,
                                      lock_timeout: float = 10.0) -> Dict[str, Any]:
    """中文：准备 bootstrap 事件，仅在证明追加前权限拒绝后使用 v7。

    English: Prepare a bootstrap event, using v7 only after a proven pre-append permission denial.
    """
    validated = _validate_session_end_event(event)
    initial_queue = Path(queue)
    original_root = _root_for_queue(initial_queue)
    original_kind = _root_kind(original_root)
    if original_kind != "primary":
        result, _stored = _prepared_result(_prepare_at_queue(initial_queue, validated, keyring_path, lock_timeout))
        return result
    fallback_root = _managed_roots()["temporary-v7"]
    selection_acquired = False
    try:
        with _selection_guard(fallback_root, validated, lock_timeout):
            selection_acquired = True
            try:
                selected = _read_route(validated)
            except Exception:
                _write_recovery_receipt(original_root, validated, original_root=original_root,
                                        stage="ROUTE_SELECTION", error_category="UNSAFE_OR_NONPERMISSION",
                                        status="ORIGINAL_CHAIN_RECOVERY_REQUIRED")
                raise
            if selected is not None:
                try:
                    result, _stored = _prepared_result(_prepare_at_queue(selected, validated, keyring_path, lock_timeout))
                    return result
                except _EnqueueAfterAppendError as exc:
                    raise exc.cause
                except Exception:
                    _write_recovery_receipt(fallback_root, validated, original_root=original_root,
                                            stage="FALLBACK_APPEND_OR_LATER", error_category="WORKER_OPERATION_FAILED",
                                            status="PINNED_CHAIN_RECOVERY_REQUIRED")
                    raise
            try:
                result, _stored = _prepared_result(_prepare_at_queue(initial_queue, validated, keyring_path, lock_timeout))
                return result
            except _PreAppendPermissionDenied:
                # 中文：只有该分支能积极证明未发生 append_event 调用。
                # English: Only this branch has positive proof that no append_event call occurred.
                fallback_queue = _queue_for_root(fallback_root, validated["project_id"])
                _pin_fallback_root(fallback_root, validated, original_root)
                try:
                    result, stored = _prepared_result(_prepare_at_queue(fallback_queue, validated, keyring_path, lock_timeout))
                except _PreAppendPermissionDenied:
                    _write_recovery_receipt(fallback_root, validated, original_root=original_root,
                                            stage="FALLBACK_PRE_APPEND_STORAGE", error_category="PERMISSION_DENIED",
                                            status="FALLBACK_UNAVAILABLE")
                    raise SealQueueError("SESSION_END_FALLBACK_UNAVAILABLE")
                except Exception:
                    _write_recovery_receipt(fallback_root, validated, original_root=original_root,
                                            stage="FALLBACK_APPEND_OR_LATER", error_category="WORKER_OPERATION_FAILED",
                                            status="PINNED_CHAIN_RECOVERY_REQUIRED")
                    raise
                _write_recovery_receipt(fallback_root, validated, original_root=original_root,
                                        stage="PRE_APPEND_STORAGE", error_category="PERMISSION_DENIED",
                                        status="PENDING_SEAL", record=stored, keyring_path=keyring_path)
                return result
            except _EnqueueAfterAppendError as exc:
                raise exc.cause
            except Exception:
                _write_recovery_receipt(original_root, validated, original_root=original_root,
                                        stage="APPEND_OR_LATER", error_category="UNSAFE_OR_NONPERMISSION",
                                        status="ORIGINAL_CHAIN_RECOVERY_REQUIRED")
                raise
    except Exception:
        if not selection_acquired:
            _write_recovery_receipt(original_root, validated, original_root=original_root,
                                    stage="ROOT_SELECTION", error_category="ROOT_AMBIGUITY",
                                    status="ORIGINAL_CHAIN_RECOVERY_REQUIRED")
        raise


def recover_pending_session_end(queue: Path, keyring_path: Optional[Path] = None) -> Dict[str, int]:
    """中文：重新入队由持久无正文回执指定的原链 SessionEnd 记录。

    English: Re-enqueue original-chain SessionEnd records named by durable body-free receipts.
    """
    queue = Path(queue)
    root = _root_for_queue(queue)
    project_id = queue.parent.parent.name
    event_path = _validate_queue(queue, project_id)
    _route_path, receipt_directory, _guard = _recovery_paths(root, project_id)
    _validate_managed_path(root, receipt_directory)
    if not native_path(receipt_directory).exists():
        return {"receipts": 0, "enqueued": 0, "already_present": 0}
    count = _bounded_directory_count(receipt_directory)
    if count > MAX_RECOVERY_RECEIPTS:
        raise SealQueueError("RECOVERY_RECEIPT_CAPACITY_EXCEEDED")
    receipt_paths = sorted(Path(receipt_directory).glob("receipt-*.json"))
    receipts = []
    for path in receipt_paths:
        _validate_managed_path(root, path)
        receipts.append((path, _load_json(path, "RECOVERY_RECEIPT_INVALID")))
    chain = read_event_chain(event_path)
    by_identity = {
        _identity_reference(item): item for item in chain["events"]
        if item.get("event_type") == "SESSION_ENDED"
    }
    enqueued = already_present = 0
    for path, receipt in receipts:
        expected_fields = {
            "schema_version", "identity_ref", "project_id", "repo_fingerprint", "original_root_ref",
            "stage", "error_category", "recovery_status", "record_hash", "recovery_eligibility",
            "key_id", "receipt_hmac_sha256",
        }
        if set(receipt) != expected_fields or receipt.get("schema_version") != RECOVERY_RECEIPT_SCHEMA:
            raise SealQueueError("RECOVERY_RECEIPT_INVALID")
        identity_ref = str(receipt.get("identity_ref") or "")
        if path.name != "receipt-" + identity_ref.removeprefix("sha256:") + ".json":
            raise SealQueueError("RECOVERY_RECEIPT_FILENAME_INVALID")
        if receipt.get("project_id") != project_id or receipt.get("original_root_ref") != _root_reference(root):
            raise SealQueueError("RECOVERY_RECEIPT_IDENTITY_INVALID")
        if receipt.get("recovery_eligibility") == "DIAGNOSTIC_ONLY":
            continue
        if receipt.get("recovery_eligibility") != "AUTHENTICATED":
            raise SealQueueError("RECOVERY_RECEIPT_UNAUTHENTICATED")
        if receipt.get("stage") != "ENQUEUE_FAILED_AFTER_APPEND" or receipt.get("recovery_status") != "ORIGINAL_CHAIN_RECOVERY_REQUIRED":
            raise SealQueueError("RECOVERY_RECEIPT_STATE_INVALID")
        key_id = str(receipt.get("key_id") or "")
        unsigned = {key: value for key, value in receipt.items() if key != "receipt_hmac_sha256"}
        try:
            _ring, secret = secret_by_id("event-hmac", key_id, keyring_path)
        except Exception as exc:
            raise SealQueueError("RECOVERY_RECEIPT_UNAUTHENTICATED") from exc
        if not hmac.compare_digest(str(receipt.get("receipt_hmac_sha256") or ""), _receipt_mac(unsigned, secret)):
            raise SealQueueError("RECOVERY_RECEIPT_HMAC_INVALID")
        event = by_identity.get(identity_ref)
        if event is None:
            raise SealQueueError("RECOVERY_EVENT_NOT_FOUND")
        if event.get("project_id") != project_id or event.get("repo_fingerprint") != receipt.get("repo_fingerprint"):
            raise SealQueueError("RECOVERY_EVENT_IDENTITY_INVALID")
        if _identity_reference(event) != identity_ref or event.get("record_hash") != receipt.get("record_hash"):
            raise SealQueueError("RECOVERY_EVENT_RECORD_INVALID")
        queued = enqueue_session_end(queue, event, keyring_path)
        if queued["enqueued"]:
            enqueued += 1
        else:
            already_present += 1
        _write_recovery_receipt(root, event, original_root=root,
                                stage="RECOVERY_ENQUEUED", error_category="NONE",
                                status="PENDING_SEAL", record=event, keyring_path=keyring_path)
    return {"receipts": count, "enqueued": enqueued, "already_present": already_present}


def _sign(job: Dict[str, Any], key: bytes, key_id: str) -> Dict[str, Any]:
    signed = dict(job)
    signed["key_id"] = key_id
    signed.pop("job_hmac_sha256", None)
    signed["job_hmac_sha256"] = hmac.new(key, canonical_json(signed).encode("utf-8"), hashlib.sha256).hexdigest()
    return signed


def _job_digest(event: Mapping[str, Any], identity_version: int) -> str:
    keys = ("event_type", "session_id", "turn_id", "task_id", "project_id", "repo_fingerprint")
    identity = {key: event[key] for key in keys}
    if identity_version == 2:
        identity = {"identity_version": 2, "event_id": event["event_id"], **identity}
    elif identity_version != 1:
        raise SealQueueError("JOB_IDENTITY_VERSION_INVALID")
    return hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()


def _verify(job: Mapping[str, Any], keyring_path: Optional[Path]) -> Dict[str, Any]:
    if job.get("schema_version") != JOB_SCHEMA or str(job.get("state")) not in JOB_STATES:
        raise SealQueueError("JOB_SCHEMA_INVALID")
    identity_version = int(job.get("identity_version", 1))
    try:
        event = make_event(job.get("event") or {})
        digest = _job_digest(event, identity_version)
    except (TypeError, ValueError) as exc:
        raise SealQueueError("JOB_IDENTITY_INVALID") from exc
    if job.get("job_id") != digest or job.get("idempotency_key") != digest:
        raise SealQueueError("JOB_IDENTITY_INVALID")
    key_id = str(job.get("key_id") or "")
    _ring, secret = secret_by_id("event-hmac", key_id, keyring_path)
    unsigned = {key: value for key, value in job.items() if key != "job_hmac_sha256"}
    expected = hmac.new(secret, canonical_json(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(job.get("job_hmac_sha256") or ""), expected):
        raise SealQueueError("JOB_HMAC_INVALID")
    return dict(job)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    native = native_path(path)
    native.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(native.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush(); os.fsync(handle.fileno())
        replace_with_retry(temporary, native)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _load(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(native_path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SealQueueError("JOB_READ_INVALID") from exc
    if not isinstance(value, dict):
        raise SealQueueError("JOB_SCHEMA_INVALID")
    return value


def _job_file(queue: Path, state: str, job_name: str) -> Path:
    if state not in JOB_STATES or not JOB_NAME.fullmatch(job_name):
        raise SealQueueError("JOB_NAME_INVALID")
    return native_path(queue / state / job_name)


def _job_paths(queue: Path, state: str) -> list[Path]:
    if state not in JOB_STATES:
        raise SealQueueError("JOB_STATE_INVALID")
    return [item for item in native_path(queue / state).glob("job-*.json") if JOB_NAME.fullmatch(item.name)]


def enqueue_session_end(queue: Path, event: Mapping[str, Any], keyring_path: Optional[Path] = None) -> Dict[str, Any]:
    validated = _validate_session_end_event(event)
    event_path = _validate_queue(Path(queue), validated["project_id"])
    digest = _job_digest(validated, JOB_IDENTITY_VERSION)
    job_name = "job-" + digest + ".json"
    queue = Path(queue)
    native_path(queue).mkdir(parents=True, exist_ok=True)
    for state in JOB_STATES:
        native_path(queue / state).mkdir(exist_ok=True)
    with OwnerTokenLock(queue / "queue-state", timeout=0.35):
        existing = next((state for state in JOB_STATES if _job_file(queue, state, job_name).exists()), None)
        if existing:
            return {"ok": True, "enqueued": False, "state": existing, "job_ref": "sha256:" + digest}
        maximum = int(os.environ.get("CP_ASSISTANT_SEAL_QUEUE_MAX_JOBS", "10000"))
        count = sum(len(_job_paths(queue, state)) for state in JOB_STATES)
        if count >= maximum:
            raise SealQueueError("QUEUE_CAPACITY_EXCEEDED")
        _ring, secret, key_id = active_secret("event-hmac", keyring_path)
        job = {
            "schema_version": JOB_SCHEMA, "identity_version": JOB_IDENTITY_VERSION,
            "job_id": digest, "idempotency_key": digest,
            "state": "pending", "attempt": 0, "lease_epoch": 0, "lease_pid": 0,
            "lease_process_identity": "",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "project_id": validated["project_id"], "repo_fingerprint": validated["repo_fingerprint"],
            "event_file": event_path.name, "event": validated, "error_code": "NONE",
        }
        _atomic_json(_job_file(queue, "pending", job_name), _sign(job, secret, key_id))
    return {"ok": True, "enqueued": True, "state": "pending", "job_ref": "sha256:" + digest}


def prepare_session_end(queue: Path, event: Mapping[str, Any], keyring_path: Optional[Path] = None,
                        lock_timeout: float = 10.0) -> Dict[str, Any]:
    """中文：在 Hook 外原子复核/补写终态，再创建 v2 签名任务。

    English: Atomically recheck/backfill the terminal event outside the Hook, then create a v2 signed job.
    """
    validated = _validate_session_end_event(event)
    event_path = _validate_queue(Path(queue), validated["project_id"])
    stored = append_event(
        event_path,
        validated,
        deduplicate_event_id=True,
        deduplicate_identity_fields=(
            "event_type", "session_id", "turn_id", "task_id", "project_id", "repo_fingerprint",
        ),
        lock_timeout=lock_timeout,
    )
    return enqueue_session_end(queue, stored, keyring_path)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        ctypes = __import__("ctypes")
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            exit_code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            # 中文：Windows 状态码 259 表示进程仍在运行。
            # English: Windows status code 259 means the process is still active.
            return bool(ok and exit_code.value == 259)
        return False
    try:
        os.kill(pid, 0); return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _process_identity(pid: int) -> str:
    """中文：在可观察时返回抵抗 PID 复用的进程启动身份。

    English: Return a PID-reuse-resistant process-start identity when observable.
    """
    if pid <= 0:
        return ""
    if os.name == "nt":
        ctypes = __import__("ctypes")
        from ctypes import wintypes

        class FileTime(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return ""
        created, exited, kernel, user = FileTime(), FileTime(), FileTime(), FileTime()
        try:
            ok = ctypes.windll.kernel32.GetProcessTimes(
                handle, ctypes.byref(created), ctypes.byref(exited),
                ctypes.byref(kernel), ctypes.byref(user))
            if not ok:
                return ""
            value = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
            return "windows-filetime:%d" % value
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        fields = (Path("/proc") / str(pid) / "stat").read_text(encoding="ascii").split()
        return "proc-start:%s" % fields[21] if len(fields) > 21 else ""
    except (OSError, UnicodeError):
        return ""


def _resign(job: Dict[str, Any], keyring_path: Optional[Path]) -> Dict[str, Any]:
    _ring, secret, key_id = active_secret("event-hmac", keyring_path)
    return _sign(job, secret, key_id)


def _recover_running(queue: Path, keyring_path: Optional[Path]) -> None:
    for path in sorted(_job_paths(queue, "running")):
        if not JOB_NAME.fullmatch(path.name):
            continue
        try:
            job = _verify(_load(path), keyring_path)
            pid = int(job.get("lease_pid") or 0)
            expected_identity = str(job.get("lease_process_identity") or "")
            if expected_identity and _pid_alive(pid) and _process_identity(pid) == expected_identity:
                continue
            job.update(state="pending", lease_pid=0, lease_process_identity="",
                       error_code="RECOVERED_AFTER_WORKER_EXIT")
            _atomic_json(path, _resign(job, keyring_path))
            replace_with_retry(path, _job_file(queue, "pending", path.name))
        except Exception:
            replace_with_retry(path, _job_file(queue, "dead-letter", path.name))


def _crash(point: str) -> None:
    if os.environ.get("CP_ASSISTANT_TEST_SEAL_WORKER_HARD_CRASH_POINT") == point:
        os._exit(94)


def process_queue(queue: Path, keyring_path: Optional[Path] = None, max_jobs: int = 100) -> Dict[str, Any]:
    queue = Path(queue)
    project_id = queue.parent.parent.name
    event_path = _validate_queue(queue, project_id)
    queue_root = _root_for_queue(queue)
    processed = completed = retried = dead = 0
    for _ in range(max_jobs):
        with OwnerTokenLock(queue / "queue-state", timeout=2.0):
            _recover_running(queue, keyring_path)
            pending = next(iter(sorted(_job_paths(queue, "pending"))), None)
            if pending is None:
                break
            if not JOB_NAME.fullmatch(pending.name):
                raise SealQueueError("JOB_NAME_INVALID")
            try:
                job = _verify(_load(pending), keyring_path)
            except Exception:
                replace_with_retry(pending, _job_file(queue, "dead-letter", pending.name))
                dead += 1
                continue
            if job.get("project_id") != project_id or job.get("event_file") != event_path.name:
                replace_with_retry(pending, _job_file(queue, "dead-letter", pending.name)); dead += 1; continue
            job["state"] = "running"; job["attempt"] = int(job.get("attempt") or 0) + 1
            job["lease_epoch"] = int(job.get("lease_epoch") or 0) + 1; job["lease_pid"] = os.getpid()
            job["lease_process_identity"] = _process_identity(os.getpid())
            if not job["lease_process_identity"]:
                raise SealQueueError("WORKER_PROCESS_IDENTITY_UNAVAILABLE")
            _atomic_json(pending, _resign(job, keyring_path))
            running = _job_file(queue, "running", pending.name)
            replace_with_retry(pending, running)
        _crash("AFTER_CLAIM")
        processed += 1
        try:
            if job["event"].get("project_id") != job["project_id"] or job["event"].get("repo_fingerprint") != job["repo_fingerprint"]:
                raise SealQueueError("JOB_PROJECT_BINDING_MISMATCH")
            _crash("BEFORE_APPEND")
            append_event(event_path, job["event"], deduplicate_event_id=True)
            _crash("AFTER_APPEND")
            seal = seal_event_chain(event_path, keyring_path=keyring_path)
            _crash("AFTER_SEAL")
            with OwnerTokenLock(queue / "queue-state", timeout=2.0):
                current = _verify(_load(running), keyring_path)
                if int(current.get("lease_epoch") or 0) != job["lease_epoch"]:
                    raise SealQueueError("JOB_LEASE_MISMATCH")
                current.update(state="done", lease_pid=0, lease_process_identity="", error_code="NONE",
                               completion={"seal_status": seal["seal_status"],
                                           "sealed_record_count": seal["sealed_record_count"]})
                _atomic_json(running, _resign(current, keyring_path)); _crash("BEFORE_ACK")
                replace_with_retry(running, _job_file(queue, "done", running.name))
            if _receipt_exists(queue_root, job["event"]):
                _write_recovery_receipt(queue_root, job["event"], original_root=queue_root,
                                        stage="SEALED", error_category="NONE", status="SEALED_CURRENT",
                                        record=job["event"], keyring_path=keyring_path)
            completed += 1
        except Exception as exc:
            _write_recovery_receipt(queue_root, job["event"], original_root=queue_root,
                                    stage="QUEUED_APPEND_OR_SEAL",
                                    error_category="WORKER_OPERATION_FAILED",
                                    status="PENDING_SEAL", record=job["event"], keyring_path=keyring_path)
            code = str(exc) if isinstance(exc, SealQueueError) and re.fullmatch(r"[A-Z0-9_]+", str(exc)) else "WORKER_OPERATION_FAILED"
            with OwnerTokenLock(queue / "queue-state", timeout=2.0):
                if not running.exists():
                    continue
                current = _load(running)
                current.update(state="dead-letter" if int(current.get("attempt") or 0) >= 3 else "pending",
                               lease_pid=0, lease_process_identity="", error_code=code)
                _atomic_json(running, _resign(current, keyring_path))
                target_state = str(current["state"])
                replace_with_retry(running, _job_file(queue, target_state, running.name))
                if target_state == "dead-letter": dead += 1
                else: retried += 1
    return {"ok": dead == 0, "processed": processed, "completed": completed,
            "retried": retried, "dead_letter": dead}


def launch_worker(plugin_root: Path, queue: Path, keyring_path: Optional[Path] = None,
                  bootstrap_event: Optional[Mapping[str, Any]] = None, *,
                  worker_script: Optional[Path] = None) -> Dict[str, Any]:
    # 中文：账户 Hook 与封印入口同目录；默认路径保留源码和 Plugin 调用兼容。
    # English: Account Hooks use their sibling entry point; retain the source/Plugin default.
    script = Path(worker_script) if worker_script is not None else Path(plugin_root) / "hooks" / "seal_worker.py"
    command = [sys.executable, "-B", str(script), "--queue", str(queue), "--max-jobs", "100"]
    if keyring_path is not None:
        command.extend(["--keyring", str(keyring_path)])
    if bootstrap_event is not None:
        validated = _validate_session_end_event(bootstrap_event, bootstrap=True)
        payload = canonical_json(validated).encode("utf-8")
        if len(payload) > BOOTSTRAP_EVENT_MAX_BYTES:
            raise SealQueueError("BOOTSTRAP_EVENT_TOO_LARGE")
        encoded = base64.urlsafe_b64encode(payload).decode("ascii")
        command.extend(["--bootstrap-event-b64", encoded])
    kwargs: Dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                              "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                                   | getattr(subprocess, "DETACHED_PROCESS", 0)
                                   | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        kwargs["start_new_session"] = True
    if not script.is_file():
        raise SealQueueError("SEAL_WORKER_ENTRYPOINT_MISSING")
    process = subprocess.Popen(command, **kwargs)
    wait_ms = int(os.environ.get("CP_ASSISTANT_TEST_SEAL_WORKER_WAIT_MS", "0") or "0")
    if wait_ms > 0:
        try:
            exit_code = process.wait(timeout=min(wait_ms, 2500) / 1000.0)
        except subprocess.TimeoutExpired:
            return {"launched": True, "worker_pid": process.pid, "test_wait_status": "TIMEOUT"}
        return {"launched": True, "worker_pid": process.pid, "test_wait_status": "EXITED",
                "worker_exit_code": exit_code}
    return {"launched": True, "worker_pid": process.pid, "test_wait_status": "NOT_REQUESTED"}
