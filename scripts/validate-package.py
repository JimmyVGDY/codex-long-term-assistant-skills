#!/usr/bin/env python3
"""Validate V4.2 structure, scripts, regression tests and isolated installation."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = "codex"
VERSION = "4.2.0"
ERRORS: list[str] = []


def fail(message: str) -> None:
    ERRORS.append(message)
    print("[FAIL]", message)


def run(
    command: list[str],
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    expected: int = 0,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        env=env,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != expected:
        fail(
            "命令结果异常: {}\nSTDOUT:\n{}\nSTDERR:\n{}".format(
                " ".join(map(str, command)), result.stdout, result.stderr
            )
        )
    return result


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


manifest = json.loads(read(ROOT / "manifest.json"))
skills = {item["name"] for item in manifest["skills"]}
if manifest.get("version") != VERSION:
    fail("manifest version 不是 " + VERSION)
if len(skills) != 9:
    fail("Skill 数量不是 9")
if len(manifest.get("custom_agents", [])) != 7:
    fail("自定义 Reviewer 数量不是 7")

for name in skills:
    skill_dir = ROOT / "skills" / name
    if not (skill_dir / "SKILL.md").is_file():
        fail("缺少 Skill " + name)
    if PLATFORM == "codex" and not (skill_dir / "agents" / "openai.yaml").is_file():
        fail("缺少 openai.yaml " + name)

for markdown in ROOT.rglob("*.md"):
    if len(re.findall(r"^```", read(markdown), re.M)) % 2:
        fail("代码块未闭合 " + str(markdown.relative_to(ROOT)))

for script in ROOT.rglob("*.py"):
    try:
        compile(read(script), str(script), "exec")
    except Exception as exc:  # pragma: no cover - validation output path
        fail("Python 语法 {}: {}".format(script.relative_to(ROOT), exc))

required = [
    "skills/engineering-quality-delivery/scripts/execution_guard.py",
    "skills/multi-agent-independent-review/scripts/review_packet.py",
    "skills/multi-agent-independent-review/scripts/review_controller.py",
    "skills/multi-agent-independent-review/references/reviewer-model-routing.md",
    "skills/long-running-task-memory/scripts/checkpoint.py",
    "scripts/package_manager.py",
    "scripts/semantic-lint.py",
    "config/agents.example.toml",
    "docs/CODEX_CONFIG_GUIDE.md",
    "docs/MODEL_ROUTING_AND_COST_POLICY.md",
    "docs/V4_2_COST_FLOW_OPTIMIZATION.md",
    "docs/SUBAGENT_INDEPENDENT_CONTEXT.md",
]
for relative in required:
    if not (ROOT / relative).is_file():
        fail("缺少 " + relative)

progressive_indexes = [
    "skills/java-backend-engineering/references/java-backend-rules.md",
    "skills/python-backend-ai-engineering/references/python-backend-ai-rules.md",
    "skills/data-middleware-ai-infrastructure/references/data-middleware-ai-infrastructure-rules.md",
    "skills/engineering-quality-delivery/references/engineering-quality-delivery-workflow.md",
    "skills/log-observability-analysis/references/log-observability-analysis-workflow.md",
    "skills/long-running-task-memory/references/long-running-task-memory-rules.md",
    "skills/multi-agent-independent-review/references/multi-agent-independent-review-workflow.md",
    "skills/technical-document-writing/references/technical-document-writing-rules.md",
]
for relative in progressive_indexes:
    if len(read(ROOT / relative).splitlines()) > 120:
        fail("索引过长 " + relative)

# Unit and regression tests.
for test in [
    ROOT / "skills/frontend-engineering/tests/test_detect_frontend_stack.py",
    ROOT / "skills/engineering-quality-delivery/tests/test_execution_guard.py",
    ROOT / "skills/multi-agent-independent-review/tests/test_review_tools.py",
    ROOT / "skills/long-running-task-memory/tests/test_checkpoint_dedupe.py",
]:
    run(
        [sys.executable, "-B", str(test)],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
run(
    [sys.executable, "-B", str(ROOT / "scripts/semantic-lint.py")],
    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
)
run(
    [sys.executable, "-B", str(ROOT / "scripts/routing-eval.py"), "validate"],
    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
)

# Package manager isolated test: dry-run, install, verify, idempotent reinstall, doctor, restore.
with tempfile.TemporaryDirectory(prefix="v42-install-") as temp:
    home = Path(temp) / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"}
    env["CODEX_HOME"] = str(home / ".codex")
    manager = ROOT / "scripts/package_manager.py"
    run([sys.executable, "-B", str(manager), "install", "--dry-run"], env=env)
    run([sys.executable, "-B", str(manager), "install"], env=env)
    run([sys.executable, "-B", str(manager), "verify"], env=env)
    run([sys.executable, "-B", str(manager), "install"], env=env)
    run([sys.executable, "-B", str(manager), "verify"], env=env)
    run([sys.executable, "-B", str(manager), "doctor"], env=env)
    run([sys.executable, "-B", str(manager), "restore"], env=env)

# Bash wrapper integration in an isolated HOME/CODEX_HOME.
with tempfile.TemporaryDirectory(prefix="v42-wrapper-") as temp:
    home = Path(temp) / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"}
    env["CODEX_HOME"] = str(home / ".codex")
    run(["bash", str(ROOT / "scripts/install-user.sh"), "all", "--dry-run"], env=env)
    run(["bash", str(ROOT / "scripts/install-user.sh"), "all"], env=env)
    run(["bash", str(ROOT / "scripts/verify-user-install.sh")], env=env)
    run(["bash", str(ROOT / "scripts/doctor.sh")], env=env)
    run(["bash", str(ROOT / "scripts/restore-latest-backup.sh")], env=env)

for shell_script in ROOT.glob("scripts/*.sh"):
    run(["bash", "-n", str(shell_script)])

# Release checksum coverage and integrity. CHECKSUMS.sha256 excludes itself and .git.
checksum_file = ROOT / "CHECKSUMS.sha256"
if not checksum_file.is_file():
    fail("缺少 CHECKSUMS.sha256")
else:
    declared: dict[str, str] = {}
    for line_no, raw_line in enumerate(read(checksum_file).splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            fail("CHECKSUMS.sha256 第 {} 行格式错误".format(line_no))
            continue
        declared[parts[1]] = parts[0]
    actual_paths = {
        path.relative_to(ROOT).as_posix(): path
        for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.relative_to(ROOT).parts
        and path.name != "CHECKSUMS.sha256"
        and path.suffix != ".pyc"
        and "__pycache__" not in path.relative_to(ROOT).parts
    }
    missing = sorted(set(actual_paths) - set(declared))
    extra = sorted(set(declared) - set(actual_paths))
    if missing:
        fail("CHECKSUMS.sha256 缺少文件: " + ", ".join(missing[:10]))
    if extra:
        fail("CHECKSUMS.sha256 包含不存在文件: " + ", ".join(extra[:10]))
    for relative, path in actual_paths.items():
        expected_hash = declared.get(relative)
        if not expected_hash:
            continue
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            fail("校验和不匹配 " + relative)

if any(ROOT.rglob("__pycache__")) or any(ROOT.rglob("*.pyc")):
    fail("包内存在 Python 缓存残留")

if ERRORS:
    print("验证失败", len(ERRORS))
    raise SystemExit(1)
print("V4.2 安装包验证通过。")
