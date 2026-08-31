"""自观察数据脱敏。

只输出分析所需的结构化字段；疑似密钥、令牌、Cookie、私钥及连接串均替换为固定标记。
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
    # 治理字段描述的是授权状态，不是凭据本身，不能被误删，否则会破坏合同哈希。
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
    """用于测试和最终写入前的保守检查。"""
    text = repr(value)
    if _REDACTED in text:
        text = text.replace(_REDACTED, "")
    return any(pattern.search(text) for pattern in _PATTERNS)
