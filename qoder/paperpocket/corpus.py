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
"""论文 / 笔记的解析与切分。

支持两种输入：

- **Markdown**（推荐）：文件头部用 ``---`` 包裹的简单 front matter 声明元数据，
  正文按标题层级切成段落块（chunk）。
- **纯文本**：没有 front matter 时，用文件名当标题、整篇作为一块。

切分结果保留来源路径与行号区间，检索命中后可以直接定位到原文段落。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

#: front matter 的分隔符。
_FENCE = "---"

#: Markdown 标题行。
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

#: 默认的段落最大字符数（超出后按空行继续切）。
DEFAULT_MAX_CHARS = 480


@dataclass
class Document:
    """一篇被解析出来的资料。"""

    doc_key: str
    title: str
    authors: str
    year: int
    venue: str
    tags: list[str]
    kind: str
    source_path: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def tags_text(self) -> str:
        """以逗号分隔的标签文本（数据库里以字符串保存）。"""
        return ",".join(self.tags)


@dataclass
class Chunk:
    """资料中的一个段落块。"""

    chunk_key: str
    doc_key: str
    title: str
    authors: str
    year: int
    venue: str
    tags: list[str]
    kind: str
    heading: str
    seq: int
    source_path: str
    start_line: int
    end_line: int
    content: str

    @property
    def tags_text(self) -> str:
        """以逗号分隔的标签文本。"""
        return ",".join(self.tags)


def _parse_front_matter(lines: list[str]) -> tuple[dict[str, str], int]:
    """解析 front matter，返回元数据字典与正文起始行号（0 基）。"""
    meta: dict[str, str] = {}
    if not lines or lines[0].strip() != _FENCE:
        return meta, 0
    for index in range(1, len(lines)):
        line = lines[index]
        if line.strip() == _FENCE:
            return meta, index + 1
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip().lower()] = value.strip()
    return meta, 0


def _slug(text: str) -> str:
    """把标题转换成可用于自然键的短标识。"""
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.strip().lower())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned[:64] or "doc"


def _split_long(text: str, max_chars: int) -> list[str]:
    """把过长的段落按空行继续切分。"""
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    buffer = ""
    for paragraph in re.split(r"\n\s*\n", text):
        candidate = paragraph if not buffer else f"{buffer}\n\n{paragraph}"
        if len(candidate) > max_chars and buffer:
            pieces.append(buffer.strip())
            buffer = paragraph
        else:
            buffer = candidate
    if buffer.strip():
        pieces.append(buffer.strip())
    return pieces


def parse_file(path: Path, root: Path | None = None) -> Document | None:
    """解析单个文件，返回 :class:`Document`；空文件返回 ``None``。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    lines = raw.splitlines()
    meta, body_start = _parse_front_matter(lines)
    body = "\n".join(lines[body_start:]).strip()
    if not body:
        return None
    relative = str(path.relative_to(root)) if root else str(path)
    title = meta.get("title") or path.stem
    doc_key = f"{_slug(title)}"
    tags = [tag.strip() for tag in re.split(r"[,，]", meta.get("tags", "")) if tag.strip()]
    year_text = meta.get("year", "0").strip() or "0"
    try:
        year = int(year_text)
    except ValueError:
        year = 0
    return Document(
        doc_key=doc_key,
        title=title,
        authors=meta.get("authors", ""),
        year=year,
        venue=meta.get("venue", ""),
        tags=tags,
        kind=meta.get("kind", "paper" if path.suffix.lower() == ".md" else "note"),
        source_path=relative,
        content=body,
        metadata={key: value for key, value in meta.items() if key not in {"title", "authors", "year", "venue", "tags", "kind"}},
    )


def iter_documents(corpus_dir: Path, suffixes: Iterable[str] = (".md", ".txt")) -> list[Document]:
    """扫描目录下的所有资料文件，按文件名排序返回。"""
    allowed = {suffix.lower() for suffix in suffixes}
    documents: list[Document] = []
    for path in sorted(corpus_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in allowed:
            continue
        document = parse_file(path, root=corpus_dir)
        if document is not None:
            documents.append(document)
    return documents


def chunk_document(document: Document, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    """把一篇资料切成段落块，保留标题层级与行号。"""
    lines = document.content.splitlines()
    chunks: list[Chunk] = []
    heading = ""
    heading_line = 1
    buffer: list[str] = []
    buffer_start = 1

    def flush(end_line: int) -> None:
        nonlocal buffer
        text = "\n".join(buffer).strip()
        buffer = []
        if not text:
            return
        for index, piece in enumerate(_split_long(text, max_chars)):
            chunks.append(
                Chunk(
                    chunk_key=f"{document.doc_key}#{len(chunks):03d}",
                    doc_key=document.doc_key,
                    title=document.title,
                    authors=document.authors,
                    year=document.year,
                    venue=document.venue,
                    tags=list(document.tags),
                    kind=document.kind,
                    heading=heading,
                    seq=len(chunks),
                    source_path=document.source_path,
                    start_line=buffer_start,
                    end_line=end_line,
                    content=piece,
                )
            )
            del index

    for offset, line in enumerate(lines):
        line_no = offset + 1
        match = _HEADING_RE.match(line)
        if match:
            flush(line_no - 1)
            heading = match.group(2).strip()
            heading_line = line_no
            buffer_start = line_no
            continue
        if not buffer:
            buffer_start = line_no
        buffer.append(line)
    flush(len(lines))
    return chunks
