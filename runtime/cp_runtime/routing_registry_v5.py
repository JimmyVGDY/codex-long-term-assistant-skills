"""中文：宿主激活的会话登记；English: pending intent becomes active only in a parent Hook."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
from . import budget_v5, routing_registry_v4 as legacy
from .common import atomic_write_json, require_external_state
from .event_v2 import OwnerTokenLock
from .routing_context_v5 import verify_root
from .routing_contract import exact, fail, identifier, read_document, ref

def _root(session, directory=None):
    identifier(session, "V5_HOST_SESSION_REQUIRED")
    return legacy._directory(directory) / ("v5-root-" + ref(session)[7:] + ".json")

def _intent(session, directory=None):
    return _root(session, directory).with_name("v5-intent-" + ref(session)[7:] + ".json")

def _core(value):
    return {key: item for key, item in value.items() if key != "status"}

def _tombstone(state, session, directory=None):
    """中文：热路径复用冻结身份，避免重复 Git；English: derive the exact legacy key without Git."""
    key=ref({"session_ref":ref(session),"repo_fingerprint":state["identity"]["repo_fingerprint"]})
    return legacy._directory(directory)/(key[7:]+".json")

def _read(path, session, directory=None):
    value, _ = read_document(path)
    exact(value, legacy.FIELDS, "V5_BINDING_FIELDS")
    intent, _ = read_document(_intent(session, directory))
    if intent != _core(value) or value["schema_version"] != "desktop-routing-binding/2" \
            or value["session_ref"] != ref(session) or value["status"] not in {"pending", "active", "closed"} \
            or not Path(value["ledger_path"]).is_absolute():
        fail("V5_BINDING_IDENTITY")
    state = budget_v5.read_budget(Path(value["ledger_path"]))
    if value["identity"] != state["identity"] or value["root_binding_ref"] != ref(state["root_binding"]) \
            or value["repo_fingerprint"] != state["identity"]["repo_fingerprint"] \
            or state["root_binding"]["host_session_ref"] != ref(session) \
            or (value["status"] == "closed" and not state["closed"]) \
            or (value["status"] == "active" and not state["root_host_binding"]):
        fail("V5_BINDING_LEDGER_CHANGED")
    tombstone, _ = read_document(_tombstone(state, session, directory))
    if _core(tombstone) != _core(value):
        fail("V5_TOMBSTONE_CONFLICT")
    return value, state

def bind(ledger_path, *, cwd, host_session_id, directory=None):
    state = budget_v5.read_budget(ledger_path)
    verify_root(state, cwd=cwd, host_session_id=host_session_id)
    if state["closed"]:
        fail("V5_BIND_CLOSED_ROOT")
    path = _root(host_session_id, directory)
    require_external_state(path, Path(cwd))
    value = {"schema_version": "desktop-routing-binding/2", "session_ref": ref(host_session_id),
             "repo_fingerprint": state["identity"]["repo_fingerprint"], "identity": state["identity"],
             "ledger_path": str(ledger_path.resolve()), "root_binding_ref": ref(state["root_binding"]),
             "status": "active" if state["root_host_binding"] else "pending"}
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(legacy._session_lock(host_session_id, directory), timeout=2):
        tombstone = _tombstone(state, host_session_id, directory)
        existing = legacy._existing(cwd, host_session_id, directory)
        if existing:
            previous, _ = read_document(existing[0])
            if _core(previous) != _core(value):
                fail("V5_ROOT_ALREADY_BOUND")
        intent = _intent(host_session_id, directory)
        if intent.exists() and read_document(intent)[0] != _core(value):
            fail("V5_ROOT_INTENT_CONFLICT")
        if path.exists():
            old, _ = _read(path, host_session_id, directory)
            if _core(old) != _core(value):
                fail("V5_ROOT_ALREADY_BOUND")
        # 中文：先持久化意图，任一登记写入丢失均不能退回中性模式。
        # English: Persist intent first; a missing registration must not look unbound.
        atomic_write_json(intent, _core(value))
        atomic_write_json(tombstone, value)
        atomic_write_json(path, value)
    return value

def lookup(*, host_session_id, directory=None):
    if not host_session_id:
        return None
    from .research_seed import lookup as seed_lookup
    successor=seed_lookup(host_session_id,directory=directory)
    if successor is not None:return successor
    path = _root(host_session_id, directory)
    if not path.exists():
        if _intent(host_session_id, directory).exists():
            fail("V5_ROOT_BINDING_MISSING")
        return None
    with OwnerTokenLock(legacy._session_lock(host_session_id, directory), timeout=2):
        value, _ = _read(path, host_session_id, directory)
    return Path(value["ledger_path"])

@contextmanager
def admission(ledger_path, *, session, cwd, host_call_id, directory=None):
    """中文：根锁在预算锁之前；English: hold root lock through the atomic budget admission."""
    path = _root(session, directory)
    with OwnerTokenLock(legacy._session_lock(session, directory), timeout=2):
        if not path.exists():
            fail("V5_ACTIVE_REGISTRATION_REQUIRED")
        value, state = _read(path, session, directory)
        if Path(value["ledger_path"]).resolve() != ledger_path.resolve() or state["closed"]:
            fail("V5_ADMISSION_REGISTRATION_MISMATCH")
        verify_root(state, cwd=cwd, host_session_id=session)
        budget_v5.bind_native_root(ledger_path, session_ref=ref(session),
            repo_ref=ref(state["root_binding"]["repo_path"]), host_call_ref=ref(identifier(host_call_id)))
        value["status"] = "active"
        tombstone = _tombstone(state, session, directory)
        atomic_write_json(tombstone, value)
        atomic_write_json(path, value)
        def recheck(locked_state):
            current, _ = read_document(path)
            persisted_intent, _ = read_document(_intent(session, directory))
            prior, _ = read_document(tombstone)
            if current != value or prior != value or persisted_intent != _core(value) \
                    or not locked_state["root_host_binding"] \
                    or locked_state["root_binding"]["host_session_ref"] != ref(session):
                fail("V5_REGISTRATION_CHANGED_DURING_ADMISSION")
        yield recheck

def retire(*, host_session_id, directory=None):
    path = _root(host_session_id, directory)
    with OwnerTokenLock(legacy._session_lock(host_session_id, directory), timeout=2):
        value, state = _read(path, host_session_id, directory)
        if not state["closed"]:
            fail("V5_RETIRE_ACTIVE")
        value["status"] = "closed"
        atomic_write_json(path, value)
        atomic_write_json(_tombstone(state, host_session_id, directory), value)
    return value
