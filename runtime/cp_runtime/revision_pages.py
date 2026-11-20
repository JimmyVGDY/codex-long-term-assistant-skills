"""中文：封存已记录的修订页，保持幂等引用与全局修订号。
English: Archive full revision pages without reusing revision numbers or request references.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .capability_gate import _read, _write
from .capability_store import safe_path
from .routing_contract import exact, fail, ref


@dataclass
class Page:
    rows: list
    start: int = 0
    previous: str | None = None
    baseline: object = None
    boundary: str | None = None

    @property
    def revision(self) -> int:
        return self.start + len(self.rows)

    def header(self) -> dict:
        if not self.start:
            return {}
        return {
            "page": {
                "start": self.start,
                "previous": self.previous,
                "baseline": self.baseline,
                "boundary": self.boundary,
            }
        }


def _archive(path: Path, through: int) -> Path:
    return safe_path(path.parent / (path.stem + ".history") / (str(through) + ".json"))


def decode(value: dict, rows_key: str) -> Page:
    info = value.get("page")
    if info is None:
        return Page(value[rows_key])
    exact(info, {"start", "previous", "baseline", "boundary"}, "REVISION_PAGE_FIELDS")
    if type(info["start"]) is not int or info["start"] <= 0 or not isinstance(info["previous"], str):
        fail("REVISION_PAGE_BOUNDARY")
    return Page(value[rows_key], info["start"], info["previous"], info["baseline"], info["boundary"])


def read_previous(path: Path, through: int, witness: str, limit: int) -> dict:
    old = _read(_archive(path, through), limit)
    if ref(old) != witness:
        fail("REVISION_ARCHIVE_CHANGED")
    return old


def roll(path: Path, page: Page, baseline, boundary, limit: int) -> Page:
    old = _read(path, limit)
    target = _archive(path, page.revision)
    if target.exists():
        if _read(target, limit) != old:
            fail("REVISION_ARCHIVE_CONFLICT")
    else:
        unsigned = {k: v for k, v in old.items() if k != "integrity"}
        if _write(target, unsigned, limit) != old:
            fail("REVISION_ARCHIVE_CHANGED")
    return Page([], page.revision, ref(old), baseline, boundary)


def old_row(path, page, revision, rows_key, limit):
    while revision < page.start:
        old = read_previous(path, page.start, page.previous, limit)
        previous = decode(old, rows_key)
        if previous.revision != page.start or previous.start >= page.start:
            fail("REVISION_ARCHIVE_SEQUENCE")
        page = previous
    if not page.start <= revision < page.revision:
        return None
    return page.rows[revision - page.start]
