"""中文：onboarding/1 询问、CAS、租约、取消和故障恢复。 English: onboarding/1 offer, CAS, lease, cancellation, and recovery."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
from cp_runtime import onboarding as onboarding_module
from cp_runtime.capability_store import CapabilityError
from cp_runtime.onboarding import OnboardingStore

ROOT = Path(__file__).resolve().parents[2]


class Clock:
    def __init__(self):
        self.value = datetime(2026, 9, 10, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        fixtures.CapabilityStoreTests.setUp(self)
        self.clock = Clock()
        self.onboarding = OnboardingStore(self.profile, self.repo, clock=self.clock)

    tearDown = fixtures.CapabilityStoreTests.tearDown

    def offer(self, ttl=120):
        return self.onboarding.create_offer(["."], "test-owner", ttl)

    def accept(self, offer=None):
        offer = offer or self.offer()
        return self.onboarding.respond("ACCEPTED", offer["nonce"], offer["revision"],
                                       "MODEL_INTERPRETED_USER_REPLY", "message-ref-1")

    def test_unseen_and_repeated_offer_are_no_write_then_single_persisted_fact(self):
        status = self.onboarding.offer_status()
        self.assertEqual(("UNSEEN", False), (status["state"], status["persisted"]))
        self.assertFalse(self.onboarding.offer_path.exists())
        first = self.offer()
        second = self.offer()
        self.assertEqual(first, second)
        self.assertEqual(("OFFERED", 0, "OFFER_PERSISTED"),
                         (first["state"], first["revision"], first["persistence_status"]))

    def test_offer_owner_and_scope_are_single_and_unanswered_offer_cannot_queue(self):
        self.offer()
        with self.assertRaisesRegex(CapabilityError, "ONBOARDING_OWNER_CONFLICT"):
            self.onboarding.create_offer(["runtime"], "other-owner", 120)
        with self.assertRaisesRegex(CapabilityError, "ONBOARDING_NOT_ACCEPTED"):
            self.onboarding.queue_scan()

    def test_expiry_equality_rejects_and_renewal_fences_old_nonce(self):
        offered = self.offer(60)
        self.clock.advance(60)
        with self.assertRaisesRegex(CapabilityError, "ONBOARDING_EXPIRED"):
            self.onboarding.respond("ACCEPTED", offered["nonce"], 0,
                                     "HOST_STRUCTURED_REPLY", "host-ref")
        renewed = self.onboarding.renew_offer(0, offered["nonce"], 60)
        self.assertNotEqual((offered["offer_ref"], offered["nonce"]),
                            (renewed["offer_ref"], renewed["nonce"]))
        with self.assertRaisesRegex(CapabilityError, "ONBOARDING_NONCE_MISMATCH"):
            self.onboarding.respond("ACCEPTED", offered["nonce"], 0,
                                     "HOST_STRUCTURED_REPLY", "host-ref")

    def test_clock_rollback_never_accepts(self):
        offered = self.offer()
        self.clock.advance(-1)
        with self.assertRaisesRegex(CapabilityError, "CLOCK_ROLLBACK"):
            self.onboarding.respond("ACCEPTED", offered["nonce"], 0,
                                     "HOST_STRUCTURED_REPLY", "host-ref")

    def test_wrong_nonce_never_accepts_and_does_not_change_offer(self):
        offered = self.offer()
        with self.assertRaisesRegex(CapabilityError, "ONBOARDING_NONCE_MISMATCH"):
            self.onboarding.respond("ACCEPTED", "0" * 48, 0,
                                     "HOST_STRUCTURED_REPLY", "host-ref")
        self.assertEqual(offered, self.onboarding.offer_status())

    def test_same_choice_is_idempotent_and_different_reference_does_not_replace_fact(self):
        offered = self.offer()
        first = self.accept(offered)
        same = self.onboarding.respond("ACCEPTED", offered["nonce"], 0,
                                       "HOST_STRUCTURED_REPLY", "different-ref")
        self.assertEqual(first, same)
        self.assertEqual("message-ref-1", same["response"]["reference"])
        self.assertNotIn("user text", json.dumps(same).lower())

    def test_opposite_concurrent_choices_have_one_cas_winner(self):
        offered = self.offer()

        def choose(choice):
            try:
                return ("OK", self.onboarding.respond(choice, offered["nonce"], 0,
                        "MODEL_INTERPRETED_USER_REPLY", "ref-" + choice)["state"])
            except CapabilityError as exc:
                return ("ERROR", str(exc))

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(choose, ("ACCEPTED", "DECLINED")))
        self.assertEqual(1, sum(result[0] == "OK" for result in results))
        self.assertEqual(1, sum("ONBOARDING_REVISION_CONFLICT" in result[1] for result in results if result[0] == "ERROR"))

    def test_only_persisted_acceptance_queues_and_decline_cancels_running_scan(self):
        offered = self.offer()
        self.accept(offered)
        queued = self.onboarding.queue_scan()
        claimed = self.onboarding.claim_scan("scan-worker", 30)
        scan = claimed["scan"]
        declined = self.onboarding.respond("DECLINED", offered["nonce"], 1,
                                            "MODEL_INTERPRETED_USER_REPLY", "cancel-ref")
        self.assertEqual("DECLINED", declined["state"])
        self.assertEqual("CANCELLED", self.onboarding.scan_status()["state"])
        with self.assertRaisesRegex(CapabilityError, "ONBOARDING_SCAN_NOT_RUNNING"):
            self.onboarding.checkpoint(claimed["lease_token"], scan["lease"]["generation"],
                                       scan["cancel_epoch"], "late", {"complete": True})

    def test_decline_retry_compensates_scan_cancel_write_failure_and_fences_worker(self):
        offered = self.offer()
        self.accept(offered)
        self.onboarding.queue_scan()
        claimed = self.onboarding.claim_scan("scan-worker", 30)
        scan = claimed["scan"]
        original = onboarding_module._write
        failed = {"value": False}

        def fail_cancel_once(path, value, limit):
            if path == self.onboarding.scan_path and value.get("state") == "CANCELLED" and not failed["value"]:
                failed["value"] = True
                raise CapabilityError("GATE_COMMIT_UNCERTAIN")
            return original(path, value, limit)

        with patch.object(onboarding_module, "_write", side_effect=fail_cancel_once):
            with self.assertRaisesRegex(CapabilityError, "GATE_COMMIT_UNCERTAIN"):
                self.onboarding.respond("DECLINED", offered["nonce"], 1,
                                        "MODEL_INTERPRETED_USER_REPLY", "decline-ref")
        self.assertEqual("DECLINED", self.onboarding.offer_status()["state"])
        self.assertEqual("RUNNING", self.onboarding.scan_status()["state"])
        with self.assertRaisesRegex(CapabilityError, "ONBOARDING_NOT_ACCEPTED"):
            self.onboarding.finish_scan(claimed["lease_token"], scan["lease"]["generation"],
                                        scan["cancel_epoch"], "COMPLETED", {"complete": True})
        replay = self.onboarding.respond("DECLINED", offered["nonce"], 1,
                                         "MODEL_INTERPRETED_USER_REPLY", "decline-ref")
        self.assertEqual("DECLINED", replay["state"])
        self.assertEqual("CANCELLED", self.onboarding.scan_status()["state"])

    def test_lease_takeover_fences_old_worker_and_resumes_cursor(self):
        self.accept()
        self.onboarding.queue_scan()
        first = self.onboarding.claim_scan("worker-1", 5)
        state = first["scan"]
        self.onboarding.checkpoint(first["lease_token"], state["lease"]["generation"],
                                   state["cancel_epoch"], "cursor-1", {"complete": False}, lease_seconds=5)
        self.clock.advance(5)
        second = self.onboarding.claim_scan("worker-2", 30)
        self.assertEqual("cursor-1", second["scan"]["cursor"])
        with self.assertRaisesRegex(CapabilityError, "LEASE_FENCED"):
            self.onboarding.checkpoint(first["lease_token"], state["lease"]["generation"],
                                       state["cancel_epoch"], "old", {"complete": False})

    def test_projection_commits_before_cursor_and_replay_is_idempotent(self):
        self.accept(); self.onboarding.queue_scan()
        claimed = self.onboarding.claim_scan("worker", 30)
        state = claimed["scan"]
        projections = set()

        def commit():
            projections.add("stable-locator")
            return "projection-ok"

        original = onboarding_module._write
        failed = {"value": False}

        def fail_once(path, value, limit):
            if path == self.onboarding.scan_path and value.get("cursor") == "cursor-1" and not failed["value"]:
                failed["value"] = True
                raise CapabilityError("GATE_COMMIT_UNCERTAIN")
            return original(path, value, limit)

        with patch.object(onboarding_module, "_write", side_effect=fail_once):
            with self.assertRaisesRegex(CapabilityError, "GATE_COMMIT_UNCERTAIN"):
                self.onboarding.checkpoint(claimed["lease_token"], state["lease"]["generation"],
                                           state["cancel_epoch"], "cursor-1", {"complete": False}, commit)
        self.assertIsNone(self.onboarding.scan_status()["cursor"])
        result = self.onboarding.checkpoint(claimed["lease_token"], state["lease"]["generation"],
                                            state["cancel_epoch"], "cursor-1", {"complete": False}, commit)
        self.assertEqual(("cursor-1", {"stable-locator"}, "projection-ok"),
                         (result["scan"]["cursor"], projections, result["projection"]))

    def test_completed_requires_complete_coverage_and_terminal_is_idempotent(self):
        self.accept(); self.onboarding.queue_scan()
        claimed = self.onboarding.claim_scan("worker", 30)
        state = claimed["scan"]
        with self.assertRaisesRegex(CapabilityError, "ONBOARDING_SCAN_INCOMPLETE"):
            self.onboarding.finish_scan(claimed["lease_token"], state["lease"]["generation"],
                                        state["cancel_epoch"], "COMPLETED", {"complete": False})
        finished = self.onboarding.finish_scan(claimed["lease_token"], state["lease"]["generation"],
                                               state["cancel_epoch"], "COMPLETED", {"complete": True})
        same = self.onboarding.finish_scan("irrelevant", 999, 999, "COMPLETED", {"complete": True})
        self.assertEqual(finished, same)

    def test_response_persistence_failure_never_queues_full_scan(self):
        offered = self.offer()
        original = onboarding_module._write

        def deny_response(path, value, limit):
            if path == self.onboarding.offer_path and value.get("state") == "ACCEPTED":
                raise OSError("read-only")
            return original(path, value, limit)

        with patch.object(onboarding_module, "_write", side_effect=deny_response):
            with self.assertRaises(OSError):
                self.accept(offered)
        self.assertEqual("OFFERED", self.onboarding.offer_status()["state"])
        with self.assertRaisesRegex(CapabilityError, "ONBOARDING_NOT_ACCEPTED"):
            self.onboarding.queue_scan()

    def test_new_onboarding_state_never_changes_legacy_profile_state_or_index(self):
        state_path = self.profile.with_name("project-state.json")
        before = (self.profile.read_bytes(), state_path.read_bytes())
        offered = self.offer()
        self.accept(offered)
        self.onboarding.queue_scan()
        self.assertEqual(before, (self.profile.read_bytes(), state_path.read_bytes()))
        self.assertFalse(self.store.current.exists())

    def test_cli_offer_and_structured_response_readback(self):
        def invoke(*args):
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "cp-runtime.py"), *args],
                                    cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8")
            return json.loads(result.stdout)

        offered = invoke("onboarding-offer", "--profile", str(self.profile), "--repo-path", str(self.repo),
                         "--owner", "cli-owner", "--ttl-seconds", "120")
        accepted = invoke("onboarding-respond", "--profile", str(self.profile), "--repo-path", str(self.repo),
                          "--choice", "ACCEPTED", "--nonce", offered["nonce"], "--expected-revision", "0",
                          "--source", "HOST_STRUCTURED_REPLY", "--response-ref", "host-response-1")
        self.assertEqual(("ACCEPTED", "HOST_STRUCTURED_REPLY", "ACCEPTED_PERSISTED"),
                         (accepted["state"], accepted["response"]["source"], accepted["persistence_status"]))


if __name__ == "__main__":
    unittest.main()
