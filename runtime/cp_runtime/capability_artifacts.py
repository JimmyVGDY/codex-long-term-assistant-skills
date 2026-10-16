"""中文：原生会话绑定的产物范围与无正文调用索引；不授予宿主权限。
English: Native-session artifact scopes and content-free call bindings, not host authorization.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .atomic_io import native_path
from .capability_gate import POLICY_LIMIT, GatePolicy, _digest, _read, _write
from .capability_store import DENIED_NAMES, DENIED_PARTS, fields, require, safe_path
from .common import parse_iso, resolve_codex_home
from .event_v3 import OwnerTokenLock
from .patch_scope import PathBudget

STATE_LIMIT = 32 * 1024
MAX_ROOTS = 16
MAX_POLICIES = 128
MAX_REQUESTS = 64
REQUEST = re.compile(r"AR1-[0-9a-f]{16}-[0-9a-f]{32}")


def gate_root() -> Path:
    configured = os.environ.get("CP_CAPABILITY_GATE_ROOT")
    root = Path(configured) if configured else resolve_codex_home() / "capability-gates"
    require(root.is_absolute(), "GATE_ROOT_INVALID")
    return safe_path(root)


def _ref(*values: str) -> str:
    require(all(isinstance(v, str) and 0 < len(v) <= 256 and "\x00" not in v for v in values),
            "OP_INVALID_ID")
    return _digest(list(values))


def _session_path(policy: GatePolicy, session: str) -> Path:
    return safe_path(policy.root / "native-sessions" / _ref(session) /
                     (policy.store.identity["worktree_id"] + ".json"))


def _session(policy: GatePolicy, session: str) -> dict:
    record = _read(_session_path(policy, session), STATE_LIMIT)
    fields(record, {"schema_version", "session_ref", "identity", "roots", "integrity"})
    require(record["schema_version"] == 1 and record["session_ref"] == _ref(session)
            and record["identity"] == policy.store.identity, "ARTIFACT_IDENTITY_MISMATCH")
    require(isinstance(record["roots"], list) and len(record["roots"]) <= MAX_ROOTS,
            "ARTIFACT_SCOPE_INVALID")
    seen = set()
    for row in record["roots"]:
        fields(row, {"path", "file_id", "expires_at", "request_ref"})
        require(isinstance(row["path"], str) and Path(row["path"]).is_absolute()
                and row["path"] not in seen, "ARTIFACT_SCOPE_INVALID")
        require(isinstance(row["file_id"], list) and len(row["file_id"]) == 2
                and all(type(v) is int and v >= 0 for v in row["file_id"]), "ARTIFACT_SCOPE_INVALID")
        require(isinstance(row["request_ref"], str) and REQUEST.fullmatch(row["request_ref"]),
                "ARTIFACT_REQUEST_INVALID")
        parse_iso(row["expires_at"])
        seen.add(row["path"])
    return record


def observe_native_session(policy: GatePolicy, session: str) -> None:
    """中文：只有原生Hook调用该入口；管理命令不能创建起点。
    English: Only the native Hook creates this origin; management commands cannot create it.
    """
    path = _session_path(policy, session)
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path):
        if native_path(path).exists():
            _session(policy, session)
        else:
            _write(path, {"schema_version": 1, "session_ref": _ref(session),
                         "identity": policy.store.identity, "roots": []}, STATE_LIMIT)


def _overlap(left: Path, right: Path) -> bool:
    return left.is_relative_to(right) or right.is_relative_to(left)


def _protected(policy: GatePolicy, plugin_root: Path, budget: PathBudget) -> list[Path]:
    controls = [safe_path(plugin_root), policy.root, policy.store.profile_path.parent,
                policy.store.root, policy.store.repo_path, Path.home() / ".agents"]
    count = 0
    for total, item in enumerate(native_path(policy.root).iterdir(), 1):
        require(total <= MAX_POLICIES + 16, "PATH_LOOKUP_LIMIT")
        budget.stat(policy.root)
        if not re.fullmatch(r"[0-9a-f]{64}(?:\.previous)?\.json", item.name):
            continue
        count += 1
        require(count <= MAX_POLICIES, "PATH_LOOKUP_LIMIT")
        # 中文：所有已登记项目的控制状态都受保护，包括停用策略。
        # English: Protect control state for every registered project, including disabled policies.
        path = budget.resolve(str(policy.root / item.name), policy.root)
        record = _read(path, POLICY_LIMIT)
        fields(record, {"schema_version", "revision", "enabled", "identity", "integrity"})
        identity = record["identity"]
        fields(identity, {"project_id", "repo_fingerprint", "profile_path", "profile_binding",
                          "worktree_root", "worktree_id", "index_root"})
        require(record["schema_version"] == 1 and type(record["enabled"]) is bool
                and all(isinstance(v, str) and v for v in identity.values()), "GATE_SCHEMA")
        require(item.name.split(".")[0] == identity["worktree_id"], "GATE_IDENTITY_MISMATCH")
        for key in ("worktree_root", "index_root", "profile_path"):
            require(Path(identity[key]).is_absolute(), "GATE_SCHEMA")
            # 中文：历史登记别名不能阻断无关产物；别名与实际控制范围同时保护。
            # English: Historical aliases must not block unrelated artifacts; protect both lexical and actual controls.
            for value in budget.control_path(identity[key], policy.root):
                controls.append(value.parent if key == "profile_path" else value)
    return controls


def _artifact_path(path: Path, budget: PathBudget) -> None:
    lower = [part.lower() for part in path.parts]
    require(not any(part in DENIED_PARTS or part.startswith(".env") for part in lower)
            and path.name.lower() not in DENIED_NAMES
            and path.suffix.lower() not in {".pem", ".key", ".p12", ".pfx"}, "SENSITIVE_PATH")
    home = safe_path(resolve_codex_home())
    if path.is_relative_to(home):
        parts = path.relative_to(home).parts
        require(len(parts) >= 2 and parts[0] == "visualizations", "CONTROL_PATH_CONFLICT")
    require(path != Path.home() and path != Path(path.anchor), "ARTIFACT_ROOT_TOO_BROAD")
    # 中文：已有普通文件不是目录；POSIX 的 file/.git 会抛出 ENOTDIR。
    # English: An existing regular file is not a directory; file/.git raises ENOTDIR on POSIX.
    node = budget.stat(path)
    ancestors = path.parents if node is not None and stat.S_ISREG(node.st_mode) else (path, *path.parents)
    for ancestor in ancestors:
        # 中文：产物目录不是另一个源码仓库；已有Git边界也不能被登记。
        # English: An artifact root cannot enter another source repository, even without an opt-in policy.
        require(budget.stat(ancestor / ".git") is None, "CROSS_REPO_PATH_CONFLICT")


def _request_path(policy: GatePolicy, request_ref: str) -> Path:
    require(isinstance(request_ref, str) and REQUEST.fullmatch(request_ref),
            "ARTIFACT_REQUEST_INVALID")
    return safe_path(policy.root / "artifact-requests" / policy.store.identity["worktree_id"]
                     / request_ref.split("-")[1] / (request_ref + ".json"))


def _request(policy: GatePolicy, request_ref: str) -> dict:
    path = _request_path(policy, request_ref)
    require(native_path(path).is_file(), "ARTIFACT_NATIVE_ORIGIN_REQUIRED")
    value = _read(path, STATE_LIMIT)
    fields(value, {"schema_version", "request_ref", "identity", "session_id", "turn_id",
                   "tool_use_id", "root", "file_id", "command_sha256", "expires_at",
                   "lease_expires_at", "state", "integrity"})
    expected = "AR1-" + _ref(value["session_id"], value["turn_id"])[:16] + "-" + _ref(
        value["session_id"], value["turn_id"], value["tool_use_id"])[:32]
    require(value["schema_version"] == 1 and value["request_ref"] == request_ref == expected
            and value["identity"] == policy.store.identity, "ARTIFACT_IDENTITY_MISMATCH")
    require(value["state"] in {"PENDING", "REGISTERED", "REVOKED"}
            and isinstance(value["root"], str) and Path(value["root"]).is_absolute()
            and isinstance(value["file_id"], list) and len(value["file_id"]) == 2
            and all(type(v) is int and v >= 0 for v in value["file_id"]),
            "ARTIFACT_REQUEST_INVALID")
    require(isinstance(value["command_sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", value["command_sha256"]), "ARTIFACT_REQUEST_INVALID")
    parse_iso(value["expires_at"])
    parse_iso(value["lease_expires_at"])
    return value


def _root_row(request: dict) -> dict:
    return {"path": request["root"], "file_id": request["file_id"],
            "expires_at": request["lease_expires_at"], "request_ref": request["request_ref"]}


def _candidate_root(policy: GatePolicy, plugin_root: Path, targets: list[Path],
                    budget: PathBudget) -> Path:
    require(targets and len(targets) <= 64
            and all(not target.is_relative_to(policy.store.repo_path) for target in targets),
            "MIXED_PATH_SCOPE")
    try:
        root = Path(os.path.commonpath([str(target.parent) for target in targets]))
    except ValueError:
        raise CapabilityError("MIXED_PATH_SCOPE") from None
    while budget.stat(root) is None:
        require(root != root.parent, "ARTIFACT_ROOT_REQUIRED")
        root = root.parent
    require(root.is_dir(), "ARTIFACT_ROOT_REQUIRED")
    _artifact_path(root, budget)
    require(not any(_overlap(root, control) for control in _protected(policy, plugin_root, budget)),
            "CONTROL_PATH_CONFLICT")
    for target in targets:
        _artifact_path(target, budget)
        state = budget.stat(target)
        require(state is None or state.st_nlink == 1, "HARDLINK_REJECTED")
    return root


def create_native_request(policy: GatePolicy, plugin_root: Path, session: str, turn: str,
                          tool_use_id: str, command: str, targets: list[Path],
                          budget: PathBudget) -> dict:
    """中文：仅Hook从真实补丁冻结最窄已存在公共父目录，管理入口没有此能力。
    English: Only the Hook freezes the narrowest existing common parent from a real patch.
    """
    root = _candidate_root(policy, plugin_root, targets, budget)
    request_ref = "AR1-" + _ref(session, turn)[:16] + "-" + _ref(session, turn, tool_use_id)[:32]
    path = _request_path(policy, request_ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path):
        if native_path(path).exists():
            value = _request(policy, request_ref)
            require(value["root"] == str(root) and value["command_sha256"] ==
                    hashlib.sha256(command.encode("utf-8")).hexdigest(), "ARTIFACT_REQUEST_CONFLICT")
            return value
        for count, _ in enumerate(native_path(path.parent).iterdir(), 1):
            require(count <= MAX_REQUESTS, "ARTIFACT_REQUEST_LIMIT")
        now = datetime.now(timezone.utc)
        state = budget.stat(root)
        return _write(path, {"schema_version": 1, "request_ref": request_ref,
            "identity": policy.store.identity, "session_id": session, "turn_id": turn,
            "tool_use_id": tool_use_id, "root": str(root), "file_id": [state.st_dev, state.st_ino],
            "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
            "lease_expires_at": (now + timedelta(minutes=240)).isoformat(),
            "state": "PENDING"}, STATE_LIMIT)


def register_request(policy: GatePolicy, plugin_root: Path, request_ref: str,
                     *, revoke: bool = False) -> dict:
    """中文：只消费原生起点的冻结范围；不使用环境变量自报身份或任意目录参数。
    English: Consume only a frozen native request, without environment identity or arbitrary root inputs.
    """
    require(policy.read()["enabled"], "OP_GATE_NOT_ENABLED")
    request_path = _request_path(policy, request_ref)
    with OwnerTokenLock(request_path):
        request = _request(policy, request_ref)
        session = request["session_id"]
        path = _session_path(policy, session)
        with OwnerTokenLock(path):
            record = _session(policy, session)
            if revoke:
                # 中文：先撤销请求使残留root立即失效；中断后可幂等完成移除。
                # English: Revoke first so any remaining root is invalid; retry completes removal.
                request["state"] = "REVOKED"
                _write(request_path, request, STATE_LIMIT)
                record["roots"] = [row for row in record["roots"] if row["request_ref"] != request_ref]
                _write(path, record, STATE_LIMIT)
            elif request["state"] == "REGISTERED":
                require(_root_row(request) in record["roots"], "ARTIFACT_SCOPE_CHANGED")
            else:
                require(request["state"] == "PENDING", "ARTIFACT_REQUEST_REVOKED")
                require(parse_iso(request["expires_at"]) > datetime.now(timezone.utc),
                        "ARTIFACT_REQUEST_EXPIRED")
                budget = PathBudget()
                root = budget.resolve(request["root"], policy.store.repo_path)
                _artifact_path(root, budget)
                state = budget.stat(root)
                require(state is not None and root.is_dir()
                        and [state.st_dev, state.st_ino] == request["file_id"], "ARTIFACT_SCOPE_CHANGED")
                require(not any(_overlap(root, control) for control in _protected(policy, plugin_root, budget)),
                        "CONTROL_PATH_CONFLICT")
                row = _root_row(request)
                roots = [item for item in record["roots"] if item["request_ref"] != request_ref
                         and Path(item["path"]) != root
                         and parse_iso(item["expires_at"]) > datetime.now(timezone.utc)]
                require(not any(_overlap(root, Path(item["path"])) for item in roots),
                        "ARTIFACT_SCOPE_CONFLICT")
                require(len(roots) < MAX_ROOTS, "ARTIFACT_SCOPE_LIMIT")
                record["roots"] = [*roots, row]
                _write(path, record, STATE_LIMIT)
                # 中文：未完成此步的root保持不可用；重试仍用同一冻结到期时间。
                # English: Until this step completes the root remains unusable; retries retain its frozen expiry.
                request["state"] = "REGISTERED"
                _write(request_path, request, STATE_LIMIT)
    return {"request_ref": request_ref, "request_state": request["state"], "roots": record["roots"],
            "execution_authorization": "NONE", "host_permissions": "UNCHANGED"}


def validate_targets(policy: GatePolicy, plugin_root: Path, session: str,
                     targets: list[Path], budget: PathBudget) -> None:
    path = _session_path(policy, session)
    require(native_path(path).is_file(), "ARTIFACT_SCOPE_UNREGISTERED")
    record = _session(policy, session)
    candidates = [row for row in record["roots"]
                  if all(target.is_relative_to(Path(row["path"])) for target in targets)]
    require(len(candidates) == 1, "ARTIFACT_SCOPE_UNREGISTERED")
    row = candidates[0]
    request = _request(policy, row["request_ref"])
    require(request["session_id"] == session and request["state"] == "REGISTERED"
            and _root_row(request) == row, "ARTIFACT_REQUEST_CONFLICT")
    require(parse_iso(row["expires_at"]) > datetime.now(timezone.utc), "ARTIFACT_SCOPE_EXPIRED")
    root = budget.resolve(row["path"], policy.store.repo_path)
    state = budget.stat(root)
    require(state is not None and [state.st_dev, state.st_ino] == row["file_id"]
            and root.is_dir(), "ARTIFACT_SCOPE_CHANGED")
    controls = _protected(policy, plugin_root, budget)
    # 中文：登记后出现的新控制根也不能落入已登记范围。
    # English: Newly registered control roots cannot overlap an existing artifact scope.
    require(not any(_overlap(root, control) for control in controls), "CONTROL_PATH_CONFLICT")
    for target in targets:
        _artifact_path(target, budget)
        state = budget.stat(target)
        require(state is None or state.st_nlink == 1, "HARDLINK_REJECTED")


def call_binding(session: str, turn: str, tool_use_id: str) -> dict | None:
    root = gate_root()
    path = safe_path(root / "native-calls" / (_ref(session, turn, tool_use_id) + ".json"))
    if not native_path(path).exists():
        return None
    value = _read(path, STATE_LIMIT)
    fields(value, {"schema_version", "call_ref", "policy_path", "identity", "cwd",
                   "kind", "operation_ref", "command_sha256", "integrity"})
    require(value["schema_version"] == 1 and value["call_ref"] == _ref(session, turn, tool_use_id)
            and value["kind"] in {"repository", "artifact"}, "OP_CALL_BINDING_INVALID")
    require(isinstance(value["cwd"], str) and Path(value["cwd"]).is_absolute()
            and isinstance(value["policy_path"], str)
            and Path(value["policy_path"]).parent == root, "OP_CALL_BINDING_INVALID")
    require(isinstance(value["command_sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", value["command_sha256"]), "OP_CALL_BINDING_INVALID")
    require((value["kind"] == "artifact" and value["operation_ref"] is None)
            or (value["kind"] == "repository" and isinstance(value["operation_ref"], str)
                and re.fullmatch(r"OP2-[0-9a-f]{16}-[0-9a-f]{32}", value["operation_ref"])),
            "OP_CALL_BINDING_INVALID")
    return value


def bind_call(policy: GatePolicy, session: str, turn: str, tool_use_id: str,
              cwd: Path, command: str, kind: str, operation_ref: str | None) -> None:
    path = safe_path(policy.root / "native-calls" / (_ref(session, turn, tool_use_id) + ".json"))
    value = {"schema_version": 1, "call_ref": _ref(session, turn, tool_use_id),
             "policy_path": str(policy.path), "identity": policy.store.identity, "cwd": str(cwd),
             "kind": kind, "operation_ref": operation_ref,
             "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path):
        if native_path(path).exists():
            prior = call_binding(session, turn, tool_use_id)
            require({k: prior[k] for k in value} == value, "OP_CALL_BINDING_CONFLICT")
        else:
            _write(path, value, STATE_LIMIT)
