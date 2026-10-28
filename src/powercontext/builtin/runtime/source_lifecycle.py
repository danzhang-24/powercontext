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

"""Persistent source-dependency lifecycle for Memory and Topic Memory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator
from sqlalchemy import insert, select, update

from powercontext.artifacts import ArtifactRef, MemoryCitation
from powercontext.builtin.persistence.database import AsyncDatabase
from powercontext.builtin.persistence.tables import SOURCE_LIFECYCLE_NODES_TABLE
from powercontext.builtin.sources import validate_scope_id
from powercontext.sources import SourceRef

if TYPE_CHECKING:
    from powercontext.builtin.runtime.application import BuiltinRuntime


class SourceLifecycleError(ValueError):
    """A lifecycle graph, event, or reference invariant was violated."""


class SourceLifecycleEvent(BaseModel):
    """One strictly validated source availability transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str
    revision: StrictInt = Field(ge=1)
    sequence: StrictInt = Field(ge=1)
    available: StrictBool
    reason: str

    @field_validator("node_id", "reason")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be a non-empty, non-whitespace string")  # noqa: TRY003
        return value


Reference = SourceRef | MemoryCitation | ArtifactRef
Policy = Literal["all", "any"]
NodeKind = Literal["source", "memory", "topic"]


@dataclass(frozen=True, slots=True)
class _Node:
    node_id: str
    kind: NodeKind
    reference: Reference
    parents: tuple[str, ...]
    policy: Policy
    available: bool
    lifecycle_revision: int | None
    event_sequence: int
    event_payload: bytes | None


class LifecycleApplication:
    """Select a persistent source-lifecycle graph for one Scope."""

    def __init__(self, runtime: BuiltinRuntime, database: AsyncDatabase) -> None:
        self._runtime = runtime
        self._database = database
        self._locks: dict[str, Any] = {}

    def for_scope(self, scope_id: str, /) -> SourceLifecycleService:
        scope = validate_scope_id(scope_id)
        import asyncio

        lock = self._locks.get(scope)
        if lock is None:
            lock = self._locks[scope] = asyncio.Lock()
        return SourceLifecycleService(self._runtime, self._database, scope, lock)

    async def active_topic_refs(self, scope_id: str) -> frozenset[tuple[str, str, int]] | None:
        """Return the searchable Topic projection, or ``None`` when unmanaged."""

        scope = validate_scope_id(scope_id)
        async with self._database.transaction() as connection:
            rows = (
                await connection.execute(
                    select(SOURCE_LIFECYCLE_NODES_TABLE).where(
                        SOURCE_LIFECYCLE_NODES_TABLE.c.scope_id == scope
                    )
                )
            ).mappings().all()
        nodes = tuple(_decode_node(row) for row in rows)
        topics = tuple(node for node in nodes if node.kind == "topic")
        if not topics:
            return None
        active = _effective_availability(nodes)
        return frozenset(
            (node.reference.family, node.reference.artifact_id, node.reference.revision)
            for node in topics
            if active.get(node.node_id, False) and isinstance(node.reference, ArtifactRef)
        )


class SourceLifecycleService:
    """Register and propagate one Scope's explicit evidence dependency DAG."""

    def __init__(
        self,
        runtime: BuiltinRuntime,
        database: AsyncDatabase,
        scope_id: str,
        lock: Any,
    ) -> None:
        self._runtime = runtime
        self._database = database
        self.scope_id = scope_id
        self._lock = lock

    async def register_source(self, node_id: str, source_ref: SourceRef, revision: int) -> None:
        """Register one exposed Source and its lifecycle version."""

        _require_node_id(node_id)
        _require_revision(revision)
        if not isinstance(source_ref, SourceRef):
            raise SourceLifecycleError("source_ref must be a SourceRef")
        binding = _binding("source", source_ref, (), "all", revision)
        async with self._runtime._context(self.scope_id), self._lock, self._runtime._locked(self.scope_id):
            existing = await self._read_node(node_id)
            if existing is not None:
                if (
                    existing.kind != "source"
                    or existing.reference != source_ref
                    or existing.lifecycle_revision != revision
                ):
                    raise SourceLifecycleError(f"node {node_id!r} is already registered with another binding")
                return
            await self._verify_source(source_ref)
            async with self._database.transaction() as connection:
                await connection.execute(
                    insert(SOURCE_LIFECYCLE_NODES_TABLE).values(
                        scope_id=self.scope_id,
                        node_id=node_id,
                        node_kind="source",
                        binding=binding,
                        parents=b"[]",
                        policy="all",
                        available=True,
                        lifecycle_revision=revision,
                        event_sequence=0,
                        event_payload=None,
                    )
                )

    async def register_memory(
        self,
        node_id: str,
        citation: MemoryCitation,
        /,
        *,
        parents: tuple[str, ...],
        policy: Policy,
    ) -> None:
        """Register one exact Memory entry-version and its support policy."""

        await self._register_derived(node_id, "memory", citation, parents=parents, policy=policy)

    async def register_topic(
        self,
        node_id: str,
        artifact_ref: ArtifactRef,
        /,
        *,
        parents: tuple[str, ...],
        policy: Policy,
    ) -> None:
        """Register one exact Topic revision and its support policy."""

        if not isinstance(artifact_ref, ArtifactRef) or artifact_ref.family != "topic-memory":
            raise SourceLifecycleError("topic registration requires a topic-memory ArtifactRef")
        await self._register_derived(node_id, "topic", artifact_ref, parents=parents, policy=policy)

    async def apply(self, event: SourceLifecycleEvent, /) -> list[str]:
        """Persist one idempotent Source event and synchronize every descendant."""

        if not isinstance(event, SourceLifecycleEvent):
            raise SourceLifecycleError("event must be a SourceLifecycleEvent")
        payload = _canonical_json(event.model_dump(mode="json"))
        async with self._runtime._context(self.scope_id), self._lock, self._runtime._locked(self.scope_id):
            nodes = await self._load_nodes()
            source = next((node for node in nodes if node.node_id == event.node_id), None)
            if source is None or source.kind != "source":
                raise SourceLifecycleError(f"unknown Source lifecycle node {event.node_id!r}")
            if source.lifecycle_revision != event.revision:
                raise SourceLifecycleError("event revision does not match the registered Source revision")
            if event.sequence < source.event_sequence:
                raise SourceLifecycleError("event sequence must increase monotonically")
            if event.sequence == source.event_sequence:
                if source.event_payload != payload:
                    raise SourceLifecycleError("event sequence was reused with different content")
            else:
                async with self._database.transaction() as connection:
                    await connection.execute(
                        update(SOURCE_LIFECYCLE_NODES_TABLE)
                        .where(
                            SOURCE_LIFECYCLE_NODES_TABLE.c.scope_id == self.scope_id,
                            SOURCE_LIFECYCLE_NODES_TABLE.c.node_id == event.node_id,
                        )
                        .values(
                            available=event.available,
                            event_sequence=event.sequence,
                            event_payload=payload,
                        )
                    )
                nodes = await self._load_nodes()
            states = _effective_availability(nodes)
            await self._persist_availability(nodes, states)
            context = await self._runtime._provider.get(self.scope_id)
            await self._sync_memory(context, nodes, states)
            return sorted(node_id for node_id, available in states.items() if available)

    async def resolve(self, node_id: str, /, *, purpose: str) -> Reference:
        """Resolve an original reference for generation or historical audit."""

        _require_node_id(node_id)
        if not isinstance(purpose, str) or purpose not in {"generation", "audit"}:
            raise SourceLifecycleError(f"unknown lifecycle purpose {purpose!r}")
        nodes = await self._load_nodes()
        node = next((candidate for candidate in nodes if candidate.node_id == node_id), None)
        if node is None:
            raise SourceLifecycleError(f"unknown lifecycle node {node_id!r}")
        if purpose == "generation" and not _effective_availability(nodes).get(node_id, False):
            raise SourceLifecycleError(f"lifecycle node {node_id!r} is unavailable for generation")
        return node.reference

    async def _register_derived(
        self,
        node_id: str,
        kind: Literal["memory", "topic"],
        reference: Reference,
        *,
        parents: tuple[str, ...],
        policy: Policy,
    ) -> None:
        _require_node_id(node_id)
        parent_ids = _validate_parents(node_id, parents, policy)
        expected_type = MemoryCitation if kind == "memory" else ArtifactRef
        if not isinstance(reference, expected_type):
            raise SourceLifecycleError(f"{kind} registration requires an exact {expected_type.__name__}")
        binding = _binding(kind, reference, parent_ids, policy, None)
        async with self._runtime._context(self.scope_id) as context, self._lock, self._runtime._locked(self.scope_id):
            existing = await self._read_node(node_id)
            if existing is not None:
                if (
                    existing.kind != kind
                    or existing.reference != reference
                    or existing.parents != parent_ids
                    or existing.policy != policy
                ):
                    raise SourceLifecycleError(f"node {node_id!r} is already registered with another binding")
                nodes = await self._load_nodes()
                await self._sync_memory(context, nodes, _effective_availability(nodes))
                return
            nodes = await self._load_nodes()
            by_id = {node.node_id: node for node in nodes}
            missing = tuple(parent for parent in parent_ids if parent not in by_id)
            if missing:
                raise SourceLifecycleError(f"missing lifecycle parents: {', '.join(missing)}")
            await self._verify_reference(context, reference)
            parents_state = _effective_availability(nodes)
            available = (
                all(parents_state[parent] for parent in parent_ids)
                if policy == "all"
                else any(parents_state[parent] for parent in parent_ids)
            )
            async with self._database.transaction() as connection:
                await connection.execute(
                    insert(SOURCE_LIFECYCLE_NODES_TABLE).values(
                        scope_id=self.scope_id,
                        node_id=node_id,
                        node_kind=kind,
                        binding=binding,
                        parents=_canonical_json(list(parent_ids)),
                        policy=policy,
                        available=available,
                        lifecycle_revision=None,
                        event_sequence=0,
                        event_payload=None,
                    )
                )
            nodes = await self._load_nodes()
            states = _effective_availability(nodes)
            await self._persist_availability(nodes, states)
            await self._sync_memory(context, nodes, states)

    async def _verify_source(self, source_ref: SourceRef) -> None:
        try:
            async with self._database.transaction() as connection:
                await self._runtime._provider.repositories.sources.get(connection, self.scope_id, source_ref)
        except Exception as error:
            raise SourceLifecycleError("registered Source does not exist or is unreadable") from error

    async def _verify_reference(self, context: Any, reference: Reference) -> None:
        try:
            if isinstance(reference, MemoryCitation):
                memory = await context.artifacts.memory.revision(reference.memory_ref)
                entries = await context.artifacts.memory.entries(memory)
                if not any(
                    entry.entry_id == reference.entry_id
                    and entry.entry_version_id == reference.entry_version_id
                    for entry in entries
                ):
                    raise SourceLifecycleError("Memory citation does not identify an exact entry version")
            elif isinstance(reference, ArtifactRef):
                async with self._database.transaction() as connection:
                    await self._runtime._provider.repositories.artifacts.get(
                        connection,
                        self.scope_id,
                        reference,
                    )
            else:
                raise SourceLifecycleError("unsupported dependency reference")
        except SourceLifecycleError:
            raise
        except Exception as error:
            raise SourceLifecycleError("registered dependency reference does not exist or is unreadable") from error

    async def _sync_memory(
        self,
        context: Any,
        nodes: tuple[_Node, ...],
        states: dict[str, bool],
    ) -> None:
        memory_nodes = tuple(node for node in nodes if node.kind == "memory")
        if not memory_nodes:
            return
        service = context.artifacts.memory
        try:
            current = await service.head(context.artifacts.memory_artifact_id)
        except Exception as error:
            raise SourceLifecycleError("registered Memory artifact is unavailable") from error
        for node in sorted(memory_nodes, key=lambda item: item.node_id.encode("utf-8")):
            citation = node.reference
            if not isinstance(citation, MemoryCitation):
                raise SourceLifecycleError("Memory lifecycle node has an invalid reference")
            entries = {entry.entry_id: entry for entry in await service.entries(current)}
            entry = entries.get(citation.entry_id)
            if entry is None or entry.entry_version_id != citation.entry_version_id:
                raise SourceLifecycleError(
                    f"Memory node {node.node_id!r} no longer matches its registered entry version"
                )
            desired = states.get(node.node_id, False)
            manifest = {item.entry_id: item for item in current.content.manifest.entries}
            is_active = manifest[entry.entry_id].state == "active"
            if desired == is_active:
                continue
            if desired:
                current = await service.reactivate(
                    current,
                    entries=(entry,),
                    reason="source-lifecycle",
                )
            else:
                current = await service.forget(
                    current,
                    entries=(entry,),
                    reason="source-lifecycle",
                )

    async def _load_nodes(self) -> tuple[_Node, ...]:
        async with self._database.transaction() as connection:
            rows = (
                await connection.execute(
                    select(SOURCE_LIFECYCLE_NODES_TABLE).where(
                        SOURCE_LIFECYCLE_NODES_TABLE.c.scope_id == self.scope_id
                    )
                )
            ).mappings().all()
        return tuple(_decode_node(row) for row in rows)

    async def _read_node(self, node_id: str) -> _Node | None:
        async with self._database.transaction() as connection:
            row = (
                await connection.execute(
                    select(SOURCE_LIFECYCLE_NODES_TABLE).where(
                        SOURCE_LIFECYCLE_NODES_TABLE.c.scope_id == self.scope_id,
                        SOURCE_LIFECYCLE_NODES_TABLE.c.node_id == node_id,
                    )
                )
            ).mappings().one_or_none()
        return None if row is None else _decode_node(row)

    async def _persist_availability(self, nodes: tuple[_Node, ...], states: dict[str, bool]) -> None:
        async with self._database.transaction() as connection:
            for node in nodes:
                if node.available != states.get(node.node_id, False):
                    await connection.execute(
                        update(SOURCE_LIFECYCLE_NODES_TABLE)
                        .where(
                            SOURCE_LIFECYCLE_NODES_TABLE.c.scope_id == self.scope_id,
                            SOURCE_LIFECYCLE_NODES_TABLE.c.node_id == node.node_id,
                        )
                        .values(available=states[node.node_id])
                    )


def _decode_node(row: Any) -> _Node:
    kind = row["node_kind"]
    binding = json.loads(bytes(row["binding"]))
    reference_payload = binding["reference"]
    if kind == "source":
        reference: Reference = SourceRef.model_validate(reference_payload)
    elif kind == "memory":
        reference = MemoryCitation.model_validate(reference_payload)
    elif kind == "topic":
        reference = ArtifactRef.model_validate(reference_payload)
    else:
        raise SourceLifecycleError(f"invalid persisted lifecycle node kind {kind!r}")
    parents = tuple(json.loads(bytes(row["parents"])))
    event_payload = None if row["event_payload"] is None else bytes(row["event_payload"])
    return _Node(
        node_id=str(row["node_id"]),
        kind=kind,
        reference=reference,
        parents=parents,
        policy=row["policy"],
        available=bool(row["available"]),
        lifecycle_revision=None if row["lifecycle_revision"] is None else int(row["lifecycle_revision"]),
        event_sequence=int(row["event_sequence"]),
        event_payload=event_payload,
    )


def _effective_availability(nodes: tuple[_Node, ...]) -> dict[str, bool]:
    states = {
        node.node_id: node.available
        for node in nodes
        if node.kind == "source"
    }
    resolved = set(states)
    unresolved = {node.node_id for node in nodes if node.kind != "source"}
    while unresolved:
        progressed = False
        for node in nodes:
            if node.node_id not in unresolved or any(parent not in resolved for parent in node.parents):
                continue
            states[node.node_id] = (
                all(states[parent] for parent in node.parents)
                if node.policy == "all"
                else any(states[parent] for parent in node.parents)
            )
            unresolved.remove(node.node_id)
            resolved.add(node.node_id)
            progressed = True
        if not progressed:
            raise SourceLifecycleError("lifecycle dependencies are missing or cyclic")
    return states


def _binding(
    kind: NodeKind,
    reference: Reference,
    parents: tuple[str, ...],
    policy: Policy,
    revision: int | None,
) -> bytes:
    return _canonical_json(
        {
            "kind": kind,
            "reference": reference.model_dump(mode="json"),
            "parents": list(parents),
            "policy": policy,
            "revision": revision,
        }
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _require_node_id(node_id: str) -> None:
    if not isinstance(node_id, str) or not node_id.strip():
        raise SourceLifecycleError("node_id must be a non-empty, non-whitespace string")
    if len(node_id) > 512:
        raise SourceLifecycleError("node_id must not exceed 512 characters")


def _require_revision(revision: int) -> None:
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise SourceLifecycleError("revision must be a positive integer")


def _validate_parents(node_id: str, parents: tuple[str, ...], policy: Policy) -> tuple[str, ...]:
    if not isinstance(policy, str) or policy not in {"all", "any"}:
        raise SourceLifecycleError("policy must be 'all' or 'any'")
    if not isinstance(parents, tuple) or not parents:
        raise SourceLifecycleError("a derived lifecycle node requires at least one parent")
    if any(not isinstance(parent, str) or not parent.strip() for parent in parents):
        raise SourceLifecycleError("parent node ids must be non-empty strings")
    if any(len(parent) > 512 for parent in parents):
        raise SourceLifecycleError("parent node ids must not exceed 512 characters")
    if len(set(parents)) != len(parents):
        raise SourceLifecycleError("parent node ids must be unique")
    if node_id in parents:
        raise SourceLifecycleError("a lifecycle node cannot depend on itself")
    return tuple(sorted(parents))


__all__ = ["LifecycleApplication", "SourceLifecycleError", "SourceLifecycleEvent", "SourceLifecycleService"]
