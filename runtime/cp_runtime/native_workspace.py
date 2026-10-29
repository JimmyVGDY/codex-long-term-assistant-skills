"""中文：有界核验原生回合目录，证据不授予操作权限。
English: Bounded native turn workspace evidence; this module grants no authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .native_transcript import complete_window, session_header
from .path_identity import same_path
from .routing_contract import _object, _constant, exact, fail, ref, sha

SCHEMA = "native-workspace-proof/1"
MAX_RECORD = 1_048_576
MAX_CONTEXT_WINDOWS = 8
FIELDS = {"schema_version", "session_ref", "repo_path", "turn_id", "start", "end", "record_ref",
          "header_ref", "transcript_path_ref", "transcript_file_ref"}


def _context(raw: bytes, *, turn_id: str, cwd: Path) -> None:
    value = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    if not isinstance(value, dict):
        fail("WORKSPACE_CONTEXT_IDENTITY")
    payload = value.get("payload", {})
    if (value.get("type") != "turn_context" or not isinstance(payload, dict)
            or payload.get("turn_id") != turn_id or not isinstance(payload.get("cwd"), str)
            or not same_path(Path(payload["cwd"]), cwd)):
        fail("WORKSPACE_CONTEXT_IDENTITY")


def from_record(path: Path, raw: bytes, start: int, *, session_id: str, turn_id: str, cwd: Path) -> dict:
    """中文：把已读取的原生目录行绑定到实际文件，不接受正文中的声明。
    English: Bind a native context line to the actual file, never to a message-body assertion.
    """
    if type(start) is not int or start < 0 or not raw.endswith(b"\n") or len(raw) > MAX_RECORD:
        fail("WORKSPACE_PROOF_IDENTITY")
    _context(raw, turn_id=turn_id, cwd=cwd)
    header, binding = session_header(path, session_id=session_id)
    proof = {"schema_version": SCHEMA, "session_ref": ref(session_id), "repo_path": str(cwd),
             "turn_id": turn_id, "start": start, "end": start + len(raw),
             "record_ref": "sha256:" + hashlib.sha256(raw).hexdigest(),
             "header_ref": ref(header), **binding}
    verify(path, proof, session_id=session_id, cwd=cwd)
    return proof


def observe(path: Path, *, session_id: str, turn_id: str, cwd: Path, before_byte: int | None = None) -> dict:
    """中文：只接受精确原生回合，不从消息正文取得目录。
    English: Read only an exact native turn, never a path mentioned in message text.
    """
    if not isinstance(turn_id, str) or not 0 < len(turn_id) <= 256:
        fail("WORKSPACE_TURN_REQUIRED")
    header, binding = session_header(path, session_id=session_id)
    selected, cursor = None, before_byte
    for _ in range(MAX_CONTEXT_WINDOWS):
        raw, window = complete_window(path, before_byte=cursor)
        offset = window["start"]
        for line in raw.splitlines(keepends=True):
            start, offset = offset, offset + len(line)
            if not line.endswith(b"\n") or len(line) > MAX_RECORD:
                continue
            value = json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
            if not isinstance(value, dict):
                fail("WORKSPACE_CONTEXT_IDENTITY")
            payload = value.get("payload", {})
            if value.get("type") != "turn_context" or not isinstance(payload, dict) or payload.get("turn_id") != turn_id:
                continue
            _context(line, turn_id=turn_id, cwd=cwd)
            selected = (start, offset, line)
        if selected is not None:
            break
        cursor = window["start"] if window["start"] < window["scan_end"] else window["scan_start"]
        if cursor <= 0:
            break
    if selected is None:
        fail("WORKSPACE_CONTEXT_UNAVAILABLE")
    start, end, line = selected
    proof = {"schema_version": SCHEMA, "session_ref": ref(session_id), "repo_path": str(cwd),
             "turn_id": turn_id, "start": start, "end": end,
             "record_ref": "sha256:" + hashlib.sha256(line).hexdigest(),
             "header_ref": ref(header), **binding}
    verify(path, proof, session_id=session_id, cwd=cwd)
    return proof


def verify(path: Path, proof: dict, *, session_id: str, cwd: Path) -> tuple[dict, dict]:
    """中文：重读同一原生记录和文件，缓存标签不能代替校验。
    English: Recheck the same native record and file; cached labels are insufficient.
    """
    exact(proof, FIELDS, "WORKSPACE_PROOF_FIELDS")
    if (proof["schema_version"] != SCHEMA or proof["session_ref"] != ref(session_id)
            or not isinstance(proof["repo_path"], str) or not same_path(Path(proof["repo_path"]), cwd)
            or not isinstance(proof["turn_id"], str) or not 0 < len(proof["turn_id"]) <= 256
            or type(proof["start"]) is not int or type(proof["end"]) is not int
            or proof["start"] < 0 or not 0 < proof["end"] - proof["start"] <= MAX_RECORD):
        fail("WORKSPACE_PROOF_IDENTITY")
    for key in ("record_ref", "header_ref", "transcript_path_ref", "transcript_file_ref"):
        sha(proof[key], "WORKSPACE_PROOF_REFERENCE")
    header, binding = session_header(path, session_id=session_id)
    if proof["header_ref"] != ref(header) or any(proof[key] != value for key, value in binding.items()):
        fail("WORKSPACE_SOURCE_REPLACED")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if ref({"device": opened.st_dev, "inode": opened.st_ino}) != binding["transcript_file_ref"]:
            fail("WORKSPACE_SOURCE_REPLACED")
        stream.seek(proof["start"])
        raw = stream.read(proof["end"] - proof["start"])
        current = path.stat()
        if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino) or current.st_size < opened.st_size:
            fail("WORKSPACE_SOURCE_REPLACED")
    if (not raw.endswith(b"\n") or "sha256:" + hashlib.sha256(raw).hexdigest() != proof["record_ref"]):
        fail("WORKSPACE_CONTEXT_CHANGED")
    _context(raw, turn_id=proof["turn_id"], cwd=cwd)
    return header, binding
