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
"""简报生成：seekdb ``AI_COMPLETE`` + 本地抽取式降级。

检索到的段落会被拼成提示词，交给 seekdb 的 ``AI_COMPLETE`` 函数——它由数据库
内部调用已注册的模型端点（OpenAI 兼容协议）。当服务端没有可用的模型端点时，
模块退回到本地的确定性抽取式摘要，保证在任何环境里都能产出简报。

项目自带一个本地 OpenAI 兼容模型服务（``paperpocket/model_server.py``），
演示时把它注册到 seekdb 上，因此 ``AI_COMPLETE`` 走的是真实链路。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .db import SeekDB
from .retrieval import SearchHit
from .sqlutil import sql_str

#: 提示词里资料片段的起始标记。
PASSAGE_MARK = "【资料片段】"
PASSAGE_END_MARK = "【要求】"

#: 句子结束符（中英文）。
_SENTENCE_END = "。！？!?;；\n"


def build_prompt(query: str, hits: Iterable[SearchHit], max_chars: int = 160) -> str:
    """把检索结果拼成简报提示词。"""
    blocks: list[str] = []
    for index, hit in enumerate(hits, start=1):
        excerpt = hit.content[:max_chars].strip()
        blocks.append(
            f"{index}. 《{hit.title}》 {hit.source_path}:{hit.start_line}-{hit.end_line}\n{excerpt}"
        )
    passage_text = "\n\n".join(blocks) if blocks else "（没有检索到资料）"
    return (
        f"请根据下面的检索结果，用中文写一段不超过 200 字的研究简报。\n\n"
        f"【检索词】\n{query}\n\n"
        f"{PASSAGE_MARK}\n{passage_text}\n\n"
        f"{PASSAGE_END_MARK}\n"
        "1. 只使用上面给出的资料，不要编造结论；\n"
        "2. 给出 3-5 条要点，每条一行，以「- 」开头；\n"
        "3. 末尾用一行标注主要来源文件。"
    )


def parse_passages(prompt: str) -> list[str]:
    """从提示词中还原资料片段（本地模型服务与降级实现共用）。"""
    if PASSAGE_MARK not in prompt:
        return []
    body = prompt.split(PASSAGE_MARK, 1)[1]
    if PASSAGE_END_MARK in body:
        body = body.split(PASSAGE_END_MARK, 1)[0]
    passages = [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]
    cleaned: list[str] = []
    for passage in passages:
        cleaned.append(re.sub(r"^\d+\.\s*", "", passage))
    return cleaned


def split_sentences(text: str) -> list[str]:
    """把文本切成句子。"""
    sentences: list[str] = []
    buffer = ""
    for char in text:
        buffer += char
        if char in _SENTENCE_END:
            stripped = buffer.strip()
            if stripped:
                sentences.append(stripped)
            buffer = ""
    tail = buffer.strip()
    if tail:
        sentences.append(tail)
    return sentences


def extractive_summary(passages: list[str], query: str, max_points: int = 5) -> str:
    """本地抽取式摘要：按与检索词的重合度挑选要点。

    完全确定性，不依赖任何外部服务，用于无模型端点时的降级路径。
    """
    from .embedding import tokenize

    query_tokens = {token for token in tokenize(query) if len(token) >= 2}
    candidates: list[tuple[float, str, str]] = []
    for passage in passages:
        title = ""
        body = passage
        if "\n" in passage:
            head, _, rest = passage.partition("\n")
            title = head.strip()
            body = rest
        for sentence in split_sentences(body):
            cleaned = sentence.strip()
            if len(cleaned) < 8:
                continue
            tokens = {token for token in tokenize(cleaned) if len(token) >= 2}
            overlap = len(query_tokens & tokens)
            score = overlap + min(len(cleaned), 200) / 1000.0
            candidates.append((score, title, cleaned))
    candidates.sort(key=lambda item: (-item[0], item[2]))
    selected = candidates[:max_points]
    lines = [f"- {sentence}" for _, _, sentence in selected]
    sources: list[str] = []
    for _, title, _ in selected:
        if title and title not in sources:
            sources.append(title)
    if sources:
        lines.append("来源：" + "；".join(sources[:3]))
    if not lines:
        lines.append("- （检索结果为空，无法生成简报）")
    return "\n".join(lines)


@dataclass
class BriefResult:
    """一次简报生成的结果。"""

    text: str
    engine: str
    model: str = ""
    error: str = ""
    passages: list[str] = field(default_factory=list)
    sql: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转成可 JSON 序列化的字典。"""
        return {
            "text": self.text,
            "engine": self.engine,
            "model": self.model,
            "error": self.error,
            "sql": self.sql,
        }


class BriefGenerator:
    """简报生成器。"""

    def __init__(self, db: SeekDB, model: str = "pp_summarizer") -> None:
        self.db = db
        self.model = model

    def model_available(self) -> bool:
        """判断 seekdb 端是否已注册摘要模型与端点。"""
        try:
            models = self.db.query(
                "SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = " + sql_str(self.model),
                note="探测摘要模型是否已注册",
            )
            endpoints = self.db.query(
                "SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS "
                "WHERE AI_MODEL_NAME = " + sql_str(self.model),
                note="探测摘要端点是否已注册",
            )
        except Exception:  # noqa: BLE001 - 缺少 AI 元数据表时视为不可用
            return False
        return bool(models) and bool(endpoints)

    def generate(self, query: str, hits: list[SearchHit], use_ai: bool = True) -> BriefResult:
        """生成简报：优先走 seekdb ``AI_COMPLETE``，失败时本地降级。"""
        prompt = build_prompt(query, hits)
        passages = parse_passages(prompt)
        if use_ai and self.model_available():
            sql = (
                f"SELECT AI_COMPLETE({sql_str(self.model)}, {sql_str(prompt)}) AS brief"
            )
            try:
                self.db.step("简报生成-AI_COMPLETE")
                rows = self.db.query(sql, note="seekdb AI_COMPLETE 生成简报")
                if rows and rows[0].get("brief"):
                    return BriefResult(
                        text=str(rows[0]["brief"]),
                        engine="seekdb-ai-complete",
                        model=self.model,
                        passages=passages,
                        sql=sql,
                    )
            except Exception as exc:  # noqa: BLE001 - 模型不可用时降级
                fallback = extractive_summary(passages, query)
                return BriefResult(
                    text=fallback,
                    engine="local-extractive",
                    model=self.model,
                    error=f"AI_COMPLETE 调用失败，已降级为本地抽取式摘要：{exc}",
                    passages=passages,
                    sql=sql,
                )
        fallback = extractive_summary(passages, query)
        reason = "未注册 AI 模型端点" if not self.model_available() else "已禁用 AI 摘要"
        return BriefResult(
            text=fallback,
            engine="local-extractive",
            model=self.model,
            error=f"{reason}，使用本地抽取式摘要",
            passages=passages,
            sql="",
        )
