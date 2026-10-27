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

"""HTTP cross-encoder reranking with strict response validation."""

from __future__ import annotations

import math
from collections.abc import Mapping

import httpx

from powercontext.builtin.artifacts.memory.models import MemoryHit
from powercontext.builtin.artifacts.memory.reranking import (
    MemoryRerankDecision,
    MemoryReranker,
    _validate_bounds,
)
from powercontext.builtin.inference import InferenceUsage


class HTTPMemoryReranker(MemoryReranker):
    """Score bounded candidate batches through a caller-owned HTTP client."""

    def __init__(
        self,
        endpoint: str,
        *,
        client: httpx.AsyncClient,
        batch_size: int = 32,
        policy_id: str = "http-cross-encoder-v1",
    ) -> None:
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")  # noqa: TRY003
        self._endpoint = endpoint
        self._client = client
        self._batch_size = batch_size
        self.policy_id = policy_id

    async def rerank(
        self,
        query: str,
        candidates: tuple[MemoryHit, ...],
        limit: int,
        /,
    ) -> MemoryRerankDecision:
        """Score every candidate once and select one globally stable prefix."""

        _validate_bounds(len(candidates), limit)
        if not isinstance(query, str) or not query:
            raise ValueError("rerank query must be a non-empty string")  # noqa: TRY003

        scores: dict[int, float] = {}
        requests = 0
        for offset in range(0, len(candidates), self._batch_size):
            batch = candidates[offset : offset + self._batch_size]
            expected_ranks = set(range(offset + 1, offset + len(batch) + 1))
            payload = {
                "query": query,
                "candidates": [
                    {"rank": rank, "text": candidate.text}
                    for rank, candidate in zip(
                        range(offset + 1, offset + len(batch) + 1),
                        batch,
                        strict=True,
                    )
                ],
            }
            response = await self._client.post(self._endpoint, json=payload)
            requests += 1
            response.raise_for_status()
            batch_scores = _parse_scores(response, expected_ranks)
            scores.update(batch_scores)

        selected = tuple(
            rank
            for rank, _ in sorted(
                scores.items(),
                key=lambda item: (-item[1], item[0]),
            )[:limit]
        )
        return MemoryRerankDecision(
            selected_ranks=selected,
            usage=InferenceUsage(requests=requests),
        )


def _parse_scores(response: httpx.Response, expected_ranks: set[int]) -> dict[int, float]:
    payload = response.json()
    if not isinstance(payload, dict) or set(payload) != {"scores"}:
        raise ValueError("reranker response must contain exactly 'scores'")  # noqa: TRY003
    records = payload["scores"]
    if not isinstance(records, list):
        raise ValueError("reranker scores must be a list")  # noqa: TRY003

    scores: dict[int, float] = {}
    for record in records:
        if not isinstance(record, Mapping) or set(record) != {"rank", "score"}:
            raise ValueError("each reranker score must contain exactly 'rank' and 'score'")  # noqa: TRY003
        rank = record["rank"]
        score = record["score"]
        if not isinstance(rank, int) or isinstance(rank, bool):
            raise ValueError("reranker rank must be an integer")  # noqa: TRY003
        if rank in scores:
            raise ValueError("reranker response contains a duplicate rank")  # noqa: TRY003
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise ValueError("reranker score must be numeric")  # noqa: TRY003
        normalized_score = float(score)
        if not math.isfinite(normalized_score):
            raise ValueError("reranker score must be finite")  # noqa: TRY003
        scores[rank] = normalized_score

    if set(scores) != expected_ranks:
        raise ValueError("reranker response ranks must exactly cover the request batch")  # noqa: TRY003
    return scores


__all__ = ["HTTPMemoryReranker"]
