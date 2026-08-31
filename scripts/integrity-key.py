#!/usr/bin/env python3
"""Manage the V6.5 host-bound integrity keyring without exporting secrets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.integrity import IntegrityError, init_keyring, keyring_status, rotate_key, verify_keyring  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.5 integrity keyring")
    parser.add_argument("--keyring")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    rotate = commands.add_parser("rotate")
    rotate.add_argument("--purpose", required=True, choices=["event-hmac", "release-attestation"])
    commands.add_parser("status")
    commands.add_parser("verify")
    args = parser.parse_args()
    path = Path(args.keyring) if args.keyring else None
    if args.command == "init":
        result = init_keyring(path)
    elif args.command == "rotate":
        result = rotate_key(args.purpose, path)
    elif args.command == "verify":
        result = verify_keyring(path)
    else:
        result = keyring_status(path)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except IntegrityError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
