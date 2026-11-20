"""中文：从原生用户消息取得有来源的选型和任务类别。
English: Direct user choices and task categories, bound to their native turn. No prompt body is stored.
"""

import re
from pathlib import Path

from . import g6_catalog
from .capability_gate import _read, _write
from .capability_store import safe_path
from .common import resolve_codex_home
from .event_v2 import OwnerTokenLock
from .g6_user_choice_v1 import NEGATION
from .g6_route_settings import _binding
from .routing_contract import fail, ref

MODEL = re.compile(
    r"(?:请)?(?:使用|选择|指定|use|choose)\s+([a-z0-9][a-z0-9._-]{0,80})\s+([a-z]+)[。.]?", re.I
)
FIELDS = re.compile(r"model\s*=\s*([a-z0-9][a-z0-9._-]{0,80})\s+reasoning_effort\s*=\s*([a-z]+)", re.I)
KIND = re.compile(r"(?:任务类别|task_kind)\s*=\s*([a-z_]+|定位|提取|机械|普通|跨域裁决)", re.I)
KINDS = {
    "定位": "lookup",
    "提取": "extraction",
    "机械": "mechanical",
    "普通": "ordinary",
    "跨域裁决": "cross_domain_adjudication",
}
SYMBOL = re.compile(
    r"(?:定位符号|查找符号|locate symbol|find symbol)\s+\x60?[A-Za-z_][A-Za-z0-9_.:]{0,100}\x60?[。.]?", re.I
)


def parse(prompt):
    if not isinstance(prompt, str) or len(prompt.encode("utf-8")) > 65536 or NEGATION.search(prompt):
        return None
    lines = prompt.strip().splitlines()
    if not lines:
        return None
    choice, kind, probe = None, None, False
    for index, line in enumerate(lines):
        line = line.strip()
        match = MODEL.fullmatch(line) or FIELDS.fullmatch(line)
        label = KIND.fullmatch(line)
        if match:
            if index > 2 or choice is not None:
                return None
            choice = [match[1].lower(), match[2].lower()]
        elif label:
            if index > 2 or kind is not None:
                return None
            kind = KINDS.get(label[1], label[1].lower())
            if kind not in g6_catalog.KINDS or kind == "unknown":
                return None
        elif index == 0 and len(lines) == 1 and SYMBOL.fullmatch(line):
            kind = "lookup"
        elif line in {"试用所选精确档位一次", "try the selected exact profile once"}:
            if index > 2 or probe:
                return None
            probe = True
        elif index == 0:
            return None
    if choice is None and kind is None:
        return None
    return {"choice": choice, "kind": kind, "pilot_once": bool(probe and choice)}


def _path(session, turn):
    return safe_path(
        resolve_codex_home()
        / "cp-assistant/g6-routing/turn-intent"
        / ref(session)[7:]
        / (ref(turn)[7:] + ".json")
    )


def observe(event):
    if event.get("hook_event_name") != "UserPromptSubmit" or event.get("agent_id"):
        return
    requested = parse(event.get("prompt"))
    if requested is None:
        return
    session, turn, cwd = (event.get(k) for k in ("session_id", "turn_id", "cwd"))
    if not all(isinstance(v, str) and v for v in (session, turn, cwd)):
        return
    from .g6_default_activation import resolve

    active = resolve(session_id=session, cwd=Path(cwd))
    digest = active.get("policy_digest")
    if digest is None or g6_catalog.for_digest(digest) is None:
        return
    from .g6_task_scope import read as read_scope

    bound = read_scope(session)
    task = (bound or {}).get("task_id") or event.get("task_id") or session
    if bound and not bound.get("task_id"):
        from .g6_budget_v1 import read_budget

        task = read_budget(Path(bound["new_ledger_path"]))["root"]["task_id"]
    path = _path(session, turn)
    value = {
        "schema_version": "desktop-user-intent/1",
        "session_ref": ref(session),
        "turn_ref": ref(turn),
        "project": _binding(Path(cwd)),
        "cwd_ref": ref(str(Path(cwd).resolve())),
        "task_id": task,
        "intent": requested,
    }
    with OwnerTokenLock(path, timeout=2):
        if path.exists():
            old = _read(path, 16384)
            old.pop("integrity")
            if old != value:
                fail("CATALOG_TURN_INTENT_CONFLICT")
        else:
            _write(path, value, 16384)


def read(session, turn, cwd, task_id=None):
    if not turn:
        return None
    path = _path(session, turn)
    if not path.exists():
        return None
    value = _read(path, 16384)
    if (
        value["schema_version"] != "desktop-user-intent/1"
        or value["session_ref"] != ref(session)
        or value["turn_ref"] != ref(turn)
        or value["project"] != _binding(cwd)
        or value["cwd_ref"] != ref(str(cwd.resolve()))
    ):
        fail("CATALOG_TURN_INTENT_IDENTITY")
    if task_id is not None and value["task_id"] != task_id:
        fail("CATALOG_TURN_INTENT_TASK_CHANGED")
    return {**value["intent"], "source_ref": ref(value)}


def selected(intent, catalog):
    if not intent or intent["choice"] is None:
        return None
    profile = catalog.lookup(*intent["choice"])
    if profile is None or catalog.profiles[profile]["stage"] == "shadow":
        fail("USER_EXACT_PROFILE_NOT_IN_APPROVED_CATALOG")
    return {"profile_id": profile}
