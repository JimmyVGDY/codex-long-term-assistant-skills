#!/usr/bin/env python3
"""Validate V5.1 structure, contracts, regressions and isolated installation."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = "codex"
VERSION = "5.1.0"
ERRORS: List[str] = []
COMMAND_TIMEOUT_SECONDS = 240


def fail(message: str) -> None:
    ERRORS.append(message)
    print("[FAIL]", message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def run(
    command: List[str],
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[Path] = None,
    expected: int = 0,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            env=env,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        fail("命令超时（{} 秒）: {}".format(COMMAND_TIMEOUT_SECONDS, " ".join(map(str, command))))
        return subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "")
    if result.returncode != expected:
        fail(
            "命令结果异常: {}\nSTDOUT:\n{}\nSTDERR:\n{}".format(
                " ".join(map(str, command)), result.stdout, result.stderr
            )
        )
    return result


def release_tree_sha256() -> str:
    digest = hashlib.sha256()
    for path in sorted(ROOT.rglob("*"), key=lambda item: item.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT)
        if ".git" in relative.parts or "__pycache__" in relative.parts or path.name == "CHECKSUMS.sha256":
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        name = relative.as_posix()
        digest.update(name.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"L")
            digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        elif path.is_file():
            digest.update(b"F")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        elif path.is_dir():
            digest.update(b"D")
        digest.update(b"\0")
    return digest.hexdigest()


initial_tree_hash = release_tree_sha256()
manifest = json.loads(read(ROOT / "manifest.json"))
skills = {item["name"] for item in manifest.get("skills", [])}
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

required = [
    "runtime/cp_runtime/__init__.py",
    "runtime/cp_runtime/contracts.py",
    "runtime/cp_runtime/common.py",
    "runtime/cp_runtime/project.py",
    "runtime/cp_runtime/approval.py",
    "runtime/cp_runtime/evidence.py",
    "runtime/cp_runtime/finalization.py",
    "runtime/cp_runtime/memory.py",
    "runtime/cp_runtime/feedback.py",
    "runtime/cp_runtime/cli.py",
    "runtime/tests/test_cp_runtime.py",
    "scripts/cp-runtime.py",
    "skills/engineering-quality-delivery/scripts/execution_guard.py",
    "skills/engineering-quality-delivery/tests/test_execution_guard_v5.py",
    "skills/multi-agent-independent-review/scripts/review_packet.py",
    "skills/multi-agent-independent-review/scripts/review_controller.py",
    "skills/long-running-task-memory/scripts/checkpoint.py",
    "scripts/package_manager.py",
    "scripts/semantic-lint.py",
    "tests/test_package_manager_security.py",
    "config/agents.example.toml",
    "docs/V5_0_PROJECT_GOVERNANCE_AND_EVIDENCE_CLOSURE.md",
    "docs/V5.0_升级说明与迁移指南.md",
    "docs/PROJECT_CONTEXT_AND_ONBOARDING.md",
    "docs/APPROVAL_EVIDENCE_FINALIZATION.md",
    "docs/AUTHORITY_REGISTRY.md",
    "runtime/cp_runtime/evolution/__init__.py",
    "runtime/cp_runtime/evolution/contracts.py",
    "runtime/cp_runtime/evolution/redaction.py",
    "runtime/cp_runtime/evolution/storage.py",
    "runtime/cp_runtime/evolution/observation.py",
    "runtime/cp_runtime/evolution/analysis.py",
    "runtime/cp_runtime/evolution/proposal.py",
    "runtime/cp_runtime/evolution/registry.py",
    "runtime/cp_runtime/evolution/service.py",
    "runtime/cp_runtime/evolution/cli.py",
    "runtime/cp_runtime/evolution/manifest.json",
    "config/evolution-policy.json",
    "scripts/evolution.py",
    "scripts/evolution.ps1",
    "scripts/evolution.cmd",
    "scripts/validate-v51-evolution.py",
    "tests/test_v51_controlled_evolution.py",
    "docs/V5.1_升级说明与迁移指南.md",
    "docs/evolution/SELF_EVOLUTION_ARCHITECTURE.md",
    "docs/evolution/CONTROLLED_EVOLUTION_OPERATIONS.md",
]
for relative in required:
    if not (ROOT / relative).is_file():
        fail("缺少 " + relative)

for path in ROOT.rglob("*"):
    if path.is_symlink():
        fail("发布包不得包含符号链接: " + str(path.relative_to(ROOT)))

for markdown in ROOT.rglob("*.md"):
    if len(re.findall(r"^```", read(markdown), re.M)) % 2:
        fail("代码块未闭合 " + str(markdown.relative_to(ROOT)))

for script in ROOT.rglob("*.py"):
    try:
        compile(read(script), str(script), "exec")
    except Exception as exc:  # pragma: no cover - validation output path
        fail("Python 语法 {}: {}".format(script.relative_to(ROOT), exc))

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

# Narrow release-secret scan. Generic placeholders and test fixtures are intentionally not treated as credentials.
secret_patterns = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "aws-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
}
for path in ROOT.rglob("*"):
    if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".zip"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    for name, pattern in secret_patterns.items():
        if pattern.search(text):
            fail("疑似真实凭据 {} in {}".format(name, path.relative_to(ROOT)))

base_env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "GIT_PAGER": "cat", "PAGER": "cat"}
for test in [
    ROOT / "runtime/tests/test_cp_runtime.py",
    ROOT / "skills/frontend-engineering/tests/test_detect_frontend_stack.py",
    ROOT / "skills/engineering-quality-delivery/tests/test_execution_guard.py",
    ROOT / "skills/engineering-quality-delivery/tests/test_execution_guard_v5.py",
    ROOT / "skills/multi-agent-independent-review/tests/test_review_tools.py",
    ROOT / "skills/long-running-task-memory/tests/test_checkpoint_dedupe.py",
    ROOT / "tests/test_package_manager_security.py",
    ROOT / "tests/test_v51_controlled_evolution.py",
]:
    run([sys.executable, "-B", str(test)], env=base_env)

run([sys.executable, "-B", str(ROOT / "scripts/validate-v51-evolution.py")], env=base_env)
run([sys.executable, "-B", str(ROOT / "scripts/semantic-lint.py")], env=base_env)
run([sys.executable, "-B", str(ROOT / "scripts/routing-eval.py"), "validate"], env=base_env)

# Package manager isolated test: dry-run, install, verify, idempotent reinstall, doctor and restore.
with tempfile.TemporaryDirectory(prefix="v51-install-") as temp:
    home = Path(temp) / "home"
    home.mkdir()
    env = {**base_env, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}
    manager = ROOT / "scripts/package_manager.py"
    run([sys.executable, "-B", str(manager), "install", "--dry-run"], env=env)
    run([sys.executable, "-B", str(manager), "install"], env=env)
    run([sys.executable, "-B", str(manager), "verify"], env=env)
    run([sys.executable, "-B", str(manager), "install"], env=env)
    run([sys.executable, "-B", str(manager), "verify"], env=env)
    run([sys.executable, "-B", str(home / ".codex" / "tools" / "evolution.py"), "--help"], env=env)
    run([sys.executable, "-B", str(manager), "doctor"], env=env)
    run([sys.executable, "-B", str(manager), "restore"], env=env)

# Bash wrappers in an isolated HOME/CODEX_HOME.
with tempfile.TemporaryDirectory(prefix="v51-wrapper-") as temp:
    home = Path(temp) / "home"
    home.mkdir()
    env = {**base_env, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}
    run(["bash", str(ROOT / "scripts/install-user.sh"), "all", "--dry-run"], env=env)
    run(["bash", str(ROOT / "scripts/install-user.sh"), "all"], env=env)
    run(["bash", str(ROOT / "scripts/verify-user-install.sh")], env=env)
    run(["bash", str(ROOT / "scripts/doctor.sh")], env=env)
    run(["bash", str(ROOT / "scripts/restore-latest-backup.sh")], env=env)

for shell_script in ROOT.glob("scripts/*.sh"):
    run(["bash", "-n", str(shell_script)], env=base_env)

if release_tree_sha256() != initial_tree_hash:
    fail("测试或校验过程修改了发布源码树")

# Release checksum coverage and integrity. CHECKSUMS.sha256 excludes itself and caches.
checksum_file = ROOT / "CHECKSUMS.sha256"
if not checksum_file.is_file():
    fail("缺少 CHECKSUMS.sha256")
else:
    declared: Dict[str, str] = {}
    for line_no, raw_line in enumerate(read(checksum_file).splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            fail("CHECKSUMS.sha256 第 {} 行格式错误".format(line_no))
            continue
        if parts[1] in declared:
            fail("CHECKSUMS.sha256 重复路径: " + parts[1])
        declared[parts[1]] = parts[0]
    actual_paths = {
        path.relative_to(ROOT).as_posix(): path
        for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.relative_to(ROOT).parts
        and path.name != "CHECKSUMS.sha256"
        and path.suffix not in {".pyc", ".pyo"}
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
        if expected_hash and hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            fail("校验和不匹配 " + relative)

if any(ROOT.rglob("__pycache__")) or any(ROOT.rglob("*.pyc")) or any(ROOT.rglob("*.pyo")):
    fail("包内存在 Python 缓存残留")

if ERRORS:
    print("验证失败", len(ERRORS))
    raise SystemExit(1)
print("V5.1 安装包验证通过。")
