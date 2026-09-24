#!/usr/bin/env python3
"""中文：为包验证采集简洁、受完整性绑定的 unittest 证据。

English: Collect concise, integrity-bound unittest evidence for package validation.

中文：报告只保留测试标识、结果类别和固定白名单中的异常类别代码，不保存断言正文、回溯、标准输出、标准错误或子测试参数。
English: The report keeps identifiers, outcome classes, and fixed-allowlist exception-class codes only; it never stores assertion text, tracebacks, stdout, stderr, or subtest parameters.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import unittest
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "validation-evidence/1"
SUCCESS = "PASS"
NON_PASSING = {"FAILURE", "ERROR", "SUBTEST_FAILURE", "UNEXPECTED_SUCCESS"}
OUTCOME_STATUSES = NON_PASSING | {SUCCESS, "SKIPPED", "EXPECTED_FAILURE", "NOT_REPORTED"}
ERROR_CLASS_CODES = frozenset({
    "TimeoutExpired", "IntegrityError", "PermissionError", "FileNotFoundError",
    "OSError", "CalledProcessError", "RuntimeError", "UNCLASSIFIED_EXCEPTION",
})

# 中文：每项都是可执行 unittest 标识，而不是文件级代理；选中用例覆盖能力名称所指的性质。
# English: Each item is an executable unittest identifier, rather than a file-level proxy. The selected cases exercise the property named by the capability.
CAPABILITY_TEST_MAP: dict[str, tuple[str, ...]] = {
    "reviewer_routing_v4": (
        "test_routing_v4_contract_statistics.V4ContractTests.test_catalog_has_eighteen_tuples_but_default_reviewer_pool_has_nine",
        "test_routing_v4_cards.CardTests.test_insufficient_samples_cannot_be_promoted_by_qualified_boolean",
        "test_routing_v4_evaluation.EvaluationTests.test_complete_experiment_requires_every_trial_and_keeps_quality_unqualified",
        "test_routing_v4_evaluation.EvaluationTests.test_multiple_scenarios_share_one_budget_and_keep_protocol_specific_traces",
    ),
    "delegation_budget_v4": (
        "test_routing_v4_process.ProcessTests.test_two_processes_cannot_consume_one_permit_twice",
        "test_routing_v4_process.ProcessTests.test_killed_writer_releases_os_lock_without_half_reservation",
        "test_routing_v4_hook.V4HookTests.test_registered_task_reserves_without_parent_environment_mutation",
        "test_routing_v4_hook.V4HookTests.test_corrupt_entry_fails_closed_and_other_sessions_remain_unbound",
        "test_routing_v4_hook.V4HookTests.test_desktop_uuid_stop_before_task_tree_receipt_links_once",
        "test_routing_v4_hook.V4HookTests.test_task_tree_identity_rejects_foreign_metadata_and_paths",
        "test_routing_v4_budget.BudgetTests.test_identity_link_cannot_assign_one_uuid_to_two_reserved_calls",
        "test_routing_v4_budget.BudgetTests.test_known_unsuccessful_stop_only_accepts_incomplete_without_refund",
        "test_routing_v4_budget.BudgetTests.test_reserved_repair_and_new_evidence_retry_resolve_blockers_in_same_root",
        "test_routing_v4_budget.AstraConcurrencyTests.test_second_astra_is_blocked_but_ordinary_parallelism_remains_available",
        "test_routing_v4_budget.AstraConcurrencyTests.test_atomic_reservation_rejects_a_loader_that_hides_active_astra",
    ),
    "review_state_v9_and_observation_v4": (
        "test_routing_v4_review.ReviewV4Tests.test_prepared_permit_prevents_closing_before_host_decision",
        "test_routing_v4_review.ReviewV4Tests.test_projection_interruption_recovers_committed_result_from_content_store",
        "test_routing_v4_calibration.CalibrationTests.test_forged_finalized_flag_or_changed_metrics_cannot_enter_report",
        "test_routing_v4_publication.PublicationTests.test_two_outputs_cannot_consume_one_approval_twice",
    ),
    "desktop_component_contract": (
        "test_desktop_host.DesktopHostTests.test_internal_prerelease_is_not_rejected_as_a_standalone_cli_version",
        "test_desktop_host.DesktopHostTests.test_changed_component_commands_fail_before_installation",
        "test_desktop_host.DesktopHostTests.test_corrupt_saved_binding_cannot_claim_current_desktop_compatibility",
    ),
    "session_end_recovery": (
        "test_session_end_recovery.SessionEndRecoveryTests.test_missing_worker_entry_is_rejected_before_process_creation",
        "test_package_manager_security.PackageManagerV64Tests.test_account_session_end_uses_managed_sibling_worker",
        "test_session_end_recovery.SessionEndRecoveryTests.test_preappend_permission_failure_uses_v7_and_pins_later_events",
        "test_session_end_recovery.SessionEndRecoveryTests.test_root_role_collision_rejects_equal_and_nested_configured_data_roots",
        "test_session_end_recovery.SessionEndRecoveryTests.test_recovery_receipt_tampering_never_creates_a_job",
        "test_session_end_recovery.SessionEndRecoveryTests.test_untrusted_keyless_diagnostic_is_never_promoted_to_recovery",
    ),
    "quick_status_readonly": (
        "test_quick_status.QuickStatusTests.test_quick_is_bounded_read_only_and_never_passes",
        "test_quick_status.QuickStatusTests.test_base_only_installation_is_not_reported_as_missing_enhancement",
        "test_quick_status.QuickStatusTests.test_changed_second_read_is_unknown_and_drops_recovery_action",
    ),
    "phase_routing_evidence": (
        "test_routing_phases.RoutingPhaseTests.test_four_current_skills_require_reason_not_silent_limit_increase",
        "test_routing_host_acceptance.HostRoutingAcceptanceTests.test_phase_report_is_bound_and_missing_exception_fails",
        "test_routing_host_acceptance.HostRoutingAcceptanceTests.test_unphased_exception_is_bound_to_report_bytes",
    ),
    "validation_evidence_integrity": (
        "test_validation_evidence.ValidationEvidenceTests.test_zero_discovery_and_missing_required_test_cannot_pass",
        "test_validation_evidence.ValidationEvidenceTests.test_all_skipped_required_tests_cannot_pass",
        "test_validation_evidence.ValidationEvidenceTests.test_error_and_subtest_failure_cannot_pass_and_do_not_expose_body",
        "test_validation_evidence.ValidationEvidenceTests.test_current_source_metadata_and_tampered_report_structure_fail_closed",
    ),
    "event_history_and_identity": (
        "test_event_scaling.EventScalingTests.test_append_revalidates_earliest_history_before_writing",
        "test_event_scaling.EventScalingTests.test_shared_identity_resolution_reads_repository_once",
    ),
    "multiprocess_fault_injection": (
        "test_v66_runtime_deepening.V66RuntimeDeepeningTests.test_true_spawn_multiprocess_append_and_rotate",
        "test_v66_runtime_deepening.V66RuntimeDeepeningTests.test_worker_recovers_each_claim_seal_and_ack_crash_boundary",
    ),
    "delayed_session_end_seal": (
        "test_v66_runtime_deepening.V66RuntimeDeepeningTests.test_session_end_enqueue_is_bounded_and_worker_seals_later",
        "test_v66_runtime_deepening.V66RuntimeDeepeningTests.test_session_end_hook_only_dispatches_and_worker_deduplicates_terminal_identity",
    ),
    "reviewer_result_v4": (
        "test_model_routing_calibration_gates.ModelRoutingCalibrationGateTests.test_result_template_v4_and_legacy_results_are_read_only",
    ),
    "minimum_profile_and_inline_delegate_gates": (
        "test_model_routing_calibration_gates.ModelRoutingCalibrationGateTests.test_approved_profile_projects_cost_without_runtime_identity",
        "test_model_routing_calibration_gates.ModelRoutingCalibrationGateTests.test_inline_decision_is_append_only_budget_free_and_requires_evidenced_redecision",
    ),
    "state_bound_plugin_runtime": (
        "test_package_manager_security.PackageManagerV64Tests.test_plugin_tools_fail_closed_when_state_or_bound_cache_is_unavailable",
    ),
    "delegation_budget_v2": (
        "test_v74_delegation_budget.DelegationBudgetV2Tests.test_parallel_reservation_is_atomic_and_idempotent",
        "test_v74_delegation_budget.DelegationBudgetV2Tests.test_chain_tamper_and_cross_project_identity_fail_closed",
    ),
    "reviewer_policy_v2": (
        "test_dispatch_policy.DispatchPolicyTests.test_registered_reviewers_accept_ten_exact_tuples_and_general_roles_keep_four",
        "test_dispatch_policy.DispatchPolicyTests.test_missing_stale_and_cross_context_evidence_add_no_points",
    ),
    "delegation_budget_v3": (
        "test_matrix_delegation_budget.MatrixDelegationBudgetTests.test_native_reservation_race_claims_one_permit_and_rejects_after_receipt",
        "test_matrix_delegation_budget.MatrixDelegationBudgetTests.test_pending_or_running_attempt_cannot_be_closed_as_pass",
    ),
    "reviewer_state_v8_result_v5": (
        "test_matrix_review_controller.MatrixReviewControllerTests.test_current_packet_generates_bound_v5_and_rejects_legacy_or_stale_input",
        "test_matrix_review_controller.MatrixReviewControllerTests.test_success_cannot_be_closed_without_real_review_results",
    ),
    "matrix_hook_protocol": (
        "test_matrix_delegation_hook.MatrixDelegationHookTests.test_v3_hook_consumes_scored_permit_once_and_projects_bound_identity",
        "test_matrix_delegation_hook.MatrixDelegationHookTests.test_unknown_tool_reply_and_generic_status_cannot_complete_or_refund",
    ),
    "calibration_sample_v3": (
        "test_matrix_delegation_calibration.MatrixCalibrationTests.test_matrix_sample_pins_policy_formula_and_declared_pairs",
        "test_matrix_delegation_calibration.MatrixCalibrationTests.test_pending_and_repeated_same_task_do_not_create_independent_evidence",
    ),
    "delegation_hook_gate": (
        "test_v74_delegation_hook.DelegationHookTests.test_pretool_consumes_explicit_permit_and_replay_is_idempotent",
        "test_v74_delegation_hook.DelegationHookTests.test_required_budget_without_ledger_fails_closed",
    ),
    "delegation_calibration_replay": (
        "test_v74_delegation_calibration.DelegationCalibrationTests.test_sample_must_match_completed_budget_reservation_and_metric_bounds",
        "test_v74_delegation_calibration.DelegationCalibrationTests.test_approved_profile_sample_never_changes_route_automatically",
    ),
    "event_archive_capacity_health": (
        "test_v66_runtime_deepening.V66RuntimeDeepeningTests.test_non_destructive_archive_capacity_and_privacy_health",
        "test_v66_runtime_deepening.V66RuntimeDeepeningTests.test_health_overview_isolates_one_malformed_segment_project",
    ),
}


class EvidenceError(ValueError):
    pass


def package_metadata(project_root: Path) -> dict[str, Any]:
    """中文：从权威源文件读取当前发行事实。

    English: Read current release facts from their authoritative source files.
    """
    root = Path(project_root).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
    plugin = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8-sig"))
    routing_cases = json.loads((root / "tests" / "skill-routing-cases.json").read_text(encoding="utf-8-sig"))
    compatibility = json.loads((root / "config" / "codex-compatibility-v1.json").read_text(encoding="utf-8-sig"))
    dispatch_policy = json.loads((root / "runtime" / "cp_runtime" / "data" / "dispatch-policy-v3.json").read_text(encoding="utf-8-sig"))
    if not all(isinstance(value, dict) for value in (manifest, plugin, routing_cases, compatibility, dispatch_policy)):
        raise EvidenceError("package metadata root invalid")
    package, version = manifest.get("package"), manifest.get("version")
    if not isinstance(package, str) or not package or not isinstance(version, str) or not version:
        raise EvidenceError("package metadata identity invalid")
    if plugin.get("name") != package or plugin.get("version") != version:
        raise EvidenceError("package/plugin metadata inconsistent")
    cases, versions, reviewers = routing_cases.get("cases"), compatibility.get("versions"), dispatch_policy.get("reviewer_roles")
    automatic = manifest.get("controlled_evolution_v75", {}).get("automatic_self_modification")
    if not isinstance(cases, list) or not isinstance(versions, list) or not isinstance(reviewers, list):
        raise EvidenceError("package metadata collection invalid")
    if type(automatic) is not bool:
        raise EvidenceError("automatic self-modification metadata invalid")
    skills = [path for path in (root / "skills").iterdir() if path.is_dir() and (path / "SKILL.md").is_file()]
    hooks = json.loads((root / "hooks" / "hooks.json").read_text(encoding="utf-8-sig"))
    if not isinstance(hooks, dict) or not isinstance(hooks.get("hooks"), dict):
        raise EvidenceError("plugin hook metadata invalid")
    return {
        "package": package,
        "version": version,
        "skill_count": len(skills),
        "reviewer_count": len(reviewers),
        "routing_case_count": len(cases),
        "compatibility_version_count": len(versions),
        "hooks": list(hooks["hooks"]),
        "task_outcome_event": manifest.get("controlled_evolution", {}).get("task_outcome_event_schema"),
        "automatic_self_modification": automatic,
        "python_minimum": manifest.get("python_compatibility", {}).get("minimum"),
    }


def _flatten(suite: unittest.TestSuite) -> Iterable[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


def _skip_code(reason: str) -> str:
    lowered = reason.lower()
    if any(token in lowered for token in ("windows", "linux", "macos", "darwin", "platform", "powershell")):
        return "PLATFORM_GATED"
    return "SKIPPED"


def _error_class_code(err: Any) -> str:
    """中文：仅返回固定诊断码，不保留异常控制的文本或类名。

    English: Return a fixed diagnostic code without retaining exception-controlled text or names.
    """
    error = err[1] if isinstance(err, tuple) and len(err) > 1 and isinstance(err[1], BaseException) else None
    if isinstance(error, subprocess.TimeoutExpired):
        return "TimeoutExpired"
    if isinstance(error, subprocess.CalledProcessError):
        return "CalledProcessError"
    if isinstance(error, PermissionError):
        return "PermissionError"
    if isinstance(error, FileNotFoundError):
        return "FileNotFoundError"
    if isinstance(error, OSError):
        return "OSError"
    error_type = type(error)
    if error_type.__module__ == "cp_runtime.integrity" and error_type.__qualname__ == "IntegrityError":
        return "IntegrityError"
    if isinstance(error, RuntimeError):
        return "RuntimeError"
    return "UNCLASSIFIED_EXCEPTION"


class _RecordingResult(unittest.TestResult):
    def __init__(self) -> None:
        super().__init__()
        self.outcomes: dict[str, list[dict[str, str]]] = defaultdict(list)
        self.subtest_count = 0

    def _record(self, test: unittest.TestCase, status: str, **extra: str) -> None:
        self.outcomes[test.id()].append({"status": status, **extra})

    def addSuccess(self, test: unittest.TestCase) -> None:  # noqa: N802
        super().addSuccess(test)
        self._record(test, SUCCESS)

    def addFailure(self, test: unittest.TestCase, err: Any) -> None:  # noqa: N802
        super().addFailure(test, err)
        self._record(test, "FAILURE")

    def addError(self, test: unittest.TestCase, err: Any) -> None:  # noqa: N802
        super().addError(test, err)
        self._record(test, "ERROR", error_class_code=_error_class_code(err))

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:  # noqa: N802
        super().addSkip(test, reason)
        self._record(test, "SKIPPED", skip_reason_code=_skip_code(reason))

    def addExpectedFailure(self, test: unittest.TestCase, err: Any) -> None:  # noqa: N802
        super().addExpectedFailure(test, err)
        self._record(test, "EXPECTED_FAILURE")

    def addUnexpectedSuccess(self, test: unittest.TestCase) -> None:  # noqa: N802
        super().addUnexpectedSuccess(test)
        self._record(test, "UNEXPECTED_SUCCESS")

    def addSubTest(self, test: unittest.TestCase, subtest: unittest.TestCase, err: Any) -> None:  # noqa: N802
        super().addSubTest(test, subtest, err)
        self.subtest_count += 1
        if err is not None:
            self._record(test, "SUBTEST_FAILURE")
            # 中文：沿用 unittest 对异常的区分及现有 ERROR 诊断合同。
            # English: Preserve unittest's exception distinction and the existing ERROR diagnostic contract.
            if not issubclass(err[0], test.failureException):
                self._record(test, "ERROR", error_class_code=_error_class_code(err))


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _with_digest(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["report_sha256"] = hashlib.sha256(_canonical_bytes(result)).hexdigest()
    return result


def collect_unittest(start_dir: Path, pattern: str = "test_*.py", suite_name: str | None = None) -> dict[str, Any]:
    """中文：发现并运行一套测试，只返回有界结果元数据。

    English: Discover and run one suite, returning only bounded outcome metadata.
    """
    start_dir = Path(start_dir).resolve()
    loader = unittest.TestLoader()
    suite = loader.discover(str(start_dir), pattern=pattern)
    discovered = [test.id() for test in _flatten(suite)]
    result = _RecordingResult()
    suite.run(result)
    cases = []
    for test_id in discovered:
        outcomes = result.outcomes.get(test_id, [])
        statuses = [item["status"] for item in outcomes]
        if not statuses:
            statuses = ["NOT_REPORTED"]
        entry: dict[str, Any] = {"id": test_id, "statuses": statuses}
        skip_codes = sorted({item["skip_reason_code"] for item in outcomes if "skip_reason_code" in item})
        if skip_codes:
            entry["skip_reason_codes"] = skip_codes
        error_class_codes = sorted({item["error_class_code"] for item in outcomes if "error_class_code" in item})
        if error_class_codes:
            entry["error_class_codes"] = error_class_codes
        cases.append(entry)
    counts = Counter(status for item in cases for status in item["statuses"])
    report = {
        "schema_version": SCHEMA_VERSION,
        "suite": suite_name or start_dir.name,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system(),
        "execution_status": "COMPLETED",
        "discovered_test_count": len(discovered),
        "executed_test_count": result.testsRun,
        "outcome_counts": dict(sorted(counts.items())),
        "subtest_count": result.subtest_count,
        "test_cases": cases,
    }
    return _with_digest(report)


def validate_evidence_report(value: Mapping[str, Any]) -> dict[str, Any]:
    report = dict(value)
    digest = report.pop("report_sha256", None)
    if report.get("schema_version") != SCHEMA_VERSION:
        raise EvidenceError("unsupported validation evidence schema")
    if not isinstance(digest, str) or digest != hashlib.sha256(_canonical_bytes(report)).hexdigest():
        raise EvidenceError("validation evidence digest mismatch")
    if report.get("execution_status") not in {"COMPLETED", "TIMEOUT", "INTERRUPTED"}:
        raise EvidenceError("validation evidence execution status invalid")
    if not isinstance(report.get("test_cases"), list):
        raise EvidenceError("validation evidence test cases invalid")
    if not isinstance(report.get("discovered_test_count"), int) or report["discovered_test_count"] < 0:
        raise EvidenceError("validation evidence discovery count invalid")
    if not isinstance(report.get("executed_test_count"), int) or report["executed_test_count"] < 0:
        raise EvidenceError("validation evidence execution count invalid")
    if report["discovered_test_count"] != len(report["test_cases"]):
        raise EvidenceError("validation evidence discovery count mismatch")
    if report["execution_status"] == "COMPLETED" and report["executed_test_count"] != report["discovered_test_count"]:
        raise EvidenceError("validation evidence execution count mismatch")
    if not isinstance(report.get("outcome_counts"), dict):
        raise EvidenceError("validation evidence outcome counts invalid")
    seen = set()
    actual_counts: Counter[str] = Counter()
    for item in report["test_cases"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise EvidenceError("validation evidence test identifier invalid")
        if item["id"] in seen:
            raise EvidenceError("validation evidence duplicate test identifier")
        seen.add(item["id"])
        if not isinstance(item.get("statuses"), list) or not item["statuses"]:
            raise EvidenceError("validation evidence test outcomes invalid")
        if any(status not in OUTCOME_STATUSES for status in item["statuses"]):
            raise EvidenceError("validation evidence outcome status invalid")
        error_class_codes = item.get("error_class_codes")
        if error_class_codes is not None:
            if ("ERROR" not in item["statuses"] or not isinstance(error_class_codes, list)
                    or not error_class_codes
                    or any(not isinstance(code, str) or code not in ERROR_CLASS_CODES for code in error_class_codes)
                    or error_class_codes != sorted(set(error_class_codes))):
                raise EvidenceError("validation evidence error class codes invalid")
        actual_counts.update(item["statuses"])
    if dict(sorted(actual_counts.items())) != report["outcome_counts"]:
        raise EvidenceError("validation evidence outcome counts mismatch")
    return dict(value)


def load_evidence_report(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("validation evidence unreadable") from exc
    if not isinstance(value, dict):
        raise EvidenceError("validation evidence must be an object")
    return validate_evidence_report(value)


def timeout_report(suite_name: str, timeout_seconds: int) -> dict[str, Any]:
    return _with_digest({
        "schema_version": SCHEMA_VERSION,
        "suite": suite_name,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system(),
        "execution_status": "TIMEOUT",
        "timeout_seconds": timeout_seconds,
        "discovered_test_count": 0,
        "executed_test_count": 0,
        "outcome_counts": {},
        "subtest_count": 0,
        "test_cases": [],
    })


def suite_passed(report: Mapping[str, Any]) -> bool:
    checked = validate_evidence_report(report)
    if checked["execution_status"] != "COMPLETED" or checked["discovered_test_count"] <= 0:
        return False
    return not any(
        status in NON_PASSING or status == "NOT_REPORTED"
        for item in checked["test_cases"]
        for status in item["statuses"]
    )


def evaluate_capabilities(
    reports: Sequence[Mapping[str, Any]],
    capability_map: Mapping[str, Sequence[str]] = CAPABILITY_TEST_MAP,
) -> dict[str, dict[str, Any]]:
    """中文：将必需测试结果投影为失败关闭的能力结论。

    English: Project required test outcomes into fail-closed capability conclusions.
    """
    observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incomplete_suites = []
    for raw_report in reports:
        report = validate_evidence_report(raw_report)
        if report["execution_status"] != "COMPLETED":
            incomplete_suites.append(str(report["suite"]))
        for case in report["test_cases"]:
            observations[case["id"]].append(case)
    capabilities: dict[str, dict[str, Any]] = {}
    for capability, required in capability_map.items():
        if not required:
            capabilities[capability] = {
                "required_test_ids": [], "observed_test_ids": [], "status": "NOT_VERIFIED",
                "reason_codes": ["REQUIRED_TEST_MAPPING_EMPTY"],
            }
            continue
        missing = [test_id for test_id in required if test_id not in observations]
        selected = [case for test_id in required for case in observations.get(test_id, [])]
        statuses = [status for case in selected for status in case["statuses"]]
        platform_skips = [
            case["id"] for case in selected
            if case["statuses"] == ["SKIPPED"] and "PLATFORM_GATED" in case.get("skip_reason_codes", [])
        ]
        row: dict[str, Any] = {
            "required_test_ids": list(required),
            "observed_test_ids": sorted({case["id"] for case in selected}),
            "status": SUCCESS,
            "reason_codes": [],
        }
        if incomplete_suites:
            row["status"] = "NOT_VERIFIED"
            row["reason_codes"] = ["SUITE_NOT_COMPLETED"]
            row["incomplete_suites"] = sorted(set(incomplete_suites))
        elif missing:
            row["status"] = "NOT_VERIFIED"
            row["reason_codes"] = ["REQUIRED_TEST_MISSING"]
            row["missing_test_ids"] = missing
        elif statuses and all(status == "SKIPPED" for status in statuses):
            row["status"] = "NOT_APPLICABLE" if len(platform_skips) == len(selected) else "NOT_VERIFIED"
            row["reason_codes"] = ["PLATFORM_EXCEPTION" if platform_skips else "ALL_REQUIRED_TESTS_SKIPPED"]
            if platform_skips:
                row["platform_exception_test_ids"] = platform_skips
        elif any(status in NON_PASSING for status in statuses):
            row["status"] = "FAIL"
            row["reason_codes"] = sorted({status for status in statuses if status in NON_PASSING})
        elif any(status != SUCCESS for status in statuses):
            row["status"] = "NOT_VERIFIED"
            row["reason_codes"] = sorted({status for status in statuses if status != SUCCESS})
        capabilities[capability] = row
    return capabilities


def mapping_test_ids_are_loadable(project_root: Path, capability_map: Mapping[str, Sequence[str]] = CAPABILITY_TEST_MAP) -> list[str]:
    """中文：返回 unittest 无法从源模块加载的映射标识。

    English: Return mapped IDs that unittest cannot load from their source modules.
    """
    tests_dir = str(Path(project_root).resolve() / "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    loader = unittest.TestLoader()
    missing = []
    for test_id in sorted({item for values in capability_map.values() for item in values}):
        cases = list(_flatten(loader.loadTestsFromName(test_id)))
        if len(cases) != 1 or cases[0].id() != test_id:
            missing.append(test_id)
    return missing


def _collect_command(args: argparse.Namespace) -> int:
    report = collect_unittest(Path(args.start_dir), args.pattern, args.suite)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect redacted unittest validation evidence")
    subparsers = parser.add_subparsers(dest="command", required=True)
    collect = subparsers.add_parser("collect")
    collect.add_argument("--start-dir", required=True)
    collect.add_argument("--pattern", default="test_*.py")
    collect.add_argument("--suite")
    collect.add_argument("--output", required=True)
    collect.set_defaults(func=_collect_command)
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
