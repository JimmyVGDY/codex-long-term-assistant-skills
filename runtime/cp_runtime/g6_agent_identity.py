"""中文：将原生子任务身份映射到本根的规范路径，不跨项目搜索。

English: Map native child identities to this root's canonical paths, without
cross-project searches or prompt storage.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from . import g6_budget_v1 as budget
from .capability_store import bounded_read
from .common import atomic_write_json, verify_record
from .event_v2 import OwnerTokenLock
from .path_identity import same_path
from .routing_contract import _constant, _object, exact, ref

FIELDS = {"schema_version", "ledger_ref", "session_ref", "agent_id_ref", "task_path",
          "agent_type", "transcript_path", "header_ref", "integrity"}


def _path(ledger: Path, agent_id: str) -> Path:
    return ledger.with_name(ledger.name + ".agents") / (ref(agent_id)[7:] + ".json")


def remember(ledger: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    from .g6_handoff_v1 import _child_task_path
    from .routing_hook_v5 import _transcript_path

    task = _child_task_path(dict(data))
    state = budget.read_budget(ledger)
    if (state["root"]["host_session_ref"] != ref(data.get("session_id"))
            or not any(receipt["disposition"] == "created" and receipt["agent_ref"] == ref(task)
                       for receipt in state["receipts"].values())):
        raise ValueError("G6_AGENT_LINK_UNBOUND")
    transcript = _transcript_path(data)
    with transcript.open("rb") as stream:
        raw = stream.readline(131073)
    if len(raw) > 131072:
        raise ValueError("G6_AGENT_HEADER_BOUND")
    header = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    if not same_path(Path(header["payload"]["cwd"]), Path(state["root"]["repo_path"])):
        raise ValueError("G6_AGENT_REPOSITORY_CONFLICT")
    value = {"schema_version": "g6-native-agent-link/1", "ledger_ref": ref(str(ledger.resolve())),
             "session_ref": state["root"]["host_session_ref"], "agent_id_ref": ref(data["agent_id"]),
             "task_path": task, "agent_type": data["agent_type"],
             "transcript_path": str(transcript), "header_ref": ref(header)}
    path = _path(ledger, data["agent_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=2):
        if path.exists():
            previous = json.loads(bounded_read(path, 32_768), object_pairs_hook=_object, parse_constant=_constant)
            verify_record(previous, "native agent identity")
            previous.pop("integrity")
            if previous != value:
                raise ValueError("G6_AGENT_LINK_CONFLICT")
            return value
        atomic_write_json(path, value, seal=True)
    return value


def resolve(ledger: Path, target: str, *, session_id: str) -> str:
    if not isinstance(target, str) or not target or len(target) > 256:
        raise ValueError("G6_MESSAGE_TARGET_REQUIRED")
    if re.fullmatch(r"/root/[a-z0-9_]{1,64}", target):
        return target
    if re.fullmatch(r"[a-z0-9_]{1,64}", target):
        return "/root/" + target
    path = _path(ledger, target)
    if not path.exists():
        raise ValueError("G6_AGENT_ID_UNVERIFIED_USE_CANONICAL_PATH")
    with OwnerTokenLock(path, timeout=2):
        value = json.loads(bounded_read(path, 32_768), object_pairs_hook=_object, parse_constant=_constant)
        exact(value, FIELDS, "G6_AGENT_LINK_FIELDS")
        verify_record(value, "native agent identity")
    state = budget.read_budget(ledger)
    if (value["schema_version"] != "g6-native-agent-link/1"
            or value["ledger_ref"] != ref(str(ledger.resolve()))
            or value["session_ref"] != state["root"]["host_session_ref"]
            or ref(session_id) != state["root"]["host_session_ref"]
            or value["agent_id_ref"] != ref(target)):
        raise ValueError("G6_AGENT_LINK_IDENTITY")
    from .g6_handoff_v1 import _child_task_path
    event = {"session_id": session_id,
             "agent_id": target, "agent_type": value["agent_type"],
             "hook_event_name": "PreToolUse", "transcript_path": value["transcript_path"]}
    # 中文：先验证宿主路径，再读取已绑定头；缓存不得使读取越出原生会话目录。
    # English: Verify the host path before reading the bound header; a cache
    # must not redirect reads outside the native session directory.
    from .routing_hook_v5 import _transcript_path
    with _transcript_path(event).open("rb") as stream:
        raw = stream.readline(131073)
    if len(raw) > 131072:
        raise ValueError("G6_AGENT_HEADER_BOUND")
    header = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    parent = header["payload"]["source"]["subagent"]["thread_spawn"]["parent_thread_id"]
    if ref(header) != value["header_ref"] or ref(parent) != value["session_ref"]:
        raise ValueError("G6_AGENT_HEADER_CHANGED")
    if _child_task_path(event) != value["task_path"]:
        raise ValueError("G6_AGENT_LINK_IDENTITY")
    return value["task_path"]
