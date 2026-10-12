"""中文：在有界内存内识别大型 Hook 的任务归属，不保存工具正文。

English: Classify large Hook envelopes with bounded memory and no body telemetry.
Only confirmed parent events may bypass the existing child input limit.
"""
from __future__ import annotations

import codecs
import json
import re
import time
from typing import BinaryIO

from .routing_contract import _constant, _object

INPUT_LIMIT = 2 * 1024 * 1024
TRANSPORT_LIMIT = 128 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
MAX_DEPTH = 64
MAX_NODES = 262144
MAX_KEY_CHARS = 1024 * 1024
MAX_STRING_CHARS = 65536
MAX_SECONDS = 3.0
_SPECIAL = re.compile(r'["\\\x00-\x1f]')
_SPACE = re.compile(r'[ \t\r\n]*')
_NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z')


def _parent(data: dict) -> bool:
    child = data.get('agent_id')
    alias = data.get('agentId', child)
    for value in (child, alias):
        if value is not None and not isinstance(value, str):
            raise ValueError('V5_CHILD_IDENTITY')
    if (child or '') != (alias or ''):
        raise ValueError('V5_CHILD_ALIAS_CONFLICT')
    return not child


class _Envelope:
    """中文：验证完整 JSON，仅保留顶层身份；English: validate all, retain identity only."""

    def __init__(self, prefix: bytes, stream: BinaryIO):
        self.deadline = time.monotonic() + MAX_SECONDS
        self.chunks = self._chunks(prefix, stream)
        self.buffer = ''
        self.position = 0
        self.nodes = 0
        self.key_chars = 0

    def _chunks(self, prefix, stream):
        decoder = codecs.getincrementaldecoder('utf-8-sig')('strict')
        total = 0
        for offset in range(0, len(prefix), CHUNK_BYTES):
            if time.monotonic() > self.deadline:
                raise ValueError('V5_HOOK_TIME')
            chunk = prefix[offset:offset + CHUNK_BYTES]
            total += len(chunk)
            if total > TRANSPORT_LIMIT:
                raise ValueError('V5_HOOK_TRANSPORT_SIZE')
            yield decoder.decode(chunk)
        while True:
            if time.monotonic() > self.deadline:
                raise ValueError('V5_HOOK_TIME')
            chunk = stream.read(min(CHUNK_BYTES, TRANSPORT_LIMIT - total + 1))
            total += len(chunk)
            if total > TRANSPORT_LIMIT:
                raise ValueError('V5_HOOK_TRANSPORT_SIZE')
            if not chunk:
                yield decoder.decode(b'', final=True)
                return
            yield decoder.decode(chunk)

    def peek(self):
        while self.position == len(self.buffer):
            try:
                self.buffer = next(self.chunks)
                self.position = 0
            except StopIteration:
                return ''
        return self.buffer[self.position]

    def take(self):
        value = self.peek()
        if not value:
            raise ValueError('V5_HOOK_JSON')
        self.position += 1
        return value

    def space(self):
        while self.peek():
            self.position = _SPACE.match(self.buffer, self.position).end()
            if self.position < len(self.buffer):
                return

    def expect(self, value):
        if self.take() != value:
            raise ValueError('V5_HOOK_JSON')

    def string(self, keep=False):
        self.expect('"')
        pieces = ['"'] if keep else None
        length = 0

        def retain(value):
            nonlocal length
            if keep:
                length += len(value)
                if length > MAX_STRING_CHARS:
                    raise ValueError('V5_HOOK_METADATA_SIZE')
                pieces.append(value)

        while self.peek():
            match = _SPECIAL.search(self.buffer, self.position)
            end = match.start() if match else len(self.buffer)
            retain(self.buffer[self.position:end] if keep else '')
            self.position = end
            if not match:
                continue
            char = self.take()
            if char == '"':
                if keep:
                    pieces.append('"')
                    return json.loads(''.join(pieces))
                return None
            if char != '\\':
                raise ValueError('V5_HOOK_JSON')
            escape = self.take()
            if escape == 'u':
                digits = ''.join(self.take() for _ in range(4))
                if any(char not in '0123456789abcdefABCDEF' for char in digits):
                    raise ValueError('V5_HOOK_JSON')
                retain('\\u' + digits)
            elif escape in '"\\/bfnrt':
                retain('\\' + escape)
            else:
                raise ValueError('V5_HOOK_JSON')
        raise ValueError('V5_HOOK_JSON')

    def value(self, depth, keep=False):
        self.nodes += 1
        if self.nodes > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError('V5_HOOK_STRUCTURE_LIMIT')
        if self.nodes % 512 == 0 and time.monotonic() > self.deadline:
            raise ValueError('V5_HOOK_TIME')
        self.space()
        char = self.peek()
        if char == '"':
            return self.string(keep)
        if char in ('{', '['):
            if keep:
                raise ValueError('V5_CHILD_IDENTITY')
            if char == '{':
                self.object(depth)
            else:
                self.take()
                self.space()
                if self.peek() == ']':
                    self.take()
                    return None
                while True:
                    self.value(depth + 1)
                    self.space()
                    separator = self.take()
                    if separator == ']':
                        break
                    if separator != ',':
                        raise ValueError('V5_HOOK_JSON')
            return None
        token = []
        while self.peek() and self.peek() not in ',]} \t\r\n':
            token.append(self.take())
            if len(token) > 4096:
                raise ValueError('V5_HOOK_STRUCTURE_LIMIT')
        text = ''.join(token)
        if text not in ('true', 'false', 'null') and not _NUMBER.fullmatch(text):
            raise ValueError('V5_HOOK_JSON')
        return json.loads(text) if keep else None

    def object(self, depth, top=False):
        self.expect('{')
        seen = set()
        identity = {}
        self.space()
        if self.peek() == '}':
            self.take()
            return identity
        while True:
            self.space()
            key = self.string(True)
            self.key_chars += len(key)
            if self.key_chars > MAX_KEY_CHARS:
                raise ValueError('V5_HOOK_METADATA_SIZE')
            if key in seen:
                raise ValueError('V5_HOOK_DUPLICATE_KEY')
            seen.add(key)
            self.space()
            self.expect(':')
            keep = top and key in ('agent_id', 'agentId')
            value = self.value(depth + 1, keep)
            if keep:
                identity[key] = value
            self.space()
            separator = self.take()
            if separator == '}':
                return identity
            if separator != ',':
                raise ValueError('V5_HOOK_JSON')

    def identity(self):
        self.space()
        if self.peek() != '{':
            raise ValueError('V5_HOOK_OBJECT')
        data = self.object(0, top=True)
        self.space()
        if self.peek():
            raise ValueError('V5_HOOK_JSON')
        return data


def read_context_input(stream: BinaryIO) -> dict:
    """中文：完整小事件或已验证主任务空事件；English: full child data or a proven neutral parent."""
    raw = stream.read(INPUT_LIMIT + 1)
    if len(raw) <= INPUT_LIMIT:
        data = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
        if not isinstance(data, dict):
            raise ValueError('V5_HOOK_OBJECT')
        _parent(data)
        return data
    identity = _Envelope(raw, stream).identity()
    if not _parent(identity):
        raise ValueError('V5_HOOK_SIZE')
    return {}
