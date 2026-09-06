"""中文：可检验的优化假设和确定性指标读取。

English: Testable optimization hypotheses and deterministic metric extraction.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from .artifacts import ArtifactError, HASH
from .contracts import PatternSignal, SelfObservationSnapshot, SignalType, to_primitive

METRICS = {"failure_rate", "negative_outcome_rate", "routing_deviation_rate", "repair_round_average",
           "reviewer_benefit_per_unit", "dispatch_value_per_unit"}


def metric_value(metrics: Mapping[str, Any], metric: str, target: str) -> float | None:
    if metric == "failure_rate":
        count = metrics.get("task_count", 0)
        value = metrics.get("failure_patterns", {}).get(target, 0) / count if count else None
    elif metric == "reviewer_benefit_per_unit":
        value = metrics.get("reviewer_stats", {}).get(target, {}).get("benefit_proxy")
    elif metric == "dispatch_value_per_unit":
        value = next((item.get("higher_value_per_unit") for item in metrics.get("dispatch_profile_value_comparisons", [])
                      if item.get("eligible") and target == "dispatch-profile:" + item["lower_profile"] + "->" + item["higher_profile"] + ":" + item.get("scenario_key", "")), None)
    else:
        value = metrics.get(metric)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ArtifactError("HYPOTHESIS_METRIC_INVALID")
    return float(value)


def create_hypothesis(snapshot: SelfObservationSnapshot, signal: PatternSignal) -> dict[str, Any] | None:
    fingerprint = snapshot.metrics.get("repo_fingerprint")
    if not fingerprint:
        return None
    metric = {
        SignalType.REPEATED_FAILURE: "failure_rate",
        SignalType.NEGATIVE_OUTCOME: "negative_outcome_rate",
        SignalType.ROUTING_DEVIATION: "routing_deviation_rate",
        SignalType.EXCESSIVE_REPAIR: "repair_round_average",
        SignalType.LOW_REVIEWER_YIELD: "reviewer_benefit_per_unit",
        SignalType.DISPATCH_PROFILE_VALUE_REGRESSION: "dispatch_value_per_unit",
    }.get(signal.signal_type)
    if metric is None:
        return None
    target = signal.target.removeprefix("reviewer:") if metric == "reviewer_benefit_per_unit" else signal.target
    baseline = metric_value(snapshot.metrics, metric, target)
    direction = "increase" if metric.endswith("per_unit") else "decrease"
    return {
        "schema_version": "optimization-hypothesis/1",
        "scope": {"project_id": snapshot.project_id, "repo_fingerprint": fingerprint,
                  "metric_target": target, "signal_type": signal.signal_type.value},
        "baseline_snapshot_id": snapshot.snapshot_id, "baseline_snapshot_hash": snapshot.content_hash,
        "metric": metric, "baseline": baseline, "direction": direction,
        "target": None if baseline is None else round(baseline * (1.1 if direction == "increase" else 0.9), 8),
        "minimum_independent_tasks": 5, "minimum_window_days": 7,
        "guardrails": {"maximum_negative_outcome_rate": snapshot.metrics.get("negative_outcome_rate", 0),
                       "minimum_known_terminal_outcome_coverage": 0.8},
        "stop_conditions": ["IDENTITY_OR_BASELINE_MISMATCH", "QUALITY_REGRESSION", "EVIDENCE_INVALID"],
        "interpretation": "OBSERVATIONAL_NOT_CAUSAL",
    }


def validate_hypothesis(raw: Mapping[str, Any], project_id: str) -> None:
    expected = {"schema_version", "scope", "baseline_snapshot_id", "baseline_snapshot_hash", "metric", "baseline",
                "direction", "target", "minimum_independent_tasks", "minimum_window_days", "guardrails", "stop_conditions", "interpretation"}
    if set(raw) != expected or raw["schema_version"] != "optimization-hypothesis/1":
        raise ArtifactError("HYPOTHESIS_SCHEMA_INVALID")
    scope = raw["scope"]
    if set(scope) != {"project_id", "repo_fingerprint", "metric_target", "signal_type"} or scope["project_id"] != project_id:
        raise ArtifactError("HYPOTHESIS_SCOPE_MISMATCH")
    if not str(scope["repo_fingerprint"]).startswith("sha256:") or not HASH.fullmatch(str(scope["repo_fingerprint"])[7:]):
        raise ArtifactError("HYPOTHESIS_REPO_INVALID")
    if not HASH.fullmatch(raw["baseline_snapshot_hash"]) or raw["metric"] not in METRICS or raw["direction"] not in {"increase", "decrease"}:
        raise ArtifactError("HYPOTHESIS_METRIC_INVALID")
    for key in ("minimum_independent_tasks", "minimum_window_days"):
        if type(raw[key]) is not int or not 1 <= raw[key] <= 10000:
            raise ArtifactError("HYPOTHESIS_SAMPLE_LIMIT_INVALID")
    for key in ("baseline", "target"):
        if raw[key] is not None and (isinstance(raw[key], bool) or not isinstance(raw[key], (int, float)) or not math.isfinite(raw[key]) or raw[key] < 0):
            raise ArtifactError("HYPOTHESIS_TARGET_INVALID")
    if (raw["baseline"] is None) != (raw["target"] is None):
        raise ArtifactError("HYPOTHESIS_TARGET_INVALID")
    if raw["target"] is not None:
        if (raw["direction"] == "increase" and raw["target"] < raw["baseline"]) or (raw["direction"] == "decrease" and raw["target"] > raw["baseline"]):
            raise ArtifactError("HYPOTHESIS_DIRECTION_INVALID")
    guardrails = raw["guardrails"]
    if set(guardrails) != {"maximum_negative_outcome_rate", "minimum_known_terminal_outcome_coverage"}:
        raise ArtifactError("HYPOTHESIS_GUARDRAILS_INVALID")
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1 for value in guardrails.values()):
        raise ArtifactError("HYPOTHESIS_GUARDRAILS_INVALID")
    if list(raw["stop_conditions"]) != ["IDENTITY_OR_BASELINE_MISMATCH", "QUALITY_REGRESSION", "EVIDENCE_INVALID"]:
        raise ArtifactError("HYPOTHESIS_STOP_CONDITIONS_INVALID")
    if raw["interpretation"] != "OBSERVATIONAL_NOT_CAUSAL":
        raise ArtifactError("HYPOTHESIS_INTERPRETATION_INVALID")
