"""中文：评测、卡片与观察的桌面内部管理命令。

English: Desktop-internal evaluation, publication and observation controls.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import budget_v4, calibration_v4, routing_evaluation_v4 as evaluation
from .common import atomic_write_json, repo_snapshot, require_external_state, utc_now
from .routing_cards import (approval_binding_note, build_bundle, publish_bundle, revoke_publication)
from .routing_context_v4 import _trace_loader, verify_root
from .routing_contract import exact, fail, policy, read_document, ref

COMMANDS = {
    "eval-plan": ("spec", "case-sources", "output"),
    "eval-suite": ("plans", "output"),
    "eval-request": ("ledger", "slot-id", "case-id", "profile-id", "prompt-file", "output"),
    "eval-result": ("ledger", "reservation-id", "response-file", "gold-file", "rubric-file", "grade"),
    "eval-assemble": ("evaluation", "trial-sources", "experiment-id", "issuer-task-id", "output"),
    "bundle-build": ("experiment", "costs", "bundle-id", "expires-at", "output"),
    "publish": ("bundle", "experiment", "trace-ledgers", "approval", "publication-id", "output"),
    "revoke-publication": ("publication", "reason-ref"),
    "sample-pending": ("ledger", "reservation-id", "result-file", "metrics", "output"),
    "sample-finalize": ("sample", "sources", "output"),
    "sample-report": ("samples", "sources", "output"),
    "revoke-prepare": ("ledger", "permit-id", "reason-ref"),
    "eval-advance": ("ledger", "slot-id", "previous-result-ref", "next-packet-sha256"),
    "add-evidence": ("ledger", "evidence-sources"),
}


def add_commands(subparsers) -> None:
    for name, fields in COMMANDS.items():
        command = subparsers.add_parser(name)
        for field in fields:
            command.add_argument("--" + field, required=True)
        if name in {"eval-request", "eval-result", "revoke-prepare", "eval-advance", "add-evidence"}:
            command.add_argument("--host-session-id", default=os.environ.get("CODEX_THREAD_ID", ""))
        if name in {"eval-request", "eval-result"}:
            command.add_argument("--repetition", type=int, default=1)
        if name in {"bundle-build", "publish"}:
            command.add_argument("--consumption", choices=["issuer-only", "project-bound-reuse"],
                                 default="project-bound-reuse")
        if name == "revoke-publication":
            command.add_argument("--expected-revision", type=int, required=True)


def document(path: str):
    return read_document(Path(path), maximum=policy()["limits"]["max_experiment_bytes"])[0]


def write_artifact(path: str, value: dict) -> dict:
    target = Path(path).resolve()
    require_external_state(target, Path.cwd().resolve())
    if target.exists():
        if document(str(target)) != value:
            fail("V4_ARTIFACT_ALREADY_EXISTS")
    else:
        atomic_write_json(target, value)
    return {"output": str(target), "content_ref": ref(value), "schema_version": value["schema_version"]}


def run(args) -> dict:
    name = args.command
    if name == "eval-suite":
        paths = exact(document(args.plans), {"paths"}, "EVALUATION_PLAN_SOURCES")["paths"]
        if not isinstance(paths, list) or not paths or len(paths) > policy()["limits"]["max_slots"]:
            fail("EVALUATION_SUITE_LIMIT")
        value = evaluation.create_suite([document(path) for path in paths])
        return {**write_artifact(args.output, value), "planned_trials": value["planned_trials"],
                "status": "PREREGISTERED_NOT_QUALIFIED"}
    if name == "eval-plan":
        cases = exact(document(args.case_sources), {"cases"}, "EVALUATION_CASE_SOURCES")
        value = evaluation.create_plan(document(args.spec), cases["cases"])
        result = write_artifact(args.output, value)
        profiles = {p for pair in value["comparisons"] for p in pair.values()}
        result.update(planned_trials=len(value["cases"]) * len(profiles) * value["repetitions"],
                      status="PREREGISTERED_NOT_QUALIFIED")
        return result
    if name == "eval-request":
        return write_artifact(args.output, evaluation.make_request(Path(args.ledger), cwd=os.getcwd(),
            host_session_id=args.host_session_id, slot_id=args.slot_id, case_id=args.case_id,
            profile_id=args.profile_id, repetition=args.repetition, prompt_path=Path(args.prompt_file)))
    if name == "eval-result":
        return evaluation.record_trial(Path(args.ledger), cwd=os.getcwd(), host_session_id=args.host_session_id,
            reservation_id=args.reservation_id, repetition=args.repetition, response_path=Path(args.response_file),
            gold_path=Path(args.gold_file), rubric_path=Path(args.rubric_file), grade=document(args.grade))
    if name == "eval-assemble":
        sources = exact(document(args.trial_sources), {"trials"}, "EVALUATION_TRIAL_SOURCES")
        value = evaluation.assemble_experiment(document(args.evaluation), sources["trials"],
            experiment_id=args.experiment_id, issuer_task_id=args.issuer_task_id,
            issuer_baseline=repo_snapshot(Path.cwd())["sha256"])
        return write_artifact(args.output, value)
    if name == "bundle-build":
        costs = exact(document(args.costs), {"costs"}, "V4_COST_DOCUMENT")
        value = build_bundle(document(args.experiment), costs["costs"], bundle_id=args.bundle_id,
                             created_at=utc_now(), expires_at=args.expires_at)
        result = write_artifact(args.output, value)
        result.update(qualified_profiles=[c["profile_id"] for c in value["qualification"] if c["qualified"]],
                      approval_note=approval_binding_note(value, args.consumption), status="UNPUBLISHED")
        return result
    if name == "publish":
        paths = exact(document(args.trace_ledgers), {"paths"}, "V4_TRACE_LEDGER_PATHS")["paths"]
        if not isinstance(paths, list) or not paths or len(paths) > 100:
            fail("V4_TRACE_SOURCE_LIMIT")
        value = publish_bundle(Path(args.output), document(args.bundle), document(args.experiment),
            approval_path=Path(args.approval), repo_path=Path.cwd(), trace_loader=_trace_loader(paths),
            publication_id=args.publication_id, consumption=args.consumption, now=utc_now())
        return {"status": value["status"], "publication_ref": ref(value), "revision": value["revision"]}
    if name == "revoke-publication":
        value = revoke_publication(Path(args.publication), expected_revision=args.expected_revision,
                                   reason_ref=args.reason_ref)
        return {"status": value["status"], "publication_ref": ref(value), "revision": value["revision"]}
    if name == "sample-pending":
        return write_artifact(args.output, calibration_v4.pending_sample(Path(args.ledger), args.reservation_id,
                              Path(args.result_file), document(args.metrics)))
    if name == "sample-finalize":
        sample, source = document(args.sample), document(args.sources)
        exact(source, {"ledger_path", "result_path", "evidence_paths"}, "V4_SAMPLE_SOURCE_REQUIRED")
        value = calibration_v4.finalize_sample(sample, ledger_path=Path(source["ledger_path"]),
            result_path=Path(source["result_path"]), evidence_paths=source["evidence_paths"],
            finalized_by="parent:" + sample["identity"]["task_id"])
        return write_artifact(args.output, value)
    if name == "sample-report":
        rows = exact(document(args.samples), {"samples"}, "V4_SAMPLE_REPORT_FIELDS")
        return write_artifact(args.output, calibration_v4.observation_report(rows["samples"],
                                                                             sources=document(args.sources)))
    state = budget_v4.read_budget(Path(args.ledger))
    verify_root(state, cwd=os.getcwd(), host_session_id=args.host_session_id)
    if name == "add-evidence":
        from .routing_context_v4 import add_current_evidence
        paths = exact(document(args.evidence_sources), {"paths"}, "V4_EVIDENCE_SOURCE_PATHS")["paths"]
        if not isinstance(paths, list) or not paths or len(paths) > 24:
            fail("V4_EVIDENCE_ADDITIONS_REQUIRED")
        value = add_current_evidence(Path(args.ledger), [Path(path) for path in paths],
                                     cwd=os.getcwd(), host_session_id=args.host_session_id)
    elif name == "revoke-prepare":
        value = budget_v4.revoke_prepare(Path(args.ledger), permit_id=args.permit_id, reason_ref=args.reason_ref)
    elif name == "eval-advance":
        value = budget_v4.advance_evaluation(Path(args.ledger), slot_id=args.slot_id,
                    previous_result_ref=args.previous_result_ref, next_packet_sha256=args.next_packet_sha256)
    else:
        fail("V4_CONTROL_COMMAND_UNKNOWN")
    return {"identity": value["identity"], "sequence": value["sequence"], "status": "RECORDED"}
