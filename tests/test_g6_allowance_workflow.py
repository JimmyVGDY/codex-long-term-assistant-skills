"""中文：真实脚本/Hook 子进程中的隔离追加链路，不声称真实用户或模型调用。

English: Isolated subprocess workflow, including installed-layout hooks.
Native-format fixtures are not evidence of real human approval or model execution.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cp_runtime import g6_budget_v1 as budget, g6_review_requests as requests
from cp_runtime.common import utc_now
from cp_runtime.payload_integrity import build_manifest
from cp_runtime.routing_contract import RoutingError, ref

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "skills/multi-agent-independent-review/scripts/review_controller.py"
PACKET = ROOT / "skills/multi-agent-independent-review/scripts/review_packet.py"
ROLE = "cp_review_security_access"


class AllowanceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home, self.repo = self.base / "home", self.base / "repo"
        (self.repo / "src").mkdir(parents=True)
        self.packet, self.review = self.base / "packet", self.base / "review"
        self.session = "allowance-workflow-fixture"
        self.transcript = self.home / "sessions" / ("rollout-" + self.session + ".jsonl")
        self.transcript.parent.mkdir(parents=True)
        self.env = dict(os.environ, CODEX_HOME=str(self.home), CODEX_THREAD_ID=self.session,
                        PLUGIN_ROOT=str(ROOT), PYTHONUTF8="1")
        for key in ("CP_DELEGATION_BUDGET_PATH", "CP_DELEGATION_ENVELOPE_PATH"):
            self.env.pop(key, None)
        self.install_runtime_fixture()
        for command in (["init", "-q"], ["config", "user.name", "Test"],
                        ["config", "user.email", "test@example.invalid"]):
            subprocess.run(["git", *command], cwd=self.repo, check=True, capture_output=True)
        self.source = self.repo / "src/app.py"
        self.source.write_text("value = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.repo, check=True, capture_output=True)
        self.source.write_text("value = 2\n", encoding="utf-8")
        self.emit(self.transcript, "session_meta", {"id": self.session, "cwd": str(self.repo), "source": "desktop"})
        self.control("init", "--repo-path", self.repo, "--boundary-id", "feature-a", "--host-session-id", self.session)
        value = self.control("bind-native-source", "--transcript-path", self.transcript)
        self.ledger = Path(value["ledger_path"])
        self.make_packet()

    def emit(self, path, kind, payload):
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"type": kind, "timestamp": utc_now(), "payload": payload}, ensure_ascii=False) + "\n")

    def install_runtime_fixture(self):
        shutil.copytree(ROOT / "runtime", self.home / "runtime", ignore=shutil.ignore_patterns("__pycache__"))
        self.cache = self.home / "plugins/cache/cp-assistant-local/codex-cross-project-engineering-assistant/9.9.9"
        for name in (".codex-plugin", "skills", "hooks"):
            (self.cache / name).mkdir(parents=True)
        shutil.copytree(ROOT / "runtime", self.cache / "runtime", ignore=shutil.ignore_patterns("__pycache__"))
        for relative in ("skills/multi-agent-independent-review/scripts/review_packet.py",
                         "skills/multi-agent-independent-review/scripts/review_controller.py", "hooks/cp_hook.py"):
            target = self.cache / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        (self.home / "cp-assistant-hooks").mkdir()
        shutil.copyfile(ROOT / "hooks/cp_hook.py", self.home / "cp-assistant-hooks/cp_hook.py")
        manifest = build_manifest(self.cache, "codex-cross-project-engineering-assistant", "9.9.9")
        (self.cache / "PLUGIN_PAYLOAD_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        (self.home / "cp-assistant-v6-state.json").write_text(json.dumps({"mode": "plugin", "version": "9.9.9"}), encoding="utf-8")

    def tool(self, path, *args, ok=True):
        result = subprocess.run([sys.executable, "-B", str(path), *map(str, args)], cwd=self.repo,
            env=self.env, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def control(self, command, *args, ok=True):
        result = self.tool(CONTROLLER, command, "--review-dir", self.review, *args, ok=ok)
        return json.loads(result.stdout) if ok else result.stdout + result.stderr

    def make_packet(self):
        self.tool(PACKET, "create", "--repo-path", self.repo, "--output-dir", self.packet,
                  "--boundary-id", "feature-a", "--phase", "post", "--force")

    def plan(self, *args):
        return self.control("plan", "--phase", "post", "--packet-dir", self.packet,
                            "--reviewers", ROLE, "--allowed-path", "src", *args)

    def dispatch(self, **kwargs):
        return self.control("dispatch", "--phase", "post", "--round", 1, "--reviewer", ROLE, **kwargs)

    def hook(self, kind, data):
        payload = {"session_id": self.session, "turn_id": "turn-one", "cwd": str(self.repo),
                   "transcript_path": str(self.transcript), **data, "hook_event_name": kind}
        result = subprocess.run([sys.executable, "-B", str(ROOT / "hooks/cp_hook.py"), kind],
            input=json.dumps(payload, ensure_ascii=False), text=True, encoding="utf-8", capture_output=True,
            cwd=self.repo, env=self.env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def exhaust(self):
        # 中文：夹具只模拟基础终态事实，不运行真实 Agent，也不使用真实根账本。
        # English: Fixtures simulate base terminals, without real agents or live roots.
        for number in range(4):
            call = "base-" + str(number)
            args = {"task_name": "base_" + str(number), "agent_type": "worker", "model": "gpt-6-sol",
                    "reasoning_effort": "medium", "fork_turns": "none", "message": "Fixture base work " + str(number)}
            self.assertEqual(self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": call, "tool_input": args}), {})
            budget.record_receipt(self.ledger, host_call_id=call, disposition="created",
                                  agent_path="/root/base_" + str(number), proof_ref=ref(call))
            budget.record_terminal(self.ledger, agent_path="/root/base_" + str(number), outcome="PASS", proof_ref=ref("done-" + call))

    def approve(self, request):
        text = "<send_user_message_question_reply>\n" + json.dumps([{
            "questionItemId": "fixture-question", "question": request["question"], "answer": request["options"][0]}], ensure_ascii=False) + "\n</send_user_message_question_reply>"
        self.emit(self.transcript, "response_item", {"type": "message", "id": "approval-" + request["request_id"],
            "internal_chat_message_metadata_passthrough": {"turn_id": "turn-one", "content_item_kinds": ["user.text"]},
            "role": "user", "content": [{"type": "input_text", "text": text}]})
        self.hook("UserPromptSubmit", {"prompt": text})

    def child_result(self, args, call, report, *, acknowledge_context=True):
        self.hook("PostToolUse", {"tool_name": "spawn_agent", "tool_use_id": call,
            "tool_input": args, "tool_response": {"task_name": "/root/" + args["task_name"]}})
        child = "child-" + call
        transcript = self.home / "sessions" / ("rollout-" + child + ".jsonl")
        self.emit(transcript, "session_meta", {"id": child, "cwd": str(self.repo), "source": {
            "subagent": {"thread_spawn": {"parent_thread_id": self.session, "depth": 1,
                                          "agent_role": ROLE, "agent_path": "/root/" + args["task_name"]}}}})
        self.emit(transcript, "event_msg", {"type": "task_started", "turn_id": "child-turn"})
        self.last_bootstrap = self.hook("SubagentStart", {"agent_id": child, "agent_type": ROLE,
            "turn_id": "child-turn", "agent_transcript_path": str(transcript), "transcript_path": str(transcript)})
        context = self.last_bootstrap.get("hookSpecificOutput", {}).get("additionalContext", "")
        marker = re.search(r"context_sha256=[0-9a-f]{64}", context)
        if marker and acknowledge_context:
            report["checked_scope"] = [*report["checked_scope"], marker[0]]
        self.emit(transcript, "response_item", {"type": "message", "role": "assistant", "phase": "final_answer",
            "content": [{"type": "output_text", "text": json.dumps(report)}]})
        self.emit(transcript, "event_msg", {"type": "task_complete", "turn_id": "child-turn"})
        self.hook("SubagentStop", {"agent_id": child, "agent_type": ROLE, "turn_id": "child-turn",
            "agent_transcript_path": str(transcript), "transcript_path": str(transcript), "terminal_outcome": "PASS"})

    def test_exhaustion_quote_native_approval_dispatch_and_receipt(self):
        self.exhaust()
        plan = self.plan()
        blocked = self.dispatch()
        self.assertEqual(blocked["dispatch_recovery"]["reason_code"], "UNITS_EXHAUSTED")
        quoted = self.control("allowance-quote")["allowance_request"]
        self.assertEqual(quoted["allocations"][0]["units"], 4)
        self.approve(quoted)
        ready = self.dispatch()
        args = ready["dispatch_decision"]["exact_tool_parameters"]
        self.assertIsNotNone(args)
        self.assertEqual(self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "review-one", "tool_input": args}), {})
        resumed = self.dispatch()
        self.assertEqual(resumed["next_action"], "resume_existing_review")
        self.assertIsNone(resumed["dispatch_decision"]["exact_tool_parameters"])
        packet_hash = plan["plans"][plan["active_plan_key"]]["packet_sha256"]
        report = {"status": "pass", "findings": [], "checked_scope": ["packet_sha256=" + packet_hash],
                  "unverified_items": [], "summary": "Synthetic fixture result."}
        self.child_result(args, "review-one", report)
        state = budget.read_budget(self.ledger)
        self.assertEqual(budget.allowance_status(state)["total_usage"]["completed_charged_units"], 20)
        report_file = self.base / "report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")
        result = self.control("result", "--phase", "post", "--round", 1, "--reviewer", ROLE,
            "--status", "pass", "--summary", "Fixture", "--result-file", report_file)
        self.assertEqual(result["results"][ROLE]["verification_state"], "NATIVE_REPORT_VERIFIED")
        self.assertIn("G6_REVIEW_UNCHANGED_ALREADY_COMPLETE", self.dispatch(ok=False))

    def test_grant_survives_refreshed_packet_without_second_approval(self):
        self.exhaust()
        initial = self.plan()
        old_id = initial["plans"][initial["active_plan_key"]]["work_ids"][ROLE]
        quote = self.control("allowance-quote")["allowance_request"]
        self.approve(quote)
        old_call = requests.bind_call(self.ledger, work_id=old_id, packet_dir=self.packet)
        self.source.write_text("value = 3\n", encoding="utf-8")
        self.make_packet()
        refreshed = self.plan()
        self.assertEqual(refreshed["plans"][refreshed["active_plan_key"]]["work_ids"][ROLE], old_id)
        with self.assertRaises(RoutingError):
            requests.resolve_call(budget.read_budget(self.ledger), old_call)
        self.assertIsNotNone(self.dispatch()["dispatch_decision"]["exact_tool_parameters"])
        self.assertEqual(len(budget.read_budget(self.ledger)["allowance_grants"]), 1)

    def test_opaque_host_transport_uses_authoritative_context_and_scoped_funding(self):
        from cp_runtime.common import read_json
        from cp_runtime.g6_review_receipt_v1 import _receipt_path
        self.exhaust()
        plan = self.plan()
        self.approve(self.control("allowance-quote")["allowance_request"])
        args = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
        plain = args["message"]
        args["message"] = base64.urlsafe_b64encode(bytes([128]) + bytes(8) + b"a" * 64).decode()
        self.assertEqual(self.hook("PreToolUse", {"tool_name": "collaborationspawn_agent",
            "tool_use_id": "opaque", "tool_input": args}), {})
        packet = plan["plans"][plan["active_plan_key"]]["packet_sha256"]
        self.child_result(args, "opaque", {"status": "pass", "findings": [],
            "checked_scope": ["packet_sha256=" + packet], "unverified_items": [], "summary": "Fixture."})
        context = self.last_bootstrap["hookSpecificOutput"]["additionalContext"]
        self.assertIn(plain.split("\n\n", 1)[1], context)
        self.assertNotIn(args["message"], context)
        state = budget.read_budget(self.ledger)
        pid = state["host_calls"][ref("opaque")]
        self.assertNotEqual(state["permits"][pid]["funding_id"], "base")
        self.assertEqual(read_json(_receipt_path(self.ledger, pid), verify=True)["gate_state"], "PASS")

    def test_opaque_transport_cannot_use_missing_context_or_changed_role(self):
        self.exhaust()
        self.plan()
        self.approve(self.control("allowance-quote")["allowance_request"])
        args = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
        call = requests.resolve_call(budget.read_budget(self.ledger), args)
        plaintext = args["message"]
        args["message"] = base64.urlsafe_b64encode(bytes([128]) + bytes(8) + b"a" * 64).decode()
        bad_role = {**args, "agent_type": "cp_review_data_contract"}
        denied = self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "wrong-role", "tool_input": bad_role})
        self.assertIn("G6_REVIEW_CALL_PARAMETERS_CHANGED", denied["hookSpecificOutput"]["permissionDecisionReason"])
        requests._context_file(self.ledger, call["call_id"]).unlink()
        denied = self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "missing-context", "tool_input": args})
        self.assertIn("G6_REVIEW_CONTEXT_UNAVAILABLE", denied["hookSpecificOutput"]["permissionDecisionReason"])
        denied = self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "missing-plain-context",
            "tool_input": {**args, "message": plaintext}})
        self.assertIn("G6_REVIEW_CONTEXT_UNAVAILABLE", denied["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(len(budget.read_budget(self.ledger)["reservations"]), 4)

    def test_packet_only_report_cannot_claim_authoritative_context_delivery(self):
        from cp_runtime.common import read_json
        from cp_runtime.g6_review_receipt_v1 import _receipt_path
        plan = self.plan()
        args = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
        self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "no-context-ack", "tool_input": args})
        packet = plan["plans"][plan["active_plan_key"]]["packet_sha256"]
        self.child_result(args, "no-context-ack", {"status": "pass", "findings": [],
            "checked_scope": ["packet_sha256=" + packet], "unverified_items": [], "summary": "Fixture."},
            acknowledge_context=False)
        state = budget.read_budget(self.ledger)
        pid = state["host_calls"][ref("no-context-ack")]
        receipt = read_json(_receipt_path(self.ledger, pid), verify=True)
        self.assertEqual(receipt["gate_state"], "MISSING_EVIDENCE")
        self.assertEqual(receipt["reason_code"], "REVIEW_CONTEXT_UNVERIFIED")

    def test_opaque_registered_continuation_prepares_fresh_spawn_without_spending(self):
        self.plan()
        args = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
        self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "first-review", "tool_input": args})
        self.child_result(args, "first-review", {"status": "incomplete", "findings": [],
            "checked_scope": [], "unverified_items": ["More material needed."], "summary": "Fixture."})
        opaque = base64.urlsafe_b64encode(bytes([128]) + bytes(8) + b"a" * 64).decode()
        result = self.hook("PreToolUse", {"tool_name": "followup_task", "tool_use_id": "opaque-followup",
            "tool_input": {"target": "/root/" + args["task_name"], "message": opaque}})
        self.assertIn("prepare_scoped_review_spawn", result["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(len(budget.read_budget(self.ledger)["reservations"]), 1)
        fresh = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
        self.assertNotEqual(fresh["task_name"], args["task_name"])

    def test_registered_reviewer_continuation_uses_distinct_attempt_and_same_work(self):
        plan = self.plan()
        args = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
        self.assertEqual(self.hook("PreToolUse", {"tool_name": "spawn_agent",
            "tool_use_id": "initial", "tool_input": args}), {})
        self.child_result(args, "initial", {"status": "incomplete", "findings": [], "checked_scope": [],
            "unverified_items": ["Need another pass."], "summary": "Incomplete fixture."})
        inputs = {"target": "/root/" + args["task_name"], "message": args["message"]}
        event = {"tool_name": "followup_task", "tool_use_id": "followup", "tool_input": inputs}
        self.assertEqual(self.hook("PreToolUse", event), {})
        self.assertEqual(self.hook("PostToolUse", {**event,
            "tool_response": {"task_name": inputs["target"]}}), {})
        state = budget.read_budget(self.ledger)
        permits = list(state["permits"].values())
        self.assertEqual(len(state["reservations"]), 2)
        self.assertEqual(len(state["receipts"]), 2)
        self.assertEqual(permits[0]["work_item_id"], permits[1]["work_item_id"])
        self.assertNotEqual(permits[0]["task_name"], permits[1]["task_name"])
        self.assertEqual(len(state["terminals"]), 1)

    def test_pass_without_matching_packet_proof_does_not_close_review(self):
        from cp_runtime.common import read_json
        from cp_runtime.g6_review_receipt_v1 import _receipt_path
        plan = self.plan()
        work = plan["plans"][plan["active_plan_key"]]["work_ids"][ROLE]
        for number, checked in enumerate(([], ["packet_sha256=" + "0" * 64])):
            args = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
            call = "unbound-report-" + str(number)
            self.assertEqual(self.hook("PreToolUse", {"tool_name": "spawn_agent",
                "tool_use_id": call, "tool_input": args}), {})
            self.child_result(args, call, {"status": "pass", "findings": [], "checked_scope": checked,
                "unverified_items": [], "summary": "Fixture without matching packet proof."})
            state = budget.read_budget(self.ledger)
            permit_id = state["host_calls"][ref(call)]
            receipt = read_json(_receipt_path(self.ledger, permit_id), verify=True)
            self.assertEqual(receipt["gate_state"], "MISSING_EVIDENCE")
            self.assertEqual(receipt["reason_code"], "REVIEW_PACKET_UNVERIFIED")
            self.assertIsNotNone(requests.bind_call(self.ledger, work_id=work, packet_dir=self.packet))

    def test_expanded_scope_cannot_use_existing_grant(self):
        self.exhaust()
        initial = self.plan()
        work = initial["plans"][initial["active_plan_key"]]["work_ids"][ROLE]
        self.approve(self.control("allowance-quote")["allowance_request"])
        (self.repo / "outside.py").write_text("value = 1\n", encoding="utf-8")
        self.make_packet()
        with self.assertRaisesRegex(RoutingError, "SCOPE_EXPANDED"):
            requests.bind_call(self.ledger, work_id=work, packet_dir=self.packet)
        self.assertIn("G6_REVIEW_SCOPE_EXPANDED", self.control("plan", "--phase", "post", "--packet-dir", self.packet,
            "--reviewers", ROLE, "--allowed-path", "src", ok=False))

    def test_close_preserves_grant_history_but_blocks_new_spend(self):
        self.exhaust()
        value = self.plan()
        work = value["plans"][value["active_plan_key"]]["work_ids"][ROLE]
        self.approve(self.control("allowance-quote")["allowance_request"])
        self.control("close", "--conclusion", "工具或环境受限，未完成独立复审")
        state = budget.read_budget(self.ledger)
        self.assertEqual(len(state["allowance_grants"]), 1)
        self.assertIn(work, state["closed_review_work"])
        with self.assertRaises(RoutingError):
            requests.bind_call(self.ledger, work_id=work, packet_dir=self.packet)

    def test_future_repair_is_explicitly_reserved(self):
        value = self.plan("--reserve-repair")
        plan = value["plans"][value["active_plan_key"]]
        self.assertEqual(len(plan["future_work_ids"]), 1)
        self.assertEqual(budget.snapshot(budget.read_budget(self.ledger), work_item_id="worker", depth=0)
                         ["future_required_hold_units"], 8)

    def test_repeat_quote_after_approval_uses_existing_grant(self):
        self.exhaust()
        self.plan()
        self.approve(self.control("allowance-quote")["allowance_request"])
        value = self.control("allowance-quote")
        self.assertEqual(value["allowance_status"]["status"], "ALREADY_AUTHORIZED")
        self.assertNotIn("allowance_request", value)
        self.assertEqual(len(budget.read_budget(self.ledger)["allowance_requests"]), 1)

    def test_locale_change_preserves_request_and_accepts_english_approval(self):
        self.exhaust()
        self.plan()
        chinese = self.control("allowance-quote")["allowance_request"]
        english = self.control("allowance-quote", "--locale", "en")["allowance_request"]
        self.assertEqual(chinese["request_id"], english["request_id"])
        self.assertNotEqual(chinese["question"], english["question"])
        self.assertEqual(english["options"][0], "Approve this allowance")
        self.approve(english)
        self.assertEqual(len(budget.read_budget(self.ledger)["allowance_grants"]), 1)

    def test_quote_waits_for_existing_unknown_call(self):
        self.exhaust()
        self.plan()
        self.approve(self.control("allowance-quote")["allowance_request"])
        args = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
        self.assertEqual(self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "unknown", "tool_input": args}), {})
        value = self.control("allowance-quote")
        self.assertEqual(value["allowance_status"]["status"], "NATIVE_OUTCOME_PENDING")
        self.assertNotIn("allowance_request", value)

    def test_pending_native_history_is_recovered_without_reasking(self):
        self.exhaust()
        self.plan()
        quoted = self.control("allowance-quote")["allowance_request"]
        self.emit(self.transcript, "response_item", {"type": "function_call_output", "output": "x" * 2_200_000})
        value = self.control("allowance-quote")
        self.assertEqual(value["next_action"], "continue_native_authority_recovery")
        self.assertNotIn("allowance_request", value)
        self.approve(quoted)
        self.assertEqual(len(budget.read_budget(self.ledger)["allowance_grants"]), 1)

    def test_missing_native_source_reports_unsupported_before_asking(self):
        self.plan()
        from cp_runtime.g6_allowance_authority import source_path
        source_path(self.ledger).unlink()
        value = self.control("allowance-quote")
        self.assertFalse(value["allowance_status"]["supported"])
        self.assertNotIn("allowance_request", value)
        self.assertEqual(len(budget.read_budget(self.ledger)["allowance_requests"]), 0)

    def test_account_runtime_resolves_verified_matching_plugin_packet_tool(self):
        self.exhaust()
        self.plan()
        self.approve(self.control("allowance-quote")["allowance_request"])
        args = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
        self.env["PLUGIN_ROOT"] = str(self.home)
        self.assertEqual(self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "installed-layout", "tool_input": args}), {})

    def test_old_installed_reader_is_rejected_before_writing_new_events_or_asking(self):
        before = self.ledger.read_bytes()
        (self.home / "runtime/cp_runtime/g6_allowance_contract.py").unlink()
        self.assertIn("G6_INSTALLED_ALLOWANCE_READER_UNAVAILABLE", self.control("plan", "--phase", "post",
            "--packet-dir", self.packet, "--reviewers", ROLE, ok=False))
        self.assertEqual(self.ledger.read_bytes(), before)
        value = self.control("allowance-quote")
        self.assertFalse(value["allowance_status"]["supported"])
        self.assertNotIn("allowance_request", value)
        self.assertEqual(self.ledger.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
