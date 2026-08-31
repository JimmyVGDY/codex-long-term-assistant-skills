#!/usr/bin/env python3
"""中文：V5.0 确定性 Task Envelope、项目绑定、授权与终态控制器。

English: V5.0 deterministic Task Envelope, project binding, approval, and finalization controller.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

# 中文：源码目录为 <root>/skills/.../scripts，安装目录为 <CODEX_HOME>/skills/.../scripts。
# English: Source tree: <root>/skills/.../scripts; installed tree: <CODEX_HOME>/skills/.../scripts.
_RUNTIME_ROOT = Path(__file__).resolve().parents[3] / "runtime"
if str(_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_ROOT))

from cp_runtime.approval import check_approval, consume_approval, load_approval  # noqa: E402
from cp_runtime.common import (  # noqa: E402
    RuntimeContractError,
    atomic_write_json,
    repo_snapshot,
    utc_now,
)
from cp_runtime.finalization import build_finalization_report  # noqa: E402
from cp_runtime.project import validate_binding  # noqa: E402

STATE = "execution-state.json"
SCHEMA = 3
PROFILES = {"LIGHT", "STANDARD", "STRICT"}
COMPLEXITIES = {"L0", "L1", "L2", "L3", "L4"}
PROJECT_STAGES = {"UNPROFILED", "ONBOARDING", "ACTIVE", "PAUSED", "ARCHIVED"}
REVIEWER_BUDGETS = {"economy", "balanced", "deep"}
MODEL_PROFILES = {"luna-low", "luna-medium", "terra-medium", "terra-high"}
HOST_SURFACES = {"main-session", "subagent", "direct-workspace", "worktree", "mcp", "long-running-task"}
ENVIRONMENTS = {"local", "nonproduction", "production"}
PHASES = {
    "IDENTIFY", "PLAN", "IMPLEMENT", "VALIDATE", "REVIEW", "DELIVER",
    "RECOVER", "BLOCKED", "ROLLBACK", "CANCELLED", "CLOSED",
}
TRANSITIONS = {
    "IDENTIFY": {"PLAN", "BLOCKED", "CANCELLED"},
    "PLAN": {"IMPLEMENT", "BLOCKED", "CANCELLED"},
    "IMPLEMENT": {"VALIDATE", "BLOCKED", "ROLLBACK", "CANCELLED"},
    "VALIDATE": {"REVIEW", "IMPLEMENT", "BLOCKED", "ROLLBACK", "CANCELLED"},
    "REVIEW": {"DELIVER", "IMPLEMENT", "VALIDATE", "BLOCKED", "ROLLBACK", "CANCELLED"},
    "DELIVER": {"CLOSED", "BLOCKED", "ROLLBACK"},
    "RECOVER": {"IDENTIFY", "PLAN", "IMPLEMENT", "VALIDATE", "REVIEW", "DELIVER", "BLOCKED"},
    "BLOCKED": {"RECOVER", "PLAN", "IMPLEMENT", "VALIDATE", "REVIEW", "CANCELLED"},
    "ROLLBACK": {"VALIDATE", "DELIVER", "CLOSED", "BLOCKED"},
    "CANCELLED": set(),
    "CLOSED": set(),
}
REQUIRED = {
    "LIGHT": [],
    "STANDARD": ["targeted_validation", "git_diff_review"],
    "STRICT": [
        "preimplementation_review", "targeted_validation", "postimplementation_review",
        "rollback_ready", "memory_checkpoint",
    ],
}
ACTION_TO_OPERATION = {
    "committed": "commit",
    "pushed": "push",
    "deployed": "deploy",
    "restarted": "restart",
    "data-written": "data-write",
    "production-operated": "production-operation",
    "effective": "make-effective",
}


def die(message: str) -> None:
    print("[FAIL] " + message, file=sys.stderr)
    raise SystemExit(1)


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def capture_repo_fingerprint(repo: Path) -> Dict[str, Any]:
    """中文：捕获包含 untracked_sha256 的完整仓库指纹。

    English: Capture the complete repository fingerprint, including untracked_sha256.
    """
    fingerprint = repo_snapshot(repo)
    if not fingerprint.get("untracked_sha256"):
        raise RuntimeContractError("仓库指纹缺少 untracked_sha256")
    return fingerprint


def migrate_state(state: Dict[str, Any]) -> Dict[str, Any]:
    version = int(state.get("schema_version", 1))
    if version > SCHEMA:
        die("不支持的 execution-state schema_version")
    if version < 3:
        old_fingerprint = state.get("repo_fingerprint") or {}
        state["schema_version"] = 3
        state.setdefault("baseline_fingerprint", old_fingerprint)
        state.setdefault("current_fingerprint", old_fingerprint)
        state.setdefault("project", {
            "project_id": "",
            "profile_path": "",
            "state_path": "",
            "profile_sha256": "",
            "binding_status": "UNBOUND",
        })
        state.setdefault("routing", {
            "complexity": "L1",
            "project_stage": "UNPROFILED",
            "execution_profile": state.get("profile", "STANDARD"),
            "reviewer_budget": "balanced",
            "model_profile": "terra-medium",
            "host_surface": "direct-workspace",
        })
        state.setdefault("environment", "local")
        state.setdefault("authorized_actions", {})
        state.setdefault("actions", {})
        state.setdefault("history", []).append({
            "at": utc_now(), "event": "migrate", "from": version, "to": SCHEMA,
        })
    state["repo_fingerprint"] = state.get("current_fingerprint") or state.get("repo_fingerprint") or {}
    return state


def load_state(directory: Path) -> Dict[str, Any]:
    path = directory / STATE
    if not path.is_file():
        die("缺少 execution-state.json，请先 init")
    try:
        state = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        die("读取 execution-state.json 失败: " + str(exc))
    return migrate_state(state)


def save_state(directory: Path, state: Dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    state["repo_fingerprint"] = state.get("current_fingerprint", {})
    atomic_write_json(directory / STATE, state)


def validate_project_context(state: Dict[str, Any]) -> None:
    project = state.get("project") or {}
    profile_path = project.get("profile_path")
    if not profile_path:
        return
    binding = validate_binding(
        Path(profile_path), Path(state["repo_path"]), project.get("project_id") or None,
        Path(project["state_path"]) if project.get("state_path") else None,
    )
    if binding.profile_sha256 != project.get("profile_sha256"):
        raise RuntimeContractError("Project Profile 已变化，必须重新绑定任务信封")


def command_init(args: argparse.Namespace) -> None:
    repo = Path(args.repo_path).expanduser().resolve()
    directory = Path(args.state_dir).expanduser().resolve()
    if inside(directory, repo) and not args.allow_inside_repo:
        die("执行状态默认必须保存在仓库外；需要时显式使用 --allow-inside-repo")
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / STATE).exists() and not args.force:
        die("状态已存在")
    fingerprint = capture_repo_fingerprint(repo)
    project = {
        "project_id": args.project_id or "",
        "profile_path": "",
        "state_path": "",
        "profile_sha256": "",
        "binding_status": "UNBOUND",
    }
    project_stage = args.project_stage
    if args.project_profile:
        try:
            binding = validate_binding(
                Path(args.project_profile), repo, args.project_id,
                Path(args.project_state) if args.project_state else None,
            )
        except RuntimeContractError as exc:
            die(str(exc))
        project = {
            "project_id": binding.project_id,
            "profile_path": str(binding.profile_path),
            "state_path": str(binding.state_path),
            "profile_sha256": binding.profile_sha256,
            "binding_status": "BOUND",
        }
        if project_stage == "UNPROFILED":
            project_stage = "ACTIVE"
    state = {
        "schema_version": SCHEMA,
        "task_id": args.task_id,
        "title": args.title,
        "profile": args.profile,
        "mode": args.mode,
        "risk_level": args.risk_level,
        "phase": "IDENTIFY",
        "repo_path": str(Path(fingerprint["repo_path"])),
        "environment": args.environment,
        "project": project,
        "routing": {
            "complexity": args.complexity,
            "project_stage": project_stage,
            "execution_profile": args.profile,
            "reviewer_budget": args.reviewer_budget,
            "model_profile": args.model_profile,
            "host_surface": args.host_surface,
        },
        "authorization": {},
        "authorized_actions": {},
        "actions": {},
        "skills": {"primary": "", "supporting": [], "deferred": []},
        "required_gates": REQUIRED[args.profile],
        "completed_gates": [],
        "evidence": {"validations": {}, "reviews": {}},
        "baseline_fingerprint": fingerprint,
        "current_fingerprint": fingerprint,
        "repo_fingerprint": fingerprint,
        "history": [{"at": utc_now(), "event": "init", "phase": "IDENTIFY"}],
    }
    save_state(directory, state)
    print("[OK] 已初始化 Task Envelope V2:", directory / STATE)


def command_transition(args: argparse.Namespace) -> None:
    directory = Path(args.state_dir).resolve()
    state = load_state(directory)
    try:
        validate_project_context(state)
    except RuntimeContractError as exc:
        die(str(exc))
    current = state["phase"]
    target = args.to
    if target not in TRANSITIONS.get(current, set()):
        die(f"不允许阶段转换 {current} -> {target}")
    if target == "IMPLEMENT" and state["profile"] == "STRICT" and "preimplementation_review" not in state["completed_gates"]:
        die("STRICT 进入 IMPLEMENT 前必须完成实施前审查")
    if target == "DELIVER":
        missing = [item for item in state["required_gates"] if item not in state["completed_gates"]]
        if missing:
            die("DELIVER 前门禁未完成: " + ",".join(missing))
    state["phase"] = target
    state["history"].append({"at": utc_now(), "event": "transition", "from": current, "to": target, "note": args.note})
    save_state(directory, state)
    print("[OK]", current, "->", target)


def command_set_envelope(args: argparse.Namespace) -> None:
    directory = Path(args.state_dir).resolve()
    state = load_state(directory)
    if args.primary_skill:
        state["skills"]["primary"] = args.primary_skill
    if args.supporting_skills is not None:
        state["skills"]["supporting"] = [item.strip() for item in args.supporting_skills.split(",") if item.strip()]
    if args.deferred_skills is not None:
        state["skills"]["deferred"] = [item.strip() for item in args.deferred_skills.split(",") if item.strip()]
    for item in args.authorization:
        if "=" not in item:
            die("authorization 使用 key=true|false")
        key, value = item.split("=", 1)
        state["authorization"][key] = value.lower() == "true"
    routing_updates = {
        "complexity": args.complexity,
        "project_stage": args.project_stage,
        "reviewer_budget": args.reviewer_budget,
        "model_profile": args.model_profile,
        "host_surface": args.host_surface,
    }
    for key, value in routing_updates.items():
        if value:
            state["routing"][key] = value
    if args.environment:
        state["environment"] = args.environment
    save_state(directory, state)
    print("[OK] 已更新 Task Envelope V2")


def command_gate(args: argparse.Namespace) -> None:
    directory = Path(args.state_dir).resolve()
    state = load_state(directory)
    try:
        validate_project_context(state)
    except RuntimeContractError as exc:
        die(str(exc))
    if args.name not in state["completed_gates"]:
        state["completed_gates"].append(args.name)
    state["history"].append({"at": utc_now(), "event": "gate", "name": args.name, "evidence": args.evidence})
    save_state(directory, state)
    print("[OK] 已记录门禁", args.name)


def record_evidence(args: argparse.Namespace, kind: str) -> None:
    directory = Path(args.state_dir).resolve()
    state = load_state(directory)
    try:
        validate_project_context(state)
    except RuntimeContractError as exc:
        die(str(exc))
    fingerprint = capture_repo_fingerprint(Path(state["repo_path"]))
    target = state["evidence"]["validations" if kind == "validation" else "reviews"]
    target[args.name] = {
        "status": args.status,
        "command_or_packet": args.command_or_packet,
        "summary": args.summary,
        "project_id": (state.get("project") or {}).get("project_id", ""),
        "task_id": state.get("task_id", ""),
        "fingerprint": fingerprint,
        "recorded_at": utc_now(),
    }
    state["current_fingerprint"] = fingerprint
    state["repo_fingerprint"] = fingerprint
    save_state(directory, state)
    print("[OK] 已记录", kind, args.name)


def command_authorize_action(args: argparse.Namespace) -> None:
    directory = Path(args.state_dir).resolve()
    state = load_state(directory)
    try:
        validate_project_context(state)
    except RuntimeContractError as exc:
        die(str(exc))
    action = args.action
    operation = ACTION_TO_OPERATION[action]
    project_id = (state.get("project") or {}).get("project_id")
    if not project_id:
        die("受保护动作必须先绑定 Project Profile")
    current = capture_repo_fingerprint(Path(state["repo_path"]))
    try:
        result = check_approval(
            Path(args.approval), project_id, state["task_id"], operation,
            state["environment"], current["sha256"],
        )
        if not result.valid:
            die("Approval 无效: " + ",".join(result.reasons))
        record = consume_approval(
            Path(args.approval), project_id, state["task_id"], operation,
            state["environment"], current["sha256"],
        )
    except RuntimeContractError as exc:
        die(str(exc))
    state["authorized_actions"][action] = {
        "approval_id": record["approval_id"],
        "approval_path": str(Path(args.approval).expanduser().resolve()),
        "operation": operation,
        "environment": state["environment"],
        "baseline_sha256": current["sha256"],
        "baseline_fingerprint": current,
        "authorized_at": utc_now(),
    }
    state["history"].append({
        "at": utc_now(), "event": "authorize-action", "action": action,
        "approval_id": record["approval_id"], "baseline_sha256": current["sha256"],
    })
    save_state(directory, state)
    print("[OK] 已消费 Approval 并授权动作", action)


def command_record_action(args: argparse.Namespace) -> None:
    directory = Path(args.state_dir).resolve()
    state = load_state(directory)
    try:
        validate_project_context(state)
    except RuntimeContractError as exc:
        die(str(exc))
    action = args.action
    authorization = state.get("authorized_actions", {}).get(action)
    if args.status == "success" and not authorization:
        die("成功记录受保护动作前必须先执行 authorize-action")
    current = capture_repo_fingerprint(Path(state["repo_path"]))
    if args.status == "success" and authorization:
        baseline = authorization.get("baseline_fingerprint") or {}
        if action == "committed":
            if not baseline.get("head") or current.get("head") == baseline.get("head"):
                die("Commit 动作读回未检测到 HEAD 变化")
        elif current.get("sha256") != authorization.get("baseline_sha256"):
            die("动作执行前后仓库基线已变化，旧 Approval 失效；必须重新授权")
    state["actions"][action] = {
        "status": args.status,
        "summary": args.summary,
        "evidence": args.evidence,
        "fingerprint": current,
        "approval": authorization,
        "recorded_at": utc_now(),
    }
    state["current_fingerprint"] = current
    state["history"].append({"at": utc_now(), "event": "record-action", "action": action, "status": args.status})
    save_state(directory, state)
    print("[OK] 已记录动作读回", action, args.status)


def command_validate(args: argparse.Namespace) -> None:
    directory = Path(args.state_dir).resolve()
    state = load_state(directory)
    try:
        validate_project_context(state)
    except RuntimeContractError as exc:
        die(str(exc))
    current = capture_repo_fingerprint(Path(state["repo_path"]))
    stale = []
    for group in ("validations", "reviews"):
        for name, item in state["evidence"][group].items():
            if item.get("fingerprint", {}).get("sha256") != current["sha256"]:
                item["status"] = "stale"
                stale.append(group + ":" + name)
    state["current_fingerprint"] = current
    state["repo_fingerprint"] = current
    save_state(directory, state)
    missing = [item for item in state["required_gates"] if item not in state["completed_gates"]]
    if stale:
        print("[WARN] 失效证据:", ",".join(stale))
    if args.require_gates and missing:
        die("缺少门禁: " + ",".join(missing))
    print("[OK] 状态有效; phase={} profile={} project={} stale={} missing={}".format(
        state["phase"], state["profile"], (state.get("project") or {}).get("binding_status", "UNBOUND"),
        len(stale), len(missing),
    ))


def command_finalize(args: argparse.Namespace) -> None:
    directory = Path(args.state_dir).resolve()
    state_path = directory / STATE
    state = load_state(directory)
    try:
        validate_project_context(state)
        report = build_finalization_report(
            state_path,
            Path(state["repo_path"]),
            args.claim,
            Path(args.output_json),
            Path(args.output_markdown) if args.output_markdown else None,
        )
    except RuntimeContractError as exc:
        die(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_all and report["result"] != "PASS":
        raise SystemExit(2)


def command_status(args: argparse.Namespace) -> None:
    print(json.dumps(load_state(Path(args.state_dir).resolve()), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--state-dir", required=True)
    init.add_argument("--task-id", required=True)
    init.add_argument("--title", default="")
    init.add_argument("--profile", choices=sorted(PROFILES), default="STANDARD")
    init.add_argument("--mode", default="local-modification")
    init.add_argument("--risk-level", default="medium")
    init.add_argument("--repo-path", required=True)
    init.add_argument("--project-profile")
    init.add_argument("--project-state")
    init.add_argument("--project-id")
    init.add_argument("--complexity", choices=sorted(COMPLEXITIES), default="L1")
    init.add_argument("--project-stage", choices=sorted(PROJECT_STAGES), default="UNPROFILED")
    init.add_argument("--reviewer-budget", choices=sorted(REVIEWER_BUDGETS), default="balanced")
    init.add_argument("--model-profile", choices=sorted(MODEL_PROFILES), default="terra-medium")
    init.add_argument("--host-surface", choices=sorted(HOST_SURFACES), default="direct-workspace")
    init.add_argument("--environment", choices=sorted(ENVIRONMENTS), default="local")
    init.add_argument("--force", action="store_true")
    init.add_argument("--allow-inside-repo", action="store_true")
    init.set_defaults(func=command_init)

    transition = sub.add_parser("transition")
    transition.add_argument("--state-dir", required=True)
    transition.add_argument("--to", choices=sorted(PHASES), required=True)
    transition.add_argument("--note", default="")
    transition.set_defaults(func=command_transition)

    envelope = sub.add_parser("set-envelope")
    envelope.add_argument("--state-dir", required=True)
    envelope.add_argument("--primary-skill")
    envelope.add_argument("--supporting-skills")
    envelope.add_argument("--deferred-skills")
    envelope.add_argument("--authorization", action="append", default=[])
    envelope.add_argument("--complexity", choices=sorted(COMPLEXITIES))
    envelope.add_argument("--project-stage", choices=sorted(PROJECT_STAGES))
    envelope.add_argument("--reviewer-budget", choices=sorted(REVIEWER_BUDGETS))
    envelope.add_argument("--model-profile", choices=sorted(MODEL_PROFILES))
    envelope.add_argument("--host-surface", choices=sorted(HOST_SURFACES))
    envelope.add_argument("--environment", choices=sorted(ENVIRONMENTS))
    envelope.set_defaults(func=command_set_envelope)

    gate = sub.add_parser("gate")
    gate.add_argument("--state-dir", required=True)
    gate.add_argument("--name", required=True)
    gate.add_argument("--evidence", default="")
    gate.set_defaults(func=command_gate)

    for name, kind in (("record-validation", "validation"), ("record-review", "review")):
        item = sub.add_parser(name)
        item.add_argument("--state-dir", required=True)
        item.add_argument("--name", required=True)
        item.add_argument("--status", choices=["valid", "failed", "blocked", "unknown"], required=True)
        item.add_argument("--command-or-packet", default="")
        item.add_argument("--summary", default="")
        item.set_defaults(func=lambda arguments, current_kind=kind: record_evidence(arguments, current_kind))

    item = sub.add_parser("authorize-action")
    item.add_argument("--state-dir", required=True)
    item.add_argument("--action", choices=sorted(ACTION_TO_OPERATION), required=True)
    item.add_argument("--approval", required=True)
    item.set_defaults(func=command_authorize_action)

    item = sub.add_parser("record-action")
    item.add_argument("--state-dir", required=True)
    item.add_argument("--action", choices=sorted(ACTION_TO_OPERATION), required=True)
    item.add_argument("--status", choices=["success", "failed", "blocked", "unknown"], required=True)
    item.add_argument("--summary", default="")
    item.add_argument("--evidence", default="")
    item.set_defaults(func=command_record_action)

    validate = sub.add_parser("validate")
    validate.add_argument("--state-dir", required=True)
    validate.add_argument("--require-gates", action="store_true")
    validate.set_defaults(func=command_validate)

    item = sub.add_parser("finalize")
    item.add_argument("--state-dir", required=True)
    item.add_argument("--claim", action="append", default=[])
    item.add_argument("--output-json", required=True)
    item.add_argument("--output-markdown")
    item.add_argument("--require-all", action="store_true")
    item.set_defaults(func=command_finalize)

    status_cmd = sub.add_parser("status")
    status_cmd.add_argument("--state-dir", required=True)
    status_cmd.set_defaults(func=command_status)

    arguments = parser.parse_args()
    arguments.func(arguments)


if __name__ == "__main__":
    main()
