"""中文：同聊天路由交接使用独立版本，旧研究历史不变。

English: Versioned same-chat routing handoff; old research history remains untouched.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import budget_v5, g6_budget_v1, research_campaign
from .common import atomic_write_json, read_json, require_external_state, resolve_codex_home
from .event_v2 import OwnerTokenLock
from .g6_handoff_provenance import verify_stop_checkpoint
from .path_identity import same_path
from .routing_contract import _constant, _object, exact, fail, ref, sha

SCHEMA = "g6-session-routing-handoff/1"
FIELDS = {"schema_version", "session_ref", "repo_path", "project_identity",
          "new_ledger_path", "new_policy_id", "new_policy_digest",
          "old_stop_evidence", "user_change_ref"}


def pointer_for(session_id: str, directory: Path | None = None) -> Path:
    root = directory or resolve_codex_home() / "cp-assistant" / "g6-routing"
    return root / ("session-" + ref(session_id)[7:] + ".json")


def _old_anchor(evidence: dict[str, Any]) -> Path:
    old = Path(evidence["old_ledger_path"])
    events = budget_v5._read_events(old)
    sequence = evidence["old_ledger_anchor_sequence"]
    if (type(sequence) is not int or sequence < 1 or sequence > len(events)
            or events[sequence - 1]["record_hash"] != evidence["old_ledger_anchor_hash"]):
        fail("G6_HANDOFF_OLD_LEDGER_ANCHOR")
    budget_v5.replay(events)
    return old


def bind(*, session_id: str, repo_path: Path, new_ledger_path: Path,
         user_change_ref: str, stop_checkpoint_path: Path | None = None,
         directory: Path | None = None, old_head_path: Path | None = None) -> dict[str, Any]:
    sha(user_change_ref)
    new_state = g6_budget_v1.read_budget(new_ledger_path)
    root = new_state["root"]
    if (root["host_session_ref"] != ref(session_id)
            or not same_path(Path(root["repo_path"]), repo_path)
            or root["policy_digest"] != "sha256:" + g6_budget_v1.POLICY_SHA256):
        fail("G6_HANDOFF_NEW_ROOT")
    old_head = old_head_path or research_campaign._head(session_id)
    evidence = None
    if old_head.exists():
        if stop_checkpoint_path is None:
            fail("G6_HANDOFF_STOP_CHECKPOINT_REQUIRED")
        evidence = verify_stop_checkpoint(stop_checkpoint_path, session_id=session_id,
                                          repo_path=repo_path, head_path=old_head)
        if any(root["identity"][key] != evidence["identity"][key]
               for key in ("project_id", "repo_fingerprint")):
            fail("G6_HANDOFF_PROJECT_IDENTITY")
    elif stop_checkpoint_path is not None:
        fail("G6_HANDOFF_OLD_HEAD_MISSING")
    pointer = pointer_for(session_id, directory)
    require_external_state(pointer.resolve(), repo_path.resolve())
    value = {"schema_version": SCHEMA, "session_ref": ref(session_id),
             "repo_path": str(repo_path.resolve()), "project_identity": root["identity"],
             "new_ledger_path": str(new_ledger_path.resolve()),
             "new_policy_id": g6_budget_v1.POLICY_ID,
             "new_policy_digest": "sha256:" + g6_budget_v1.POLICY_SHA256,
             "old_stop_evidence": evidence, "user_change_ref": user_change_ref}
    pointer.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(pointer, timeout=2):
        if pointer.exists():
            old = read_json(pointer, verify=True, label="GPT-6 routing handoff")
            old.pop("integrity")
            if old != value:
                fail("G6_HANDOFF_ALREADY_BOUND")
            return value
        atomic_write_json(pointer, value, seal=True)
    return value


def read(session_id: str, *, directory: Path | None = None) -> dict[str, Any] | None:
    pointer = pointer_for(session_id, directory)
    if not pointer.exists():
        return None
    with OwnerTokenLock(pointer, timeout=2):
        value = read_json(pointer, verify=True, label="GPT-6 routing handoff")
    value.pop("integrity")
    exact(value, FIELDS, "G6_HANDOFF_FIELDS")
    if (value["schema_version"] != SCHEMA or value["session_ref"] != ref(session_id)
            or value["new_policy_id"] != g6_budget_v1.POLICY_ID
            or value["new_policy_digest"] != "sha256:" + g6_budget_v1.POLICY_SHA256):
        fail("G6_HANDOFF_POLICY_OR_SESSION")
    sha(value["user_change_ref"])
    new = g6_budget_v1.read_budget(Path(value["new_ledger_path"]))
    if (new["root"]["host_session_ref"] != ref(session_id)
            or new["root"]["identity"] != value["project_identity"]
            or not same_path(Path(new["root"]["repo_path"]), Path(value["repo_path"]))):
        fail("G6_HANDOFF_NEW_ROOT_CHANGED")
    if value["old_stop_evidence"] is not None:
        evidence = value["old_stop_evidence"]
        if (evidence["session_ref"] != ref(session_id)
                or any(evidence["identity"][key] != value["project_identity"][key]
                       for key in ("project_id", "repo_fingerprint"))):
            fail("G6_HANDOFF_OLD_ROOT_CHANGED")
        _old_anchor(evidence)
    return value


def _child_task_path(data: dict[str, Any]) -> str:
    from .routing_hook_v5 import _transcript_path
    path = _transcript_path(data)
    with path.open("rb") as stream:
        raw = stream.readline(131073)
    if len(raw) > 131072 or not raw.endswith(b"\n"):
        fail("G6_CHILD_HEADER_BOUND")
    event = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    meta = event["payload"]
    spawn = meta["source"]["subagent"]["thread_spawn"]
    task = spawn["agent_path"]
    if (event["type"] != "session_meta" or meta["id"] != data.get("agent_id")
            or spawn["parent_thread_id"] != data.get("session_id")
            or spawn["agent_role"] != data.get("agent_type")
            or not isinstance(task, str)
            or not re.fullmatch(r"/root/[a-z0-9_]{1,64}", task)):
        fail("G6_CHILD_HEADER_IDENTITY")
    return task


def route(data: dict[str, Any], *, directory: Path | None = None) -> tuple[str, Path] | None:
    """中文：返回归属及账本，不猜测未知子任务或调用的归属。
    
    English: Return (owner, ledger); never guess an unrecognized child or call.
    """
    session = data.get("session_id")
    if not isinstance(session, str) or not session:
        return None
    binding = read(session, directory=directory)
    if binding is None:
        return None
    new_path = Path(binding["new_ledger_path"])
    old_evidence = binding["old_stop_evidence"]
    old_path = Path(old_evidence["old_ledger_path"]) if old_evidence else None
    if data.get("agent_id"):
        task_path = _child_task_path(data)
        agent_ref = ref(task_path)
        new = g6_budget_v1.read_budget(new_path)
        new_owner = any(receipt["agent_ref"] == agent_ref
                        for receipt in new["receipts"].values())
        old_owner = False
        if old_path:
            old = budget_v5.read_budget(old_path)
            old_owner = any(receipt["agent_ref"] == agent_ref
                            for receipt in old["host_receipts"].values())
        if new_owner == old_owner:
            fail("G6_CHILD_OWNER_AMBIGUOUS_OR_UNKNOWN")
        if old_owner:
            # 中文：归属查询本身只读；事件交给旧 V5 生命周期处理时，仍核验原 expected-spawn 索引。
            # English: Ownership lookup itself stays read-only.  The frozen V5 lifecycle
            # still validates its expected-spawn index when this event falls
            # through to that handler.
            return "old", old_path
        return "new", new_path
    from .dispatch_policy import delegation_tool_name
    event = data.get("hook_event_name")
    billable = {"spawn_agent", "followup_task", "send_input", "resume_agent"}
    if event == "PostToolUse" and delegation_tool_name(data.get("tool_name")) in billable:
        call_ref = ref(data.get("tool_use_id"))
        new_owner = call_ref in g6_budget_v1.read_budget(new_path)["host_calls"]
        old_owner = old_path is not None and call_ref in budget_v5.read_budget(old_path)["host_dispatches"]
        if new_owner == old_owner:
            fail("G6_PARENT_CALL_OWNER_AMBIGUOUS_OR_UNKNOWN")
        return ("new", new_path) if new_owner else ("old", old_path)
    if event == "PreToolUse" and delegation_tool_name(data.get("tool_name")) in billable:
        if old_path and ref(data.get("tool_use_id")) in budget_v5.read_budget(old_path)["host_dispatches"]:
            fail("G6_OLD_CALL_CANNOT_REENTER")
    return "new", new_path
