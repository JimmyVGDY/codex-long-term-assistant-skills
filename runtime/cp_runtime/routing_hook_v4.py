"""中文：桌面委派的 V4 请求/回执适配，未识别的响应不猜关联。

English: V4 Desktop delegation adapter; unknown responses stay unassociated.
Only hashes of messages and host identifiers enter the budget journal.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from . import budget_v4
from .common import inside, resolve_codex_home
from .path_identity import path_aliases, same_path
from .routing_context_v4 import loader, verify_root
from .routing_contract import fail, ref

TOOLS = {"agent", "spawn_agent", "collaboration.spawn_agent"}
NONCE_HEADER = re.compile(r"^CP_REVIEW_DISPATCH/2 ([0-9a-f]{64})\r?\n\r?\n")


def _session_identity(data: Mapping[str, Any], *, session: str, cwd: str, agent_id: str) -> dict[str, Any] | None:
    """中文：只接受宿主提供的 sessions 内路径，只读第一行身份元数据，不读正文。

    English: The observed Desktop metadata shape is explicitly fail-closed. Only a
    host-provided path under sessions is read, bounded to its first metadata record.
    The transcript body and runtime model fields are never inspected or persisted.
    """
    source = data.get("agent_transcript_path")
    if not isinstance(source, str) or not source:
        return None
    try:
        path = Path(source)
        if not path.is_absolute():
            return None
        path = path.resolve(strict=True)
        if not inside(path, (resolve_codex_home() / "sessions").resolve(strict=True)):
            return None
        if path.suffix != ".jsonl" or not path.name.endswith(agent_id + ".jsonl"):
            return None
        with path.open("rb") as stream:
            raw = stream.readline(131073)
        if len(raw) > 131072 or not raw.endswith(b"\n"):
            return None
        from .routing_contract import _object, _constant
        event = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
        meta = event["payload"]
        spawn = meta["source"]["subagent"]["thread_spawn"]
        task_path = spawn["agent_path"]
        if event["type"] != "session_meta" or meta["id"] != agent_id \
                or not same_path(Path(meta["cwd"]), Path(cwd)) \
                or spawn["parent_thread_id"] != session or type(spawn["depth"]) is not int or spawn["depth"] != 1 \
                or spawn["agent_role"] != data.get("agent_type") \
                or not isinstance(task_path, str) or not re.fullmatch(r"/root/[a-z0-9_]{1,64}", task_path):
            return None
        return {"schema_version": "desktop-agent-identity/1", "parent_session_ref": ref(session),
                "agent_ref": ref(agent_id), "task_path": task_path, "role": spawn["agent_role"],
                "header_source_ref": ref(str(path))}
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return None


def pretool(path: Path, data: Mapping[str, Any], args: Mapping[str, Any], *,
            lookup: Callable, aliases: Mapping[str, Any]) -> dict[str, Any]:
    state = budget_v4.read_budget(path)
    session = str(lookup(data, "root_session_id", "rootSessionId") or lookup(data, *aliases["session_id"]) or "")
    cwd = str(lookup(data, *aliases["cwd"]) or "")
    verify_root(state, cwd=cwd, host_session_id=session)
    if lookup(data, *aliases["agent_id"]):
        fail("V4_NESTED_CALLER_NOT_AUTHORIZED")
    if not ((args.get("fork_turns") == "none" and args.get("fork_context", False) is False)
            or (args.get("fork_context") is False and args.get("fork_turns", "none") == "none")):
        fail("V4_INDEPENDENT_CONTEXT_REQUIRED")
    message = args.get("message")
    if not isinstance(message, str):
        fail("V4_MESSAGE_REQUIRED")
    dispatch_key = str(lookup(args, *aliases["task_name"]) or "").strip()
    nonce = ""
    if dispatch_key:
        if message.startswith(budget_v4.NATIVE_PREFIX):
            fail("V4_DISPATCH_KEY_NONCE_CONFLICT")
        matches = [value for value in state["permits"].values() if value["dispatch_ref"] == ref(dispatch_key)]
        body = message
    else:
        matched = NONCE_HEADER.match(message)
        if not matched:
            fail("V4_NATIVE_DISPATCH_HEADER_REQUIRED")
        nonce, body = matched.group(1), message[matched.end():]
        if body.startswith(budget_v4.NATIVE_PREFIX):
            fail("V4_DUPLICATE_DISPATCH_HEADER")
        matches = [value for value in state["permits"].values() if value["nonce_ref"] == ref(nonce)]
    if len(matches) != 1:
        fail("V4_PERMIT_MISSING_OR_AMBIGUOUS")
    return budget_v4.approve_and_reserve(
        path, permit_id=matches[0]["permit_id"],
        host_dispatch_id=str(lookup(data, *aliases["tool_use_id"]) or ""),
        model=str(lookup(args, *aliases["model"]) or ""),
        effort=str(lookup(args, *aliases["reasoning_effort"]) or ""),
        agent_type=str(lookup(args, *aliases["agent_type"]) or ""),
        snapshot_loader=loader(cwd=cwd, host_session_id=session),
        message_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(), nonce=nonce,
    )


def lifecycle(path: Path, data: Mapping[str, Any], hook_name: str, *, args: Mapping[str, Any],
              lookup: Callable, aliases: Mapping[str, Any]) -> str | None:
    state = budget_v4.read_budget(path)
    session = str(lookup(data, "root_session_id", "rootSessionId") or lookup(data, *aliases["session_id"]) or "")
    cwd = str(lookup(data, *aliases["cwd"]) or "")
    verify_root(state, cwd=cwd, host_session_id=session)
    if hook_name == "PostToolUse":
        tool = str(lookup(data, *aliases["tool_name"]) or "").lower()
        if tool not in TOOLS:
            return None
        response = data.get("tool_response")
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except ValueError:
                return None
        if not isinstance(response, Mapping):
            return None
        agent_id = lookup(response, *aliases["agent_id"])
        # 中文：只解析桌面工具明确的任务树回执，不扫描正文或从通用状态猜创建结果。
        # English: The task-tree interface is explicit in the Desktop tool contract.
        # Do not scan response prose or infer creation from generic status.
        if not agent_id and tool in {"spawn_agent", "collaboration.spawn_agent"}:
            value = response.get("task_name")
            requested_name = lookup(args, *aliases["task_name"])
            if isinstance(value, str) and isinstance(requested_name, str) \
                    and value == "/root/" + requested_name:
                agent_id = value
        if not isinstance(agent_id, str) or not agent_id:
            return None
        result = budget_v4.record_receipt(
            path, host_dispatch_id=str(lookup(data, *aliases["tool_use_id"]) or ""), agent_id=agent_id)
        return result["reservation_id"]
    agent_id = lookup(data, *aliases["agent_id"])
    if not isinstance(agent_id, str) or not agent_id:
        return None
    if hook_name == "SubagentStop":
        header = _session_identity(data, session=session, cwd=cwd, agent_id=agent_id)
        if header:
            dispatch_key = header["task_path"].rsplit("/", 1)[-1]
            matches = [attempt for attempt in state["reservations"].values()
                       if state["permits"][attempt["permit_id"]]["dispatch_ref"] == ref(dispatch_key)
                       and state["permits"][attempt["permit_id"]]["role"] == header["role"]]
            if len(matches) == 1:
                proof_ref = ref(header)
                # 中文：不根据锁外快照猜旧摘要；账本原子比较已核验的等价证明。
                # English: Do not select from a stale snapshot; the ledger compares verified proofs atomically.
                proofs = tuple(sorted({ref({**header, "header_source_ref": ref(str(alias))})
                                       for alias in path_aliases(Path(data["agent_transcript_path"]))}))
                budget_v4.link_host_identity(path, reservation_id=matches[0]["reservation_id"],
                    task_path=header["task_path"], agent_id=agent_id, dispatch_key=dispatch_key,
                    role=header["role"], proof_ref=proof_ref, verified_proof_aliases=proofs)
    outcome = str(lookup(data, *aliases["terminal_outcome"]) or "UNKNOWN").upper()
    budget_v4.record_observation(path, agent_id=agent_id, phase="start" if hook_name == "SubagentStart" else "stop",
                                 outcome="UNKNOWN" if hook_name == "SubagentStart" else outcome)
    updated = budget_v4.read_budget(path)
    matches = [rid for rid in updated["host_receipts"]
               if budget_v4.effective_agent_ref(updated, rid) == ref(agent_id)]
    return matches[0] if len(matches) == 1 else None
