"""中文：只读对照计算，以独立任务和经登记的协调者证据解释质量。
English: Read-only policy comparison using independent tasks and registered coordinator evidence.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from . import g6_budget_v1 as budget, g6_catalog as catalogs
from .capability_store import bounded_read, safe_path
from .common import parse_iso, require_external_state, resolve_codex_home, utc_now
from .capability_gate import _read, _write, worktree_key
from .event_v2 import OwnerTokenLock
from .evidence import load_evidence
from .g6_flexible_policy import decide, profile_spec
from .g6_route_settings import _binding, _selection, registered_ledgers
from .routing_contract import fail, ref, role_for

MAX_ROOTS = 32
MAX_WORK_PER_ROOT = 8
MAX_METER = 1_000_000
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MIN_TIMING_ROOTS = 3
METRICS = {
    "reviewer": {"findings", "accepted", "false_positive"},
    "worker": {"accepted", "rework"},
    "explorer": {"hit"},
}


def _adjudications(files, profile, repo, project):
    """中文：只消费项目登记的父协调者质量证据。 English: A child outcome alone cannot describe business quality."""
    import json
    from .project import validate_binding

    if not files:
        return {}
    if not profile or len(files) > 128:
        fail("STUDY_BOUND_PROJECT_PROFILE_REQUIRED")
    validate_binding(profile, repo, project["project_id"])
    registered = {}
    for line in bounded_read(safe_path(profile.parent / "evidence-ledger.jsonl"), 1_048_576).splitlines():
        item = json.loads(line)
        if item.get("project_id") == project["project_id"]:
            registered[(item["evidence_id"], str(Path(item["path"]).resolve()))] = item
    results = {}
    for path in files:
        path = safe_path(path)
        require_external_state(path, repo)
        record = load_evidence(path)
        witness = registered.get((record["evidence_id"], str(path.resolve())))
        baseline = record["baseline"]
        if (
            not witness
            or witness["baseline_sha256"] != baseline["sha256"]
            or witness["task_id"] != record["task_id"]
            or witness["recorded_at"] != record["recorded_at"]
            or record["project_id"] != project["project_id"]
            or Path(baseline["repo_path"]).resolve() != repo
            or record.get("source") != "parent-coordinator"
            or record.get("subject") != "routing-quality/1"
            or record.get("kind") != "validation"
            or record["status"] != "valid"
        ):
            fail("STUDY_EVIDENCE_BINDING")
        refs = {}
        for token in record["scope_refs"]:
            key, sep, value = token.partition("=")
            if not sep or key in refs:
                fail("STUDY_EVIDENCE_FIELDS")
            refs[key] = value
        indexed = (record["task_id"], refs.get("permit"), refs.get("terminal"))
        if indexed in results:
            fail("STUDY_EVIDENCE_DUPLICATE")
        results[indexed] = (refs, baseline["sha256"])
    return results


def compare(repo, target_policy, ledgers=None, *, evidence=None, profile=None, save_timing=False):
    _, root = _selection(Path(repo))
    project = _binding(root)
    digest = catalogs.digest_for(target_policy)
    paths = set(safe_path(p) for p in ledgers) if ledgers else set(registered_ledgers(root, project))
    if len(paths) > MAX_ROOTS or sum(p.stat().st_size for p in paths) > MAX_TOTAL_BYTES:
        fail("STUDY_NARROW_LEDGER_WINDOW")
    judgments = _adjudications(evidence or [], profile, root, project)
    roots_seen = set()
    rows = []
    omitted = 0
    cohorts = defaultdict(list)
    for path in sorted(paths):
        require_external_state(path, root)
        with OwnerTokenLock(path, timeout=2):
            events = budget._read_events(path)
            state = budget.replay(events)
        original = state["root"]
        if original["identity"] != project or Path(original["repo_path"]).resolve() != root:
            fail("STUDY_FOREIGN_ROOT")
        token = (original["host_session_ref"], original["task_id"])
        if token in roots_seen:
            fail("STUDY_DUPLICATE_ROOT")
        roots_seen.add(token)
        terminal_at = {
            e["data"]["permit_id"]: e["recorded_at"] for e in events if e["event_type"] == "TERMINAL"
        }
        selected = {}
        for i, e in enumerate(events):
            if e["event_type"] == "PREPARED" and e["data"]["permit_id"] in state["reservations"]:
                selected.setdefault(e["data"]["work_item_id"], (i, e["data"]))
        omitted += max(0, len(selected) - MAX_WORK_PER_ROOT)
        for i, permit in list(selected.values())[:MAX_WORK_PER_ROOT]:
            pid = permit["permit_id"]
            role = role_for(permit["agent_type"])
            facts = permit["facts"]
            old_state = budget.replay(events[:i])
            fixed = budget.snapshot(
                old_state,
                work_item_id=permit["work_item_id"],
                depth=permit["depth"],
                funding_id=permit.get("funding_id", "base"),
            )
            target_catalog = catalogs.for_digest(digest)
            if fixed["schema_version"] == "g6-budget-snapshot/3" and not target_catalog:
                fixed = {k: v for k, v in fixed.items() if k != "active_groups"}
                fixed["schema_version"] = "g6-budget-snapshot/2"
            if target_catalog and "active_groups" in fixed:
                fixed["active_groups"] = {
                    group: fixed["active_groups"].get(group, 0) for group in target_catalog.limits
                }
            original_cap = permit["capability"]
            known = original_cap["available_profiles"]

            def remap(old):
                from .g6_flexible_policy import profiles_for

                if old not in profiles_for(original["policy_digest"]):
                    return None
                previous = profile_spec(old, original["policy_digest"])
                if target_catalog:
                    return target_catalog.lookup(previous["model"], previous["effort"])
                from .g6_flexible_policy import PROFILES

                return next(
                    (
                        p
                        for p in PROFILES
                        if profile_spec(p)["model"] == previous["model"]
                        and profile_spec(p)["effort"] == previous["effort"]
                    ),
                    None,
                )

            available = None if known is None else sorted({mapped for p in known if (mapped := remap(p))})
            explicit = permit["explicit_user_profile"]
            forced = next(
                (s for s in original["required_slots"] if s["work_item_id"] == permit["work_item_id"]), None
            )
            work = state.get("review_work", {}).get(permit["work_item_id"])
            if forced or work:
                constrained = (
                    [work["profile_id"]]
                    if work
                    else forced["allowed_profiles"] or [forced["baseline_profile"]]
                )
                permitted = {mapped for p in constrained if (mapped := remap(p))}
                available = sorted(permitted if available is None else permitted.intersection(available))
            candidate = None
            if not explicit or remap(explicit):
                advisory = permit.get("adjustment")
                if advisory:
                    mapped = remap(advisory["requested_profile"])
                    advisory = {**advisory, "requested_profile": mapped} if mapped else None
                # 中文：耗时样本按策略、角色与任务类别隔离。
                # English: Timing cohorts belong to an exact policy, role and task kind.
                if digest == original["policy_digest"]:
                    shadow_capability = {**original_cap, "available_profiles": available}
                else:
                    shadow_capability = {
                        "schema_version": "g6-desktop-capability/1",
                        "available_profiles": available,
                        "source_ref": original_cap["source_ref"],
                    }
                shadow = decide(
                    facts=facts,
                    budget=fixed,
                    capability=shadow_capability,
                    gates=permit["gates"],
                    agent_type=permit["agent_type"],
                    task_name=permit["task_name"],
                    message="offline projection",
                    decision_time=permit["decision_time"],
                    explicit_user_profile=remap(explicit) if explicit else None,
                    adjustment=advisory,
                    policy_digest=digest,
                )
                candidate = shadow["approved_profile"]
            terminal = state["terminals"].get(pid)
            measured = None
            if pid in terminal_at:
                elapsed = (
                    parse_iso(terminal_at[pid]) - parse_iso(state["reservations"][pid]["reserved_at"])
                ).total_seconds()
                if elapsed >= 0:
                    measured = round(elapsed * 1000)
            grade = None
            if terminal:
                adjudicated = judgments.pop((original["task_id"], pid, ref(terminal)), None)
                if adjudicated:
                    refs, baseline = adjudicated
                    if (
                        refs.get("policy") != original["policy_digest"]
                        or refs.get("repository") != project["repo_fingerprint"]
                        or refs.get("root") != ref(original)
                        or not facts.get("baseline_sha256")
                        or refs.get("initial_baseline") != facts["baseline_sha256"]
                        or not baseline
                    ):
                        fail("STUDY_EVIDENCE_SCOPE")
                    metric_names = METRICS[role]
                    if set(refs) != {
                        "permit",
                        "terminal",
                        "policy",
                        "root",
                        "repository",
                        "initial_baseline",
                        *metric_names,
                    }:
                        fail("STUDY_EVIDENCE_METRICS")
                    grade = {k: int(refs[k]) for k in metric_names}
                    if any(not 0 <= v <= MAX_METER for v in grade.values()) or (
                        role == "reviewer"
                        and grade["accepted"] + grade["false_positive"] > grade["findings"]
                        or role == "worker"
                        and grade["accepted"] > 1
                        or role == "explorer"
                        and grade["hit"] > 1
                    ):
                        fail("STUDY_EVIDENCE_METRICS")
                    cohort = (role, facts["task_kind"], original["policy_digest"], permit["approved_profile"])
                    cohorts[cohort].append((ref(original), grade, measured))
            rows.append(
                {
                    "root_ref": ref(original),
                    "role": role,
                    "kind": facts["task_kind"],
                    "permit_id": pid,
                    "terminal_ref": ref(terminal) if terminal else None,
                    "original_policy_digest": original["policy_digest"],
                    "initial_baseline": facts.get("baseline_sha256"),
                    "approved_profile": permit["approved_profile"],
                    "candidate": candidate,
                    "original_planning_units": permit["planning_units"],
                    "candidate_planning_units": profile_spec(candidate, digest)["planning_units"]
                    if candidate
                    else None,
                    "reservation_to_terminal_ms": measured,
                    "adjudicated_metrics": grade,
                }
            )
    if judgments:
        fail("STUDY_EVIDENCE_NOT_BOUND_TO_ELIGIBLE_WORK")
    groups = []
    for (role, kind, policy, profile_id), samples in sorted(cohorts.items()):
        # 中文：按独立根等权聚合，重试和大任务不会取得额外权重。
        # English: Per-root means keep retries and large roots from overweighting the comparison.
        by_root = defaultdict(list)
        for key, grade, elapsed in samples:
            by_root[key].append((grade, elapsed))
        metrics = {
            k: sum(sum(g[k] for g, _ in items) / len(items) for items in by_root.values()) / len(by_root)
            for k in METRICS[role]
        }
        times = [
            median(t for _, t in items if t is not None)
            for items in by_root.values()
            if any(t is not None for _, t in items)
        ]
        groups.append(
            {
                "role": role,
                "kind": kind,
                "policy_digest": policy,
                "approved_profile": profile_id,
                "independent_roots": len(by_root),
                "timed_roots": len(times),
                "mean_per_root": metrics,
                "median_root_duration_ms": median(times) if times else None,
            }
        )
    report = {
        "scope": "project-and-repository",
        "candidate_policy": target_policy,
        "candidate_digest": digest,
        "independent_roots": len(roots_seen),
        "compared_work": len(rows),
        "omitted_work": omitted,
        "rows": rows,
        "graded_cohorts": groups,
        "quality_status": "HUMAN_COMPARISON_ONLY" if groups else "INSUFFICIENT_FINALIZED_SAMPLES",
        "actual_credits": None,
        "strategy_change": "NONE",
        "execution_authorization": "NONE",
    }
    if save_timing:
        eligible = [g for g in groups if g["timed_roots"] >= MIN_TIMING_ROOTS and g["kind"] != "unknown"]
        path = _timing_path(root)
        with OwnerTokenLock(path, timeout=2):
            _write(
                path,
                {
                    "schema_version": "desktop-comparable-timing/1",
                    "project": project,
                    "worktree": worktree_key(root),
                    "collected_at": utc_now(),
                    "study_ref": ref(report),
                    "groups": eligible,
                },
                262144,
            )
        report["stored_timing_cohorts"] = len(eligible)
    return report


def _timing_path(root):
    return safe_path(resolve_codex_home() / "cp-assistant/routing-timing" / (worktree_key(root) + ".json"))


def comparable_timing(root, project, digest, role, kind):
    if not (resolve_codex_home() / "cp-assistant/routing-timing").exists():
        return {}
    path = _timing_path(root)
    if not path.is_file():
        return {}
    record = _read(path, 262144)
    if (
        record["schema_version"] != "desktop-comparable-timing/1"
        or record["project"] != project
        or record["worktree"] != worktree_key(root)
        or not timedelta(0)
        <= datetime.now(timezone.utc) - parse_iso(record["collected_at"])
        < timedelta(days=1)
    ):
        return {}
    return {
        r["approved_profile"]: round(r["median_root_duration_ms"])
        for r in record["groups"]
        if r["policy_digest"] == digest
        and r["role"] == role
        and r["kind"] == kind
        and r["timed_roots"] >= MIN_TIMING_ROOTS
        and 0 <= r["median_root_duration_ms"] <= 86_400_000
    }
