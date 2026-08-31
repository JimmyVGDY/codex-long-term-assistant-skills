"""中文：有界原子文件发布辅助函数。

English: Bounded atomic file publication helpers.
"""
from __future__ import annotations

import os
import time
from pathlib import Path


WINDOWS_TRANSIENT_FILE_ERRORS = {5, 32, 33}


def replace_with_retry(source: str | Path, target: str | Path, timeout: float = 0.75) -> None:
    """中文：替换单个文件，只重试 Windows 短暂共享冲突。

    English: Replace one file, retrying only transient Windows sharing failures.
    """
    deadline = time.monotonic() + max(0.0, timeout)
    delay = 0.005
    while True:
        try:
            os.replace(source, target)
            return
        except OSError as exc:
            transient = os.name == "nt" and getattr(exc, "winerror", None) in WINDOWS_TRANSIENT_FILE_ERRORS
            if not transient or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.05)
