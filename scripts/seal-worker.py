#!/usr/bin/env python3
"""中文：在 Hook 预算外处理签名 SessionEnd 追加与封印任务。

English: Process signed SessionEnd append-and-seal jobs outside the Hook budget.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.seal_queue import SealQueueError, process_queue  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.6 delayed event seal worker")
    parser.add_argument("--queue", required=True)
    parser.add_argument("--keyring")
    parser.add_argument("--max-jobs", type=int, default=100)
    args = parser.parse_args()
    report = process_queue(Path(args.queue), Path(args.keyring) if args.keyring else None, args.max_jobs)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except SealQueueError as exc:
        print(json.dumps({"ok": False, "error_code": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
