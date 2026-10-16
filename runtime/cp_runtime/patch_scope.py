"""中文：原生补丁路径的有界分类，不授予文件权限。
English: Bounded native patch classification; never a filesystem permission grant.
"""
from __future__ import annotations

import os
import re
import stat
import time
from pathlib import Path

from .atomic_io import native_path
from .capability_store import CapabilityError, relative_path
from .patch_intent import MAX_PATH_BYTES, PatchIntentError, patch_entries

MAX_NODES = 512
MAX_SECONDS = 1.0


class PathBudget:
    """中文：一次调用共享祖先检查和总时限。 English: Share ancestor checks and a total deadline per call."""

    def __init__(self):
        self.deadline = time.monotonic() + MAX_SECONDS
        self.nodes = {}

    def stat(self, path: Path):
        if time.monotonic() >= self.deadline:
            raise PatchIntentError("PATH_LOOKUP_LIMIT")
        if path not in self.nodes:
            if len(self.nodes) >= MAX_NODES:
                raise PatchIntentError("PATH_LOOKUP_LIMIT")
            try:
                value = native_path(path).lstat()
            except FileNotFoundError:
                value = None
            except OSError:
                raise PatchIntentError("PATH_UNREADABLE") from None
            if value is not None and (stat.S_ISLNK(value.st_mode)
                    or getattr(value, "st_file_attributes", 0) & 0x400):
                raise PatchIntentError("LINK_REJECTED")
            self.nodes[path] = value
        return self.nodes[path]

    def absolute(self, value: str, cwd: Path) -> Path:
        if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
            raise PatchIntentError("INVALID_PATH")
        if len(value.encode("utf-8")) > MAX_PATH_BYTES:
            raise PatchIntentError("PATH_TOO_LONG")
        normalized = value.replace("\\", "/")
        supplied = Path(value)
        if normalized.startswith(("//", "~")) or (supplied.drive and not supplied.is_absolute()):
            raise PatchIntentError("INVALID_PATH")
        parts = normalized.split("/")
        if ".." in parts:
            raise PatchIntentError("PATH_ESCAPE")
        # 中文：盘符只可出现在Windows绝对路径首部。 English: A drive prefix is valid only in a Windows absolute path.
        tail = parts[1:] if supplied.is_absolute() else parts
        if (not tail or any(part in {"", "."} or part.endswith((" ", ".")) or ":" in part for part in tail)
                or (not supplied.is_absolute() and (":" in normalized or "\\" in value))):
            raise PatchIntentError("INVALID_PATH")
        if os.name == "nt" and any(re.fullmatch(
                r"(?i:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?", part)
                or any(c in part for c in '<>"|?*') for part in tail):
            raise PatchIntentError("INVALID_PATH")
        absolute = Path(os.path.abspath(supplied if supplied.is_absolute() else cwd / supplied))
        if len(absolute.parents) > 64:
            raise PatchIntentError("PATH_LOOKUP_LIMIT")
        return absolute

    def resolve(self, value: str, cwd: Path) -> Path:
        absolute = self.absolute(value, cwd)
        for parent in reversed((absolute, *absolute.parents)):
            self.stat(parent)
        try:
            resolved = absolute.resolve()
        except OSError:
            raise PatchIntentError("PATH_UNREADABLE") from None
        if resolved != absolute:
            raise PatchIntentError("PATH_ALIAS_REJECTED")
        return resolved

    def control_path(self, value: str, cwd: Path) -> tuple[Path, Path]:
        """中文：只为登记控制路径查找本地别名；此方法不验证或授权写入目标。
        English: Resolve local aliases only for registered controls, never to admit write targets.
        """
        if isinstance(value, str) and value.replace("\\", "/").startswith("//"):
            normalized = value.replace("\\", "/")
            remote = Path(value)
            if (normalized.startswith(("//?/", "//./")) or not remote.is_absolute()
                    or any(part in {"", ".", ".."} for part in normalized[2:].split("/"))
                    or len(value.encode("utf-8")) > MAX_PATH_BYTES
                    or any(ord(char) < 32 for char in value)):
                raise PatchIntentError("CONTROL_SCOPE_INVALID")
            # 中文：远端登记仅保留路径边界，不为本地写入探测远端；实际UNC写入仍拒绝。
            # English: Keep remote control boundaries without network I/O; actual UNC writes remain rejected.
            return remote, remote
        original = current = self.absolute(value, cwd)
        followed = set()
        while True:
            for parent in reversed((current, *current.parents)):
                try:
                    self.stat(parent)
                except PatchIntentError as exc:
                    if str(exc) != "LINK_REJECTED":
                        raise
                    key = os.path.normcase(str(parent))
                    if key in followed or len(followed) >= 16:
                        raise PatchIntentError("CONTROL_ALIAS_LIMIT")
                    followed.add(key)
                    try:
                        before = native_path(parent).lstat()
                        target = os.readlink(native_path(parent))
                        after = native_path(parent).lstat()
                    except OSError:
                        raise PatchIntentError("CONTROL_ALIAS_UNREADABLE") from None
                    stamp = lambda item: (item.st_dev, item.st_ino, item.st_mtime_ns)
                    if stamp(before) != stamp(after):
                        raise PatchIntentError("CONTROL_ALIAS_CHANGED")
                    # 中文：Windows junction 返回设备前缀；只接受本地盘符，不访问网络别名。
                    # English: Junctions return a device prefix; accept local drives only, never network aliases.
                    if os.name == "nt" and target.startswith("\\\\?\\"):
                        if not re.match(r"^[A-Za-z]:[\\/]", target[4:]):
                            raise PatchIntentError("CONTROL_ALIAS_NONLOCAL")
                        target = target[4:]
                    if target.replace("\\", "/").startswith("//"):
                        raise PatchIntentError("CONTROL_ALIAS_NONLOCAL")
                    link = Path(target)
                    if link.drive and not link.is_absolute():
                        raise PatchIntentError("CONTROL_ALIAS_NONLOCAL")
                    resolved = Path(os.path.abspath(link if link.is_absolute() else parent.parent / link))
                    current = self.absolute(str(resolved / current.relative_to(parent)), cwd)
                    break
            else:
                try:
                    canonical = self.resolve(str(current.resolve()), cwd)
                except (OSError, RuntimeError):
                    raise PatchIntentError("CONTROL_ALIAS_UNREADABLE") from None
                return original, canonical


def classify_patch(command: str, repo: Path, cwd: Path) -> tuple[str, list[Path], PathBudget]:
    """中文：所有源与目标必须属于一个域。 English: All sources and destinations must share one domain."""
    _, entries = patch_entries(command)
    budget = PathBudget()
    targets, keys, domains = [], set(), set()
    for _, source, destination in entries:
        for value in (source, destination):
            if value is None:
                continue
            path = budget.resolve(value, cwd)
            inside = path.is_relative_to(repo)
            domains.add(inside)
            if not inside and not Path(value).is_absolute():
                raise PatchIntentError("PATH_ESCAPE")
            if inside:
                try:
                    relative_path(path.relative_to(repo).as_posix())
                except CapabilityError as exc:
                    raise PatchIntentError(str(exc)) from None
            key = os.path.normcase(str(path))
            if key in keys:
                raise PatchIntentError("DUPLICATE_TARGET")
            keys.add(key)
            state = budget.stat(path)
            if state and not stat.S_ISREG(state.st_mode):
                raise PatchIntentError("TARGET_DIRECTORY")
            targets.append(path)
    if len(domains) != 1:
        raise PatchIntentError("MIXED_PATH_SCOPE")
    return ("repository" if True in domains else "artifact"), targets, budget
