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
from typing import Any, Dict, List, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.event_v2 import EventContractError, read_event_chain  # noqa: E402

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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_host_session_facts(path: Path, parent_session_id: str) -> List[Dict[str, str]]:
    facts: List[Dict[str, str]] = []
    session_meta: Mapping[str, Any] | None = None
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise AcceptanceError("host session evidence could not be read") from exc
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AcceptanceError("host session evidence is not valid JSONL") from exc
        if not isinstance(record, dict) or not isinstance(record.get("payload"), dict):
            continue
        payload = record["payload"]
        if record.get("type") == "session_meta":
            source = payload.get("source") or {}
            subagent = source.get("subagent") if isinstance(source, dict) else {}
            spawn = subagent.get("thread_spawn") if isinstance(subagent, dict) else {}
            if isinstance(spawn, dict) and str(spawn.get("parent_thread_id") or "") == parent_session_id:
                session_meta = payload
        elif record.get("type") == "turn_context" and session_meta is not None:
            model = str(payload.get("model") or session_meta.get("model") or "")
            effort = str(payload.get("effort") or "")
            turn_id = str(payload.get("turn_id") or "")
            role = str(session_meta.get("agent_role") or "")
            if model and turn_id:
                facts.append({"turn_id": turn_id, "model": model, "reasoning_effort": effort, "agent_role": role})
    if not facts:
        raise AcceptanceError("host session evidence does not contain a correlated subagent turn")
    return facts


def _model_evidence(
    paired_tasks: Sequence[str],
    starts: Sequence[Mapping[str, Any]],
    expected_model: str,
    expected_effort: str,
    host_session_log: Path | None,
    parent_session_id: str,
) -> Dict[str, Any]:
    actual_models = sorted({str(event.get("actual_model") or "") for event in starts if event.get("actual_model")})
    hook_match = bool(expected_model and expected_model in actual_models)
    host_match = False
    observed_efforts: List[str] = []
    host_log_hash = ""
    if host_session_log is not None:
        facts = _load_host_session_facts(host_session_log, parent_session_id)
        host_log_hash = _sha256_file(host_session_log)
        matching = [fact for fact in facts if fact["turn_id"] in paired_tasks]
        if expected_model:
            matching = [fact for fact in matching if fact["model"] == expected_model]
        if expected_effort:
            matching = [fact for fact in matching if fact["reasoning_effort"] == expected_effort]
        host_match = bool(matching)
        observed_efforts = sorted({fact["reasoning_effort"] for fact in matching if fact["reasoning_effort"]})
    if expected_model and not (hook_match or host_match):
        raise AcceptanceError("expected subagent model was not proven by hook or correlated host session evidence")
    return {
        "status": "PASS" if expected_model and (hook_match or host_match) else "NOT_REQUESTED",
        "expected_model": expected_model,
        "expected_reasoning_effort": expected_effort,
        "hook_payload_match": hook_match,
        "host_session_match": host_match,
        "host_session_log_sha256": host_log_hash,
        "observed_reasoning_efforts": observed_efforts,
        "actual_model_fact_preserved": True,
    }


def verify_lifecycle(
    event_file: Path,
    session_id: str,
    project_id: str,
    repo_fingerprint: str,
    expected_subagent_model: str = "",
    expected_reasoning_effort: str = "",
    host_session_log: Path | None = None,
) -> Dict[str, Any]:
    try:
        chain = read_event_chain(event_file, os.environ.get("CP_ASSISTANT_HMAC_KEY"))
    except EventContractError as exc:
        raise AcceptanceError("event hash chain validation failed: %s" % exc) from exc
    selected = [event for event in chain["events"] if str(event.get("session_id") or "") == session_id]
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
        if not child_task:
            continue
        matching_stop = next(
            (
                stop
                for stop_index, stop in indexed_stops
                if start_index < stop_index < parent_completed_index
                and parent_open_index < start_index
                and str(stop.get("task_id") or "") == child_task
            ),
            None,
        )
        if matching_stop is not None:
            paired_tasks.append(child_task)
    paired_tasks = sorted(set(paired_tasks))
    if not paired_tasks:
        raise AcceptanceError("no ordered subagent start/stop pair was found inside the parent task")
    model_evidence = _model_evidence(
        paired_tasks,
        starts,
        expected_subagent_model,
        expected_reasoning_effort,
        host_session_log,
        session_id,
    )
    counts = Counter(types)
    source_fields = ("actual_model_source", "actual_reasoning_effort_source", "terminal_outcome_source")
    fact_sources = {
        field: dict(sorted(Counter(str(event.get(field) or "unavailable") for event in selected).items()))
        for field in source_fields
    }
    fact_coverage = {
        field: sum(1 for event in selected if event.get(field) == "hook-payload") / len(selected)
        for field in source_fields
    }
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
        "subagent_model_evidence": model_evidence,
        "host_fact_sources": fact_sources,
        "host_fact_coverage": fact_coverage,
        "event_chain": {
            "valid": True,
            "record_count": chain["record_count"],
            "head": chain["head_hash"],
            "files": chain["files"],
            "hmac_verified": bool(os.environ.get("CP_ASSISTANT_HMAC_KEY")),
        },
        "privacy": {
            "raw_session_id_exported": False,
            "raw_task_id_exported": False,
            "prompt_or_response_exported": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.4 real lifecycle verifier")
    parser.add_argument("--event-file", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--repo-fingerprint", required=True)
    parser.add_argument("--expected-subagent-model", default="")
    parser.add_argument("--expected-reasoning-effort", default="")
    parser.add_argument("--host-session-log")
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    report = verify_lifecycle(
        Path(arguments.event_file),
        arguments.session_id,
        arguments.project_id,
        arguments.repo_fingerprint,
        arguments.expected_subagent_model,
        arguments.expected_reasoning_effort,
        Path(arguments.host_session_log) if arguments.host_session_log else None,
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
