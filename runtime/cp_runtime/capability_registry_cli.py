"""中文：能力注册、选择与显式偏好的只读/原子 CLI。 English: Registry, selection, and atomic preference CLI."""
from __future__ import annotations

import json
from pathlib import Path

from .capability_registry import PreferenceStore, load_registry, migrate_legacy_classification, select_capability
from .capability_store import require

DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / "config" / "capability-registry-v1.json"


def _registry(args):
    return load_registry(Path(args.registry) if args.registry else DEFAULT_REGISTRY)


def _prerequisites(values):
    result = {}
    for value in values or []:
        name, separator, raw = value.partition("=")
        require(separator == "=" and name and raw in {"true", "false"} and name not in result, "PREREQUISITE_ARGUMENT")
        result[name] = raw == "true"
    return result


def run(args):
    if args.registry_action == "show":
        return _registry(args)
    store = PreferenceStore(Path(args.profile), Path(args.repo_path))
    if args.registry_action == "preference-show":
        current = store.read()
        return {"configured_mode": "AUTO", "max_level": None, "source": "DEFAULT_NO_FILE",
                "revision": None, "persisted": False} if current is None else {
                    "revision": current["revision"], "persisted": True,
                    "preference": current["preferences"].get(args.capability_id),
                }
    if args.registry_action == "preference-set":
        return store.set_preference(args.capability_id, args.configured_mode, args.max_level,
                                    args.expected_revision, "USER")
    if args.registry_action == "preference-migrate":
        migrated = migrate_legacy_classification(args.classification)
        return store.set_preference(args.capability_id, migrated["configured_mode"], migrated["max_level"],
                                    args.expected_revision, args.classification)
    registry = _registry(args)
    return select_capability(registry, args.capability_id, _prerequisites(args.prerequisite),
                             store.preference(args.capability_id), args.risk)


def _emit(args):
    print(json.dumps(run(args), ensure_ascii=True, indent=2))


def add_commands(subparsers):
    parser = subparsers.add_parser("capability-registry")
    parser.add_argument("--registry")
    parser.set_defaults(registry_action="show", func=_emit)

    parser = subparsers.add_parser("capability-select")
    parser.add_argument("--registry")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--capability-id", required=True)
    parser.add_argument("--prerequisite", action="append")
    parser.add_argument("--risk", choices=("LIGHT", "STANDARD", "STRICT", "UNKNOWN"), default="UNKNOWN")
    parser.set_defaults(registry_action="select", func=_emit)

    for command, action in (("capability-preference-show", "preference-show"),
                            ("capability-preference-set", "preference-set"),
                            ("capability-preference-migrate", "preference-migrate")):
        parser = subparsers.add_parser(command)
        parser.add_argument("--profile", required=True)
        parser.add_argument("--repo-path", required=True)
        parser.add_argument("--capability-id", required=True)
        parser.set_defaults(registry_action=action, func=_emit)
        if action == "preference-set":
            parser.add_argument("--configured-mode", choices=("AUTO", "OFF"), required=True)
            parser.add_argument("--max-level", choices=("BASIC", "ASSISTED", "FULL"))
            parser.add_argument("--expected-revision", type=int)
        elif action == "preference-migrate":
            parser.add_argument("--classification", choices=("DEFAULT_OFF", "USER_OFF", "UNKNOWN_OFF", "LEGACY_ON"), required=True)
            parser.add_argument("--expected-revision", type=int)
