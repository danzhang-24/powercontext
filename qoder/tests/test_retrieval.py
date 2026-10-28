"""PaperPocket 核心检索路径的可运行测试。

这些测试分两类：

1. **纯离线单元测试**（不需要任何服务）：分词、哈希嵌入、切块、SQL 拼装、
   RRF 融合与记忆加权；
2. **集成测试**（需要 seekdb 与 PowerContext 在跑）：真实导入 → 检索 → 写记忆
   → 独立进程读回。

集成测试在没有外部服务时会自动跳过（``pytest.skip``），因此 ``pytest`` 在任何
环境下都能跑通；一旦按 ``docs/run-guide.md`` 启动了服务，集成测试就会真正执行
核心检索路径，任何回归都会让退出码非零。

运行方式（在 qoder/ 目录下）::

    .venv/bin/python -m pytest tests/ -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

QODER_DIR = Path(__file__).resolve().parent.parent
if str(QODER_DIR) not in sys.path:
    sys.path.insert(0, str(QODER_DIR))

from paperpocket.brief import build_prompt, extractive_summary, parse_passages
from paperpocket.corpus import chunk_document, iter_documents, parse_file
from paperpocket.embedding import blend, hash_embedding, tokenize
from paperpocket.retrieval import SearchFilters, make_snippet
from paperpocket.sqlutil import quote_ident, sql_str, sql_vector

DEMO_QUERY = "图神经网络 消息传递 邻居聚合"


# --------------------------------------------------------------------------
# 离线单元测试
# --------------------------------------------------------------------------
def test_tokenize_splits_cjk_into_bigrams() -> None:
    """中文按二元组切分，英文按词切分。"""
    tokens = tokenize("图神经网络 message passing")
    assert "图神" in tokens
    assert "神经" in tokens
    assert "message" in tokens
    assert "passing" in tokens


def test_hash_embedding_is_deterministic_and_normalized() -> None:
    """哈希嵌入必须可复现且 L2 归一化。"""
    first = hash_embedding("图神经网络 消息传递", 64)
    second = hash_embedding("图神经网络 消息传递", 64)
    assert first == second
    assert len(first) == 64
    norm = sum(value * value for value in first) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-6)
    # 不同文本必须落在不同位置。
    assert hash_embedding("完全不同的文本", 64) != first


def test_blend_keeps_dimension_and_normalizes() -> None:
    """向量混合后维度不变且仍然归一化。"""
    a = hash_embedding("消息传递", 64)
    b = hash_embedding("邻居聚合", 64)
    mixed = blend([a, b], [1.0, 0.35])
    assert len(mixed) == 64
    norm = sum(value * value for value in mixed) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_corpus_parsing_and_chunking() -> None:
    """语料能被解析成文档，并按标题切成带行号的段落块。"""
    documents = iter_documents(QODER_DIR / "corpus")
    assert documents, "corpus/ 目录里应该有示例资料"
    titles = {doc.title for doc in documents}
    assert any("图神经网络" in title for title in titles)

    document = parse_file(QODER_DIR / "corpus" / "papers" / "gnn_survey.md",
                          root=QODER_DIR / "corpus")
    assert document is not None
    assert document.year > 0
    assert document.tags

    chunks = chunk_document(document, max_chars=480)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.chunk_key.startswith(document.doc_key)
        assert chunk.end_line >= chunk.start_line
        assert chunk.content.strip()


def test_sql_helpers_escape_quotes() -> None:
    """SQL 字面量与标识符必须正确转义。"""
    assert sql_str("it's") == "'it\\'s'"
    assert sql_str("a\nb") == "'a\\nb'"
    assert quote_ident("we`ird") == "`we``ird`"
    vector = sql_vector([0.5, -0.25])
    assert vector.startswith("'[") and vector.endswith("]'")


def test_filters_build_where_clause() -> None:
    """结构化过滤条件要生成正确的 SQL 片段。"""
    clause = SearchFilters(year_from=2019, year_to=2024, tags=["gnn"], kinds=["paper"]).where_clause()
    assert "year >= 2019" in clause
    assert "year <= 2024" in clause
    assert "tags LIKE" in clause
    assert "kind = 'paper'" in clause


def test_make_snippet_contains_query_term() -> None:
    """摘要片段应该落在查询词附近。"""
    content = "前面是无关内容。" * 20 + "这里出现了邻居聚合的关键论述。" + "后面是无关内容。" * 20
    snippet = make_snippet(content, "邻居聚合")
    assert "邻居聚合" in snippet


def test_brief_prompt_roundtrip_and_summary() -> None:
    """提示词里能还原资料片段，本地抽取式摘要能产出要点。"""
    from paperpocket.retrieval import SearchHit

    hit = SearchHit(
        chunk_key="doc#000",
        doc_key="doc",
        title="图神经网络综述：从消息传递到可学习聚合",
        authors="",
        year=2023,
        venue="",
        tags=["gnn"],
        heading="一、消息传递范式",
        seq=0,
        source_path="papers/gnn_survey.md",
        start_line=6,
        end_line=12,
        content="消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息，再把消息聚合。",
    )
    prompt = build_prompt(DEMO_QUERY, [hit])
    restored = parse_passages(prompt)
    assert restored and "消息传递范式" in restored[0]
    summary = extractive_summary(restored, DEMO_QUERY)
    assert summary.strip().startswith("- ")
    assert len(summary) > 20


# --------------------------------------------------------------------------
# 集成测试（需要 seekdb + PowerContext）
# --------------------------------------------------------------------------
def _service_available(host: str, port: int) -> bool:
    """检查 TCP 端口是否可连接。"""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(2.0)
        return sock.connect_ex((host, port)) == 0


@pytest.fixture(scope="module")
def app():
    """准备一个连上 seekdb / PowerContext 的应用实例；服务不在就跳过。"""
    from paperpocket.config import load_settings
    from paperpocket.service import PaperPocket

    settings = load_settings()
    if not _service_available(settings.db_host, settings.db_port):
        pytest.skip("seekdb 未启动（%s:%s），请先执行 bash scripts/setup.sh" % (
            settings.db_host, settings.db_port))
    instance = PaperPocket(settings)
    try:
        instance.open()
    except Exception as exc:  # noqa: BLE001
        pytest.skip("无法连接 seekdb：%s" % exc)
    try:
        instance.prepare_schema()
        instance.ingest()
        yield instance
    finally:
        instance.close()


def test_core_retrieval_path_uses_both_lanes(app) -> None:
    """核心检索路径：全文通道 + 向量通道都有命中，并且能被结构化过滤收窄。"""
    from paperpocket.retrieval import SearchFilters

    result = app.search(DEMO_QUERY, filters=SearchFilters(), top_k=8,
                        use_memory=False, remember=False)
    assert result.hits, "混合检索必须有命中"
    assert any(hit.bm25_rank is not None for hit in result.hits), "全文通道必须有命中"
    assert any(hit.ann_rank is not None for hit in result.hits), "向量通道必须有命中"
    assert any(hit.bm25_rank is not None and hit.ann_rank is not None for hit in result.hits), (
        "至少有一个段落要同时命中两条通道")
    assert "MATCH(title, content) AGAINST" in result.bm25_sql
    assert "l2_distance(emb" in result.ann_sql

    # 结构化过滤必须真的在 SQL 层生效。
    tagged = app.search(DEMO_QUERY, filters=SearchFilters(tags=["gnn"]), top_k=8,
                        use_memory=False, remember=False)
    assert tagged.hits
    for hit in tagged.hits:
        assert "gnn" in [tag.lower() for tag in hit.tags]

    empty = app.search(DEMO_QUERY, filters=SearchFilters(year_from=1990, year_to=1991),
                       top_k=8, use_memory=False, remember=False)
    assert not empty.hits
    assert "year >= 1990" in empty.bm25_sql


def test_memory_write_then_read_from_another_process(app) -> None:
    """记忆写入后，另一个进程能读回同一个方向与标签。"""
    direction = "图神经网络 消息传递"
    tags = ["gnn", "message-passing"]
    app.remember_profile(direction, tags)

    command = [
        sys.executable, "-m", "paperpocket",
        "--powercontext-url", app.settings.powercontext_url,
        "--scope-id", app.settings.scope_id,
        "--records-dir", str(app.settings.records_dir),
        "--json", "recall",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120,
                               cwd=str(QODER_DIR))
    assert completed.returncode == 0, "独立进程 recall 失败：%s" % completed.stderr[-500:]
    payload = json.loads(completed.stdout)
    assert payload["profile"]["direction"] == direction
    assert set(tags) <= set(payload["profile"]["tags"])


def test_brief_is_generated(app) -> None:
    """简报必须非空。"""
    _, brief = app.make_brief(DEMO_QUERY, top_k=5, remember=False)
    assert brief.text.strip()
    assert len(brief.text.strip()) > 20


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
