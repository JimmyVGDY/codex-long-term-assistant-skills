"""中文：限时的项目或任务恢复偏好；不授予操作权限。
English: Finite, revisioned recovery preferences. Settings never authorize an action.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from .capability_gate import _read, _write, worktree_key
from . import revision_pages as pages
from .capability_store import safe_path
from .common import parse_iso, require_external_state, resolve_codex_home
from .event_v2 import OwnerTokenLock, project_identity_for
from .routing_contract import exact, fail, identity, ref

SCHEMA = "desktop-recovery-preferences/1"
MAX_EVENTS = 256
MAX_BYTES = 512 * 1024
ACTIONS = {"write", "dispatch"}
BOUNDS = {"retry_limit": (0, 2), "backoff_ms": (0, 8000), "wait_ms": (0, 30_000)}


def _clock(value: str) -> datetime:
    moment = parse_iso(value)
    if moment.tzinfo is None:
        fail("PREFERENCE_TIME_ZONE")
    return moment.astimezone(timezone.utc)


def _scope(task: str | None, action: str) -> None:
    if (
        action not in ACTIONS
        or task is not None
        and (
            not isinstance(task, str)
            or not task.strip()
            or len(task) > 160
            or any(ord(ch) < 32 for ch in task)
        )
    ):
        fail("PREFERENCE_SCOPE")


def _values(values: Mapping[str, Any], action: str) -> dict:
    if not isinstance(values, dict) or set(values) - set(BOUNDS) - {"verify_optional_index"}:
        fail("PREFERENCE_FIELDS")
    for k, value in values.items():
        if k == "verify_optional_index":
            if action != "write" or type(value) is not bool:
                fail("PREFERENCE_OPTIONAL_CHECK")
        elif type(value) is not int or not BOUNDS[k][0] <= value <= BOUNDS[k][1]:
            fail("PREFERENCE_VALUE")
    return dict(values)


def location(repo: Path) -> Path:
    root = repo.resolve()
    folder = resolve_codex_home() / "cp-assistant" / "gate-preferences"
    path = folder / (worktree_key(root) + ".json")
    require_external_state(path, root)
    return safe_path(path)


def _active_rows(rows, now):
    current = {}
    for event in rows:
        r = event["request"]
        key = (r["task"], r["action"])
        if r["values"] and _clock(r["expires_at"]) > now:
            current[key] = event
        else:
            current.pop(key, None)
    return list(current.values())


def _layers(page):
    return (page.baseline["layers"] if page.start else []) + page.rows


def _history(path: Path, binding: dict, value=None) -> pages.Page:
    if value is None and not path.exists():
        return pages.Page([])
    value = value if value is not None else _read(path, MAX_BYTES)
    fields = {"schema_version", "binding", "events", "integrity"}
    exact(value, fields | ({"page"} if "page" in value else set()), "PREFERENCE_STORE")
    events = value["events"]
    if (
        value["schema_version"] != SCHEMA
        or value["binding"] != binding
        or not isinstance(events, list)
        or len(events) > MAX_EVENTS
    ):
        fail("PREFERENCE_BINDING")
    page = pages.decode(value, "events")
    previous = None
    if page.start:
        archive = pages.read_previous(path, page.start, page.previous, MAX_BYTES)
        prior = pages.decode(archive, "events")
        if (
            not prior.rows
            or prior.revision != page.start
            or archive["binding"] != binding
            or page.baseline
            != {
                "anchor": prior.rows[-1]["digest"],
                "layers": _active_rows(_layers(prior), _clock(page.boundary)),
            }
        ):
            fail("PREFERENCE_ARCHIVE_BINDING")
        previous = page.baseline["anchor"]
    for revision, event in enumerate(events, page.start):
        exact(event, {"request", "previous", "recorded_at", "digest"}, "PREFERENCE_EVENT")
        request = exact(
            event["request"],
            {"binding", "revision", "task", "action", "values", "expires_at"},
            "PREFERENCE_REQUEST",
        )
        if (
            request["binding"] != binding
            or type(request["revision"]) is not int
            or request["revision"] != revision
            or event["previous"] != previous
            or event["digest"] != ref({k: v for k, v in event.items() if k != "digest"})
        ):
            fail("PREFERENCE_HISTORY")
        _scope(request["task"], request["action"])
        _values(request["values"], request["action"])
        created = _clock(event["recorded_at"])
        if not created < _clock(request["expires_at"]) <= created + timedelta(days=31):
            fail("PREFERENCE_VALIDITY")
        previous = event["digest"]
    return page


def project_binding(repo: Path) -> dict:
    fingerprint, project = project_identity_for(str(repo))
    return {
        "identity": {"project_id": project, "repo_fingerprint": fingerprint},
        "worktree": worktree_key(repo),
    }


def _effective(events: list[dict], task: str | None, action: str, now: datetime) -> dict:
    layers: dict[str | None, dict] = {}
    for entry in events:
        request = entry["request"]
        if (
            request["action"] == action
            and request["task"] in {None, task}
            and _clock(entry["recorded_at"]) <= now
        ):
            layers[request["task"]] = request["values"] if now < _clock(request["expires_at"]) else {}
    return {**layers.get(None, {}), **layers.get(task, {})}


def effective(
    repo: Path, project: Mapping[str, str], task: str | None, action: str, *, at: str | None = None
) -> dict:
    # 中文：未启用偏好的项目沿用原行为，无需写状态或查询 Git。
    # English: Existing operations on projects without preferences should neither write state nor query Git.
    folder = resolve_codex_home() / "cp-assistant" / "gate-preferences"
    if not folder.exists():
        return {}
    path = location(repo)
    if not path.is_file():
        return {}
    binding = {
        "identity": identity({k: project[k] for k in ("project_id", "repo_fingerprint")}),
        "worktree": worktree_key(repo),
    }
    now = _clock(at) if at else datetime.now(timezone.utc)
    page = _history(path, binding)
    while page.start and now < _clock(page.boundary):
        page = _history(path, binding, pages.read_previous(path, page.start, page.previous, MAX_BYTES))
    return _effective(_layers(page), task, action, now)


def write_task(policy, session_id: str, turn_id: str) -> str:
    """中文：只在存在范围偏好且项目匹配时读取任务归属。 English: Resolve only a matching native task."""
    fallback = "turn:" + turn_id
    if not (resolve_codex_home() / "cp-assistant" / "gate-preferences").exists():
        return fallback
    if not location(policy.store.repo_path).is_file():
        return fallback
    from .g6_task_scope import registry

    value = registry(session_id)
    if (
        value
        and Path(value["repo_path"]).resolve() == policy.store.repo_path.resolve()
        and all(
            value["project_identity"][k] == policy.store.identity[k]
            for k in ("project_id", "repo_fingerprint")
        )
    ):
        return value["scopes"][value["active_scope"]]["task_id"]
    return fallback


def manage(
    repo: Path,
    mode: str,
    *,
    action: str,
    task: str | None = None,
    revision: int | None = None,
    values: dict | None = None,
    expires_at: str | None = None,
    confirmation: str | None = None,
) -> dict:
    root = repo.resolve()
    _scope(task, action)
    path = location(root)
    binding = project_binding(root)
    now = datetime.now(timezone.utc)
    page = _history(path, binding)
    before = _effective(_layers(page), task, action, now)
    if mode == "show":
        return {
            "revision": page.revision,
            "binding": binding,
            "task": task,
            "action": action,
            "effective": before,
            "execution_authorization": "NONE",
        }
    if mode not in {"preview", "apply"} or type(revision) is not int or revision < 0 or not expires_at:
        fail("PREFERENCE_PREVIEW_FIELDS")
    request = {
        "binding": binding,
        "revision": revision,
        "task": task,
        "action": action,
        "values": _values(values if values is not None else {}, action),
        "expires_at": expires_at,
    }
    key = ref(request)
    if mode == "apply" and confirmation != key:
        fail("PREFERENCE_CONFIRMATION_CHANGED")
    if mode == "apply":
        with OwnerTokenLock(path, timeout=2):
            page = _history(path, binding)
            prior = (
                pages.old_row(path, page, revision, "events", MAX_BYTES) if revision < page.revision else None
            )
            if prior and prior["request"] == request:
                return {
                    "revision": page.revision,
                    "idempotent": True,
                    "request_ref": key,
                    "execution_authorization": "NONE",
                }
            if revision != page.revision:
                fail("PREFERENCE_REVISION_CHANGED")
            now = datetime.now(timezone.utc)
            if not now < _clock(expires_at) <= now + timedelta(days=31):
                fail("PREFERENCE_EXPIRY")
            active = _active_rows(_layers(page), now)
            if (
                request["values"]
                and len(active) >= MAX_EVENTS
                and not any(a["request"]["task"] == task and a["request"]["action"] == action for a in active)
            ):
                fail("PREFERENCE_ACTIVE_SCOPE_LIMIT")
            if len(page.rows) >= MAX_EVENTS:
                page = pages.roll(
                    path,
                    page,
                    {"anchor": page.rows[-1]["digest"], "layers": active},
                    now.isoformat(),
                    MAX_BYTES,
                )
            if project_binding(root) != binding:
                fail("PREFERENCE_BINDING")
            entry = {
                "request": request,
                "previous": page.rows[-1]["digest"]
                if page.rows
                else page.baseline["anchor"]
                if page.start
                else None,
                "recorded_at": now.isoformat(),
            }
            page.rows.append({**entry, "digest": ref(entry)})
            _write(
                path,
                {"schema_version": SCHEMA, "binding": binding, "events": page.rows, **page.header()},
                MAX_BYTES,
            )
            return {
                "revision": page.revision,
                "idempotent": False,
                "request_ref": key,
                "effective": _effective(_layers(page), task, action, now),
                "execution_authorization": "NONE",
            }
    if revision != page.revision or not now < _clock(expires_at) <= now + timedelta(days=31):
        fail("PREFERENCE_REVISION_OR_EXPIRY")
    after = _effective(
        _layers(page) + [{"request": request, "recorded_at": now.isoformat()}], task, action, now
    )
    return {
        "revision": revision,
        "request_ref": key,
        "before": before,
        "after": after,
        "request": request,
        "next_action": "apply_exact_preview",
        "execution_authorization": "NONE",
    }


def add_commands(sub):
    parser = sub.add_parser("gate-settings")
    parser.add_argument("mode", choices=("show", "preview", "apply"))
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--action", choices=sorted(ACTIONS), required=True)
    parser.add_argument("--task")
    parser.add_argument("--revision", type=int)
    parser.add_argument("--expires-at")
    parser.add_argument("--confirm")
    parser.add_argument("--retry-limit", type=int)
    parser.add_argument("--backoff-ms", type=int)
    parser.add_argument("--wait-ms", type=int)
    parser.add_argument("--verify-optional-index", choices=("yes", "no"))
    parser.add_argument("--revoke", action="store_true")

    def emit(args):
        values = {k: getattr(args, k) for k in BOUNDS if getattr(args, k) is not None}
        if args.verify_optional_index is not None:
            values["verify_optional_index"] = args.verify_optional_index == "yes"
        if args.mode != "show" and bool(values) == args.revoke:
            fail("PREFERENCE_SELECT_VALUES_OR_REVOKE")
        result = manage(
            Path(args.repo_path),
            args.mode,
            action=args.action,
            task=args.task,
            revision=args.revision,
            expires_at=args.expires_at,
            values=values,
            confirmation=args.confirm,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    parser.set_defaults(func=emit)
