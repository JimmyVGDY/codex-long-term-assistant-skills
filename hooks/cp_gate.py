#!/usr/bin/env python3
"""中文：文件工具专用的轻量门禁入口。

English: Lightweight gate entry point dedicated to file-tool Hooks.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
INPUT_LIMIT = 2 * 1024 * 1024
WIRE_LIMIT = 16 * 1024
POLICY_LIMIT = 16 * 1024
ROOT = Path(os.environ.get("PLUGIN_ROOT") or Path(__file__).resolve().parents[1])


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate")
        value[key] = item
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _plain_path(path: Path) -> bool:
    absolute = Path(os.path.abspath(path.expanduser()))
    for item in reversed((absolute, *absolute.parents)):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return False
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            return False
    return True


def _fast_neutral(data: dict[str, Any]) -> bool:
    """中文：只对可证明未配置或 disabled 的规范文件事件走快速中性路径。

    English: Fast-neutral only proven unconfigured or disabled canonical file events.
    """
    # 中文：PostToolUse 始终走完整路径；B 许可后策略可能停用或移除，进行中操作仍须收敛。
    # English: PostToolUse always takes the full path so an in-flight B converges after policy changes.
    if (data.get("hook_event_name") != "PreToolUse"
            or data.get("tool_name") != "apply_patch"):
        return False
    configured = os.environ.get("CP_CAPABILITY_GATE_ROOT")
    gate_root = Path(configured) if configured else Path(
        os.environ.get("CODEX_HOME") or (Path.home() / ".codex")
    ) / "capability-gates"
    if not gate_root.is_absolute() or not _plain_path(gate_root):
        return False
    if not gate_root.exists():
        return True
    if not gate_root.is_dir():
        return False
    cwd = Path(str(data.get("cwd") or ""))
    if not cwd.is_absolute() or not cwd.is_dir() or not _plain_path(cwd):
        return False
    try:
        repo = cwd.resolve()
        parents = (repo, *repo.parents)
        for depth, parent in enumerate(parents):
            if depth >= 64:
                return False
            key = hashlib.sha256(os.path.normcase(str(parent.resolve())).encode("utf-8")).hexdigest()
            current = gate_root / (key + ".json")
            previous = gate_root / (key + ".previous.json")
            if not current.exists():
                if previous.exists():
                    return False
                continue
            raw = current.read_bytes()
            if len(raw) > POLICY_LIMIT:
                return False
            record = json.loads(raw, object_pairs_hook=_unique)
            if (not isinstance(record, dict)
                    or set(record) != {"schema_version", "revision", "enabled", "identity", "integrity"}
                    or record.get("schema_version") != 1
                    or type(record.get("revision")) is not int
                    or type(record.get("enabled")) is not bool):
                return False
            identity = record.get("identity")
            expected_identity = {"project_id", "repo_fingerprint", "profile_path", "profile_binding",
                                 "worktree_root", "worktree_id", "index_root"}
            integrity = record.get("integrity")
            unsigned = dict(record)
            unsigned.pop("integrity", None)
            if (not isinstance(identity, dict) or set(identity) != expected_identity
                    or not all(isinstance(item, str) and 0 < len(item) <= 2048
                               for item in identity.values())
                    or Path(identity.get("worktree_root", "")).resolve() != parent.resolve()
                    or identity.get("worktree_id") != key
                    or current.name != hashlib.sha256(
                        os.path.normcase(str(parent.resolve())).encode("utf-8")
                    ).hexdigest() + ".json"
                    or not isinstance(integrity, dict)
                    or integrity.get("algorithm") != "sha256-canonical-json"
                    or integrity.get("sha256") != hashlib.sha256(_canonical(unsigned)).hexdigest()):
                return False
            return record["enabled"] is False
    except (OSError, ValueError, TypeError, UnicodeError):
        return False
    return True


def _failure(event: str, reason: str) -> dict[str, Any]:
    message = "Capability gate: " + reason + ". No current process PASS was verified."
    if event == "PreToolUse":
        return {"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny",
                                        "permissionDecisionReason": message}}
    if event == "PostToolUse":
        return {"decision": "block", "reason": message,
                "hookSpecificOutput": {"hookEventName": event,
                                        "additionalContext": "Operation outcome is unknown."}}
    return {}


def main() -> int:
    expected = sys.argv[1] if len(sys.argv) > 1 else "Stop"
    event = expected
    try:
        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            raise ValueError("GATE_INPUT_LIMIT")
        data = json.loads(raw, object_pairs_hook=_unique)
        if not isinstance(data, dict):
            raise ValueError("GATE_HOST_IDENTITY")
        event = str(data.get("hook_event_name") or expected)
        if _fast_neutral(data):
            print("{}", flush=True)
            return 0
        sys.path.insert(0, str(ROOT / "runtime"))
        from cp_runtime.capability_gate_hook import WIRE_LIMIT as runtime_wire_limit, handle
        result = handle(ROOT, data)
        response = result["response"]
        if result["observe"] and event not in {"PreToolUse", "PostToolUse", "Interrupt"}:
            # 中文：文件工具热路径不加载完整生命周期观察器。
            # English: The file-tool hot path does not import the full lifecycle observer.
            import cp_hook as observer
            observer._observe(data, allow_feedback=result["allow_feedback"])
        if runtime_wire_limit != WIRE_LIMIT:
            raise ValueError("GATE_WIRE_CONTRACT")
    except Exception as exc:
        reason = str(exc) if str(exc) in {"GATE_INPUT_LIMIT", "GATE_HOST_IDENTITY"} else "GATE_WORKER_FAILED"
        response = _failure(event, reason)
    output = json.dumps(response, ensure_ascii=True)
    if len(output.encode("utf-8")) > WIRE_LIMIT:
        output = json.dumps(_failure(event, "GATE_OUTPUT_LIMIT"), ensure_ascii=True)
    print(output, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
