#!/usr/bin/env python3
"""Persist and enforce multi-agent review budgets and isolation evidence.

This helper never launches agents and never modifies source repositories. It only
writes a deterministic JSON ledger under --review-dir. A Reviewer TOML declaration
is recorded separately from the runtime isolation actually observed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List

STATE_FILE = "review-state.json"
LOCK_FILE = ".review-controller.lock"
SCHEMA_VERSION = 3
DEFAULT_LIMITS = {
    "max_agent_depth": 3,
    "max_post_review_rounds": 3,
    "max_preimplementation_rounds": 1,
    "max_preimplementation_reviewers": 4,
    "max_parallel_reviewers": 6,
    "max_total_reviewers": 12,
    "max_repair_rounds": 3,
}
VALID_PHASES = {"pre", "post"}
VALID_EFFORT_TIERS = {"economy", "balanced", "deep"}
VALID_RESULT_STATUSES = {"pass", "nonblocking", "blocking", "incomplete"}
VALID_PARENT_SANDBOXES = {"read-only", "workspace-write", "danger-full-access", "unknown"}
VALID_DECLARED_SANDBOXES = {"read-only", "workspace-write", "danger-full-access", "unknown"}
VALID_PROBE_RESULTS = {
    "not-run",
    "sandbox-denied",
    "permission-denied",
    "write-succeeded",
    "invalid",
}
VALID_REVIEW_MODES = {"independent-agent", "self-review", "unknown"}
VALID_ISOLATION_LEVELS = {"system-readonly", "logical-readonly", "self-review", "unknown"}
VALID_CONCLUSIONS = {
    "系统隔离复审通过，无阻塞项",
    "系统隔离复审有非阻塞问题",
    "逻辑只读复审完成，无阻塞项",
    "逻辑只读复审完成，有非阻塞问题",
    "系统隔离未验证或失败，仅完成逻辑只读复审",
    "有阻塞问题",
    "达到复审上限，仍有阻塞或未验证项",
    "工具或环境受限，未完成独立复审",
    "不适用",
    # Backward-compatible values from schema v1. New records should use explicit isolation wording.
    "通过，无阻塞项",
    "有非阻塞问题",
    "工具或环境受限，未完成严格独立复审",
}


def die(message: str) -> None:
    print("[FAIL] " + message, file=sys.stderr)
    raise SystemExit(1)


def warn(message: str) -> None:
    print("[WARN] " + message, file=sys.stderr)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp), str(path))
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


@contextmanager
def review_lock(review_dir: Path, force_unlock: bool = False) -> Iterator[None]:
    review_dir.mkdir(parents=True, exist_ok=True)
    lock_path = review_dir / LOCK_FILE
    if force_unlock and lock_path.exists():
        lock_path.unlink()
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        die("检测到复审台账写入锁；确认是崩溃遗留锁后可使用 --force-unlock")
    try:
        os.write(fd, "pid={}\ntime={}\n".format(os.getpid(), now_iso()).encode("utf-8"))
        os.close(fd)
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def state_path(review_dir: Path) -> Path:
    return review_dir / STATE_FILE


def default_isolation() -> Dict[str, Any]:
    return {
        "review_mode": "unknown",
        "parent_sandbox": "unknown",
        "declared_sandbox": "read-only",
        "probe_result": "not-run",
        "agent_config_confirmed": False,
        "runtime_agent_confirmed": False,
        "isolation_level": "unknown",
        "strict_readonly_eligible": False,
        "evidence": "",
        "verified_at": "",
    }


def derive_isolation_level(data: Dict[str, Any]) -> tuple[str, bool]:
    review_mode = str(data.get("review_mode", "unknown"))
    parent_sandbox = str(data.get("parent_sandbox", "unknown"))
    probe_result = str(data.get("probe_result", "not-run"))

    if review_mode == "self-review":
        return "self-review", False
    # Runtime write success is stronger counter-evidence than any declared or parent mode.
    if probe_result == "write-succeeded":
        return "logical-readonly", False
    # An explicit sandbox denial is direct runtime evidence, but identity must still be confirmed.
    if probe_result == "sandbox-denied":
        confirmed = bool(data.get("runtime_agent_confirmed"))
        return ("system-readonly", True) if confirmed else ("unknown", False)
    if parent_sandbox in {"workspace-write", "danger-full-access"}:
        return "logical-readonly", False
    if parent_sandbox == "read-only":
        confirmed = bool(data.get("runtime_agent_confirmed")) and bool(data.get("agent_config_confirmed"))
        return ("system-readonly", True) if confirmed else ("unknown", False)
    return "unknown", False


def normalize_state_data(state: Dict[str, Any]) -> Dict[str, Any]:
    version = state.get("schema_version")
    if version == 1:
        state["schema_version"] = SCHEMA_VERSION
        state.setdefault("risk_level", "unknown")
        state.setdefault("strict_readonly_required", False)
        state.setdefault("isolation", default_isolation())
        state.setdefault("notes", []).append(
            "从 schema v1 升级：原状态没有运行时隔离证据，默认标记为 unknown。"
        )
    elif version == 2:
        state["schema_version"] = SCHEMA_VERSION
        state.setdefault("risk_level", "unknown")
        state.setdefault("strict_readonly_required", False)
        state.setdefault("isolation", default_isolation())
        state.setdefault("notes", []).append("从 schema v2 升级：重新按 V4.1 证据优先级计算隔离等级。")
        level, eligible = derive_isolation_level(state["isolation"])
        state["isolation"]["isolation_level"] = level
        state["isolation"]["strict_readonly_eligible"] = eligible
    elif version == SCHEMA_VERSION:
        state.setdefault("risk_level", "unknown")
        state.setdefault("strict_readonly_required", False)
        state.setdefault("isolation", default_isolation())
    return state


def load_state(review_dir: Path) -> Dict[str, Any]:
    path = state_path(review_dir)
    if not path.is_file():
        die("缺少复审状态文件，请先执行 init: " + str(path))
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        die("复审状态文件不是有效 JSON: {}".format(exc))
    if not isinstance(data, dict):
        die("复审状态根节点必须是对象")
    return normalize_state_data(data)


def save_state(review_dir: Path, state: Dict[str, Any]) -> None:
    state["schema_version"] = SCHEMA_VERSION
    state["updated_at"] = now_iso()
    atomic_write(state_path(review_dir), state)


def parse_reviewers(value: str) -> List[str]:
    reviewers = [item.strip() for item in value.split(",") if item.strip()]
    if not reviewers:
        die("Reviewer 列表不能为空")
    if len(set(reviewers)) != len(reviewers):
        die("Reviewer 列表存在重复名称或重复职责")
    return reviewers


def phase_state(state: Dict[str, Any], phase: str) -> Dict[str, Any]:
    if phase not in VALID_PHASES:
        die("phase 必须是 pre 或 post")
    return state.setdefault("phases", {}).setdefault(
        phase, {"current_round": 0, "rounds": {}}
    )


def active_count(state: Dict[str, Any]) -> int:
    return sum(
        len(round_data.get("active", []))
        for phase in state.get("phases", {}).values()
        for round_data in phase.get("rounds", {}).values()
    )


def validate_isolation_data(state: Dict[str, Any]) -> None:
    isolation = state.get("isolation", {})
    if isolation.get("review_mode") not in VALID_REVIEW_MODES:
        die("未知 review_mode")
    if isolation.get("parent_sandbox") not in VALID_PARENT_SANDBOXES:
        die("未知 parent_sandbox")
    if isolation.get("declared_sandbox") not in VALID_DECLARED_SANDBOXES:
        die("未知 declared_sandbox")
    if isolation.get("probe_result") not in VALID_PROBE_RESULTS:
        die("未知 probe_result")
    if isolation.get("isolation_level") not in VALID_ISOLATION_LEVELS:
        die("未知 isolation_level")
    derived_level, derived_eligible = derive_isolation_level(isolation)
    if isolation.get("isolation_level") != derived_level:
        die("isolation_level 与运行时证据不一致")
    if bool(isolation.get("strict_readonly_eligible")) != derived_eligible:
        die("strict_readonly_eligible 与运行时证据不一致")


def validate_state_data(state: Dict[str, Any]) -> None:
    if state.get("schema_version") != SCHEMA_VERSION:
        die("不支持的 review-state schema_version")
    limits = state.get("limits", {})
    for key, ceiling in DEFAULT_LIMITS.items():
        value = limits.get(key)
        if not isinstance(value, int) or value < 1:
            die("复审限制 {} 必须是正整数".format(key))
        if value > ceiling:
            die("复审限制 {}={} 超过安全上限 {}".format(key, value, ceiling))
    counters = state.get("counters", {})
    if int(counters.get("total_reviewers", 0)) > limits["max_total_reviewers"]:
        die("累计 Reviewer 超过上限")
    if int(counters.get("repair_rounds", 0)) > limits["max_repair_rounds"]:
        die("集中修复轮次超过上限")
    if active_count(state) > limits["max_parallel_reviewers"]:
        die("活跃 Reviewer 超过并行上限")

    validate_isolation_data(state)

    for phase_name, phase in state.get("phases", {}).items():
        if phase_name not in VALID_PHASES:
            die("未知复审阶段: " + phase_name)
        max_rounds = (
            limits["max_preimplementation_rounds"]
            if phase_name == "pre"
            else limits["max_post_review_rounds"]
        )
        if int(phase.get("current_round", 0)) > max_rounds:
            die("{} 阶段轮次超过上限".format(phase_name))
        for round_key, round_data in phase.get("rounds", {}).items():
            reviewers = round_data.get("planned_reviewers", [])
            if len(reviewers) != len(set(reviewers)):
                die("{} / {} Reviewer 重复".format(phase_name, round_key))
            if int(round_data.get("depth", 0)) > limits["max_agent_depth"]:
                die("{} / {} 深度超过上限".format(phase_name, round_key))
            if phase_name == "pre" and len(reviewers) > limits["max_preimplementation_reviewers"]:
                die("实施前 Reviewer 超过上限")
            if len(reviewers) > limits["max_parallel_reviewers"]:
                die("单轮计划 Reviewer 超过并行上限")
            active = set(round_data.get("active", []))
            completed = set(round_data.get("results", {}).keys())
            planned = set(reviewers)
            if not active.issubset(planned) or not completed.issubset(planned):
                die("{} / {} 存在未计划 Reviewer".format(phase_name, round_key))
            if active & completed:
                die("Reviewer 不能同时处于 active 和 completed")


def command_init(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    review_dir.mkdir(parents=True, exist_ok=True)
    if state_path(review_dir).exists() and not args.force:
        die("复审状态已存在；如需重建请使用 --force")
    limits = dict(DEFAULT_LIMITS)
    for key, ceiling in DEFAULT_LIMITS.items():
        value = getattr(args, key, None)
        if value is not None:
            if value > ceiling:
                die("{} 不能高于安全上限 {}".format(key, ceiling))
            limits[key] = value
    state = {
        "schema_version": SCHEMA_VERSION,
        "boundary_id": args.boundary_id,
        "title": args.title,
        "risk_level": args.risk_level,
        "strict_readonly_required": bool(args.strict_readonly_required),
        "status": "open",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "limits": limits,
        "counters": {"total_reviewers": 0, "repair_rounds": 0},
        "phases": {
            "pre": {"current_round": 0, "rounds": {}},
            "post": {"current_round": 0, "rounds": {}},
        },
        "isolation": default_isolation(),
        "conclusion": "",
        "notes": [],
    }
    validate_state_data(state)
    with review_lock(review_dir, args.force_unlock):
        save_state(review_dir, state)
    print("[OK] 已初始化复审台账: " + str(state_path(review_dir)))
    print("[WARN] 运行时隔离尚未记录；TOML read-only 声明不能单独证明系统级只读。")


def command_isolation(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        isolation = {
            "review_mode": args.review_mode,
            "parent_sandbox": args.parent_sandbox,
            "declared_sandbox": args.declared_sandbox,
            "probe_result": args.probe_result,
            "agent_config_confirmed": bool(args.agent_config_confirmed),
            "runtime_agent_confirmed": bool(args.runtime_agent_confirmed),
            "evidence": args.evidence,
            "verified_at": now_iso(),
        }
        level, eligible = derive_isolation_level(isolation)
        isolation["isolation_level"] = level
        isolation["strict_readonly_eligible"] = eligible
        state["isolation"] = isolation
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已记录复审隔离: level={} strict={}".format(level, eligible))
    if level == "logical-readonly":
        warn("当前仅为逻辑只读；Reviewer TOML 声明没有形成系统级写入隔离。")
    elif level == "unknown":
        warn("运行时隔离仍未验证；不得声称系统强制只读。")


def ensure_strict_if_required(state: Dict[str, Any]) -> None:
    if state.get("strict_readonly_required") and not state["isolation"].get("strict_readonly_eligible"):
        die("当前功能边界要求严格只读复审，但父会话/运行时隔离未满足；请切换到只读父会话或记录有效 sandbox-denied 证据")


def command_plan(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    reviewers = parse_reviewers(args.reviewers)
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        validate_state_data(state)
        if state.get("status") != "open":
            die("复审台账已关闭")
        ensure_strict_if_required(state)
        phase = phase_state(state, args.phase)
        next_round = int(phase.get("current_round", 0)) + 1
        max_rounds = (
            state["limits"]["max_preimplementation_rounds"]
            if args.phase == "pre"
            else state["limits"]["max_post_review_rounds"]
        )
        if next_round > max_rounds:
            die("{} 阶段已达到最大轮次 {}".format(args.phase, max_rounds))
        if args.depth > state["limits"]["max_agent_depth"]:
            die("复审深度超过上限")
        if args.phase == "pre" and len(reviewers) > state["limits"]["max_preimplementation_reviewers"]:
            die("实施前 Reviewer 最多 {} 个".format(state["limits"]["max_preimplementation_reviewers"]))
        if len(reviewers) > state["limits"]["max_parallel_reviewers"]:
            die("计划 Reviewer 超过并行上限")
        if len(reviewers) > 1 and not args.packet_sha256:
            die("多 Reviewer 复审必须提供统一审查包 packet_sha256")
        remaining = state["limits"]["max_total_reviewers"] - state["counters"]["total_reviewers"]
        if len(reviewers) > remaining:
            die("Reviewer 总预算不足；剩余 {}，计划 {}".format(remaining, len(reviewers)))
        phase["current_round"] = next_round
        phase["rounds"][str(next_round)] = {
            "round": next_round,
            "phase": args.phase,
            "depth": args.depth,
            "purpose": args.purpose,
            "effort_tier": args.effort_tier,
            "packet_sha256": args.packet_sha256,
            "planned_reviewers": reviewers,
            "active": [],
            "results": {},
            "merge": None,
            "isolation_snapshot": {
                "isolation_level": state["isolation"]["isolation_level"],
                "strict_readonly_eligible": state["isolation"]["strict_readonly_eligible"],
                "parent_sandbox": state["isolation"]["parent_sandbox"],
            },
            "created_at": now_iso(),
        }
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已创建 {} 第 {} 轮计划: {}".format(args.phase, next_round, ", ".join(reviewers)))


def get_round(state: Dict[str, Any], phase_name: str, round_number: int) -> Dict[str, Any]:
    data = phase_state(state, phase_name).get("rounds", {}).get(str(round_number))
    if not isinstance(data, dict):
        die("不存在 {} 第 {} 轮计划".format(phase_name, round_number))
    return data


def command_dispatch(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        validate_state_data(state)
        ensure_strict_if_required(state)
        round_data = get_round(state, args.phase, args.round)
        if args.reviewer not in round_data["planned_reviewers"]:
            die("Reviewer 未包含在当前轮计划中")
        if args.reviewer in round_data["active"] or args.reviewer in round_data["results"]:
            die("Reviewer 已派发或已完成")
        if active_count(state) >= state["limits"]["max_parallel_reviewers"]:
            die("当前并行 Reviewer 已达到上限")
        if state["counters"]["total_reviewers"] >= state["limits"]["max_total_reviewers"]:
            die("累计 Reviewer 已达到上限")
        round_data["active"].append(args.reviewer)
        round_data.setdefault("dispatch", {})[args.reviewer] = {
            "scope": args.scope,
            "isolation_level": state["isolation"]["isolation_level"],
            "packet_sha256": round_data.get("packet_sha256", ""),
            "effort_tier": round_data.get("effort_tier", "balanced"),
            "dispatched_at": now_iso(),
        }
        state["counters"]["total_reviewers"] += 1
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已记录派发: {} / {} / round {} / {}".format(
        args.reviewer, args.phase, args.round, state["isolation"]["isolation_level"]
    ))


def command_result(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        validate_state_data(state)
        round_data = get_round(state, args.phase, args.round)
        expected_packet = round_data.get("packet_sha256", "")
        if expected_packet and not args.result_file:
            die("当前轮绑定了审查包，必须提供结构化 result_file")
        if args.result_file:
            result_path = Path(args.result_file).expanduser().resolve()
            if not result_path.is_file():
                die("Reviewer result_file 不存在")
            try:
                result_payload = json.loads(result_path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError as exc:
                die("Reviewer result_file 不是有效 JSON: {}".format(exc))
            if result_payload.get("reviewer") != args.reviewer:
                die("Reviewer result_file 身份不匹配")
            if result_payload.get("boundary_id") != state.get("boundary_id"):
                die("Reviewer result_file boundary_id 不匹配")
            if expected_packet and result_payload.get("packet_sha256") != expected_packet:
                die("Reviewer result_file packet_sha256 不匹配")
        if args.reviewer not in round_data["active"]:
            die("Reviewer 当前不处于 active 状态")
        round_data["active"].remove(args.reviewer)
        round_data["results"][args.reviewer] = {
            "status": args.status,
            "blocking_count": args.blocking_count,
            "nonblocking_count": args.nonblocking_count,
            "summary": args.summary,
            "result_file": args.result_file,
            "isolation_level": state["isolation"]["isolation_level"],
            "completed_at": now_iso(),
        }
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已记录 Reviewer 结果: {} -> {}".format(args.reviewer, args.status))


def command_merge(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        validate_state_data(state)
        round_data = get_round(state, args.phase, args.round)
        if round_data["active"]:
            die("仍有活跃 Reviewer，不能归并")
        missing = set(round_data["planned_reviewers"]) - set(round_data["results"].keys())
        if missing:
            die("尚未收齐 Reviewer 结果: {}".format(", ".join(sorted(missing))))
        round_data["merge"] = {
            "blocking_count": args.blocking_count,
            "nonblocking_count": args.nonblocking_count,
            "root_cause_groups": args.root_cause_groups,
            "summary": args.summary,
            "repair_required": args.repair_required,
            "isolation_level": state["isolation"]["isolation_level"],
            "merged_at": now_iso(),
        }
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已归并 {} 第 {} 轮".format(args.phase, args.round))


def command_repair(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        validate_state_data(state)
        current = state["counters"]["repair_rounds"] + 1
        if current > state["limits"]["max_repair_rounds"]:
            die("集中修复轮次已达到上限")
        state["counters"]["repair_rounds"] = current
        state.setdefault("repairs", []).append(
            {
                "round": current,
                "summary": args.summary,
                "affected_dimensions": [
                    item.strip() for item in args.affected_dimensions.split(",") if item.strip()
                ],
                "validation": args.validation,
                "recorded_at": now_iso(),
            }
        )
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已记录第 {} 轮集中修复".format(current))


def command_validate(args: argparse.Namespace) -> None:
    state = load_state(Path(args.review_dir).expanduser().resolve())
    validate_state_data(state)
    if args.require_strict_readonly:
        ensure_strict_if_required({**state, "strict_readonly_required": True})
    print(
        "[OK] 复审台账有效: boundary={} total={} repairs={} active={} isolation={} strict={}".format(
            state.get("boundary_id", ""),
            state["counters"]["total_reviewers"],
            state["counters"]["repair_rounds"],
            active_count(state),
            state["isolation"]["isolation_level"],
            state["isolation"]["strict_readonly_eligible"],
        )
    )


def command_status(args: argparse.Namespace) -> None:
    state = load_state(Path(args.review_dir).expanduser().resolve())
    validate_state_data(state)
    limits = state["limits"]
    isolation = state["isolation"]
    print("# 复审状态")
    print("- 功能边界: " + str(state.get("boundary_id", "")))
    print("- 风险级别: " + str(state.get("risk_level", "")))
    print("- 状态: " + str(state.get("status", "")))
    print("- 严格只读要求: " + ("是" if state.get("strict_readonly_required") else "否"))
    print("- Reviewer 配置声明: " + str(isolation.get("declared_sandbox", "unknown")))
    print("- 父会话运行时沙箱: " + str(isolation.get("parent_sandbox", "unknown")))
    print("- 写入探针: " + str(isolation.get("probe_result", "not-run")))
    print("- 复审隔离等级: " + str(isolation.get("isolation_level", "unknown")))
    print("- 系统级严格只读资格: " + ("是" if isolation.get("strict_readonly_eligible") else "否"))
    print("- 累计 Reviewer: {} / {}".format(state["counters"]["total_reviewers"], limits["max_total_reviewers"]))
    print("- 集中修复轮次: {} / {}".format(state["counters"]["repair_rounds"], limits["max_repair_rounds"]))
    print("- 当前活跃 Reviewer: {} / {}".format(active_count(state), limits["max_parallel_reviewers"]))
    for phase_name in ("pre", "post"):
        phase = phase_state(state, phase_name)
        print("- {} 当前轮次: {}".format(phase_name, phase.get("current_round", 0)))
        for round_key, round_data in sorted(phase.get("rounds", {}).items(), key=lambda item: int(item[0])):
            print(
                "  - round {}: planned={} active={} completed={} merged={}".format(
                    round_key,
                    len(round_data.get("planned_reviewers", [])),
                    len(round_data.get("active", [])),
                    len(round_data.get("results", {})),
                    "是" if round_data.get("merge") else "否",
                )
            )
    if state.get("conclusion"):
        print("- 最终结论: " + state["conclusion"])


def command_close(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        validate_state_data(state)
        if active_count(state):
            die("仍有活跃 Reviewer，不能关闭")
        isolation = state["isolation"]
        if args.conclusion.startswith("系统隔离复审") and not isolation.get("strict_readonly_eligible"):
            die("没有系统级只读运行时证据，不能使用系统隔离复审结论")
        if state.get("strict_readonly_required") and not isolation.get("strict_readonly_eligible"):
            allowed = {
                "系统隔离未验证或失败，仅完成逻辑只读复审",
                "有阻塞问题",
                "达到复审上限，仍有阻塞或未验证项",
                "工具或环境受限，未完成独立复审",
                "工具或环境受限，未完成严格独立复审",
            }
            if args.conclusion not in allowed:
                die("当前要求严格只读，但运行时隔离不满足；只能记录未完成、阻塞或逻辑只读降级结论")
        state["status"] = "closed"
        state["conclusion"] = args.conclusion
        if args.note:
            state.setdefault("notes", []).append(args.note)
        save_state(review_dir, state)
    print("[OK] 已关闭复审台账: " + args.conclusion)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--review-dir", required=True)
    parser.add_argument("--force-unlock", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="维护多 Agent 复审预算与运行时隔离证据")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--review-dir", required=True)
    init.add_argument("--boundary-id", required=True)
    init.add_argument("--title", default="")
    init.add_argument("--risk-level", choices=["low", "medium", "high", "critical", "unknown"], default="unknown")
    init.add_argument("--strict-readonly-required", action="store_true")
    init.add_argument("--force", action="store_true")
    init.add_argument("--force-unlock", action="store_true")
    for key, ceiling in DEFAULT_LIMITS.items():
        init.add_argument("--" + key.replace("_", "-"), type=int, default=None, help="安全上限 {}".format(ceiling))
    init.set_defaults(func=command_init)

    isolation = sub.add_parser("isolation")
    add_common(isolation)
    isolation.add_argument("--review-mode", choices=sorted(VALID_REVIEW_MODES), required=True)
    isolation.add_argument("--parent-sandbox", choices=sorted(VALID_PARENT_SANDBOXES), required=True)
    isolation.add_argument("--declared-sandbox", choices=sorted(VALID_DECLARED_SANDBOXES), default="read-only")
    isolation.add_argument("--probe-result", choices=sorted(VALID_PROBE_RESULTS), default="not-run")
    isolation.add_argument("--agent-config-confirmed", action="store_true")
    isolation.add_argument("--runtime-agent-confirmed", action="store_true")
    isolation.add_argument("--evidence", default="")
    isolation.set_defaults(func=command_isolation)

    plan = sub.add_parser("plan")
    add_common(plan)
    plan.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    plan.add_argument("--depth", type=int, required=True)
    plan.add_argument("--reviewers", required=True)
    plan.add_argument("--purpose", required=True)
    plan.add_argument("--effort-tier", choices=sorted(VALID_EFFORT_TIERS), default="balanced")
    plan.add_argument("--packet-sha256", default="")
    plan.set_defaults(func=command_plan)

    dispatch = sub.add_parser("dispatch")
    add_common(dispatch)
    dispatch.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    dispatch.add_argument("--round", type=int, required=True)
    dispatch.add_argument("--reviewer", required=True)
    dispatch.add_argument("--scope", required=True)
    dispatch.set_defaults(func=command_dispatch)

    result = sub.add_parser("result")
    add_common(result)
    result.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    result.add_argument("--round", type=int, required=True)
    result.add_argument("--reviewer", required=True)
    result.add_argument("--status", choices=sorted(VALID_RESULT_STATUSES), required=True)
    result.add_argument("--blocking-count", type=int, default=0)
    result.add_argument("--nonblocking-count", type=int, default=0)
    result.add_argument("--summary", required=True)
    result.add_argument("--result-file", default="")
    result.set_defaults(func=command_result)

    merge = sub.add_parser("merge")
    add_common(merge)
    merge.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    merge.add_argument("--round", type=int, required=True)
    merge.add_argument("--blocking-count", type=int, default=0)
    merge.add_argument("--nonblocking-count", type=int, default=0)
    merge.add_argument("--root-cause-groups", type=int, default=0)
    merge.add_argument("--summary", required=True)
    merge.add_argument("--repair-required", action="store_true")
    merge.set_defaults(func=command_merge)

    repair = sub.add_parser("repair")
    add_common(repair)
    repair.add_argument("--summary", required=True)
    repair.add_argument("--affected-dimensions", default="")
    repair.add_argument("--validation", default="")
    repair.set_defaults(func=command_repair)

    validate = sub.add_parser("validate")
    validate.add_argument("--review-dir", required=True)
    validate.add_argument("--require-strict-readonly", action="store_true")
    validate.set_defaults(func=command_validate)

    status = sub.add_parser("status")
    status.add_argument("--review-dir", required=True)
    status.set_defaults(func=command_status)

    close = sub.add_parser("close")
    add_common(close)
    close.add_argument("--conclusion", choices=sorted(VALID_CONCLUSIONS), required=True)
    close.add_argument("--note", default="")
    close.set_defaults(func=command_close)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
