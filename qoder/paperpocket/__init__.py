"""PaperPocket——基于 seekdb 混合检索 + PowerContext 记忆的研究资料助手。

模块职责：

- :mod:`paperpocket.config` 运行期配置（数据库、PowerContext、模型服务）。
- :mod:`paperpocket.db` seekdb（MySQL 协议）访问层，并记录每一条真实执行的 SQL。
- :mod:`paperpocket.schema` 表结构、全文索引与向量索引的建表语句。
- :mod:`paperpocket.corpus` 论文 / 笔记的解析与切分。
- :mod:`paperpocket.embedding` 向量化（本地确定性嵌入 + seekdb ``AI_EMBED`` 通道）。
- :mod:`paperpocket.retrieval` 混合检索（BM25 全文 + 向量 ANN + 结构化过滤 + 融合排序）。
- :mod:`paperpocket.memory` PowerContext 记忆读写（研究方向、检索历史、阅读进度）。
- :mod:`paperpocket.brief` 简报生成（seekdb ``AI_COMPLETE`` + 本地抽取式降级）。
- :mod:`paperpocket.records` 技术使用记录输出。
- :mod:`paperpocket.demo` 端到端演示编排。
- :mod:`paperpocket.cli` 命令行入口。
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["__version__"]
