#!/usr/bin/env python3
"""Validate the Codex cross-project assistant package.

The validator is read-only for the package. Runtime tests use isolated temporary
HOME, CODEX_HOME, repositories, and external-memory directories.
"""
from __future__ import annotations

import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

try:
    import tomllib
except ImportError as exc:  # pragma: no cover - Python < 3.11
    raise SystemExit("Python 3.11+ is required to validate TOML files") from exc

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_VERSION = "3.0.0"
EXPECTED_SKILLS = {
    "java-backend-engineering",
    "python-backend-ai-engineering",
    "vue-frontend-engineering",
    "data-middleware-ai-infrastructure",
    "engineering-quality-delivery",
    "multi-agent-independent-review",
    "technical-document-writing",
    "long-running-task-memory",
}
EXPECTED_AGENTS = {
    "cp_review_functional_business": "cp-review-functional-business.toml",
    "cp_review_compatibility_regression": "cp-review-compatibility-regression.toml",
    "cp_review_security_access": "cp-review-security-access.toml",
    "cp_review_performance_resources": "cp-review-performance-resources.toml",
    "cp_review_data_contract": "cp-review-data-contract.toml",
    "cp_review_state_concurrency": "cp-review-state-concurrency.toml",
    "cp_review_test_delivery": "cp-review-test-delivery.toml",
}
DOC_TEMPLATES = {
    "TECHNICAL_SOLUTION.template.md",
    "ARCHITECTURE_DESIGN.template.md",
    "IMPLEMENTATION_PLAN.template.md",
    "API_DESIGN.template.md",
    "DATABASE_DESIGN.template.md",
    "DEPLOYMENT_RUNBOOK.template.md",
    "INCIDENT_REPORT.template.md",
    "CODE_REVIEW_REPORT.template.md",
    "PROJECT_PROGRESS_REPORT.template.md",
    "TECHNICAL_SELECTION.template.md",
    "README.template.md",
    "MANAGEMENT_REPORT.template.md",
}
MEMORY_TEMPLATES = {
    "PROJECT_CONTEXT.template.md",
    "CURRENT_TASK.template.md",
    "PLAN.template.md",
    "PROGRESS.template.md",
    "DECISIONS.template.md",
    "HANDOFF.template.md",
    "KNOWN_ISSUES.template.md",
    "DELIVERY_RECORD.template.md",
    "CHECKPOINT_ENTRY.template.md",
    "RECOVERY_CHECKLIST.template.md",
}
REVIEW_TEMPLATES = {
    "REVIEW_PLAN.template.md",
    "REVIEW_RESULT.template.md",
    "REVIEW_LEDGER.template.md",
}
REQUIRED_SCRIPTS = {
    "install-user.ps1",
    "install-user.sh",
    "verify-user-install.ps1",
    "verify-user-install.sh",
    "uninstall-user.ps1",
    "uninstall-user.sh",
    "install-repo-skills.ps1",
    "install-repo-skills.sh",
    "uninstall-repo-skills.ps1",
    "uninstall-repo-skills.sh",
    "validate-package.py",
}
REQUIRED_GLOBAL_PHRASES = {
    "$multi-agent-independent-review",
    "$long-running-task-memory",
    "最大逻辑递归深度 3",
    "最大复审轮次 3",
    "最大并行 Reviewer 6",
    "Reviewer 总量 12",
    "每完成一个可独立恢复的小节点",
    "已完成节点不得只存在于当前聊天上下文",
}
PERSONAL_PATH_PATTERNS = (
    r"C:\\Users\\Example(?:\\|$)",
    r"/home/example(?:/|$)",
    r"/mnt/c/Users/Example(?:/|$)",
)

ERRORS: List[str] = []
WARNINGS: List[str] = []


def error(message: str) -> None:
    ERRORS.append(message)
    print("[FAIL] " + message)


def warn(message: str) -> None:
    WARNINGS.append(message)
    print("[WARN] " + message)


def ok(message: str) -> None:
    print("[OK] " + message)


def read(path: Path) -> str:
    if not path.is_file():
        error("缺少文件: " + str(path.relative_to(ROOT)))
        return ""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        error("文件不是有效 UTF-8: {} ({})".format(path.relative_to(ROOT), exc))
        return ""


def run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Dict[str, str] | None = None,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if expect_success and result.returncode != 0:
        error(
            "命令失败: {}\nstdout:\n{}\nstderr:\n{}".format(
                " ".join(command), result.stdout, result.stderr
            )
        )
    return result


def validate_markdown_fences(path: Path, text: str) -> None:
    if len(re.findall(r"^```", text, flags=re.MULTILINE)) % 2:
        error("Markdown 代码块未闭合: " + str(path.relative_to(ROOT)))


def parse_frontmatter(path: Path, text: str) -> Tuple[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, flags=re.DOTALL)
    if not match:
        error("SKILL.md 缺少 YAML Frontmatter: " + str(path.relative_to(ROOT)))
        return "", ""
    meta = match.group(1)
    name_match = re.search(r"(?m)^name:\s*([^\n]+?)\s*$", meta)
    description_match = re.search(
        r"(?ms)^description:\s*(?:>-\s*\n(?P<folded>(?:[ \t]+.*\n?)+)|(?P<plain>[^\n]+))",
        meta,
    )
    if not name_match or not description_match:
        error("SKILL.md 缺少 name 或 description: " + str(path.relative_to(ROOT)))
        return "", ""
    name = name_match.group(1).strip().strip("\"'")
    raw_description = description_match.group("folded") or description_match.group("plain") or ""
    description = " ".join(line.strip() for line in raw_description.splitlines()).strip()
    return name, description


def validate_openai_yaml(path: Path, text: str) -> None:
    required = (
        r"(?m)^interface:\s*$",
        r"(?m)^\s+display_name:\s*.+$",
        r"(?m)^\s+short_description:\s*.+$",
        r"(?m)^policy:\s*$",
        r"(?m)^\s+allow_implicit_invocation:\s*(true|false)\s*$",
    )
    for pattern in required:
        if not re.search(pattern, text):
            error("openai.yaml 缺少字段 {}: {}".format(pattern, path.relative_to(ROOT)))


def validate_manifest() -> Dict[str, object]:
    path = ROOT / "manifest.json"
    try:
        manifest = json.loads(read(path))
    except json.JSONDecodeError as exc:
        error("manifest.json 不是有效 JSON: " + str(exc))
        return {}
    if manifest.get("version") != EXPECTED_VERSION:
        error("manifest.json 版本不是 " + EXPECTED_VERSION)
    skill_names = {
        item.get("name") for item in manifest.get("skills", []) if isinstance(item, dict)
    }
    if skill_names != EXPECTED_SKILLS:
        error("manifest Skills 不一致: {}".format(sorted(name for name in skill_names if name)))
    agent_mapping = {
        item.get("name"): Path(str(item.get("file", ""))).name
        for item in manifest.get("custom_agents", [])
        if isinstance(item, dict)
    }
    if agent_mapping != EXPECTED_AGENTS:
        error("manifest 自定义 Agent 不一致: {}".format(agent_mapping))
    limits = manifest.get("quality_limits", {})
    expected_limits = {
        "max_review_agent_depth": 3,
        "max_review_rounds": 3,
        "max_parallel_reviewers": 6,
        "max_total_review_agents_per_boundary": 12,
        "max_repair_rounds": 3,
        "max_unpersisted_completed_nodes": 0,
        "max_substantive_actions_without_checkpoint": 5,
        "recent_checkpoints_to_load": 5,
        "hot_progress_checkpoint_limit": 30,
        "single_memory_writer": True,
    }
    for key, expected in expected_limits.items():
        if limits.get(key) != expected:
            error("manifest quality_limits.{} 应为 {}".format(key, expected))
    ok("manifest.json: version 3.0.0，8 Skills，7 Reviewer")
    return manifest


def validate_global_agents() -> None:
    path = ROOT / "global" / "AGENTS.md"
    text = read(path)
    begin = "<!-- codex-cross-project-assistant:begin -->"
    end = "<!-- codex-cross-project-assistant:end -->"
    if text.count(begin) != 1 or text.count(end) != 1:
        error("全局 AGENTS.md 受管标记必须各出现一次")
    if text.find(begin) > text.find(end):
        error("全局 AGENTS.md 受管标记顺序错误")
    size = len(text.encode("utf-8"))
    if size > 24 * 1024:
        error("全局 AGENTS.md 超过 24 KiB: {} bytes".format(size))
    for phrase in REQUIRED_GLOBAL_PHRASES:
        if phrase not in text:
            error("全局 AGENTS.md 缺少关键规则: " + phrase)
    validate_markdown_fences(path, text)
    ok("全局 AGENTS.md: {} bytes".format(size))


def validate_skills() -> None:
    skills_root = ROOT / "skills"
    actual = {path.name for path in skills_root.iterdir() if path.is_dir()}
    if actual != EXPECTED_SKILLS:
        error("实际 Skills 目录不一致: {}".format(sorted(actual)))
    for expected_name in sorted(EXPECTED_SKILLS):
        skill_dir = skills_root / expected_name
        skill_file = skill_dir / "SKILL.md"
        text = read(skill_file)
        name, description = parse_frontmatter(skill_file, text)
        if name != expected_name:
            error("Skill 目录名与 name 不一致: {} != {}".format(expected_name, name))
        if not description:
            error("Skill description 为空: " + expected_name)
        if len(description) > 500:
            error("Skill description 过长: {} ({} chars)".format(expected_name, len(description)))
        validate_markdown_fences(skill_file, text)
        yaml_path = skill_dir / "agents" / "openai.yaml"
        validate_openai_yaml(yaml_path, read(yaml_path))
        for relative in re.findall(r"`((?:references|assets|scripts)/[^`]+)`", text):
            if not (skill_dir / relative).exists():
                error("Skill 引用不存在: {}/{}".format(expected_name, relative))
        ok("Skill: " + expected_name)


def validate_custom_agents() -> None:
    manifest_files = set(EXPECTED_AGENTS.values())
    actual_files = {path.name for path in (ROOT / "custom-agents").glob("*.toml")}
    if actual_files != manifest_files:
        error("实际 Reviewer TOML 不一致: {}".format(sorted(actual_files)))
    for agent_name, file_name in sorted(EXPECTED_AGENTS.items()):
        path = ROOT / "custom-agents" / file_name
        try:
            data = tomllib.loads(read(path))
        except tomllib.TOMLDecodeError as exc:
            error("Reviewer TOML 解析失败 {}: {}".format(file_name, exc))
            continue
        if data.get("name") != agent_name:
            error("Reviewer name 不一致: {} != {}".format(file_name, data.get("name")))
        for field in ("description", "developer_instructions"):
            if not isinstance(data.get(field), str) or not data.get(field, "").strip():
                error("Reviewer 缺少 {}: {}".format(field, file_name))
        if data.get("sandbox_mode") != "read-only":
            error("Reviewer 必须使用 read-only: " + file_name)
        instructions = str(data.get("developer_instructions", ""))
        if "禁止" not in instructions or "派生其他 Agent" not in instructions:
            error("Reviewer 缺少禁止写入或禁止递归约束: " + file_name)
        ok("只读 Reviewer: " + agent_name)

    config_path = ROOT / "config" / "agents.example.toml"
    try:
        config = tomllib.loads(read(config_path))
    except tomllib.TOMLDecodeError as exc:
        error("agents.example.toml 解析失败: " + str(exc))
        return
    agents = config.get("agents", {})
    if agents.get("enabled") is not True:
        error("agents.example.toml 应启用 agents.enabled")
    if agents.get("max_concurrent_threads_per_session") != 6:
        error("agents.example.toml 并发上限应为 6")
    ok("Agent 配置示例")


def validate_template_set(relative_dir: str, expected: Iterable[str], label: str) -> None:
    directory = ROOT / relative_dir
    actual = {path.name for path in directory.glob("*.md")}
    missing = set(expected) - actual
    if missing:
        error("缺少{}: {}".format(label, sorted(missing)))
    ok("{}: {} 个".format(label, len(actual)))


def validate_markdown_and_paths() -> None:
    for path in ROOT.rglob("*.md"):
        text = read(path)
        validate_markdown_fences(path, text)
        for pattern in PERSONAL_PATH_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                error("发现硬编码个人路径: {} ({})".format(path.relative_to(ROOT), pattern))
    ok("Markdown 代码块与个人路径检查")


def validate_shell_scripts() -> None:
    actual_scripts = {path.name for path in (ROOT / "scripts").iterdir() if path.is_file()}
    missing = REQUIRED_SCRIPTS - actual_scripts
    if missing:
        error("缺少安装或验证脚本: {}".format(sorted(missing)))
    for path in sorted((ROOT / "scripts").glob("*.sh")):
        result = run(["bash", "-n", str(path)], expect_success=False)
        if result.returncode != 0:
            error("Shell 语法错误 {}: {}".format(path.name, result.stderr.strip()))
        else:
            ok("Shell 语法: " + path.name)


def strip_ps_strings_and_comments(text: str) -> str:
    text = re.sub(r"(?m)#.*$", "", text)
    text = re.sub(r"'(?:''|[^'])*'", "''", text)
    text = re.sub(r'"(?:`.|[^"`])*"', '""', text)
    return text


def validate_powershell_scripts() -> None:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    for path in sorted((ROOT / "scripts").glob("*.ps1")):
        text = read(path)
        if "[CmdletBinding()]" not in text or "$ErrorActionPreference" not in text:
            error("PowerShell 脚本缺少基础结构: " + path.name)
        stripped = strip_ps_strings_and_comments(text)
        for left, right, label in (("{", "}", "大括号"), ("(", ")", "圆括号")):
            if stripped.count(left) != stripped.count(right):
                error("PowerShell {}不平衡: {}".format(label, path.name))
        if powershell:
            escaped = str(path).replace("'", "''")
            command = (
                "$tokens=$null; $errors=$null; "
                "[System.Management.Automation.Language.Parser]::ParseFile('{}', [ref]$tokens, [ref]$errors) | Out-Null; "
                "if ($errors.Count -gt 0) {{ $errors | ForEach-Object {{ Write-Error $_.Message }}; exit 1 }}"
            ).format(escaped)
            result = run([powershell, "-NoProfile", "-Command", command], expect_success=False)
            if result.returncode != 0:
                error("PowerShell 解析失败 {}: {}".format(path.name, result.stderr.strip()))
            else:
                ok("PowerShell 解析: " + path.name)
        else:
            ok("PowerShell 静态结构: " + path.name)
    if not powershell:
        warn("当前环境没有 PowerShell；未执行 Windows PowerShell 解析器和实机安装。")


def git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "validator"], cwd=repo)
    run(["git", "config", "user.email", "validator@example.com"], cwd=repo)
    (repo / "app.txt").write_text("initial\n", encoding="utf-8")
    run(["git", "add", "app.txt"], cwd=repo)
    run(["git", "commit", "-qm", "initial"], cwd=repo)


def validate_checkpoint_helper() -> None:
    helper = ROOT / "skills" / "long-running-task-memory" / "scripts" / "checkpoint.py"
    with tempfile.TemporaryDirectory(prefix="codex-checkpoint-compile-") as compile_tmp:
        try:
            py_compile.compile(str(helper), cfile=str(Path(compile_tmp) / "checkpoint.pyc"), doraise=True)
        except py_compile.PyCompileError as exc:
            error("checkpoint.py 语法编译失败: " + str(exc))
    with tempfile.TemporaryDirectory(prefix="codex-checkpoint-") as tmp_value:
        tmp = Path(tmp_value)
        repo = tmp / "repo"
        memory = tmp / "memory"
        git_init(repo)
        base = [sys.executable, str(helper)]
        run(base + [
            "init", "--project-dir", str(memory), "--task-id", "TASK-VALIDATE",
            "--title", "检查点自测", "--repo-path", str(repo),
        ])
        run(base + [
            "append", "--project-dir", str(memory), "--task-id", "TASK-VALIDATE",
            "--stage", "A1", "--node-type", "分析", "--summary", "完成初始分析",
            "--fact", "已确认测试仓库状态", "--next-action", "修改样例文件",
            "--repo-path", str(repo), "--hot-limit", "30",
        ])
        run(base + [
            "validate", "--project-dir", str(memory), "--repo-path", str(repo), "--strict-git",
        ])
        recover = run(base + [
            "recover", "--project-dir", str(memory), "--repo-path", str(repo), "--recent", "5",
        ])
        if "CP-" not in recover.stdout or "下一步唯一行动" not in recover.stdout:
            error("checkpoint.py recover 输出不完整")

        with (repo / "app.txt").open("a", encoding="utf-8") as handle:
            handle.write("changed\n")
        mismatch = run(base + [
            "validate", "--project-dir", str(memory), "--repo-path", str(repo), "--strict-git",
        ], expect_success=False)
        if mismatch.returncode == 0:
            error("checkpoint.py 未检测到 Git 指纹偏移")

        for index in range(2, 5):
            run(base + [
                "append", "--project-dir", str(memory), "--task-id", "TASK-VALIDATE",
                "--stage", "A{}".format(index), "--node-type", "修改",
                "--summary", "完成节点 {}".format(index),
                "--next-action", "继续节点 {}".format(index + 1),
                "--repo-path", str(repo), "--hot-limit", "30",
            ])

        current = memory / "CURRENT_TASK.md"
        current.write_text(
            current.read_text(encoding="utf-8").replace(
                "- 最后检查点 ID：CP-", "- 最后检查点 ID：BROKEN-CP-", 1
            ),
            encoding="utf-8",
        )
        inconsistent = run(base + ["validate", "--project-dir", str(memory)], expect_success=False)
        if inconsistent.returncode == 0:
            error("checkpoint.py 未检测到 CURRENT_TASK / PROGRESS 不一致")
        run(base + [
            "repair", "--project-dir", str(memory), "--repo-path", str(repo), "--strict-git",
        ])
        run(base + [
            "archive", "--project-dir", str(memory), "--task-id", "TASK-VALIDATE",
            "--hot-limit", "2",
        ])
        run(base + [
            "validate", "--project-dir", str(memory), "--repo-path", str(repo), "--strict-git",
        ])
        archives = list((memory / "archive" / "TASK-VALIDATE").glob("PROGRESS-*.md"))
        if not archives:
            error("checkpoint.py archive 未生成归档文件")
        progress_text = (memory / "PROGRESS.md").read_text(encoding="utf-8")
        if progress_text.count("### CP-") > 2:
            error("checkpoint.py archive 未限制活跃检查点数量")
        if (memory / ".checkpoint.lock").exists():
            error("checkpoint.py 遗留写入锁")
    ok("checkpoint.py: init / append / validate / recover / repair / archive")


def validate_shell_installers_runtime() -> None:
    with tempfile.TemporaryDirectory(prefix="codex-install-") as tmp_value:
        tmp = Path(tmp_value)
        home = tmp / "home"
        codex_home = home / ".codex"
        skills_home = home / ".agents" / "skills"
        agents_home = codex_home / "agents"
        home.mkdir(parents=True)
        codex_home.mkdir(parents=True)
        skills_home.mkdir(parents=True)
        agents_home.mkdir(parents=True)
        (codex_home / "AGENTS.md").write_text("# 用户原有规则\n\n保留此行。\n", encoding="utf-8")
        (skills_home / "third-party-skill").mkdir()
        (skills_home / "third-party-skill" / "SKILL.md").write_text("third party\n", encoding="utf-8")
        (agents_home / "third-party.toml").write_text('name="third_party"\n', encoding="utf-8")
        env = os.environ.copy()
        env.update({"HOME": str(home), "CODEX_HOME": str(codex_home)})

        install = ROOT / "scripts" / "install-user.sh"
        verify = ROOT / "scripts" / "verify-user-install.sh"
        uninstall = ROOT / "scripts" / "uninstall-user.sh"
        run(["bash", str(install), "all"], env=env)
        run(["bash", str(verify)], env=env)
        run(["bash", str(install), "all"], env=env)
        run(["bash", str(verify)], env=env)
        global_text = (codex_home / "AGENTS.md").read_text(encoding="utf-8-sig")
        if global_text.count("<!-- codex-cross-project-assistant:begin -->") != 1:
            error("重复安装后 AGENTS.md 受管区块重复")
        if "保留此行" not in global_text:
            error("用户原有 AGENTS.md 内容未保留")
        if not (skills_home / "third-party-skill" / "SKILL.md").is_file():
            error("第三方 Skill 被安装脚本删除")
        if not (agents_home / "third-party.toml").is_file():
            error("第三方 Agent 被安装脚本删除")

        run(["bash", str(uninstall), "all"], env=env)
        remaining = (codex_home / "AGENTS.md").read_text(encoding="utf-8-sig")
        if "保留此行" not in remaining:
            error("卸载后用户原有 AGENTS.md 内容未保留")
        for skill in EXPECTED_SKILLS:
            if (skills_home / skill).exists():
                error("卸载后仍存在本包 Skill: " + skill)
        for file_name in EXPECTED_AGENTS.values():
            if (agents_home / file_name).exists():
                error("卸载后仍存在本包 Reviewer: " + file_name)
        if not (skills_home / "third-party-skill").exists() or not (agents_home / "third-party.toml").exists():
            error("卸载误删第三方资源")
    ok("Shell 用户级首次安装 / 重复升级 / 验证 / 卸载")


def validate_repo_installers_runtime() -> None:
    with tempfile.TemporaryDirectory(prefix="codex-repo-install-") as tmp_value:
        repo = Path(tmp_value) / "repo"
        repo.mkdir(parents=True)
        extra_skill = repo / ".agents" / "skills" / "third-party-skill"
        extra_skill.mkdir(parents=True)
        (extra_skill / "SKILL.md").write_text("third party\n", encoding="utf-8")
        extra_agent = repo / ".codex" / "agents" / "third-party.toml"
        extra_agent.parent.mkdir(parents=True)
        extra_agent.write_text('name="third_party"\n', encoding="utf-8")
        install = ROOT / "scripts" / "install-repo-skills.sh"
        uninstall = ROOT / "scripts" / "uninstall-repo-skills.sh"
        run(["bash", str(install), str(repo), "--include-review-agents"])
        for skill in EXPECTED_SKILLS:
            if not (repo / ".agents" / "skills" / skill / "SKILL.md").is_file():
                error("仓库级安装缺少 Skill: " + skill)
        for file_name in EXPECTED_AGENTS.values():
            if not (repo / ".codex" / "agents" / file_name).is_file():
                error("仓库级安装缺少 Reviewer: " + file_name)
        run(["bash", str(uninstall), str(repo), "--include-review-agents"])
        if not extra_skill.exists() or not extra_agent.exists():
            error("仓库级卸载误删第三方资源")
    ok("Shell 仓库级 Skills + Reviewer 安装 / 卸载")


def main() -> None:
    validate_manifest()
    validate_global_agents()
    validate_skills()
    validate_custom_agents()
    validate_template_set(
        "skills/technical-document-writing/assets/templates", DOC_TEMPLATES, "正式文档模板"
    )
    validate_template_set(
        "skills/long-running-task-memory/assets/templates", MEMORY_TEMPLATES, "外部记忆模板"
    )
    validate_template_set(
        "skills/multi-agent-independent-review/assets/templates", REVIEW_TEMPLATES, "复审模板"
    )
    validate_markdown_and_paths()
    validate_shell_scripts()
    validate_powershell_scripts()
    validate_checkpoint_helper()
    validate_shell_installers_runtime()
    validate_repo_installers_runtime()

    print()
    if WARNINGS:
        print("警告: {} 项".format(len(WARNINGS)))
    if ERRORS:
        print("验证失败: {} 项错误。".format(len(ERRORS)))
        raise SystemExit(1)
    print("验证通过。")


if __name__ == "__main__":
    main()
