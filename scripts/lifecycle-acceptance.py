#!/usr/bin/env python3
"""Verify one real Codex lifecycle without exporting raw task identifiers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.event_v2 import EventContractError, verify_event_chain  # noqa: E402

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


def _read_events(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AcceptanceError("invalid JSONL record at line %d" % number) from exc
        if not isinstance(item, dict):
            raise AcceptanceError("event record must be an object")
        events.append(item)
    return events


def verify_lifecycle(
    event_file: Path,
    session_id: str,
    project_id: str,
    repo_fingerprint: str,
    expected_subagent_model: str = "gpt-5.6-luna",
) -> Dict[str, Any]:
    try:
        chain = verify_event_chain(event_file, os.environ.get("CP_ASSISTANT_HMAC_KEY"))
    except EventContractError as exc:
        raise AcceptanceError("event hash chain validation failed: %s" % exc) from exc
    selected = [event for event in _read_events(event_file) if str(event.get("session_id") or "") == session_id]
    if not selected:
        raise AcceptanceError("target session was not found")
    for event in selected:
        if event.get("project_id") != project_id:
            raise AcceptanceError("project_id mismatch inside target session")
        if event.get("repo_fingerprint") != repo_fingerprint:
            raise AcceptanceError("repo_fingerprint mismatch inside target session")
    types = [str(event.get("event_type") or "") for event in selected]
    positions: List[int] = []
    cursor = 0
    for required in REQUIRED_SEQUENCE:
        try:
            position = types.index(required, cursor)
        except ValueError as exc:
            raise AcceptanceError("missing or out-of-order lifecycle event: %s" % required) from exc
        positions.append(position)
        cursor = position + 1
    indexed_starts = [(index, event) for index, event in enumerate(selected) if event.get("event_type") == "SUBAGENT_STARTED"]
    indexed_stops = [(index, event) for index, event in enumerate(selected) if event.get("event_type") == "SUBAGENT_STOPPED"]
    starts = [event for _index, event in indexed_starts]
    actual_models = sorted({str(event.get("actual_model") or "") for event in starts if event.get("actual_model")})
    if expected_subagent_model not in actual_models:
        raise AcceptanceError("expected subagent model was not observed")
    parent_open_index = positions[0]
    parent_open = selected[parent_open_index]
    parent_task = str(parent_open.get("task_id") or "")
    completed_candidates = [
        (index, event)
        for index, event in enumerate(selected)
        if index > parent_open_index
        and event.get("event_type") == "TASK_COMPLETED"
        and str(event.get("task_id") or "") == parent_task
    ]
    if not parent_task or not completed_candidates:
        raise AcceptanceError("parent task correlation failed")
    parent_completed_index, parent_completed = completed_candidates[0]
    session_end_indexes = [index for index, event in enumerate(selected) if event.get("event_type") == "SESSION_ENDED"]
    if not any(index > parent_completed_index for index in session_end_indexes):
        raise AcceptanceError("SessionEnd did not occur after parent completion")
    paired_tasks = []
    for start_index, start in indexed_starts:
        child_task = str(start.get("task_id") or "")
        if not child_task or str(start.get("actual_model") or "") != expected_subagent_model:
            continue
        matching_stop = next(
            (
                stop
                for stop_index, stop in indexed_stops
                if start_index < stop_index < parent_completed_index
                and parent_open_index < start_index
                and str(stop.get("task_id") or "") == child_task
                and str(stop.get("actual_model") or "") == expected_subagent_model
            ),
            None,
        )
        if matching_stop is not None:
            paired_tasks.append(child_task)
    paired_tasks = sorted(set(paired_tasks))
    if not paired_tasks:
        raise AcceptanceError("no ordered, model-matched subagent start/stop pair was found inside the parent task")
    counts = Counter(types)
    return {
        "ok": True,
        "schema_version": "1.0",
        "project_id": project_id,
        "repo_fingerprint": repo_fingerprint,
        "session_ref": _ref(session_id),
        "parent_task_ref": _ref(parent_task),
        "subagent_task_refs": [_ref(task) for task in paired_tasks],
        "required_sequence": list(REQUIRED_SEQUENCE),
        "event_type_counts": dict(sorted(counts.items())),
        "actual_subagent_models": actual_models,
        "actual_reasoning_efforts": sorted(
            {str(event.get("actual_reasoning_effort") or "") for event in starts if event.get("actual_reasoning_effort")}
        ),
        "event_chain": {
            "valid": True,
            "record_count": chain["record_count"],
            "head": chain["head_hash"],
            "hmac_verified": bool(os.environ.get("CP_ASSISTANT_HMAC_KEY")),
        },
        "privacy": {
            "raw_session_id_exported": False,
            "raw_task_id_exported": False,
            "prompt_or_response_exported": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.3 real lifecycle verifier")
    parser.add_argument("--event-file", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--repo-fingerprint", required=True)
    parser.add_argument("--expected-subagent-model", default="gpt-5.6-luna")
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    report = verify_lifecycle(
        Path(arguments.event_file),
        arguments.session_id,
        arguments.project_id,
        arguments.repo_fingerprint,
        arguments.expected_subagent_model,
    )
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except AcceptanceError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
