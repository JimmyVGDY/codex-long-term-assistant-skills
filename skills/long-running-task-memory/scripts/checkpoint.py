#!/usr/bin/env python3
"""中文：长期 Codex 任务的确定性 Markdown 检查点；仅使用 Python 标准库，只写入显式外部记忆目录，并可只读 Git 仓库生成工作区指纹。

English: Deterministic Markdown checkpoints for long-running Codex tasks. The helper uses only the Python standard library, writes only to the explicit external-memory directory, and may read a Git repository to record a workspace fingerprint.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None  # type: ignore

LIVE_BEGIN = "<!-- live-task-state:begin -->"
LIVE_END = "<!-- live-task-state:end -->"
CHECKPOINTS_BEGIN = "<!-- progress-checkpoints:begin -->"
CHECKPOINTS_END = "<!-- progress-checkpoints:end -->"
ARCHIVE_INDEX_BEGIN = "<!-- progress-archive-index:begin -->"
ARCHIVE_INDEX_END = "<!-- progress-archive-index:end -->"
CHECKPOINT_RE = re.compile(r"(?m)^### (CP-(\d{8})-(\d{3,}))\s*$")
STATE_VERSION_RE = re.compile(r"(?m)^- 状态版本：(\d+)\s*$")
DEFAULT_HOT_LIMIT = 20
SENSITIVE_PATTERNS = (
    ("OpenAI/API Key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Bearer Token", re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    ("Credential URI", re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/:]+:[^\s/@]+@")),
    ("Generic Secret", re.compile(r"(?i)\b(password|passwd|token|secret|access[_-]?key|secret[_-]?key)\b\s*[:=]\s*([^\s`]+)")),
)


def die(message: str, code: int = 1) -> None:
    print("[FAIL] " + message, file=sys.stderr)
    raise SystemExit(code)


def warn(message: str) -> None:
    print("[WARN] " + message, file=sys.stderr)


def now_in_timezone(name: str) -> datetime:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(name))
        except Exception:
            pass
    if name in {"Asia/Shanghai", "UTC+08:00", "+08:00"}:
        return datetime.now(timezone(timedelta(hours=8)))
    return datetime.now(timezone.utc)


def read_text(path: Path) -> str:
    if not path.is_file():
        die("缺少文件: " + str(path))
    return path.read_text(encoding="utf-8-sig")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            if not content.endswith("\n"):
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
def project_lock(project_dir: Path, force_unlock: bool = False) -> Iterator[None]:
    """中文：防止共享任务记忆文件被意外并发写入。

    English: Prevent accidental concurrent writes to shared task-memory files.
    """
    lock_path = project_dir / ".checkpoint.lock"
    if force_unlock and lock_path.exists():
        lock_path.unlink()
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        die(
            "检测到检查点写入锁: {}。请确认没有其他主协调 Agent 正在写入；"
            "确认是崩溃遗留锁后可使用 --force-unlock。".format(lock_path)
        )
    try:
        payload = "pid={}\ntime={}\n".format(os.getpid(), datetime.now(timezone.utc).isoformat())
        os.write(fd, payload.encode("utf-8"))
        os.close(fd)
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def replace_field(text: str, label: str, value: str) -> str:
    pattern = re.compile(r"(?m)^- " + re.escape(label) + r"：.*$")
    replacement = "- " + label + "：" + value
    if pattern.search(text):
        return pattern.sub(lambda _: replacement, text, count=1)
    return text


def replace_field_if_blank(text: str, label: str, value: str) -> str:
    pattern = re.compile(r"(?m)^- " + re.escape(label) + r"：\s*$")
    replacement = "- " + label + "：" + value
    return pattern.sub(lambda _: replacement, text, count=1)


def field_value(text: str, label: str) -> str:
    match = re.search(r"(?m)^- " + re.escape(label) + r"：(.*?)\s*$", text)
    return match.group(1).strip() if match else ""


def entry_field(block: str, label: str) -> str:
    return field_value(block, label)


def section_text(block: str, heading: str) -> str:
    pattern = re.compile(
        r"(?ms)^#### " + re.escape(heading) + r"\s*\n(.*?)(?=^#### |\Z)"
    )
    match = pattern.search(block)
    return match.group(1).strip() if match else ""


def first_bullet(section: str) -> str:
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if value and value != "无":
                return value
    return ""


def bullet_lines(values: Optional[Iterable[str]]) -> str:
    items = [one_line(item) for item in (values or []) if item and item.strip()]
    return "\n".join("- " + item for item in items) if items else "- 无"


def one_line(value: str, limit: int = 1000) -> str:
    compact = " | ".join(line.strip() for line in value.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def validate_markers(text: str, begin: str, end: str, file_name: str) -> Tuple[int, int]:
    if text.count(begin) != 1 or text.count(end) != 1:
        die("{} 的标记缺失或重复: {} / {}".format(file_name, begin, end))
    start = text.index(begin) + len(begin)
    finish = text.index(end)
    if start > finish:
        die("{} 的标记顺序错误".format(file_name))
    return start, finish


def active_checkpoint_region(progress: str) -> Tuple[int, int, str]:
    start, end = validate_markers(progress, CHECKPOINTS_BEGIN, CHECKPOINTS_END, "PROGRESS.md")
    return start, end, progress[start:end]


def checkpoint_blocks(progress: str) -> List[Tuple[str, str]]:
    _, _, region = active_checkpoint_region(progress)
    matches = list(CHECKPOINT_RE.finditer(region))
    blocks: List[Tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(region)
        blocks.append((match.group(1), region[start:end].strip()))
    return blocks


def replace_active_region(progress: str, blocks: Sequence[str]) -> str:
    start, end, _ = active_checkpoint_region(progress)
    body = "\n\n".join(block.strip() for block in blocks if block.strip())
    replacement = "\n"
    if body:
        replacement += body + "\n"
    return progress[:start] + replacement + progress[end:]


def insert_checkpoint(progress: str, entry: str) -> str:
    blocks = [block for _, block in checkpoint_blocks(progress)]
    blocks.append(entry.strip())
    return replace_active_region(progress, blocks)


def append_archive_index(progress: str, checkpoint_range: str, relative_path: str, display_time: str) -> str:
    start, end = validate_markers(progress, ARCHIVE_INDEX_BEGIN, ARCHIVE_INDEX_END, "PROGRESS.md")
    region = progress[start:end]
    safe_path = relative_path.replace("|", "\\|")
    row = "| {} | `{}` | {} |".format(checkpoint_range, safe_path, display_time)
    new_region = region.rstrip() + "\n" + row + "\n"
    return progress[:start] + new_region + progress[end:]


def next_checkpoint_id(progress: str, timestamp: datetime) -> str:
    date_key = timestamp.strftime("%Y%m%d")
    seq = 0
    for checkpoint_id, date_part, number in CHECKPOINT_RE.findall(progress):
        del checkpoint_id
        if date_part == date_key:
            seq = max(seq, int(number))
    return "CP-{}-{:03d}".format(date_key, seq + 1)


def update_live_block(text: str, checkpoint_id: str, summary: str, blocked: str, next_action: str) -> str:
    start, end = validate_markers(text, LIVE_BEGIN, LIVE_END, "CURRENT_TASK.md")
    block = (
        "\n- 最近完成节点：{} - {}\n"
        "- 当前阻塞：{}\n"
        "- 下一步唯一行动：{}\n".format(
            checkpoint_id, one_line(summary), one_line(blocked) or "无", one_line(next_action)
        )
    )
    return text[:start] + block + text[end:]


def run_git(repo: Path, args: List[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo)] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def git_snapshot(repo_path: Optional[str]) -> Dict[str, str]:
    empty = {
        "repo": "",
        "branch": "",
        "head": "",
        "status": "",
        "diff_stat": "",
        "untracked": "",
        "fingerprint": "",
    }
    if not repo_path:
        return empty
    repo = Path(repo_path).expanduser().resolve()
    if run_git(repo, ["rev-parse", "--is-inside-work-tree"]) != "true":
        warn("不是 Git 工作区，跳过 Git 快照: " + str(repo))
        return empty
    branch = run_git(repo, ["branch", "--show-current"]) or "(detached)"
    head = run_git(repo, ["rev-parse", "HEAD"])
    status = run_git(repo, ["status", "--short", "--untracked-files=all"])
    diff_stat = run_git(repo, ["diff", "--stat", "HEAD", "--"])
    name_status = run_git(repo, ["diff", "--name-status", "HEAD", "--"])
    cached = run_git(repo, ["diff", "--cached", "--name-status", "HEAD", "--"])
    untracked_lines = [line[3:] for line in status.splitlines() if line.startswith("?? ")]
    fingerprint_payload = "\n".join([head, status, name_status, cached])
    fingerprint = hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()
    return {
        "repo": str(repo),
        "branch": branch,
        "head": head,
        "status": one_line(status) or "干净",
        "diff_stat": one_line(diff_stat) or "无",
        "untracked": ", ".join(untracked_lines) if untracked_lines else "无",
        "fingerprint": fingerprint,
    }


def apply_git_snapshot(current: str, snapshot: Dict[str, str]) -> str:
    if not snapshot.get("repo"):
        return current
    replacements = {
        "仓库路径": snapshot["repo"],
        "当前分支": snapshot["branch"],
        "当前 HEAD": snapshot["head"],
        "git status --short 摘要": snapshot["status"],
        "git diff --stat 摘要": snapshot["diff_stat"],
        "未跟踪文件": snapshot["untracked"],
        "工作区指纹": snapshot["fingerprint"],
        "工作区是否与最后检查点一致": "是",
    }
    for label, value in replacements.items():
        current = replace_field(current, label, value)
    return current


def ensure_external_directory(project_dir: Path, allow_inside_repo: bool) -> None:
    if allow_inside_repo:
        return
    if run_git(project_dir, ["rev-parse", "--is-inside-work-tree"]) == "true":
        die(
            "外部记忆目录位于 Git 工作区内。请改用仓库外的 <AGENT_CONTEXT_ROOT>，"
            "或在确实理解风险时显式传入 --allow-inside-repo。"
        )


def safe_path_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip("-.") or "task"


def archive_progress_text(
    progress: str,
    project_dir: Path,
    task_id: str,
    timestamp: datetime,
    hot_limit: int,
) -> Tuple[str, Optional[Path], int]:
    if hot_limit < 1:
        die("活跃检查点上限必须大于等于 1")
    blocks = checkpoint_blocks(progress)
    excess = len(blocks) - hot_limit
    if excess <= 0:
        return progress, None, 0

    archived = blocks[:excess]
    remaining = [block for _, block in blocks[excess:]]
    first_id = archived[0][0]
    last_id = archived[-1][0]
    task_dir = project_dir / "archive" / safe_path_component(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    archive_name = "PROGRESS-{}-{}.md".format(first_id, last_id)
    archive_path = task_dir / archive_name
    if archive_path.exists():
        archive_path = task_dir / (
            archive_path.stem + "-" + timestamp.strftime("%H%M%S") + archive_path.suffix
        )
    archive_content = (
        "# 已归档检查点\n\n"
        "- 任务标识：{}\n"
        "- 检查点范围：{} 至 {}\n"
        "- 归档时间：{}\n\n".format(
            task_id,
            first_id,
            last_id,
            timestamp.strftime("%Y-%m-%d %H:%M:%S %Z").strip(),
        )
        + "\n\n".join(block for _, block in archived)
        + "\n"
    )
    atomic_write(archive_path, archive_content)
    progress = replace_active_region(progress, remaining)
    relative = archive_path.relative_to(project_dir).as_posix()
    progress = append_archive_index(
        progress,
        "{} ～ {}".format(first_id, last_id),
        relative,
        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
    )
    return progress, archive_path, excess


def command_init(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).expanduser().resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    ensure_external_directory(project_dir, args.allow_inside_repo)
    templates = Path(__file__).resolve().parent.parent / "assets" / "templates"

    with project_lock(project_dir, args.force_unlock):
        mappings = {
            "CURRENT_TASK.template.md": "CURRENT_TASK.md",
            "PROGRESS.template.md": "PROGRESS.md",
            "PLAN.template.md": "PLAN.md",
        }
        created: List[Path] = []
        for source_name, target_name in mappings.items():
            target = project_dir / target_name
            if target.exists() and not args.force:
                continue
            source = templates / source_name
            if not source.is_file():
                die("模板不存在: " + str(source))
            shutil.copyfile(str(source), str(target))
            created.append(target)

        (project_dir / "reviews").mkdir(exist_ok=True)
        (project_dir / "archive").mkdir(exist_ok=True)
        timestamp = now_in_timezone(args.timezone)
        display_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        current_path = project_dir / "CURRENT_TASK.md"
        current = read_text(current_path)
        for label, value in {
            "任务标识": args.task_id,
            "创建时间": display_time,
            "最近更新时间": display_time,
            "统一时区": args.timezone,
        }.items():
            current = replace_field_if_blank(current, label, value)
        if args.force:
            current = replace_field(current, "任务标识", args.task_id)
            current = replace_field(current, "创建时间", display_time)
            current = replace_field(current, "最近更新时间", display_time)
            current = replace_field(current, "统一时区", args.timezone)
        if args.title:
            current = replace_field_if_blank(current, "本次目标", one_line(args.title))
        current = apply_git_snapshot(current, git_snapshot(args.repo_path))
        atomic_write(current_path, current)

        progress_path = project_dir / "PROGRESS.md"
        progress = read_text(progress_path)
        identity = args.title + " / " + args.task_id if args.title else args.task_id
        progress = replace_field_if_blank(progress, "项目 / 任务 / 标识", identity)
        progress = replace_field_if_blank(progress, "开始时间", display_time + " " + args.timezone)
        atomic_write(progress_path, progress)

        plan_path = project_dir / "PLAN.md"
        plan = read_text(plan_path)
        plan = replace_field_if_blank(plan, "项目 / 任务", one_line(args.title))
        plan = replace_field_if_blank(plan, "任务标识", args.task_id)
        atomic_write(plan_path, plan)

    print("[OK] 外部记忆目录: " + str(project_dir))
    for path in created:
        print("[OK] 已创建: " + path.name)
    if not created:
        print("[OK] 核心文档已存在，未覆盖。使用 --force 可按模板重新初始化。")


def checkpoint_payload_fingerprint(args: argparse.Namespace, snapshot: Dict[str, str]) -> str:
    """中文：为幂等检查点追加构建稳定摘要；时间和检查点 ID 不参与，除非显式强制，相同工作区与内容再次追加会成为 no-op。

    English: Build a stable digest for idempotent checkpoint appends. Time and checkpoint ID are excluded, so the same workspace and content become a no-op unless explicitly forced.
    """
    values: List[str] = [
        one_line(args.task_id),
        one_line(args.node_type),
        one_line(args.node_status),
        one_line(args.task_status),
        one_line(args.summary),
        one_line(args.next_action),
        one_line(args.blocked),
        one_line(args.stage),
        one_line(args.agent),
        one_line(snapshot.get("fingerprint", "")),
    ]
    for name in ("goal", "fact", "file", "command", "validation", "risk", "impact"):
        items = getattr(args, name, None) or []
        values.append(name + "=" + "\n".join(one_line(item) for item in items))
    return hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()


def build_checkpoint_entry(
    args: argparse.Namespace,
    checkpoint_id: str,
    state_version: int,
    display_time: str,
    snapshot: Dict[str, str],
) -> str:
    git_section = "- 未提供仓库路径"
    if snapshot.get("repo"):
        git_section = "\n".join(
            [
                "- 仓库：" + snapshot["repo"],
                "- 分支 / HEAD：" + snapshot["branch"] + " / " + snapshot["head"],
                "- 工作区指纹：" + snapshot["fingerprint"],
                "- 状态摘要：" + snapshot["status"],
                "- 差异摘要：" + snapshot["diff_stat"],
            ]
        )

    return """### {checkpoint_id}

- 时间：{display_time} {timezone}
- 状态版本：{state_version}
- 内容指纹：{content_fingerprint}
- 所属任务 / 阶段：{task_id} / {stage}
- 节点类型：{node_type}
- 执行 Agent：{agent}
- 节点状态：{node_status}

#### 本节点目标

{goal}

#### 实际完成

- {summary}

#### 已确认事实与证据

{fact}

#### 修改文件与关键位置

{file}

#### 实际命令与结果摘要

{command}

#### Git 与工作区快照

{git_section}

#### 验证、复审和环境状态

{validation}

#### 失败、阻塞、风险与未验证项

{risk}

#### 对计划、范围或授权的影响

{impact}

#### 下一步唯一行动

- {next_action}
""".format(
        checkpoint_id=checkpoint_id,
        display_time=display_time,
        timezone=args.timezone,
        state_version=state_version,
        content_fingerprint=checkpoint_payload_fingerprint(args, snapshot),
        task_id=one_line(args.task_id),
        stage=one_line(args.stage or "未指定"),
        node_type=one_line(args.node_type),
        agent=one_line(args.agent),
        node_status=one_line(args.node_status),
        goal=bullet_lines(args.goal),
        summary=one_line(args.summary),
        fact=bullet_lines(args.fact),
        file=bullet_lines(args.file),
        command=bullet_lines(args.command),
        git_section=git_section,
        validation=bullet_lines(args.validation),
        risk=bullet_lines(args.risk),
        impact=bullet_lines(args.impact),
        next_action=one_line(args.next_action),
    )


def command_append(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).expanduser().resolve()
    ensure_external_directory(project_dir, args.allow_inside_repo)
    with project_lock(project_dir, args.force_unlock):
        current_path = project_dir / "CURRENT_TASK.md"
        progress_path = project_dir / "PROGRESS.md"
        current = read_text(current_path)
        progress = read_text(progress_path)

        timestamp = now_in_timezone(args.timezone)
        display_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        current_state_match = STATE_VERSION_RE.search(current)
        state_version = int(current_state_match.group(1)) + 1 if current_state_match else 1
        snapshot = git_snapshot(args.repo_path)
        content_fingerprint = checkpoint_payload_fingerprint(args, snapshot)
        blocks = checkpoint_blocks(progress)
        if blocks and not args.force_append:
            last_fingerprint = entry_field(blocks[-1][1], "内容指纹")
            if last_fingerprint and last_fingerprint == content_fingerprint:
                print("[SKIP] 检查点内容和工作区均未变化，未重复写入。")
                return
        checkpoint_id = next_checkpoint_id(progress, timestamp)
        entry = build_checkpoint_entry(args, checkpoint_id, state_version, display_time, snapshot)

        progress = insert_checkpoint(progress, entry)
        progress = replace_field(progress, "当前状态", one_line(args.task_status))
        progress = replace_field(progress, "最近检查点 ID", checkpoint_id)
        progress = replace_field(progress, "下一步唯一行动", one_line(args.next_action))
        progress = replace_field(progress, "进行中", one_line(args.next_action))
        if args.node_status == "已完成":
            progress = replace_field(progress, "已完成", one_line(args.summary))
        blocked = one_line(args.blocked) or (
            one_line(args.summary) if args.node_status in {"阻塞", "失败"} else "无"
        )
        progress = replace_field(progress, "阻塞", blocked)
        progress, archive_path, archived_count = archive_progress_text(
            progress, project_dir, args.task_id, timestamp, args.hot_limit
        )

        # 中文：先持久化只追加证据；若 CURRENT_TASK 更新失败，修复流程可据此恢复。
        # English: Persist append-only evidence first so repair can recover if CURRENT_TASK update fails.
        atomic_write(progress_path, progress)

        current = replace_field(current, "状态版本", str(state_version))
        current = replace_field(current, "任务标识", one_line(args.task_id))
        current = replace_field(current, "最近更新时间", display_time)
        current = replace_field(current, "统一时区", args.timezone)
        current = replace_field(current, "最后检查点 ID", checkpoint_id)
        current = replace_field(current, "当前状态", one_line(args.task_status))
        current = replace_field(current, "当前节点", one_line(args.summary))
        current = replace_field(current, "未持久化已完成节点", "0")
        current = replace_field(current, "距离上次检查点的实质性动作", "0 / 8")
        if args.stage:
            current = replace_field(current, "当前阶段", one_line(args.stage))
        current = apply_git_snapshot(current, snapshot)
        current = update_live_block(current, checkpoint_id, args.summary, blocked, args.next_action)
        atomic_write(current_path, current)

        validate_state(project_dir, args.repo_path, strict_git=True, quiet=True)

    print("[OK] 已写入检查点: " + checkpoint_id)
    if archive_path:
        print("[OK] 已归档 {} 个旧检查点: {}".format(archived_count, archive_path))


def validate_state(
    project_dir: Path,
    repo_path: Optional[str],
    strict_git: bool,
    quiet: bool,
) -> Tuple[str, int]:
    current = read_text(project_dir / "CURRENT_TASK.md")
    progress = read_text(project_dir / "PROGRESS.md")
    blocks = checkpoint_blocks(progress)
    if not blocks:
        die("PROGRESS.md 尚无有效检查点")
    ids = [checkpoint_id for checkpoint_id, _ in blocks]
    if len(ids) != len(set(ids)):
        die("PROGRESS.md 存在重复检查点 ID")
    last_id, last_block = blocks[-1]
    current_id = field_value(current, "最后检查点 ID")
    progress_id = field_value(progress, "最近检查点 ID")
    if current_id != last_id:
        die("检查点不一致: CURRENT_TASK={}，PROGRESS 最后一条={}".format(current_id, last_id))
    if progress_id and progress_id != last_id:
        die("检查点不一致: PROGRESS 摘要={}，最后一条={}".format(progress_id, last_id))
    validate_markers(current, LIVE_BEGIN, LIVE_END, "CURRENT_TASK.md")
    live_start = current.index(LIVE_BEGIN)
    live_end = current.index(LIVE_END)
    next_action = field_value(current[live_start:live_end], "下一步唯一行动")
    if not next_action:
        die("CURRENT_TASK.md 缺少下一步唯一行动")
    state_version = int(field_value(current, "状态版本") or "0")
    entry_version = int(entry_field(last_block, "状态版本") or "0")
    if state_version != entry_version:
        die("状态版本不一致: CURRENT_TASK={}，最后检查点={}".format(state_version, entry_version))

    snapshot = git_snapshot(repo_path)
    if snapshot.get("repo"):
        recorded = field_value(current, "工作区指纹")
        if recorded and recorded != snapshot["fingerprint"]:
            message = "工作区已偏离最后检查点: recorded={} current={}".format(
                recorded, snapshot["fingerprint"]
            )
            if strict_git:
                die(message)
            warn(message)
    if not quiet:
        print("[OK] 检查点一致: {}，状态版本 {}".format(last_id, state_version))
    return last_id, state_version


def command_validate(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).expanduser().resolve()
    validate_state(project_dir, args.repo_path, args.strict_git, args.quiet)


def repair_current_from_last_checkpoint(
    project_dir: Path,
    repo_path: Optional[str],
    timezone_name: str,
) -> str:
    current_path = project_dir / "CURRENT_TASK.md"
    progress_path = project_dir / "PROGRESS.md"
    current = read_text(current_path)
    progress = read_text(progress_path)
    blocks = checkpoint_blocks(progress)
    if not blocks:
        die("没有可用于修复 CURRENT_TASK.md 的检查点")
    checkpoint_id, block = blocks[-1]
    state_version = int(entry_field(block, "状态版本") or "0")
    task_stage = entry_field(block, "所属任务 / 阶段")
    if " / " in task_stage:
        task_id, stage = task_stage.rsplit(" / ", 1)
    else:
        task_id, stage = task_stage, ""
    summary = first_bullet(section_text(block, "实际完成")) or "从最后检查点恢复"
    next_action = first_bullet(section_text(block, "下一步唯一行动"))
    if not next_action:
        die("最后检查点缺少下一步唯一行动，不能自动修复")
    node_status = entry_field(block, "节点状态")
    risk = first_bullet(section_text(block, "失败、阻塞、风险与未验证项"))
    blocked = risk if node_status in {"阻塞", "失败"} and risk else "无"
    display_time = now_in_timezone(timezone_name).strftime("%Y-%m-%d %H:%M:%S")

    current = replace_field(current, "状态版本", str(state_version))
    current = replace_field(current, "任务标识", task_id)
    current = replace_field(current, "最近更新时间", display_time)
    current = replace_field(current, "统一时区", timezone_name)
    current = replace_field(current, "最后检查点 ID", checkpoint_id)
    current = replace_field(current, "当前状态", field_value(progress, "当前状态") or "进行中")
    current = replace_field(current, "当前节点", summary)
    current = replace_field(current, "当前阶段", stage)
    current = replace_field(current, "未持久化已完成节点", "0")
    current = replace_field(current, "距离上次检查点的实质性动作", "0 / 8")
    current = apply_git_snapshot(current, git_snapshot(repo_path))
    current = update_live_block(current, checkpoint_id, summary, blocked, next_action)
    atomic_write(current_path, current)
    return checkpoint_id


def command_repair(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).expanduser().resolve()
    ensure_external_directory(project_dir, args.allow_inside_repo)
    with project_lock(project_dir, args.force_unlock):
        checkpoint_id = repair_current_from_last_checkpoint(
            project_dir, args.repo_path, args.timezone
        )
        validate_state(project_dir, args.repo_path, args.strict_git, quiet=True)
    print("[OK] 已根据最后检查点修复 CURRENT_TASK.md: " + checkpoint_id)


def command_archive(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).expanduser().resolve()
    ensure_external_directory(project_dir, args.allow_inside_repo)
    with project_lock(project_dir, args.force_unlock):
        progress_path = project_dir / "PROGRESS.md"
        progress = read_text(progress_path)
        task_id = args.task_id or field_value(read_text(project_dir / "CURRENT_TASK.md"), "任务标识")
        timestamp = now_in_timezone(args.timezone)
        progress, archive_path, count = archive_progress_text(
            progress, project_dir, task_id or "task", timestamp, args.hot_limit
        )
        if archive_path:
            atomic_write(progress_path, progress)
            print("[OK] 已归档 {} 个检查点: {}".format(count, archive_path))
        else:
            print("[OK] 活跃检查点未超过上限，无需归档。")


def command_recover(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).expanduser().resolve()
    last_id, state_version = validate_state(
        project_dir, args.repo_path, args.strict_git, quiet=True
    )
    current = read_text(project_dir / "CURRENT_TASK.md")
    progress = read_text(project_dir / "PROGRESS.md")
    blocks = checkpoint_blocks(progress)
    selected = blocks[-max(1, args.recent):]
    live_start = current.index(LIVE_BEGIN)
    live_end = current.index(LIVE_END)

    print("# 恢复摘要")
    print("- 任务标识: " + field_value(current, "任务标识"))
    print("- 当前状态: " + field_value(current, "当前状态"))
    print("- 当前阶段: " + field_value(current, "当前阶段"))
    print("- 当前分支 / HEAD: {} / {}".format(
        field_value(current, "当前分支"), field_value(current, "当前 HEAD")
    ))
    print("- 最后检查点: {} / 状态版本 {}".format(last_id, state_version))
    print("- 下一步唯一行动: " + field_value(
        current[live_start:live_end], "下一步唯一行动"
    ))
    print("\n## 最近检查点")
    for checkpoint_id, block in selected:
        summary = first_bullet(section_text(block, "实际完成")) or "未提取摘要"
        action = first_bullet(section_text(block, "下一步唯一行动")) or "未提取下一步"
        print("- {}: {} -> {}".format(checkpoint_id, summary, action))



def iter_memory_files(project_dir: Path) -> Iterator[Path]:
    for path in project_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name in {".checkpoint.lock"} or path.suffix.lower() not in {".md", ".json", ".txt"}:
            continue
        yield path


def sensitive_findings(project_dir: Path) -> List[str]:
    findings: List[str] = []
    for path in iter_memory_files(project_dir):
        try:
            content = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            findings.append("{}: 无法读取 ({})".format(path, exc))
            continue
        for line_no, line in enumerate(content.splitlines(), 1):
            for label, pattern in SENSITIVE_PATTERNS:
                for match in pattern.finditer(line):
                    value = match.group(0)
                    if "<" in value and ">" in value:
                        continue
                    if label == "Generic Secret" and len(match.group(2).strip("'\"")) < 8:
                        continue
                    findings.append("{}:{}: {}".format(path.relative_to(project_dir), line_no, label))
    return findings


def permission_findings(project_dir: Path) -> List[str]:
    if os.name == "nt":
        return []
    findings: List[str] = []
    directory_mode = project_dir.stat().st_mode & 0o777
    if directory_mode & 0o077:
        findings.append("目录权限过宽: {} (建议 700)".format(oct(directory_mode)))
    for path in iter_memory_files(project_dir):
        mode = path.stat().st_mode & 0o777
        if mode & 0o077:
            findings.append("文件权限过宽: {} {} (建议 600)".format(path.relative_to(project_dir), oct(mode)))
    return findings


def command_security_check(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).expanduser().resolve()
    if not project_dir.is_dir():
        die("外部记忆目录不存在: " + str(project_dir))
    findings = sensitive_findings(project_dir)
    permissions = permission_findings(project_dir)
    for item in findings:
        warn("疑似敏感信息: " + item)
    for item in permissions:
        warn(item)
    if findings or (permissions and args.strict_permissions):
        die("外部记忆安全检查未通过")
    if permissions:
        print("[WARN] 当前平台权限检查发现 {} 项；可执行 secure 收紧权限。".format(len(permissions)))
    print("[OK] 外部记忆安全检查通过；未发现可识别的明文凭据模式。")


def command_secure(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).expanduser().resolve()
    if os.name == "nt":
        warn("Windows ACL 不能由本脚本可靠统一设置；请确保目录仅当前账户可访问。")
        return
    with project_lock(project_dir, args.force_unlock):
        for path in sorted(project_dir.rglob("*")):
            if path.is_dir():
                os.chmod(path, 0o700)
            elif path.is_file():
                os.chmod(path, 0o600)
        os.chmod(project_dir, 0o700)
    print("[OK] 已将外部记忆目录收紧为目录 700、文件 600。")


def command_retention_report(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).expanduser().resolve()
    archive_dir = project_dir / "archive"
    if not archive_dir.exists():
        print("[OK] 没有 archive 目录，无保留期候选。")
        return
    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - args.days * 86400
    candidates = [path for path in archive_dir.rglob("*") if path.is_file() and path.stat().st_mtime < cutoff]
    print("# 外部记忆保留期报告")
    print("- 扫描目录: {}".format(archive_dir))
    print("- 保留阈值: {} 天".format(args.days))
    print("- 到期候选: {} 个".format(len(candidates)))
    for path in sorted(candidates):
        age = int((now - path.stat().st_mtime) / 86400)
        print("- {}（约 {} 天）".format(path.relative_to(project_dir), age))
    print("- 本命令只报告，不自动删除。删除、迁移或同步必须单独授权并遵循公司策略。")

def add_common_mutation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--allow-inside-repo", action="store_true")
    parser.add_argument("--force-unlock", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="维护长期任务 Markdown 检查点")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    init = sub.add_parser("init", help="初始化 CURRENT_TASK、PROGRESS、PLAN、reviews 和 archive")
    init.add_argument("--project-dir", required=True)
    init.add_argument("--task-id", required=True)
    init.add_argument("--title", default="")
    init.add_argument("--timezone", default="Asia/Shanghai")
    init.add_argument("--repo-path")
    init.add_argument("--force", action="store_true")
    add_common_mutation_args(init)
    init.set_defaults(func=command_init)

    append = sub.add_parser("append", help="追加检查点并刷新当前任务快照")
    append.add_argument("--project-dir", required=True)
    append.add_argument("--task-id", required=True)
    append.add_argument("--node-type", required=True)
    append.add_argument("--node-status", default="已完成")
    append.add_argument("--task-status", default="进行中")
    append.add_argument("--summary", required=True)
    append.add_argument("--next-action", required=True)
    append.add_argument("--blocked", default="")
    append.add_argument("--stage", default="")
    append.add_argument("--agent", default="主协调 Agent")
    append.add_argument("--timezone", default="Asia/Shanghai")
    append.add_argument("--repo-path")
    append.add_argument("--hot-limit", type=int, default=DEFAULT_HOT_LIMIT)
    append.add_argument("--force-append", action="store_true", help="即使内容指纹未变化也写入新检查点")
    add_common_mutation_args(append)
    for name in ("goal", "fact", "file", "command", "validation", "risk", "impact"):
        append.add_argument("--" + name, action="append")
    append.set_defaults(func=command_append)

    validate = sub.add_parser("validate", help="校验 CURRENT_TASK 与 PROGRESS，并可核对 Git 指纹")
    validate.add_argument("--project-dir", required=True)
    validate.add_argument("--repo-path")
    validate.add_argument("--strict-git", action="store_true")
    validate.add_argument("--quiet", action="store_true")
    validate.set_defaults(func=command_validate)

    recover = sub.add_parser("recover", help="校验状态并输出最近检查点恢复摘要")
    recover.add_argument("--project-dir", required=True)
    recover.add_argument("--repo-path")
    recover.add_argument("--strict-git", action="store_true")
    recover.add_argument("--recent", type=int, default=3)
    recover.set_defaults(func=command_recover)

    repair = sub.add_parser("repair", help="根据最后检查点修复 CURRENT_TASK 当前快照")
    repair.add_argument("--project-dir", required=True)
    repair.add_argument("--repo-path")
    repair.add_argument("--strict-git", action="store_true")
    repair.add_argument("--timezone", default="Asia/Shanghai")
    add_common_mutation_args(repair)
    repair.set_defaults(func=command_repair)

    archive = sub.add_parser("archive", help="归档超出热区上限的旧检查点")
    archive.add_argument("--project-dir", required=True)
    archive.add_argument("--task-id", default="")
    archive.add_argument("--hot-limit", type=int, default=DEFAULT_HOT_LIMIT)
    archive.add_argument("--timezone", default="Asia/Shanghai")
    add_common_mutation_args(archive)
    archive.set_defaults(func=command_archive)

    security = sub.add_parser("security-check", help="扫描疑似明文凭据并检查 POSIX 权限")
    security.add_argument("--project-dir", required=True)
    security.add_argument("--strict-permissions", action="store_true")
    security.set_defaults(func=command_security_check)

    secure = sub.add_parser("secure", help="在 POSIX 上将目录收紧为 700、文件收紧为 600")
    secure.add_argument("--project-dir", required=True)
    secure.add_argument("--force-unlock", action="store_true")
    secure.set_defaults(func=command_secure)

    retention = sub.add_parser("retention-report", help="只读列出超过保留期的归档候选")
    retention.add_argument("--project-dir", required=True)
    retention.add_argument("--days", type=int, default=90)
    retention.set_defaults(func=command_retention_report)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
