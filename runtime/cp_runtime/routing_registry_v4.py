"""中文：桌面根任务绑定；不依赖子进程修改桌面进程环境。

English: Task-scoped Desktop bindings without mutating the host environment.
Entries are logical workflow state, not OS isolation or authenticated host proof.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import budget_v4
from .common import atomic_write_json, require_external_state, resolve_codex_home
from .event_v2 import OwnerTokenLock, stable_repo_fingerprint
from .routing_context_v4 import verify_root
from .routing_contract import exact, fail, identifier, read_document, ref

FIELDS = {"schema_version", "session_ref", "repo_fingerprint", "identity", "ledger_path",
          "root_binding_ref", "status"}


def _entry(cwd: str, host_session_id: str, directory: Path | None = None) -> Path:
    identifier(host_session_id, "DESKTOP_ROOT_SESSION_REQUIRED")
    if not cwd:
        fail("DESKTOP_ROOT_CWD_REQUIRED")
    repo = Path(cwd).resolve()
    base = directory or Path(os.environ.get("CP_ROUTING_BINDINGS_ROOT") or
                             resolve_codex_home() / "cp-assistant" / "desktop-routing")
    key = ref({"session_ref": ref(host_session_id), "repo_fingerprint": stable_repo_fingerprint(str(repo))})
    return base.resolve() / (key[7:] + ".json")


def _read(path: Path, cwd: str, host_session_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    value, _ = read_document(path)
    exact(value, FIELDS, "DESKTOP_BINDING_FIELDS")
    if value["schema_version"] != "desktop-routing-binding/1" \
            or value["status"] not in {"active", "closed"} \
            or value["session_ref"] != ref(host_session_id) \
            or value["repo_fingerprint"] != stable_repo_fingerprint(cwd) \
            or not isinstance(value["ledger_path"], str) or not Path(value["ledger_path"]).is_absolute():
        fail("DESKTOP_BINDING_IDENTITY")
    state = budget_v4.read_budget(Path(value["ledger_path"]))
    verify_root(state, cwd=cwd, host_session_id=host_session_id)
    if value["identity"] != state["identity"] or value["root_binding_ref"] != ref(state["root_binding"]):
        fail("DESKTOP_BINDING_LEDGER_CHANGED")
    if value["status"] == "closed" and not state["closed"]:
        fail("DESKTOP_BINDING_CLOSED_LEDGER_REPLACED")
    return value, state


def bind(ledger_path: Path, *, cwd: str, host_session_id: str,
         directory: Path | None = None) -> dict[str, Any]:
    state = budget_v4.read_budget(ledger_path)
    verify_root(state, cwd=cwd, host_session_id=host_session_id)
    if state["closed"]:
        fail("DESKTOP_BINDING_LEDGER_CLOSED")
    path = _entry(cwd, host_session_id, directory)
    require_external_state(path, Path(cwd).resolve())
    value = {"schema_version": "desktop-routing-binding/1", "session_ref": ref(host_session_id),
             "repo_fingerprint": state["identity"]["repo_fingerprint"], "identity": state["identity"],
             "ledger_path": str(ledger_path.resolve()), "root_binding_ref": ref(state["root_binding"]),
             "status": "active"}
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=2):
        if path.exists():
            prior, _ = _read(path, cwd, host_session_id)
            if prior != value:
                fail("DESKTOP_ROOT_ALREADY_BOUND")
        else:
            atomic_write_json(path, value)
    return value


def lookup(*, cwd: str, host_session_id: str, directory: Path | None = None) -> Path | None:
    # 中文：宿主身份缺失时不能关联任务，不扫描其他登记。
    # English: Missing host identity cannot identify any task. Never scan other bindings.
    if not cwd or not host_session_id:
        return None
    path = _entry(cwd, host_session_id, directory)
    if not path.exists():
        return None
    require_external_state(path, Path(cwd).resolve())
    value, _ = _read(path, cwd, host_session_id)
    # 中文：墓碑继续指向已关闭账本，防止后续调用退回策略模式或重置预算。
    # English: A tombstone continues to select the closed ledger, so a later request
    # cannot silently fall back to policy-only admission or reset its budget.
    return Path(value["ledger_path"])


def retire(*, cwd: str, host_session_id: str, directory: Path | None = None) -> dict[str, Any]:
    path = _entry(cwd, host_session_id, directory)
    with OwnerTokenLock(path, timeout=2):
        value, state = _read(path, cwd, host_session_id)
        if not state["closed"]:
            fail("DESKTOP_BINDING_ACTIVE_LEDGER")
        value["status"] = "closed"
        atomic_write_json(path, value)
    return value
