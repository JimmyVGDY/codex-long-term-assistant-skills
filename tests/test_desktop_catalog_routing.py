"""中文：验收新目录、真实入口绑定和迟到回执的兼容行为。
English: Verify catalog selection, native bindings, and late settlement across a policy rollback.
"""

import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from cp_runtime import g6_budget_v1 as budget, g6_catalog as catalogs, g6_capability_source as sources
from cp_runtime import g6_hook_v1 as hook, g6_route_settings as routing, g6_user_intent as intent
from cp_runtime import g6_routing_study as study
from cp_runtime.g6_flexible_policy import decide
from cp_runtime.routing_contract import RoutingError, ref
from tests.test_g6_flexible_policy import inputs


class DesktopCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.repo = Path(__file__).resolve().parents[1]
        self.env = patch.dict(os.environ, {"CODEX_HOME": str(self.home)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.identity = routing._binding(self.repo)
        self.digest = catalogs.digest_for("desktop-catalog-v2")
        self.catalog = catalogs.for_digest(self.digest)

    def switch(self, policy, rev):
        preview = routing.selection(self.repo, "preview", policy, rev)
        with patch(
            "cp_runtime.g6_runtime_support.installed_task_scope_support", return_value={"supported": True}
        ):
            outcome = routing.selection(self.repo, "apply", policy, rev, preview["request_ref"])
            replay = routing.selection(self.repo, "apply", policy, rev, preview["request_ref"])
        self.assertTrue(replay["idempotent"])
        return outcome

    def root(self, path, task):
        with patch(
            "cp_runtime.g6_runtime_support.installed_task_scope_support", return_value={"supported": True}
        ):
            return budget.initialize(
                path,
                identity_value=self.identity,
                host_session_id=task,
                repo_path=self.repo,
                task_id=task,
                authorization_ref=ref(["test", task]),
            )

    def test_catalog_rollback_survives_full_revision_page(self):
        with patch.object(routing, "MAX_CHANGES", 2):
            first = routing.selection(self.repo, "preview", "desktop-catalog-v2", 0)["request_ref"]
            self.switch("desktop-catalog-v2", 0)
            self.switch(catalogs.LEGACY_ID, 1)
            self.switch("desktop-catalog-v2", 2)
            self.assertTrue(
                routing.selection(self.repo, "apply", "desktop-catalog-v2", 0, first)["idempotent"]
            )
            self.switch(catalogs.LEGACY_ID, 3)
            self.assertEqual(routing.selection(self.repo, "show")["revision"], 4)

    def start(self, path, task, preferred, kind=None):
        args = inputs()
        facts = args["facts"]
        facts.update(identity=self.identity, task_id=task)
        if kind:
            facts.update(
                task_kind=kind, task_kind_source="user_direct", source_refs=[ref(["category", task, kind])]
            )
        current = budget.read_budget(path)["root"]["policy_digest"]
        if current != catalogs.LEGACY:
            available = sources.project(
                self.catalog, {("gpt-6.2-sol", "medium")}, True, {("gpt-6.2-sol", "medium")}, set()
            )
            available["source_ref"] = ref("bound test capability")
        else:
            available = args["capability"]
        now = datetime.now(timezone.utc).isoformat()
        item = budget.prepare(
            path,
            facts=facts,
            capability=available,
            gates=[],
            agent_type="worker",
            task_name=task,
            message="Read a bounded fixture",
            decision_time=now,
            explicit_user_profile=preferred,
        )
        self.assertIsNotNone(item["permit_id"], item["decision"])
        budget.approve_and_reserve(
            path,
            permit_id=item["permit_id"],
            host_call_id=task,
            session_id=task,
            cwd=self.repo,
            args=item["decision"]["exact_tool_parameters"],
            now=now,
        )
        budget.record_receipt(
            path, host_call_id=task, disposition="created", agent_path="/root/" + task, proof_ref=ref(task)
        )
        return item

    def test_offline_comparison_preserves_recorded_latency_for_the_same_policy(self):
        self.switch("desktop-catalog-v2", 0)
        path = self.home / "timed.jsonl"
        self.root(path, "timed")
        pairs = {("gpt-6.1-sol", "medium"), ("gpt-6.2-sol", "medium")}
        capability = sources.project(self.catalog, pairs, True, pairs, set(),
                                     latency={"g61-sol-medium": 10, "g62-sol-medium": 100})
        capability["source_ref"] = ref("bound timing")
        facts = dict(inputs()["facts"], identity=self.identity, task_id="timed")
        now = datetime.now(timezone.utc).isoformat()
        permit = budget.prepare(path, facts=facts, capability=capability, gates=[], agent_type="worker",
                                task_name="compare", message="Inspect fixture", decision_time=now)
        budget.approve_and_reserve(path, permit_id=permit["permit_id"], session_id="timed", cwd=self.repo,
                                   host_call_id="only", args=permit["decision"]["exact_tool_parameters"], now=now)
        row = study.compare(self.repo, "desktop-catalog-v2", [path])["rows"][0]
        self.assertEqual(row["approved_profile"], "g61-sol-medium")
        self.assertEqual(row["candidate"], row["approved_profile"])
        self.assertIsNone(study.compare(self.repo, catalogs.LEGACY_ID, [path])["rows"][0]["candidate"])

    def test_mixed_lists_rank_by_role_and_explicit_priority(self):
        args = inputs()
        args["capability"]["available_profiles"] = ["new-unknown", "g6-luna-high", "g6-astra-low"]
        with self.assertRaisesRegex(RoutingError, "G6_CAPABILITY_LIST"):
            decide(**args)
        args["agent_type"] = "explorer"
        selected = decide(**args, policy_digest=self.digest)
        self.assertEqual(selected["approved_profile"], "g6-luna-high")
        args["agent_type"] = "cp_review_data_contract"
        self.assertEqual(decide(**args, policy_digest=self.digest)["approved_profile"], "g6-astra-low")
        args["capability"]["available_profiles"].reverse()
        self.assertEqual(decide(**args, policy_digest=self.digest)["approved_profile"], "g6-astra-low")
        args["capability"]["available_profiles"] = ["future-only"]
        self.assertIsNone(decide(**args, policy_digest=self.digest)["exact_tool_parameters"])

    def test_partial_sources_keep_known_exclusions_and_distinct_efforts(self):
        old = ("gpt-6-astra", "low")
        new = ("gpt-6.2-sol", "medium")
        for provider, native in [(None, {old}), ({old}, None)]:
            observed = sources.project(self.catalog, provider, provider is not None, native, set())
            self.assertEqual(observed["available_profiles"], ["g6-astra-low"])
        self.assertEqual(sources.project(self.catalog, {new}, True, None, set())["available_profiles"], [])
        self.assertEqual(
            sources.project(self.catalog, {new}, True, None, {new})["available_profiles"], ["g62-sol-medium"]
        )
        self.assertEqual(
            sources.project(self.catalog, {new}, True, {(new[0], "high")}, set())["available_profiles"], []
        )
        self.assertEqual(sources.project(self.catalog, None, False, set(), set())["available_profiles"], [])

    def test_exported_catalogs_reject_changed_digest_and_ambiguous_tuples(self):
        desc = dict(catalogs.entries()[0])
        raw = (catalogs.DATA / desc["file"]).read_bytes()
        with self.assertRaisesRegex(RoutingError, "CATALOG_DIGEST_MISMATCH"):
            catalogs._load(raw + b" ", desc)
        value = json.loads(raw)
        dup = copy.deepcopy(value["models"][0])
        dup.update(id="other", priority=251)
        value["models"].append(dup)
        import hashlib

        payload = json.dumps(value).encode()
        desc["sha256"] = hashlib.sha256(payload).hexdigest()
        with self.assertRaisesRegex(RoutingError, "CATALOG_AMBIGUOUS_TUPLE"):
            catalogs._load(payload, desc)

    def test_old_new_roots_keep_their_policy_and_late_terminal(self):
        first = self.home / "old.jsonl"
        second = self.home / "new.jsonl"
        self.root(first, "old")
        legacy = self.start(first, "old", "g6-sol-medium")
        old_prefix = first.read_bytes()
        self.switch("desktop-catalog-v2", 0)
        self.root(second, "new")
        modern = self.start(second, "new", "g62-sol-medium")
        self.assertEqual(modern["decision"]["exact_tool_parameters"]["model"], "gpt-6.2-sol")
        self.assertEqual(legacy["decision"]["exact_tool_parameters"]["model"], "gpt-6-sol")
        self.switch(catalogs.LEGACY_ID, 1)
        self.assertEqual(self.root(first, "old")["root"]["policy_digest"], catalogs.LEGACY)
        self.assertEqual(self.root(second, "new")["root"]["policy_digest"], self.digest)
        for file, name in ((second, "new"), (first, "old")):
            budget.record_terminal(
                file, agent_path="/root/" + name, outcome="PASS", proof_ref=ref("done-" + name)
            )
            before = file.read_bytes()
            budget.record_terminal(
                file, agent_path="/root/" + name, outcome="PASS", proof_ref=ref("done-" + name)
            )
            self.assertEqual(file.read_bytes(), before)
            view = budget.snapshot(budget.read_budget(file), work_item_id="status", depth=0)
            self.assertEqual(
                (view["completed_charged_units"], view["completed_charged_attempts"], view["active_calls"]),
                (4, 1, 0),
            )
        self.assertTrue(first.read_bytes().startswith(old_prefix))
        old_manifest = self.home / "bundle" / "manifest.json"
        old_manifest.parent.mkdir()
        old_manifest.write_text(
            json.dumps(
                {
                    "package": "codex-cross-project-engineering-assistant",
                    "desktop_g6_default_v1": {
                        "policy_id": catalogs.LEGACY_ID,
                        "readable_budget_schema_versions": ["g6-budget-journal/1"],
                    },
                }
            )
        )
        self.assertFalse(routing.rollback_check(self.repo, old_manifest, [second])["safe_to_replace_reader"])
        self.assertTrue(
            routing.rollback_check(self.repo, self.repo / "manifest.json", [first, second])[
                "safe_to_replace_reader"
            ]
        )
        report = study.compare(self.repo, "desktop-catalog-v2", [first, second])
        self.assertEqual(report["quality_status"], "INSUFFICIENT_FINALIZED_SAMPLES")
        self.assertEqual(report["independent_roots"], 2)
        self.assertEqual(report["strategy_change"], "NONE")

    def test_native_turn_classification_and_unavailable_explicit_model(self):
        self.switch("desktop-catalog-v2", 0)
        ev = {
            "hook_event_name": "UserPromptSubmit",
            "cwd": str(self.repo),
            "session_id": "localtest",
            "turn_id": "turn-1",
            "prompt": "task_kind=mechanical\nRead the declared fixture.",
        }
        intent.observe(ev)
        view = hook.preview(
            session_id="localtest",
            cwd=self.repo,
            agent_type="explorer",
            task_name="lookup",
            message="Read the fixture.",
            turn_id="turn-1",
        )
        self.assertEqual(view["approved_profile"], "g6-luna-low")
        later = hook.preview(
            session_id="localtest",
            cwd=self.repo,
            agent_type="explorer",
            task_name="general",
            message="Read the fixture.",
            turn_id="turn-2",
        )
        self.assertEqual(later["approved_profile"], "g6-sol-medium")
        intent.observe({**ev, "turn_id": "turn-3", "prompt": "use unknown-fixture-model medium"})
        with self.assertRaisesRegex(RoutingError, "USER_EXACT_PROFILE_NOT_IN_APPROVED_CATALOG"):
            hook.preview(
                session_id="localtest",
                cwd=self.repo,
                agent_type="worker",
                task_name="choice",
                message="Bound task.",
                turn_id="turn-3",
            )
        self.assertIsNone(intent.parse("> use gpt-6.2-sol medium"))
        self.assertIsNone(intent.parse("use gpt-6.2-sol medium\nuse gpt-6-astra high"))
        self.assertIsNone(intent.parse("do not use this model"))

    def test_once_only_pilot_is_reserved_atomically_and_never_overrides_an_exclusion(self):
        self.switch("desktop-catalog-v2", 0)
        path = self.home / "pilot.jsonl"
        self.root(path, "pilot")
        now = datetime.now(timezone.utc).isoformat()
        args = inputs()
        facts = args["facts"]
        facts.update(identity=self.identity, task_id="pilot")
        token = ref(["native-turn", "one-exact-pilot"])
        cap = {
            "schema_version": "g6-desktop-capability/2",
            "source_ref": ref("verified-provider"),
            "coverage": "PARTIAL",
            "available_profiles": ["g62-sol-medium"],
            "latency_ms": {},
            "pilot_ref": token,
        }

        def prepare(name):
            return budget.prepare(
                path,
                facts={**facts, "work_item_id": name},
                capability=cap,
                gates=[],
                agent_type="worker",
                task_name=name,
                message="One explicit test.",
                decision_time=now,
                explicit_user_profile="g62-sol-medium",
            )

        a, b = prepare("first"), prepare("second")

        def reserve(item, call):
            return budget.approve_and_reserve(
                path,
                permit_id=item["permit_id"],
                host_call_id=call,
                session_id="pilot",
                cwd=self.repo,
                args=item["decision"]["exact_tool_parameters"],
                now=now,
            )

        self.assertFalse(reserve(a, "a")["idempotent"])
        self.assertTrue(reserve(a, "a")["idempotent"])
        with self.assertRaisesRegex(RoutingError, "G6_EXPLICIT_PILOT_ALREADY_ATTEMPTED"):
            reserve(b, "b")
        self.assertEqual(len(budget.read_budget(path)["reservations"]), 1)
        unavailable = sources.project(
            self.catalog, {("gpt-6.2-sol", "medium")}, True, set(), {("gpt-6.2-sol", "medium")}
        )
        self.assertEqual(unavailable["available_profiles"], [])

    def test_target_reader_guard_blocks_inflight_rollback_and_accepts_current_bundle(self):
        self.switch("desktop-catalog-v2", 0)
        path = self.home / "active.jsonl"
        self.root(path, "active")
        self.start(path, "active", "g62-sol-medium")
        from cp_runtime.g6_handoff_v1 import bind

        bind(
            session_id="active",
            repo_path=self.repo,
            new_ledger_path=path,
            user_change_ref=ref("test-binding"),
        )
        with self.assertRaisesRegex(RoutingError, "CATALOG_RETAIN_READER_FOR_ACTIVE_ROOT"):
            routing.check_replacement(
                self.home, {"policy_digests": [catalogs.LEGACY], "journal_versions": ["g6-budget-journal/1"]}
            )
        routing.check_replacement(self.home, routing.reader_contract(self.repo / "manifest.json"))
        budget.record_terminal(path, agent_path="/root/active", outcome="PASS", proof_ref=ref("done"))
        routing.check_replacement(self.home, None)

    def test_switch_refuses_missing_installed_reader_without_consuming_request(self):
        before = routing.selection(self.repo, "preview", "desktop-catalog-v2", 0)
        with patch(
            "cp_runtime.g6_runtime_support.installed_task_scope_support", return_value={"supported": False}
        ):
            with self.assertRaisesRegex(RoutingError, "CATALOG_MATCHING_INSTALLED_READER_REQUIRED"):
                routing.selection(self.repo, "apply", "desktop-catalog-v2", 0, before["request_ref"])
        self.assertEqual(routing.selection(self.repo, "show")["current_digest"], catalogs.LEGACY)

    def test_registered_ledger_only_expands_same_account_alias(self):
        account = self.home / "physical-account"
        ledger = account / "history" / "budget.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("historical ledger", encoding="utf-8")
        alias = self.home / ".codex"
        try:
            alias.symlink_to(account, target_is_directory=True)
        except OSError:
            self.skipTest("This platform does not permit creation of a test directory alias")
        via_alias = alias / "history" / ledger.name
        self.assertEqual(routing.registered_ledger_path(via_alias, account), ledger.resolve())
        other = self.home / "different-account"
        other.mkdir()
        with self.assertRaisesRegex(RuntimeError, "LINK_REJECTED"):
            routing.registered_ledger_path(via_alias, other)
        inside = account / "linked-history"
        inside.symlink_to(ledger.parent, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "LINK_REJECTED"):
            routing.registered_ledger_path(alias / inside.name / ledger.name, account)
        with self.assertRaisesRegex(RoutingError, "CATALOG_ROLLBACK_ROOT_BINDING"):
            routing.registered_ledger_path(alias / "history" / ".." / "history" / ledger.name, account)
        with self.assertRaisesRegex(RuntimeError, "LINK_REJECTED"):
            routing.registered_ledger_path(alias / "missing.jsonl", account)

    def test_component_alias_uses_only_the_installed_identity_and_exact_digest(self):
        import hashlib

        physical = self.home / "installed-host"
        physical.mkdir()
        binary = physical / ("codex.exe" if os.name == "nt" else "codex")
        binary.write_bytes(b"registered local component")
        alias = self.home / "alias"
        try:
            alias.symlink_to(physical, target_is_directory=True)
        except OSError:
            self.skipTest("Platform does not permit a test directory alias")
        state = {
            "compatibility_snapshot": {
                "host_binding": {
                    "executable_path": str(binary),
                    "executable_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                }
            }
        }
        (self.home / "cp-assistant-v6-state.json").write_text(json.dumps(state), encoding="utf-8")
        with patch.dict(os.environ, CP_ASSISTANT_DESKTOP_COMPONENT=str(alias / binary.name)):
            self.assertEqual(sources._component(verify_binary=True), binary.resolve())
            binary.write_bytes(b"changed after registration")
            with self.assertRaisesRegex(RoutingError, "CAPABILITY_COMPONENT_CHANGED"):
                sources._component(verify_binary=True)

    def test_quality_cohorts_require_registered_evidence_and_distinct_roots(self):
        from cp_runtime.evidence import record_evidence
        from cp_runtime.project import onboard_project

        binding = onboard_project(
            repo_path=self.repo,
            project_id=self.identity["project_id"],
            context_dir=self.home / "project-context",
        )
        self.switch("desktop-catalog-v2", 0)
        paths, evidence_files = [], []
        for number in range(3):
            name = "graded" + str(number)
            path = self.home / (name + ".jsonl")
            self.root(path, name)
            result = self.start(path, name, "g62-sol-medium", kind="ordinary")
            pid = result["permit_id"]
            budget.record_terminal(path, agent_path="/root/" + name, outcome="PASS", proof_ref=ref(name))
            state = budget.read_budget(path)
            fields = {
                "permit": pid,
                "terminal": ref(state["terminals"][pid]),
                "policy": self.digest,
                "root": ref(state["root"]),
                "repository": self.identity["repo_fingerprint"],
                "initial_baseline": state["permits"][pid]["facts"]["baseline_sha256"],
                "accepted": "1",
                "rework": "0",
            }
            evidence = self.home / (name + "-quality.json")
            record_evidence(
                evidence,
                name,
                binding.profile_path,
                name,
                self.repo,
                "validation",
                "routing-quality/1",
                "valid",
                "parent-coordinator",
                "Synthetic fixture for the evidence contract.",
                [key + "=" + value for key, value in fields.items()],
            )
            paths.append(path)
            evidence_files.append(evidence)
        result = study.compare(
            self.repo,
            "desktop-catalog-v2",
            paths,
            evidence=evidence_files,
            profile=binding.profile_path,
            save_timing=True,
        )
        self.assertEqual(result["independent_roots"], 3)
        self.assertEqual(result["graded_cohorts"][0]["independent_roots"], 3)
        self.assertEqual(result["stored_timing_cohorts"], 1)
        self.assertIn(
            "g62-sol-medium",
            study.comparable_timing(self.repo, self.identity, self.digest, "worker", "ordinary"),
        )
        self.assertEqual(
            study.comparable_timing(self.repo, self.identity, self.digest, "reviewer", "ordinary"), {}
        )
        self.assertIsNone(result["actual_credits"])
