"""中文：准备独立的公开合成样例及规则快照，不派发 Agent 或执行样例。
English: Prepare independent public synthetic fixtures and rule snapshots without dispatching agents or running fixtures.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.capability_store import bounded_read, safe_path
from cp_runtime.common import scan_sensitive_text
from cp_runtime.resume_snapshot import SnapshotBudget, _bounded_process

SPEC = importlib.util.spec_from_file_location("fixture_skill_eval", ROOT / "scripts/skill-eval.py")
EVAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVAL)
MAX_RULE_BYTES = 8 * 1024 * 1024
MAX_RULE_FILES = 150
CASE_FIELDS = {"id", "task", "skills", "files", "allowed_changes", "artifacts", "checks"}


def git_bytes(arguments, limit=MAX_RULE_BYTES):
    budget = SnapshotBudget(timeout=20.0, byte_limit=limit)
    raw, code, complete = _bounded_process(["git", *arguments], ROOT, budget)
    EVAL.require(complete and budget.complete and code == 0, "GIT_SNAPSHOT_UNAVAILABLE")
    return raw


def resolve_commit(reference):
    EVAL.require(isinstance(reference, str)
                 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,199}", reference),
                 "COMMIT_REFERENCE")
    value = git_bytes(["rev-parse", "--verify", reference + "^{commit}"], 256).decode().strip()
    EVAL.require(re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", value), "COMMIT_REQUIRED")
    return value


def select_case(suite, case_id):
    EVAL.require(set(suite) == {"schema", "suite_id", "data_classification", "cases"}
                 and suite["schema"] == "skill-eval-suite/1"
                 and suite["data_classification"] == "public-synthetic", "SUITE_SCHEMA")
    EVAL.require(isinstance(suite["suite_id"], str)
                 and EVAL.IDENTIFIER.fullmatch(suite["suite_id"]), "SUITE_ID")
    EVAL.require(isinstance(suite["cases"], list) and 1 <= len(suite["cases"]) <= 100, "CASE_LIMIT")
    seen = set()
    selected = None
    for case in suite["cases"]:
        EVAL.require(isinstance(case, dict) and set(case) == CASE_FIELDS, "CASE_SCHEMA")
        EVAL.require(isinstance(case["id"], str) and EVAL.IDENTIFIER.fullmatch(case["id"])
                     and case["id"] not in seen, "CASE_ID")
        seen.add(case["id"])
        EVAL.text_value(case["task"], 12000)
        if case["id"] == case_id:
            selected = case
    EVAL.require(selected is not None, "CASE_NOT_FOUND")
    case = selected
    EVAL.require(isinstance(case["files"], dict) and len(case["files"]) <= 50, "FIXTURE_FILES")
    size = 0
    for name, text in case["files"].items():
        EVAL.relative(name)
        EVAL.require(name != "AGENTS.md" and not name.startswith(".agents/"), "FIXTURE_RULE_OVERRIDE")
        EVAL.require(isinstance(text, str), "FIXTURE_TEXT")
        raw = text.encode("utf-8")
        size += len(raw)
        EVAL.require(len(raw) <= EVAL.MAX_FILE_BYTES and size <= EVAL.MAX_TOTAL_BYTES,
                     "FIXTURE_BYTE_LIMIT")
        EVAL.require(not scan_sensitive_text([text]), "SENSITIVE_FIXTURE")
    EVAL.require(isinstance(case["skills"], list) and 1 <= len(case["skills"]) <= 4
                 and len(set(case["skills"])) == len(case["skills"]), "SKILL_LIST")
    known = {entry["name"] for entry in json.loads(
        bounded_read(ROOT / "manifest.json", EVAL.MAX_JSON_BYTES).decode("utf-8"))["skills"]}
    for skill in case["skills"]:
        EVAL.require(skill in known, "UNKNOWN_SKILL")
    for name in case["allowed_changes"]:
        EVAL.relative(name)
        EVAL.require(name != "AGENTS.md" and not name.startswith(".agents/"), "RULE_MUTATION_FORBIDDEN")
    return case


def rules_snapshot(skills, commit=None):
    """中文：只复制选定 Skill 的有界普通文件；历史模式拒绝 Git 链接项。
    English: Copy bounded regular files from selected Skills only; reject link entries in historical trees.
    """
    result = {}
    total = 0
    for skill in skills:
        prefix = "skills/" + skill + "/"
        entries = git_bytes(["ls-tree", "-r", "-l", "-z", commit or "HEAD", "--", prefix])
        sources = []
        objects = {}
        for entry in entries.split(b"\0"):
            if not entry:
                continue
            header, raw_name = entry.split(b"\t", 1)
            mode, kind, object_id, size = header.decode("ascii").split()
            name = raw_name.decode("utf-8")
            EVAL.require(name.startswith(prefix) and mode in {"100644", "100755"}
                         and kind == "blob", "RULE_LINK_OR_TYPE")
            if "/tests/" in name or "/__pycache__/" in name:
                continue
            EVAL.require(int(size) <= EVAL.MAX_FILE_BYTES, "RULE_FILE_LIMIT")
            EVAL.require(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", object_id), "RULE_OBJECT_ID")
            sources.append(name)
            objects[name] = object_id
        if commit is None:
            source = safe_path(ROOT / "skills" / skill)
            pending, visited = [source], 0
            sources = []
            while pending:
                directory = safe_path(pending.pop())
                visited += 1
                EVAL.require(visited <= EVAL.MAX_DIRECTORIES, "RULE_DIRECTORY_LIMIT")
                for path in directory.iterdir():
                    checked = safe_path(path)
                    if path.name in {"tests", "__pycache__"}:
                        continue
                    if checked.is_dir():
                        pending.append(checked)
                    else:
                        EVAL.require(checked.is_file() and checked.stat().st_nlink == 1,
                                     "RULE_FILE_TYPE")
                        sources.append(checked.relative_to(ROOT).as_posix())
                    EVAL.require(len(sources) <= MAX_RULE_FILES and len(pending) <= 128,
                                 "RULE_COUNT_LIMIT")
        for name in sorted(sources):
            EVAL.relative(name)
            EVAL.require(len(result) < MAX_RULE_FILES, "RULE_COUNT_LIMIT")
            # 中文：按树中的对象读取，避免 Windows 将较长的 commit:path 当作文件名探测。
            # English: Read the tree's blob ID; long commit:path arguments trigger Windows filename probing.
            data = (git_bytes(["cat-file", "blob", objects[name]], EVAL.MAX_FILE_BYTES)
                    if commit else bounded_read(ROOT / name, EVAL.MAX_FILE_BYTES))
            total += len(data)
            EVAL.require(total <= MAX_RULE_BYTES, "RULE_BYTE_LIMIT")
            destination = ".agents/" + name
            result[destination] = data
        EVAL.require(".agents/skills/" + skill + "/SKILL.md" in result, "SKILL_ENTRY_MISSING")
    guard = bounded_read(ROOT / "global/AGENTS.md", EVAL.MAX_FILE_BYTES)
    guard += (
        "\n\n## Evaluation fixture boundary\n\n"
        "Work only in this fixture directory. Use applicable local Skills. "
        "Preserve AGENTS.md, .agents, and existing tests. Do not inspect sibling runs, "
        "input manifests, answer keys, or evaluation reports. Do not delegate, commit, "
        "install dependencies, access the network, or operate production resources. "
        "Use existing runtimes; disable Python bytecode writes. "
        "Directory separation is logical isolation, not an enforced sandbox.\n"
    ).encode("utf-8")
    result["AGENTS.md"] = guard
    EVAL.require(sum(len(data) for data in result.values()) <= MAX_RULE_BYTES, "RULE_BYTE_LIMIT")
    return result


def prepare(suite, case_id, output, baseline, environment, candidate=None, sample_id="one"):
    """中文：先校验全部材料，再创建不可覆盖的两组目录和独立评估输入。
    English: Validate all material before creating two non-overwriting runs and separate evaluator inputs.
    """
    case = select_case(suite, case_id)
    target = EVAL.external(output)
    EVAL.require(not target.exists(), "OUTPUT_ALREADY_EXISTS")
    old_sha = resolve_commit(baseline)
    new_sha = resolve_commit(candidate or "HEAD")
    snapshots = {"baseline": rules_snapshot(case["skills"], old_sha),
                 "candidate": rules_snapshot(case["skills"], new_sha if candidate else None)}
    fixtures = {name: text.encode("utf-8") for name, text in case["files"].items()}
    initial = {name: EVAL.digest(data) for name, data in fixtures.items()}
    configs = {}
    for variant, rules in snapshots.items():
        rule_files = {name: EVAL.digest(data) for name, data in rules.items()}
        value = {
            "schema": "skill-eval-input/1", "study_id": suite["suite_id"], "case_id": case_id,
            "sample_id": sample_id, "variant": variant,
            "fixture_digest": EVAL.digest(EVAL.canonical(case)), "rule_files": rule_files,
            "rule_digest": EVAL.digest(EVAL.canonical(rule_files)),
            "source_sha": old_sha if variant == "baseline" else new_sha,
            "environment": environment, "initial_files": initial,
            "allowed_changes": case["allowed_changes"], "artifacts": case["artifacts"],
            "checks": case["checks"], "metrics": {},
        }
        EVAL.validate_input(value)
        EVAL.require(len(fixtures) + len(rules) <= EVAL.MAX_FILES, "COMBINED_FILE_LIMIT")
        EVAL.require(sum(len(data) for data in fixtures.values())
                     + sum(len(data) for data in rules.values()) <= EVAL.MAX_TOTAL_BYTES,
                     "COMBINED_BYTE_LIMIT")
        configs[variant] = value
    target.mkdir(parents=True, exist_ok=False)
    for variant, rules in snapshots.items():
        run = target / variant
        workspace = run / "workspace"
        workspace.mkdir(parents=True)
        for name, data in {**fixtures, **rules}.items():
            EVAL.write_new(workspace / name, data)
        EVAL.write_new(run / "input.json", EVAL.canonical(configs[variant]) + b"\n")
        EVAL.write_new(run / "prompt.txt", case["task"].encode("utf-8"))
    manifest = {
        "schema": "skill-eval-study/1", "suite_digest": EVAL.digest(EVAL.canonical(suite)),
        "case_id": case_id, "sample_id": sample_id, "baseline": old_sha, "candidate": new_sha,
        "candidate_source": "commit" if candidate else "working-tree",
        "rule_digests": {key: value["rule_digest"] for key, value in configs.items()},
        "isolation": "logical-only", "model_execution": "NOT_STARTED",
    }
    EVAL.write_new(target / "study.json", EVAL.canonical(manifest) + b"\n")
    return {"study": str(target / "study.json"),
            "baseline_workspace": str(target / "baseline/workspace"),
            "candidate_workspace": str(target / "candidate/workspace"),
            "model_execution": "NOT_STARTED"}
