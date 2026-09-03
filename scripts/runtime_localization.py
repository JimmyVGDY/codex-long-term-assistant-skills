#!/usr/bin/env python3
"""中文：提取、校验并应用 Python 运行时自然语言字面量的人工英文映射。

English: Extract, validate, and apply human-reviewed English mappings for Python runtime literals.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import re
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r"[\u4e00-\u9fff]")
DEFAULT_MAP = ROOT / "locales" / "en" / "runtime-strings.json"


class RuntimeLocalizationError(RuntimeError):
    pass


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """中文：返回模块、类和函数 Docstring 常量节点。

    English: Return constant nodes used as module, class, and function docstrings.
    """
    nodes: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if not body or not isinstance(body[0], ast.Expr):
            continue
        value = body[0].value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        nodes.add(id(value))
    return nodes


def _fstring_children(tree: ast.AST) -> set[int]:
    return {id(child) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr)
            for child in ast.walk(node) if child is not node}


def extract_literals(path: Path) -> list[dict[str, Any]]:
    """中文：提取 Docstring 之外含中文的普通字符串与 f-string Token。

    English: Extract non-docstring plain strings and f-string tokens that contain Chinese text.
    """
    text = path.read_text(encoding="utf-8-sig")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise RuntimeLocalizationError(f"cannot parse {path}: {exc}") from exc
    docstrings = _docstring_nodes(tree)
    fstring_children = _fstring_children(tree)
    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            source = ast.get_source_segment(text, node)
            if source and CJK.search(source):
                rows.append({"kind": "fstring", "source": source, "line": node.lineno})
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings and id(node) not in fstring_children \
                and CJK.search(node.value):
            rows.append({"kind": "plain", "source": node.value, "line": node.lineno})
    return rows


def load_mapping(path: Path = DEFAULT_MAP) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("files"), dict):
        raise RuntimeLocalizationError("runtime localization map schema is invalid")
    return data


def mapping_findings(root: Path, mapping: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if any(part in {".git", "dist", "locales", "__pycache__", "tests", "project-context"} for part in path.parts) \
                or path.name.startswith("test_"):
            continue
        configured = mapping["files"].get(relative, {})
        plain = configured.get("plain", {})
        fstrings = configured.get("fstring", {})
        preserved = set(configured.get("preserve", []))
        for row in extract_literals(path):
            source = row["source"]
            target = plain.get(source) if row["kind"] == "plain" else fstrings.get(source)
            if source in preserved:
                continue
            if not isinstance(target, str) or not target.strip():
                findings.append({"code": "RUNTIME_ENGLISH_MAPPING_MISSING", "path": relative,
                                 "line": row["line"], "kind": row["kind"], "source": source})
            elif CJK.search(target):
                findings.append({"code": "RUNTIME_ENGLISH_MAPPING_CONTAINS_CJK", "path": relative,
                                 "line": row["line"], "kind": row["kind"], "source": source})
    return findings


def localize_file(path: Path, configured: dict[str, Any]) -> None:
    """中文：用经过人工校订的映射替换单个 Python 文件的运行时字面量。

    English: Replace runtime literals in one Python file with their human-reviewed mappings.
    """
    text = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(text)
    docstrings = _docstring_nodes(tree)
    fstring_children = _fstring_children(tree)
    plain = configured.get("plain", {})
    fstrings = configured.get("fstring", {})
    raw = text.encode("utf-8")
    starts: list[int] = []
    offset = 0
    for line in raw.splitlines(keepends=True):
        starts.append(offset)
        offset += len(line)
    if not starts:
        starts.append(0)
    edits: list[tuple[int, int, bytes]] = []

    def add_edit(node: ast.AST, replacement: str) -> None:
        start = starts[node.lineno - 1] + node.col_offset  # type: ignore[attr-defined]
        end = starts[node.end_lineno - 1] + node.end_col_offset  # type: ignore[attr-defined]
        edits.append((start, end, replacement.encode("utf-8")))

    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            source = ast.get_source_segment(text, node)
            if source in fstrings:
                add_edit(node, fstrings[source])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings and id(node) not in fstring_children \
                and node.value in plain:
            add_edit(node, json.dumps(plain[node.value], ensure_ascii=False))
    for start, end, replacement in sorted(edits, reverse=True):
        raw = raw[:start] + replacement + raw[end:]
    rendered = raw.decode("utf-8")
    ast.parse(rendered)
    path.write_text(rendered, encoding="utf-8", newline="\n")


def localize_tree(root: Path, mapping: dict[str, Any]) -> None:
    findings = mapping_findings(root, mapping)
    if findings:
        first = findings[0]
        raise RuntimeLocalizationError(
            f"runtime localization is incomplete: {len(findings)} findings; first={first['path']}:{first['line']}")
    for relative, configured in mapping["files"].items():
        path = root / relative
        if path.is_file():
            localize_file(path, configured)


def main() -> None:
    parser = argparse.ArgumentParser(description="Runtime string localization audit and renderer")
    parser.add_argument("command", choices=("audit", "extract", "apply"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    arguments = parser.parse_args()
    mapping = load_mapping(arguments.map)
    if arguments.command == "extract":
        rows = []
        for path in sorted(arguments.root.rglob("*.py")):
            if any(part in {".git", "dist", "locales", "__pycache__", "tests"} for part in path.parts) \
                    or path.name.startswith("test_"):
                continue
            for row in extract_literals(path):
                rows.append({"path": path.relative_to(arguments.root).as_posix(), **row})
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if arguments.command == "audit":
        findings = mapping_findings(arguments.root, mapping)
        print(json.dumps({"ok": not findings, "finding_count": len(findings),
                          "findings": findings}, ensure_ascii=False, indent=2))
        if findings:
            raise SystemExit(1)
        return
    localize_tree(arguments.root, mapping)


if __name__ == "__main__":
    main()
