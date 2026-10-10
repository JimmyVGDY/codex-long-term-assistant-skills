"""中文：同一原生调用的有界对账队列，不启动或免费重派模型。

English: Bounded reconciliation of the same native call; never spawn or refund.
"""
from __future__ import annotations

import json
import time
from datetime import timedelta
from itertools import islice
from pathlib import Path
from typing import Any, Callable

from . import g6_budget_v1 as budget
from .common import RuntimeContractError, atomic_write_json, utc_now, parse_iso, verify_record
from .capability_store import bounded_read
from .event_v2 import OwnerTokenLock
from .g6_retry_v1 import next_action
from .routing_contract import ref, _object, _constant, exact

EVENT_FIELDS = {"hook_event_name", "session_id", "turn_id", "agent_id", "agent_type",
                "cwd", "transcript_path", "agent_transcript_path", "terminal_outcome"}


def _directory(path: Path) -> Path:
    return path.with_name(path.name + ".reconciliation")


def _read_job(path: Path) -> dict[str, Any]:
    value = json.loads(bounded_read(path, 32_768), object_pairs_hook=_object, parse_constant=_constant)
    verify_record(value, "native reconciliation")
    exact(value, {"schema_version", "ledger_ref", "permit_id", "event", "attempts",
                  "observed_size", "next_at", "status", "integrity"}, "G6_RECONCILIATION_FIELDS")
    if (not isinstance(value["event"], dict) or set(value["event"]) - EVENT_FIELDS
            or type(value["attempts"]) is not int or value["attempts"] < 0
            or value["event"].get("hook_event_name") != "SubagentStop"
            or value["status"] not in {"PENDING", "COMPLETE"}):
        raise ValueError("G6_RECONCILIATION_FIELDS")
    return value


def enqueue_stop(path: Path, data: dict[str, Any], permit_id: str) -> None:
    state = budget.read_budget(path)
    if (permit_id not in state["receipts"]
            or state["root"]["host_session_ref"] != ref(data.get("session_id"))):
        raise ValueError("G6_RECONCILIATION_IDENTITY")
    event = {key: data[key] for key in EVENT_FIELDS if key in data}
    if (event.get("hook_event_name") != "SubagentStop"
            or any(value is not None and (not isinstance(value, str) or len(value) > 4096)
                   for value in event.values())):
        raise ValueError("G6_RECONCILIATION_EVENT")
    from .g6_handoff_v1 import _child_task_path
    if state["receipts"][permit_id]["agent_ref"] != ref(_child_task_path(event)):
        raise ValueError("G6_RECONCILIATION_CHILD")
    target = _directory(path) / (ref([permit_id, event.get("turn_id")])[7:] + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(target, timeout=2):
        if target.exists():
            old = _read_job(target)
            if old["permit_id"] != permit_id or old["event"] != event:
                raise ValueError("G6_RECONCILIATION_EVENT_CHANGED")
            return
        atomic_write_json(target, {"schema_version": "g6-native-reconciliation/1",
                          "ledger_ref": ref(str(path.resolve())), "permit_id": permit_id,
                          "event": event, "attempts": 0, "observed_size": None,
                          "next_at": utc_now(), "status": "PENDING"}, seal=True)


def _drain_one(path: Path, source: Path, callback: Callable) -> dict[str, Any] | None:
    with OwnerTokenLock(source, timeout=0.01):
        value = _read_job(source)
        value.pop("integrity")
        if value["status"] == "COMPLETE":
            return None
        state = budget.read_budget(path)
        pid = value["permit_id"]
        if (value["schema_version"] != "g6-native-reconciliation/1"
                or value["ledger_ref"] != ref(str(path.resolve()))
                or pid not in state["receipts"]
                or source.name != ref([pid, value["event"].get("turn_id")])[7:] + ".json"
                or ref(value["event"].get("session_id")) != state["root"]["host_session_ref"]):
            raise ValueError("G6_RECONCILIATION_IDENTITY")
        if pid in state["terminals"]:
            value["status"] = "COMPLETE"
            atomic_write_json(source, value, seal=True)
            return {"permit_id": pid, "status": "COMPLETE"}
        from .g6_handoff_v1 import route, _child_task_path
        owner = route(value["event"])
        if owner is None or owner[0] != "new" or owner[1].resolve() != path.resolve():
            raise ValueError("G6_RECONCILIATION_OWNER")
        if state["receipts"][pid]["agent_ref"] != ref(_child_task_path(value["event"])):
            raise ValueError("G6_RECONCILIATION_CHILD")
        from .routing_hook_v5 import _transcript_path
        observed = _transcript_path(value["event"]).stat().st_size
        now = parse_iso(utc_now())
        changed = observed != value["observed_size"]
        if not changed and (value["attempts"] >= 2 or now < parse_iso(value["next_at"])):
            return None
        advice = next_action(state, work_item_id=state["permits"][pid]["work_item_id"],
                             failure_kind="verified_transient_read", now=now.isoformat(),
                             deadline_at=(now + timedelta(seconds=30)).isoformat())
        if advice["action"] != "RESUME_SAME_HANDLE":
            raise ValueError("G6_RECONCILIATION_HANDLE")
        callback(path, value["event"])
        value.update(attempts=value["attempts"] + 1, observed_size=observed,
                     next_at=(now + timedelta(seconds=2)).isoformat(),
                     status="COMPLETE" if pid in budget.read_budget(path)["terminals"] else "PENDING")
        atomic_write_json(source, value, seal=True)
        return {"permit_id": pid, "status": value["status"], "attempts": value["attempts"],
                "retry_decision": advice["action"]}


def drain(path: Path, callback: Callable[[Path, dict[str, Any]], Any], *, limit: int = 1) -> dict[str, Any]:
    """中文：每次最多核验两个句柄；记录增长可触发再次读回但不清零次数。

    English: Recheck at most two handles. File growth permits a new readback
    without resetting prior attempts or model accounting.
    """
    if type(limit) is not int or not 1 <= limit <= 2:
        raise ValueError("G6_RECONCILIATION_LIMIT")
    rows, errors = [], []
    directory = _directory(path)
    if not directory.exists():
        return {"status": "NO_PENDING", "items": rows}
    files = sorted(islice(directory.glob("*.json"), 65))
    if len(files) > 64:
        return {"status": "WAIT_RECONCILE", "reason_code": "G6_RECONCILIATION_BOUND", "items": rows}
    deadline = time.monotonic() + 0.25
    for source in files:
        if len(rows) >= limit or time.monotonic() >= deadline:
            break
        try:
            row = _drain_one(path, source, callback)
            if row is not None:
                rows.append(row)
        except (RuntimeContractError, OSError, ValueError, KeyError, TypeError):
            # 中文：单条辅助记录损坏只限制该记录；不阻止其他原生句柄对账。
            # English: A damaged sidecar restricts that record only, not
            # reconciliation of other native handles.
            errors.append({"record_ref": ref(str(source)), "reason_code": "RECONCILIATION_RECORD_UNAVAILABLE"})
    return {"status": "READBACK_PERFORMED" if rows else "WAIT_RECONCILE", "items": rows, "errors": errors}
