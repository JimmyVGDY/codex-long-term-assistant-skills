"""中文：非破坏事件归档、容量预算与隐私安全健康概览。

English: Non-destructive event archives, capacity budgets, and privacy-safe health summaries.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from .event_v2 import (OwnerTokenLock, _read_event_files_unlocked, _verify_events,
                       canonical_json, event_segment_paths, read_event_chain)
from .integrity import IntegrityError, verify_event_seals

ARCHIVE_SCHEMA = "1.0"
ZERO_HASH = "0" * 64


class EventArchiveError(RuntimeError):
    pass


def _archive_root_for_event(event_path: Path) -> Path:
    """中文：返回单条物理事件链的版本隔离归档目录。

    English: Return the version-isolated archive root for one physical event chain.
    """
    event_path = Path(event_path)
    name = "events-v3" if "task-outcome-v3" in event_path.name else "events"
    return event_path.parent / "archive" / name


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_hash(previous: str, unsigned: Mapping[str, Any]) -> str:
    return hashlib.sha256((previous + "\n" + canonical_json(unsigned)).encode("utf-8")).hexdigest()


def _manifests(root: Path) -> list[Path]:
    result = sorted(root.glob("manifest-*.json"))
    expected = ["manifest-%06d.json" % index for index in range(1, len(result) + 1)]
    if [item.name for item in result] != expected:
        raise EventArchiveError("ARCHIVE_MANIFEST_SEQUENCE_INVALID")
    return result


def _load_manifest(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EventArchiveError("ARCHIVE_MANIFEST_INVALID") from exc
    if not isinstance(value, dict):
        raise EventArchiveError("ARCHIVE_MANIFEST_INVALID")
    return value


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
    os.close(fd)
    try:
        shutil.copyfile(source, temporary)
        with open(temporary, "r+b") as handle:
            os.fsync(handle.fileno())
        if target.exists():
            if _sha_file(target) != _sha_file(Path(temporary)):
                raise EventArchiveError("ARCHIVE_COPY_CONFLICT")
        else:
            os.replace(temporary, target)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush(); os.fsync(handle.fileno())
        if path.exists():
            raise EventArchiveError("ARCHIVE_MANIFEST_EXISTS")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def verify_archive(event_path: Path, archive_root: Optional[Path] = None) -> Dict[str, Any]:
    event_path = Path(event_path)
    root = Path(archive_root or _archive_root_for_event(event_path))
    previous = ZERO_HASH
    archived_names: set[str] = set()
    segment_count = record_count = 0
    for manifest_path in _manifests(root) if root.exists() else []:
        manifest = _load_manifest(manifest_path)
        supplied = str(manifest.get("manifest_hash") or "")
        unsigned = {key: value for key, value in manifest.items() if key != "manifest_hash"}
        if manifest.get("schema_version") != ARCHIVE_SCHEMA or manifest.get("previous_manifest_hash") != previous:
            raise EventArchiveError("ARCHIVE_MANIFEST_LINK_INVALID")
        if _manifest_hash(previous, unsigned) != supplied:
            raise EventArchiveError("ARCHIVE_MANIFEST_HASH_INVALID")
        for segment in manifest.get("segments") or []:
            name = str(segment.get("archive_name") or "")
            if not name or name in archived_names:
                raise EventArchiveError("ARCHIVE_SEGMENT_IDENTITY_INVALID")
            archived = root / "segments" / name
            if not archived.is_file() or _sha_file(archived) != segment.get("sha256"):
                raise EventArchiveError("ARCHIVE_SEGMENT_HASH_INVALID")
            archived_names.add(name); segment_count += 1; record_count += int(segment.get("record_count") or 0)
        previous = supplied
    return {"ok": True, "manifest_count": len(_manifests(root)) if root.exists() else 0,
            "segment_count": segment_count, "record_count": record_count,
            "manifest_head": previous}


def archive_closed_segments(event_path: Path, archive_root: Optional[Path] = None) -> Dict[str, Any]:
    event_path = Path(event_path)
    root = Path(archive_root or _archive_root_for_event(event_path))
    with OwnerTokenLock(event_path, timeout=10.0):
        segments = event_segment_paths(event_path)
        _files, events, _tail = _read_event_files_unlocked(event_path)
        _verify_events(events, None, allow_duplicate_ids=True)
        existing = verify_archive(event_path, root)
        already = set()
        for manifest_path in _manifests(root) if root.exists() else []:
            for item in _load_manifest(manifest_path).get("segments") or []:
                already.add(str(item.get("source_name") or ""))
        additions = []
        segment_names = {item.name for item in segments}
        for segment in segments:
            if segment.name in already:
                continue
            target = root / "segments" / segment.name
            _atomic_copy(segment, target)
            additions.append({"source_name": segment.name, "archive_name": segment.name,
                              "sha256": _sha_file(segment), "bytes": segment.stat().st_size,
                              "record_count": sum(1 for event in events
                                                  if event.get("__event_source_file") == segment.name)})
        if not additions:
            return {**existing, "created": False, "archived_now": 0}
        closed_events = [event for event in events if event.get("__event_source_file") in segment_names]
        project_ids = {str(event.get("project_id") or "") for event in closed_events}
        repo_fingerprints = {str(event.get("repo_fingerprint") or "") for event in closed_events}
        if len(project_ids) != 1 or len(repo_fingerprints) != 1:
            raise EventArchiveError("ARCHIVE_PROJECT_BINDING_INVALID")
        number = existing["manifest_count"] + 1
        unsigned = {"schema_version": ARCHIVE_SCHEMA, "manifest_number": number,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    "project_id": next(iter(project_ids)), "repo_fingerprint": next(iter(repo_fingerprints)),
                    "frozen_chain_head": str(closed_events[-1].get("record_hash") or "") if closed_events else ZERO_HASH,
                    "previous_manifest_hash": existing["manifest_head"], "segments": additions}
        manifest = dict(unsigned, manifest_hash=_manifest_hash(existing["manifest_head"], unsigned))
        _atomic_json(root / ("manifest-%06d.json" % number), manifest)
    result = verify_archive(event_path, root)
    return {**result, "created": True, "archived_now": len(additions)}


def capacity_report(project_dir: Path, soft_bytes: Optional[int] = None,
                    hard_bytes: Optional[int] = None) -> Dict[str, Any]:
    root = Path(project_dir)
    soft = int(soft_bytes or os.environ.get("CP_ASSISTANT_CAPACITY_SOFT_BYTES", 256 * 1024 * 1024))
    hard = int(hard_bytes or os.environ.get("CP_ASSISTANT_CAPACITY_HARD_BYTES", 512 * 1024 * 1024))
    if soft <= 0 or hard < soft:
        raise EventArchiveError("CAPACITY_POLICY_INVALID")
    categories = {"events": 0, "seals": 0, "archives": 0, "queue": 0, "other": 0}
    files = 0
    for path in root.rglob("*") if root.exists() else []:
        if not path.is_file():
            continue
        files += 1; size = path.stat().st_size
        normalized = path.as_posix().lower()
        if "seal-queue-v3/" in normalized or "seal-queue/" in normalized: category = "queue"
        elif "/archive/" in normalized: category = "archives"
        elif path.name.endswith(".seals.jsonl"): category = "seals"
        elif "task-outcome-v3" in path.name or "task-outcome-v2" in path.name: category = "events"
        else: category = "other"
        categories[category] += size
    total = sum(categories.values())
    status = "HARD_LIMIT" if total >= hard else ("SOFT_LIMIT" if total >= soft else "OK")
    return {"status": status, "total_bytes": total, "file_count": files,
            "soft_bytes": soft, "hard_bytes": hard, "categories": categories,
            "automatic_deletion": False}


def _is_reparse(path: Path) -> bool:
    try:
        value = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(value.st_mode) or bool(getattr(value, "st_file_attributes", 0) & 0x400)


def _health_item(project_name: str) -> Dict[str, Any]:
    return {"project_ref": "sha256:" + hashlib.sha256(project_name.encode("utf-8")).hexdigest(),
            "binding_status": "UNKNOWN", "chain_status": "FAILED",
            "seal_status": "UNAVAILABLE", "queue_status": "EMPTY",
            "archive_status": "UNAVAILABLE", "capacity_status": "UNKNOWN",
            "event_count": 0, "segment_count": 0, "seal_count": 0,
            "pending_jobs": 0, "archive_segment_count": 0,
            "last_event_at": None, "error_code": "NONE", "event_chains": []}


def health_overview(project_context_root: Path, keyring_path: Optional[Path] = None) -> Dict[str, Any]:
    root = Path(project_context_root)
    if _is_reparse(root):
        raise EventArchiveError("HEALTH_ROOT_REPARSE_REJECTED")
    root_resolved = root.resolve(strict=False)
    projects = []
    for project in sorted(root.iterdir() if root.exists() else []):
        if _is_reparse(project):
            item = _health_item(project.name)
            item["error_code"] = "PROJECT_REPARSE_REJECTED"
            projects.append(item)
            continue
        if not project.is_dir():
            continue
        try:
            project.resolve(strict=False).relative_to(root_resolved)
        except ValueError:
            item = _health_item(project.name)
            item["error_code"] = "PROJECT_PATH_ESCAPE_REJECTED"
            projects.append(item)
            continue
        feedback = project / "feedback"
        current_event = feedback / "task-outcome-v3.jsonl"
        legacy_event = feedback / "task-outcome-v2.jsonl"
        current_has_files = current_event.exists() or any(
            current_event.parent.glob(current_event.stem + ".segment-*" + current_event.suffix)
        )
        legacy_has_files = legacy_event.exists() or any(
            legacy_event.parent.glob(legacy_event.stem + ".segment-*" + legacy_event.suffix)
        )
        events = ([current_event] if current_has_files else []) + ([legacy_event] if legacy_has_files else [])
        current_queue = feedback / "seal-queue-v3"
        legacy_queue = feedback / "seal-queue"
        queues = (current_queue, legacy_queue)
        archive_root = feedback / "archive"
        boundaries = (feedback, *events, *queues, archive_root,
                      *(_archive_root_for_event(event) for event in events),
                      *(queue / state for queue in queues
                        for state in ("pending", "running", "done", "dead-letter")))
        if any(_is_reparse(path) for path in boundaries):
            item = _health_item(project.name)
            item["error_code"] = "PROJECT_REPARSE_REJECTED"
            projects.append(item)
            continue
        if not events:
            continue
        try:
            for event in events:
                segments = event_segment_paths(event)
                seal_path = Path(str(event) + ".seals.jsonl")
                if any(_is_reparse(path) for path in [*segments, seal_path]):
                    raise EventArchiveError("PROJECT_REPARSE_REJECTED")
        except Exception as exc:
            item = _health_item(project.name)
            item["error_code"] = ("PROJECT_REPARSE_REJECTED" if str(exc) == "PROJECT_REPARSE_REJECTED"
                                  else "PROJECT_HEALTH_VALIDATION_FAILED")
            projects.append(item)
            continue
        item = _health_item(project.name)
        try:
            project_ids: set[str] = set()
            repos: set[str] = set()
            last_events: list[str] = []
            seal_statuses: list[str] = []
            for event in events:
                chain = read_event_chain(event, allow_duplicate_ids=True)
                rows = chain["events"]
                project_ids.update(str(row.get("project_id") or "") for row in rows)
                repos.update(str(row.get("repo_fingerprint") or "") for row in rows)
                if rows:
                    last_events.append(str(rows[-1].get("captured_at") or ""))
                detail = {
                    "role": "current" if event == current_event else "legacy-readonly",
                    "schema_version": chain["schema_version"],
                    "chain_status": "VALID",
                    "event_count": chain["record_count"],
                    "segment_count": len(event_segment_paths(event)),
                    "seal_status": "UNAVAILABLE",
                    "seal_count": 0,
                    "archive_status": "UNAVAILABLE",
                    "archive_segment_count": 0,
                    "queue_status": "EMPTY",
                    "pending_jobs": 0,
                }
                item["event_count"] += detail["event_count"]
                item["segment_count"] += detail["segment_count"]
                try:
                    seal = verify_event_seals(event, keyring_path=keyring_path)
                    detail.update(seal_status=seal["seal_status"], seal_count=seal["seal_count"])
                except IntegrityError:
                    pass
                seal_statuses.append(detail["seal_status"])
                archive = verify_archive(event)
                detail.update(archive_status="VALID", archive_segment_count=archive["segment_count"])
                chain_queue = current_queue if event == current_event else legacy_queue
                pending = sum(1 for state in ("pending", "running")
                              for _ in (chain_queue / state).glob("job-*.json"))
                detail.update(pending_jobs=pending, queue_status="PENDING" if pending else "EMPTY")
                item["seal_count"] += detail["seal_count"]
                item["archive_segment_count"] += detail["archive_segment_count"]
                item["pending_jobs"] += pending
                item["event_chains"].append(detail)
            item.update(chain_status="VALID", last_event_at=max(last_events) if last_events else None)
            if project_ids == {project.name} and len(repos) == 1:
                item["binding_status"] = "VALID"
            else:
                item.update(binding_status="CONFLICT", error_code="PROJECT_BINDING_CONFLICT")
            if seal_statuses and len(set(seal_statuses)) == 1:
                item["seal_status"] = seal_statuses[0]
            elif seal_statuses and "UNAVAILABLE" not in seal_statuses:
                item["seal_status"] = "VALID_SEALED_PREFIX_WITH_UNSEALED_TAIL"
            item["queue_status"] = "PENDING" if item["pending_jobs"] else "EMPTY"
            item["archive_status"] = "VALID"
            item["capacity_status"] = capacity_report(project)["status"]
        except Exception:
            item["error_code"] = "PROJECT_HEALTH_VALIDATION_FAILED"
        projects.append(item)
    return {"ok": all(item["error_code"] == "NONE" for item in projects),
            "schema_version": "1.0", "project_count": len(projects), "projects": projects,
            "privacy": {"raw_project_id": False, "raw_path": False, "event_body": False,
                        "prompt_or_response": False}}
