"""中文：保留历史路径字符串，同时识别已证实等价的 Windows 命名空间。

English: Recognize proven Windows namespace aliases without rewriting stored identities.
"""
from __future__ import annotations

import os
import re
from pathlib import Path


def _alternate_windows_spelling(value: str) -> str | None:
    if value.upper().startswith("\\\\?\\UNC\\"):
        return "\\\\" + value[8:]
    if value.startswith("\\\\?\\"):
        tail = value[4:]
        return tail if re.match(r"^[A-Za-z]:\\", tail) else None
    if re.match(r"^[A-Za-z]:\\", value):
        return "\\\\?\\" + value
    if value.startswith("\\\\") and not value.startswith(("\\\\.\\", "\\??\\")):
        return "\\\\?\\UNC\\" + value[2:]
    return None


def path_aliases(path: Path, *, preserve_spelling: bool = False) -> tuple[Path, ...]:
    """中文：返回同一实体的命名空间拼写。校验历史指纹时保留已核实的旧路径。
    English: Keep the proven historical spelling when checking a recorded path fingerprint.
    """
    primary = path if preserve_spelling else path.expanduser().resolve()
    if os.name != "nt":
        return (primary,)
    alternate = _alternate_windows_spelling(str(primary))
    if alternate is None:
        return (primary,)
    candidate = Path(alternate) if preserve_spelling else Path(alternate).resolve()
    if candidate != primary and os.path.samefile(primary, candidate):
        return primary, candidate
    return (primary,)


def same_path(left: Path, right: Path) -> bool:
    """中文：保留原有相等语义；别名必须指向同一存在实体。

    English: Preserve exact-path behavior and require filesystem proof for aliases.
    """
    left, right = left.expanduser().resolve(), right.expanduser().resolve()
    if left == right:
        return True
    alternate = _alternate_windows_spelling(str(left)) if os.name == "nt" else None
    # 中文：不同路径无需实体核验，未创建的合法子目标仍保持原有行为。
    # English: Unrelated paths need no entity probe, including a not-yet-created child.
    if alternate is None or Path(alternate) != right:
        return False
    return os.path.samefile(left, right)


def path_is_within(child: Path, parent: Path) -> bool:
    """中文：普通路径保持快速判断；只有可能匹配的别名才核对实体。

    English: Keep the ordinary fast path and prove only a potentially containing alias.
    """
    child, parent = child.resolve(), parent.resolve()
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        pass
    alternate = _alternate_windows_spelling(str(parent)) if os.name == "nt" else None
    if alternate is None:
        return False
    candidate = Path(alternate)
    try:
        child.relative_to(candidate)
    except ValueError:
        return False
    return os.path.samefile(parent, candidate)
