#!/usr/bin/env python3
"""中文：验证一次真实 Codex 生命周期，不导出原始任务标识。

English: Verify one real Codex lifecycle without exporting raw task identifiers.
"""
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
from cp_runtime.host_facts import HostFactError, load_host_session_facts  # noqa: E402
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


def _model_evidence(
    paired_tasks: Sequence[str],
    starts: Sequence[Mapping[str, Any]],
    expected_model: str,
    expected_effort: str,
    host_session_log: Path | Sequence[Path] | None,
    parent_session_id: str,
) -> Dict[str, Any]:
    hook_facts = [event for event in starts
                  if event.get("actual_model_source") == "host-attested-hook-payload"
                  and event.get("actual_reasoning_effort_source") == "host-attested-hook-payload"
                  and isinstance(event.get("metadata"), Mapping)
                  and str(event.get("metadata", {}).get("host_attestation_ref") or "").startswith("sha256:")]
    attestation_refs = [str(event["metadata"]["host_attestation_ref"]) for event in hook_facts]
    if len(attestation_refs) != len(set(attestation_refs)):
        raise AcceptanceError("trusted runtime model attestation was replayed")
    hook_match = any(
        str(event.get("actual_model") or "") == expected_model
        and (not expected_effort or str(event.get("actual_reasoning_effort") or "") == expected_effort)
        for event in hook_facts
    ) if expected_model else False
    host_match = False
    observed_efforts: List[str] = []
    host_log_hash: str | List[str] = ""
    host_diagnostic: Dict[str, Any] = {"trust_level": "DIAGNOSTIC", "source_count": 0,
                                      "correlated_turn_count": 0, "source_sha256": []}
    if host_session_log is not None:
        paths = [host_session_log] if isinstance(host_session_log, Path) else list(host_session_log)
        try:
            host_diagnostic = load_host_session_facts(paths, parent_session_id, paired_tasks)
        except HostFactError as exc:
            raise AcceptanceError(str(exc)) from exc
        facts = host_diagnostic["facts"]
        host_log_hash = host_diagnostic["source_sha256"]
        matching = [fact for fact in facts if fact["turn_id"] in paired_tasks]
        if expected_model:
            matching = [fact for fact in matching if fact["model"] == expected_model]
        if expected_effort:
            matching = [fact for fact in matching if fact["reasoning_effort"] == expected_effort]
        host_match = bool(matching)
        observed_efforts = sorted({fact["reasoning_effort"] for fact in matching if fact["reasoning_effort"]})
        hook_models = {(str(event.get("actual_model") or ""),
                        str(event.get("actual_reasoning_effort") or "")) for event in hook_facts}
        host_models = {(fact["model"], fact["reasoning_effort"]) for fact in matching}
        diagnostic_conflict = bool(hook_models and host_models and not (hook_models & host_models))
    else:
        diagnostic_conflict = False
    if expected_model and hook_facts and not hook_match:
        raise AcceptanceError("trusted runtime model evidence conflicts with the expected model")
    observations = sorted({"%s / %s" % (fact["model"], fact["reasoning_effort"] or "unknown")
                           for fact in host_diagnostic.get("facts", [])})
    return {
        "status": "VERIFIED" if hook_match else "UNAVAILABLE",
        "runtime_model_evidence": "VERIFIED" if hook_match else "UNAVAILABLE",
        "diagnostic_model_observation": ", ".join(observations) if observations else "UNAVAILABLE",
        "expected_model": expected_model,
        "expected_reasoning_effort": expected_effort,
        "hook_payload_match": hook_match,
        "host_session_match": host_match,
        "host_session_log_sha256": host_log_hash,
        "host_session_trust_level": "DIAGNOSTIC",
        "host_session_source_count": host_diagnostic["source_count"],
        "host_session_correlated_turn_count": host_diagnostic["correlated_turn_count"],
        "observed_reasoning_efforts": observed_efforts,
        "diagnostic_conflict_with_runtime_evidence": diagnostic_conflict,
        "actual_model_fact_preserved": True,
    }


def verify_lifecycle(
    event_file: Path,
    session_id: str,
    project_id: str,
    repo_fingerprint: str,
    expected_subagent_model: str = "",
    expected_reasoning_effort: str = "",
    host_session_log: Path | Sequence[Path] | None = None,
    seal_file: Path | None = None,
    keyring_path: Path | None = None,
    requested_model_policy: str = "UNAVAILABLE",
) -> Dict[str, Any]:
    try:
        chain = read_event_chain(event_file, os.environ.get("CP_ASSISTANT_HMAC_KEY"))
    except EventContractError as exc:
        raise AcceptanceError("event hash chain validation failed: %s" % exc) from exc
    seal_evidence: Dict[str, Any] = {"seal_status": "UNAVAILABLE", "seal_count": 0,
                                    "sealed_record_count": 0}
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
        field: sum(1 for event in selected
                   if event.get(field) in {"hook-payload", "host-attested-hook-payload"}) / len(selected)
        for field in source_fields
    }
    return {
        "ok": True,
        "schema_version": "1.1",
        "requested_model_policy": requested_model_policy,
        "runtime_model_evidence": model_evidence["runtime_model_evidence"],
        "diagnostic_model_observation": model_evidence["diagnostic_model_observation"],
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
            "seal_status": seal_evidence.get("seal_status"),
            "seal_count": seal_evidence.get("seal_count", 0),
            "sealed_record_count": seal_evidence.get("sealed_record_count", 0),
            "seal_key_ids": seal_evidence.get("key_ids", []),
        },
        "privacy": {
            "raw_session_id_exported": False,
            "raw_task_id_exported": False,
            "prompt_or_response_exported": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.6 real lifecycle verifier")
    parser.add_argument("--event-file", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--repo-fingerprint", required=True)
    parser.add_argument("--expected-subagent-model", default="")
    parser.add_argument("--expected-reasoning-effort", default="")
    parser.add_argument("--host-session-log", action="append", default=[])
    parser.add_argument("--seal-file")
    parser.add_argument("--keyring")
    parser.add_argument("--requested-model-policy", choices=("PASS", "FAIL", "UNAVAILABLE"), default="UNAVAILABLE")
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    report = verify_lifecycle(
        Path(arguments.event_file),
        arguments.session_id,
        arguments.project_id,
        arguments.repo_fingerprint,
        arguments.expected_subagent_model,
        arguments.expected_reasoning_effort,
        [Path(item) for item in arguments.host_session_log] if arguments.host_session_log else None,
        Path(arguments.seal_file) if arguments.seal_file else None,
        Path(arguments.keyring) if arguments.keyring else None,
        arguments.requested_model_policy,
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
