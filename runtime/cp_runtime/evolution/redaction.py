"""中文：自观察数据脱敏：只处理明确的结构化字段，并把凭据、Token、Cookie、私钥和疑似代码替换为固定标记。

English: Redact self-observation data by processing explicit structured fields and replacing credentials, tokens, cookies, private keys, and suspected source content with fixed markers.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Mapping

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY_RE = re.compile(
    r"(?:^|[_\-.])(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|authorization|cookie|session|credential|client[_-]?secret)(?:$|[_\-.])",
    re.IGNORECASE,
)
_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+\-/=]{12,}"),
    re.compile(r"(?i)\b(Basic)\s+[A-Za-z0-9+/=]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)(mongodb(?:\+srv)?|mysql|postgres(?:ql)?|redis)://[^\s]+"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def is_sensitive_key(key: str) -> bool:
    normalized = str(key).strip().lower()
# 中文：治理字段描述授权状态而非凭据，不能误删，否则会破坏契约哈希。
# English: Governance fields describe authorization state rather than credentials and must not be removed because that would break contract hashes.
    if normalized in {
        "execution_authorization",
        "automatic_execution",
        "approval_scope",
        "authorization_scope",
    }:
        return False
    return bool(_SENSITIVE_KEY_RE.search(normalized))


def redact_text(value: str) -> str:
    result = value
    for pattern in _PATTERNS:
        result = pattern.sub(_REDACTED, result)
    if len(result) > 8192:
        result = result[:8192] + "...[TRUNCATED]"
    return result


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if is_sensitive_key(name):
                result[name] = _REDACTED
            else:
                result[name] = redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def contains_obvious_secret(value: Any) -> bool:
    """中文：供测试和最终写入前使用的保守敏感信息检查。

    English: Conservative sensitive-data check for tests and final pre-write validation.
    """
    text = repr(value)
    if _REDACTED in text:
        text = text.replace(_REDACTED, "")
    return any(pattern.search(text) for pattern in _PATTERNS)
