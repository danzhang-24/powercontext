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

"""Pi v3 session branch parsing and durable raw-event acquisition."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, JsonValue

from powercontext.limits import MAX_SOURCE_ID_LENGTH
from powercontext.sources import (
    TEXT_EVIDENCE_PROJECTION_KEY,
    AdapterSourceDefinition,
    ConnectorRunCompletion,
    ConnectorRunSession,
    ConnectorRunStatus,
    TextEvidence,
)
from powercontext.sources.models import Source, SourceMaterialization

PI_EVENT_SOURCE_NAME = "pi-event"
PI_CONNECTOR_NAME = "pi-session-history"
_CHECKPOINT_SCHEMA = "powercontext.pi-session-checkpoint.v1"


class PiSessionInput(BaseModel):
    """One complete Pi v3 JSONL archive and an optional selected leaf."""

    model_config = ConfigDict(extra="forbid")

    content: bytes
    leaf_id: str | None = None


class PiEventInput(BaseModel):
    """One visible event on the selected Pi branch, with its complete raw record."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    event_id: str
    parent_id: str | None
    event_type: str
    role: str
    content: str
    record: JsonValue


class PiEventSource(Source):
    """Captured evidence for one immutable Pi event."""

    source_id: str
    session_id: str
    event_id: str
    parent_id: str | None
    event_type: str
    role: str
    content: str
    record: JsonValue


def parse_pi_session(value: PiSessionInput, /) -> tuple[PiEventInput, ...]:
    """Fully parse one graph and return visible events on its selected branch."""

    session_id, records, selected_ids = _parse_graph(value)
    return _selected_events(session_id, records, selected_ids)


def _selected_events(
    session_id: str,
    records: tuple[dict[str, Any], ...],
    selected_ids: tuple[str, ...],
) -> tuple[PiEventInput, ...]:
    parent_by_id = {record["id"]: record.get("parentId") for record in records}
    events: list[PiEventInput] = []
    for event_id in selected_ids:
        record = _event_by_id(records, event_id)
        rendered = _render_event(record)
        if rendered is None:
            continue
        role, content = rendered
        events.append(
            PiEventInput(
                session_id=session_id,
                event_id=event_id,
                parent_id=parent_by_id[event_id],
                event_type=str(record.get("type")),
                role=role,
                content=content,
                record=record,
            )
        )
    return tuple(events)


class PiSessionConnector:
    """Acquire only visible events not already imported for this session."""

    name = PI_CONNECTOR_NAME
    version = "1"
    source_definitions = frozenset({PI_EVENT_SOURCE_NAME})

    def __init__(self, path: str | Path, leaf_id: str | None = None) -> None:
        self._path = Path(path)
        self._leaf_id = leaf_id

    async def run(self, session: ConnectorRunSession, /) -> ConnectorRunCompletion:
        content = self._path.read_bytes()
        parsed_session_id, records, selected_ids = _parse_graph(
            PiSessionInput(content=content, leaf_id=self._leaf_id)
        )
        events = _selected_events(parsed_session_id, records, selected_ids)
        imported = _decode_checkpoint(session.checkpoint, parsed_session_id)
        record_by_id = {str(record["id"]): record for record in records}
        for event_id, digest in imported.items():
            record = record_by_id.get(event_id)
            if record is not None and _record_fingerprint(record) != digest:
                raise ValueError(f"imported Pi event {event_id!r} was rewritten")

        current: dict[str, str] = {}
        for event in events:
            fingerprint = _record_fingerprint(event.record)
            previous = imported.get(event.event_id)
            if previous is not None and previous != fingerprint:
                raise ValueError(f"imported Pi event {event.event_id!r} was rewritten")
            current[event.event_id] = fingerprint
        for event in events:
            if event.event_id not in imported:
                await session.submit(
                    event.event_id,
                    PI_EVENT_SOURCE_NAME,
                    event,
                )
        imported.update(current)
        checkpoint = {
            "schema": _CHECKPOINT_SCHEMA,
            "session_id": parsed_session_id,
            "events": [
                {"event_id": event_id, "record_sha256": imported[event_id]}
                for event_id in sorted(imported)
            ],
        }
        return ConnectorRunCompletion(
            status=ConnectorRunStatus.COMPLETE,
            checkpoint=checkpoint,
        )


class PiEventSourceAdapter:
    """Resolve and read exact Pi event Sources."""

    input_class = PiEventInput
    name = PI_EVENT_SOURCE_NAME
    source_class = PiEventSource

    async def resolve(self, value: PiEventInput, /) -> PiEventSource:
        source_id = pi_event_source_id(value.session_id, value.event_id)
        return PiEventSource(
            name=source_id,
            source_id=source_id,
            materialization=SourceMaterialization.CAPTURED,
            session_id=value.session_id,
            event_id=value.event_id,
            parent_id=value.parent_id,
            event_type=value.event_type,
            role=value.role,
            content=value.content,
            record=value.record,
        )

    async def read(self, source: PiEventSource, /) -> PiEventInput:
        return PiEventInput(
            session_id=source.session_id,
            event_id=source.event_id,
            parent_id=source.parent_id,
            event_type=source.event_type,
            role=source.role,
            content=source.content,
            record=source.record,
        )


class PiEventTextEvidenceProjection:
    """Expose one Pi event's complete visible text as standard evidence."""

    name = TEXT_EVIDENCE_PROJECTION_KEY.name
    version = TEXT_EVIDENCE_PROJECTION_KEY.version
    source_class = PiEventSource
    output_class: type[BaseModel] = TextEvidence

    def project(self, source: PiEventSource, /) -> TextEvidence:
        return TextEvidence(
            source_type=PI_EVENT_SOURCE_NAME,
            source_id=source.source_id,
            content=source.content,
            metadata={
                "session_id": source.session_id,
                "event_id": source.event_id,
                "parent_id": source.parent_id,
                "event_type": source.event_type,
                "role": source.role,
            },
        )


PI_EVENT_SOURCE_ADAPTER = PiEventSourceAdapter()
PI_EVENT_SOURCE_DEFINITION = AdapterSourceDefinition(
    PI_EVENT_SOURCE_ADAPTER,
    version="1",
    projections=(PiEventTextEvidenceProjection(),),
)


def pi_event_source_id(session_id: str, event_id: str) -> str:
    source_id = f"pi:{quote(session_id, safe='')}:{quote(event_id, safe='')}"
    if len(source_id) > MAX_SOURCE_ID_LENGTH:
        raise ValueError(f"Pi event Source identity exceeds {MAX_SOURCE_ID_LENGTH} characters")  # noqa: TRY003
    return source_id


def _parse_graph(value: PiSessionInput) -> tuple[str, tuple[dict[str, Any], ...], tuple[str, ...]]:
    if not isinstance(value, PiSessionInput):
        raise ValueError("Pi session input must be PiSessionInput")  # noqa: TRY003
    try:
        text = value.content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Pi session must be valid UTF-8") from error
    try:
        raw_records = [json.loads(line) for line in text.splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        raise ValueError("Pi session must contain valid JSONL") from error
    if not raw_records or not isinstance(raw_records[0], dict):
        raise ValueError("Pi session must start with a session header")  # noqa: TRY003
    header = raw_records[0]
    session_id = header.get("id")
    if (
        header.get("type") != "session"
        or type(header.get("version")) is not int
        or header.get("version") != 3
        or not isinstance(session_id, str)
        or not session_id.strip()
    ):
        raise ValueError("unsupported or invalid Pi session header")  # noqa: TRY003
    records: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for record in raw_records[1:]:
        if not isinstance(record, dict):
            raise ValueError("Pi session records must be JSON objects")  # noqa: TRY003
        event_id = record.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("Pi session record id must be non-empty")  # noqa: TRY003
        if event_id in by_id:
            raise ValueError(f"duplicate Pi session record id {event_id!r}")  # noqa: TRY003
        if "parentId" not in record:
            raise ValueError("Pi session record is missing parentId")  # noqa: TRY003
        parent_id = record["parentId"]
        if parent_id is not None and (
            not isinstance(parent_id, str) or not parent_id or parent_id not in by_id
        ):
            raise ValueError("Pi session parent must refer to an earlier record")  # noqa: TRY003
        by_id[event_id] = record
        records.append(record)
    leaf_id = value.leaf_id
    if leaf_id is None:
        leaf_id = None if not records else str(records[-1]["id"])
    if leaf_id is not None and leaf_id not in by_id:
        raise ValueError(f"Pi session leaf {leaf_id!r} does not exist")  # noqa: TRY003
    selected: list[str] = []
    cursor: str | None = leaf_id
    while cursor is not None:
        selected.append(cursor)
        cursor = by_id[cursor]["parentId"]
    selected.reverse()
    return session_id, tuple(records), tuple(selected)


def _render_event(record: dict[str, Any]) -> tuple[str, str] | None:
    event_type = record.get("type")
    if event_type in {"compaction", "branch_summary"}:
        summary = record.get("summary")
        if not isinstance(summary, str) or summary == "":
            return None
        return str(event_type), f"{event_type}: {summary}"
    if event_type == "custom_message":
        body = _visible_text(record.get("content"))
        if body == "":
            return None
        return "custom", f"custom: {body}"
    if event_type != "message" or not isinstance(record.get("message"), dict):
        return None
    message = record["message"]
    role = message.get("role")
    if not isinstance(role, str) or not role:
        return None
    if role == "toolResult":
        body = _text_blocks(message.get("content"))
        if body == "":
            return None
        tool_name = message.get("toolName")
        tool_call_id = message.get("toolCallId")
        if not isinstance(tool_name, str) or not isinstance(tool_call_id, str):
            return None
        return role, f"toolResult: [tool_result {tool_name} {tool_call_id}] {body}"
    if role == "bashExecution":
        command = message.get("command")
        output = message.get("output", "")
        if not isinstance(command, str) or not isinstance(output, str):
            return None
        return role, f"bashExecution: $ {command}\n{output}"
    body = _visible_text(message.get("content"))
    if body == "":
        return None
    return role, f"{role}: {body}"


def _visible_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
        elif block_type == "toolCall":
            name = block.get("name")
            call_id = block.get("id")
            if isinstance(name, str) and isinstance(call_id, str):
                arguments = json.dumps(
                    block.get("arguments", {}),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                parts.append(f"[tool_call {name} {call_id}] {arguments}")
    return "\n".join(parts)


def _text_blocks(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block["text"]
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    )


def _event_by_id(records: tuple[dict[str, Any], ...], event_id: str) -> dict[str, Any]:
    for record in records:
        if record["id"] == event_id:
            return record
    raise ValueError(f"unknown Pi event {event_id!r}")  # noqa: TRY003


def _record_fingerprint(record: JsonValue) -> str:
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decode_checkpoint(checkpoint: JsonValue | None, session_id: str) -> dict[str, str]:
    if checkpoint is None:
        return {}
    if not isinstance(checkpoint, dict) or set(checkpoint) != {"schema", "session_id", "events"}:
        raise ValueError("invalid Pi connector checkpoint")  # noqa: TRY003
    if checkpoint["schema"] != _CHECKPOINT_SCHEMA or checkpoint["session_id"] != session_id:
        raise ValueError("Pi connector checkpoint belongs to another archive")  # noqa: TRY003
    events = checkpoint["events"]
    if not isinstance(events, list):
        raise ValueError("invalid Pi connector checkpoint events")  # noqa: TRY003
    decoded: dict[str, str] = {}
    for row in events:
        if not isinstance(row, dict) or set(row) != {"event_id", "record_sha256"}:
            raise ValueError("invalid Pi connector checkpoint event")  # noqa: TRY003
        event_id, digest = row["event_id"], row["record_sha256"]
        if not isinstance(event_id, str) or not isinstance(digest, str) or event_id in decoded:
            raise ValueError("invalid Pi connector checkpoint identity")  # noqa: TRY003
        decoded[event_id] = digest
    return decoded


__all__ = [
    "PI_EVENT_SOURCE_DEFINITION",
    "PI_EVENT_SOURCE_NAME",
    "PiEventInput",
    "PiEventSource",
    "PiSessionConnector",
    "PiSessionInput",
    "parse_pi_session",
    "pi_event_source_id",
]
