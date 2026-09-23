"""中文：V4 合成数据与宿主回执夹具，不构成实机验收。

English: Synthetic V4 datasets and host-receipt fixtures, never live acceptance.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from cp_runtime.routing_contract import ref
from cp_runtime.routing_cards import build_bundle, protocol_reference

_CLOCK = datetime.now(timezone.utc)
NOW = (_CLOCK - timedelta(hours=1)).isoformat()
EXPIRES = (_CLOCK + timedelta(days=1)).isoformat()
IDENTITY = {"project_id": "synthetic-v4", "repo_fingerprint": ref("synthetic-repository")}
SCENARIO = {
    "role": "cp_review_data_contract", "phase": "post", "semantic": 1, "reasoning": 1,
    "risk": 1, "tags": ["bounded_logic"], "context_bucket": "small",
    "tools_profile": "readonly", "speed_mode": "standard", "prompt_sha256": "a" * 64,
}


def experiment(n=400, profiles=("g6-sol-medium", "g6-sol-high"), *, origin="synthetic"):
    rows = []
    for profile in profiles:
        for i in range(n):
            key = f"{profile}-{i}"
            row = {
                "sample_id": key, "cluster_id": f"cluster-{i}", "case_id": f"case-{i}",
                "repetition": 1, "profile_id": profile, "passed": True, "clean": i != n - 1,
                "critical": i == n - 1, "false_block": False, "critical_failure": False,
                "boundary_failure": False, "task_ref": ref("task-" + key),
                "call_ref": ref("call-" + key), "receipt_ref": ref("receipt-" + key),
                "response_ref": ref("response-" + key), "gold_ref": ref(f"gold-{i}"),
                "prompt_ref": ref(f"synthetic-prompt-{i}"),
                "cost_units": 10, "latency_ms": 100,
            }
            row["case_ref"] = case_reference(row)
            rows.append(row)
    pairs = [{"anchor": profiles[0], "challenger": item} for item in profiles[1:]]
    result = {
        "schema_version": "routing-experiment/1", "experiment_id": "synthetic-experiment",
        "identity": copy.deepcopy(IDENTITY), "origin": origin,
        "issuer": {"task_id": "issuer-task", "baseline_sha256": "b" * 64},
        "scenario": copy.deepcopy(SCENARIO), "rubric_ref": ref("synthetic-rubric"),
        "minimum_pass_bp": 9000, "baseline_profile": profiles[0],
        "comparisons": pairs, "family_intervals": 4 * len(pairs),
        "case_plan": sorted({row["case_ref"] for row in rows}), "repetitions": 1, "protocol_ref": "",
        "samples": rows, "finalizer": "parent:issuer-task",
    }
    result["protocol_ref"] = protocol_reference(result)
    return result


def costs(exp):
    return [
        {"profile_id": profile, "scenario_ref": ref(exp["scenario"]),
         "cost_basis": "synthetic-proxy", "plan_cost": 10 + i * 6, "reserve_units": 10 + i * 6,
         "latency_ms": 100 + i * 10, "measurement": "declared_proxy", "source_ref": ref("synthetic-costs")}
        for i, profile in enumerate(sorted({row["profile_id"] for row in exp["samples"]}))
    ]


def case_reference(row):
    return ref({key: row[key] for key in ("case_id", "cluster_id", "prompt_ref", "gold_ref", "clean", "critical")})


def refreeze_protocol(exp):
    for row in exp["samples"]:
        row["case_ref"] = case_reference(row)
    exp["case_plan"] = sorted({row["case_ref"] for row in exp["samples"]})
    exp["protocol_ref"] = protocol_reference(exp)


def bundle(exp):
    return build_bundle(exp, costs(exp), bundle_id="synthetic-bundle", created_at=NOW, expires_at=EXPIRES)


def trace_loader(exp):
    traces = {
        row["receipt_ref"]: {
            "schema_version": "desktop-evaluation-trace/1", "host_surface": "codex-desktop",
            "identity": copy.deepcopy(exp["identity"]), "source": "verified-host-receipt",
            "outcome": "COMPLETED",
            "scenario_ref": ref(exp["scenario"]),
            "protocol_ref": exp["protocol_ref"],
            **{key: row[key] for key in
               ("task_ref", "call_ref", "receipt_ref", "response_ref", "profile_id", "prompt_ref", "case_ref")},
        }
        for row in exp["samples"]
    }
    return lambda receipt: copy.deepcopy(traces[receipt])


def desktop_capability(contract):
    value = {
        "codex_version": "0.155.0-alpha.16", "executable_path": "/synthetic/desktop-component",
        "executable_sha256": "a" * 64, "registry_schema": "desktop-host-contract/1",
        "registry_digest": ref(contract)[7:], "plugin_list_contract": True,
        **{key: contract["management"][key] for key in ("marketplace_profile", "plugin_cli_profile", "plugin_json_profile")},
        **{key: contract["runtime"][key] for key in ("hook_profile", "apply_patch_result_profile")},
        "commands": {key: {"ok": True, "sha256": digest} for key, digest in contract["management"]["commands"].items()},
    }
    value["capability_digest"] = ref(value)[7:]
    return {**value, "ok": True}
