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

"""Row-level CSV Sources with stable identity and original-record projection."""

from __future__ import annotations

import csv
import io
import json
from urllib.parse import quote

from pydantic import BaseModel, JsonValue, field_validator, model_validator

from powercontext.limits import MAX_SOURCE_ID_LENGTH
from powercontext.sources import (
    TEXT_EVIDENCE_PROJECTION_KEY,
    AdapterSourceDefinition,
    TextEvidence,
)
from powercontext.sources.models import Source, SourceMaterialization

CSV_ROW_SOURCE_NAME = "csv-row"


class CSVDocumentInput(BaseModel):
    """One offline CSV document to split into row-level Sources."""

    document_id: str
    primary_key: str
    content: bytes


class CSVRowInput(BaseModel):
    """One validated CSV record in its original column order."""

    document_id: str
    primary_key: str
    primary_key_value: str
    columns: tuple[str, ...]
    values: tuple[str, ...]

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("document_id must be non-empty without surrounding whitespace")  # noqa: TRY003
        return value

    @field_validator("primary_key")
    @classmethod
    def validate_primary_key(cls, value: str) -> str:
        if not value:
            raise ValueError("primary_key must be non-empty")  # noqa: TRY003
        return value

    @field_validator("primary_key_value")
    @classmethod
    def validate_primary_key_value(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("primary_key_value must be non-empty")  # noqa: TRY003
        return value

    @model_validator(mode="after")
    def validate_row_width(self) -> CSVRowInput:
        if len(self.columns) != len(self.values):
            raise ValueError("columns and values must have the same length")  # noqa: TRY003
        return self


class CSVRowSource(Source):
    """Captured evidence for one CSV record."""

    source_id: str
    document_id: str
    primary_key: str
    primary_key_value: str
    columns: tuple[str, ...]
    values: tuple[str, ...]


def csv_row_source_id(document_id: str, primary_key_value: str) -> str:
    """Build the stable, delimiter-safe identity of one CSV row."""

    if not isinstance(document_id, str) or not document_id or document_id != document_id.strip():
        raise ValueError("document_id must be non-empty without surrounding whitespace")  # noqa: TRY003
    if not isinstance(primary_key_value, str) or not primary_key_value:
        raise ValueError("primary_key_value must be non-empty")  # noqa: TRY003
    source_id = f"csv:{quote(document_id, safe='')}:{quote(primary_key_value, safe='')}"
    if len(source_id) > MAX_SOURCE_ID_LENGTH:
        raise ValueError(
            f"csv row source id exceeds {MAX_SOURCE_ID_LENGTH} characters"
        )  # noqa: TRY003
    return source_id


def parse_csv_document(value: CSVDocumentInput) -> tuple[CSVRowInput, ...]:
    """Parse and fully validate one CSV document before returning any row."""

    if not isinstance(value.document_id, str) or not value.document_id or value.document_id != value.document_id.strip():
        raise ValueError("document_id must be non-empty without surrounding whitespace")  # noqa: TRY003
    if not isinstance(value.primary_key, str) or not value.primary_key:
        raise ValueError("primary_key must be non-empty")  # noqa: TRY003
    try:
        text = value.content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV document must be valid UTF-8") from exc

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValueError("CSV document must contain a header") from exc
    except csv.Error as exc:
        raise ValueError("malformed CSV header") from exc
    if not header:
        raise ValueError("CSV header must not be empty")  # noqa: TRY003
    if any(not column or not column.strip() for column in header):
        raise ValueError("CSV header fields must be non-empty and not blank")  # noqa: TRY003
    if len(set(header)) != len(header):
        raise ValueError("CSV header fields must be unique")  # noqa: TRY003
    try:
        primary_index = header.index(value.primary_key)
    except ValueError as exc:
        raise ValueError("primary_key must match a CSV header field exactly") from exc

    rows: list[CSVRowInput] = []
    seen_keys: set[str] = set()
    try:
        for record in reader:
            if not record:
                # A completely empty physical record carries no data.
                continue
            if len(record) != len(header):
                raise ValueError("CSV record width must match the header")  # noqa: TRY003
            primary_key_value = record[primary_index]
            if not primary_key_value or not primary_key_value.strip():
                raise ValueError("CSV primary key value must be non-empty")  # noqa: TRY003
            if primary_key_value in seen_keys:
                raise ValueError("CSV primary key values must be unique per document")  # noqa: TRY003
            seen_keys.add(primary_key_value)
            rows.append(
                CSVRowInput(
                    document_id=value.document_id,
                    primary_key=value.primary_key,
                    primary_key_value=primary_key_value,
                    columns=tuple(header),
                    values=tuple(record),
                )
            )
    except csv.Error as exc:
        raise ValueError("malformed CSV document") from exc

    return tuple(rows)


class CSVRowSourceAdapter:
    """Resolve and read row-level CSV Sources."""

    input_class = CSVRowInput
    name = CSV_ROW_SOURCE_NAME
    source_class = CSVRowSource

    async def resolve(self, value: CSVRowInput, /) -> CSVRowSource:
        source_id = csv_row_source_id(value.document_id, value.primary_key_value)
        return CSVRowSource(
            name=source_id,
            source_id=source_id,
            materialization=SourceMaterialization.CAPTURED,
            document_id=value.document_id,
            primary_key=value.primary_key,
            primary_key_value=value.primary_key_value,
            columns=value.columns,
            values=value.values,
        )

    async def read(self, source: CSVRowSource, /) -> CSVRowInput:
        return CSVRowInput(
            document_id=source.document_id,
            primary_key=source.primary_key,
            primary_key_value=source.primary_key_value,
            columns=source.columns,
            values=source.values,
        )


class CSVRowTextEvidenceProjection:
    """Expose one CSV record as canonical textual evidence."""

    name = TEXT_EVIDENCE_PROJECTION_KEY.name
    version = TEXT_EVIDENCE_PROJECTION_KEY.version
    source_class = CSVRowSource
    output_class: type[BaseModel] = TextEvidence

    def project(self, source: CSVRowSource, /) -> TextEvidence:
        row: dict[str, str] = {
            column: value
            for column, value in zip(source.columns, source.values, strict=True)
        }
        metadata: dict[str, JsonValue] = {
            "document_id": source.document_id,
            "primary_key": source.primary_key,
            "primary_key_value": source.primary_key_value,
            "columns": list(source.columns),
            "row": row,
        }
        return TextEvidence(
            source_type=CSV_ROW_SOURCE_NAME,
            source_id=source.source_id,
            content=json.dumps(row, ensure_ascii=False, separators=(",", ":")),
            metadata=metadata,
        )


CSV_ROW_SOURCE_ADAPTER = CSVRowSourceAdapter()
CSV_ROW_SOURCE_DEFINITION = AdapterSourceDefinition(
    CSV_ROW_SOURCE_ADAPTER,
    version="1",
    projections=(CSVRowTextEvidenceProjection(),),
)

__all__ = [
    "CSV_ROW_SOURCE_DEFINITION",
    "CSVDocumentInput",
    "CSVRowInput",
    "CSVRowSource",
    "csv_row_source_id",
    "parse_csv_document",
]
