"""中文：首次引导与扫描任务 CLI；消息 Hook 不执行扫描。 English: First-use and scan-job CLI; message Hooks never scan."""
from __future__ import annotations

import json
from pathlib import Path

from .capability_index import scan
from .capability_store import CapabilityError, CapabilityStore, require, unique_json_object
from .onboarding import OnboardingStore


def _store(args):
    return OnboardingStore(Path(args.profile), Path(args.repo_path))


def _coverage(value: str):
    try:
        result = json.loads(value, object_pairs_hook=unique_json_object)
    except (ValueError, TypeError, RecursionError):
        raise CapabilityError("ONBOARDING_SCAN_COVERAGE") from None
    require(isinstance(result, dict), "ONBOARDING_SCAN_COVERAGE")
    return result


def run(args):
    store = _store(args)
    action = args.onboarding_action
    if action == "status":
        return {"offer": store.offer_status(), "scan": store.scan_status()}
    if action == "offer":
        return store.create_offer(args.scope or ["."], args.owner, args.ttl_seconds)
    if action == "renew":
        return store.renew_offer(args.expected_revision, args.nonce, args.ttl_seconds)
    if action == "respond":
        return store.respond(args.choice, args.nonce, args.expected_revision, args.source, args.response_ref)
    if action == "scan-queue":
        return store.queue_scan()
    if action == "scan-status":
        return store.scan_status()
    if action == "scan-claim":
        return store.claim_scan(args.owner, args.lease_seconds)
    if action == "scan-checkpoint":
        return store.checkpoint(args.lease_token, args.generation, args.cancel_epoch,
                                args.cursor, _coverage(args.coverage), lease_seconds=args.lease_seconds)
    if action == "scan-finish":
        return store.finish_scan(args.lease_token, args.generation, args.cancel_epoch,
                                 args.state, _coverage(args.coverage), args.reason)
    if action == "scan-cancel":
        return store.cancel_scan(args.reason)
    claimed = store.claim_scan(args.owner, args.lease_seconds)
    state = claimed["scan"]
    offer = store.offer_status()
    index_store = CapabilityStore(Path(args.profile), Path(args.repo_path),
                                  Path(args.index_root) if args.index_root else None)
    index_result = scan(index_store, offer["scope"])
    coverage = dict(index_result["coverage"])
    store.checkpoint(claimed["lease_token"], state["lease"]["generation"], state["cancel_epoch"],
                     "index-revision:%s" % index_result["revision"], coverage)
    terminal = "COMPLETED" if coverage.get("complete") is True else "PARTIAL"
    result = store.finish_scan(claimed["lease_token"], state["lease"]["generation"], state["cancel_epoch"],
                               terminal, coverage, "" if terminal == "COMPLETED" else "BOUNDED_SCAN_PARTIAL")
    return {"scan": result, "index": index_result}


def _emit(args):
    print(json.dumps(run(args), ensure_ascii=True, indent=2))


def add_commands(subparsers):
    common = {}
    for command, action in (
        ("onboarding-status", "status"), ("onboarding-offer", "offer"),
        ("onboarding-renew", "renew"), ("onboarding-respond", "respond"),
        ("onboarding-scan-queue", "scan-queue"), ("onboarding-scan-status", "scan-status"),
        ("onboarding-scan-claim", "scan-claim"), ("onboarding-scan-checkpoint", "scan-checkpoint"),
        ("onboarding-scan-finish", "scan-finish"), ("onboarding-scan-cancel", "scan-cancel"),
        ("onboarding-scan-run", "scan-run"),
    ):
        parser = subparsers.add_parser(command)
        parser.add_argument("--profile", required=True)
        parser.add_argument("--repo-path", required=True)
        parser.set_defaults(onboarding_action=action, func=_emit)
        common[action] = parser
    common["offer"].add_argument("--scope", action="append")
    common["offer"].add_argument("--owner", required=True)
    common["offer"].add_argument("--ttl-seconds", type=int, default=86400)
    common["renew"].add_argument("--expected-revision", type=int, required=True)
    common["renew"].add_argument("--nonce", required=True)
    common["renew"].add_argument("--ttl-seconds", type=int, default=86400)
    common["respond"].add_argument("--choice", choices=("ACCEPTED", "DECLINED"), required=True)
    common["respond"].add_argument("--nonce", required=True)
    common["respond"].add_argument("--expected-revision", type=int, required=True)
    common["respond"].add_argument("--source", choices=("MODEL_INTERPRETED_USER_REPLY", "HOST_STRUCTURED_REPLY"), required=True)
    common["respond"].add_argument("--response-ref", required=True)
    for action in ("scan-claim", "scan-run"):
        common[action].add_argument("--owner", required=True)
        common[action].add_argument("--lease-seconds", type=int, default=120)
    common["scan-run"].add_argument("--index-root")
    for action in ("scan-checkpoint", "scan-finish"):
        common[action].add_argument("--lease-token", required=True)
        common[action].add_argument("--generation", type=int, required=True)
        common[action].add_argument("--cancel-epoch", type=int, required=True)
        common[action].add_argument("--coverage", required=True)
    common["scan-checkpoint"].add_argument("--cursor", required=True)
    common["scan-checkpoint"].add_argument("--lease-seconds", type=int, default=120)
    common["scan-finish"].add_argument("--state", choices=("COMPLETED", "PARTIAL", "FAILED"), required=True)
    common["scan-finish"].add_argument("--reason", default="")
    common["scan-cancel"].add_argument("--reason", default="USER_CANCELLED")
