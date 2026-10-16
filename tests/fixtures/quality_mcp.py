"""中文：公开合成 MCP 协议样例；无网络、真实账户或持久写入。
English: Public synthetic MCP protocol fixture; no network, live account or persistent writes.
"""
from __future__ import annotations

import json
import sys

VERSION = "2025-11-25"
ITEMS = [
    {"id": "A1", "name": "Notebook", "category": "stationery", "quantity": 5, "price_cents": 1200},
    {"id": "A2", "name": "Desk lamp", "category": "lighting", "quantity": 2, "price_cents": 4500},
    {"id": "A3", "name": "Chair", "category": "furniture", "quantity": 0, "price_cents": 9000},
    {"id": "A4", "name": "Shelf", "category": "furniture", "quantity": 3, "price_cents": 6200},
]
OUTPUT = {"type": "object", "properties": {"ok": {"type": "boolean"}, "data": {"type": "object"},
    "error": {"type": ["object", "null"]}}, "required": ["ok", "data", "error"], "additionalProperties": False}


def schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


ID = {"type": "string", "minLength": 1, "maxLength": 24}
TOOLS = [
    {"name": "catalog.list", "description": "List owned catalog IDs and names. Read-only. Follow next_cursor until null; limit is 1 or 2. Cursors are bound to category and limit. Empty results are successful.",
     "inputSchema": schema({"category": {"type": "string", "enum": ["all", "stationery", "lighting", "furniture", "empty"]},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 2},
                            "cursor": {"type": "string", "minLength": 1, "maxLength": 64}})},
    {"name": "catalog.read", "description": "Read an owned item's quantity and unit price_cents. Get IDs from catalog.list. Missing and unauthorized IDs share NOT_AUTHORIZED.",
     "inputSchema": schema({"id": ID}, ["id"])},
    {"name": "health.probe", "description": "Read readiness. A synthetic first-call TIMEOUT is retryable once in the same process; never change identity or widen scope.",
     "inputSchema": schema({})},
    {"name": "inventory.summary", "description": "Read a partial cross-source inventory summary. complete=false and failed_sources mean it is not a complete inventory.",
     "inputSchema": schema({})},
    {"name": "reservation.create", "description": "Reserve owned inventory. Requires server-granted writer role. No caller role/tenant argument. Same idempotency_key with identical input returns the existing reservation; changed input conflicts. A denial must not be bypassed.",
     "inputSchema": schema({"id": ID, "quantity": {"type": "integer", "minimum": 1, "maximum": 10},
                            "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 48}},
                           ["id", "quantity", "idempotency_key"])}
]
for tool in TOOLS:
    tool["outputSchema"] = OUTPUT
    tool["annotations"] = {"readOnlyHint": tool["name"] != "reservation.create",
                           "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}


def valid(value, spec):
    kind = spec["type"]
    if kind == "object":
        return (isinstance(value, dict) and set(spec["required"]).issubset(value)
                and not set(value) - set(spec["properties"])
                and all(valid(item, spec["properties"][key]) for key, item in value.items()))
    if kind == "integer":
        return type(value) is int and spec["minimum"] <= value <= spec["maximum"]
    if kind == "string":
        return (isinstance(value, str) and spec.get("minLength", 0) <= len(value) <= spec.get("maxLength", 100)
                and ("enum" not in spec or value in spec["enum"]))
    return False


def result(data=None, code=None, retryable=False, next_action=None):
    structured = {"ok": code is None, "data": data or {}, "error": None if code is None else {
        "code": code, "retryable": retryable, "next_action": next_action or "correct_request_or_stop"}}
    return {"content": [{"type": "text", "text": json.dumps(structured, separators=(",", ":"))}],
            "structuredContent": structured, "isError": code is not None}


class Server:
    def __init__(self, *, writer_fixture=False):
        # 中文：只有单元夹具构造器可选择写角色；协议和命令行没有提权字段。
        # English: Only unit-fixture construction can select a writer; the protocol and CLI cannot elevate.
        self.writer = writer_fixture
        self.items = {row["id"]: dict(row) for row in ITEMS}
        self.reservations = {}
        self.probes = 0
        self.initialized = False

    def call(self, name, arguments):
        tool = next((row for row in TOOLS if row["name"] == name), None)
        if tool is None:
            return result(code="UNKNOWN_TOOL")
        if not valid(arguments, tool["inputSchema"]):
            return result(code="INVALID_ARGUMENT")
        if name == "catalog.list":
            category, limit = arguments.get("category", "all"), arguments.get("limit", 2)
            rows = [row for row in self.items.values() if category == "all" or row["category"] == category]
            offset = 0
            cursor = arguments.get("cursor")
            if cursor is not None:
                parts = cursor.split(":")
                if len(parts) != 3 or parts[:2] != [category, str(limit)] or not parts[2].isdigit():
                    return result(code="INVALID_CURSOR")
                offset = int(parts[2])
                if offset <= 0 or offset >= len(rows) or offset % limit:
                    return result(code="INVALID_CURSOR")
            page = rows[offset:offset + limit]
            next_cursor = f"{category}:{limit}:{offset + limit}" if offset + limit < len(rows) else None
            return result({"items": [{"id": row["id"], "name": row["name"]} for row in page],
                           "next_cursor": next_cursor, "truncated": next_cursor is not None})
        if name == "catalog.read":
            row = self.items.get(arguments["id"])
            return result(dict(row)) if row else result(code="NOT_AUTHORIZED", next_action="request_owner_access")
        if name == "health.probe":
            self.probes += 1
            return (result(code="TIMEOUT", retryable=True, next_action="retry_once_in_same_process")
                    if self.probes == 1 else result({"status": "READY"}))
        if name == "inventory.summary":
            return result({"items": [{"source": "east", "quantity": 7}], "complete": False,
                           "failed_sources": ["west"]}, code="PARTIAL_RESULT", next_action="report_partial_coverage")
        if not self.writer or arguments["id"] not in self.items:
            return result(code="NOT_AUTHORIZED", next_action="request_owner_access")
        key = arguments["idempotency_key"]
        payload = {"id": arguments["id"], "quantity": arguments["quantity"]}
        if key in self.reservations:
            previous = self.reservations[key]
            return (result(previous["result"]) if previous["input"] == payload
                    else result(code="IDEMPOTENCY_CONFLICT", next_action="read_existing_operation"))
        item = self.items[arguments["id"]]
        if item["quantity"] < arguments["quantity"]:
            return result(code="INSUFFICIENT_STOCK", next_action="choose_available_quantity")
        item["quantity"] -= arguments["quantity"]
        created = {"reservation_id": "R" + str(len(self.reservations) + 1), **payload}
        self.reservations[key] = {"input": payload, "result": created}
        return result(created)

    def handle(self, message):
        if (not isinstance(message, dict) or message.get("jsonrpc") != "2.0"
                or not isinstance(message.get("method"), str)):
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
        if "id" not in message:
            return None
        method, params = message["method"], message.get("params", {})
        response = {"jsonrpc": "2.0", "id": message["id"]}
        if method == "initialize":
            self.initialized = True
            response["result"] = {"protocolVersion": VERSION, "capabilities": {"tools": {"listChanged": False}},
                                  "serverInfo": {"name": "public-quality-fixture", "version": "1.0"}}
        elif not self.initialized:
            response["error"] = {"code": -32600, "message": "Initialize this fixture first"}
        elif method == "tools/list":
            response["result"] = {"tools": TOOLS}
        elif method == "tools/call":
            if (not isinstance(params, dict) or set(params) - {"name", "arguments"}
                    or not isinstance(params.get("name"), str)
                    or not any(tool["name"] == params["name"] for tool in TOOLS)):
                response["error"] = {"code": -32602, "message": "Invalid params"}
            else:
                response["result"] = self.call(params.get("name"), params.get("arguments", {}))
        else:
            response["error"] = {"code": -32601, "message": "Method not found"}
        return response


def main():
    server = Server()
    for _ in range(100):
        raw = sys.stdin.buffer.readline(16_385)
        if not raw:
            return 0
        if len(raw) > 16_384 or not raw.endswith(b"\n"):
            return 2
        try:
            response = server.handle(json.loads(raw))
        except (ValueError, UnicodeError, RecursionError):
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
