from __future__ import annotations
import re,json,hashlib,hmac,unicodedata
from datetime import datetime,timezone
from pathlib import PurePosixPath
from typing import Any,Mapping,Tuple

MANIFEST_NAME = "SOURCE_MANIFEST.json"

MAX_FILES = 10000

class SourceError(RuntimeError):
    pass

def relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise SourceError("invalid source path")
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or path.as_posix() != value or any(
        part in {".", ".."} or part.endswith((".", " "))
        or re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", part)
        for part in path.parts
    ) or any(ord(char) < 32 or char in '\\:<>"|?*' for char in value):
        raise SourceError("unsafe source path: %s" % value)
    return value

def _paths(values: list[str]) -> list[str]:
    if not values or len(values) > MAX_FILES:
        raise SourceError("source file count is outside capture limits")
    folded: set[str] = set()
    directories: set[str] = set()
    spelling: dict[str, str] = {}
    for value in values:
        relative_path(value)
        for item in (PurePosixPath(value), *PurePosixPath(value).parents):
            name = item.as_posix()
            if spelling.setdefault(name.casefold(), name) != name:
                raise SourceError("case-colliding source path: %s" % value)
        lowered = value.casefold()
        if lowered in folded or lowered in directories or any(
            parent.as_posix().casefold() in folded for parent in PurePosixPath(value).parents
        ):
            raise SourceError("duplicate/colliding source path: %s" % value)
        if value == MANIFEST_NAME or ".git" in PurePosixPath(value).parts:
            raise SourceError("source manifest cannot list itself or Git metadata")
        folded.add(lowered)
        directories.update(parent.as_posix().casefold() for parent in PurePosixPath(value).parents)
    return sorted(values)
