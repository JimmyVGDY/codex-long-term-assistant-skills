#!/usr/bin/env python3
"""中文：检查全仓库 Markdown 的本地链接、锚点与可选外部链接。

English: Check repository-wide Markdown paths, anchors, and optional external links.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_NAME = "codex-long-term-assistant-skills"
INLINE_LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
REFERENCE_LINK = re.compile(r"^\s*\[[^\]\n]+\]:\s*(\S+)", re.MULTILINE)
HTML_LINK = re.compile(r"\b(?:href|src)\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
HTML_ANCHOR = re.compile(r"\b(?:id|name)\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
FENCE = re.compile(r"^\s*(```|~~~)")
SKIPPED_SCHEMES = {"mailto", "tel", "data", "javascript"}
HARD_EXTERNAL_STATUS = {404, 410}
OVERLAY_BUILD_ALIASES = {
    "docs/history/RECONSTRUCTED_HISTORY.md": "docs/history/RECONSTRUCTED_HISTORY.en.md",
}


def tracked_markdown(root: Path = ROOT) -> list[Path]:
    """中文：返回受 Git 管理的 Markdown 文件，避免构建产物污染审计。

    English: Return Git-tracked Markdown files so build artifacts cannot pollute the audit.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"], cwd=root, capture_output=True, check=True)
    candidates = [root / Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]
    return [path for path in candidates if path.is_file()]


def visible_markdown(text: str) -> str:
    """中文：遮蔽围栏与行内代码，避免把示例语法误判为链接。

    English: Mask fenced and inline code so example syntax is not parsed as a link.
    """
    output: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        marker = FENCE.match(line)
        if marker:
            fence = None if fence == marker.group(1) else marker.group(1) if fence is None else fence
            output.append("")
            continue
        output.append("" if fence else re.sub(r"`[^`\n]*`", "", line))
    return "\n".join(output)


def link_target(raw: str) -> str:
    """中文：从 Markdown 目标中移除可选标题和尖括号包装。

    English: Remove an optional Markdown title and angle-bracket wrapper from a target.
    """
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1:value.index(">")]
    return re.split(r"\s+[\"'(]", value, maxsplit=1)[0]


def links_in(path: Path) -> list[tuple[int, str]]:
    """中文：提取 Markdown、引用式与 HTML 链接及其行号。

    English: Extract Markdown, reference-style, and HTML links with line numbers.
    """
    text = visible_markdown(path.read_text(encoding="utf-8-sig"))
    matches = [*INLINE_LINK.finditer(text), *REFERENCE_LINK.finditer(text), *HTML_LINK.finditer(text)]
    rows = [(text.count("\n", 0, match.start()) + 1, link_target(match.group(1))) for match in matches]
    return sorted(set(rows))


def github_slug(value: str) -> str:
    """中文：生成与 GitHub 标题锚点兼容的确定性标识。

    English: Generate a deterministic identifier compatible with GitHub heading anchors.
    """
    value = re.sub(r"<[^>]+>", "", value).strip().lower()
    value = re.sub(r"\s+", "-", value)
    return "".join(char for char in value if char in "-_" or not unicodedata.category(char).startswith(("P", "S")))


def anchors_in(path: Path) -> set[str]:
    """中文：收集标题和显式 HTML 锚点，并处理重复标题序号。

    English: Collect headings and explicit HTML anchors, including duplicate-heading suffixes.
    """
    text = visible_markdown(path.read_text(encoding="utf-8-sig"))
    anchors = set(HTML_ANCHOR.findall(text))
    counts: Counter[str] = Counter()
    for match in HEADING.finditer(text):
        base = github_slug(match.group(1))
        index = counts[base]
        counts[base] += 1
        anchors.add(base if index == 0 else f"{base}-{index}")
    return anchors


def issue(code: str, source: Path, line: int, target: str, detail: str = "") -> dict[str, Any]:
    """中文：创建稳定且可供 CI 读取的问题记录。

    English: Create a stable finding record suitable for CI consumption.
    """
    return {"code": code, "path": source.relative_to(ROOT).as_posix(), "line": line,
            "target": target, "detail": detail}


def repository_target(target: str) -> str | None:
    """中文：把当前仓库 main 分支的 GitHub URL 映射回本地路径。

    English: Map GitHub URLs for this repository's main branch back to local paths.
    """
    parsed = urllib.parse.urlsplit(target)
    parts = parsed.path.strip("/").split("/")
    if parsed.netloc.lower() == "github.com" and len(parts) >= 4 and parts[1] == REPOSITORY_NAME:
        remainder = "/".join(parts[2:])
        for kind in ("blob/main/", "tree/main/"):
            if remainder.startswith(kind):
                return urllib.parse.unquote(remainder[len(kind):]) + (
                    f"#{parsed.fragment}" if parsed.fragment else "")
    if (parsed.netloc.lower() == "raw.githubusercontent.com" and len(parts) >= 4
            and parts[1] == REPOSITORY_NAME and parts[2] == "main"):
        return urllib.parse.unquote("/".join(parts[3:]))
    return None


def exact_path(root: Path, relative: Path) -> Path | None:
    """中文：逐级匹配真实大小写，确保 Windows CI 也能发现 Linux 路径错误。

    English: Match exact path casing component by component so Windows CI catches Linux failures.
    """
    current = root
    for part in relative.parts:
        if part in ("", "."):
            continue
        if part == "..":
            current = current.parent
            continue
        if not current.is_dir():
            return None
        matches = [child for child in current.iterdir() if child.name == part]
        if len(matches) != 1:
            return None
        current = matches[0]
    return current


def overlay_relative(path: Path) -> Path | None:
    """中文：返回英文 overlay 文件在发行包中的最终相对路径。

    English: Return an English overlay file's final relative path in the distribution.
    """
    relative = path.relative_to(ROOT)
    if len(relative.parts) >= 3 and relative.parts[:2] == ("locales", "en"):
        return Path(*relative.parts[2:])
    return None


def local_finding(source: Path, line: int, target: str) -> dict[str, Any] | None:
    """中文：验证单个本地路径及其锚点。

    English: Validate one local path and its optional anchor.
    """
    mapped = repository_target(target)
    candidate = mapped if mapped is not None else target
    parsed = urllib.parse.urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        return None
    raw_path = urllib.parse.unquote(parsed.path).replace("\\", "/")
    overlay_source = overlay_relative(source)
    effective_source = ROOT / overlay_source if overlay_source is not None else source
    base = ROOT if raw_path.startswith("/") or mapped is not None else effective_source.parent
    relative = Path(raw_path.lstrip("/")) if raw_path else Path(effective_source.relative_to(ROOT))
    requested = base / relative if raw_path else ROOT / relative
    try:
        repository_relative = Path(requested.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return issue("LOCAL_PATH_OUTSIDE_REPOSITORY", source, line, target)
    resolved = None
    if overlay_source is not None and mapped is None:
        resolved = exact_path(ROOT, Path("locales") / "en" / repository_relative)
    if resolved is None:
        resolved = exact_path(ROOT, repository_relative)
    if resolved is None and overlay_source is not None:
        alias = OVERLAY_BUILD_ALIASES.get(repository_relative.as_posix())
        if alias:
            resolved = exact_path(ROOT, Path(alias))
    if resolved is None or not resolved.exists():
        return issue("LOCAL_TARGET_MISSING", source, line, target)
    if parsed.fragment and resolved.is_file() and resolved.suffix.lower() == ".md":
        fragment = urllib.parse.unquote(parsed.fragment)
        if fragment not in anchors_in(resolved):
            return issue("LOCAL_ANCHOR_MISSING", source, line, target, fragment)
    return None


def check_external(targets: Iterable[tuple[Path, int, str]], timeout: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """中文：探测外部链接；明确的 404/410 失败，权限或网络限制仅警告。

    English: Probe external links; fail on definite 404/410 and warn on access or network limits.
    """
    findings: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checked: dict[str, tuple[str, str]] = {}
    for source, line, target in targets:
        if target in checked:
            state, detail = checked[target]
        else:
            request = urllib.request.Request(target, headers={"User-Agent": "codex-link-audit/1.0"})
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    state, detail = "ok", str(response.status)
            except urllib.error.HTTPError as exc:
                state = "broken" if exc.code in HARD_EXTERNAL_STATUS else "warning"
                detail = f"HTTP {exc.code}"
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                state, detail = "warning", str(exc)
            checked[target] = state, detail
        if state == "broken":
            findings.append(issue("EXTERNAL_TARGET_MISSING", source, line, target, detail))
        elif state == "warning":
            warnings.append(issue("EXTERNAL_TARGET_UNVERIFIED", source, line, target, detail))
    return findings, warnings


def audit(files: Iterable[Path], external: bool = False, timeout: float = 10.0) -> dict[str, Any]:
    """中文：执行全仓库链接审计并返回机器可读报告。

    English: Run the repository-wide link audit and return a machine-readable report.
    """
    paths = list(files)
    findings: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    external_targets: list[tuple[Path, int, str]] = []
    link_count = 0
    for source in paths:
        for line, target in links_in(source):
            if not target:
                continue
            link_count += 1
            parsed = urllib.parse.urlsplit(target)
            if parsed.scheme.lower() in SKIPPED_SCHEMES:
                continue
            mapped = repository_target(target)
            if mapped is not None or not parsed.scheme:
                finding = local_finding(source, line, target)
                if finding:
                    findings.append(finding)
            elif parsed.scheme.lower() in {"http", "https"}:
                external_targets.append((source, line, target))
    if external:
        external_findings, external_warnings = check_external(external_targets, timeout)
        findings.extend(external_findings)
        warnings.extend(external_warnings)
    counts = Counter(row["code"] for row in findings)
    warning_counts = Counter(row["code"] for row in warnings)
    return {"ok": not findings, "schema_version": 1, "markdown_files": len(paths),
            "link_count": link_count, "external_checked": external,
            "finding_count": len(findings), "findings_by_code": dict(sorted(counts.items())),
            "warning_count": len(warnings), "warnings_by_code": dict(sorted(warning_counts.items())),
            "findings": findings, "warnings": warnings}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="全仓库 Markdown 链接检查 / Repository-wide Markdown link check")
    parser.add_argument("--external", action="store_true")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output")
    parser.add_argument("--strict", action="store_true")
    arguments = parser.parse_args()
    report = audit(tracked_markdown(), arguments.external, arguments.timeout)
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
