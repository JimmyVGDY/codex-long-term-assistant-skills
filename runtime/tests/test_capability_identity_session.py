"""中文：有界身份检查优化必须保留资料变更、仓库变更及线程隔离检查。

English: Bounded identity checks must retain metadata drift, repository drift, and thread isolation checks.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
from cp_runtime import capability_store as module
from cp_runtime.capability_store import CapabilityError


class CapabilityIdentitySessionTests(unittest.TestCase):
    setUp = fixtures.CapabilityStoreTests.setUp
    tearDown = fixtures.CapabilityStoreTests.tearDown

    def test_bounded_scope_checks_binding_on_both_edges_and_does_not_cache_next_operation(self):
        with patch.object(module, "validate_binding", wraps=module.validate_binding) as binding:
            with self.store.bounded_identity_session():
                for _ in range(5):
                    self.store._guard()
            self.assertEqual(2, binding.call_count)
            self.store._guard()
            self.assertEqual(3, binding.call_count)

    def test_profile_change_is_rejected_inside_scope_even_when_json_semantics_match(self):
        original = self.profile.read_bytes()
        try:
            with self.assertRaisesRegex(CapabilityError, "IDENTITY_CHANGED"):
                with self.store.bounded_identity_session():
                    self.profile.write_bytes(original + b"\n")
                    self.store._guard()
        finally:
            self.profile.write_bytes(original)
        self.store._guard()

    def test_git_remote_change_is_rejected_before_scope_returns(self):
        returned = False
        with self.assertRaisesRegex(CapabilityError, "IDENTITY_CHANGED"):
            with self.store.bounded_identity_session():
                fixtures.git(self.repo, "config", "remote.origin.url", "https://example.invalid/other")
            returned = True
        self.assertFalse(returned)
        with self.assertRaisesRegex(CapabilityError, "IDENTITY_CHANGED"):
            self.store._guard()

    def test_another_thread_cannot_borrow_in_progress_identity_checks(self):
        with self.store.bounded_identity_session():
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.store._guard)
                with self.assertRaisesRegex(CapabilityError, "IDENTITY_CHANGED"):
                    future.result(timeout=5)


if __name__ == "__main__":
    unittest.main()
