#!/usr/bin/env python3
"""中文：拒绝活动产物重新引入宿主实际模型身份契约。

English: Reject host runtime model-identity contracts in active artifacts.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".md", ".json", ".toml", ".yaml", ".yml", ".ps1", ".sh", ".cmd"}
PROHIBITED = (
    "actual" + "_model",
    "actual" + "_reasoning_effort",
    "runtime" + "_model",
    "runtime" + "_reasoning_effort",
    "recommended" + "_model",
    "diagnostic" + "_model_observation",
    "declared" + "_runtime_profile",
    "runtime" + "_model_evidence",
    "host" + "_runtime_attestation",
    "actual" + "_profile",
    "runtime" + "_evidence",
    "top" + "_up_units",
    "ACTUAL" + "_PROFILE_TOP_UP_EXCEEDED",
)


def allowed(relative: Path) -> bool:
    posix = relative.as_posix()
    if posix == "scripts/privacy-boundary-lint.py":
        return True
    if posix.startswith("tests/") or "/tests/" in posix:
        return True
    parts = relative.parts
    historical_release = (
        len(parts) >= 4 and parts[:2] == ("docs", "releases")
        and parts[2].startswith("v") and parts[2] != "v7.4.4"
    ) or (
        len(parts) >= 6 and parts[:4] == ("locales", "en", "docs", "releases")
        and parts[4].startswith("v") and parts[4] != "v7.4.4"
    )
    if historical_release:
        return True
    if posix.endswith("task-outcome-event-v2.md"):
        return True
    if posix.startswith("docs/USER_GUIDE_V6") or posix.startswith("locales/en/docs/USER_GUIDE_V6"):
        return True
    if posix.endswith("V7_4_1_CODEX_COMPATIBILITY_DESIGN.md") \
            or posix.endswith("V7_4_1_CODEX_COMPATIBILITY_DESIGN.en.md"):
        return True
    return False


def active_lines(relative: Path, text: str):
    """中文：返回活动代码行，并排除显式限定的旧版只读解析范围。

    English: Yield active lines while excluding explicitly delimited legacy-reader scopes.
    """
    legacy_capable = relative.as_posix() in {
        "runtime/cp_runtime/event_v2.py", "runtime/cp_runtime/delegation_budget.py",
    }
    inside_legacy_reader = False
    for number, line in enumerate(text.splitlines(), 1):
        if "PRIVACY_LEGACY_READER_BEGIN" in line:
            if not legacy_capable or inside_legacy_reader:
                yield number, line
            inside_legacy_reader = True
            continue
        if "PRIVACY_LEGACY_READER_END" in line:
            if not legacy_capable or not inside_legacy_reader:
                yield number, line
            inside_legacy_reader = False
            continue
        if not inside_legacy_reader:
            yield number, line
    if inside_legacy_reader:
        yield len(text.splitlines()) + 1, "UNCLOSED_PRIVACY_LEGACY_READER_SCOPE"


def main() -> int:
    failures = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(ROOT)
        if relative.parts and relative.parts[0] in {".git", "packages", "test-results", "project-context"}:
            continue
        if allowed(relative):
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            continue
        for number, line in active_lines(relative, text):
            for field in PROHIBITED:
                if field in line:
                    failures.append("%s:%d: %s" % (relative.as_posix(), number, field))
    if failures:
        for failure in failures:
            print("[FAIL] 宿主模型身份禁止项: " + failure)
        return 1
    print("[OK] 活动代码、配置、当前文档和发布脚本不包含宿主实际模型身份字段")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
