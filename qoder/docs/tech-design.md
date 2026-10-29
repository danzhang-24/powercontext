# PaperPocket / 研知库 —— 技术设计

> 目录：`qoder/`。代码在 `qoder/paperpocket/`，脚本在 `qoder/scripts/`，
> 演示语料在 `qoder/corpus/`，真实运行记录在 `qoder/records/`。

---

## 1. 要解决的问题

研究者读文献时的三个老问题：

1. **关键词搜不准**——同义表述、缩写、中英文混排让纯关键词检索频繁漏召回；
2. **条件说不清**——"2019 年以后、综述类、带 gnn 标签"的组合条件很难在关键词
   引擎里表达；
3. **每次检索都从零开始**——上周读过的、上周关注的方向，下周还得重新交代一遍。

PaperPocket（研知库）的做法是把这三件事拆成三条检索通道 + 一层记忆：

| 通道 | 解决 | 落在哪个技术 |
| --- | --- | --- |
| BM25 全文 | 精确词命中、可解释的相关度 | seekdb **ngram 全文索引** + `MATCH ... AGAINST` |
| 向量 ANN | 同义 / 语义相近的召回 | seekdb **VECTOR 列 + HNSW(vsag) 向量索引** + `l2_distance ... APPROXIMATE` |
| 结构化过滤 | 年份 / 标签 / 类型 / 已读 | 同一条 SQL 的 `WHERE`，由数据库执行 |
| 记忆加权 | "上次我在看什么" | **PowerContext** 记忆层，方向 / 标签 / 历史 / 进度 |

---

## 2. 总体架构

```
                      ┌──────────────────────── PowerContext Server :8100 ────────────────────────┐
                      │  scope = paperpocket:research                                          │
                      │  ┌────────────┐ ┌────────────┐ ┌────────────┐                        │
   POST /v1/memory/  ─►│  │  profile   │ │  history   │ │  progress  │  方向 / 标签 / 历史 / 已读 │
   remember          │  │ 研究方向   │ │ 检索历史   │ │ 阅读进度   │                        │
                      │  └────────────┘ └────────────┘ └────────────┘                        │
                      └───────────▲──────────────────────────────────────────┬─────────────────┘
                                  │ POST /v1/memory/search（读回）             │
                                  │                                          │
  ┌───────────────────────────────┴──────────────────────────────────────────┴─────────────────┐
  │  PaperPocket CLI（qoder/paperpocket/）                                                │
  │                                                                                          │
  │   corpus.py ──► ingest.py ──► embedding.py ──────────────────┐                            │
  │   (解析/切块)    (写 papers / paper_chunks / reading_log)      │                            │
  │                                                                ▼                            │
  │                        ┌──────────────── seekdb :5881 (MySQL 协议) ─────────────────┐      │
  │                        │  papers / paper_chunks / reading_log / briefs             │      │
  │                        │  ft_papers, ft_chunks  (FULLTEXT, ngram)                 │      │
  │                        │  vi_papers, vi_chunks  (VECTOR, HNSW + vsag)              │      │
  │                        │  AI_EMBED / AI_COMPLETE  ──► 本地模型服务 :8300/v1 ──────┼──┐   │
  │                        └──────────────────────────────────────────────────────────┘  │   │
  │                                       ▲                                          │   │
  │                            retrieval.py（融合排序）                                │   │
  │                                       ▲                                          │   │
  │                            brief.py（AI_COMPLETE 摘要）─────────────────────────────┘   │
  │                            memory.py（PowerContext 客户端）                              │
  │                            records.py（证据落盘）                                       │
  └──────────────────────────────────────────────────────────────────────────────────────────┘
```

### 四条通道如何合并（`retrieval.py`）

```
query ──┬─► BM25 通道   MATCH(title, content) AGAINST(... IN NATURAL LANGUAGE MODE)   ─┐
        │                                                                          ├─► RRF 融合 ─► 记忆加权 ─► 排序
        ├─► 向量通道   l2_distance(emb, '<query vec>') ... APPROXIMATE LIMIT n       ─┤     ▲
        │                                                                          │     │
        └─► 记忆通道   方向 / 标签 / 历史命中 ────────────────────────────────────────┘     │
                                                                                                 │
            结构性条件（year / tags / kind / 已读排除）直接写进上面两条 SQL 的 WHERE ────────┘
```

---

## 3. 数据模型

数据库名默认 `paperpocket`，定义在 `paperpocket/schema.py`。

### 3.1 `papers`——文档级元数据 + 全文 + 向量

| 列 | 类型 | 说明 |
| --- | --- | --- |
| `doc_key` | `VARCHAR(96) NOT NULL` | 自然键（标题 slug），由**唯一索引** `uk_papers_doc` 约束 |
| `title` / `authors` / `year` / `venue` / `tags` / `kind` | `VARCHAR` / `INT` | 来自 Markdown front matter |
| `source_path` | `VARCHAR(512)` | 相对语料根目录的路径，用于回溯原文 |
| `summary` | `MEDIUMTEXT` | 本地抽取式摘要 |
| `content` | `MEDIUMTEXT NOT NULL` | 正文全文（供全文索引） |
| `emb` | `VECTOR(64)` | 文档级向量，供向量索引 |

### 3.2 `paper_chunks`——检索的真正主体（段落块）

在 `papers` 的字段基础上多出：

| 列 | 类型 | 说明 |
| --- | --- | --- |
| `chunk_key` | `VARCHAR(128) NOT NULL` | `<doc_key>#<序号>`，唯一索引 `uk_chunks_key` |
| `heading` | `VARCHAR(256)` | 该块所属的小节标题 |
| `seq` | `INT` | 块序号 |
| `start_line` / `end_line` | `INT` | 在原 Markdown 中的行号区间（命中后可直接定位） |
| `content` | `MEDIUMTEXT NOT NULL` | 块正文 |
| `emb` | `VECTOR(64)` | 块级向量 |

> **为什么不声明用户主键**：`papers` / `paper_chunks` 都不写 `PRIMARY KEY`，
> 只用唯一索引约束自然键。这样 seekdb 使用隐藏主键，服务端原生混合检索
> `dbms_hybrid_search` 才能在这两张表上工作（该接口不支持带用户主键的表）。
> 见 `schema.py` 顶部注释。

### 3.3 `reading_log` / `briefs`——普通自增主键表

| 表 | 列 | 说明 |
| --- | --- | --- |
| `reading_log` | `id BIGINT AUTO_INCREMENT PRIMARY KEY`, `doc_key`, `chunk_key`, `action`, `query_text`, `score DOUBLE`, `detail TEXT`, `created_at` | 导入 / 检索 / 简报引用的流水 |
| `briefs` | `id BIGINT AUTO_INCREMENT PRIMARY KEY`, `query_text`, `brief_md MEDIUMTEXT`, `engine`, `model_name`, `source_keys TEXT`, `created_at` | 生成过的简报及其来源段落键 |

### 3.4 索引

| 索引 | 表 | 语句 | 作用 |
| --- | --- | --- | --- |
| `uk_papers_doc` | papers | `UNIQUE (doc_key)` | 自然键唯一（幂等导入） |
| `uk_chunks_key` | paper_chunks | `UNIQUE (chunk_key)` | 段落键唯一 |
| `idx_chunks_doc` | paper_chunks | `(doc_key)` | 按文档回溯 |
| `idx_chunks_year` | paper_chunks | `(year)` | 年份过滤 |
| `ft_papers` | papers | `FULLTEXT (title, content) WITH PARSER ngram` | **ngram 全文索引**（中文按二元组切分） |
| `ft_chunks` | paper_chunks | `FULLTEXT (title, content) WITH PARSER ngram` | 同上 |
| `vi_papers` | papers | `VECTOR (emb) WITH (distance=l2, type=hnsw, lib=vsag)` | **HNSW 向量索引**（vsag 实现） |
| `vi_chunks` | paper_chunks | `VECTOR (emb) WITH (distance=l2, type=hnsw, lib=vsag)` | 同上 |

---

## 4. 导入流水线

`corpus.py` → `ingest.py` → `embedding.py` → `db.py`

1. **解析**（`corpus.py:116` `parse_file`）：读 Markdown，用 `---` 包裹的 front matter
   取 `title / authors / year / venue / tags / kind`；正文按标题层级切块
   （`corpus.py:163` `chunk_document`），超长块按空行继续切（`corpus.py:98` `_split_long`，
   默认上限 480 字符）。每块保留 `source_path` 与 `start_line/end_line`。
2. **向量化**（`embedding.py:118` `embed_expression`）——两条通道，维度都是 64：
   - `ai`：**由 seekdb 内部**执行 `AI_EMBED('pp_embed', '<文本>')`，向量计算发生在数据库里；
   - `local`：Python 侧确定性哈希嵌入（`embedding.py:56` `hash_embedding`），
     词元 → MD5 分桶 → 带符号词频 → L2 归一化，**完全可复现、离线可跑**。
   `PAPERPOCKET_EMBED_MODE=auto` 时，模型端点已注册就用 `ai`，否则自动回退 `local`。
3. **写入**（`ingest.py:94` `ingest_documents`）：先按 `doc_key` 删旧数据（幂等），
   再写 `papers` 一行、`paper_chunks` N 行，并在 `reading_log` 留一条 `ingest` 记录。
4. 本地模型服务 `paperpocket/model_server.py` 提供 OpenAI 兼容的
   `/v1/embeddings` 与 `/v1/chat/completions`，通过
   `CALL DBMS_AI_SERVICE.CREATE_AI_MODEL_ENDPOINT` 注册到 seekdb
   （`service.py:136` `setup_ai_models`）。

---

## 5. 混合检索

入口 `retrieval.py:281` `HybridSearch.search`。

### 5.1 全文通道（BM25）

`retrieval.py:209` `_bm25_sql`：

```sql
SELECT chunk_key, ..., MATCH(title, content) AGAINST ('<query>' IN NATURAL LANGUAGE MODE) AS bm25_score
FROM paperpocket.paper_chunks
WHERE MATCH(title, content) AGAINST ('<query>' IN NATURAL LANGUAGE MODE)
  AND <结构化条件>
ORDER BY bm25_score DESC LIMIT 40
```

ngram 解析器让中文按二元组建索引，`MATCH` 返回相关度分数而不是布尔命中。

### 5.2 向量通道（ANN）

`retrieval.py:223` `_ann_sql`：

```sql
SELECT chunk_key, ..., l2_distance(emb, '[...]') AS ann_distance
FROM paperpocket.paper_chunks
WHERE <结构化条件>
ORDER BY l2_distance(emb, '[...]') APPROXIMATE LIMIT 40
```

`APPROXIMATE` 让 seekdb 走 `vi_chunks` 的 HNSW 图，而不是全表扫。

### 5.3 结构化过滤

`retrieval.py:48` `SearchFilters.where_clause()` 把过滤条件渲染成 SQL 片段，
**直接拼进上面两条 SQL 的 `WHERE`**——过滤由数据库完成，不是拉回内存后再筛：

| 条件 | SQL 片段 |
| --- | --- |
| 年份区间 | `year >= 2019 AND year <= 2024` |
| 标签 | `tags LIKE '%gnn%'` |
| 类型 | `kind = 'paper'` |
| 已读排除 | `filters.exclude_doc_keys`（Python 侧过滤，走 `--exclude-read`） |

### 5.4 记忆通道

`retrieval.py:236` `_memory_scores`：读回 PowerContext 的快照后，给每条命中算一个
`memory_score`，并记录**可解释的加分原因**：

| 命中情况 | 加分 | 说明文案 |
| --- | --- | --- |
| 标签命中记忆里的常用标签 | `2.0 × min(命中数,2)/2` | `命中记忆标签 ['gnn', 'message-passing']` |
| 标题/小节/正文里出现记忆方向的关键词 | `0.5 × min(命中数,4)` | `命中记忆方向关键词 ['图神经网络', '消息传递']` |
| 该段落在历史检索命中里 | `+1.0` | `出现在历史检索命中中` |

### 5.5 融合排序

`retrieval.py:340`：

```
rrf_score   = 1/(60 + bm25_rank)  +  1/(60 + ann_rank)          # RRF_K = 60
final_score = rrf_score × (1 + 0.35 × memory_score)              # MEMORY_WEIGHT = 0.35
```

选 RRF 而不是分数线性相加，是因为 BM25 分数和 L2 距离**量纲完全不同**
（本次运行中 BM25 ∈ [0.5, 3.6]、ANN 距离 ∈ [0.9, 1.5]），直接加权会被某一路主导。
RRF 只看名次，天然可比较；记忆加权是一个 0.35 上限的乘性系数，避免记忆盖过内容相关性。

排序相同时按 `chunk_key` 字典序兜底，保证结果**稳定可复现**。

---

## 6. PowerContext 记忆怎么用

`paperpocket/memory.py`。

### 6.1 三类记忆条目

记忆正文用固定的可解析文本格式（首行 `paperpocket-memory v1`，见 `memory.py:29`
`MEMORY_HEADER`），读回时能重新解析成结构化对象（`memory.py:106` `_parse`）：

```
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:03:21+00:00
```

| `type` | 写入时机 | 检索时怎么用 |
| --- | --- | --- |
| `profile` | `remember --direction ... --tag ...` | 方向关键词参与命中打分；标签参与加权 |
| `history` | 每次检索自动写回（`service.py:230`） | 命中的段落键出现在历史里 → `+1.0` |
| `progress` | 简报/阅读后写回 | `read_doc_keys` 里的资料从候选里剔除 |

### 6.2 作用域与跨进程复用

- 作用域由 `POST /v1/scopes` 创建，逻辑名 `paperpocket:research`
  （`PAPERPOCKET_SCOPE_ID` 可改）；
- 真实 `scope_id` 落在 `runtime/scope.json`（`memory.py:200` `_load_binding` /
  `memory.py:212` `_save_binding`），**进程重启后仍指向同一个作用域**；
- `read_doc_keys`、`profile`、`history` 全部来自 `POST /v1/memory/search`，
  所以**另一个进程**（`python -m paperpocket recall`）能读到同样的内容——
  `verify.sh` 的第 9 项就是用独立进程做的交叉验证。

### 6.3 记忆参与向量检索

`retrieval.py:294`：有记忆时，查询向量不再是"查询词"单独一个向量，而是

```
query_vector = normalize( embed(query) + 0.35 × embed(profile.direction) )
```

于是"语义相近 + 方向相关"的段落更容易进入向量通道的候选集。

---

## 7. 简报生成

`brief.py:163` `BriefGenerator.generate`：

1. `build_prompt`（`brief.py:29`）把命中段落拼成提示词，每段带标题与 `来源:行号区间`；
2. 走 seekdb 的 `SELECT AI_COMPLETE('pp_summarizer', '<prompt>')`——**由数据库调用
   已注册的模型端点**；
3. 端点不可用或调用失败时，降级到本地抽取式摘要 `extractive_summary`
   （`brief.py:80`，按与检索词的重合度挑句子），保证任何环境都能产出简报；
4. 结果写进 `briefs` 表，来源段落写进 `reading_log`。

---

## 8. 可核查性：证据落盘

`records.py` 把"指定技术是否真的在项目功能里发挥作用"变成可逐条核对的文件：

| 文件 | 内容 |
| --- | --- |
| `records/db_query_record.md` / `.json` | 每一条真实执行的 SQL（步骤、命中行数、耗时 ms），逐条可复制到客户端执行 |
| `records/powercontext_memory_record.md` / `.json` | 每次 `POST /v1/memory/remember` 的正文与条目 ID、每次 `POST /v1/memory/search` 的命中条目 |
| `records/demo_output.md` | 演示 8 步的完整输出 |
| `records/retrieval_sample.md` / `.json` | 单次检索样本：检索词、命中行、两条通道各自的耗时 |
| `records/verify_run.log` | 11 项验收自检清单 |

记录文件是**累积**的（`records.py:83` `_merge_sql_records`、
`records.py:141` `_merge_memory_records`）：任何一次只读子命令都不会覆盖掉演示阶段
留下的写入证据。

---

## 9. 关键文件清单

| 文件 | 关键位置 | 作用 |
| --- | --- | --- |
| `qoder/paperpocket/schema.py` | `:25` `table_ddl` / `:91` `index_ddl` / `:126` `prepare` | 建库建表 + 全文/向量索引 |
| `qoder/paperpocket/db.py` | `:47` `SeekDB` / `:56` `connect` / `:78` `use_database` / `:113` `execute` / `:127` `query` / `:178` `indexes_of` | MySQL 协议访问层 + SQL 计时记录 |
| `qoder/paperpocket/corpus.py` | `:75` `_parse_front_matter` / `:116` `parse_file` / `:163` `chunk_document` | Markdown 解析与切块 |
| `qoder/paperpocket/ingest.py` | `:59` `_insert_paper` / `:72` `_insert_chunk` / `:94` `ingest_documents` | 幂等导入 |
| `qoder/paperpocket/embedding.py` | `:35` `tokenize` / `:56` `hash_embedding` / `:69` `blend` / `:118` `embed_expression` | 本地嵌入 + `AI_EMBED` 表达式 |
| `qoder/paperpocket/retrieval.py` | `:39` `SearchFilters` / `:209` `_bm25_sql` / `:223` `_ann_sql` / `:236` `_memory_scores` / `:281` `search` | 混合检索与融合排序 |
| `qoder/paperpocket/memory.py` | `:29` `MEMORY_HEADER` / `:106` `_parse` / `:170` `ensure_scope` / `:225` `remember` / `:283` `search_memories` / `:298` `load` | PowerContext 客户端 |
| `qoder/paperpocket/brief.py` | `:29` `build_prompt` / `:80` `extractive_summary` / `:163` `generate` | 简报（`AI_COMPLETE` + 降级） |
| `qoder/paperpocket/service.py` | `:27` `PaperPocket` / `:136` `setup_ai_models` / `:203` `ingest` / `:210` `search` / `:233` `make_brief` / `:269` `stats` | 应用门面 |
| `qoder/paperpocket/demo.py` | `:41` `run_demo` | 8 步端到端编排 |
| `qoder/paperpocket/verify.py` | `:50` `run_checks` | 11 项验收自检 |
| `qoder/paperpocket/records.py` | `:83` `_merge_sql_records` / `:171` `write_memory_record` | 证据落盘 |
| `qoder/paperpocket/model_server.py` | `:114` `_handle_embeddings` / `:129` `_handle_chat` | 本地 OpenAI 兼容模型服务 |
| `qoder/paperpocket/cli.py` | `:36` `_build_parser` / `:150` `main` | 命令行入口 |
| `qoder/scripts/common.sh` | `:44` `paperpocket` / `:51` `ensure_model_server` / `:80` `ensure_powercontext` | 脚本公共部分 |
| `qoder/scripts/setup.sh` | — | 装依赖 + 起服务 + 建表 + 注册模型 |
| `qoder/scripts/run_demo.sh` | — | 端到端演示 |
| `qoder/scripts/verify.sh` | — | 验收自检 |
| `qoder/scripts/capture_sample.py` | — | 抓取检索样本 |
| `qoder/tests/test_retrieval.py` | — | 11 个测试（8 离线 + 3 集成） |

---

## 10. 容错与降级

| 能力 | 有服务时 | 没有服务时 |
| --- | --- | --- |
| 向量化 | seekdb 内部 `AI_EMBED` | 本地确定性哈希嵌入（`PAPERPOCKET_EMBED_MODE=local`） |
| 简报 | seekdb `AI_COMPLETE` | 本地抽取式摘要，并在输出里标注降级原因 |
| 全文 / 向量检索 | 依赖 seekdb 索引 | 无（seekdb 是硬依赖） |
| 记忆 | PowerContext HTTP API | 记忆通道自动关闭，检索仍然可用（`use_memory=False` 路径） |

本地嵌入与本地模型服务用**同一套**词元与分桶规则
（`embedding.hash_embedding` ↔ `model_server._handle_embeddings`），
因此把端点换成真实 OpenAI 兼容服务时，只需改一个 URL。
