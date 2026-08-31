"""中文：以诊断旁证读取隐私有界的 Codex 宿主事实；宿主会话文件属于不可信输入，关联检查不能把记录提升为授权或模型门禁证明。

English: Read privacy-bounded Codex host facts as diagnostic-only evidence. Host session files are untrusted inputs; correlation never promotes records into authorization or model-gate proof.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

MAX_HOST_LOG_BYTES = 64 * 1024 * 1024
KNOWN_MODELS = {"gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.5",
                "gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex-spark"}
KNOWN_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}


class HostFactError(ValueError):
    pass


def _is_reparse(stat_result: os.stat_result) -> bool:
    return stat.S_ISLNK(stat_result.st_mode) or bool(getattr(stat_result, "st_file_attributes", 0) & 0x400)


def _stable_read(path: Path) -> Tuple[bytes, os.stat_result]:
    try:
        before = path.lstat()
    except OSError as exc:
        raise HostFactError("host session evidence could not be inspected") from exc
    if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
        raise HostFactError("host session evidence must be a regular non-reparse file")
    if before.st_size > MAX_HOST_LOG_BYTES:
        raise HostFactError("host session evidence exceeds 64 MiB")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    fd = os.open(str(path), flags)
    try:
        opened = os.fstat(fd)
        if _is_reparse(opened) or not stat.S_ISREG(opened.st_mode):
            raise HostFactError("host session evidence changed identity")
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != \
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns):
            raise HostFactError("host session evidence changed before read")
        chunks: List[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(1024 * 1024, MAX_HOST_LOG_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_HOST_LOG_BYTES:
                raise HostFactError("host session evidence exceeds 64 MiB")
        after = os.fstat(fd)
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != \
                (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns):
            raise HostFactError("host session evidence changed during read")
        return b"".join(chunks), after
    finally:
        os.close(fd)


def load_host_session_facts(paths: Sequence[Path], parent_session_id: str,
                            paired_turn_ids: Sequence[str]) -> Dict[str, Any]:
    expected_turns = set(paired_turn_ids)
    all_facts: List[Dict[str, str]] = []
    source_hashes: List[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        data, _identity = _stable_read(path)
        source_hashes.append(hashlib.sha256(data).hexdigest())
        try:
            lines = data.decode("utf-8-sig").splitlines()
        except UnicodeDecodeError as exc:
            raise HostFactError("host session evidence is not valid UTF-8") from exc
        session_meta: Mapping[str, Any] | None = None
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HostFactError("host session evidence is not valid JSONL") from exc
            if not isinstance(record, dict) or not isinstance(record.get("payload"), dict):
                continue
            payload = record["payload"]
            if record.get("type") == "session_meta":
                source = payload.get("source") or {}
                subagent = source.get("subagent") if isinstance(source, dict) else {}
                spawn = subagent.get("thread_spawn") if isinstance(subagent, dict) else {}
                if isinstance(spawn, dict) and str(spawn.get("parent_thread_id") or "") == parent_session_id:
                    session_meta = payload
            elif record.get("type") == "turn_context" and session_meta is not None:
                turn_id = str(payload.get("turn_id") or "")
                if turn_id not in expected_turns:
                    continue
                model = str(payload.get("model") or session_meta.get("model") or "")
                effort = str(payload.get("effort") or "").lower()
                role = str(session_meta.get("agent_role") or "")
                if model not in KNOWN_MODELS or (effort and effort not in KNOWN_EFFORTS):
                    raise HostFactError("host session evidence contains an unknown model or effort")
                all_facts.append({"turn_id": turn_id, "model": model,
                                  "reasoning_effort": effort, "agent_role": role})
    if paths and not all_facts:
        raise HostFactError("host session evidence does not contain a correlated subagent turn")
    grouped: Dict[str, set[Tuple[str, str, str]]] = {}
    for fact in all_facts:
        grouped.setdefault(fact["turn_id"], set()).add(
            (fact["model"], fact["reasoning_effort"], fact["agent_role"]))
    if any(len(values) > 1 for values in grouped.values()):
        raise HostFactError("host session evidence contains conflicting facts")
    return {
        "trust_level": "DIAGNOSTIC",
        "facts": all_facts,
        "source_sha256": sorted(source_hashes),
        "source_count": len(paths),
        "correlated_turn_count": len(grouped),
    }
