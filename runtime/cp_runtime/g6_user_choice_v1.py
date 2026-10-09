"""中文：有界读取原生用户选型，模型自报标签不能提升为用户授权。

English: Bounded native user model choice; never promote model-supplied labels to user authority.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

from .common import atomic_write_json, read_json, resolve_codex_home, utc_now
from .event_v2 import OwnerTokenLock, project_identity_for
from .g6_flexible_policy import POLICY_ID, POLICY_SHA256, PROFILES
from .routing_contract import exact, fail, ref

FIELDS = {"schema_version", "source", "policy_id", "policy_digest", "session_ref",
          "turn_ref", "repo_fingerprint", "profile_id", "prompt_sha256", "recorded_at"}
DIRECTIVE = re.compile(
    r"^\s*(?:请)?(?:使用|选择|指定|use|choose)\s+"
    r"(?P<model>gpt-6-(?:luna|sol|astra))\s+(?P<effort>low|medium|high)"
    r"\s*(?:[。.;；]|$)", re.IGNORECASE,
)
STRUCTURED_DIRECTIVE = re.compile(
    r"^\s*model\s*=\s*(?P<model>gpt-6-(?:luna|sol|astra))\s+"
    r"reasoning_effort\s*=\s*(?P<effort>low|medium|high)\s*$", re.IGNORECASE,
)
NEGATION = re.compile(r"不要.{0,16}(?:改变|切换|使用).{0,16}模型|不要使用|"
                      r"do\s+not\s+(?:change|use).{0,16}model|don't\s+use", re.IGNORECASE)


def _path(session: str, turn: str, directory: Path | None = None) -> Path:
    root = directory or resolve_codex_home() / "cp-assistant" / "g6-routing" / "user-choice"
    return root / ref(session)[7:] / (ref(turn)[7:] + ".json")


def parse_direct_choice(prompt: str) -> str | None:
    if not isinstance(prompt, str) or len(prompt.encode("utf-8")) > 65_536:
        return None
    if NEGATION.search(prompt):
        return None
    first = prompt.splitlines()[0] if prompt.splitlines() else ""
    match = DIRECTIVE.fullmatch(first) or STRUCTURED_DIRECTIVE.fullmatch(first)
    if match is None:
        return None
    # 中文：后续引用或矛盾指令会使用户意图不明确。
    # English: Later quoted or contradictory directives make intent ambiguous.
    if any(DIRECTIVE.fullmatch(line) or STRUCTURED_DIRECTIVE.fullmatch(line)
           for line in prompt.splitlines()[1:]):
        return None
    model = match.group("model").lower()
    effort = match.group("effort").lower()
    profile = "g6-" + model.rsplit("-", 1)[1] + "-" + effort
    return profile if profile in PROFILES else None


def observe_native_prompt(data: Mapping[str, Any], *, directory: Path | None = None) -> dict | None:
    """中文：只记录唯一且无歧义的宿主直接选型，不保存提示正文。
    
    English: Record only one unambiguous direct host prompt choice, never prompt text.
    """
    if data.get("hook_event_name") != "UserPromptSubmit":
        return None
    session, turn, cwd = data.get("session_id"), data.get("turn_id"), data.get("cwd")
    if not all(isinstance(item, str) and item for item in (session, turn, cwd)):
        return None
    prompt = data.get("prompt")
    profile = parse_direct_choice(prompt)
    if profile is None:
        return None
    fingerprint, _ = project_identity_for(cwd)
    value = {"schema_version": "g6-native-user-choice/1", "source": "native-user-prompt-submit",
             "policy_id": POLICY_ID, "policy_digest": "sha256:" + POLICY_SHA256,
             "session_ref": ref(session), "turn_ref": ref(turn),
             "repo_fingerprint": fingerprint, "profile_id": profile,
             "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
             "recorded_at": utc_now()}
    path = _path(session, turn, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=2):
        if path.exists():
            old = read_json(path, verify=True, label="native user model choice")
            old.pop("integrity")
            if {k: old[k] for k in FIELDS - {"recorded_at"}} != {
                    k: value[k] for k in FIELDS - {"recorded_at"}}:
                fail("G6_USER_CHOICE_CONFLICT")
            return old
        atomic_write_json(path, value, seal=True)
    return value


def read_choice(*, session_id: str, turn_id: str, cwd: Path,
                directory: Path | None = None) -> dict | None:
    if not session_id or not turn_id:
        return None
    path = _path(session_id, turn_id, directory)
    if not path.exists():
        return None
    with OwnerTokenLock(path, timeout=2):
        value = read_json(path, verify=True, label="native user model choice")
    value.pop("integrity")
    exact(value, FIELDS, "G6_USER_CHOICE_FIELDS")
    fingerprint, _ = project_identity_for(str(cwd))
    if (value["schema_version"] != "g6-native-user-choice/1"
            or value["source"] != "native-user-prompt-submit"
            or value["policy_id"] != POLICY_ID
            or value["policy_digest"] != "sha256:" + POLICY_SHA256
            or value["session_ref"] != ref(session_id)
            or value["turn_ref"] != ref(turn_id)
            or value["repo_fingerprint"] != fingerprint
            or value["profile_id"] not in PROFILES
            or not re.fullmatch(r"[0-9a-f]{64}", value["prompt_sha256"])):
        fail("G6_USER_CHOICE_IDENTITY")
    return value
