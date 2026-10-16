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
        from .g6_task_scope import route, _child_task_path
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


def _recover_child_creation(path: Path, transcript: Path) -> dict[str, Any]:
    # 中文：显式来源只定位候选；真实原生头、原预占与项目归属共同证明创建。
    # English: An explicit path only locates a candidate; its native header, reservation and project ownership prove creation.
    from .capability_store import safe_path
    from .common import resolve_codex_home
    from .path_identity import path_is_within, same_path
    from .g6_handoff_v1 import _child_task_path
    from .g6_task_scope import child_owner
    from .g6_agent_identity import remember
    from .g6_hook_v1 import _recover_native_creation
    transcript = safe_path(transcript)
    if not path_is_within(transcript, safe_path(resolve_codex_home() / "sessions")):
        raise ValueError("G6_AGENT_TRANSCRIPT_PATH")
    with transcript.open("rb") as stream:
        raw = stream.readline(131_073)
    if len(raw) > 131_072 or not raw.endswith(b"\n"):
        raise ValueError("G6_AGENT_HEADER_BOUND")
    header = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    meta = header["payload"]
    spawn = meta["source"]["subagent"]["thread_spawn"]
    event = {"hook_event_name": "NativeTranscriptReadback", "session_id": spawn["parent_thread_id"],
             "agent_id": meta["id"], "agent_type": spawn["agent_role"], "cwd": meta["cwd"],
             "transcript_path": str(transcript)}
    task = _child_task_path(event)
    state = budget.read_budget(path)
    if (ref(event["session_id"]) != state["root"]["host_session_ref"]
            or not same_path(Path(meta["cwd"]), Path(state["root"]["repo_path"]))):
        raise ValueError("G6_CHILD_REPOSITORY_CONFLICT")
    matches = [pid for pid in state["reservations"]
               if "/root/" + state["permits"][pid]["task_name"] == task
               and state["permits"][pid]["agent_type"] == event["agent_type"]]
    if len(matches) != 1 or parse_iso(header["timestamp"]) < parse_iso(state["reservations"][matches[0]]["reserved_at"]):
        raise ValueError("G6_NATIVE_CREATION_UNVERIFIED")
    owner = child_owner(event)
    if owner is None or owner[0] != "new" or not same_path(owner[1], path):
        raise ValueError("G6_RECONCILIATION_OWNER")
    _recover_native_creation(event, native_readback=True)
    remember(path, event)
    return {"permit_id": matches[0], "status": "CREATION_RECOVERED",
            "evidence_source": "native-child-header-readback"}


def recover_bound_terminals(path: Path, *, limit: int = 2,
                            child_transcripts: list[Path] | None = None) -> dict[str, Any]:
    """中文：原生Stop丢失时读取已绑定子任务的真实结束事件，不伪造Hook或业务PASS。
    English: Recover real terminal events of bound children when Stop is missing, without inventing a Hook or business PASS.
    """
    from .g6_agent_identity import FIELDS, resolve
    from .g6_hook_v1 import _terminal
    from .native_transcript import complete_tail
    from .capability_store import safe_path
    from .common import resolve_codex_home

    if type(limit) is not int or not 1 <= limit <= 2:
        raise ValueError("G6_RECONCILIATION_LIMIT")
    sources = child_transcripts if child_transcripts is not None else []
    if not isinstance(sources, list) or len(sources) > 2:
        raise ValueError("G6_CHILD_SOURCE_LIMIT")
    creations, creation_errors = [], []
    for source in sources:
        try:
            creations.append(_recover_child_creation(path, source))
        except (RuntimeContractError, OSError, ValueError, KeyError, TypeError, RecursionError):
            creation_errors.append({"record_ref": ref(str(source)), "reason_code": "G6_NATIVE_CREATION_UNVERIFIED"})
    from .g6_review_receipt_v1 import recover_pending
    recovered_receipts = recover_pending(path, limit=limit)
    recovered_receipts["errors"].extend(creation_errors)
    state = budget.read_budget(path)
    active_groups = {}
    for pid, row in state["receipts"].items():
        if row["disposition"] == "created" and pid not in state["terminals"]:
            active_groups.setdefault(row["agent_ref"], []).append(pid)
    active = {key: ids[0] for key, ids in active_groups.items() if len(ids) == 1}
    if not active:
        return {"status": "READBACK_PERFORMED" if recovered_receipts["items"] else
                "WAIT_RECONCILE" if active_groups or creation_errors else "NO_PENDING",
                "creations": creations, **recovered_receipts}
    directory = safe_path(path.with_name(path.name + ".agents"))
    if not directory.is_dir():
        return {"status": "WAIT_RECONCILE", "items": [], "errors": []}
    files = list(islice(directory.glob("*.json"), 513))
    if len(files) > 512:
        return {"status": "WAIT_RECONCILE", "reason_code": "NATIVE_LINK_SCAN_BOUND", "items": [], "errors": []}
    rows, errors = recovered_receipts["items"], recovered_receipts["errors"]
    deadline = time.monotonic() + 2
    for source in files:
        if len(rows) >= limit or time.monotonic() >= deadline:
            break
        try:
            link = json.loads(bounded_read(safe_path(source), 32_768), object_pairs_hook=_object, parse_constant=_constant)
            exact(link, FIELDS, "G6_AGENT_LINK_FIELDS")
            verify_record(link, "native agent identity")
            pid = active.get(ref(link["task_path"]))
            if pid is None:
                continue
            if (link["schema_version"] != "g6-native-agent-link/1"
                    or link["ledger_ref"] != ref(str(path.resolve()))
                    or link["session_ref"] != state["root"]["host_session_ref"]
                    or link["agent_type"] != state["permits"][pid]["agent_type"]
                    or source.name != link["agent_id_ref"][7:] + ".json"):
                raise ValueError("G6_AGENT_LINK_IDENTITY")
            transcript = safe_path(Path(link["transcript_path"]))
            if not transcript.is_relative_to(safe_path(resolve_codex_home() / "sessions")):
                raise ValueError("G6_AGENT_TRANSCRIPT_PATH")
            before = transcript.stat()
            with transcript.open("rb") as stream:
                raw_header = stream.readline(131_073)
            if len(raw_header) > 131_072 or not raw_header.endswith(b"\n"):
                raise ValueError("G6_AGENT_HEADER_BOUND")
            header = json.loads(raw_header, object_pairs_hook=_object, parse_constant=_constant)
            meta = header["payload"]
            session = meta["source"]["subagent"]["thread_spawn"]["parent_thread_id"]
            if (ref(header) != link["header_ref"] or ref(meta["id"]) != link["agent_id_ref"]
                    or resolve(path, meta["id"], session_id=session) != link["task_path"]):
                raise ValueError("G6_AGENT_HEADER_CHANGED")
            raw, window = complete_tail(transcript)
            turns = set()
            reserved_at = parse_iso(state["reservations"][pid]["reserved_at"])
            if not window["truncated_prefix"]:
                for line in raw.splitlines():
                    event = json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
                    payload = event.get("payload", {})
                    stamp = event.get("timestamp")
                    if (isinstance(payload, dict) and isinstance(stamp, str)
                            and parse_iso(stamp) >= reserved_at
                            and (event.get("type") == "turn_context" or event.get("type") == "event_msg"
                                 and payload.get("type") == "task_started")):
                        turn = payload.get("turn_id")
                        if isinstance(turn, str) and 0 < len(turn) <= 256:
                            turns.add(turn)
            after = transcript.stat()
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino) or after.st_size < before.st_size:
                raise ValueError("NATIVE_WINDOW_CHANGED")
            if len(turns) != 1:
                rows.append({"permit_id": pid, "status": "WAIT_RECONCILE", "reason_code": "NATIVE_TURN_UNVERIFIED"})
                continue
            event = {"hook_event_name": "NativeTranscriptReadback", "session_id": session,
                     "agent_id": meta["id"], "agent_type": link["agent_type"], "cwd": state["root"]["repo_path"],
                     "transcript_path": str(transcript), "turn_id": next(iter(turns))}
            _terminal(path, event, reconciling=True, native_readback=True)
            completed = pid in budget.read_budget(path)["terminals"]
            rows.append({"permit_id": pid, "status": "COMPLETE" if completed else "WAIT_RECONCILE",
                         "evidence_source": "native-transcript-readback"})
        except (RuntimeContractError, OSError, ValueError, KeyError, TypeError, RecursionError):
            errors.append({"record_ref": ref(str(source)), "reason_code": "NATIVE_READBACK_UNVERIFIED"})
    return {"status": "READBACK_PERFORMED" if rows else "WAIT_RECONCILE", "items": rows,
            "errors": errors, "creations": creations}
