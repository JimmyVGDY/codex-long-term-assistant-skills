from __future__ import annotations
import re,json,hashlib,hmac,unicodedata
from datetime import datetime,timezone
from pathlib import PurePosixPath
from typing import Any,Mapping,Tuple

HAN_PATTERN = re.compile(r"[\u3400-\u9fff]")

RELEASE_NAME_MAX_CODEPOINTS = {"zh-CN": 30, "en": 80}

RELEASE_TITLE_MAX_CODEPOINTS = 125

RELEASE_TITLE_MAX_UTF8_BYTES = 200

GENERIC_RELEASE_NAMES = {
    "zh-CN": {"发行候选", "中英文发行候选"},
    "en": {"release candidate", "bilingual release candidate"},
}

class ReleaseWorkflowError(RuntimeError):
    """中文：表示发布输入、边界或受管产物不满足失败关闭条件。

    English: Report a release input, boundary, or managed-artifact fail-closed violation.
    """

def _release_name(value: Any, locale: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReleaseWorkflowError("%s release_name must be a non-empty trimmed string" % locale)
    if len(value) > RELEASE_NAME_MAX_CODEPOINTS[locale]:
        raise ReleaseWorkflowError("%s release_name is too long" % locale)
    if any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in value):
        raise ReleaseWorkflowError("%s release_name contains control characters" % locale)
    if value.casefold() in GENERIC_RELEASE_NAMES[locale]:
        raise ReleaseWorkflowError("%s release_name must describe this release" % locale)
    if locale == "zh-CN" and not HAN_PATTERN.search(value):
        raise ReleaseWorkflowError("zh-CN release_name must contain Chinese text")
    if locale == "en" and HAN_PATTERN.search(value):
        raise ReleaseWorkflowError("en release_name must not contain Chinese text")
    return value

def _release_title(version: str, chinese: str, english: str) -> str:
    value = "V%s | %s / %s" % (version, chinese, english)
    if len(value) > RELEASE_TITLE_MAX_CODEPOINTS \
            or len(value.encode("utf-8")) > RELEASE_TITLE_MAX_UTF8_BYTES:
        raise ReleaseWorkflowError("combined release title is too long")
    return value
