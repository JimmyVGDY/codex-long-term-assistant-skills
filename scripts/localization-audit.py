#!/usr/bin/env python3
"""中文：审计全项目自然语言面的中英文配套覆盖。

English: Audit Chinese and English coverage for every natural-language surface.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import re
import subprocess
import tokenize
from pathlib import Path
from typing import Any, Iterable

from runtime_localization import extract_literals, load_mapping, mapping_findings


ROOT = Path(__file__).resolve().parents[1]
CODE_SUFFIXES = {".py", ".ps1", ".sh", ".cmd"}
DOCUMENT_SUFFIXES = {".md", ".txt"}
STRUCTURED_SUFFIXES = {".json", ".toml", ".yaml", ".yml"}
TEXT_SUFFIXES = CODE_SUFFIXES | DOCUMENT_SUFFIXES | STRUCTURED_SUFFIXES | {".psd1"}
DIRECTIVE = re.compile(r"^(?:#!|#\s*(?:noqa|type:|pragma:|coding[:=]|fmt:|nosec|pylint:|coverage:))", re.I)
CJK = re.compile(r"[\u4e00-\u9fff]")
REVIEWED_PATH = ROOT / "locales" / "en" / "HUMAN_REVIEWED.txt"
EXCLUDED_ROOTS = {"dist"}


def human_reviewed_paths() -> set[str]:
    """中文：读取已经逐文件人工翻译并校订的规范源路径。

    English: Read canonical source paths translated and reviewed file by file.
    """
    if not REVIEWED_PATH.is_file():
        return set()
    return {line.strip() for line in REVIEWED_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, check=True)
    files: list[Path] = []
    for item in result.stdout.split(b"\0"):
        if not item:
            continue
        relative = Path(item.decode("utf-8"))
        if relative.parts and relative.parts[0] in EXCLUDED_ROOTS:
            continue
        files.append(ROOT / relative)
    return files


def issue(code: str, path: Path, line: int = 1, detail: str = "") -> dict[str, Any]:
    return {"code": code, "path": path.relative_to(ROOT).as_posix(), "line": line, "detail": detail}


def sibling_english(path: Path) -> Path:
    return path.with_name(path.stem + ".en" + path.suffix)


def document_pair_exists(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    name = path.name
    if name.endswith(".en.md"):
        base = path.with_name(name[:-6] + ".md")
        zh = path.with_name(name[:-6] + ".zh-CN.md")
        return base.is_file() or zh.is_file()
    if name.endswith(".zh-CN.md"):
        return path.with_name(name[:-9] + ".en.md").is_file()
    return sibling_english(path).is_file() or (ROOT / "locales" / "en" / relative).is_file()


def structured_pair_exists(relative: Path) -> bool:
    """中文：确认结构化文件存在完整英文副本或专用本地化映射。

    English: Confirm a full English copy or a dedicated localization mapping.
    """
    if relative.as_posix() == "manifest.json":
        return (ROOT / "locales" / "en" / "manifest-localization.json").is_file()
    return (ROOT / "locales" / "en" / relative).is_file()


def natural_language_without_code(text: str) -> str:
    """中文：移除作为标识符或示例代码保存的字面内容。

    English: Remove literal content preserved as identifiers or example code.
    """
    output: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not fenced:
            output.append(re.sub(r"`[^`\n]*`", "", line))
    return "\n".join(output)


def audit_python(path: Path, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [issue("PYTHON_PARSE_FAILED", path, exc.lineno or 1, str(exc))]
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        value = ast.get_docstring(node, clean=False)
        if value and not ("中文：" in value and "English:" in value):
            findings.append(issue("DOCSTRING_NOT_BILINGUAL", path, getattr(node, "lineno", 1),
                                  value.splitlines()[0][:120]))
    tokens = [token for token in tokenize.generate_tokens(io.StringIO(text).readline)
              if token.type == tokenize.COMMENT and not DIRECTIVE.match(token.string.strip())]
    blocks: list[list[tokenize.TokenInfo]] = []
    for token in tokens:
        if blocks and token.start[1] == blocks[-1][-1].start[1] \
                and token.start[0] <= blocks[-1][-1].end[0] + 1:
            blocks[-1].append(token)
        else:
            blocks.append([token])
    for block in blocks:
        value = "\n".join(token.string for token in block)
        if "中文：" not in value or "English:" not in value:
            findings.append(issue("COMMENT_BLOCK_NOT_BILINGUAL", path, block[0].start[0], value[:160]))
    return findings


def audit_line_comments(path: Path, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    marker = re.compile(r"^\s*(?:#|rem\s+|::)\s*", re.I)
    rows = [(index, line) for index, line in enumerate(text.splitlines(), 1)
            if marker.match(line) and not DIRECTIVE.match(line.strip())]
    blocks: list[list[tuple[int, str]]] = []
    for row in rows:
        if blocks and row[0] == blocks[-1][-1][0] + 1:
            blocks[-1].append(row)
        else:
            blocks.append([row])
    for block in blocks:
        value = "\n".join(row[1] for row in block)
        if "中文：" not in value or "English:" not in value:
            findings.append(issue("COMMENT_BLOCK_NOT_BILINGUAL", path, block[0][0], value[:160]))
    return findings


def audit(files: Iterable[Path]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    reviewed = human_reviewed_paths()
    counts = {"tracked": 0, "text": 0, "documents": 0, "code": 0, "structured": 0}
    for path in files:
        counts["tracked"] += 1
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        counts["text"] += 1
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            findings.append(issue("TEXT_DECODE_FAILED", path, detail=str(exc)))
            continue
        relative = path.relative_to(ROOT)
        if path.suffix.lower() in DOCUMENT_SUFFIXES:
            counts["documents"] += 1
            if CJK.search(text) and "locales/en" not in relative.as_posix():
                if not document_pair_exists(path):
                    findings.append(issue("DOCUMENT_ENGLISH_PAIR_MISSING", path))
                elif relative.as_posix() not in reviewed:
                    findings.append(issue("ENGLISH_PAIR_NOT_HUMAN_REVIEWED", path))
            english_document = path.name.endswith(".en.md") or "locales/en" in relative.as_posix()
            # 中文：人工校订索引保存规范源路径，中文文件名属于路径数据而不是英文正文。
            # English: The review index stores canonical source paths; Chinese filenames are path data, not English prose.
            if english_document and path != REVIEWED_PATH and CJK.search(natural_language_without_code(text)):
                findings.append(issue("ENGLISH_DOCUMENT_CONTAINS_CJK", path))
        elif path.suffix.lower() in STRUCTURED_SUFFIXES:
            counts["structured"] += 1
            if CJK.search(text) and "locales/en" not in relative.as_posix():
                if not structured_pair_exists(relative):
                    findings.append(issue("STRUCTURED_ENGLISH_PAIR_MISSING", path))
                elif relative.as_posix() not in reviewed:
                    findings.append(issue("ENGLISH_PAIR_NOT_HUMAN_REVIEWED", path))
        elif path.suffix.lower() in CODE_SUFFIXES:
            counts["code"] += 1
            findings.extend(audit_python(path, text) if path.suffix.lower() == ".py"
                            else audit_line_comments(path, text))
    findings.extend(mapping_findings(ROOT, load_mapping()))
    by_code: dict[str, int] = {}
    for row in findings:
        by_code[row["code"]] = by_code.get(row["code"], 0) + 1
    return {"ok": not findings, "schema_version": 1, "counts": counts,
            "finding_count": len(findings), "findings_by_code": dict(sorted(by_code.items())),
            "findings": findings}


def main() -> None:
    parser = argparse.ArgumentParser(description="全项目双语覆盖审计 / Full-project bilingual coverage audit")
    parser.add_argument("--output")
    parser.add_argument("--strict", action="store_true")
    arguments = parser.parse_args()
    report = audit(tracked_files())
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if arguments.output:
        target = Path(arguments.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    if arguments.strict and not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
