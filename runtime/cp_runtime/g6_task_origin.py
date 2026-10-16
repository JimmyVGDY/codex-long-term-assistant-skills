"""中文：为逻辑任务冻结原生人类输入引用，不保存提示正文或自动判定新任务。
English: Freeze native human-input references without storing prompt bodies or deciding task semantics.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from .capability_store import bounded_read, safe_path
from .common import atomic_write_json, parse_iso, read_json, resolve_codex_home, utc_now, verify_record
from .event_v2 import OwnerTokenLock, project_identity_for
from .g6_allowance_authority import _native_header
from .path_identity import same_path
from .routing_contract import _constant, _object, exact, fail, ref

MAX_WINDOW = 2_000_000
MAX_RECORD = 1_048_576
ORIGIN = re.compile(r"TO1-[0-9a-f]{32}")
SOURCE_FIELDS = {"schema_version", "session_ref", "repo_path", "identity", "transcript_path",
                 "transcript_path_ref", "transcript_file_ref", "header_ref", "anchor", "observed_at"}
ORIGIN_FIELDS = {"schema_version", "origin_ref", "source", "session_ref", "repo_path", "identity",
                 "transcript_path", "transcript_path_ref", "transcript_file_ref", "header_ref",
                 "message_ref", "turn_ref", "native_turn_id", "text_ref", "record_ref",
                 "start", "end", "submitted_at", "kind"}
CONTROL = {"继续", "继续执行", "好的", "好", "确认", "同意", "批准", "yes", "ok", "continue"}


def _directory(session: str) -> Path:
    if not isinstance(session, str) or not 0 < len(session) <= 256:
        fail("TASK_SOURCE_SESSION")
    return safe_path(resolve_codex_home() / "cp-assistant/g6-routing/task-origins" / ref(session)[7:])


def _identity(cwd: Path) -> dict:
    fingerprint, project_id = project_identity_for(str(cwd))
    return {"project_id": project_id, "repo_fingerprint": fingerprint}


def observe(data: Mapping[str, Any]) -> dict | None:
    """中文：原生父Hook只绑定来源位置；不创建任务或预算。
    English: A native parent Hook binds the source locator, never a task or budget.
    """
    if data.get("agent_id") or data.get("hook_event_name") not in {"UserPromptSubmit", "PreToolUse"}:
        return None
    session, cwd, transcript = (data.get(key) for key in ("session_id", "cwd", "transcript_path"))
    if not all(isinstance(value, str) and value for value in (session, cwd, transcript)):
        return None
    cwd = safe_path(Path(cwd))
    source = safe_path(Path(transcript))
    header, binding = _native_header(source, session_id=session, cwd=cwd)
    fixed = {"schema_version": "g6-task-native-source/1", "session_ref": ref(session),
             "repo_path": str(cwd), "identity": _identity(cwd), "transcript_path": str(source),
             **binding, "header_ref": ref(header)}
    path = _directory(session) / "source.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=2):
        if path.exists():
            previous = _read_source(session, cwd)
            fixed["identity"] = _identity(Path(previous["repo_path"]))
            # 中文：路径别名必须指向同一实体，其他身份和内容指纹仍需完全一致。
            # English: Path aliases must name the same entity; every other identity and content digest stays exact.
            locations = ("repo_path", "transcript_path")
            if (any(previous[key] != value for key, value in fixed.items() if key not in locations)
                    or any(not same_path(Path(previous[key]), Path(fixed[key])) for key in locations)):
                fail("TASK_SOURCE_REPLACED")
            if data["hook_event_name"] != "UserPromptSubmit":
                return previous
            fixed.update({key: previous[key] for key in locations})
        value = {**fixed, "anchor": source.stat().st_size, "observed_at": utc_now()}
        atomic_write_json(path, value, seal=True)
    return value


def _read_source(session: str, cwd: Path) -> dict:
    path = _directory(session) / "source.json"
    if not path.exists():
        fail("TASK_NATIVE_SOURCE_UNAVAILABLE")
    value = json.loads(bounded_read(path, 16_384), object_pairs_hook=_object, parse_constant=_constant)
    verify_record(value, "native task source")
    value.pop("integrity")
    exact(value, SOURCE_FIELDS, "TASK_SOURCE_FIELDS")
    if (value["schema_version"] != "g6-task-native-source/1" or value["session_ref"] != ref(session)
            or not same_path(Path(value["repo_path"]), cwd)
            or value["identity"] != _identity(Path(value["repo_path"]))
            or type(value["anchor"]) is not int or value["anchor"] < 0):
        fail("TASK_SOURCE_IDENTITY")
    header, binding = _native_header(Path(value["transcript_path"]), session_id=session, cwd=cwd)
    if ref(header) != value["header_ref"] or any(value[key] != item for key, item in binding.items()):
        fail("TASK_SOURCE_REPLACED")
    return value


def _human(record: Mapping[str, Any]) -> tuple[str, str, str] | None:
    payload = record.get("payload", {})
    if (record.get("type") != "response_item" or not isinstance(payload, dict)
            or payload.get("type") != "message" or payload.get("role") != "user"
            or not isinstance(payload.get("id"), str) or not payload["id"]):
        return None
    meta, content = payload.get("internal_chat_message_metadata_passthrough"), payload.get("content")
    if not isinstance(meta, dict) or not isinstance(content, list) or not 0 < len(content) <= 16:
        return None
    kinds = meta.get("content_item_kinds")
    if (not isinstance(kinds, list) or not kinds or len(kinds) > 16
            or any(kind not in {"user.text", "user.image"} for kind in kinds)
            or "user.text" not in kinds or not isinstance(meta.get("turn_id"), str) or not meta["turn_id"]):
        return None
    texts = []
    for item in content:
        if not isinstance(item, dict) or item.get("type") not in {"input_text", "input_image"}:
            return None
        if item["type"] == "input_text":
            if not isinstance(item.get("text"), str):
                return None
            texts.append(item["text"])
    text = "\n".join(texts)
    if not text.strip() or len(text.encode("utf-8")) > 131_072:
        return None
    return payload["id"], meta["turn_id"], text


def _kind(text: str) -> str:
    if text.strip().startswith("<send_user_message_question_reply>"):
        return "control_reply"
    if text.strip().lower().rstrip("。.!") in CONTROL:
        return "continuation_hint"
    return "goal_candidate"


def prepare(session: str, cwd: Path) -> dict:
    """中文：读取提交位置附近的有界完整行，冻结引用供主Agent作语义判断。
    English: Freeze bounded complete records near submission for the coordinator's semantic decision.
    """
    cwd = safe_path(cwd)
    source = _read_source(session, cwd)
    path = Path(source["transcript_path"])
    origins = []
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if opened.st_size < source["anchor"]:
            fail("TASK_SOURCE_TRUNCATED")
        end = min(opened.st_size, source["anchor"] + 262_144)
        start = max(0, end - MAX_WINDOW)
        stream.seek(start)
        raw = stream.read(end - start)
        after = os.fstat(stream.fileno())
    if ((opened.st_dev, opened.st_ino) != (after.st_dev, after.st_ino)
            or after.st_size < opened.st_size
            or ref({"device": opened.st_dev, "inode": opened.st_ino}) != source["transcript_file_ref"]):
        fail("TASK_SOURCE_CHANGED")
    if start:
        boundary = raw.find(b"\n")
        drop = len(raw) if boundary < 0 else boundary + 1
        start, raw = start + drop, raw[drop:]
    offset = start
    for line in raw.splitlines(keepends=True):
        here, offset = offset, offset + len(line)
        if not line.endswith(b"\n") or len(line) > MAX_RECORD:
            continue
        record = json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
        human = _human(record)
        if human is None:
            continue
        message_id, turn, text = human
        stamp = record.get("timestamp")
        if not isinstance(stamp, str):
            continue
        parse_iso(stamp)
        message_ref = ref([ref(session), message_id])
        origin_ref = "TO1-" + message_ref[7:39]
        value = {"schema_version": "g6-native-task-origin/1", "origin_ref": origin_ref,
                 "source": "native-parent-message", "session_ref": ref(session),
                 "repo_path": source["repo_path"], "identity": source["identity"], "message_ref": message_ref,
                 "turn_ref": ref(turn), "native_turn_id": turn, "text_ref": ref(text),
                 "record_ref": "sha256:" + hashlib.sha256(line).hexdigest(), "start": here, "end": offset,
                 "submitted_at": stamp, "kind": _kind(text),
                 **{key: source[key] for key in ("transcript_path", "transcript_path_ref",
                                               "transcript_file_ref", "header_ref")}}
        target = _directory(session) / (origin_ref + ".json")
        with OwnerTokenLock(target, timeout=2):
            if target.exists():
                old = json.loads(bounded_read(target, 16_384), object_pairs_hook=_object, parse_constant=_constant)
                verify_record(old, "native task origin")
                old.pop("integrity")
                if old != value:
                    fail("TASK_ORIGIN_CONFLICT")
            else:
                atomic_write_json(target, value, seal=True)
        origins.append({"origin_ref": origin_ref, "turn_ref": value["turn_ref"],
                        "submitted_at": stamp, "kind": value["kind"], "text_ref": value["text_ref"]})
    return {"schema_version": "g6-task-origin-view/1", "origins": origins[-16:],
            "latest_goal_candidate": next((item for item in reversed(origins)
                                           if item["kind"] == "goal_candidate"), None),
            "bytes_read": len(raw), "execution_authorization": "NONE"}


def read_origin(session: str, cwd: Path, origin_ref: str) -> dict:
    """中文：重读原始片段和身份，缓存或调用方声明不能替代来源。
    English: Recheck source bytes and identity; cached or caller-supplied labels are insufficient.
    """
    if not isinstance(origin_ref, str) or ORIGIN.fullmatch(origin_ref) is None:
        fail("TASK_ORIGIN_REF")
    path = _directory(session) / (origin_ref + ".json")
    value = json.loads(bounded_read(path, 16_384), object_pairs_hook=_object, parse_constant=_constant)
    verify_record(value, "native task origin")
    value.pop("integrity")
    exact(value, ORIGIN_FIELDS, "TASK_ORIGIN_FIELDS")
    if (value["schema_version"] != "g6-native-task-origin/1" or value["origin_ref"] != origin_ref
            or value["session_ref"] != ref(session) or not same_path(Path(value["repo_path"]), cwd)
            or value["identity"] != _identity(Path(value["repo_path"]))
            or value["kind"] not in {"goal_candidate", "control_reply", "continuation_hint"}
            or type(value["start"]) is not int or type(value["end"]) is not int
            or value["start"] < 0 or not 0 < value["end"] - value["start"] <= MAX_RECORD):
        fail("TASK_ORIGIN_IDENTITY")
    header, binding = _native_header(Path(value["transcript_path"]), session_id=session, cwd=cwd)
    if ref(header) != value["header_ref"] or any(value[key] != item for key, item in binding.items()):
        fail("TASK_SOURCE_REPLACED")
    with Path(value["transcript_path"]).open("rb") as stream:
        opened = os.fstat(stream.fileno())
        stream.seek(value["start"])
        raw = stream.read(value["end"] - value["start"])
        if ref({"device": opened.st_dev, "inode": opened.st_ino}) != value["transcript_file_ref"]:
            fail("TASK_SOURCE_REPLACED")
    if "sha256:" + hashlib.sha256(raw).hexdigest() != value["record_ref"]:
        fail("TASK_ORIGIN_CHANGED")
    record = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    human = _human(record)
    if human is None:
        fail("TASK_ORIGIN_NOT_HUMAN")
    message_id, turn, text = human
    if (ref([ref(session), message_id]) != value["message_ref"] or ref(turn) != value["turn_ref"]
            or turn != value["native_turn_id"] or ref(text) != value["text_ref"]
            or _kind(text) != value["kind"] or record.get("timestamp") != value["submitted_at"]):
        fail("TASK_ORIGIN_CHANGED")
    return value
