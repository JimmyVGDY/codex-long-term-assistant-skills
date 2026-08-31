"""Project identity, bounded read-only onboarding and project-state management."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .common import (
    RuntimeContractError,
    atomic_write_json,
    atomic_write_text,
    canonical_sha256,
    ensure_git_repo,
    read_json,
    repo_snapshot,
    require_external_state,
    optional_git_text,
    resolve_codex_home,
    utc_now,
    validate_identifier,
)
from .contracts import ProjectBinding, ProjectStage

PROFILE_FILE = "project-profile.json"
STATE_FILE = "project-state.json"
MEMORY_FILE = "project-memory.md"
PROFILE_SCHEMA = 1
STATE_SCHEMA = 1


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return (cleaned or "project")[:48]


def make_project_id(repo: Path, explicit: Optional[str] = None) -> str:
    if explicit:
        return validate_identifier(explicit, "project_id")
    snapshot = repo_snapshot(repo)
    source = snapshot.get("remote_origin") or str(repo.resolve())
    suffix = hashlib.sha256(source.encode("utf-8", errors="surrogateescape")).hexdigest()[:10]
    return validate_identifier(_slug(repo.name) + "-" + suffix, "project_id")


def default_context_dir(project_id: str) -> Path:
    return resolve_codex_home() / "project-context" / validate_identifier(project_id, "project_id")


def _detect_markers(repo: Path) -> Dict[str, Any]:
    files = {path.name: path for path in repo.iterdir() if path.is_file()}
    languages: List[str] = []
    frameworks: List[str] = []
    build_tools: List[str] = []
    runtime_markers: List[str] = []
    commands: Dict[str, Dict[str, str]] = {}

    if "pom.xml" in files:
        languages.append("Java")
        build_tools.append("Maven")
        commands["build"] = {"value": "./mvnw clean package 或 mvn clean package", "confidence": "marker-based"}
        commands["test"] = {"value": "./mvnw test 或 mvn test", "confidence": "marker-based"}
        try:
            text = files["pom.xml"].read_text(encoding="utf-8", errors="ignore")[:512000]
            if "spring-boot" in text:
                frameworks.append("Spring Boot")
                commands["start"] = {"value": "./mvnw spring-boot:run 或按项目脚本启动", "confidence": "marker-based"}
        except OSError:
            pass
    if "build.gradle" in files or "build.gradle.kts" in files:
        languages.append("Java/Kotlin")
        build_tools.append("Gradle")
        commands.setdefault("build", {"value": "./gradlew build", "confidence": "marker-based"})
        commands.setdefault("test", {"value": "./gradlew test", "confidence": "marker-based"})
    if "package.json" in files:
        languages.extend(["JavaScript", "TypeScript"])
        build_tools.append("npm-compatible")
        try:
            package = json.loads(files["package.json"].read_text(encoding="utf-8-sig"))
            dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
            for dep, framework in (
                ("vue", "Vue"), ("nuxt", "Nuxt"), ("react", "React"),
                ("next", "Next.js"), ("@angular/core", "Angular"),
                ("svelte", "Svelte"), ("@nestjs/core", "NestJS"),
            ):
                if dep in dependencies:
                    frameworks.append(framework)
            scripts = package.get("scripts", {})
            for key, target in (("build", "build"), ("test", "test"), ("start", "start")):
                if key in scripts:
                    commands[target] = {"value": f"npm run {key}", "confidence": "declared-script"}
            if "dev" in scripts and "start" not in commands:
                commands["start"] = {"value": "npm run dev", "confidence": "declared-script"}
        except (OSError, json.JSONDecodeError):
            runtime_markers.append("package.json-unparsed")
    if "pyproject.toml" in files or "requirements.txt" in files or "setup.py" in files:
        languages.append("Python")
        build_tools.append("Python packaging")
        commands.setdefault("test", {"value": "pytest（需先确认项目配置）", "confidence": "inferred-unconfirmed"})
    if "go.mod" in files:
        languages.append("Go")
        build_tools.append("Go modules")
        commands["build"] = {"value": "go build ./...", "confidence": "marker-based"}
        commands["test"] = {"value": "go test ./...", "confidence": "marker-based"}
    if any(repo.glob("*.sln")) or any(repo.glob("*.csproj")):
        languages.append("C#")
        build_tools.append("dotnet")
        commands["build"] = {"value": "dotnet build", "confidence": "marker-based"}
        commands["test"] = {"value": "dotnet test", "confidence": "marker-based"}
    if "Dockerfile" in files:
        runtime_markers.append("Dockerfile")
    if "docker-compose.yml" in files or "docker-compose.yaml" in files or "compose.yml" in files or "compose.yaml" in files:
        runtime_markers.append("Docker Compose")
    if ".github" in [p.name for p in repo.iterdir() if p.is_dir()]:
        runtime_markers.append("GitHub Actions directory")

    modules: List[str] = []
    marker_names = {"pom.xml", "build.gradle", "build.gradle.kts", "package.json", "pyproject.toml", "go.mod"}
    for child in sorted((p for p in repo.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name):
        if any((child / marker).is_file() for marker in marker_names):
            modules.append(child.name)
        if len(modules) >= 50:
            break

    return {
        "languages": sorted(set(languages)),
        "frameworks": sorted(set(frameworks)),
        "build_tools": sorted(set(build_tools)),
        "runtime_markers": sorted(set(runtime_markers)),
        "modules": modules,
        "commands": commands,
    }


def _profile_binding_sha256(profile: Dict[str, Any]) -> str:
    payload = dict(profile)
    payload.pop("integrity", None)
    payload.pop("binding_sha256", None)
    payload.pop("last_verified_at", None)
    identity = dict(payload.get("identity") or {})
    identity.pop("default_branch_observed", None)
    payload["identity"] = identity
    return canonical_sha256(payload)


def _initial_memory(project_id: str, project_name: str) -> str:
    return f"""# Project Memory: {project_name}\n\n- Project ID：`{project_id}`\n- 状态：尚无已审核项目记忆\n- 说明：任务 Checkpoint 不能自动写入本文件；必须先生成 Projection Candidate，再经过明确审核后晋升。\n\n<!-- project-memory:begin -->\n<!-- project-memory:end -->\n"""


def onboard_project(
    repo_path: Path,
    project_id: Optional[str] = None,
    project_name: str = "",
    context_dir: Optional[Path] = None,
    force: bool = False,
    allow_inside_repo: bool = False,
) -> ProjectBinding:
    repo = ensure_git_repo(repo_path)
    pid = make_project_id(repo, project_id)
    target = (context_dir or default_context_dir(pid)).expanduser().resolve()
    require_external_state(target, repo, allow_inside_repo)
    profile_path = target / PROFILE_FILE
    state_path = target / STATE_FILE
    if (profile_path.exists() or state_path.exists()) and not force:
        raise RuntimeContractError("项目上下文已存在；使用 --force 才能重建")
    target.mkdir(parents=True, exist_ok=True)

    snapshot = repo_snapshot(repo)
    detected = _detect_markers(repo)
    now = utc_now()
    name = project_name.strip() or repo.name
    unknowns = [
        "目标环境与环境负责人尚未确认",
        "数据敏感等级和数据所有权尚未确认",
        "部署、回滚和生产操作入口尚未确认",
    ]
    if not detected["commands"]:
        unknowns.append("构建、测试和启动入口尚未确认")
    profile: Dict[str, Any] = {
        "schema_version": PROFILE_SCHEMA,
        "project_id": pid,
        "project_name": name,
        "status": "active",
        "identity": {
            "vcs": "git",
            "repo_path": str(repo),
            "remote_origin": snapshot["remote_origin"],
            "default_branch_observed": snapshot["branch"],
        },
        "technology": {
            "languages": detected["languages"],
            "frameworks": detected["frameworks"],
            "build_tools": detected["build_tools"],
            "runtime_markers": detected["runtime_markers"],
            "modules": detected["modules"],
        },
        "entrypoints": detected["commands"],
        "boundaries": {
            "environment": "unknown",
            "data_classification": "unknown",
            "data_owner": "unknown",
            "prohibited_paths": [".git", "node_modules", "target", "build", "dist", "venv", ".venv"],
        },
        "facts": [],
        "unknowns": unknowns,
        "onboarding": {
            "mode": "bounded-readonly",
            "deep_dependency_scan": False,
            "network_access": False,
            "production_access": False,
        },
        "created_at": now,
        "last_verified_at": now,
    }
    profile["binding_sha256"] = _profile_binding_sha256(profile)
    sealed_profile = atomic_write_json(profile_path, profile, seal=True)
    state: Dict[str, Any] = {
        "schema_version": STATE_SCHEMA,
        "project_id": pid,
        "stage": ProjectStage.ACTIVE.value,
        "baseline": snapshot,
        "current_task_id": "",
        "risks": [],
        "blockers": [],
        "next_action": "确认 Profile 中的 unknowns，再开始有写入影响的任务",
        "last_checkpoint": "",
        "created_at": now,
        "updated_at": now,
    }
    atomic_write_json(state_path, state, seal=True)
    memory_path = target / MEMORY_FILE
    if memory_path.exists():
        existing_memory = memory_path.read_text(encoding="utf-8-sig")
        project_marker = f"- Project ID：`{pid}`"
        if project_marker not in existing_memory:
            raise RuntimeContractError(
                "现有 project-memory.md 不属于当前 project_id；拒绝在 --force 下覆盖长期记忆"
            )
    else:
        atomic_write_text(memory_path, _initial_memory(pid, name))
    for filename in ("memory-projections.jsonl", "knowledge-candidates.jsonl", "execution-feedback.jsonl", "evidence-ledger.jsonl"):
        path = target / filename
        if not path.exists():
            atomic_write_text(path, "")
    return ProjectBinding(pid, repo, profile_path, state_path, sealed_profile["binding_sha256"])


def load_profile(path: Path) -> Dict[str, Any]:
    profile = read_json(path, verify=True, label="Project Profile")
    if profile.get("schema_version") != PROFILE_SCHEMA:
        raise RuntimeContractError("不支持的 Project Profile schema_version")
    validate_identifier(str(profile.get("project_id", "")), "project_id")
    expected_binding = profile.get("binding_sha256")
    actual_binding = _profile_binding_sha256(profile)
    if expected_binding != actual_binding:
        raise RuntimeContractError("Project Profile binding_sha256 校验失败")
    return profile


def load_state(path: Path) -> Dict[str, Any]:
    state = read_json(path, verify=True, label="Project State")
    if state.get("schema_version") != STATE_SCHEMA:
        raise RuntimeContractError("不支持的 Project State schema_version")
    return state


def validate_binding(
    profile_path: Path,
    repo_path: Path,
    project_id: Optional[str] = None,
    state_path: Optional[Path] = None,
) -> ProjectBinding:
    profile_path = profile_path.expanduser().resolve()
    profile = load_profile(profile_path)
    repo = ensure_git_repo(repo_path)
    expected_repo = Path(profile["identity"]["repo_path"]).expanduser().resolve()
    if expected_repo != repo:
        raise RuntimeContractError(f"Project Profile 绑定仓库不一致: {expected_repo} != {repo}")
    expected_remote = str(profile.get("identity", {}).get("remote_origin") or "").strip()
    current_remote = optional_git_text(repo, ["config", "--get", "remote.origin.url"])
    if expected_remote and current_remote != expected_remote:
        raise RuntimeContractError("仓库 remote.origin.url 已变化；必须刷新并重新绑定 Project Profile")
    pid = str(profile["project_id"])
    if project_id and project_id != pid:
        raise RuntimeContractError(f"project_id 不一致: {project_id} != {pid}")
    resolved_state = (state_path or profile_path.with_name(STATE_FILE)).expanduser().resolve()
    state = load_state(resolved_state)
    if state.get("project_id") != pid:
        raise RuntimeContractError("Project State 与 Project Profile 的 project_id 不一致")
    return ProjectBinding(pid, repo, profile_path, resolved_state, profile["binding_sha256"])


def refresh_project(profile_path: Path, state_path: Optional[Path] = None) -> ProjectBinding:
    profile_path = profile_path.expanduser().resolve()
    profile = load_profile(profile_path)
    repo = ensure_git_repo(Path(profile["identity"]["repo_path"]))
    resolved_state = (state_path or profile_path.with_name(STATE_FILE)).expanduser().resolve()
    state = load_state(resolved_state)
    if state["project_id"] != profile["project_id"]:
        raise RuntimeContractError("Project State 与 Project Profile 不一致")
    snapshot = repo_snapshot(repo)
    state["baseline"] = snapshot
    state["updated_at"] = utc_now()
    atomic_write_json(resolved_state, state, seal=True)
    profile["last_verified_at"] = utc_now()
    profile["identity"]["remote_origin"] = snapshot["remote_origin"]
    profile["identity"]["default_branch_observed"] = snapshot["branch"]
    profile["binding_sha256"] = _profile_binding_sha256(profile)
    sealed_profile = atomic_write_json(profile_path, profile, seal=True)
    return ProjectBinding(
        str(profile["project_id"]), repo, profile_path, resolved_state,
        sealed_profile["binding_sha256"],
    )


def update_project_state(state_path: Path, **changes: Any) -> Dict[str, Any]:
    state = load_state(state_path)
    allowed = {"stage", "current_task_id", "risks", "blockers", "next_action", "last_checkpoint", "baseline"}
    unknown = sorted(set(changes) - allowed)
    if unknown:
        raise RuntimeContractError("不允许更新的 Project State 字段: " + ",".join(unknown))
    if "stage" in changes and changes["stage"] not in {item.value for item in ProjectStage}:
        raise RuntimeContractError("非法 Project Stage")
    state.update(changes)
    state["updated_at"] = utc_now()
    return atomic_write_json(state_path, state, seal=True)
