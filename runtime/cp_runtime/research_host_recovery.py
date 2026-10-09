"""中文：恢复研究第二版中因已验证宿主容量错误而结束的已创建子任务。恢复事件不是原生 SubagentStop，也不提供模型结论。

English: Recover a created study/2 child that ended with a verified host capacity error.

The recovery event is not a native SubagentStop and supplies no model verdict.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import budget_v5 as budget
from .common import atomic_write_json, require_external_state
from .context_final_v2 import read_bound_transcript
from .event_v2 import OwnerTokenLock
from .path_identity import same_path
from .research_seed import _index_dir, _index_key
from .routing_contract import _constant, _object, exact, fail, identifier, profile_spec, ref
from .routing_hook_v5 import _header_from_bytes, _transcript_path

ERROR_CODE = "server_overloaded"
ERROR_MESSAGE = "Selected model is at capacity. Please try a different model."
EVIDENCE_FIELDS = {"schema_version", "reservation_id", "permit_id", "child_ref",
                   "header_ref", "task_path_ref", "agent_ref", "transcript_bytes_sha256",
                   "file_binding", "terminal_event_ref", "turn_context_ref",
                   "error_code", "error_message", "index_ref", "ledger_head_before",
                   "created_receipt_ref", "native_subagent_stop", "model_final",
                   "reader_call", "actual_external_cost", "refund_claim"}


def _terminal_capacity_error(events_raw: list[dict], *, model: str, effort: str) -> tuple[dict, dict]:
    """中文：要求恰有一个已完成宿主回合，且没有模型最终回答或工具调用。
    
    English: Require one completed host turn, with no model final or tool invocation.
    """
    starts = [event for event in events_raw
              if event["type"] == "event_msg" and event["payload"].get("type") == "task_started"]
    contexts = [event for event in events_raw if event["type"] == "turn_context"]
    user_messages = [(position, event) for position, event in enumerate(events_raw)
                     if event["type"] == "response_item" and
                     event["payload"].get("type") == "message" and
                     event["payload"].get("role") == "user"]
    completions = [event for event in events_raw
                   if event["type"] == "event_msg" and event["payload"].get("type") == "task_complete"]
    if len(starts) != 1 or len(contexts) != 1 or len(user_messages) != 1 or len(completions) != 1:
        fail("RESEARCH_HOST_RECOVERY_TERMINAL_SHAPE")
    turn = contexts[0]["payload"].get("turn_id")
    if not isinstance(turn, str) or not turn:
        fail("RESEARCH_HOST_RECOVERY_TURN_ID")
    identifier(turn)
    if (events_raw[-1] != completions[0] or
            starts[0]["payload"].get("turn_id") != turn or
            completions[0]["payload"].get("turn_id") != turn or
            not events_raw.index(starts[0]) < user_messages[0][0] < events_raw.index(contexts[0]) < events_raw.index(completions[0]) or
            contexts[0]["payload"].get("model") != model or
            contexts[0]["payload"].get("effort") != effort):
        fail("RESEARCH_HOST_RECOVERY_TERMINAL_SHAPE")
    completion = completions[0]
    error = exact(completion["payload"].get("error"),
                  {"message", "codex_error_info"}, "RESEARCH_HOST_ERROR_FIELDS")
    if (error != {"message": ERROR_MESSAGE, "codex_error_info": ERROR_CODE} or
            completion["payload"].get("last_agent_message") is not None or
            any(event["type"] == "response_item" and event["payload"].get("phase") == "final_answer"
                for event in events_raw) or
            any(event["type"] == "response_item" and event["payload"].get("type") not in
                {"message", "agent_message"} for event in events_raw)):
        fail("RESEARCH_HOST_RECOVERY_MODEL_OR_TOOL_PRESENT")
    return contexts[0], completion


def recover_capacity_error(path: Path, transcript_path: Path, *, reservation_id: str) -> dict:
    """中文：仅对已绑定的终态容量错误追加独立宿主失败事件。
    
    English: Append a distinct failed-host event only for a bound terminal capacity error.
    """
    path = Path(path).absolute()
    transcript_path = Path(transcript_path).absolute()
    with OwnerTokenLock(path, timeout=2):
        events = budget._read_events(path)
        state = budget.replay(events)
        attempt = state["reservations"].get(reservation_id)
        if not attempt or attempt["state"] != "STARTED" or state["closed"]:
            fail("RESEARCH_HOST_RECOVERY_ACTIVE_ATTEMPT_REQUIRED")
        permit = state["permits"][attempt["permit_id"]]
        receipt = state["host_receipts"].get(reservation_id)
        link = state["host_identity_links"].get(reservation_id)
        if not receipt or receipt["disposition"] != "created" or not link:
            fail("RESEARCH_HOST_RECOVERY_CREATED_IDENTITY_REQUIRED")
        raw, file_binding = read_bound_transcript(transcript_path)
        if not raw.endswith(b"\n") or len(raw.splitlines()) > 4096:
            fail("RESEARCH_HOST_RECOVERY_TRANSCRIPT_BOUND")
        lines = raw.splitlines()
        if any(len(line) > 2 * 1024 * 1024 for line in lines):
            fail("RESEARCH_HOST_RECOVERY_EVENT_BOUND")
        events_raw = [json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
                      for line in lines]
        meta = events_raw[0]["payload"]
        child_id = meta["id"]
        session = meta["source"]["subagent"]["thread_spawn"]["parent_thread_id"]
        data = {"session_id": session, "agent_id": child_id,
                "agent_type": permit["role"], "hook_event_name": "HostTerminalRecovery",
                "transcript_path": str(transcript_path)}
        if _transcript_path(data) != transcript_path.resolve(strict=True):
            fail("RESEARCH_HOST_RECOVERY_TRANSCRIPT_PATH")
        header = _header_from_bytes(data, state, lines[0] + b"\n", file_binding)
        task_path = header["task_path"]
        if (header["parent_ref"] != state["root_binding"]["host_session_ref"] or
                link["proof_ref"] != ref(header) or link["task_path_ref"] != ref(task_path) or
                link["agent_ref"] != ref(child_id) or
                receipt["agent_ref"] != ref(task_path) or
                state["host_observations"].get(ref(child_id)) != {"start": "UNKNOWN"}):
            fail("RESEARCH_HOST_RECOVERY_HEADER_BINDING")
        index_key = _index_key(session, task_path, permit["role"])
        index_path = _index_dir(None) / (index_key + ".json")
        index = json.loads(index_path.read_text(encoding="utf8"),
                           object_pairs_hook=_object, parse_constant=_constant)
        if (index.get("status") != "READY" or
                index.get("reservation_id") != reservation_id or
                index.get("permit_id") != attempt["permit_id"] or
                index.get("task_path") != task_path or
                not same_path(Path(index.get("ledger_path", "")), path)):
            fail("RESEARCH_HOST_RECOVERY_EXPECTED_INDEX")
        spec = profile_spec(permit["selection"]["approved_profile"])
        context, completion = _terminal_capacity_error(events_raw, model=spec["model"], effort=spec["effort"])
        if (reservation_id in state["context_reads"] or
                reservation_id in state["context_deliveries"] or
                reservation_id in state.get("context_finals", {}) or
                reservation_id in state["accepted_results"]):
            fail("RESEARCH_HOST_RECOVERY_MODEL_OR_TOOL_PRESENT")
        evidence = {"schema_version": "research-host-capacity-terminal-proof/1",
                    "reservation_id": reservation_id,
                    "permit_id": attempt["permit_id"],
                    "child_ref": ref(child_id),
                    "header_ref": header["header_ref"],
                    "task_path_ref": ref(task_path),
                    "agent_ref": ref(child_id),
                    "transcript_bytes_sha256": hashlib.sha256(raw).hexdigest(),
                    "file_binding": file_binding,
                    "terminal_event_ref": ref(completion),
                    "turn_context_ref": ref(context),
                    "error_code": ERROR_CODE,
                    "error_message": ERROR_MESSAGE,
                    "index_ref": ref(index),
                    "ledger_head_before": state["head_hash"],
                    "created_receipt_ref": ref(receipt),
                    "native_subagent_stop": False,
                    "model_final": False,
                    "reader_call": False,
                    "actual_external_cost": "UNKNOWN",
                    "refund_claim": False}
        exact(evidence, EVIDENCE_FIELDS, "RESEARCH_HOST_RECOVERY_EVIDENCE_FIELDS")
        evidence_path = path.parent / "host-terminal-recovery" / (reservation_id + ".json")
        require_external_state(evidence_path, Path(state["root_binding"]["repo_path"]))
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        if evidence_path.exists():
            old = json.loads(evidence_path.read_text(encoding="utf8"),
                             object_pairs_hook=_object, parse_constant=_constant)
            if old != evidence:
                fail("RESEARCH_HOST_RECOVERY_EVIDENCE_CONFLICT")
        else:
            atomic_write_json(evidence_path, evidence)
        payload = {"reservation_id": reservation_id,
                   "agent_ref": ref(child_id),
                   "task_path_ref": ref(task_path),
                   "transcript_bytes_sha256": evidence["transcript_bytes_sha256"],
                   "file_binding_ref": ref(file_binding),
                   "error_code": ERROR_CODE,
                   "evidence_ref": ref(evidence),
                   "evidence_path": str(evidence_path)}
        updated = budget._append(path, events, budget._event(state, state["identity"],
                                                           "HOST_TERMINAL_ERROR_RECOVERED", payload))
        if (updated["reservations"][reservation_id]["state"] != "COMPLETED" or
                updated["reservations"][reservation_id]["outcome"] != "FAILED"):
            fail("RESEARCH_HOST_RECOVERY_READBACK")
        return {"schema_version": "research-host-terminal-recovery-receipt/1",
                "reservation_id": reservation_id,
                "evidence_path": str(evidence_path),
                "evidence_ref": ref(evidence),
                "event_ref": updated["head_hash"],
                "host_terminal_recovered": True,
                "native_subagent_stop": False,
                "model_grade": "UNRECORDED",
                "refund_claim": False}
