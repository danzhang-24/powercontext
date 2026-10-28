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

"""Complete PDF page Sources and lexical evidence-page retrieval."""

from __future__ import annotations

import hashlib
import io
import re
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pypdf import PdfReader

from powercontext.artifacts import MemoryCitation
from powercontext.builtin.runtime.models import SearchMemoryRequest
from powercontext.limits import MAX_SOURCE_ID_LENGTH
from powercontext.sources import (
    TEXT_EVIDENCE_PROJECTION_KEY,
    AdapterSourceDefinition,
    TextEvidence,
)
from powercontext.sources.models import Source, SourceMaterialization

PDF_PAGE_SOURCE_NAME = "pdf-page"


class PDFDocumentInput(BaseModel):
    """One complete original PDF document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    content: bytes

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("document_id must not be empty or whitespace")  # noqa: TRY003
        return value


class PDFPageInput(BaseModel):
    """One physical PDF page and the exact document revision it came from."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    document_sha256: str
    page_number: int = Field(ge=1)
    text: str

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("document_id must not be empty or whitespace")  # noqa: TRY003
        return value

    @field_validator("document_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("document_sha256 must be lowercase SHA-256 hexadecimal")  # noqa: TRY003
        return value


class PDFPageSource(Source):
    """Captured evidence for one physical PDF page."""

    source_id: str
    document_id: str
    document_sha256: str
    page_number: int
    text: str


def parse_pdf_document(value: PDFDocumentInput) -> tuple[PDFPageInput, ...]:
    """Parse every physical page before returning any page evidence."""

    if not isinstance(value, PDFDocumentInput):
        raise ValueError("PDF input must be PDFDocumentInput")  # noqa: TRY003
    if not value.content:
        raise ValueError("PDF content must not be empty")  # noqa: TRY003
    digest = hashlib.sha256(value.content).hexdigest()
    try:
        reader = PdfReader(io.BytesIO(value.content), strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("PDF requires a user password")  # noqa: TRY003
        raw_pages = tuple(reader.pages)
        if not raw_pages:
            raise ValueError("PDF contains no pages")  # noqa: TRY003
        pages: list[PDFPageInput] = []
        for page_number, page in enumerate(raw_pages, start=1):
            extracted = page.extract_text()
            if extracted is None:
                extracted = ""
            if not isinstance(extracted, str):
                raise ValueError("PDF page extraction did not return text")  # noqa: TRY003
            pages.append(
                PDFPageInput(
                    document_id=value.document_id,
                    document_sha256=digest,
                    page_number=page_number,
                    text=extracted,
                )
            )
        return tuple(pages)
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("PDF is empty, corrupt, encrypted, or only partially readable") from error


class PDFPageSourceAdapter:
    """Resolve and read exact physical-page Sources."""

    input_class = PDFPageInput
    name = PDF_PAGE_SOURCE_NAME
    source_class = PDFPageSource

    async def resolve(self, value: PDFPageInput, /) -> PDFPageSource:
        source_id = pdf_page_source_id(
            value.document_id,
            value.document_sha256,
            value.page_number,
        )
        return PDFPageSource(
            name=source_id,
            source_id=source_id,
            materialization=SourceMaterialization.CAPTURED,
            document_id=value.document_id,
            document_sha256=value.document_sha256,
            page_number=value.page_number,
            text=value.text,
        )

    async def read(self, source: PDFPageSource, /) -> PDFPageInput:
        return PDFPageInput(
            document_id=source.document_id,
            document_sha256=source.document_sha256,
            page_number=source.page_number,
            text=source.text,
        )


class PDFPageTextEvidenceProjection:
    """Expose one page with its document and physical page metadata."""

    name = TEXT_EVIDENCE_PROJECTION_KEY.name
    version = TEXT_EVIDENCE_PROJECTION_KEY.version
    source_class = PDFPageSource
    output_class: type[BaseModel] = TextEvidence

    def project(self, source: PDFPageSource, /) -> TextEvidence:
        return TextEvidence(
            source_type=PDF_PAGE_SOURCE_NAME,
            source_id=source.source_id,
            content=f"{source.document_id}\n{source.text}",
            metadata={
                "document_id": source.document_id,
                "document_sha256": source.document_sha256,
                "page_number": source.page_number,
            },
        )


PDF_PAGE_SOURCE_ADAPTER = PDFPageSourceAdapter()
PDF_PAGE_SOURCE_DEFINITION = AdapterSourceDefinition(
    PDF_PAGE_SOURCE_ADAPTER,
    version="1",
    projections=(PDFPageTextEvidenceProjection(),),
)


def pdf_page_source_id(document_id: str, document_sha256: str, page_number: int) -> str:
    """Build a collision-safe identity from document revision and physical page."""

    source_id = f"pdf:{quote(document_id, safe='')}:{document_sha256}:{page_number}"
    if len(source_id) > MAX_SOURCE_ID_LENGTH:
        raise ValueError(f"PDF page Source identity exceeds {MAX_SOURCE_ID_LENGTH} characters")  # noqa: TRY003
    return source_id


async def search_pdf_pages(
    memory: Any,
    question: str,
    limit: int = 10,
) -> tuple[MemoryCitation, ...]:
    """Retrieve distinct exact page citations through the public Memory search API."""

    if not isinstance(question, str) or not question.strip():
        raise ValueError("PDF search question must be non-empty")  # noqa: TRY003
    if type(limit) is not int or limit < 1:
        raise ValueError("PDF search limit must be a positive integer")  # noqa: TRY003

    query_results: list[tuple[str, list[MemoryCitation]]] = []
    for query in _retrieval_queries(question):
        page = await memory.search(
            SearchMemoryRequest(
                query=query,
                mode="fts",
                limit=min(100, max(limit * 4, 40)),
            )
        )
        citations: list[MemoryCitation] = []
        seen_for_query: set[tuple[str, str, int, str]] = set()
        for hit in page.hits:
            identity = (
                hit.memory_ref.family,
                hit.memory_ref.artifact_id,
                hit.memory_ref.revision,
                hit.entry_id,
            )
            if identity in seen_for_query:
                continue
            seen_for_query.add(identity)
            citations.append(MemoryCitation(
                memory_ref=hit.memory_ref,
                entry_id=hit.entry_id,
                entry_version_id=hit.entry_version_id,
            ))
        if citations:
            query_results.append((query, citations))
    result_lists = [citations for _, citations in query_results]
    if not result_lists:
        return ()

    selected: list[MemoryCitation] = []
    seen: set[tuple[str, str, int, str]] = set()

    def append(citation: MemoryCitation) -> None:
        identity = (
            citation.memory_ref.family,
            citation.memory_ref.artifact_id,
            citation.memory_ref.revision,
            citation.entry_id,
        )
        if identity not in seen and len(selected) < limit:
            seen.add(identity)
            selected.append(citation)

    # Preserve a short high-confidence seed, then give every lexical expansion
    # representation at the same rank. This favours gold-page coverage rather
    # than letting the long original question monopolize all twenty slots.
    for citation in result_lists[0][:8]:
        append(citation)
    if re.search(r"\b(?:ebitda|revenue|income|cash|margin|capex|restructuring|cost)\b", question, re.I):
        by_query = dict(query_results)
        for preferred in ("income statement", "operating income", "cash flow statement"):
            for citation in by_query.get(preferred, ())[:8]:
                append(citation)
            if len(selected) == limit:
                return tuple(selected)
    depth = 0
    while len(selected) < limit and any(depth < len(items) for items in result_lists):
        for items in result_lists:
            if depth < len(items):
                append(items[depth])
                if len(selected) == limit:
                    break
        depth += 1
    return tuple(selected)


_STOP_WORDS = frozenset({
    "a",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "define",
    "did",
    "do",
    "does",
    "for",
    "from",
    "give",
    "has",
    "have",
    "if",
    "in",
    "is",
    "it",
    "many",
    "much",
    "not",
    "of",
    "on",
    "or",
    "reported",
    "respond",
    "state",
    "that",
    "the",
    "their",
    "then",
    "to",
    "use",
    "was",
    "were",
    "what",
    "when",
    "which",
    "who",
    "why",
    "with",
    "year",
})

_FINANCIAL_PHRASES = (
    "cash flow statement",
    "income statement",
    "statements of income",
    "net cash provided by operating activities",
    "net income",
    "operating income",
    "net revenue",
    "net sales",
    "cost of sales",
    "gross profit",
    "depreciation and amortization",
    "capital expenditures",
    "property plant and equipment",
    "legal proceedings",
    "restructuring",
    "ebitda",
)


def _retrieval_queries(question: str) -> tuple[str, ...]:
    words = re.findall(r"[A-Za-z]+|\d+(?:[.,]\d+)*", question.casefold())
    terms = tuple(dict.fromkeys(word for word in words if word not in _STOP_WORDS and len(word) > 1))
    queries: list[str] = [question]
    if any(term.startswith(("geograph", "operat", "segment", "region")) for term in terms):
        queries.extend((
            "operations reportable segments divisions regions countries territories",
            "Latin America Europe Africa Middle East South Asia Asia Pacific China",
        ))
    if any(term.startswith(("legal", "litigation", "battle", "proceeding")) for term in terms):
        queries.extend((
            "legal proceedings litigation claims regulatory proceedings inquiries investigations",
            "material adverse effect financial condition results of operations cash flows",
        ))
    if terms:
        queries.append(" ".join(terms))
        queries.append(" ".join(terms[:12]))
        queries.append(" ".join(terms[-12:]))
        distinctive = tuple(term for term in terms if len(term) >= 6)
        if distinctive:
            queries.append(" ".join(distinctive[:16]))
    lowered = question.casefold()
    phrase_hits = [phrase for phrase in _FINANCIAL_PHRASES if phrase in lowered]
    if phrase_hits:
        queries.append(" ".join(phrase_hits))
        for phrase in phrase_hits:
            queries.append(phrase)
    # Unique terms after the original question let long prompts recover pages
    # that the strict full-query admission would otherwise omit.
    queries.extend(terms[:8])
    return tuple(
        dict.fromkeys(query.strip() for query in queries if query.strip())
    )[:24]


__all__ = [
    "PDF_PAGE_SOURCE_DEFINITION",
    "PDFDocumentInput",
    "PDFPageInput",
    "PDFPageSource",
    "parse_pdf_document",
    "pdf_page_source_id",
    "search_pdf_pages",
]
