#!/usr/bin/env python3
"""Deterministic task envelope, phase gates, and repository evidence fingerprints."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

STATE = "execution-state.json"
SCHEMA = 2
PROFILES = {"LIGHT", "STANDARD", "STRICT"}
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
FULL_HASH_LIMIT = 4 * 1024 * 1024
SAMPLE_BYTES = 1024 * 1024


def die(message: str) -> None:
    print("[FAIL] " + message, file=sys.stderr)
    raise SystemExit(1)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(command: Iterable[str], cwd: Path) -> bytes:
    cmd = list(command)
    result = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        die("命令失败: " + " ".join(cmd) + "\n" + result.stderr.decode(errors="replace"))
    return result.stdout


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def sampled_file_digest(path: Path) -> Tuple[str, str]:
    info = path.lstat()
    digest = hashlib.sha256()
    digest.update(str(info.st_mode).encode())
    digest.update(b"\0")
    digest.update(str(info.st_size).encode())
    digest.update(b"\0")
    if stat.S_ISLNK(info.st_mode):
        digest.update(os.readlink(path).encode(errors="surrogateescape"))
        return digest.hexdigest(), "symlink"
    if not stat.S_ISREG(info.st_mode):
        digest.update(str(info.st_mtime_ns).encode())
        return digest.hexdigest(), "metadata"
    with path.open("rb") as handle:
        if info.st_size <= FULL_HASH_LIMIT:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
            return digest.hexdigest(), "full"
        digest.update(handle.read(SAMPLE_BYTES))
        handle.seek(max(0, info.st_size - SAMPLE_BYTES))
        digest.update(handle.read(SAMPLE_BYTES))
        digest.update(str(info.st_mtime_ns).encode())
        return digest.hexdigest(), "sampled"


def untracked_fingerprint(repo: Path) -> Dict[str, Any]:
    raw = run(["git", "ls-files", "--others", "--exclude-standard", "-z"], repo)
    names = [item for item in raw.split(b"\0") if item]
    digest = hashlib.sha256()
    sampled_count = 0
    for raw_name in sorted(names):
        relative = raw_name.decode("utf-8", errors="surrogateescape")
        path = repo / relative
        digest.update(raw_name)
        digest.update(b"\0")
        if not path.exists() and not path.is_symlink():
            digest.update(b"missing")
            continue
        file_digest, mode = sampled_file_digest(path)
        if mode == "sampled":
            sampled_count += 1
        digest.update(mode.encode())
        digest.update(b":")
        digest.update(file_digest.encode())
        digest.update(b"\0")
    return {
        "sha256": digest.hexdigest(),
        "count": len(names),
        "sampled_count": sampled_count,
    }


def repo_fingerprint(repo: Path) -> Dict[str, Any]:
    repo = repo.resolve()
    head = run(["git", "rev-parse", "HEAD"], repo).decode().strip()
    status_data = run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], repo)
    diff_data = run(["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--"], repo)
    untracked = untracked_fingerprint(repo)
    digest = hashlib.sha256()
    digest.update(head.encode())
    digest.update(b"\0")
    digest.update(status_data)
    digest.update(b"\0")
    digest.update(diff_data)
    digest.update(b"\0")
    digest.update(untracked["sha256"].encode())
    return {
        "head": head,
        "sha256": digest.hexdigest(),
        "status_sha256": hashlib.sha256(status_data).hexdigest(),
        "diff_sha256": hashlib.sha256(diff_data).hexdigest(),
        "untracked_sha256": untracked["sha256"],
        "untracked_count": untracked["count"],
        "untracked_sampled_count": untracked["sampled_count"],
    }


def atomic_write(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        temp_path = Path(temp_name)
        if temp_path.exists():
            temp_path.unlink()


def load_state(directory: Path) -> Dict[str, Any]:
    path = directory / STATE
    if not path.is_file():
        die("缺少 execution-state.json，请先 init")
    state = json.loads(path.read_text(encoding="utf-8-sig"))
    if state.get("schema_version") == 1:
        state["schema_version"] = SCHEMA
        state.setdefault("history", []).append({"at": now_iso(), "event": "migrate", "from": 1, "to": SCHEMA})
    if state.get("schema_version") != SCHEMA:
        die("不支持的 execution-state schema_version")
    return state


def save_state(directory: Path, state: Dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    atomic_write(directory / STATE, state)


def command_init(args: argparse.Namespace) -> None:
    repo = Path(args.repo_path).expanduser().resolve()
    directory = Path(args.state_dir).expanduser().resolve()
    if inside(directory, repo) and not args.allow_inside_repo:
        die("执行状态默认必须保存在仓库外；需要时显式使用 --allow-inside-repo")
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / STATE).exists() and not args.force:
        die("状态已存在")
    fingerprint = repo_fingerprint(repo)
    state = {
        "schema_version": SCHEMA,
        "task_id": args.task_id,
        "title": args.title,
        "profile": args.profile,
        "mode": args.mode,
        "risk_level": args.risk_level,
        "phase": "IDENTIFY",
        "repo_path": str(repo),
        "authorization": {},
        "skills": {"primary": "", "supporting": [], "deferred": []},
        "required_gates": REQUIRED[args.profile],
        "completed_gates": [],
        "evidence": {"validations": {}, "reviews": {}},
        "repo_fingerprint": fingerprint,
        "history": [{"at": now_iso(), "event": "init", "phase": "IDENTIFY"}],
    }
    save_state(directory, state)
    print("[OK] 已初始化任务执行状态:", directory / STATE)


def command_transition(args: argparse.Namespace) -> None:
    directory = Path(args.state_dir).resolve()
    state = load_state(directory)
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
    state["history"].append({"at": now_iso(), "event": "transition", "from": current, "to": target, "note": args.note})
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
    save_state(directory, state)
    print("[OK] 已更新执行信封")


def command_gate(args: argparse.Namespace) -> None:
    directory = Path(args.state_dir).resolve()
    state = load_state(directory)
    if args.name not in state["completed_gates"]:
        state["completed_gates"].append(args.name)
    state["history"].append({"at": now_iso(), "event": "gate", "name": args.name, "evidence": args.evidence})
    save_state(directory, state)
    print("[OK] 已记录门禁", args.name)


def record_evidence(args: argparse.Namespace, kind: str) -> None:
    directory = Path(args.state_dir).resolve()
    state = load_state(directory)
    fingerprint = repo_fingerprint(Path(state["repo_path"]))
    target = state["evidence"]["validations" if kind == "validation" else "reviews"]
    target[args.name] = {
        "status": args.status,
        "command_or_packet": args.command_or_packet,
        "summary": args.summary,
        "fingerprint": fingerprint,
        "recorded_at": now_iso(),
    }
    state["repo_fingerprint"] = fingerprint
    save_state(directory, state)
    print("[OK] 已记录", kind, args.name)


def command_validate(args: argparse.Namespace) -> None:
    directory = Path(args.state_dir).resolve()
    state = load_state(directory)
    current = repo_fingerprint(Path(state["repo_path"]))
    stale = []
    for group in ("validations", "reviews"):
        for name, item in state["evidence"][group].items():
            if item.get("fingerprint", {}).get("sha256") != current["sha256"]:
                item["status"] = "stale"
                stale.append(group + ":" + name)
    state["repo_fingerprint"] = current
    save_state(directory, state)
    missing = [item for item in state["required_gates"] if item not in state["completed_gates"]]
    if stale:
        print("[WARN] 失效证据:", ",".join(stale))
    if args.require_gates and missing:
        die("缺少门禁: " + ",".join(missing))
    print("[OK] 状态有效; phase={} profile={} stale={} missing={}".format(
        state["phase"], state["profile"], len(stale), len(missing)
    ))


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
    validate = sub.add_parser("validate")
    validate.add_argument("--state-dir", required=True)
    validate.add_argument("--require-gates", action="store_true")
    validate.set_defaults(func=command_validate)
    status_cmd = sub.add_parser("status")
    status_cmd.add_argument("--state-dir", required=True)
    status_cmd.set_defaults(func=command_status)
    arguments = parser.parse_args()
    arguments.func(arguments)


if __name__ == "__main__":
    main()
