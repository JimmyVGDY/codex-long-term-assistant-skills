#!/usr/bin/env python3
"""中文：统一文档目录、英文投影和当前事实校验。

English: Unify document inventory, English projections, and current-fact checks.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
CATALOG = "config/documentation.json"
LINK = re.compile(r"(!?\[[^\]\n]*\]\()([^)\n]+)(\))")
HTML_LINK = re.compile(r"((?:href|src)=[\"'])([^\"']+)([\"'])", re.IGNORECASE)
FACT = re.compile(r"<!-- cp-fact:([a-z.-]+) -->(.*?)<!-- /cp-fact -->", re.DOTALL)
SOURCE_NOTE = "<!-- Generated from {source}; edit that source and run scripts/documentation.py sync. -->\n\n"
ALIAS_NOTE = "<!-- Generated compatibility copy from {source}; edit that source and run scripts/documentation.py sync. -->\n\n"


class DocumentationError(ValueError):
    pass


def safe_file(root: Path, name: str) -> Path:
    """中文：只接受仓库内规范相对路径，拒绝链接及越界。

    English: Accept contained canonical paths and reject links or traversal.
    """
    if not isinstance(name, str):
        raise DocumentationError("documentation path must be a string")
    relative = PurePosixPath(name)
    if not name or relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name or str(relative) != name:
        raise DocumentationError("invalid documentation path: " + name)
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink() or (os.name == "nt" and path.exists() and
                path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise DocumentationError("linked documentation path: " + name)
    return path


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise DocumentationError("duplicate JSON key: " + key)
        result[key] = value
    return result


def load_catalog(root: Path = ROOT) -> dict:
    data = json.loads(safe_file(root, CATALOG).read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if not isinstance(data, dict) or set(data) != {"schema_version", "documents", "english_projections", "fact_files", "aliases"} or type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise DocumentationError("invalid documentation catalog")
    if any(not isinstance(data[key], list) for key in ("documents", "english_projections", "aliases")) or not isinstance(data["fact_files"], dict):
        raise DocumentationError("invalid documentation catalog collections")
    seen = set()
    for item in data["documents"]:
        if not isinstance(item, dict) or set(item) != {"path", "status", "english_source"} or item["status"] not in {"active", "reference", "historical", "generated"}:
            raise DocumentationError("invalid document entry")
        if item["path"] in seen:
            raise DocumentationError("duplicate document: " + item["path"])
        seen.add(item["path"])
        for key in ("path", "english_source"):
            if not safe_file(root, item[key]).is_file():
                raise DocumentationError("missing document: " + item[key])
    targets = set()
    sources = set()
    for item in data["english_projections"]:
        if set(item) != {"source", "target"} or not item["source"].startswith("locales/en/"):
            raise DocumentationError("invalid English projection")
        source = safe_file(root, item["source"])
        safe_file(root, item["target"])
        if not source.is_file() or item["target"] in targets or item["source"] in sources or item["target"].startswith("locales/"):
            raise DocumentationError("missing or duplicate English projection")
        sources.add(item["source"])
        targets.add(item["target"])
    for name, keys in data["fact_files"].items():
        if not isinstance(keys, list) or not keys or any(not isinstance(key, str) for key in keys) or len(keys) != len(set(keys)):
            raise DocumentationError("invalid required fact markers: " + name)
        if not safe_file(root, name).is_file():
            raise DocumentationError("missing fact projection: " + name)
    aliases = set()
    for item in data["aliases"]:
        if not isinstance(item, dict) or set(item) != {"source", "target"} or item["source"] in aliases:
            raise DocumentationError("invalid document alias")
        safe_file(root, item["source"])
        if not safe_file(root, item["target"]).is_file():
            raise DocumentationError("missing alias target")
        prefix = "locales/en/docs/" if item["source"].startswith("locales/en/") else "docs/"
        if any(not item[key].startswith(prefix) or not item[key].endswith(".md") for key in ("source", "target")):
            raise DocumentationError("aliases must stay within one documentation language")
        if item["source"] in targets or item["source"] in data["fact_files"]:
            raise DocumentationError("alias has another writer: " + item["source"])
        aliases.add(item["source"])
    if any(item["target"] in aliases for item in data["aliases"]):
        raise DocumentationError("alias chains and cycles are not supported")
    for item in data["documents"]:
        if (item["status"] == "generated") != (item["path"] in aliases):
            raise DocumentationError("generated document must match a compatibility alias: " + item["path"])
    return data


def current_documents(root: Path = ROOT) -> frozenset[str]:
    return frozenset(item["path"].removeprefix("docs/") for item in load_catalog(root)["documents"]
                     if item["status"] in {"active", "reference"} and item["path"].startswith("docs/"))


def rewrite_links(text: str, transform) -> str:
    """中文：保留代码示例和链接标题，只投影 Markdown 和 HTML 链接目标。

    English: Project link destinations while preserving code examples and titles.
    """
    def markdown_link(match: re.Match) -> str:
        value = re.fullmatch(r'(\s*)(<[^>\n]+>|\S+?)(\s+(?:"[^"\n]*"|\'[^\'\n]*\'))?(\s*)', match[2])
        if not value:
            return match[0]
        location = value[2]
        if location.startswith("<") and location.endswith(">"):
            destination = "<" + transform(location[1:-1]) + ">"
        else:
            destination = transform(location)
        return match[1] + value[1] + destination + (value[3] or "") + value[4] + match[3]

    def prose(value: str) -> str:
        value = LINK.sub(markdown_link, value)
        return HTML_LINK.sub(lambda m: m[1] + transform(m[2]) + m[3], value)

    def inline(value: str) -> str:
        # 中文：配对相同长度的反引号，代码示例不进入链接转换。
        # English: Match equal-length backtick delimiters and keep code out of link conversion.
        parts = []
        cursor = 0
        for span in re.finditer(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)", value):
            parts.extend((prose(value[cursor:span.start()]), span[0]))
            cursor = span.end()
        parts.append(prose(value[cursor:]))
        return "".join(parts)

    lines = []
    fence = None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            lines.append(line)
            continue
        if fence is None:
            line = inline(line)
        lines.append(line)
    return "".join(lines)


def relocate_links(text: str, source: Path, target: Path) -> str:
    """中文：移动文档时保留相对链接所指位置及章节片段。

    English: Preserve link destinations and fragments when relocating a document.
    """
    def transform(value: str) -> str:
        if value.startswith(("#", "/")) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
            return value
        match = re.fullmatch(r'(\S+)(\s+["\'].*["\'])?', value)
        if not match:
            return value
        location, marker, fragment = match[1].partition("#")
        destination = Path(os.path.abspath(source.parent / location))
        return os.path.relpath(destination, target.parent).replace("\\", "/") + (marker + fragment if marker else "") + (match[2] or "")
    return rewrite_links(text, transform)


def project_alias(root: Path, item: dict) -> str:
    canonical = safe_file(root, item["target"])
    compatibility = safe_file(root, item["source"])
    relative = os.path.relpath(canonical, compatibility.parent).replace("\\", "/")
    label = "Current location" if item["source"].startswith("locales/en/") else "当前入口"
    return (ALIAS_NOTE.format(source=item["target"]) + "[" + label + "](" + relative + ")\n\n"
            + relocate_links(canonical.read_text(encoding="utf-8"), canonical, compatibility))


def project_english(root: Path, item: dict, catalog: dict) -> str:
    source = safe_file(root, item["source"])
    target = safe_file(root, item["target"])
    logical = root / item["source"].removeprefix("locales/en/")
    projections = {row["source"].removeprefix("locales/en/"): row["target"] for row in catalog["english_projections"]}

    def transform(value: str) -> str:
        if value.startswith(("#", "/", "http:", "https:", "mailto:", "tel:", "data:")):
            return value
        location, separator, fragment = value.partition("#")
        location = location.replace(".en.md", ".md")
        requested = Path(os.path.normpath(logical.parent / location))
        try:
            name = requested.relative_to(root).as_posix()
        except ValueError:
            return value
        if name in projections:
            destination = root / projections[name]
        elif (root / "locales/en" / name).is_file():
            destination = root / "locales/en" / name
        elif requested.exists():
            destination = requested
        else:
            return value
        result = os.path.relpath(destination, target.parent).replace("\\", "/")
        return result + (separator + fragment if separator else "")

    canonical = next((row["target"] for row in catalog["aliases"] if row["source"] == item["source"]), item["source"])
    return SOURCE_NOTE.format(source=canonical) + rewrite_links(source.read_text(encoding="utf-8"), transform)


def fact_value(key: str, root: Path) -> str:
    hooks = json.loads((root / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if key.startswith("schema."):
        values, problems = schema_contracts(root, manifest)
        if problems:
            raise DocumentationError("schema declarations disagree: " + ", ".join(problems))
        if key not in values:
            raise DocumentationError("unknown schema fact: " + key)
        return str(values[key])
    if key.startswith("owner."):
        field = {"owner.budget": "delegation_budget", "owner.review": "review_dispatch_state"}.get(key)
        if field is None:
            raise DocumentationError("unknown owner fact: " + key)
        return manifest["authority_registry"][field]
    names = "、".join("`" + name + "`" for name in hooks)
    if key == "hook-count":
        return str(len(hooks))
    if key == "package-version":
        return manifest["version"]
    if key == "upgrade-sources":
        versions = manifest.get("upgrade_from")
        if not isinstance(versions, list) or not versions or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value)
            for value in versions
        ):
            raise DocumentationError("invalid package upgrade sources")
        return ", ".join(sorted(set(versions), key=lambda value: tuple(map(int, value.split("."))), reverse=True))
    if key == "validation-report":
        version = manifest["version"]
        return f"[V{version}](releases/v{version}/VALIDATION_REPORT.md)"
    if key == "hooks.zh":
        return f"{len(hooks)} 个注册 Hook 入口：{names}。"
    if key == "hooks.en":
        return f"{len(hooks)} registered Hook entry points: " + ", ".join("`" + name + "`" for name in hooks) + "."
    raise DocumentationError("unknown documentation fact: " + key)


def declared_constant(root: Path, name: str, constant: str):
    tree = ast.parse(safe_file(root, name).read_text(encoding="utf-8-sig"))
    values = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == constant for target in node.targets)]
    if len(values) != 1:
        raise DocumentationError("missing or ambiguous schema constant: " + name)
    return values[0]


def schema_contracts(root: Path, manifest: dict) -> tuple[dict, list[str]]:
    """中文：核对实际格式声明，不执行运行时或读写任务状态。

    English: Compare format declarations without executing runtime or task-state operations.
    """
    limits = manifest["quality_limits"]
    entry = manifest["execution_determinism"]
    template = safe_file(root, entry["task_envelope"]).read_text(encoding="utf-8")
    match = re.search(r"^schema_version: ([0-9]+)$", template, re.MULTILINE)
    if not match:
        raise DocumentationError("missing envelope schema declaration")
    review_result = json.loads(safe_file(root, "skills/multi-agent-independent-review/assets/schemas/review-result.schema.json").read_text(encoding="utf-8"))
    values = {
        "schema.envelope": int(match[1]),
        "schema.execution-state": declared_constant(root, entry["guard"], "SCHEMA"),
        "schema.review-state": declared_constant(root, entry["review_controller"], "SCHEMA_VERSION"),
        "schema.review-result": review_result["properties"]["schema_version"]["const"],
        "schema.budget": declared_constant(root, entry["project_runtime"] + "/delegation_budget.py", "SCHEMA_VERSION"),
    }
    names = {"schema.envelope": "task_execution_envelope_schema_version", "schema.execution-state": "execution_state_schema_version",
             "schema.review-state": "review_state_schema_version", "schema.review-result": "review_result_schema_version",
             "schema.budget": "delegation_budget_schema_version"}
    return values, [key for key, name in names.items() if values[key] != limits.get(name)]


def authority_findings(manifest: dict, values: dict) -> list[str]:
    major = str(values["schema.budget"]).split(".")[0]
    problems = []
    budget = manifest["model_routing"]["delegation_budget"]
    authority = manifest["authority_registry"]
    if budget.get("accounting_owner") != "delegation-budget-v" + major:
        problems.append("model_routing.delegation_budget.accounting_owner")
    if "DelegationBudget V" + major + " " not in authority.get("delegation_budget", ""):
        problems.append("authority_registry.delegation_budget")
    review = authority.get("review_dispatch_state", "")
    if "review-state.json" not in review or "review_controller.py" not in review or "budget" in review.lower():
        problems.append("authority_registry.review_dispatch_state")
    return problems


def render_facts(text: str, root: Path) -> str:
    return FACT.sub(lambda m: "<!-- cp-fact:" + m[1] + " -->" + fact_value(m[1], root) + "<!-- /cp-fact -->", text)


def audit(root: Path = ROOT, *, write: bool = False) -> dict:
    catalog = load_catalog(root)
    problems = []
    updated = []
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if "quality_limits" in manifest:
        values, disagreements = schema_contracts(root, manifest)
        problems.extend({"code": "SCHEMA_DECLARATION_DRIFT", "path": "manifest.json", "field": name} for name in disagreements)
        problems.extend({"code": "AUTHORITY_DRIFT", "path": "manifest.json", "field": name} for name in authority_findings(manifest, values))
    for name, required_keys in catalog["fact_files"].items():
        path = safe_file(root, name)
        original = path.read_text(encoding="utf-8")
        keys = [match[1] for match in FACT.finditer(original)]
        if sorted(keys) != sorted(required_keys):
            problems.append({"code": "FACT_MARKER_MISSING", "path": name})
        try:
            expected = render_facts(original, root)
        except DocumentationError as exc:
            problems.append({"code": "FACT_SOURCE_INVALID", "path": name, "error": str(exc)})
            continue
        if original != expected:
            if write:
                path.write_text(expected, encoding="utf-8", newline="\n")
                updated.append(name)
            else:
                problems.append({"code": "FACT_DRIFT", "path": name})
    for item in catalog["aliases"]:
        expected = project_alias(root, item)
        path = safe_file(root, item["source"])
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            if write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(expected, encoding="utf-8", newline="\n")
                updated.append(item["source"])
            else:
                problems.append({"code": "COMPATIBILITY_COPY_DRIFT", "path": item["source"]})
    for item in catalog["english_projections"]:
        expected = project_english(root, item, catalog)
        path = safe_file(root, item["target"])
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            if write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(expected, encoding="utf-8", newline="\n")
                updated.append(item["target"])
            else:
                problems.append({"code": "ENGLISH_PROJECTION_DRIFT", "path": item["target"]})
    current_series = ".".join(manifest["version"].split(".")[:2])
    for item in catalog["documents"]:
        release = re.fullmatch(r"docs/releases/v(\d+\.\d+\.\d+)/[^/]+\.md", item["path"])
        if release:
            expected_status = "active" if release[1] == manifest["version"] else "historical"
            if item["status"] != expected_status:
                problems.append({"code": "RELEASE_DOCUMENT_STATUS", "path": item["path"]})
        if item["status"] == "historical":
            continue
        for name in (item["path"], item["english_source"]):
            text = safe_file(root, name).read_text(encoding="utf-8")
            first = next((line for line in text.splitlines() if line.startswith("# ")), "")
            versions = re.findall(r"\bV(\d+\.\d+)(?:\.\d+)?\b", first)
            if any(version != current_series for version in versions):
                problems.append({"code": "CURRENT_TITLE_VERSION", "path": name})
            if re.search(r"V7\.(?:5|6)\.2 (?:及更早版本|and earlier)", text):
                problems.append({"code": "MIGRATION_SOURCE_DRIFT", "path": name})
    tracked_docs = {p.relative_to(root).as_posix() for p in (root / "docs").rglob("*.md") if not p.name.endswith(".en.md")}
    declared_docs = {row["path"] for row in catalog["documents"] if row["path"].startswith("docs/")}
    for name in sorted(tracked_docs - declared_docs):
        problems.append({"code": "UNREGISTERED_DOCUMENT", "path": name})
    return {"ok": not problems, "documents": len(catalog["documents"]),
            "english_projections": len(catalog["english_projections"]), "updated": updated, "findings": problems}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check or regenerate documentation projections")
    parser.add_argument("command", choices=("check", "sync"))
    args = parser.parse_args()
    try:
        report = audit(write=args.command == "sync")
    except (DocumentationError, KeyError, TypeError, OSError, ValueError) as exc:
        report = {"ok": False, "findings": [{"code": "DOCUMENTATION_INPUT_INVALID", "error": str(exc)}]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
