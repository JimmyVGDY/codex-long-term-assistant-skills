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

    def child_result(self, args, call, report, *, acknowledge_context=True, complete=True, stop=True):
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
            if isinstance(report["checked_scope"], dict):
                report["checked_scope"]["context_sha256"] = marker[0].split("=", 1)[1]
            else:
                report["checked_scope"] = [*report["checked_scope"], marker[0]]
        self.emit(transcript, "response_item", {"type": "message", "role": "assistant", "phase": "final_answer",
            "content": [{"type": "output_text", "text": json.dumps(report)}]})
        if complete:
            self.emit(transcript, "event_msg", {"type": "task_complete", "turn_id": "child-turn"})
        if stop:
            self.hook("SubagentStop", {"agent_id": child, "agent_type": ROLE, "turn_id": "child-turn",
                "agent_transcript_path": str(transcript), "transcript_path": str(transcript), "terminal_outcome": "PASS"})
        return transcript

    def unsettled_review(self, *, complete=True):
        self.exhaust()
        self.plan()
        self.approve(self.control("allowance-quote")["allowance_request"])
        value = self.dispatch()
        args = value["dispatch_decision"]["exact_tool_parameters"]
        self.assertEqual(self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "missing-stop",
                                                "tool_input": args}), {})
        report = {"status": "pass", "findings": [], "checked_scope": {
            "files": ["src/app.py"], "packet_sha256": value["assignments"][ROLE]["packet_sha256"],
            "isolation": "logical-readonly"}, "unverified_items": [], "summary": "Fixture review"}
        path = self.child_result(args, "missing-stop", report, complete=complete, stop=False)
        return path, report

    @unittest.skipUnless(os.name == "nt", "Windows namespace aliases")
    def test_native_namespace_alias_uses_existing_allowance_without_rebinding(self):
        from cp_runtime import g6_allowance_authority as authority
        from cp_runtime.path_identity import _alternate_windows_spelling
        self.exhaust()
        self.plan()
        self.approve(self.control("allowance-quote")["allowance_request"])
        args = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
        before = budget.read_budget(self.ledger)
        source = json.loads(authority.source_path(self.ledger).read_text(encoding="utf-8"))
        alias = _alternate_windows_spelling(str(self.transcript.resolve()))
        self.assertNotEqual(str(Path(alias).resolve()), str(self.transcript.resolve()))
        result = self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "alias-dispatch",
                                        "tool_input": args, "transcript_path": alias})
        self.assertEqual(result, {})
        after = budget.read_budget(self.ledger)
        self.assertEqual(before["allowance_grants"], after["allowance_grants"])
        current = json.loads(authority.source_path(self.ledger).read_text(encoding="utf-8"))
        for key in ("transcript_path", "transcript_file_ref", "transcript_path_ref", "header_ref"):
            self.assertEqual(current[key], source[key])
        usage = budget.allowance_status(after)["total_usage"]
        self.assertEqual((usage["completed_charged_units"], usage["inflight_reserved_units"], usage["active_calls"]), (16, 4, 1))

    def test_reconcile_bound_completion_without_stop_retains_charge_and_is_idempotent(self):
        path, report = self.unsettled_review()
        before = budget.read_budget(self.ledger)
        pid = before["host_calls"][ref("missing-stop")]
        self.assertNotIn(pid, before["terminals"])
        value = self.control("reconcile")
        self.assertEqual(value["native_reconciliation"]["items"][0]["status"], "COMPLETE")
        after = budget.read_budget(self.ledger)
        self.assertEqual(after["terminals"][pid]["outcome"], "UNKNOWN")
        usage = budget.allowance_status(after)["total_usage"]
        self.assertEqual((usage["completed_charged_units"], usage["completed_charged_attempts"], usage["active_calls"]), (20, 5, 0))
        original = self.ledger.read_bytes()
        self.control("reconcile")
        self.hook("SubagentStop", {"agent_id": "child-missing-stop", "agent_type": ROLE, "turn_id": "child-turn",
            "agent_transcript_path": str(path), "transcript_path": str(path), "terminal_outcome": "PASS"})
        self.assertEqual(self.ledger.read_bytes(), original)
        result = self.base / "report.json"
        result.write_text(json.dumps(report), encoding="utf-8")
        recorded = self.control("result", "--phase", "post", "--round", 1, "--reviewer", ROLE,
                                "--status", "pass", "--summary", "Fixture", "--result-file", result)
        self.assertEqual(recorded["results"][ROLE]["verification_state"], "NATIVE_REPORT_VERIFIED")

    def test_reconcile_final_without_native_terminal_does_not_settle(self):
        path, _ = self.unsettled_review(complete=False)
        before = self.ledger.read_bytes()
        self.control("reconcile")
        self.assertEqual(self.ledger.read_bytes(), before)
        self.emit(path, "event_msg", {"type": "task_complete", "turn_id": "foreign-turn"})
        self.control("reconcile")
        self.assertEqual(self.ledger.read_bytes(), before)
        self.emit(path, "event_msg", {"type": "turn_aborted", "turn_id": "child-turn"})
        self.control("reconcile")
        state = budget.read_budget(self.ledger)
        pid = state["host_calls"][ref("missing-stop")]
        self.assertEqual(state["terminals"][pid]["outcome"], "CANCELLED")
        from cp_runtime.g6_review_receipt_v1 import _receipt_path
        receipt = json.loads(_receipt_path(self.ledger, pid).read_text(encoding="utf-8"))
        self.assertEqual(receipt["report_status"], "pass")
        self.assertEqual(receipt["gate_state"], "MISSING_EVIDENCE")
        self.assertEqual(receipt["reason_code"], "REVIEW_NATIVE_TERMINAL_UNSUCCESSFUL")
        call = next(row for row in state["review_calls"].values()
                    if row["task_name"] == state["permits"][pid]["task_name"])
        self.assertFalse(requests._same_packet_completed(self.ledger, state,
                         state["permits"][pid]["work_item_id"], call["packet_sha256"]))

    def test_receipt_publish_failure_recovers_frozen_metadata_without_new_charge(self):
        from unittest import mock
        from cp_runtime import g6_reconciliation as reconciliation, g6_review_receipt_v1 as receipts
        path, report = self.unsettled_review()
        pid = budget.read_budget(self.ledger)["host_calls"][ref("missing-stop")]
        with mock.patch.dict(os.environ, self.env), mock.patch.object(receipts, "_publish_receipt", side_effect=OSError("fixture publish failure")):
            reconciliation.recover_bound_terminals(self.ledger)
        settled = self.ledger.read_bytes()
        self.assertIn(pid, budget.read_budget(self.ledger)["terminals"])
        self.assertFalse(receipts._receipt_path(self.ledger, pid).exists())
        self.assertNotIn(report["summary"], receipts._pending_path(self.ledger, pid).read_text(encoding="utf-8"))
        changed = {**report, "summary": "Later answer must not replace the frozen report."}
        self.emit(path, "response_item", {"type": "message", "role": "assistant", "phase": "final_answer",
                  "content": [{"type": "output_text", "text": json.dumps(changed)}]})
        value = self.control("reconcile")
        self.assertEqual(value["native_reconciliation"]["items"][0]["status"], "RECEIPT_PUBLISHED")
        saved = json.loads(receipts._receipt_path(self.ledger, pid).read_text(encoding="utf-8"))
        self.assertEqual(saved["report_ref"], ref(report))
        self.assertEqual(self.ledger.read_bytes(), settled)
        self.control("reconcile")
        self.assertEqual(self.ledger.read_bytes(), settled)

    def missing_creation_child(self):
        self.exhaust()
        self.plan()
        self.approve(self.control("allowance-quote")["allowance_request"])
        args = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
        self.assertEqual(self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "missing-create",
                                                "tool_input": args}), {})
        child = "child-missing-creation"
        transcript = self.home / "sessions" / ("rollout-" + child + ".jsonl")
        self.emit(transcript, "session_meta", {"id": child, "cwd": str(self.repo), "source": {
            "subagent": {"thread_spawn": {"parent_thread_id": self.session, "depth": 1,
                "agent_role": ROLE, "agent_path": "/root/" + args["task_name"]}}}})
        self.emit(transcript, "event_msg", {"type": "task_started", "turn_id": "child-turn"})
        self.emit(transcript, "response_item", {"type": "message", "role": "assistant", "phase": "final_answer",
            "content": [{"type": "output_text", "text": json.dumps({"status": "incomplete", "findings": [],
                "checked_scope": [], "unverified_items": ["No native context receipt."], "summary": "Fixture"})}]})
        self.emit(transcript, "event_msg", {"type": "task_complete", "turn_id": "child-turn"})
        return transcript

    def test_explicit_native_child_recovers_missing_creation_and_terminal_without_context_claim(self):
        from cp_runtime.path_identity import _alternate_windows_spelling
        transcript = self.missing_creation_child()
        pid = budget.read_budget(self.ledger)["host_calls"][ref("missing-create")]
        self.assertNotIn(pid, budget.read_budget(self.ledger)["receipts"])
        value = self.control("reconcile", "--child-transcript", transcript)
        self.assertEqual(value["native_reconciliation"]["creations"][0]["status"], "CREATION_RECOVERED")
        state = budget.read_budget(self.ledger)
        self.assertEqual(state["receipts"][pid]["disposition"], "created")
        self.assertEqual(state["terminals"][pid]["outcome"], "UNKNOWN")
        from cp_runtime.g6_review_receipt_v1 import _receipt_path
        receipt = json.loads(_receipt_path(self.ledger, pid).read_text(encoding="utf-8"))
        self.assertEqual(receipt["gate_state"], "MISSING_EVIDENCE")
        before = self.ledger.read_bytes()
        self.control("reconcile", "--child-transcript", transcript)
        alias = _alternate_windows_spelling(str(transcript.resolve())) if os.name == "nt" else str(transcript)
        self.hook("SubagentStop", {"agent_id": "child-missing-creation", "agent_type": ROLE,
            "turn_id": "child-turn", "agent_transcript_path": alias, "transcript_path": alias,
            "terminal_outcome": "PASS"})
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_explicit_child_source_rejects_foreign_unreserved_and_predating_headers(self):
        transcript = self.missing_creation_child()
        original = transcript.read_bytes()
        lines = original.splitlines(keepends=True)
        before = self.ledger.read_bytes()
        for change in ("parent", "task", "time"):
            header = json.loads(lines[0])
            spawn = header["payload"]["source"]["subagent"]["thread_spawn"]
            if change == "parent":
                spawn["parent_thread_id"] = "other-parent"
            elif change == "task":
                spawn["agent_path"] = "/root/unreserved_fixture"
            else:
                header["timestamp"] = "2020-01-01T00:00:00Z"
            transcript.write_bytes((json.dumps(header) + "\n").encode() + b"".join(lines[1:]))
            value = self.control("reconcile", "--child-transcript", transcript)
            self.assertTrue(value["native_reconciliation"]["errors"], change)
            self.assertEqual(self.ledger.read_bytes(), before)
        transcript.write_bytes(original)

    def test_staged_receipt_is_not_published_before_terminal_and_survives_append(self):
        from unittest import mock
        from cp_runtime import g6_reconciliation as reconciliation, g6_review_receipt_v1 as receipts
        path, report = self.unsettled_review()
        pid = budget.read_budget(self.ledger)["host_calls"][ref("missing-stop")]
        with mock.patch.dict(os.environ, self.env), mock.patch.object(budget, "record_terminal", side_effect=OSError("fixture terminal write failure")):
            reconciliation.recover_bound_terminals(self.ledger)
        self.assertNotIn(pid, budget.read_budget(self.ledger)["terminals"])
        self.assertFalse(receipts._receipt_path(self.ledger, pid).exists())
        self.assertIsNone(receipts.publish_pending(self.ledger, pid))
        frozen = receipts._read_pending(receipts._pending_path(self.ledger, pid))
        self.emit(path, "event_msg", {"type": "task_complete", "turn_id": "child-turn"})
        self.control("reconcile")
        self.assertEqual(budget.read_budget(self.ledger)["terminals"][pid], frozen["terminal"])
        saved = json.loads(receipts._receipt_path(self.ledger, pid).read_text(encoding="utf-8"))
        self.assertEqual(saved["report_ref"], ref(report))

    def test_pending_receipt_with_changed_terminal_proof_cannot_publish(self):
        from unittest import mock
        from cp_runtime import g6_reconciliation as reconciliation, g6_review_receipt_v1 as receipts
        from cp_runtime.common import atomic_write_json
        self.unsettled_review()
        pid = budget.read_budget(self.ledger)["host_calls"][ref("missing-stop")]
        with mock.patch.dict(os.environ, self.env), mock.patch.object(receipts, "_publish_receipt", side_effect=OSError("fixture publish failure")):
            reconciliation.recover_bound_terminals(self.ledger)
        before = self.ledger.read_bytes()
        target = receipts._pending_path(self.ledger, pid)
        value = receipts._read_pending(target)
        value["terminal"]["proof_ref"] = ref("different fixture proof")
        atomic_write_json(target, value, seal=True)
        with self.assertRaisesRegex(ValueError, "G6_REVIEW_PENDING_TERMINAL_CHANGED"):
            receipts.publish_pending(self.ledger, pid)
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertFalse(receipts._receipt_path(self.ledger, pid).exists())

    def test_reconcile_rejects_replaced_header_and_ambiguous_turns(self):
        path, _ = self.unsettled_review()
        before = self.ledger.read_bytes()
        self.env["CODEX_THREAD_ID"] = "foreign-parent"
        self.assertIn("G6_CURRENT_NATIVE_SESSION_REQUIRED", self.control("reconcile", ok=False))
        self.assertEqual(self.ledger.read_bytes(), before)
        self.env["CODEX_THREAD_ID"] = self.session
        original = path.read_bytes()
        lines = original.splitlines()
        header = json.loads(lines[0])
        header["payload"]["cwd"] = str(self.base / "unrelated")
        path.write_bytes(json.dumps(header).encode() + b"\n" + b"\n".join(lines[1:]) + b"\n")
        before = self.ledger.read_bytes()
        value = self.control("reconcile")
        self.assertTrue(value["native_reconciliation"]["errors"])
        self.assertEqual(self.ledger.read_bytes(), before)
        path.write_bytes(original)
        self.emit(path, "event_msg", {"type": "task_started", "turn_id": "different-turn"})
        self.control("reconcile")
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_execution_native_quote_context_and_settlement_are_not_review(self):
        self.exhaust()
        self.control("plan", "--phase", "post", "--packet-dir", self.packet,
                     "--agents", "explorer", "--allowed-path", "src", "--review-stage", "task_execution",
                     "--purpose", "Read public fixture inputs.")
        quoted = self.control("allowance-quote", "--additional-dispatches", 2)["allowance_request"]
        self.assertEqual(quoted["question_version"], 2)
        self.assertGreater(quoted["journal_capacity"]["reserved_future_records"], 0)
        self.approve(quoted)
        ready = self.control("dispatch", "--phase", "post", "--round", 1, "--agent", "explorer",
                             "--scope", 'Return only {"answer":"fixture"}. No file reads are needed.')
        args = ready["dispatch_decision"]["exact_tool_parameters"]
        self.assertNotIn(str(self.packet), args["message"])
        self.assertNotIn("checked_scope", args["message"])
        self.assertNotIn("Review only", args["message"])
        self.assertEqual(args["agent_type"], "explorer")
        self.assertEqual(self.hook("PreToolUse", {"tool_name": "spawn_agent", "tool_use_id": "execution",
                         "tool_input": args}), {})
        self.hook("PostToolUse", {"tool_name": "spawn_agent", "tool_use_id": "execution", "tool_input": args,
                                  "tool_response": {"task_name": "/root/" + args["task_name"]}})
        child, turn = "execution-child", "execution-turn"
        transcript = self.home / "sessions/rollout-execution-child.jsonl"
        self.emit(transcript, "session_meta", {"id": child, "cwd": str(self.repo), "source": {
            "subagent": {"thread_spawn": {"parent_thread_id": self.session, "depth": 1,
                "agent_role": "explorer", "agent_path": "/root/" + args["task_name"]}}}})
        data = {"agent_id": child, "agent_type": "explorer", "turn_id": turn,
                "agent_transcript_path": str(transcript), "transcript_path": str(transcript)}
        context = self.hook("SubagentStart", data)["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn(str(self.packet), context)
        self.assertNotIn("in checked_scope", context)
        self.emit(transcript, "event_msg", {"type": "task_started", "turn_id": turn})
        self.emit(transcript, "response_item", {"type": "message", "role": "assistant", "phase": "final_answer",
            "content": [{"type": "output_text", "text": '{"answer":"fixture"}'}]})
        self.emit(transcript, "event_msg", {"type": "task_complete", "turn_id": turn})
        self.hook("SubagentStop", data)
        state = budget.read_budget(self.ledger)
        from cp_runtime.g6_review_receipt_v1 import _receipt_path
        pid = state["host_calls"][ref("execution")]
        self.assertEqual(state["terminals"][pid]["outcome"], "UNKNOWN")
        self.assertFalse(_receipt_path(self.ledger, pid).exists())
        status = self.control("allowance-status")
        self.assertEqual(status["allowance_status"]["grants"][0]["usage"]["completed_charged_units"], 4)
        self.assertEqual(status["verification_state"], "UNVERIFIED")

    def test_one_execution_quote_can_cover_exact_counts_across_registered_profiles(self):
        work_ids = []
        for role, profile, count in (("worker", "g6-sol-medium", 22),
                                     ("explorer", "g6-sol-medium", 10),
                                     ("explorer", "g6-luna-low", 80)):
            value = self.control("plan", "--phase", "post", "--packet-dir", self.packet,
                "--agents", role, "--allowed-path", "src", "--review-stage", "task_execution",
                "--model-profile", profile, "--purpose", "Execute fixed public acceptance cases.")
            work_ids.append((value["plans"][value["active_plan_key"]]["work_ids"][role], count))
        args = [part for key, count in work_ids for part in ("--work-count", key + "=" + str(count))]
        request = self.control("allowance-quote", *args)["allowance_request"]
        self.assertEqual(sum(row["dispatches"] for row in request["allocations"]), 112)
        self.assertEqual(sum(row["units"] for row in request["allocations"]), 208)
        self.assertEqual(len(request["allocations"]), 3)
        before = self.ledger.read_bytes()
        self.control("allowance-quote", "--work-count", "G6W_" + "0" * 32 + "=1", ok=False)
        self.assertEqual(self.ledger.read_bytes(), before)

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

    def test_structured_pass_with_outside_scope_unknown_does_not_repeat_same_review(self):
        from cp_runtime.common import read_json
        from cp_runtime.g6_review_receipt_v1 import _receipt_path
        plan = self.plan()
        args = self.dispatch()["dispatch_decision"]["exact_tool_parameters"]
        self.assertEqual(self.hook("PreToolUse", {"tool_name": "spawn_agent",
                         "tool_use_id": "limited-pass", "tool_input": args}), {})
        packet = plan["plans"][plan["active_plan_key"]]["packet_sha256"]
        report = {"status": "pass", "findings": [],
                  "checked_scope": {"paths": ["app.py"], "packet_sha256": packet},
                  "unverified_items": ["Native installation was not part of this code review."],
                  "summary": "Scoped review passed; keep the installation evidence separate."}
        self.child_result(args, "limited-pass", report)
        state = budget.read_budget(self.ledger)
        pid = state["host_calls"][ref("limited-pass")]
        receipt = read_json(_receipt_path(self.ledger, pid), verify=True)
        self.assertEqual(receipt["report_status"], "pass")
        self.assertEqual(receipt["gate_state"], "MISSING_EVIDENCE")
        self.assertEqual(receipt["reason_code"], "REVIEW_PACKET_VERIFIED")
        report_file = self.base / "structured-report.json"
        report_file.write_text(json.dumps(report), encoding="utf-8")
        result = self.control("result", "--phase", "post", "--round", 1, "--reviewer", ROLE,
                              "--status", "pass", "--summary", "Fixture", "--result-file", report_file)
        self.assertEqual(result["results"][ROLE]["verification_state"], "NATIVE_REPORT_VERIFIED")
        self.assertIn("G6_REVIEW_UNCHANGED_ALREADY_COMPLETE", self.dispatch(ok=False))
        self.assertEqual(len(budget.read_budget(self.ledger)["reservations"]), 1)

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

    def test_repeated_recovery_uses_grant_already_recorded_by_native_hook(self):
        self.exhaust()
        self.plan()
        self.approve(self.control("allowance-quote")["allowance_request"])
        before = self.ledger.read_bytes()
        for command in ("allowance-recover", "allowance-status", "allowance-recover"):
            value = self.control(command)
            self.assertNotIn("allowance_request", value)
            self.assertEqual(value["next_action"], "dispatch_with_existing_allowance")
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_recovery_does_not_resume_an_unrelated_work_reservation(self):
        self.unsettled_review(complete=False)
        self.control("plan", "--phase", "post", "--packet-dir", self.packet,
                     "--reviewers", "cp_review_state_concurrency", "--allowed-path", "src",
                     "--purpose", "A separate review work item within the same task.")
        before = self.ledger.read_bytes()
        value = self.control("allowance-status")
        self.assertEqual(value["next_action"], "continue_unaffected_work_or_quote_required_work")
        self.assertEqual(self.ledger.read_bytes(), before)
        self.approve(self.control("allowance-quote")["allowance_request"])
        before = self.ledger.read_bytes()
        for command in ("allowance-recover", "allowance-status"):
            value = self.control(command)
            self.assertEqual(value["next_action"], "dispatch_with_existing_allowance")
            self.assertEqual(value["allowance_status"]["total_usage"]["active_calls"], 1)
        self.assertEqual(self.ledger.read_bytes(), before)

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
