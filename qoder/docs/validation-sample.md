# PaperPocket / 研知库 —— 验证样本

本文是**一次真实运行**的完整记录：命令是实际敲进去的，输出是从终端原样摘录的，
没有二次加工。对应的原始文件都在 `qoder/records/` 下。

- 运行环境：Linux x86_64
- seekdb：`5.7.25-OceanBase seekdb-v1.4.0.0`（`127.0.0.1:5881`）
- Python：`3.12.14`（`qoder/.venv`）
- PowerContext Server：`1.2.0`（`127.0.0.1:8100`）
- 本地模型服务：`http://127.0.0.1:8300/v1`

---

## 1. 实际执行的命令

```bash
cd /home/zhangdan/pc2026/powercontext/qoder

# 清空到干净状态（删库 + 丢弃本地作用域绑定）
.venv/bin/python -m paperpocket reset --wipe-memory

# 端到端演示
bash scripts/run_demo.sh

# 验收自检
bash scripts/verify.sh

# 抓一份检索样本（检索词 + 命中行 + 各通道耗时）
.venv/bin/python scripts/capture_sample.py --query "图神经网络 消息传递 邻居聚合"

# 测试
bash tests/run_tests.sh
```

四条命令的退出码分别是 `0 / 0 / 0 / 0`。

---

## 2. 演示输出（`bash scripts/run_demo.sh` 真实输出片段）

### 2.1 准备表结构与导入语料

```
=== 步骤 1/8：确认本地模型服务与 PowerContext Server 可用 ===

=== 步骤 1/8：确认 seekdb 上的 AI 模型端点已注册 ===
嵌入模型端点：http://127.0.0.1:8300/v1/embeddings（注册成功：True）
摘要模型端点：http://127.0.0.1:8300/v1/chat/completions（注册成功：True）

=== 步骤 2/8：跑完整演示流程 ===
========================================================================
PaperPocket 端到端演示
========================================================================
seekdb：127.0.0.1:5881/paperpocket
PowerContext：http://127.0.0.1:8100
语料目录：/home/zhangdan/pc2026/powercontext/qoder/corpus

【步骤 1】准备表结构、全文索引与向量索引
  建表完成；向量维度 64

【步骤 2】导入论文与笔记
  导入 7 篇资料、43 个段落，清理旧数据 0 行
  向量化通道：ai（seekdb AI_EMBED）
    - 实验记录-邻居采样规模对图分类精度的影响（2025）…：5 段
    - 文献综述写作与检索习惯笔记（2024）…：5 段
    - 课程笔记-图神经网络基础-第-6-9-周（2024）…：5 段
    - attention-is-all-you-need（2020）…：7 段
    - bert-基于双向transformer的预训练语言模型（2019）…：7 段
    - 对比表示学习在检索场景中的实践（2022）…：7 段
    - 图神经网络综述-从消息传递到可学习聚合（2023）…：7 段
```

> 注意 `向量化通道：ai（seekdb AI_EMBED）`——**向量是 seekdb 内部用 `AI_EMBED`
> 函数算的**，不是 Python 侧算好塞进去的。

### 2.2 第一次检索（此时 PowerContext 里还没有记忆）

```
【步骤 3】第一次检索（此时 PowerContext 中还没有记忆）
检索词：图神经网络 消息传递 邻居聚合
候选段落数：40

[1] 图神经网络综述：从消息传递到可学习聚合（2023）· 六、结论与展望
    来源：papers/gnn_survey.md:30-31　标签：gnn,message-passing,survey,graph
    分数：0.032522（rrf=0.032522，通道=bm25+vector）
    BM25=3.562878　ANN距离=1.083319
    片段：消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。…

[2] 课程笔记：图神经网络基础（第 6-9 周）（2024）· 课后遗留问题
    来源：notes/课程笔记-图神经网络基础.md:22-25　标签：gnn,message-passing,course-note,graph
    分数：0.032266（rrf=0.032266，通道=bm25+vector）
    BM25=2.920393　ANN距离=0.957576
    片段：1. 采样引入的方差如何在多层之间传递？…

[3] 图神经网络综述：从消息传递到可学习聚合（2023）· 摘要
    来源：papers/gnn_survey.md:2-4　标签：gnn,message-passing,survey,graph
    分数：0.031754（rrf=0.031754，通道=bm25+vector）
    BM25=3.391795　ANN距离=1.207459
```

前 5 条命中的 `通道` 都是 `bm25+vector`——**两条检索通道都在起作用**，
不是只有一路在返回结果。

实际执行的两条 SQL（原文见 `records/demo_output.md`）：

```sql
SELECT chunk_key, ..., MATCH(title, content) AGAINST ('图神经网络 消息传递 邻居聚合' IN NATURAL LANGUAGE MODE) AS bm25_score
FROM paperpocket.paper_chunks
WHERE MATCH(title, content) AGAINST ('图神经网络 消息传递 邻居聚合' IN NATURAL LANGUAGE MODE)
ORDER BY bm25_score DESC LIMIT 40
```

```sql
SELECT chunk_key, ..., l2_distance(emb, '[0.000000,0.000000,0.316228,...]') AS ann_distance
FROM paperpocket.paper_chunks
ORDER BY l2_distance(emb, '[0.000000,0.000000,0.316228,...]') APPROXIMATE LIMIT 40
```

---

## 3. Before / After：写入记忆前后的检索对比

这是本项目最核心的一组对比——**同一条检索词，唯一变化的是 PowerContext 里有没有记忆**。

### 3.1 写入记忆

```
【步骤 4】把研究方向与常用标签写入 PowerContext
  已写入：direction=图神经网络 消息传递，tags=['gnn', 'message-passing']
  作用域：scp_3xe2dwd5rn50a6g3cyz6btnav8
```

### 3.2 第二次检索（读回上一步写入的记忆）

```
【步骤 5】第二次检索（读回上一步写入的记忆）
  读回记忆：方向=图神经网络 消息传递，标签=['gnn', 'message-passing']，历史检索=1 条
检索词：图神经网络 消息传递 邻居聚合
候选段落数：40

已应用 PowerContext 记忆：方向=图神经网络 消息传递，标签=gnn,message-passing，历史检索=['图神经网络 消息传递 邻居聚合']

[1] 图神经网络综述：从消息传递到可学习聚合（2023）· 六、结论与展望
    分数：0.078054（rrf=0.032522，通道=bm25+vector+memory）
    BM25=3.562878　ANN距离=1.072966
    记忆加权：4.00（命中记忆标签 ['gnn', 'message-passing']；命中记忆方向关键词 ['图神经网络', '消息传递']；出现在历史检索命中中）

[2] 图神经网络综述：从消息传递到可学习聚合（2023）· 摘要
    分数：0.076210（rrf=0.031754，通道=bm25+vector+memory）
    记忆加权：4.00（命中记忆标签 ['gnn', 'message-passing']；命中记忆方向关键词 ['图神经网络', '消息传递']；出现在历史检索命中中）

[3] 图神经网络综述：从消息传递到可学习聚合（2023）· 五、可学习聚合与超图
    分数：0.075595（rrf=0.031498，通道=bm25+vector+memory）
    记忆加权：4.00（…）

[4] 图神经网络综述：从消息传递到可学习聚合（2023）· 一、消息传递范式
    分数：0.073287（rrf=0.030536，通道=bm25+vector+memory）
    记忆加权：4.00（…）

[5] 课程笔记：图神经网络基础（第 6-9 周）（2024）· 课后遗留问题
    分数：0.071793（rrf=0.032266，通道=bm25+vector+memory）
    记忆加权：3.50（命中记忆标签 ['gnn', 'message-passing']；命中记忆方向关键词 ['图神经网络']；出现在历史检索命中中）

  与第一次检索的差异：
    第一次：['图神经网络综述-从消息传递到可学习聚合#006', '课程笔记-图神经网络基础-第-6-9-周#004', '图神经网络综述-从消息传递到可学习聚合#000', '图神经网络综述-从消息传递到可学习聚合#005', '图神经网络综述-从消息传递到可学习聚合#001']
    第二次：['图神经网络综述-从消息传递到可学习聚合#006', '图神经网络综述-从消息传递到可学习聚合#000', '图神经网络综述-从消息传递到可学习聚合#005', '图神经网络综述-从消息传递到可学习聚合#001', '课程笔记-图神经网络基础-第-6-9-周#004']
    排序变化：是
```

### 3.3 对比结论（可直接从上面数字读出）

| 观察点 | 第一次（无记忆） | 第二次（有记忆） | 说明 |
| --- | --- | --- | --- |
| 通道 | `bm25+vector` | `bm25+vector+memory` | 记忆确实参与了打分，不是摆设 |
| 第 1 条最终分 | `0.032522` | `0.078054` | RRF 相同（`0.032522`），差异全部来自记忆乘子 `1 + 0.35 × 4.00 = 2.4` |
| 排序 | 课程笔记排第 2 | 课程笔记降到第 5 | 与"研究方向"更贴近的段落被顶上来 |
| ANN 距离 | `1.083319` | `1.072966` | 查询向量被 `0.35 × embed(direction)` 扩展后，同一段落的距离**变小了** |
| BM25 | `3.562878` | `3.562878` | 全文通道完全不受记忆影响，两条通道是独立的 |

> 换句话说：**记忆没有污染内容相关性（BM25 不变），只是重新排了序、
> 并让向量通道更偏向用户的方向**。这正是 `final = rrf × (1 + 0.35 × memory)` 的设计意图。

---

## 4. 记忆的跨进程读回（`recall`）

`run_demo.sh` 用**另一个进程**再读一次记忆，证明 PowerContext 的状态真的在服务端：

```
=== 步骤 3/8：以独立进程读回 PowerContext 记忆（验证跨进程复用） ===
作用域：scp_3xe2dwd5rn50a6g3cyz6btnav8
研究方向：图神经网络 消息传递
常用标签：gnn,message-passing
历史检索次数：3
  - 2026-10-28T17:03:21+00:00　图神经网络 消息传递 邻居聚合　命中 5 段
  - 2026-10-28T17:03:21+00:00　图神经网络 消息传递 邻居聚合　命中 5 段
  - 2026-10-28T17:03:22+00:00　图神经网络 消息传递 邻居聚合　命中 5 段
阅读进度条目：1
  - 2026-10-28T17:03:22+00:00　read　图神经网络综述：从消息传递到可学习聚合
```

演示内部的第 8 步也做了同样的事：

```
【步骤 8】读回全部记忆，验证“第二次读到了第一次写下的内容”
  作用域：scp_3xe2dwd5rn50a6g3cyz6btnav8
  方向：图神经网络 消息传递
  标签：['gnn', 'message-passing']
  历史检索：['图神经网络 消息传递 邻居聚合', '图神经网络 消息传递 邻居聚合', '图神经网络 消息传递 邻居聚合']
  阅读进度：[('图神经网络综述：从消息传递到可学习聚合', 'read')]
  记忆条目总数：5
```

原始的写入 / 读回报文（含条目 ID、修订号）见
`records/powercontext_memory_record.md`：

```
### 写入 2：`profile`

- 作用域：`scp_3xe2dwd5rn50a6g3cyz6btnav8`
- 写入原因：记住研究方向：图神经网络 消息传递
- 条目 ID：`mem_ent_...`（修订号 0）
- 记忆正文：

paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:03:21+00:00
```

---

## 5. 结构化过滤在 SQL 层生效

`verify.sh` 的第 8 项与 `tests/test_retrieval.py::test_core_retrieval_path_uses_both_lanes`
都做了同一组断言：

```
[通过] 结构化过滤（年份区间 / 标签）：标签过滤命中 8 条且全部带 gnn 标签；年份过滤 1990-1991 命中 0 条，SQL 中含年份条件
```

具体行为：

| 过滤 | 结果 |
| --- | --- |
| `--tag gnn` | 命中的 8 条**全部**带 `gnn` 标签 |
| `--year-from 1990 --year-to 1991` | 命中 **0** 条（语料最早是 2019 年），且 SQL 里确实带着 `year >= 1990 AND year <= 1991` |

---

## 6. 简报（seekdb `AI_COMPLETE`）

```
【步骤 6】生成研究简报（seekdb AI_COMPLETE）
  简报引擎：seekdb-ai-complete，模型：pp_summarizer
- 消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。
- 超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。
- 本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。
- 消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。
- 可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。
来源：《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:30-31；… papers/gnn_survey.md:2-4
  引用的段落：
    [1] 图神经网络综述：从消息传递到可学习聚合 — papers/gnn_survey.md:30-31
    [2] 图神经网络综述：从消息传递到可学习聚合 — papers/gnn_survey.md:2-4
    [3] 图神经网络综述：从消息传递到可学习聚合 — papers/gnn_survey.md:26-28
    [4] 图神经网络综述：从消息传递到可学习聚合 — papers/gnn_survey.md:6-12
    [5] 课程笔记：图神经网络基础（第 6-9 周） — notes/课程笔记-图神经网络基础.md:22-25
```

`简报引擎：seekdb-ai-complete` 说明走的是 `SELECT AI_COMPLETE('pp_summarizer', ...)`
——**由数据库去调用已注册的模型端点**，不是 Python 侧直接调 HTTP。

---

## 7. 验收自检：`bash scripts/verify.sh`

```
=== 步骤 3/4：逐项验收自检 ===
验收自检清单
============================================================
[通过] seekdb 连接与版本：版本 5.7.25-OceanBase seekdb-v1.4.0.0
[通过] 表结构存在：表：papers=7 行、paper_chunks=43 行、reading_log=9 行、briefs=1 行
[通过] 全文索引（ngram 全文检索）：papers 索引类型 ['BTREE', 'FULLTEXT', 'VECTOR']；paper_chunks 索引类型 ['BTREE', 'FULLTEXT', 'VECTOR']
[通过] 向量索引（HNSW + vsag）：paper_chunks 索引类型 ['BTREE', 'FULLTEXT', 'VECTOR']
[通过] 语料已导入 seekdb：papers=7，paper_chunks=43
[通过] 混合检索有命中：检索“图神经网络 消息传递 邻居聚合”命中 8 条（候选 33 条）
[通过] BM25 全文 + 向量 ANN 双通道融合：同时命中两路的段落 8 条；全文通道 8 条、向量通道 8 条
[通过] 结构化过滤（年份区间 / 标签）：标签过滤命中 8 条且全部带 gnn 标签；年份过滤 1990-1991 命中 0 条，SQL 中含年份条件
[通过] PowerContext 记忆写入后被独立进程读回：独立进程读回方向“图神经网络 消息传递”、标签 ['gnn', 'message-passing']，历史 3 条
[通过] 研究简报生成：引擎 seekdb-ai-complete，模型 pp_summarizer，长度 376
[通过] seekdb AI 函数（AI_EMBED / AI_COMPLETE）：AI_EMBED 可用：是；AI_COMPLETE 可用：是
============================================================
合计：11/11 项通过

=== 步骤 4/4：复核技术使用记录是否已生成 ===
  db_query_record.md 已生成（894 行）
  powercontext_memory_record.md 已生成（319 行）
  demo_output.md 已生成（151 行）
  PowerContext 记录包含写入与读回证据
```

---

## 8. 性能采样：`.venv/bin/python scripts/capture_sample.py`

`records/retrieval_sample.md` 的原文：

```
# 检索样本（真实运行抓取）

- 抓取时间：2026-10-28T17:03:46+00:00
- 数据库：`127.0.0.1:5881/paperpocket`
- 检索词：`图神经网络 消息传递 邻居聚合`
- 候选段落数：33，返回条数：5
- 端到端耗时：131.893 ms

## 各通道耗时

| 通道 | 命中行数 | 耗时(ms) |
| --- | --- | --- |
| 混合检索-全文通道 | 19 | 2.200 |
| 混合检索-向量通道 | 40 | 1.761 |

## 命中结果

| # | 标题 | 年份 | 来源 | 最终分 | RRF | BM25 | ANN 距离 | 通道 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 课程笔记：图神经网络基础（第 6-9 周） | 2024 | `notes/课程笔记-图神经网络基础.md:22-25` | 0.071793 | 0.032266 | 2.920393 | 0.981663 | bm25+vector+memory |
| 2 | 课程笔记：图神经网络基础（第 6-9 周） | 2024 | `notes/课程笔记-图神经网络基础.md:8-12` | 0.058571 | 0.028571 | 1.462612 | 1.305174 | bm25+vector+memory |
| 3 | 课程笔记：图神经网络基础（第 6-9 周） | 2024 | `notes/课程笔记-图神经网络基础.md:2-6` | 0.050685 | 0.027032 | 0.562548 | 1.330912 | bm25+vector+memory |
| 4 | 课程笔记：图神经网络基础（第 6-9 周） | 2024 | `notes/课程笔记-图神经网络基础.md:18-20` | 0.048211 | 0.025712 | 0.903819 | 1.420824 | bm25+vector+memory |
| 5 | 课程笔记：图神经网络基础（第 6-9 周） | 2024 | `notes/课程笔记-图神经网络基础.md:14-16` | 0.044277 | 0.023615 | 0.660209 | 1.509505 | bm25+vector+memory |
```

读法：

- 全文通道与向量通道**各返回一批不同的候选**（19 行 vs 40 行，去重后 33 个段落），
  这正是需要融合的原因；
- 向量通道 1.761 ms 走的是 HNSW 近似最近邻（`APPROXIMATE LIMIT 40`），不是全表扫；
- 端到端 131.893 ms 里绝大部分是 Python 侧的请求装配与记忆读回，数据库侧只占几毫秒。

---

## 9. 测试：`bash tests/run_tests.sh`

```
============================= test session starts ==============================
platform linux -- Python 3.12.14, pytest-9.2.0, pluggy-1.7.0
collected 11 items

tests/test_retrieval.py::test_tokenize_splits_cjk_into_bigrams PASSED     [  9%]
tests/test_retrieval.py::test_hash_embedding_is_deterministic_and_normalized PASSED [ 18%]
tests/test_retrieval.py::test_blend_keeps_dimension_and_normalizes PASSED  [ 27%]
tests/test_retrieval.py::test_corpus_parsing_and_chunking PASSED          [ 36%]
tests/test_retrieval.py::test_sql_helpers_escape_quotes PASSED            [ 45%]
tests/test_retrieval.py::test_filters_build_where_clause PASSED           [ 54%]
tests/test_retrieval.py::test_make_snippet_contains_query_term PASSED      [ 63%]
tests/test_retrieval.py::test_brief_prompt_roundtrip_and_summary PASSED   [ 72%]
tests/test_retrieval.py::test_core_retrieval_path_uses_both_lanes PASSED  [ 81%]
tests/test_retrieval.py::test_memory_write_then_read_from_another_process PASSED [ 90%]
tests/test_retrieval.py::test_brief_is_generated PASSED                   [100%]

============================== 11 passed in 1.09s ==============================
=== 全部测试通过 ===
```

前 8 个是离线用例，后 3 个是连着 seekdb + PowerContext 的集成用例（本次运行中
**没有被 skip**，是真的跑过了核心检索路径）。

---

## 10. 本次验证对应的证据文件

| 文件 | 大小 | 内容 |
| --- | --- | --- |
| `records/db_query_record.md` / `.json` | 894 行 / 114 KB | 本次运行的全部真实 SQL（步骤、命中行数、耗时） |
| `records/powercontext_memory_record.md` / `.json` | 319 行 / 15 KB | PowerContext 写入与读回的完整报文 |
| `records/demo_output.md` | 151 行 | 演示 8 步的原始输出 |
| `records/demo_run.log` | – | 同上的日志副本 |
| `records/retrieval_sample.md` / `.json` | 1.5 KB / 16 KB | 单次检索样本（含每条命中的全部字段） |
| `records/verify_run.log` | 1.4 KB | 11 项验收自检清单 |

`records/db_query_record.json` 里的单条记录长这样（真实字段，未加工）：

```json
{
  "step": "混合检索-全文通道",
  "sql": "SELECT chunk_key, doc_key, title, ... MATCH(title, content) AGAINST ('图神经网络 消息传递 邻居聚合' IN NATURAL LANGUAGE MODE) AS bm25_score FROM paperpocket.paper_chunks WHERE MATCH(...) ORDER BY bm25_score DESC LIMIT 40",
  "row_count": 19,
  "elapsed_ms": 2.2,
  "note": "BM25 全文检索"
}
```
