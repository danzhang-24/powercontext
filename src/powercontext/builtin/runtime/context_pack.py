# Copyright (c) 2026 OceanBase.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Deterministic full and incremental wire formats for prepared Context."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from typing import Any

PACK_SCHEMA = "powercontext.context-pack.v1"
DELTA_SCHEMA = "powercontext.context-pack-delta.v1"
_PACK_FIELDS = frozenset({"schema", "items", "digest", "byte_count"})
_DELTA_FIELDS = frozenset({"schema", "base_digest", "target_digest", "prefix_items", "appended"})


class ContextPackError(ValueError):
    """A Context pack or delta failed protocol validation."""


@dataclass(frozen=True, slots=True)
class ContextPack:
    """One validated complete sequence of UTF-8 byte chunks."""

    items: tuple[bytes, ...]
    digest: str
    byte_count: int

    @classmethod
    def build(cls, items: tuple[bytes, ...], /) -> ContextPack:
        normalized = _validate_items(items)
        digest = _pack_digest(normalized)
        byte_count = _pack_byte_count(normalized, digest)
        return cls(items=normalized, digest=digest, byte_count=byte_count)

    @classmethod
    def from_content(cls, content: str, /, *, chunk_bytes: int = 512) -> ContextPack:
        if not isinstance(content, str):
            raise ContextPackError("content must be text")
        if not isinstance(chunk_bytes, int) or isinstance(chunk_bytes, bool) or chunk_bytes < 1:
            raise ContextPackError("chunk_bytes must be a positive integer")
        if not content:
            return cls.build(())
        chunks: list[bytes] = []
        current: list[str] = []
        current_bytes = 0
        for character in content:
            encoded = character.encode("utf-8")
            if len(encoded) > chunk_bytes:
                raise ContextPackError("a UTF-8 character exceeds the chunk limit")
            if current and current_bytes + len(encoded) > chunk_bytes:
                chunks.append("".join(current).encode("utf-8"))
                current = []
                current_bytes = 0
            current.append(character)
            current_bytes += len(encoded)
        if current:
            chunks.append("".join(current).encode("utf-8"))
        return cls.build(tuple(chunks))

    def to_bytes(self) -> bytes:
        if self.digest != _pack_digest(self.items):
            raise ContextPackError("pack digest does not match its items")
        payload = _pack_payload(self.items, self.digest, self.byte_count)
        encoded = _canonical_json(payload)
        if len(encoded) != self.byte_count:
            raise ContextPackError("pack byte_count does not match its wire representation")
        return encoded

    @classmethod
    def from_bytes(cls, value: bytes, /) -> ContextPack:
        raw, payload = _decode_object(value, _PACK_FIELDS, "pack")
        if payload["schema"] != PACK_SCHEMA:
            raise ContextPackError("unsupported Context pack schema")
        items = _decode_items(payload["items"], "items")
        digest = payload["digest"]
        byte_count = payload["byte_count"]
        if not isinstance(digest, str):
            raise ContextPackError("pack digest must be a string")
        if type(byte_count) is not int or byte_count < 0 or byte_count != len(raw):
            raise ContextPackError("pack byte_count does not match the received bytes")
        expected = _pack_digest(items)
        if digest != expected:
            raise ContextPackError("pack digest verification failed")
        if raw != _canonical_json(_pack_payload(items, digest, byte_count)):
            raise ContextPackError("pack is not canonically encoded")
        return cls(items=items, digest=digest, byte_count=byte_count)


@dataclass(frozen=True, slots=True)
class ContextPackDelta:
    """A target suffix paired with a reusable prefix of one complete pack."""

    base_digest: str
    target_digest: str
    prefix_items: int
    appended: tuple[bytes, ...]

    @classmethod
    def between(cls, base: ContextPack, target: ContextPack, /) -> ContextPackDelta:
        if not isinstance(base, ContextPack) or not isinstance(target, ContextPack):
            raise ContextPackError("delta endpoints must be ContextPack values")
        base.to_bytes()
        target.to_bytes()
        prefix = 0
        for left, right in zip(base.items, target.items, strict=False):
            if left != right:
                break
            prefix += 1
        return cls(
            base_digest=base.digest,
            target_digest=target.digest,
            prefix_items=prefix,
            appended=target.items[prefix:],
        )

    @property
    def byte_count(self) -> int:
        return len(self.to_bytes())

    def to_bytes(self) -> bytes:
        if not isinstance(self.prefix_items, int) or isinstance(self.prefix_items, bool) or self.prefix_items < 0:
            raise ContextPackError("prefix_items must be a non-negative integer")
        appended = _validate_items(self.appended)
        if self.base_digest == self.target_digest and self.prefix_items < 0:
            raise ContextPackError("invalid unchanged delta")
        return _canonical_json({
            "schema": DELTA_SCHEMA,
            "base_digest": self.base_digest,
            "target_digest": self.target_digest,
            "prefix_items": self.prefix_items,
            "appended": [base64.b64encode(item).decode("ascii") for item in appended],
        })

    @classmethod
    def from_bytes(cls, value: bytes, /) -> ContextPackDelta:
        _, payload = _decode_object(value, _DELTA_FIELDS, "delta")
        if payload["schema"] != DELTA_SCHEMA:
            raise ContextPackError("unsupported Context pack delta schema")
        base_digest = payload["base_digest"]
        target_digest = payload["target_digest"]
        prefix = payload["prefix_items"]
        if not isinstance(base_digest, str) or not isinstance(target_digest, str):
            raise ContextPackError("delta digests must be strings")
        if type(prefix) is not int or prefix < 0:
            raise ContextPackError("prefix_items must be a non-negative integer")
        appended = _decode_items(payload["appended"], "appended")
        return cls(base_digest, target_digest, prefix, appended)


def apply_context_pack_delta(base: ContextPack, delta: ContextPackDelta, /) -> ContextPack:
    """Verify and reconstruct the exact target pack using only wire-safe values."""

    if not isinstance(base, ContextPack) or not isinstance(delta, ContextPackDelta):
        raise ContextPackError("base and delta must be Context pack values")
    base = ContextPack.from_bytes(base.to_bytes())
    if base.digest != delta.base_digest:
        raise ContextPackError("delta base digest does not match")
    if type(delta.prefix_items) is not int or not 0 <= delta.prefix_items <= len(base.items):
        raise ContextPackError("delta prefix is outside the base pack")
    items = base.items[: delta.prefix_items] + _validate_items(delta.appended)
    target = ContextPack.build(items)
    if target.digest != delta.target_digest:
        raise ContextPackError("reconstructed target digest does not match")
    return target


def _validate_items(items: tuple[bytes, ...], /) -> tuple[bytes, ...]:
    if not isinstance(items, tuple):
        raise ContextPackError("items must be a tuple of bytes")
    for item in items:
        if not isinstance(item, bytes):
            raise ContextPackError("items must contain bytes")
        try:
            item.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ContextPackError("each item must be valid UTF-8") from error
    return items


def _pack_payload(items: tuple[bytes, ...], digest: str, byte_count: int) -> dict[str, object]:
    return {
        "schema": PACK_SCHEMA,
        "items": [base64.b64encode(item).decode("ascii") for item in items],
        "digest": digest,
        "byte_count": byte_count,
    }


def _pack_digest(items: tuple[bytes, ...]) -> str:
    unsigned = {
        "schema": PACK_SCHEMA,
        "items": [base64.b64encode(item).decode("ascii") for item in items],
    }
    return "sha256:" + hashlib.sha256(_canonical_json(unsigned)).hexdigest()


def _pack_byte_count(items: tuple[bytes, ...], digest: str) -> int:
    byte_count = 0
    while True:
        actual = len(_canonical_json(_pack_payload(items, digest, byte_count)))
        if actual == byte_count:
            return byte_count
        byte_count = actual


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _decode_object(value: bytes, expected_fields: frozenset[str], name: str) -> tuple[bytes, dict[str, Any]]:
    if not isinstance(value, bytes):
        raise ContextPackError(f"{name} wire value must be bytes")
    try:
        pairs = json.loads(value.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContextPackError(f"{name} is not valid UTF-8 JSON") from error
    if not isinstance(pairs, dict) or set(pairs) != expected_fields:
        raise ContextPackError(f"{name} fields do not match the protocol")
    return value, pairs


def _decode_items(value: object, field: str) -> tuple[bytes, ...]:
    if not isinstance(value, list):
        raise ContextPackError(f"{field} must be an array")
    items: list[bytes] = []
    for encoded in value:
        if not isinstance(encoded, str):
            raise ContextPackError(f"{field} entries must be Base64 strings")
        try:
            item = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ContextPackError(f"{field} contains invalid Base64") from error
        items.append(item)
    return _validate_items(tuple(items))


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContextPackError("wire object contains a duplicate field")
        result[key] = value
    return result


__all__ = [
    "ContextPack",
    "ContextPackDelta",
    "ContextPackError",
    "apply_context_pack_delta",
]
