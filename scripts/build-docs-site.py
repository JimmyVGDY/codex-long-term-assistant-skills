#!/usr/bin/env python3
"""中文：为 GitHub Pages 准备隔离的中英文 MkDocs 文档源。

English: Prepare isolated Chinese and English MkDocs sources for GitHub Pages.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist" / "docs-source"
SITE_TEMPLATE = ROOT / ".github" / "docs-site"
REPOSITORY_BLOB = "https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/"
MARKDOWN_LINK = re.compile(r"(!?\[[^\]\n]*\]\()([^)\n]+)(\))")
HTML_LINK = re.compile(r"((?:href|src)=[\"'])([^\"']+)([\"'])", re.IGNORECASE)


class DocumentationBuildError(RuntimeError):
    pass


def is_link(path: Path) -> bool:
    """中文：识别符号链接和 Windows Reparse Point。

    English: Identify symbolic links and Windows reparse points.
    """
    try:
        if path.is_symlink():
            return True
        return os.name == "nt" and bool(
            path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, OSError):
        return False


def reset_output(output: Path) -> None:
    """中文：仅重建明确的文档暂存目录，拒绝宽泛或越界目标。

    English: Recreate only an explicit documentation staging directory and reject broad targets.
    """
    resolved = output.resolve()
    if resolved == ROOT.resolve() or resolved == Path(resolved.anchor):
        raise DocumentationBuildError("documentation output is too broad")
    if output.exists():
        allowed = (ROOT / "dist").resolve()
        if resolved.parent != allowed or resolved.name != "docs-source":
            raise DocumentationBuildError("existing output may be replaced only at dist/docs-source")
        if is_link(output):
            raise DocumentationBuildError("documentation output is a link or reparse point")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=False)


def copy_files(source: Path, destination: Path, include: Callable[[Path], bool]) -> None:
    """中文：按确定顺序复制安全文件，并拒绝链接来源。

    English: Copy safe files in deterministic order and reject linked sources.
    """
    for path in sorted(source.rglob("*")):
        if is_link(path):
            raise DocumentationBuildError(f"documentation source contains a link: {path}")
        if not path.is_file() or not include(path):
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def rewrite_target(path: Path, output: Path, target: str) -> str:
    """中文：把源码双语跳转转换为 Pages 暂存目录中的实际位置。

    English: Convert source bilingual links to their actual Pages staging locations.
    """
    value = target.strip()
    if not value or value.startswith(("#", "http://", "https://", "mailto:", "tel:")):
        return target
    path_part, marker, fragment = value.partition("#")
    if ".github/" in path_part.replace("\\", "/"):
        normalized = path_part.replace("\\", "/")
        repository_path = normalized[normalized.index(".github/"):]
        return REPOSITORY_BLOB + repository_path + (marker + fragment if marker else "")
    relative = path.relative_to(output)
    language = relative.parts[0] if relative.parts else ""
    destination: Path | None = None
    if language == "zh-CN" and path_part.endswith(".en.md"):
        requested = (path.parent / path_part).resolve()
        chinese_root = (output / "zh-CN").resolve()
        try:
            counterpart = requested.relative_to(chinese_root)
        except ValueError:
            return target
        counterpart = counterpart.with_name(counterpart.name.replace(".en.md", ".md"))
        if counterpart.as_posix() == "README.md":
            counterpart = Path("index.md")
        destination = output / "en" / counterpart
    elif language == "en" and path_part.endswith(".en.md"):
        destination = path.parent / path_part.replace(".en.md", ".md")
    elif relative.as_posix() == "en/index.md" and path_part == "README.md":
        destination = output / "zh-CN" / "index.md"
    elif relative.as_posix() == "en/CHANGELOG.md" and path_part == "CHANGELOG.md":
        destination = output / "zh-CN" / "CHANGELOG.md"
    if destination is None:
        return target
    rewritten = os.path.relpath(destination, path.parent).replace("\\", "/")
    return rewritten + (marker + fragment if marker else "")


def rewrite_site_links(output: Path) -> None:
    """中文：只重写生成副本中的链接，不改变仓库规范源。

    English: Rewrite links only in generated copies, leaving repository sources unchanged.
    """
    for path in sorted(output.rglob("*.md")):
        text = path.read_text(encoding="utf-8-sig")
        lines: list[str] = []
        fence: str | None = None
        for line in text.splitlines(keepends=True):
            stripped = line.lstrip()
            marker = stripped[:3] if stripped.startswith(("```", "~~~")) else None
            if marker:
                fence = None if fence == marker else marker if fence is None else fence
                lines.append(line)
                continue
            if fence:
                lines.append(line)
                continue
            rewritten_line = MARKDOWN_LINK.sub(
                lambda match: match.group(1) + rewrite_target(path, output, match.group(2)) + match.group(3),
                line,
            )
            lines.append(HTML_LINK.sub(
                lambda match: match.group(1) + rewrite_target(path, output, match.group(2)) + match.group(3),
                rewritten_line,
            ))
        path.write_text("".join(lines), encoding="utf-8", newline="\n")


def prepare(output: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    """中文：生成只包含正式文档的中英文站点源目录。

    English: Generate Chinese and English site sources containing only formal documentation.
    """
    output = output.resolve()
    reset_output(output)
    shutil.copyfile(SITE_TEMPLATE / "index.md", output / "index.md")
    copy_files(SITE_TEMPLATE / "stylesheets", output / "stylesheets", lambda _: True)

    chinese = output / "zh-CN"
    english = output / "en"
    chinese.mkdir()
    english.mkdir()
    shutil.copyfile(ROOT / "README.md", chinese / "index.md")
    shutil.copyfile(ROOT / "README.en.md", english / "index.md")
    shutil.copyfile(ROOT / "CHANGELOG.md", chinese / "CHANGELOG.md")
    shutil.copyfile(ROOT / "CHANGELOG.en.md", english / "CHANGELOG.md")
    for name in ("LICENSE", "NOTICE"):
        shutil.copyfile(ROOT / name, chinese / name)
        shutil.copyfile(ROOT / name, english / name)

    copy_files(ROOT / "docs", chinese / "docs", lambda path: not path.name.endswith(".en.md"))
    copy_files(ROOT / "docs", english / "docs", lambda path: path.suffix.lower() != ".md")
    copy_files(ROOT / "locales" / "en" / "docs", english / "docs", lambda _: True)
    reconstructed = ROOT / "docs" / "history" / "RECONSTRUCTED_HISTORY.en.md"
    if reconstructed.is_file():
        target = english / "docs" / "history" / "RECONSTRUCTED_HISTORY.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(reconstructed, target)

    rewrite_site_links(output)
    markdown_files = list(output.rglob("*.md"))
    return {
        "ok": True,
        "output": output.as_posix(),
        "markdown_files": len(markdown_files),
        "chinese_markdown": len(list(chinese.rglob("*.md"))),
        "english_markdown": len(list(english.rglob("*.md"))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="准备 GitHub Pages 文档源 / Prepare GitHub Pages documentation source")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    report = prepare(arguments.output)
    for key, value in report.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
