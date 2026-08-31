#!/usr/bin/env python3
"""中文：管理非破坏 V6.6 事件归档与健康报告。

English: Manage non-destructive V6.6 event archives and health reports.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.event_archive import (EventArchiveError, archive_closed_segments, capacity_report,
                                      health_overview, verify_archive)  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.6 event archive and capacity utility")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("archive", "verify"):
        item = sub.add_parser(name); item.add_argument("--event-file", required=True); item.add_argument("--archive-root")
    capacity = sub.add_parser("capacity"); capacity.add_argument("--project-dir", required=True)
    health = sub.add_parser("health"); health.add_argument("--project-context-root", required=True); health.add_argument("--keyring")
    args = parser.parse_args()
    if args.command == "archive": report = archive_closed_segments(Path(args.event_file), Path(args.archive_root) if args.archive_root else None)
    elif args.command == "verify": report = verify_archive(Path(args.event_file), Path(args.archive_root) if args.archive_root else None)
    elif args.command == "capacity": report = capacity_report(Path(args.project_dir))
    else: report = health_overview(Path(args.project_context_root), Path(args.keyring) if args.keyring else None)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except EventArchiveError as exc:
        print(json.dumps({"ok": False, "error_code": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
