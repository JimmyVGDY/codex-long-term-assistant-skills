"""中文：采集派发前可用组合。账户目录和子代理工具证据分开。
English: Observe pre-dispatch tuples. The provider catalog and the child tool surface are independent sources.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import g6_catalog as catalogs
from .capability_gate import _read, _write, worktree_key
from .capability_store import bounded_read, safe_path
from .common import parse_iso, resolve_codex_home, utc_now
from .event_v2 import OwnerTokenLock
from .g6_route_settings import _binding
from .routing_contract import fail, ref
from .path_identity import same_path

TTL = timedelta(minutes=5)
MODEL = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}\Z")
WIRE_LIMIT = 1_048_576


def _component(*, verify_binary: bool = False) -> Path:
    home = resolve_codex_home()
    native = home / "plugins/.plugin-appserver" / ("codex.exe" if os.name == "nt" else "codex")
    declared = os.environ.get("CP_ASSISTANT_DESKTOP_COMPONENT", "").strip()
    if declared and not same_path(Path(declared), native):
        # 中文：显式指定的组件必须与受管安装的实物绑定匹配。
        # English: An override is authoritative only when the actual managed installation recorded this executable.
        state = json.loads(bounded_read(safe_path(home / "cp-assistant-v6-state.json"), 262144))
        binding = state["compatibility_snapshot"]["host_binding"]
        installed = safe_path(Path(binding["executable_path"]))
        if not same_path(Path(declared), installed):
            fail("CAPABILITY_COMPONENT_BINDING")
        native = installed
        if verify_binary:
            with native.open("rb") as stream:
                hasher = hashlib.sha256()
                for block in iter(lambda: stream.read(1_048_576), b""):
                    hasher.update(block)
            if hasher.hexdigest() != binding.get("executable_sha256"):
                fail("CAPABILITY_COMPONENT_CHANGED")
    return safe_path(native)


def _stamp(component: Path) -> list:
    s = component.stat()
    return [str(component), s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns]


def _cache(cwd: Path, session: str) -> Path:
    return safe_path(
        resolve_codex_home()
        / "cp-assistant/g6-routing/capability-snapshots"
        / worktree_key(cwd)
        / (ref(session)[7:] + ".json")
    )


def _provider(component: Path, cwd: Path) -> tuple[set[tuple[str, str]], bool]:
    """中文：有界读取本地协议和分页，仅读模型目录。 English: Bound stdio, pagination, memory and lifetime."""
    deadline = time.monotonic() + 5
    process = subprocess.Popen(
        [str(component), "app-server"],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    replies: queue.Queue = queue.Queue(maxsize=16)

    def drain():
        try:
            while True:
                line = process.stdout.readline(WIRE_LIMIT + 1)
                if not line or len(line) > WIRE_LIMIT:
                    break
                value = json.loads(line)
                if isinstance(value, dict) and "id" in value:
                    replies.put_nowait(value)
        except (OSError, ValueError, queue.Full):
            pass
        finally:
            try:
                replies.put_nowait(None)
            except queue.Full:
                pass

    thread = threading.Thread(target=drain, daemon=True)
    thread.start()

    def send(method, params=None, request_id=None):
        msg = {"method": method}
        if params is not None:
            msg["params"] = params
        if request_id is not None:
            msg["id"] = request_id
        process.stdin.write(json.dumps(msg).encode() + b"\n")
        process.stdin.flush()
        if request_id is None:
            return None
        try:
            reply = replies.get(timeout=max(0, deadline - time.monotonic()))
        except queue.Empty as exc:
            raise TimeoutError("CAPABILITY_COMPONENT_TIMEOUT") from exc
        if (
            not isinstance(reply, dict)
            or reply.get("id") != request_id
            or not isinstance(reply.get("result"), dict)
        ):
            fail("CAPABILITY_COMPONENT_REPLY")
        return reply["result"]

    pairs: set[tuple[str, str]] = set()
    try:
        send("initialize", {"clientInfo": {"name": "cp-assistant-capabilities", "version": "1.0"}}, 1)
        send("initialized")
        cursor = None
        cursors = set()
        for page in range(8):
            params = {"limit": 64, "includeHidden": False}
            if cursor is not None:
                params["cursor"] = cursor
            result = send("model/list", params, page + 2)
            items = result.get("data")
            if not isinstance(items, list) or len(items) > 128 or "nextCursor" not in result:
                fail("CAPABILITY_CATALOG_ROWS")
            for item in items:
                if not isinstance(item, dict) or type(item.get("hidden", False)) is not bool:
                    fail("CAPABILITY_CATALOG_ROW")
                if item.get("hidden"):
                    continue
                model, efforts = item.get("model"), item.get("supportedReasoningEfforts")
                if (
                    not isinstance(model, str)
                    or not MODEL.fullmatch(model)
                    or not isinstance(efforts, list)
                    or len(efforts) > 24
                ):
                    fail("CAPABILITY_CATALOG_ROW")
                for entry in efforts:
                    if not isinstance(entry, dict) or not isinstance(entry.get("reasoningEffort"), str):
                        fail("CAPABILITY_EFFORT")
                    if entry["reasoningEffort"] in catalogs.EFFORTS:
                        pairs.add((model, entry["reasoningEffort"]))
            cursor = result["nextCursor"]
            if cursor is None:
                return pairs, True
            if not isinstance(cursor, str) or not 1 <= len(cursor) <= 2048 or cursor in cursors:
                return pairs, False
            cursors.add(cursor)
        return pairs, False
    finally:
        try:
            process.stdin.close()
            process.wait(timeout=0.5)
        except (OSError, subprocess.TimeoutExpired):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=2)
        thread.join(timeout=1)
        process.stdout.close()


def refresh(cwd: Path, session: str) -> dict:
    component = _component(verify_binary=True)
    path = _cache(cwd, session)
    with OwnerTokenLock(path, timeout=2):
        stamp = _stamp(component)
        pairs, complete = _provider(component, cwd)
        if _stamp(component) != stamp:
            fail("CAPABILITY_COMPONENT_CHANGED")
        value = {
            "schema_version": "desktop-provider-snapshot/1",
            "stamp": stamp,
            "project": _binding(cwd),
            "session": ref(session),
            "cwd": str(cwd.resolve()),
            "collected_at": utc_now(),
            "complete": complete,
            "pairs": [list(p) for p in sorted(pairs)],
        }
        _write(path, value, 262144)
    from .g6_flexible_policy import PROFILES, profile_spec
    from .g6_route_settings import selected_digest

    digest = selected_digest(cwd, value["project"])
    selected = catalogs.for_digest(digest)
    names = selected.profiles if selected else PROFILES
    known = {(profile_spec(name, digest)["model"], profile_spec(name, digest)["effort"]) for name in names}
    unmapped = sorted(pairs - known)
    return {
        "provider_status": "COMPLETE" if complete else "PARTIAL",
        "tuple_count": len(pairs),
        "comparison_policy": catalogs.policy_id(digest),
        "mapped_tuple_count": len(pairs & known),
        "unmapped_tuple_count": len(unmapped),
        "unmapped_for_this_policy": [list(pair) for pair in unmapped[:64]],
        "source_ref": ref(value),
        "execution_authorization": "NONE",
    }


def _fresh(stamp: str, now: datetime) -> bool:
    return timedelta(0) <= now - parse_iso(stamp) < TTL


def _session_tools(cwd: Path, session: str):
    """中文：只接受绑定父会话的内置工具结构化声明。
    English: Read only a trusted, parent-bound machine declaration for the builtin tool.
    Client-defined dynamicTools and free text are never a source of native authority.
    """
    from .g6_task_origin import _read_binding, _binding_header

    try:
        anchor = _read_binding(session, cwd, locator=True)
        header, _ = _binding_header(anchor, session, cwd)
        if ref(header) != anchor["header_ref"]:
            return None
        declarations = header["payload"].get("builtin_tools")
        if not isinstance(declarations, list) or len(declarations) > 256:
            return None
        found = [
            t
            for t in declarations
            if isinstance(t, dict)
            and t.get("namespace") == "collaboration"
            and t.get("name") == "spawn_agent"
        ]
        if len(found) != 1:
            return None
        # 中文：只采信精确组合，两个独立枚举不能证明其笛卡尔积。
        # English: Consume only an exact tuple list. Independent model/effort enums do not prove their cross product.
        tuples = found[0].get("model_effort_pairs")
        if not isinstance(tuples, list) or len(tuples) > 256:
            return None
        pairs = set()
        for row in tuples:
            if (
                not isinstance(row, dict)
                or set(row) != {"model", "reasoning_effort"}
                or not isinstance(row["model"], str)
                or not MODEL.fullmatch(row["model"])
            ):
                return None
            if row["reasoning_effort"] in catalogs.EFFORTS:
                pairs.add((row["model"], row["reasoning_effort"]))
        return pairs
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        return None


def project(catalog, provider, provider_complete, native, accepted, *, latency=None):
    """中文：保留各完整来源的明确排除。 English: Missing sources cannot erase known exclusions."""
    from .g6_flexible_policy import bounded_profile

    complete = provider_complete and native is not None
    eligible = []
    for ident, row in catalog.profiles.items():
        pair = (row["model"], row["effort"])
        if (
            row["stage"] == "shadow"
            or provider_complete
            and pair not in provider
            or native is not None
            and pair not in native
        ):
            continue
        provider_positive = provider is not None and pair in provider
        native_positive = native is not None and pair in native or pair in accepted
        if bounded_profile(ident, catalog) or provider_positive and native_positive:
            eligible.append(ident)
    coverage = (
        "COMPLETE"
        if complete
        else "PARTIAL"
        if provider is not None or native is not None or accepted
        else "UNKNOWN"
    )
    return {
        "schema_version": "g6-desktop-capability/2",
        "coverage": coverage,
        "available_profiles": sorted(eligible),
        "latency_ms": dict(latency or {}),
    }


def observe(
    cwd: Path,
    session: str,
    digest: str,
    *,
    state: dict | None = None,
    warm: bool = False,
    intent: dict | None = None,
    role: str | None = None,
    kind: str | None = None,
) -> dict:
    catalog = catalogs.for_digest(digest)
    if not catalog:
        return {"schema_version": "g6-desktop-capability/1", "available_profiles": None, "source_ref": None}
    now = datetime.now(timezone.utc)
    path = _cache(cwd, session)
    provider, complete, witness = None, False, None
    try:
        if warm and (not path.is_file() or now.timestamp() - path.stat().st_mtime >= TTL.total_seconds()):
            refresh(cwd, session)
        if path.is_file():
            record = _read(path, 262144)
            if (
                record["schema_version"] == "desktop-provider-snapshot/1"
                and record["project"] == _binding(cwd)
                and record["session"] == ref(session)
                and same_path(Path(record["cwd"]), cwd)
                and record["stamp"] == _stamp(_component())
                and _fresh(record["collected_at"], now)
            ):
                provider = {tuple(p) for p in record["pairs"]}
                complete = record["complete"] is True
                witness = ref(record)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.SubprocessError):
        pass
    native = _session_tools(cwd, session)
    accepted = set()
    if (
        state
        and state["root"]["host_session_ref"] == ref(session)
        and same_path(Path(state["root"]["repo_path"]), cwd)
    ):
        for pid, receipt in state["receipts"].items():
            permit = state["permits"][pid]
            if receipt["disposition"] == "created" and _fresh(permit["prepared_at"], now):
                accepted.add((permit["model"], permit["reasoning_effort"]))
    timing = {}
    if role and kind:
        from .g6_routing_study import comparable_timing

        try:
            timing = comparable_timing(
                cwd, state["root"]["identity"] if state else _binding(cwd), digest, role, kind
            )
        except (OSError, RuntimeError, ValueError, KeyError, TypeError):
            pass
    result = project(catalog, provider, complete, native, accepted, latency=timing)
    # 中文：用户明确选择的试点只授权一次尝试，不能充当宿主能力证明。
    # English: An explicit, native-turn-bound pilot can test one named tuple. It is not a declaration of tool support.
    if intent and intent.get("pilot_once") and intent.get("choice"):
        pair = tuple(intent["choice"])
        requested = catalog.lookup(*pair)
        if (
            requested
            and catalog.profiles[requested]["stage"] == "pilot"
            and provider is not None
            and pair in provider
            and (native is None or pair in native)
            and requested not in result["available_profiles"]
        ):
            result["available_profiles"] = sorted([*result["available_profiles"], requested])
        if requested in result["available_profiles"]:
            result["pilot_ref"] = ref([intent["source_ref"], digest, requested, ref(session)])
    result["source_ref"] = ref(
        [
            str(cwd.resolve()),
            ref(session),
            digest,
            witness,
            sorted(native) if native is not None else None,
            sorted(accepted),
            result,
        ]
    )
    return result
