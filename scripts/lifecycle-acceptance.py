#!/usr/bin/env python3
"""中文：验证真实 Codex 生命周期，不读取或导出宿主模型信息。

English: Verify a real Codex lifecycle without reading or exporting host model facts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.event_v3 import EventContractError, read_event_chain  # noqa: E402
from cp_runtime.integrity import IntegrityError, verify_event_seals  # noqa: E402

REQUIRED_SEQUENCE = (
    "TURN_OPENED",
    "SUBAGENT_STARTED",
    "SUBAGENT_STOPPED",
    "TASK_COMPLETED",
    "SESSION_ENDED",
)


class AcceptanceError(RuntimeError):
    pass


def _ref(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_lifecycle(
    event_file: Path,
    session_id: str,
    project_id: str,
    repo_fingerprint: str,
    seal_file: Path | None = None,
    keyring_path: Path | None = None,
) -> Dict[str, Any]:
    try:
        chain = read_event_chain(event_file, os.environ.get("CP_ASSISTANT_HMAC_KEY"))
    except EventContractError as exc:
        raise AcceptanceError("event hash chain validation failed: %s" % exc) from exc
    seal_evidence: Dict[str, Any] = {
        "seal_status": "UNAVAILABLE",
        "seal_count": 0,
        "sealed_record_count": 0,
    }
    if seal_file is not None or keyring_path is not None:
        try:
            seal_evidence = verify_event_seals(event_file, seal_file, keyring_path)
        except IntegrityError as exc:
            raise AcceptanceError("event seal validation failed: %s" % exc) from exc
        if seal_evidence.get("seal_status") != "SEALED_CURRENT":
            raise AcceptanceError("current event chain head is not sealed")

    selected = [event for event in chain["events"] if str(event.get("session_id") or "") == session_id]
    if not selected:
        raise AcceptanceError("target session was not found")
    for event in selected:
        if event.get("project_id") != project_id:
            raise AcceptanceError("project_id mismatch inside target session")
        if event.get("repo_fingerprint") != repo_fingerprint:
            raise AcceptanceError("repo_fingerprint mismatch inside target session")

    types = [str(event.get("event_type") or "") for event in selected]
    positions = []
    cursor = 0
    for required in REQUIRED_SEQUENCE:
        try:
            position = types.index(required, cursor)
        except ValueError as exc:
            raise AcceptanceError("missing or out-of-order lifecycle event: %s" % required) from exc
        positions.append(position)
        cursor = position + 1

    indexed_starts = [
        (index, event)
        for index, event in enumerate(selected)
        if event.get("event_type") == "SUBAGENT_STARTED"
    ]
    indexed_stops = [
        (index, event)
        for index, event in enumerate(selected)
        if event.get("event_type") == "SUBAGENT_STOPPED"
    ]
    parent_open_index = positions[0]
    parent_task = str(selected[parent_open_index].get("task_id") or "")
    completed_candidates = [
        (index, event)
        for index, event in enumerate(selected)
        if index > parent_open_index
        and event.get("event_type") == "TASK_COMPLETED"
        and str(event.get("task_id") or "") == parent_task
    ]
    if not parent_task or not completed_candidates:
        raise AcceptanceError("parent task correlation failed")
    parent_completed_index, _parent_completed = completed_candidates[0]
    if not any(
        index > parent_completed_index
        for index, event in enumerate(selected)
        if event.get("event_type") == "SESSION_ENDED"
    ):
        raise AcceptanceError("SessionEnd did not occur after parent completion")

    paired_tasks = []
    for start_index, start in indexed_starts:
        child_task = str(start.get("task_id") or "")
        if not child_task:
            continue
        matching_stop = next(
            (
                stop
                for stop_index, stop in indexed_stops
                if parent_open_index < start_index < stop_index < parent_completed_index
                and str(stop.get("task_id") or "") == child_task
            ),
            None,
        )
        if matching_stop is not None:
            paired_tasks.append(child_task)
    paired_tasks = sorted(set(paired_tasks))
    if not paired_tasks:
        raise AcceptanceError("no ordered subagent start/stop pair was found inside the parent task")

    counts = Counter(types)
    return {
        "ok": True,
        "schema_version": "2.0",
        "project_id": project_id,
        "repo_fingerprint": repo_fingerprint,
        "session_ref": _ref(session_id),
        "parent_task_ref": _ref(parent_task),
        "subagent_task_refs": [_ref(task) for task in paired_tasks],
        "required_sequence": list(REQUIRED_SEQUENCE),
        "event_type_counts": dict(sorted(counts.items())),
        "event_chain": {
            "valid": True,
            "schema_version": chain.get("schema_version"),
            "record_count": chain["record_count"],
            "head": chain["head_hash"],
            "files": chain["files"],
            "hmac_verified": bool(os.environ.get("CP_ASSISTANT_HMAC_KEY")),
            "seal_status": seal_evidence.get("seal_status"),
            "seal_count": seal_evidence.get("seal_count", 0),
            "sealed_record_count": seal_evidence.get("sealed_record_count", 0),
            "seal_key_ids": seal_evidence.get("key_ids", []),
        },
        "privacy": {
            "host_model_information_read": False,
            "host_model_information_exported": False,
            "raw_session_id_exported": False,
            "raw_task_id_exported": False,
            "prompt_or_response_exported": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V7.4.4 real lifecycle verifier")
    parser.add_argument("--event-file", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--repo-fingerprint", required=True)
    parser.add_argument("--seal-file")
    parser.add_argument("--keyring")
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    report = verify_lifecycle(
        Path(arguments.event_file),
        arguments.session_id,
        arguments.project_id,
        arguments.repo_fingerprint,
        Path(arguments.seal_file) if arguments.seal_file else None,
        Path(arguments.keyring) if arguments.keyring else None,
    )
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except AcceptanceError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
