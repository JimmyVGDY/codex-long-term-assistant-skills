"""中文：复审工作与追加额度的纯契约；不从调用方声明生成用户权限。

English: Pure review-work and allowance contracts; caller labels never grant authority.
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Mapping

from .common import parse_iso
from .g6_flexible_policy import PROFILES, profile_spec
from .routing_contract import exact, fail, integer, ref, role_for, sha

JOURNAL_SCHEMA = "g6-budget-journal/2"
EVENT_TYPES = {"REVIEW_WORK_REGISTERED", "ALLOWANCE_REQUESTED", "ALLOWANCE_GRANTED",
               "ALLOWANCE_REVOKED", "REVIEW_CALL_BOUND", "REVIEW_WORK_CLOSED"}
CALL_FIELDS = {"call_id", "work_id", "packet_dir", "packet_sha256", "baseline_sha256",
               "body_sha256", "task_name", "scope_paths"}
WORK_FIELDS = {"work_id", "boundary_id", "phase", "agent_type", "profile_id",
               "scope_paths", "purpose", "required", "base_funded"}
REQUEST_FIELDS = {"request_id", "allocations", "requested_at", "scope_ref", "question_version"}
ALLOCATION_FIELDS = {"work_id", "dispatches", "attempts", "units"}
AUTH_FIELDS = {"source", "session_ref", "turn_ref", "message_ref", "record_ref",
               "transcript_path", "transcript_path_ref", "transcript_file_ref",
               "header_ref", "start", "end", "authorized_at"}
PHASES = {"pre_review", "post_review", "repair_review"}
MAX_WORK = 64
MAX_REQUESTS = 64


def scope_paths(values: Any) -> list[str]:
    if not isinstance(values, list) or not values or len(values) > 256:
        fail("G6_ALLOWANCE_SCOPE_PATHS")
    for value in values:
        if (not isinstance(value, str) or not value or len(value) > 512 or "\\" in value
                or ":" in value or "\x00" in value or value.startswith("/")
                or any(part in {"", ".", "..", ".git"} for part in value.split("/"))):
            fail("G6_ALLOWANCE_SCOPE_PATH")
    if values != sorted(set(values)):
        fail("G6_ALLOWANCE_SCOPE_ORDER")
    return values


def within_scope(paths: list[str], allowed: list[str]) -> bool:
    scope_paths(allowed)
    scope_paths(paths)
    return all(any(PurePosixPath(path) == PurePosixPath(base)
                   or PurePosixPath(base) in PurePosixPath(path).parents
                   for base in allowed) for path in paths)


def work_identity(value: Mapping[str, Any]) -> str:
    return "G6W_" + ref({key: value[key] for key in
                        ("boundary_id", "phase", "agent_type", "profile_id", "scope_paths", "purpose")})[7:39]


def validate_work(value: Mapping[str, Any]) -> dict[str, Any]:
    item = exact(dict(value), WORK_FIELDS, "G6_REVIEW_WORK_FIELDS")
    if (not isinstance(item["boundary_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", item["boundary_id"])
            or item["phase"] not in PHASES or role_for(item["agent_type"]) != "reviewer"
            or item["profile_id"] not in PROFILES
            or not isinstance(item["purpose"], str) or not 1 <= len(item["purpose"]) <= 1000
            or any(ord(char) < 32 for char in item["purpose"])
            or type(item["required"]) is not bool or type(item["base_funded"]) is not bool):
        fail("G6_REVIEW_WORK_SCOPE")
    scope_paths(item["scope_paths"])
    if item["work_id"] != work_identity(item):
        fail("G6_REVIEW_WORK_IDENTITY")
    return item


def validate_request(value: Mapping[str, Any], works: Mapping[str, Any]) -> dict[str, Any]:
    item = exact(dict(value), REQUEST_FIELDS, "G6_ALLOWANCE_REQUEST_FIELDS")
    if type(item["question_version"]) is not int or item["question_version"] != 1:
        fail("G6_ALLOWANCE_QUESTION_VERSION")
    if not isinstance(item["request_id"], str) or not re.fullmatch(r"G6Q_[0-9a-f]{32}", item["request_id"]):
        fail("G6_ALLOWANCE_REQUEST_ID")
    parse_iso(item["requested_at"])
    rows = item["allocations"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 3:
        fail("G6_ALLOWANCE_ALLOCATION_COUNT")
    seen = set()
    for raw in rows:
        row = exact(raw, ALLOCATION_FIELDS, "G6_ALLOWANCE_ALLOCATION_FIELDS")
        work_id = row["work_id"]
        if work_id not in works or work_id in seen:
            fail("G6_ALLOWANCE_WORK_UNKNOWN_OR_DUPLICATE")
        seen.add(work_id)
        integer(row["dispatches"], "G6_ALLOWANCE_DISPATCHES", minimum=1, maximum=8)
        integer(row["attempts"], "G6_ALLOWANCE_ATTEMPTS", minimum=row["dispatches"],
                maximum=row["dispatches"] * 3)
        integer(row["units"], "G6_ALLOWANCE_UNITS", minimum=1, maximum=128)
        if row["units"] != profile_spec(works[work_id]["profile_id"])["planning_units"] * row["dispatches"]:
            fail("G6_ALLOWANCE_UNITS")
    if item["scope_ref"] != ref([works[row["work_id"]] for row in rows]):
        fail("G6_ALLOWANCE_SCOPE_CHANGED")
    return item


def validate_authorization(value: Mapping[str, Any], root: Mapping[str, Any], request: Mapping[str, Any]) -> None:
    item = exact(dict(value), AUTH_FIELDS, "G6_ALLOWANCE_AUTH_FIELDS")
    if item["source"] != "native-user-response" or item["session_ref"] != root["host_session_ref"]:
        fail("G6_ALLOWANCE_AUTH_IDENTITY")
    for key in ("session_ref", "message_ref", "record_ref", "transcript_path_ref",
                "transcript_file_ref", "header_ref"):
        sha(item[key])
    if item["turn_ref"] is not None:
        sha(item["turn_ref"])
    if not isinstance(item["transcript_path"], str) or not item["transcript_path"]:
        fail("G6_ALLOWANCE_AUTH_SOURCE")
    integer(item["start"], "G6_ALLOWANCE_AUTH_OFFSET", maximum=2**63 - 1)
    integer(item["end"], "G6_ALLOWANCE_AUTH_OFFSET", minimum=item["start"] + 1,
            maximum=item["start"] + 131_072)
    if parse_iso(item["authorized_at"]) < parse_iso(request["requested_at"]):
        fail("G6_ALLOWANCE_AUTH_PREDATES_REQUEST")


def funding_id(request_id: str, work_id: str) -> str:
    return "G6F_" + ref([request_id, work_id])[7:39]


def apply_event(state: dict[str, Any], kind: str, data: Mapping[str, Any]) -> None:
    """中文：在根流水重放中验证新事件；用户来源的实际读回由原生适配器负责。

    English: Validate extensions during root replay; the native adapter rereads authority.
    """
    works, requests = state["review_work"], state["allowance_requests"]
    if kind == "REVIEW_WORK_REGISTERED":
        work = validate_work(data)
        if work["work_id"] in works or len(works) >= MAX_WORK:
            fail("G6_REVIEW_WORK_CONFLICT")
        works[work["work_id"]] = work
    elif kind == "ALLOWANCE_REQUESTED":
        request = validate_request(data, works)
        if request["request_id"] in requests or len(requests) >= MAX_REQUESTS:
            fail("G6_ALLOWANCE_REQUEST_CONFLICT")
        requests[request["request_id"]] = request
    elif kind == "ALLOWANCE_GRANTED":
        exact(dict(data), {"request_id", "authorization"}, "G6_ALLOWANCE_GRANT_FIELDS")
        request = requests.get(data["request_id"])
        if request is None or data["request_id"] in state["allowance_grants"] or data["request_id"] in state["allowance_revoked"]:
            fail("G6_ALLOWANCE_GRANT_CONFLICT")
        if any(row["work_id"] in state["closed_review_work"] for row in request["allocations"]):
            fail("G6_ALLOWANCE_WORK_CLOSED")
        validate_authorization(data["authorization"], state["root"], request)
        source = data["authorization"]["message_ref"]
        if any(grant["authorization"]["message_ref"] == source for grant in state["allowance_grants"].values()):
            fail("G6_ALLOWANCE_AUTH_REUSED")
        state["allowance_grants"][data["request_id"]] = dict(data)
    elif kind == "ALLOWANCE_REVOKED":
        exact(dict(data), {"request_id", "authorization"}, "G6_ALLOWANCE_REVOKE_FIELDS")
        request = requests.get(data["request_id"])
        if request is None or data["request_id"] in state["allowance_revoked"]:
            fail("G6_ALLOWANCE_REVOKE_CONFLICT")
        validate_authorization(data["authorization"], state["root"], request)
        state["allowance_revoked"][data["request_id"]] = dict(data)
    elif kind == "REVIEW_CALL_BOUND":
        exact(dict(data), CALL_FIELDS, "G6_REVIEW_CALL_FIELDS")
        work = works.get(data["work_id"])
        if work is None or data["work_id"] in state["closed_review_work"]:
            fail("G6_REVIEW_CALL_WORK")
        if (data["call_id"] != "G6C_" + ref({key: data[key] for key in CALL_FIELDS - {"call_id"}})[7:39]
                or data["call_id"] in state["review_calls"]
                or not isinstance(data["task_name"], str)
                or not re.fullmatch(r"[a-z0-9_]{1,64}", data["task_name"])
                or not isinstance(data["packet_dir"], str) or not data["packet_dir"]):
            fail("G6_REVIEW_CALL_IDENTITY")
        for key in ("packet_sha256", "baseline_sha256", "body_sha256"):
            if not isinstance(data[key], str) or not re.fullmatch(r"[0-9a-f]{64}", data[key]):
                fail("G6_REVIEW_CALL_DIGEST")
        if not within_scope(data["scope_paths"], work["scope_paths"]):
            fail("G6_REVIEW_SCOPE_EXPANDED")
        state["review_calls"][data["call_id"]] = dict(data)
    elif kind == "REVIEW_WORK_CLOSED":
        exact(dict(data), {"work_id"}, "G6_REVIEW_CLOSE_FIELDS")
        if data["work_id"] not in works or data["work_id"] in state["closed_review_work"]:
            fail("G6_REVIEW_CLOSE_CONFLICT")
        state["closed_review_work"][data["work_id"]] = True
    else:
        fail("G6_ALLOWANCE_EVENT_UNKNOWN")


def buckets(state: Mapping[str, Any], *, include_revoked: bool = False) -> dict[str, dict[str, Any]]:
    result = {}
    for request_id in state.get("allowance_grants", {}):
        if request_id in state.get("allowance_revoked", {}) and not include_revoked:
            continue
        request = state["allowance_requests"][request_id]
        for row in request["allocations"]:
            if row["work_id"] in state.get("closed_review_work", {}) and not include_revoked:
                continue
            result[funding_id(request_id, row["work_id"])] = {
                **row, "request_id": request_id,
                "authorization_ref": ref(state["allowance_grants"][request_id]),
                "profile_id": state["review_work"][row["work_id"]]["profile_id"],
                "agent_type": state["review_work"][row["work_id"]]["agent_type"]}
    return result


def quote_question(request: Mapping[str, Any], works: Mapping[str, Any], locale: str = "zh-CN") -> str:
    if locale not in {"zh-CN", "en"} or request["question_version"] != 1:
        fail("G6_ALLOWANCE_QUESTION_VERSION_OR_LOCALE")
    rows = request["allocations"]
    labels = "; ".join(f"{works[row['work_id']]['agent_type']} / {works[row['work_id']]['profile_id']}"
                       for row in rows)
    if locale == "en":
        return (f"Approve {sum(row['dispatches'] for row in rows)} additional Reviewer runs, "
                f"up to {sum(row['units'] for row in rows)} planning units and "
                f"{sum(row['attempts'] for row in rows)} dispatch attempts including no-start retries. "
                f"Only {labels}, within this request's existing scope. Request {request['request_id']}.")
    # 中文：两种固定呈现都属于同一请求，输入协议字节不随英文包转换改变。
    # English: Both fixed renderings belong to one request; preserve protocol text across locale builds.
    return (f"批准本次复审追加：{sum(row['dispatches'] for row in rows)} 次 Reviewer，"
            f"最多 {sum(row['units'] for row in rows)} 个规划单位、"
            f"{sum(row['attempts'] for row in rows)} 次含未启动重试的派发尝试；"
            f"仅限 {labels}，范围保持当前申请。申请 {request['request_id']}。")


def question_variants(request: Mapping[str, Any], works: Mapping[str, Any]) -> tuple[str, str]:
    return quote_question(request, works), quote_question(request, works, "en")


def quote_options(locale: str = "zh-CN") -> list[str]:
    if locale == "en":
        return ["Approve this allowance", "Decline this allowance"]
    if locale != "zh-CN":
        fail("G6_ALLOWANCE_QUESTION_LOCALE")
    return ["批准本次追加", "不追加"]
