"""向量化：本地确定性嵌入 + seekdb ``AI_EMBED`` 通道。

两条通道：

- **local**：纯 Python 的哈希嵌入（hashing trick）。同一个词永远映射到同一维，
  词频越高权重越大，最后做 L2 归一化。无需任何外部服务，评测环境离线可跑，
  且结果完全可复现。
- **ai**：由 **seekdb 端** 调用 ``AI_EMBED('<模型>', '<文本>')`` 计算向量，
  模型可以指向任意 OpenAI 兼容的 embedding 服务（本项目自带一个本地实现，
  也可以换成真实服务）。此时向量的计算发生在数据库内部，是 seekdb AI 能力
  的直接体现。

两条通道输出的维度必须一致（建表时的 ``vector(N)``），因此由
``PAPERPOCKET_EMBED_DIM`` 统一控制。
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Sequence

from .db import SeekDB
from .sqlutil import sql_str

#: ASCII 词元。
_ASCII_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+#.\-]*")

#: 连续的中日韩字符。
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """把文本切成检索词元（英文按词，中文按二元组）。"""
    lowered = text.lower()
    tokens: list[str] = [match.group(0) for match in _ASCII_TOKEN_RE.finditer(lowered)]
    for segment in _CJK_RE.findall(lowered):
        if len(segment) == 1:
            tokens.append(segment)
            continue
        for index in range(len(segment) - 1):
            tokens.append(segment[index : index + 2])
    return tokens


def _bucket(token: str, dim: int) -> tuple[int, float]:
    """把词元稳定地映射到某一维，并给出符号。"""
    digest = hashlib.md5(token.encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], "big") % dim
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    return index, sign


def hash_embedding(text: str, dim: int) -> list[float]:
    """计算本地确定性哈希嵌入（L2 归一化）。"""
    counts = Counter(tokenize(text))
    vector = [0.0] * dim
    for token, count in counts.items():
        index, sign = _bucket(token, dim)
        vector[index] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def blend(vectors: Sequence[Sequence[float]], weights: Sequence[float]) -> list[float]:
    """把多个向量按权重线性组合后重新归一化。"""
    if not vectors:
        return []
    dim = len(vectors[0])
    result = [0.0] * dim
    for vector, weight in zip(vectors, weights):
        for index in range(min(dim, len(vector))):
            result[index] += vector[index] * weight
    norm = math.sqrt(sum(value * value for value in result))
    if norm == 0.0:
        return result
    return [value / norm for value in result]


class Embedder:
    """按配置选择本地嵌入或 seekdb ``AI_EMBED``。"""

    def __init__(self, db: SeekDB | None = None, dim: int = 64, mode: str = "auto",
                 model: str = "pp_embed") -> None:
        self.db = db
        self.dim = dim
        self.mode = mode
        self.model = model

    # -- 能力探测 ---------------------------------------------------------
    def ai_available(self) -> bool:
        """判断 seekdb 端是否可用 ``AI_EMBED``（模型与端点都已注册）。"""
        if self.db is None or self.mode == "local":
            return False
        try:
            models = self.db.query(
                "SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = " + sql_str(self.model),
                note="探测 AI 模型是否已注册",
            )
            endpoints = self.db.query(
                "SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS "
                "WHERE AI_MODEL_NAME = " + sql_str(self.model),
                note="探测 AI 模型端点是否已注册",
            )
        except Exception:  # noqa: BLE001 - 缺少 AI 元数据表时视为不可用
            return False
        return bool(models) and bool(endpoints)

    # -- 嵌入 -------------------------------------------------------------
    def embed(self, text: str) -> list[float]:
        """在 Python 侧计算向量（本地通道）。"""
        return hash_embedding(text, self.dim)

    def embed_expression(self, text: str) -> str:
        """返回可直接写进 SQL 的向量表达式。

        - ``ai`` 通道：``AI_EMBED('pp_embed', '文本')``，由 seekdb 调用模型服务计算。
        - ``local`` 通道：``'[0.1,0.2,...]'`` 字面量。
        """
        if self.mode in {"auto", "ai"} and self.ai_available():
            return f"AI_EMBED({sql_str(self.model)}, {sql_str(text)})"
        from .sqlutil import sql_vector

        return sql_vector(self.embed(text))
