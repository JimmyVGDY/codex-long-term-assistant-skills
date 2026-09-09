"""中文：可选能力索引命令；不改变现有项目接管和刷新默认行为。 English: Optional capability commands without changing onboarding or refresh defaults."""
from __future__ import annotations

import json
from pathlib import Path

from .capability_index import coverage_summary, invalidate, lifecycle, query, register, scan
from .capability_store import CapabilityError, CapabilityStore, bounded_read, empty_payload, unique_json_object


def run(args):
    store = CapabilityStore(Path(args.profile), Path(args.repo_path), Path(args.index_root) if args.index_root else None)
    if args.capability_action == "init":
        record = store.commit(empty_payload(), None)
        return {"revision": record["revision"], "index_root": str(store.root)}
    if args.capability_action == "scan":
        return scan(store, args.scope, resume=args.resume)
    if args.capability_action == "query":
        return query(store, args.term, args.limit, include_inactive=args.include_inactive)
    if args.capability_action == "invalidate":
        return invalidate(store, args.changed_path, args.expected_revision)
    if args.capability_action == "validate":
        record = store.read()
        return {"status": "VALID", "revision": record["revision"], "entry_count": len(record["entries"]),
                "coverage": coverage_summary(record["coverage"]), "semantic_reuse_approved": False}
    if args.capability_action == "recover":
        record = store.recover(args.expected_current_sha256)
    elif args.capability_action == "register":
        try:
            entry = json.loads(bounded_read(Path(args.entry)), object_pairs_hook=unique_json_object)
        except (ValueError, UnicodeError, RecursionError):
            raise CapabilityError("INVALID_ENTRY_JSON") from None
        record = register(store, entry, args.expected_revision)
    else:
        record = lifecycle(store, args.entry_id, args.lifecycle, args.reason, args.expected_revision)
    return {"revision": record["revision"], "entry_count": len(record["entries"])}


def _emit_result(args):
    # 中文：ASCII转义后的JSON不依赖Windows控制台代码页，读取方解码仍获得原中文。 English: ASCII-escaped JSON avoids Windows code-page dependence while preserving decoded Chinese.
    print(json.dumps(run(args), ensure_ascii=True, indent=2))


def add_commands(subparsers):
    for action in ("init", "scan", "query", "validate", "recover", "register", "lifecycle", "invalidate"):
        parser = subparsers.add_parser("capability-" + action)
        parser.add_argument("--profile", required=True)
        parser.add_argument("--repo-path", required=True)
        parser.add_argument("--index-root", help="Exact snapshot directory override; normally omit for the worktree default, not its parent capability-index directory.")
        parser.set_defaults(capability_action=action, func=_emit_result)
        if action == "scan":
            parser.add_argument("--scope", action="append")
            parser.add_argument("--resume", action="store_true")
        elif action == "query":
            parser.add_argument("--term", required=True)
            parser.add_argument("--limit", type=int, default=5)
            parser.add_argument("--include-inactive", action="store_true")
        elif action == "recover":
            parser.add_argument("--expected-current-sha256", required=True)
        elif action in {"register", "lifecycle", "invalidate"}:
            parser.add_argument("--expected-revision", type=int, required=True)
            if action == "register":
                parser.add_argument("--entry", required=True)
            elif action == "invalidate":
                parser.add_argument("--changed-path", action="append", required=True)
            else:
                parser.add_argument("--entry-id", required=True)
                parser.add_argument("--lifecycle", required=True, choices=("candidate", "active", "deprecated", "removed"))
                parser.add_argument("--reason", required=True)
