"""中文：原生多进程竞争与写入中止验证，夹具不调用模型。

English: OS process races and interrupted atomic writes; no model requests.
"""
from __future__ import annotations

import multiprocessing
import tempfile
import unittest
from unittest.mock import patch

import test_routing_v4_budget as fixtures
from cp_runtime import budget_v4
from cp_runtime.routing_contract import RoutingError


def reserve_in_process(fixture, selected, call, start, output):
    start.wait(10)
    try:
        output.put(fixture.reserve(selected, call)["state"])
    except RoutingError as exc:
        output.put(str(exc))


def interrupted_write(fixture, selected, ready, wait):
    def block_replace(*args, **kwargs):
        ready.set()
        wait.wait(20)
        raise OSError("synthetic interrupted replacement")
    with patch("cp_runtime.common.os.replace", side_effect=block_replace):
        fixture.reserve(selected)


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = fixtures.BudgetFixture(self.temp.name)
        self.fixture.init()
        self.selected = self.fixture.prepare()
        self.context = multiprocessing.get_context("spawn")
        self.children = []

    def tearDown(self):
        for child in self.children:
            if child.is_alive():
                child.terminate()
            child.join(timeout=5)
            child.close()
        self.temp.cleanup()

    def test_two_processes_cannot_consume_one_permit_twice(self):
        start, output = self.context.Event(), self.context.Queue()
        for call in ("process-one", "process-two"):
            child = self.context.Process(target=reserve_in_process,
                        args=(self.fixture, self.selected, call, start, output))
            self.children.append(child)
            child.start()
        start.set()
        results = [output.get(timeout=15), output.get(timeout=15)]
        self.assertCountEqual(["RESERVED", "PERMIT_ALREADY_CONSUMED"], results)
        state = budget_v4.read_budget(self.fixture.path)
        self.assertEqual(1, len(state["reservations"]))
        self.assertEqual(self.selected["reserve_units"], state["_usage_cache"]["resources"]["units"])
        output.close(); output.join_thread()

    def test_killed_writer_releases_os_lock_without_half_reservation(self):
        before = self.fixture.path.read_bytes()
        ready, wait = self.context.Event(), self.context.Event()
        child = self.context.Process(target=interrupted_write,
                    args=(self.fixture, self.selected, ready, wait))
        self.children.append(child)
        child.start()
        self.assertTrue(ready.wait(15))
        child.terminate(); child.join(timeout=5)
        self.assertFalse(child.is_alive())
        self.assertEqual(before, self.fixture.path.read_bytes())
        self.assertFalse(budget_v4.read_budget(self.fixture.path)["reservations"])
        self.assertEqual("RESERVED", self.fixture.reserve(self.selected)["state"])


if __name__ == "__main__":
    unittest.main()
