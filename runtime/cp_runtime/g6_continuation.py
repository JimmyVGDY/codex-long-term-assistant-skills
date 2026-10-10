"""中文：续跑沿用原根和工作谱系，以新的原生调用许可计费。

English: Continue in the original root/work lineage with a new native permit.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from . import g6_budget_v1 as budget
from .capability_store import bounded_read
from .common import atomic_write_json, utc_now, verify_record
from .event_v2 import OwnerTokenLock
from .g6_agent_identity import resolve
from .gate_contract import result as gate_result
from .routing_contract import _object, _constant, ref, exact

FIELDS = {"schema_version", "ledger_ref", "permit_id", "origin_permit_id", "host_call_ref",
          "target", "message_sha256", "tool", "reserved_at", "integrity"}


def _path(ledger: Path, call_ref: str) -> Path:
    return ledger.with_name(ledger.name + ".continuations") / (call_ref[7:] + ".json")


def read(ledger: Path, call_ref: str) -> dict[str, Any] | None:
    path = _path(ledger, call_ref)
    if not path.exists():
        return None
    value = json.loads(bounded_read(path, 32_768), object_pairs_hook=_object, parse_constant=_constant)
    exact(value, FIELDS, "G6_CONTINUATION_FIELDS")
    verify_record(value, "native continuation")
    if (value["schema_version"] != "g6-native-continuation/1"
            or value["ledger_ref"] != ref(str(ledger.resolve()))
            or value["host_call_ref"] != call_ref):
        raise ValueError("G6_CONTINUATION_IDENTITY")
    return value


def _deny(code: str, action: str, parameters: Mapping[str, Any] | None = None) -> dict[str, Any]:
    decision = gate_result(gate_id="continuation", entrypoint="g6_continuation.pretool",
                           reason_code=code, decision="REPREPARE", affected_action="continue_agent",
                           next_action=action, exact_parameters=parameters)
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": code + "; decision=" + json.dumps(decision, ensure_ascii=True)}}


def pretool(ledger: Path, data: Mapping[str, Any], tool: str) -> dict[str, Any]:
    if data.get("agent_id"):
        return _deny("G6_PARENT_CONTINUATION_REQUIRED", "request_parent_continuation")
    inputs = data.get("tool_input")
    if not isinstance(inputs, Mapping) or set(inputs) - {"target", "id", "message"}:
        return _deny("G6_CONTINUATION_INPUT", "use_supported_continuation_arguments")
    target = inputs.get("target", inputs.get("id"))
    if "target" in inputs and "id" in inputs and inputs["target"] != inputs["id"]:
        return _deny("G6_CONTINUATION_TARGET_CONFLICT", "use_one_verified_target")
    message = inputs.get("message", "Continue the existing assignment.")
    if not isinstance(message, str) or not message:
        return _deny("G6_MESSAGE_REQUIRED", "supply_continuation_message")
    session, cwd, call_id = data.get("session_id"), data.get("cwd"), data.get("tool_use_id")
    if not all(isinstance(value, str) and value for value in (session, cwd, call_id)):
        return _deny("G6_CONTINUATION_HOST_IDENTITY", "read_native_call_identity")
    target = resolve(ledger, target, session_id=session)
    state = budget.read_budget(ledger)
    matches = [pid for pid, receipt in state["receipts"].items()
               if receipt["disposition"] == "created" and receipt["agent_ref"] == ref(target)]
    if not matches:
        return _deny("G6_CONTINUATION_TARGET_UNBOUND", "use_root_bound_target")
    active = [pid for pid in matches if pid not in state["terminals"]]
    if active:
        # 中文：followup 在运行/空闲竞态中可能启动新回合；改用不启动回合的消息工具。
        # English: A running-to-idle race can make followup start a new turn.
        # Use the non-starting message tool instead, retaining the original text.
        return _deny("G6_TARGET_RUNNING_USE_MESSAGE", "reroute_original_message",
                     {"tool_name": "send_message", "arguments": {"target": target},
                      "reuse_original_fields": ["message"]})
    origin_id = max(matches, key=lambda pid: state["permits"][pid]["prepared_at"])
    origin = state["permits"][origin_id]
    call_ref = ref(call_id)
    marker = _path(ledger, call_ref)
    marker.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(marker, timeout=2):
        prior = read(ledger, call_ref)
        message_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()
        if prior is not None:
            if prior["target"] != target or prior["message_sha256"] != message_hash or prior["tool"] != tool:
                raise ValueError("G6_CONTINUATION_CHANGED")
            permit_id = prior["permit_id"]
            permit = budget.read_budget(ledger)["permits"][permit_id]
            params = {"task_name": permit["task_name"], "agent_type": permit["agent_type"],
                      "model": permit["model"], "reasoning_effort": permit["reasoning_effort"],
                      "fork_turns": "none", "message": message}
        else:
            from .g6_hook_v1 import _facts
            task_name = "continue_" + call_ref[7:47]
            facts = _facts(state["root"], {"task_name": task_name, "agent_type": origin["agent_type"],
                                          "message": message}, persist=True)
            facts["work_item_id"] = origin["work_item_id"]
            prepared = budget.prepare(ledger, facts=facts,
                capability={"schema_version": "g6-desktop-capability/1",
                            "available_profiles": [origin["approved_profile"]],
                            "source_ref": ref({"registered_dispatch": origin_id})},
                gates=[], agent_type=origin["agent_type"], task_name=task_name,
                message=message, decision_time=utc_now())
            if prepared["permit_id"] is None:
                return _deny("G6_CONTINUATION_CAPACITY", prepared["decision"]["next_action"])
            permit_id, params = prepared["permit_id"], prepared["decision"]["exact_tool_parameters"]
            value = {"schema_version": "g6-native-continuation/1", "ledger_ref": ref(str(ledger.resolve())),
                     "permit_id": permit_id, "origin_permit_id": origin_id, "host_call_ref": call_ref,
                     "target": target, "message_sha256": message_hash, "tool": tool,
                     "reserved_at": utc_now()}
            atomic_write_json(marker, value, seal=True)
        budget.approve_and_reserve(ledger, permit_id=permit_id, host_call_id=call_id,
                                  session_id=session, cwd=Path(cwd), args=params, now=utc_now())
    return {}


def posttool(ledger: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    value = read(ledger, ref(data.get("tool_use_id")))
    if value is None:
        return {}
    inputs = data.get("tool_input")
    if not isinstance(inputs, Mapping):
        raise ValueError("G6_CONTINUATION_INPUT")
    target = resolve(ledger, inputs.get("target", inputs.get("id")), session_id=str(data.get("session_id") or ""))
    message = inputs.get("message", "Continue the existing assignment.")
    if (target != value["target"] or not isinstance(message, str)
            or hashlib.sha256(message.encode("utf-8")).hexdigest() != value["message_sha256"]):
        raise ValueError("G6_CONTINUATION_CHANGED")
    response = data.get("tool_response")
    if isinstance(response, str):
        try:
            response = json.loads(response, object_pairs_hook=_object, parse_constant=_constant)
        except (ValueError, UnicodeError):
            return {}
    if not isinstance(response, dict) or response.get("task_name") != value["target"]:
        return {}
    state = budget.read_budget(ledger)
    if value["permit_id"] in state["receipts"]:
        receipt = state["receipts"][value["permit_id"]]
        if receipt["disposition"] != "created" or receipt["agent_ref"] != ref(value["target"]):
            raise ValueError("G6_RECEIPT_CHANGED")
        return {}
    budget.record_receipt(ledger, host_call_id=data["tool_use_id"], disposition="created",
                          agent_path=value["target"], proof_ref=ref({"source": "native-continuation-post",
                          "call_ref": value["host_call_ref"], "response_ref": ref(response)}))
    return {}
