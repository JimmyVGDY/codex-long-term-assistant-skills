from __future__ import annotations
import os, stat, sys
from pathlib import Path, PosixPath, WindowsPath

class RuntimeContractError(RuntimeError):
    """中文：失败关闭的 Runtime 契约异常。

    English: A fail-closed runtime contract violation.
    """

def native_path(path: str | Path) -> Path:
    """中文：为 Windows 原子文件操作返回长路径安全的绝对路径。

    English: Return an absolute, long-path-safe path for Windows atomic file operations.
    """
    absolute = os.path.abspath(os.fspath(path))
    if sys.platform == "win32":
        if not absolute.startswith("\\\\?\\"):
            absolute = ("\\\\?\\UNC\\" + absolute[2:]
                        if absolute.startswith("\\\\") else "\\\\?\\" + absolute)
        return WindowsPath(absolute)
    return PosixPath(absolute)

MAX_BYTES = 8 * 1024 * 1024

class CapabilityError(RuntimeContractError):
    """中文：只暴露固定原因码，不把源内容或底层异常写入诊断。 English: Expose fixed reason codes without source content or underlying exception text."""

def require(condition: bool, code: str = "INVALID_SCHEMA") -> None:
    if not condition:
        raise CapabilityError(code)

def safe_path(path: Path) -> Path:
    """中文：解析前拒绝各级链接及 Windows reparse point。 English: Reject ancestor links and Windows reparse points before resolving paths."""
    path = Path(os.path.abspath(path.expanduser()))
    for item in reversed((path, *path.parents)):
        try:
            info = native_path(item).lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise CapabilityError("PATH_UNREADABLE") from None
        require(not stat.S_ISLNK(info.st_mode) and not (
            getattr(info, "st_file_attributes", 0) & 0x400
        ), "LINK_REJECTED")
    return path.resolve()

def bounded_read(path: Path, limit: int = MAX_BYTES) -> bytes:
    path = safe_path(path)
    try:
        before = native_path(path).stat()
        require(stat.S_ISREG(before.st_mode), "NOT_REGULAR_FILE")
        require(before.st_size <= limit, "TOO_LARGE")
        with native_path(path).open("rb") as stream:
            opened = os.fstat(stream.fileno())
            require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), "READ_CHANGED")
            data = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        final = native_path(safe_path(path)).stat()
        require(len(data) <= limit, "TOO_LARGE")
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
        # 中文：Windows路径stat与句柄fstat的ctime口径可能不同；各自前后比较。 English: Windows path stat and handle fstat may use different ctime semantics; compare each API before and after.
        require(stamp(before) == stamp(opened) == stamp(after) == stamp(final)
                and before.st_ctime_ns == final.st_ctime_ns
                and opened.st_ctime_ns == after.st_ctime_ns, "READ_CHANGED")
        return data
    except OSError:
        raise CapabilityError("UNREADABLE") from None
