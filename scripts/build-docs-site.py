#!/usr/bin/env python3
"""中文：为 GitHub Pages 准备隔离的中英文 MkDocs 文档源。

English: Prepare isolated Chinese and English MkDocs sources for GitHub Pages.
"""
from __future__ import annotations

import argparse
import json
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
PACKAGE_VERSION = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["version"]
CURRENT_RELEASE_DIRECTORY = f"v{PACKAGE_VERSION}"
CURRENT_VERSION_SERIES = ".".join(PACKAGE_VERSION.split(".")[:2])
CURRENT_DOCUMENTS = frozenset({
    "README.md",
    f"USER_GUIDE_V{CURRENT_VERSION_SERIES}.md",
    "INSTALLATION_RECOVERY.md",
    "CODEX_CONFIG_GUIDE.md",
    "PROJECT_CONTEXT_AND_ONBOARDING.md",
    "SYSTEM_ARCHITECTURE.md",
    "V7_DOMAIN_SKILL_ARCHITECTURE.md",
    "MODEL_ROUTING_AND_COST_POLICY.md",
    "REVIEWER_RUNTIME_ISOLATION.md",
    "SUBAGENT_INDEPENDENT_CONTEXT.md",
    "SKILL_TRIGGER_MATRIX.md",
    "SKILL_ROUTING_EVAL.md",
    "SOURCE_MAPPING.md",
    "APPROVAL_EVIDENCE_FINALIZATION.md",
    "AUTHORITY_REGISTRY.md",
    "evolution/CONTROLLED_EVOLUTION_OPERATIONS.md",
    "evolution/SELF_EVOLUTION_ARCHITECTURE.md",
    "VALIDATION_REPORT.md",
    "releases/README.md",
    "releases/RELEASE_AUTOMATION.md",
    "history/README.md",
    "history/RELEASE_ARCHIVES.md",
    "history/GITHUB_RELEASES.md",
})


class DocumentationBuildError(RuntimeError):
    pass


def validate_version_bound_sources() -> None:
    """中文：确保当前站点入口与 manifest 版本一致，版本漂移时失败关闭。

    English: Fail closed when a current site entry point drifts from the manifest version.
    """
    expected = {
        ROOT / ".github" / "mkdocs.yml": (
            f"USER_GUIDE_V{CURRENT_VERSION_SERIES}.md",
            f"releases/{CURRENT_RELEASE_DIRECTORY}/RELEASE_NOTES.md",
            f"V{CURRENT_VERSION_SERIES} current system architecture",
        ),
        ROOT / "locales" / "en" / ".github" / "mkdocs.yml": (
            f"USER_GUIDE_V{CURRENT_VERSION_SERIES}.md",
            f"releases/{CURRENT_RELEASE_DIRECTORY}/RELEASE_NOTES.md",
            f"V{CURRENT_VERSION_SERIES} current system architecture",
        ),
        SITE_TEMPLATE / "index.md": (
            f"V{PACKAGE_VERSION}",
            f"USER_GUIDE_V{CURRENT_VERSION_SERIES}/",
        ),
        SITE_TEMPLATE / "index.en.md": (
            f"V{PACKAGE_VERSION}",
            f"USER_GUIDE_V{CURRENT_VERSION_SERIES}/",
        ),
        SITE_TEMPLATE / "javascripts" / "repository-facts.js": (
            f'const RELEASE_VERSION = "v{PACKAGE_VERSION}";',
        ),
    }
    missing: list[str] = []
    for path, markers in expected.items():
        text = path.read_text(encoding="utf-8-sig")
        for marker in markers:
            if marker not in text:
                missing.append(f"{path.relative_to(ROOT).as_posix()}: {marker}")
    if missing:
        raise DocumentationBuildError(
            "Version-bound documentation sources are inconsistent with manifest.json: "
            + "; ".join(missing))


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


def copy_english_pairs(source: Path, destination: Path) -> None:
    """中文：把源码树中的同级英文文档复制为站点规范路径。

    English: Copy sibling English documents to their canonical site paths.
    """
    for path in sorted(source.rglob("*.en.md")):
        if is_link(path):
            raise DocumentationBuildError(f"documentation source contains a link: {path}")
        relative = path.relative_to(source)
        normalized = relative.with_name(relative.name[:-6] + ".md")
        target = destination / normalized
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def normalized_document_path(relative: Path) -> str:
    """中文：把同级英文文件名归一为站点内的规范文档路径。

    English: Normalize sibling English filenames to canonical site document paths.
    """
    value = relative.as_posix()
    if value.endswith(".en.md"):
        return value[:-6] + ".md"
    return value


def is_current_document(relative: Path) -> bool:
    """中文：区分当前 V7.3 文档与只用于追溯的历史资料。

    English: Separate current V7.3 documentation from historical reference material.
    """
    value = normalized_document_path(relative)
    return value in CURRENT_DOCUMENTS or value.startswith(
        f"releases/{CURRENT_RELEASE_DIRECTORY}/")


def mark_historical_pages(output: Path) -> int:
    """中文：为历史页增加醒目标记，并将其排除在默认站内搜索之外。

    English: Mark historical pages prominently and exclude them from default site search.
    """
    notices = {
        "zh-CN": (
            '!!! warning "历史版本资料"\n'
            f"    本页记录旧版本当时的设计、操作或验证事实，不是 V{PACKAGE_VERSION} 当前使用说明。"
            "请从文档中心进入当前规范。\n\n"
        ),
        "en": (
            '!!! warning "Historical version"\n'
            f"    This page records design, operation, or validation facts from an earlier release. "
            f"It is not current V{PACKAGE_VERSION} guidance. Start from the documentation hub for current instructions.\n\n"
        ),
    }
    metadata = "---\nsearch:\n  exclude: true\n---\n\n"
    marked = 0
    for language, notice in notices.items():
        docs_root = output / language / "docs"
        for path in sorted(docs_root.rglob("*.md")):
            relative = path.relative_to(docs_root)
            if is_current_document(relative):
                continue
            original = path.read_text(encoding="utf-8-sig")
            path.write_text(metadata + notice + original, encoding="utf-8", newline="\n")
            marked += 1
    return marked


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
    validate_version_bound_sources()
    output = output.resolve()
    reset_output(output)
    shutil.copyfile(SITE_TEMPLATE / "index.md", output / "index.md")
    copy_files(SITE_TEMPLATE / "stylesheets", output / "stylesheets", lambda _: True)
    copy_files(SITE_TEMPLATE / "javascripts", output / "javascripts", lambda _: True)

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
    copy_english_pairs(ROOT / "docs", english / "docs")
    copy_files(ROOT / "locales" / "en" / "docs", english / "docs", lambda _: True)
    reconstructed = ROOT / "docs" / "history" / "RECONSTRUCTED_HISTORY.en.md"
    if reconstructed.is_file():
        target = english / "docs" / "history" / "RECONSTRUCTED_HISTORY.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(reconstructed, target)

    historical_markdown = mark_historical_pages(output)
    rewrite_site_links(output)
    markdown_files = list(output.rglob("*.md"))
    return {
        "ok": True,
        "output": output.as_posix(),
        "markdown_files": len(markdown_files),
        "chinese_markdown": len(list(chinese.rglob("*.md"))),
        "english_markdown": len(list(english.rglob("*.md"))),
        "historical_markdown": historical_markdown,
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
