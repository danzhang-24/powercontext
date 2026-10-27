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

"""Coalesce concurrent embedding requests and cache successful vectors."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Iterable
from typing import Any

from powercontext.builtin.inference.models import (
    EmbeddingResult,
    EmbeddingVector,
    InferenceUsage,
)
from powercontext.builtin.inference.protocols import EmbeddingModel


class _BatchError:
    """Carry one failing batch's exception to every dependent waiter."""

    __slots__ = ("error",)

    def __init__(self, error: BaseException) -> None:
        self.error = error


class CoalescingEmbeddingModel:
    """Share in-flight embedding work and retain successful vectors in an LRU."""

    def __init__(
        self,
        model: EmbeddingModel,
        *,
        max_batch_size: int = 64,
        coalesce_ms: float = 5.0,
        cache_size: int = 1024,
    ) -> None:
        if max_batch_size < 1:
            raise ValueError("max_batch_size must be at least 1")  # noqa: TRY003
        if coalesce_ms < 0:
            raise ValueError("coalesce_ms must not be negative")  # noqa: TRY003
        if cache_size < 0:
            raise ValueError("cache_size must not be negative")  # noqa: TRY003
        self._model = model
        self.profile = model.profile
        self._max_batch_size = max_batch_size
        self._coalesce_seconds = coalesce_ms / 1000.0
        self._cache_size = cache_size
        self._cache: OrderedDict[str, EmbeddingVector] = OrderedDict()
        self._inflight: dict[str, asyncio.Future[EmbeddingVector]] = {}
        self._pending: OrderedDict[str, asyncio.Future[EmbeddingVector]] = OrderedDict()
        self._flush_handle: asyncio.TimerHandle | None = None
        self._next_batch_id = 0

    async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
        texts = tuple(texts)
        if not texts:
            return EmbeddingResult(vectors=(), usage=InferenceUsage(requests=0))

        unique_texts = tuple(dict.fromkeys(texts))
        vectors: dict[str, EmbeddingVector] = {}
        futures_by_text: dict[str, asyncio.Future[EmbeddingVector]] = {}

        for text in unique_texts:
            if self._cache_size > 0 and text in self._cache:
                vectors[text] = self._cache.pop(text)
                self._cache[text] = vectors[text]
            else:
                future = self._inflight.get(text)
                if future is None:
                    future = asyncio.get_running_loop().create_future()
                    self._inflight[text] = future
                    self._pending[text] = future
                futures_by_text[text] = future

        if self._pending:
            self._schedule_flush()

        usage_by_batch: dict[int, InferenceUsage] = {}
        for text in unique_texts:
            if text in vectors:
                continue
            future = futures_by_text.get(text)
            if future is None:
                raise RuntimeError("embedding result disappeared while waiting")  # noqa: TRY003
            vector = await asyncio.shield(future)
            vectors[text] = vector
            batch_id = getattr(future, "batch_id", None)
            batch_usage = getattr(future, "batch_usage", None)
            if batch_id is not None and batch_usage is not None:
                usage_by_batch[batch_id] = batch_usage

        ordered = tuple(vectors[text] for text in texts)
        return EmbeddingResult(vectors=ordered, usage=_sum_usage(usage_by_batch.values()))

    def _schedule_flush(self) -> None:
        if self._flush_handle is None:
            loop = asyncio.get_running_loop()
            self._flush_handle = loop.call_later(self._coalesce_seconds, self._flush_pending)

    def _flush_pending(self) -> None:
        self._flush_handle = None
        if not self._pending:
            return
        batch_texts: list[str] = []
        while self._pending and len(batch_texts) < self._max_batch_size:
            text, future = self._pending.popitem(last=False)
            batch_texts.append(text)
        self._next_batch_id += 1
        batch_id = self._next_batch_id
        asyncio.get_running_loop().create_task(self._run_batch(batch_id, tuple(batch_texts)))
        if self._pending:
            # The coalescing window has already elapsed for the rest.
            asyncio.get_running_loop().call_soon(self._flush_pending)

    async def _run_batch(self, batch_id: int, texts: tuple[str, ...]) -> None:
        try:
            result = await self._model.embed(texts)
            if len(result.vectors) != len(texts):
                raise ValueError("embedding vector count does not match batch size")  # noqa: TRY003
        except BaseException as exc:  # noqa: BLE001
            for text in texts:
                future = self._inflight.pop(text, None)
                if future is not None and not future.done():
                    future.set_exception(exc)
            if not isinstance(exc, Exception):
                raise
            return

        for text, vector in zip(texts, result.vectors, strict=True):
            future = self._inflight.pop(text, None)
            if self._cache_size > 0:
                self._cache.pop(text, None)
                self._cache[text] = vector
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
            if future is not None and not future.done():
                future.batch_id = batch_id
                future.batch_usage = result.usage
                future.set_result(vector)


def _sum_usage(usages: Iterable[InferenceUsage]) -> InferenceUsage:
    requests = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    for usage in usages:
        requests += usage.requests
        if usage.input_tokens is not None:
            input_tokens = (input_tokens or 0) + usage.input_tokens
        if usage.output_tokens is not None:
            output_tokens = (output_tokens or 0) + usage.output_tokens
    return InferenceUsage(
        requests=requests,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


__all__ = ["CoalescingEmbeddingModel"]
