"""中文：确定性读取恢复；English: finite recovery, independent of model judgment."""
from __future__ import annotations

import copy
from .routing_contract import exact, fail, integer, sha

MODE = "desktop-authoritative-context/2"
MAX_ATTEMPTS = 3
MAX_ELAPSED_MS = 5000
RESEARCH_MAX_ELAPSED_MS = 15000
RETRY_REASONS = {"CREATION_RECEIPT_PENDING", "OUTPUT_TRUNCATED"}
FIELDS = {"first_ms", "last_ms", "status", "calls", "active_call", "reason"}
EVENTS = {"ATTEMPT", "READING", "RETRYABLE", "DELIVERED", "DENIED"}


def deadline_for_runtime(runtime: dict) -> int:
    """中文：研究根第二版可明确采用更长但仍有上限的读取窗口。
    
    English: The v2 research root opts into a longer, still finite reader window.
    """
    if runtime.get("research_contract") == "desktop-research-campaign/2":
        if runtime.get("delivery_contract") != "same-call-notify/2":
            fail("CONTEXT_V2_RESEARCH_WINDOW_CONTRACT")
        return RESEARCH_MAX_ELAPSED_MS
    return MAX_ELAPSED_MS


def transition(previous: dict | None, *, event: str, call_ref: str, now_ms: int,
               reason: str = "", max_elapsed_ms: int = MAX_ELAPSED_MS) -> dict:
    """中文：纯状态归约器；所属预算串行化并持久化每次迁移。相同原生事件重复到达时保持幂等；不同读取调用须有先前已核实的可重试失败，超时不表示成功。
    
    English: Pure reducer; the owning budget serializes and persists every transition.
    
    Repeated identical native events are idempotent. A different read invocation
    requires a preceding verified retryable failure; no timeout implies success.
    """
    sha(call_ref)
    integer(now_ms, "CONTEXT_V2_CLOCK", minimum=0, maximum=2**53 - 1)
    if max_elapsed_ms not in {MAX_ELAPSED_MS, RESEARCH_MAX_ELAPSED_MS}:
        fail("CONTEXT_V2_DEADLINE_CONTRACT")
    if event not in EVENTS or (event == "RETRYABLE" and reason not in RETRY_REASONS) \
            or (event not in {"RETRYABLE", "DENIED"} and reason):
        fail("CONTEXT_V2_EVENT")
    if event == "DENIED" and (not isinstance(reason, str) or not reason or len(reason) > 128):
        fail("CONTEXT_V2_DENIAL_REASON")
    if previous is None:
        state = {"first_ms": now_ms, "last_ms": now_ms, "status": "NEW", "calls": {},
                 "active_call": "", "reason": ""}
    else:
        exact(previous, FIELDS, "CONTEXT_V2_STATE")
        state = copy.deepcopy(previous)
    if now_ms < state["last_ms"]:
        fail("CONTEXT_V2_CLOCK_REVERSED")
    old = state["calls"].get(call_ref)
    # 中文：重复通知不重新打开调用、不延长期限，也不再次计费。
    # English: Duplicate notifications never reopen a call, extend the deadline or spend.
    if old and event in old["events"]:
        if old["events"][event] != reason:
            fail("CONTEXT_V2_DUPLICATE_CONFLICT")
        return state
    if state["status"] == "DENIED" or (state["status"] == "DELIVERED" and event != "DENIED"):
        fail("CONTEXT_V2_TERMINAL")
    if event in {"READING", "DELIVERED"} and now_ms - state["first_ms"] > max_elapsed_ms:
        fail("CONTEXT_V2_RECOVERY_DEADLINE")
    if event == "ATTEMPT":
        if state["status"] not in {"NEW", "RETRYABLE"} or old:
            fail("CONTEXT_V2_ATTEMPT_IN_PROGRESS")
        if len(state["calls"]) >= MAX_ATTEMPTS:
            fail("CONTEXT_V2_RETRY_LIMIT")
        if now_ms - state["first_ms"] > max_elapsed_ms:
            fail("CONTEXT_V2_RETRY_DEADLINE")
        state["calls"][call_ref] = {"events": {"ATTEMPT": ""}}
        state.update(status="ADMITTED", active_call=call_ref, reason="")
    elif event == "DENIED":
        # 中文：首次有效读取前发生的命令拒绝也要记录。
        # English: A denied command is recorded even before the first valid reader call.
        state["calls"].setdefault(call_ref, {"events": {}})["events"][event] = reason
        state.update(status="DENIED", reason=reason)
    else:
        if call_ref != state["active_call"] or not old:
            fail("CONTEXT_V2_CALL_MISMATCH")
        allowed = {"READING": {"ADMITTED"}, "RETRYABLE": {"ADMITTED", "READING"},
                   "DELIVERED": {"READING"}}
        if state["status"] not in allowed[event]:
            fail("CONTEXT_V2_TRANSITION")
        if event == "RETRYABLE" and ((reason == "CREATION_RECEIPT_PENDING" and state["status"] != "ADMITTED")
                                     or (reason == "OUTPUT_TRUNCATED" and state["status"] != "READING")):
            fail("CONTEXT_V2_RETRY_REASON_STATE")
        old["events"][event] = reason
        state.update(status=event, reason=reason)
    state["last_ms"] = now_ms
    return state


def classify_output(response, expected: str) -> str:
    """中文：只有成功输出的严格前缀截断可恢复。读取失败可能来自材料损坏或权限问题，普通非零退出码或未知宿主结构不能自动重试。
    
    English: Only a successful, strict-prefix truncation is recoverable.
    
    A reader failure can mean corrupt material or permission failure, so a
    generic nonzero exit or unfamiliar host shape is never retried automatically.
    """
    if isinstance(response, dict):
        if type(response.get("exit_code")) is not int or response["exit_code"] != 0:
            return "DENIED"
        response = response.get("output")
    if not isinstance(response, str):
        return "DENIED"
    if response == expected:
        return "DELIVERED"
    if expected.startswith(response):
        return "OUTPUT_TRUNCATED"
    return "DENIED"
