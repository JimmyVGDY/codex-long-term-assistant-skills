"""中文：只提取绑定子任务的最终回答；English: no model identity or prompt telemetry."""
from __future__ import annotations

import json
import re
import os
import stat
from pathlib import Path

from .path_identity import same_path, path_aliases
from .routing_contract import _object, _constant, fail, ref, identifier
from .routing_context_contract import digest, safe_file

MAX_TRANSCRIPT_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024


def read_bound_transcript(path: Path, *, header_only: bool = False, prefix_bytes: int | None = None) -> tuple[bytes, dict]:
    """中文：绑定规范路径和稳定句柄身份，允许文件追加。完整快照的头部与最终内容来自同一打开句柄；这证明逻辑原生来源，不能防止管理员改写原文件或账本。
    
    English: Bind canonical location and stable handle identity; permit append growth.
    
    Header and final bytes in a full snapshot come from the same open handle.
    This is logical native provenance, not protection against an administrator
    rewriting the original file or the budget itself.
    """
    safe = safe_file(path)
    canonical = min((str(item) for item in path_aliases(safe)), key=lambda value: (len(value), value))
    before = safe.stat()
    with safe.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        identity = (opened.st_dev, opened.st_ino)
        if not stat.S_ISREG(opened.st_mode) or opened.st_ino <= 0 \
                or (before.st_dev, before.st_ino) != identity:
            fail("CONTEXT_V2_TRANSCRIPT_FILE_IDENTITY")
        if prefix_bytes is not None:
            if header_only or type(prefix_bytes)!=int or not 1<=prefix_bytes<=MAX_TRANSCRIPT_BYTES or opened.st_size<prefix_bytes:fail('CONTEXT_V2_TRANSCRIPT_PREFIX_BOUND')
            raw=stream.read(prefix_bytes)
            if len(raw)!=prefix_bytes or not raw.endswith(b'\n'):fail('CONTEXT_V2_TRANSCRIPT_PREFIX_CHANGED')
        elif header_only:
            raw = stream.readline(131073)
            if len(raw) > 131072 or not raw.endswith(b"\n"):
                fail("V5_CHILD_HEADER_BOUND")
        else:
            if opened.st_size > MAX_TRANSCRIPT_BYTES:
                fail("CONTEXT_V2_TRANSCRIPT_BOUND")
            raw = stream.read(opened.st_size)
            if len(raw) != opened.st_size:
                fail("CONTEXT_V2_TRANSCRIPT_CHANGED")
        after = os.fstat(stream.fileno())
        current = safe_file(path).stat()
        if (after.st_dev, after.st_ino) != identity or (current.st_dev, current.st_ino) != identity \
                or after.st_size < opened.st_size:
            fail("CONTEXT_V2_TRANSCRIPT_FILE_IDENTITY")
    return raw, {"transcript_path_ref": ref(os.path.normcase(canonical)),
                 "transcript_file_ref": ref({"device": identity[0], "inode": identity[1]})}


def _completion_matches(full_text, mirrored_text):
    if mirrored_text==full_text:return True
    if not isinstance(mirrored_text,str) or not full_text.startswith(mirrored_text):return False
    suffix=full_text[len(mirrored_text):]
    if len(suffix.encode('utf8'))>262144:return False
    return re.fullmatch(r'<oai-mem-citation>\s*<citation_entries>[^<>]*</citation_entries>\s*<rollout_ids>[^<>]*</rollout_ids>\s*</oai-mem-citation>',suffix) is not None


def extract_final(raw: bytes, *, child_id: str, root_id: str, task_path: str,
                  role: str, repo_path: str) -> tuple[str, dict]:
    """中文：仅在 Hook 验证宿主提供的转录路径后调用。已识别的 SubagentStop 是终态信号；task_complete 可稍后追加，若已存在必须一致，但不能代替业务结论。
    
    English: Called only after the Hook validates the host-supplied transcript path.
    
    A recognized SubagentStop is the terminal signal. task_complete may be
    appended later; if already present it must agree, never supply a verdict.
    """
    if not raw or len(raw) > MAX_TRANSCRIPT_BYTES or not raw.endswith(b"\n"):
        fail("CONTEXT_V2_TRANSCRIPT_BOUND")
    lines = raw.splitlines()
    if len(lines) > 4096 or len(lines[0]) > 131072 or any(len(line) > 2 * 1024 * 1024 for line in lines):
        fail("CONTEXT_V2_TRANSCRIPT_BOUND")
    try:
        events = [json.loads(line, object_pairs_hook=_object, parse_constant=_constant) for line in lines]
        header = events[0]
        meta = header["payload"]
        spawn = meta["source"]["subagent"]["thread_spawn"]
        if header["type"] != "session_meta" or meta["id"] != child_id \
                or spawn["parent_thread_id"] != root_id or spawn["agent_path"] != task_path \
                or spawn["agent_role"] != role or type(spawn["depth"]) is not int or spawn["depth"] != 1 \
                or not same_path(Path(meta["cwd"]), Path(repo_path)):
            fail("CONTEXT_V2_FINAL_IDENTITY")
        turns, finals, completions = [], [], []
        for index, event in enumerate(events[1:], 1):
            payload = event.get("payload", {})
            if event.get("type") == "event_msg" and payload.get("type") == "task_started":
                turns.append((index, identifier(payload.get("turn_id"))))
            if event.get("type") == "response_item" and payload.get("type") == "message" \
                    and payload.get("role") == "assistant" and payload.get("phase") == "final_answer":
                content = payload.get("content")
                if not isinstance(content, list) or len(content) != 1 or content[0].get("type") != "output_text" \
                        or not isinstance(content[0].get("text"), str):
                    fail("CONTEXT_V2_FINAL_SHAPE")
                finals.append((index, content[0]["text"]))
            if event.get("type") == "event_msg" and payload.get("type") == "task_complete":
                completions.append((index, payload))
        if len(turns) != 1 or len(finals) != 1 or turns[0][0] >= finals[0][0] or len(completions) > 1:
            fail("CONTEXT_V2_FINAL_AMBIGUOUS")
        text = finals[0][1]
        if not text or len(text.encode("utf-8")) > MAX_RESPONSE_BYTES:
            fail("CONTEXT_V2_FINAL_SIZE")
        if completions and (completions[0][0] <= finals[0][0]
                            or completions[0][1].get("turn_id") != turns[0][1]
                            or not _completion_matches(text,completions[0][1].get("last_agent_message"))):
            fail("CONTEXT_V2_FINAL_COMPLETION_CONFLICT")
        return text, {"header_ref": ref(header), "turn_ref": ref(turns[0][1]),
                      "response_ref": "sha256:" + digest(text.encode("utf-8"))}
    except (KeyError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("CONTEXT_V2_TRANSCRIPT_SHAPE") from exc
