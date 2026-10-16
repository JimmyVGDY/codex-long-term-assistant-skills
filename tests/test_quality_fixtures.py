"""中文：核验样例标准、受控协议、分页与写权限；不冒充模型行为验收。
English: Verify fixture oracles, bounded protocol, pagination and write access; not model acceptance.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load("quality_builder", "scripts/quality-fixtures.py")
mcp = load("quality_mcp", "tests/fixtures/quality_mcp.py")


class QualityFixtureTests(unittest.TestCase):
    def test_cases_are_bounded_and_oracles_are_outside_executor_files(self):
        suite = builder.build_suite()
        self.assertEqual(len(suite["cases"]), 12)
        for case in suite["cases"]:
            self.assertNotIn("answers.json", case["files"])
            self.assertNotIn("input.json", case["files"])
            self.assertNotIn("expected", case["task"])
            self.assertTrue(all(check["path"] in case["artifacts"] for check in case["checks"]))
        for case in suite["cases"][:3]:
            expected = case["checks"][0]["expected"]
            self.assertEqual(sum(not row["evidence"] for row in expected["doc-b"].values()), 2)
            for question in expected["doc-a"].values():
                for value in question["facts"].values():
                    self.assertIn(value, case["files"]["doc-a.md"])

    def test_pagination_and_composition_match_frozen_oracles(self):
        server = mcp.Server()
        first = server.call("catalog.list", {"limit": 2})["structuredContent"]["data"]
        second = server.call("catalog.list", {"limit": 2, "cursor": first["next_cursor"]})["structuredContent"]["data"]
        ids = [row["id"] for row in first["items"] + second["items"]]
        self.assertEqual(ids, ["A1", "A2", "A3", "A4"])
        self.assertIsNone(second["next_cursor"])
        self.assertFalse(second["truncated"])
        furniture = server.call("catalog.list", {"category": "furniture"})["structuredContent"]["data"]["items"]
        details = [server.call("catalog.read", {"id": row["id"]})["structuredContent"]["data"] for row in furniture]
        self.assertEqual(sum(row["quantity"] * row["price_cents"] for row in details), 18600)

    def test_invalid_empty_foreign_and_cross_query_cursor(self):
        server = mcp.Server()
        self.assertEqual(server.call("catalog.list", {"category": "empty"})["structuredContent"]["data"]["items"], [])
        for args in ({"limit": 0}, {"limit": True}, {"tenant": "another"}, {"role": "writer"}):
            self.assertEqual(server.call("catalog.list", args)["structuredContent"]["error"]["code"], "INVALID_ARGUMENT")
        cursor = server.call("catalog.list", {"limit": 2})["structuredContent"]["data"]["next_cursor"]
        self.assertEqual(server.call("catalog.list", {"category": "furniture", "cursor": cursor})
                         ["structuredContent"]["error"]["code"], "INVALID_CURSOR")
        for item in ("B1", "NONEXISTENT"):
            self.assertEqual(server.call("catalog.read", {"id": item})["structuredContent"]["error"]["code"], "NOT_AUTHORIZED")
        denied = server.call("reservation.create", {"id": "A1", "quantity": 1, "idempotency_key": "one"})
        self.assertEqual(denied["structuredContent"]["error"]["code"], "NOT_AUTHORIZED")
        self.assertEqual(server.items["A1"]["quantity"], 5)

    def test_writer_fixture_idempotency_conflict_and_stock(self):
        server = mcp.Server(writer_fixture=True)
        args = {"id": "A1", "quantity": 2, "idempotency_key": "one"}
        first = server.call("reservation.create", args)
        self.assertEqual(first, server.call("reservation.create", args))
        self.assertEqual(server.items["A1"]["quantity"], 3)
        conflict = server.call("reservation.create", {**args, "quantity": 1})
        self.assertEqual(conflict["structuredContent"]["error"]["code"], "IDEMPOTENCY_CONFLICT")
        stock = server.call("reservation.create", {**args, "quantity": 8, "idempotency_key": "two"})
        self.assertEqual(stock["structuredContent"]["error"]["code"], "INSUFFICIENT_STOCK")
        self.assertEqual(len(server.reservations), 1)

    def test_transient_error_and_partial_result_remain_distinct(self):
        server = mcp.Server()
        timeout = server.call("health.probe", {})
        self.assertTrue(timeout["isError"])
        self.assertTrue(timeout["structuredContent"]["error"]["retryable"])
        self.assertEqual(server.call("health.probe", {})["structuredContent"]["data"]["status"], "READY")
        partial = server.call("inventory.summary", {})
        self.assertTrue(partial["isError"])
        self.assertFalse(partial["structuredContent"]["data"]["complete"])
        self.assertEqual(partial["structuredContent"]["data"]["failed_sources"], ["west"])
        for result in (timeout, partial):
            self.assertEqual(set(result["structuredContent"]), {"ok", "data", "error"})
            self.assertEqual(json.loads(result["content"][0]["text"]), result["structuredContent"])

    def test_bounded_stdio_discovery_and_protocol_errors(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": mcp.VERSION}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "unknown", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "catalog.list", "arguments": {"limit": 0}}},
        ]
        run = subprocess.run([sys.executable, "-B", str(ROOT / "tests/fixtures/quality_mcp.py")],
            input="\n".join(json.dumps(row) for row in messages) + "\n", text=True, capture_output=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)
        outputs = [json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(len(outputs), 4)
        self.assertEqual(len(outputs[1]["result"]["tools"]), 5)
        self.assertEqual(outputs[2]["error"]["code"], -32602)
        self.assertTrue(outputs[3]["result"]["isError"])
        oversized = subprocess.run([sys.executable, "-B", str(ROOT / "tests/fixtures/quality_mcp.py")],
            input="x" * 16_385 + "\n", text=True, capture_output=True, timeout=5)
        self.assertEqual(oversized.returncode, 2)
        self.assertEqual(oversized.stdout, "")


if __name__ == "__main__":
    unittest.main()
