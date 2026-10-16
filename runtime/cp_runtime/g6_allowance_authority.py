"""中文：从已绑定原生父会话读取追加批准；不接受调用方自报的批准字段。

English: Read allowance approvals from a bound native parent transcript.
This is logical provenance, not protection against an administrator rewriting
the original transcript and runtime state. No prompt bodies are persisted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from . import g6_allowance_contract as contract, g6_budget_v1 as budget
from .common import atomic_write_json, parse_iso, read_json, resolve_codex_home
from .context_final_v2 import read_bound_transcript
from .event_v2 import OwnerTokenLock
from .path_identity import path_is_within, same_path
from .routing_context_contract import safe_file
from .routing_contract import _constant, _object, exact, fail, ref

SOURCE_FIELDS = {"schema_version", "session_ref", "repo_path", "transcript_path",
                 "transcript_path_ref", "transcript_file_ref", "header_ref",
                 "offset", "turn_id", "skipping", "presented_requests"}
MAX_LINE = 131_072
MAX_SCAN = 2_000_000
DIRECT = re.compile(r"(?:批准|同意|允许)(?:本次|这次)?追加(?:额度|复审)?\s+(G6Q_[0-9a-f]{32})[。.!]?\Z")
ENGLISH = re.compile(r"approve allowance\s+(G6Q_[0-9a-f]{32})[.!]?\Z", re.IGNORECASE)
REVOKE = re.compile(r"(?:撤销|取消)(?:本次|这次)?追加(?:额度|复审)?\s+(G6Q_[0-9a-f]{32})[。.!]?\Z")
SHORT = re.compile(r"(?:我)?(?:(?:批准|同意|允许|授权|可以)[，,\s]*)?(?:本次|这次|再)?(?:追加|增加)(?:一次|一轮|1次|1轮)?(?:专项)?(?:额度|复审|复核)?(?:[，,](?:请)?(?:继续|开始|执行))?[。.!]?\Z")
AFFIRMATIVE = {"同意", "批准", "允许", "可以", "好的", "好", "确认", "yes", "approve", "approved"}
ASYNC = re.compile(r"<send_user_message_question_reply>\s*(.*?)\s*</send_user_message_question_reply>", re.DOTALL)
ACCEPT = {"批准本次追加", "同意追加", "允许追加", "批准本次追加（推荐）", "Approve this allowance"}
DECLINE = {"不追加", "拒绝追加", "取消追加", "Decline this allowance"}


def source_path(ledger: Path) -> Path:
    return ledger.with_name(ledger.name + ".allowance-source.json")


def _native_header(path: Path, *, session_id: str, cwd: Path) -> tuple[dict, dict]:
    path = safe_file(path)
    if (not path_is_within(path, resolve_codex_home() / "sessions")
            or not path.name.endswith(session_id + ".jsonl")):
        fail("G6_ALLOWANCE_NATIVE_SOURCE_PATH")
    raw, binding = read_bound_transcript(path, header_only=True)
    header = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    meta = header.get("payload", {})
    if (header.get("type") != "session_meta" or meta.get("id") != session_id
            or not isinstance(meta.get("cwd"), str) or not same_path(Path(meta["cwd"]), cwd)
            or isinstance(meta.get("source"), dict) and "subagent" in meta["source"]):
        fail("G6_ALLOWANCE_NATIVE_SOURCE_IDENTITY")
    return header, binding


def _read_source(path: Path) -> dict:
    value = read_json(path, verify=True, label="native allowance source")
    value.pop("integrity")
    exact(value, SOURCE_FIELDS, "G6_ALLOWANCE_SOURCE_FIELDS")
    if value["schema_version"] != "g6-allowance-native-source/1":
        fail("G6_ALLOWANCE_SOURCE_VERSION")
    if (type(value["offset"]) is not int or value["offset"] < 0
            or type(value["skipping"]) is not bool or not isinstance(value["turn_id"], str)
            or not isinstance(value["presented_requests"], list)
            or len(value["presented_requests"]) > contract.MAX_REQUESTS):
        fail("G6_ALLOWANCE_SOURCE_CURSOR")
    return value


def bind_source(ledger: Path, data: Mapping[str, Any]) -> dict:
    """中文：使用宿主提供的父会话路径；既有绑定不能被同名文件替换。

    English: Bind the host-provided parent source once; a copied file cannot replace it.
    """
    state = budget.read_budget(ledger)
    root = state["root"]
    session, cwd, transcript = data.get("session_id"), data.get("cwd"), data.get("transcript_path")
    if (data.get("agent_id") or not all(isinstance(x, str) and x for x in (session, cwd, transcript))
            or ref(session) != root["host_session_ref"] or not same_path(Path(cwd), Path(root["repo_path"]))):
        fail("G6_ALLOWANCE_SOURCE_HOST_IDENTITY")
    path = source_path(ledger)
    header, binding = _native_header(Path(transcript), session_id=session, cwd=Path(cwd))
    fixed = {"schema_version": "g6-allowance-native-source/1", "session_ref": ref(session),
             "repo_path": root["repo_path"], "transcript_path": str(Path(transcript).resolve()),
             **binding, "header_ref": ref(header)}
    for grant in [*state.get("allowance_grants", {}).values(), *state.get("allowance_revoked", {}).values()]:
        proof = grant["authorization"]
        if any(proof[key] != fixed[key] for key in ("transcript_path_ref", "transcript_file_ref", "header_ref")):
            fail("G6_ALLOWANCE_SOURCE_REPLACED")
    with OwnerTokenLock(path, timeout=2):
        if path.exists():
            previous = _read_source(path)
            # 中文：已核验的 Windows 命名空间别名不代表来源替换；保留原始路径与历史证明。
            # English: Proven Windows namespace aliases are not source replacement; keep stored paths and proofs.
            if (any(previous[key] != value for key, value in fixed.items() if key != "transcript_path")
                    or not same_path(Path(previous["transcript_path"]), Path(fixed["transcript_path"]))):
                fail("G6_ALLOWANCE_SOURCE_REPLACED")
            return previous
        # 中文：报价前先绑定当前位置；只消费此后真实提交的用户消息。
        # English: Bind before quoting; only subsequent native user messages can authorize.
        value = {**fixed, "offset": Path(transcript).stat().st_size,
                 "turn_id": str(data.get("turn_id") or ""), "skipping": False,
                 "presented_requests": []}
        atomic_write_json(path, value, seal=True)
        return value


def parse_response(text: str, requests: Mapping[str, Any], works: Mapping[str, Any],
                   presented: list[str]) -> tuple[str, str] | None:
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_LINE:
        return None
    text = text.strip()
    match = DIRECT.fullmatch(text) or ENGLISH.fullmatch(text)
    if match and match[1] in requests:
        return match[1], "grant"
    match = REVOKE.fullmatch(text)
    if match and match[1] in requests:
        return match[1], "revoke"
    if SHORT.fullmatch(text) or text.lower().rstrip("。.!") in AFFIRMATIVE:
        candidates = [key for key in presented if key in requests]
        if len(candidates) == 1:
            candidate = requests[candidates[0]]
            if ("一次" in text or "1次" in text) and sum(row["dispatches"] for row in candidate["allocations"]) != 1:
                return None
            return candidates[0], "grant"
    match = ASYNC.fullmatch(text)
    if match is None:
        return None
    try:
        replies = json.loads(match[1], object_pairs_hook=_object, parse_constant=_constant)
    except (ValueError, RecursionError):
        return None
    if not isinstance(replies, list) or not 1 <= len(replies) <= 3:
        return None
    matched = []
    for reply in replies:
        if (not isinstance(reply, dict) or set(reply) != {"questionItemId", "question", "answer"}
                or not isinstance(reply["questionItemId"], str)
                or not isinstance(reply["question"], str) or not isinstance(reply["answer"], str)):
            return None
        for key, request in requests.items():
            if reply["question"] in contract.question_variants(request, works):
                answer = reply["answer"].strip()
                if answer in ACCEPT:
                    matched.append((key, "grant"))
                elif answer in DECLINE:
                    matched.append((key, "revoke"))
    return matched[0] if len(matched) == 1 else None


def _user_text(record: Mapping[str, Any]) -> str | None:
    payload = record.get("payload", {})
    if (record.get("type") != "response_item" or payload.get("type") != "message"
            or payload.get("role") != "user" or not isinstance(payload.get("id"), str)):
        return None
    metadata = payload.get("internal_chat_message_metadata_passthrough")
    if (not isinstance(metadata, dict) or metadata.get("content_item_kinds") != ["user.text"]
            or not isinstance(metadata.get("turn_id"), str) or not metadata["turn_id"]):
        return None
    content = payload.get("content")
    if (not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict)
            or content[0].get("type") != "input_text" or not isinstance(content[0].get("text"), str)):
        return None
    return content[0]["text"]


def _presentation(record: Mapping[str, Any], state: Mapping[str, Any]) -> list[str] | None:
    payload = record.get("payload", {})
    if record.get("type") != "response_item":
        return None
    text = ""
    if payload.get("type") == "message" and payload.get("role") == "assistant":
        text = "\n".join(item.get("text", "") for item in payload.get("content", [])
                         if isinstance(item, dict) and isinstance(item.get("text"), str))
    elif payload.get("type") in {"function_call", "custom_tool_call"}:
        name = payload.get("name", "")
        if not isinstance(name, str) or not name.endswith("request_user_input_async"):
            return None
        raw = payload.get("arguments", payload.get("input", ""))
        if not isinstance(raw, str):
            return None
        try:
            questions = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant).get("questions", [])
            text = "\n".join(item["title"] for item in questions
                             if isinstance(item, dict) and isinstance(item.get("title"), str))
        except (ValueError, AttributeError, TypeError):
            return None
    else:
        return None
    matches = [key for key, request in state.get("allowance_requests", {}).items()
            if key not in state.get("allowance_grants", {}) and key not in state.get("allowance_revoked", {})
            and text.strip() in contract.question_variants(request, state["review_work"])]
    # 中文：简短回复只回答最后一个明确问题；其他助手消息使旧问题失效。
    # English: A short answer belongs only to the last exact question.
    return matches


def _apply_record(ledger: Path, source: Mapping[str, Any], record: dict, raw: bytes,
                  start: int, end: int) -> dict | None:
    text = _user_text(record)
    if text is None:
        return None
    with OwnerTokenLock(ledger, timeout=2):
        events = budget._read_events(ledger)
        state = budget.replay(events)
        result = parse_response(text, state.get("allowance_requests", {}),
                                state.get("review_work", {}), source["presented_requests"])
        if result is None:
            return None
        request_id, action = result
        if any(row["work_id"] in state.get("closed_review_work", {})
               for row in state["allowance_requests"][request_id]["allocations"]):
            return {"request_id": request_id, "action": "work_closed", "idempotent": True}
        stamp = record.get("timestamp")
        if not isinstance(stamp, str) or parse_iso(stamp) < parse_iso(state["allowance_requests"][request_id]["requested_at"]):
            return None
        if source["session_ref"] != state["root"]["host_session_ref"]:
            fail("G6_ALLOWANCE_AUTH_ROOT_CONFLICT")
        proof = {"source": "native-user-response", "session_ref": source["session_ref"],
                 "turn_ref": ref(record["payload"]["internal_chat_message_metadata_passthrough"]["turn_id"]),
                 "message_ref": ref([source["session_ref"], record["payload"]["id"]]),
                 "record_ref": "sha256:" + hashlib.sha256(raw).hexdigest(),
                 "transcript_path": source["transcript_path"],
                 **{key: source[key] for key in ("transcript_path_ref", "transcript_file_ref", "header_ref")},
                 "start": start, "end": end, "authorized_at": stamp}
        existing = state.get("allowance_grants" if action == "grant" else "allowance_revoked", {}).get(request_id)
        if existing:
            return {"request_id": request_id, "action": action, "idempotent": True}
        if request_id in state.get("allowance_revoked", {}):
            return {"request_id": request_id, "action": "revoked", "idempotent": True}
        budget._append(ledger, events, "ALLOWANCE_GRANTED" if action == "grant" else "ALLOWANCE_REVOKED",
                       {"request_id": request_id, "authorization": proof})
        return {"request_id": request_id, "action": action, "idempotent": False}


def recover(ledger: Path, *, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """中文：增量核验真实回复；批准入账后崩溃时重放同一消息不会重复扩额。

    English: Incremental source recovery; replay after grant append never adds quota twice.
    """
    if data is not None and data.get("transcript_path"):
        bind_source(ledger, data)
    path = source_path(ledger)
    if not path.exists():
        return {"status": "NATIVE_SOURCE_UNAVAILABLE", "applied": [],
                "next_action": "bind_current_native_parent_source"}
    with OwnerTokenLock(path, timeout=2):
        source = _read_source(path)
        state = budget.read_budget(ledger)
        if (source["session_ref"] != state["root"]["host_session_ref"]
                or not same_path(Path(source["repo_path"]), Path(state["root"]["repo_path"]))):
            fail("G6_ALLOWANCE_SOURCE_ROOT_CONFLICT")
        transcript = safe_file(Path(source["transcript_path"]))
        # 中文：文件名、头部与会话必须仍一致；复制相同字节的另一个文件不能接管证明。
        # English: Filename/header/session must agree; a copied file cannot take over the proof.
        with transcript.open("rb") as stream:
            raw_header = stream.readline(MAX_LINE + 1)
        header = json.loads(raw_header, object_pairs_hook=_object, parse_constant=_constant)
        session = header.get("payload", {}).get("id")
        if not isinstance(session, str) or ref(session) != source["session_ref"]:
            fail("G6_ALLOWANCE_SOURCE_SESSION")
        verified_header, binding = _native_header(transcript, session_id=session, cwd=Path(source["repo_path"]))
        if ref(verified_header) != source["header_ref"] or any(source[key] != value for key, value in binding.items()):
            fail("G6_ALLOWANCE_SOURCE_REPLACED")
        applied = []
        read_bytes = 0
        with transcript.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (ref({"device": opened.st_dev, "inode": opened.st_ino}) != source["transcript_file_ref"]
                    or opened.st_size < source["offset"]):
                fail("G6_ALLOWANCE_SOURCE_CHANGED")
            stream.seek(source["offset"])
            while read_bytes < MAX_SCAN:
                start = stream.tell()
                raw = stream.readline(min(MAX_LINE + 1, MAX_SCAN - read_bytes))
                if not raw:
                    break
                read_bytes += len(raw)
                if source["skipping"] or len(raw) > MAX_LINE:
                    # 中文：无法读取的记录可能更换了问题，保守清除简短回答上下文。
                    # English: An unreadable record may replace the question; discard short-answer context.
                    source["presented_requests"] = []
                    source["skipping"] = not raw.endswith(b"\n")
                    source["offset"] = stream.tell()
                    continue
                if not raw.endswith(b"\n"):
                    break
                record = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
                payload = record.get("payload", {})
                if record.get("type") == "turn_context" or (record.get("type") == "event_msg" and payload.get("type") == "task_started"):
                    if isinstance(payload.get("turn_id"), str):
                        source["turn_id"] = payload["turn_id"]
                presented = _presentation(record, state)
                if presented is not None:
                    source["presented_requests"] = presented
                result = _apply_record(ledger, source, record, raw, start, stream.tell())
                if result:
                    applied.append(result)
                    state = budget.read_budget(ledger)
                if _user_text(record) is not None:
                    # 中文：下一条真人回复消费问题上下文；后续无关的肯定不能追加额度。
                    # English: The next human reply consumes context, even when unrelated.
                    source["presented_requests"] = []
                source["offset"] = stream.tell()
            final = os.fstat(stream.fileno())
            if (final.st_dev, final.st_ino) != (opened.st_dev, opened.st_ino) or final.st_size < opened.st_size:
                fail("G6_ALLOWANCE_SOURCE_CHANGED")
        atomic_write_json(path, source, seal=True)
        return {"status": "RECORDED" if applied else "SOURCE_SCANNED", "applied": applied,
                "bytes_read": read_bytes, "has_more": source["offset"] < final.st_size,
                "next_action": "reprepare_dispatch" if applied else "await_native_approval_or_continue"}
