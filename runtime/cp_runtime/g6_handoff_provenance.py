"""中文：同聊天切换策略前核验已停止的研究根。本模块只读历史证据，绝不关闭、退款、评分或恢复研究预占。

English: Verify a stopped research root before a same-chat policy handoff.

This module only reads historical evidence.  In particular it never closes,
refunds, grades, or resumes a research reservation.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import budget_v5, research_campaign
from .common import resolve_codex_home
from .path_identity import path_is_within, same_path
from .routing_contract import fail, read_document, ref


def verify_stop_checkpoint(checkpoint_path: Path, *, session_id: str,
                           repo_path: Path, head_path: Path | None = None) -> dict:
    """中文：返回旧根已停止的有界来源证据。仅当检查点账本仍是精确前缀时允许后续追加；真实迟到终态可保留在旧账本，不改写交接原证据。
    
    English: Return bounded, source-linked evidence for a stopped old root.
    
    A later append is allowed only when the checkpointed ledger remains an
    exact prefix.  A genuine late terminal event may therefore be retained in
    the old ledger without rewriting the handoff's original evidence.
    """
    checkpoint, checkpoint_bytes_ref = read_document(checkpoint_path, maximum=32_768)
    if (checkpoint.get("schema_version") != "study2-user-stop-checkpoint/1"
            or checkpoint.get("status") != "STOPPED_BY_USER"
            or checkpoint.get("resume_requires_new_user_direction") is not True
            or checkpoint.get("stage_terminal") is not False
            or checkpoint.get("active_host_receipt_disposition") != "created"
            or checkpoint.get("active_reservation_state") != "RESERVED"
            or checkpoint.get("active_reader_verified") is not False
            or checkpoint.get("active_native_final_verified") is not False
            or checkpoint.get("active_attempt_refund_claim") is not False):
        fail("G6_HANDOFF_STOP_EVIDENCE")
    if checkpoint.get("research_head_ref", {}).get("session_ref") != ref(session_id):
        fail("G6_HANDOFF_SESSION")
    old_ledger = Path(checkpoint["ledger_path"])
    if not old_ledger.is_absolute() or path_is_within(old_ledger, repo_path):
        fail("G6_HANDOFF_LEDGER_PATH")
    events = budget_v5._read_events(old_ledger)
    current = budget_v5.replay(events)
    sequence = checkpoint["ledger_sequence"]
    if type(sequence) is not int or sequence < 1 or sequence > len(events):
        fail("G6_HANDOFF_LEDGER_SEQUENCE")
    prefix = events[:sequence]
    checkpointed = budget_v5.replay(prefix)
    if (prefix[-1]["record_hash"] != checkpoint["ledger_head_hash"]
            or checkpointed["head_hash"] != checkpoint["ledger_head_hash"]
            or not same_path(Path(checkpointed["root_binding"]["repo_path"]), repo_path)
            or current["identity"] != checkpointed["identity"]):
        fail("G6_HANDOFF_LEDGER_IDENTITY")
    with old_ledger.open("rb") as stream:
        raw_prefix = b"".join(stream.readline() for _ in range(sequence))
    if hashlib.sha256(raw_prefix).hexdigest() != checkpoint["ledger_bytes_sha256"]:
        fail("G6_HANDOFF_LEDGER_PREFIX")
    reservation_id = checkpoint["active_reservation_id"]
    reservation = checkpointed["reservations"].get(reservation_id)
    receipt = checkpointed["host_receipts"].get(reservation_id)
    if (not reservation or reservation["state"] != "RESERVED" or not receipt
            or receipt["disposition"] != "created"
            or receipt["agent_ref"] != ref(checkpoint["active_agent_path"])):
        fail("G6_HANDOFF_INTERRUPTED_CHILD")
    transcript = Path(checkpoint["active_transcript_path"])
    sessions = resolve_codex_home() / "sessions"
    if not path_is_within(transcript, sessions) or not transcript.is_file():
        fail("G6_HANDOFF_TRANSCRIPT_PATH")
    digest = hashlib.sha256()
    with transcript.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    if digest.hexdigest() != checkpoint["active_transcript_bytes_sha256"]:
        fail("G6_HANDOFF_TRANSCRIPT_CHANGED")
    observed_head = head_path or research_campaign._head(session_id)
    head, _ = read_document(observed_head, maximum=32_768)
    if head != checkpoint["research_head_ref"]:
        fail("G6_HANDOFF_RESEARCH_HEAD_CHANGED")
    return {
        "schema_version": "g6-stopped-root-evidence/1",
        "session_ref": ref(session_id),
        "stop_checkpoint_ref": ref(checkpoint),
        "stop_checkpoint_bytes_ref": checkpoint_bytes_ref,
        "old_ledger_path": str(old_ledger.resolve()),
        "old_ledger_anchor_sequence": sequence,
        "old_ledger_anchor_hash": checkpoint["ledger_head_hash"],
        "old_ledger_current_sequence": current["sequence"],
        "old_ledger_current_hash": current["head_hash"],
        "old_root_closed": current["closed"],
        "interrupted_child_ref": ref(checkpoint["active_child_id"]),
        "interrupted_reservation_id": reservation_id,
        "interrupted_reservation_current_state": current["reservations"][reservation_id]["state"],
        "transcript_sha256": digest.hexdigest(),
        "old_research_head_ref": ref(head),
        "identity": checkpointed["identity"],
    }
