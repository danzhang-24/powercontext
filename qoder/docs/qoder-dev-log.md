# PaperPocket / 研知库 —— 开发日志

这份日志记录**实际发生过的**开发过程：先做了什么、后做了什么、撞到哪些坑、
坑是怎么填的，以及 Qoder（AI IDE）在这个过程中扮演了什么角色。
没有做过的步骤不会出现在这里。

---

## 0. 一句话背景

赛题要求"相关项目资产放入对应 `qoder` 目录"，并要在**指定技术真的在功能里发挥作用**
的前提下提交可运行的代码 + 文档 + 证据。仓库 `oceanbase/powercontext` 里
PowerContext 是记忆层，seekdb 是检索层，两边要拼成一个能跑通的产品。

目标定成：做一个 **研究资料助手**——把自己的论文 / 笔记灌进 seekdb，
用「全文 + 向量 + 结构化」三路检索捞出相关段落，再用 PowerContext 记住
「我在研究什么、我读过什么」，让第二次检索比第一次更准。最后叫 **PaperPocket / 研知库**。

---

## 1. 顺序：先定验收点，再写代码

### 步骤 1：把赛题拆成"可判定的检查项"

先读赛题页面（`oceanbase.yuque.com` 的生态赛道说明），确认三件事：
资产放在 `qoder/` 目录、开发基于 `2026-competition-ecosystem` 分支、提交到评测平台的
分支要一致。赛题页没有给出具体的文档文件名清单，所以文档结构是按"评审能自己跑起来、
自己核对"倒推出来的。

然后把验收标准写成一个**可执行的清单**，而不是一段描述：

| # | 检查项 | 判定方式 |
| --- | --- | --- |
| 1 | seekdb 可连接、版本正确 | `SELECT version()` 含 seekdb/oceanbase |
| 2 | 四张表存在 | `SELECT COUNT(*)` |
| 3 | `papers` / `paper_chunks` 上有**全文索引** | `SHOW INDEX` 的 `Index_type` 含 `FULLTEXT` |
| 4 | `paper_chunks` 上有**向量索引** | `SHOW INDEX` 的 `Index_type` 含 `VECTOR` |
| 5 | 语料已导入 | `papers > 0 且 paper_chunks > 0` |
| 6 | 混合检索有命中 | `hits` 非空 |
| 7 | 命中同时来自 BM25 与向量两路 | 每条命中的 `bm25_rank` / `ann_rank` 都不是 None |
| 8 | 结构化过滤在 SQL 层生效 | 标签过滤后全部命中带该标签；年份区间过滤结果为空且 SQL 里带条件 |
| 9 | 记忆写入后能被**另一个进程**读回 | `subprocess` 起独立 `python -m paperpocket recall` |
| 10 | 简报可生成且非空 | 长度 > 20 |
| 11 | `AI_EMBED` / `AI_COMPLETE` 可用 | 查 `DBA_OB_AI_MODELS` + `DBA_OB_AI_MODEL_ENDPOINTS` |

这份清单后来就是 `paperpocket/verify.py:50` 的 `run_checks()`，
`scripts/verify.sh` 直接调它，任一项不过就非零退出。
**先写验收、后写实现**，整个项目少走了很多弯路。

### 步骤 2：定数据模型

关键决策：**`papers` 和 `paper_chunks` 不声明用户主键**，只用唯一索引约束自然键
（`doc_key` / `chunk_key`）。原因写在 `schema.py` 的文件头注释里：seekdb 的服务端
原生混合检索 `dbms_hybrid_search` 不支持带用户主键的表。虽然本项目最终用的是
"自己写 SQL 融合"而不是服务端混合检索接口，但保持这个约束没有坏处。

### 步骤 3：搭骨架

按依赖顺序写模块，每个模块写完立刻拿真实 SQL 试：

```
config.py  →  db.py  →  schema.py  →  corpus.py  →  embedding.py
           →  ingest.py  →  retrieval.py  →  memory.py  →  brief.py
           →  records.py  →  service.py  →  demo.py / verify.py / cli.py
```

### 步骤 4：脚本与证据

`scripts/common.sh`（公共路径与服务探测）、`setup.sh`（装依赖 / 起服务 / 建表 /
注册模型）、`run_demo.sh`（8 步演示）、`verify.sh`（验收自检）。
`paperpocket/records.py` 负责把每一条真实 SQL、每一次记忆读写落盘到 `records/`，
让评审不用看代码就能核对"技术真的用上了"。

---

## 2. 撞到的坑（全部是跑起来才暴露的）

下面每一条都是**真实报错**触发的修复，不是预防性设计。

### 坑 1：第二次运行时建索引直接失败（错误码 1235）

**现象**：`setup.sh` 第一次跑成功，紧接着 `run_demo.sh` 挂在【步骤 1】：

```
执行失败：(1235, 'create vector index on column has vector index is not supported')
```

**原因**：`schema.prepare()` 原本靠捕获异常文本里的 `already exist` / `duplicate`
来跳过已存在的索引。但 seekdb 对"重复创建向量索引"报的是 **1235
`create vector index on column has vector index is not supported`**，
文本里根本没有 `already exist`，于是被原样抛出。

**修法**（`schema.py:91` / `:126`）：不再靠猜错误文本，而是**先查再建**——
`index_ddl()` 改成返回 `(表名, 索引名, 语句)` 三元组，`prepare()` 先
`SHOW INDEX FROM db.table` 拿到已有索引名，已存在的直接跳过。原来的异常捕获保留
作为兜底。顺带把 `SHOW INDEX` 也做成了带库名的全限定形式（见坑 3）。

### 坑 2：PowerContext 记忆检索 422

**现象**：

```
执行失败：PowerContext POST /v1/memory/search 失败（HTTP 422）：
{"error":{"code":"invalid_request","details":{"errors":[
  {"type":"less_than_equal","loc":["body","limit"],"msg":"Input should be less than or equal to 50"}]}}}
```

**原因**：`memory.py` 原来默认 `limit=100`，而服务端 `/v1/memory/search` 的
`limit` 上限是 **50**。

**修法**（`memory.py:32` / `:283`）：加常量 `MAX_SEARCH_LIMIT = 50`，
`search_memories()` 里做 `max(1, min(int(limit), MAX_SEARCH_LIMIT))`，
在**客户端一处**兜住，所有调用点自动受益。

**遗留说明**：超过 50 条的记忆历史会被截断。当前场景（一个作用域几十条）够用；
真要支持更长历史，得改成按 `type` 分批拉取。

### 坑 3：`SHOW INDEX` 报 `No database selected`（1046）

**现象**：`python -m paperpocket stats` 单独跑时崩：

```
执行失败：(1046, 'No database selected')
```

**原因**：连接建好后没有默认库。`SHOW INDEX FROM papers` 不带库名时，数据库不知道
查哪个库。之前没暴露，是因为 `prepare_schema()` 里的 DDL 脚本刚好执行过 `USE paperpocket`，
把默认库留在了连接上；单独跑 `stats` / `verify` 就露馅了。

**修法**（`db.py:178`）：`indexes_of()` 改成全限定形式
`SHOW INDEX FROM \`paperpocket\`.\`papers\``，不依赖连接的默认库。

### 坑 4：简报生成也需要默认库

**现象**：验收第 10 项失败：

```
[失败] 研究简报生成：检查过程出错：(1046, 'No database selected')
```

**原因**：`SELECT AI_COMPLETE('pp_summarizer', '<prompt>')` 没有表名，也没有库名。
这不是 `SHOW INDEX` 那种可以简单改写的问题——**改写成 `FROM briefs` 不行**，
表空的时候查询会返回 0 行，反而拿不到简报。

**修法**（`db.py:56` / `:78`）：在 `SeekDB.connect()` 里自动
`USE <db_name>`，并把 `use_database()` 做成"库还不存在就静默返回 False"的形式。
第一次建库之前 `USE` 会失败、被吞掉，接着 DDL 脚本自己的 `USE` 生效；
之后每次连接默认库都是对的，`INSERT INTO briefs`（不带库名）也就自然能跑。

### 坑 5：命令行传进来的路径是字符串

**现象**：验收第 9 项失败，独立进程 `recall` 报：

```
AttributeError: 'str' object has no attribute 'mkdir'
```

**原因**：`Settings.records_dir` 声明成 `Path`，但 `load_settings()` 里环境变量那支
做了 `Path(...)` 转换，**命令行覆盖那支没有**——`--records-dir` 传进来的是裸字符串，
`dataclasses.replace` 直接把它塞进了 `Settings`。

**修法**（`config.py:74`）：`load_settings()` 里统一把
`corpus_dir` / `records_dir` / `runtime_dir` 三个路径字段转成 `Path`，
不管来自环境变量还是命令行。同一处修好了 `--corpus-dir` 的同类问题。

### 坑 6：argparse 全局选项的位置

**现象**：验收第 9 项还是失败：

```
独立进程 recall 失败：usage: python -m paperpocket [-h] [--db-host DB_HOST] ...
```

**原因**：`verify.py` 里拼的子进程命令把 `--json` 放在了子命令**后面**：

```python
command = [..., "recall", "--json"]     # ← 错
```

`--json` 是定义在顶层 parser 上的全局选项，必须写在子命令**前面**；
放在 `recall` 后面 argparse 直接报"unrecognized arguments"。

**修法**（`verify.py:146`）：把 `--json` 移到 `recall` 前面。
（试过"给 `recall` 子命令也加一个 `--json`"，但 argparse 里子 parser 的默认值会
覆盖顶层已解析的值，反而更坑，所以没有采用。）

### 坑 7：只读子命令把演示的证据覆盖了

**现象**：修完坑 6 之后跑 `verify.sh`，`records/powercontext_memory_record.md` 里
"写入"一节变成了"（本次运行没有写入记忆）"。

**原因**：验收第 9 项会起一个独立进程跑 `recall`，而 `recall` 结束时也会调
`write_memory_record()`——它只有读没有写，于是把**整个文件覆盖**成"只有读回"，
演示阶段留下的写入证据被冲掉了。同理，任何人跑一次 `paperpocket search`
（它会写一条历史记忆）也会把记录冲掉。

**修法**（`records.py:83` / `:141`）：把记录文件改成**累积**语义。
数据库记录按 `(步骤, SQL, 说明)` 三元组去重（保留最后一次的耗时），
记忆记录按时间顺序追加写入 / 读回条目，各自最多保留 200 条。
现在 `recall`、`search`、`stats` 跑多少次都不会破坏已有证据。

### 坑 8（早于本次接手）：pymysql 版本冲突

`requirements.txt` 与 `requirements-powercontext.txt` 里都锁了 `pymysql==1.1.1`。
原因是 PowerContext 依赖的 `aiomysql 0.3.2` 仍以**函数**方式调用
`pymysql.escape_dict` / `escape_bytes_prefixed`，而 pymysql 1.2+ 把它们改成了
字符串哨兵。两者同时存在时，`POST /v1/memory/remember` 会抛
`TypeError: 'str' object is not callable` 并返回 HTTP 500。
两个虚拟环境**必须分别安装**，不能合并。

---

## 3. Qoder 在这个项目里怎么用的

说具体一点，不泛泛而谈：

1. **读仓库 + 对齐赛题**：让 Qoder 先把 `oceanbase/powercontext` 的目录结构、
   PowerContext Server 的 HTTP 接口（`/v1/scopes`、`/v1/memory/remember`、
   `/v1/memory/search`）和 CLI 形态摸清楚，再读赛题页面确定"资产放 `qoder/`"。
   人类容易凭印象猜 API，Qoder 直接去代码里查证。

2. **从验收点反推模块划分**：把上面那张 11 项检查表交给 Qoder，让它建议
   模块边界和接口签名，再逐个落地。`verify.py` 的检查函数结构就是这一步的产物。

3. **拿真实报错驱动调试**：这次 7 个坑，没有一个是靠"读代码看看对不对"发现的，
   全是跑 `bash scripts/verify.sh` 之后把**原始报错**（含错误码、HTTP 422 的
   JSON 体、argparse 的 usage 文本）贴回去，让 Qoder 定位到具体文件行。
   错误码 1235 那个坑尤其典型——只读代码看不出"已经存在"的判断只认两种错误文本。

4. **写文档时用真实输出，不用生成的内容**：文档里的每一段数字都来自
   `/tmp` 下真实跑的 stdout。做法是：先跑脚本 → 把输出重定向到临时文件 →
   只摘录真实片段写进文档。反过来先写文档再补数据，很容易写出"看起来很合理、
   但其实没跑通"的假样本。

5. **把门禁交给脚本而不是人肉检查**：每次改动后必跑
   `bash scripts/verify.sh`（退出码非 0 就停）和 `bash tests/run_tests.sh`。
   开发过程中有两次是"文档都写完了，跑一遍才发现 verify 挂了"，
   这道门禁把问题挡在了提交之前。

6. **明确划出"不要动"的边界**：已有的 Python 逻辑只在**确实挡住演示运行**时才改，
   且保持最小改动。本次只动了 4 个文件、都是几行：`schema.py`（索引幂等）、
   `memory.py`（limit 上限）、`db.py`（默认库 + 全限定 SHOW INDEX）、
   `config.py`（路径转 Path）、`verify.py`（`--json` 位置）、
   `records.py`（记录累积）。

---

## 4. 几次"看起来对但其实不对"的判断

- 一开始想用 seekdb 服务端的 `dbms_hybrid_search` 做融合。查下来它对表结构有
  限制（不能有用户主键），而且融合策略不可控——**最终改成自己发两条 SQL 做 RRF**，
  这样每一步的分数都能打印出来、能解释、能写进验收记录。
- 一开始想把 BM25 分数和 L2 距离直接加权求和。看了真实数据才发现两者量纲完全不同
  （BM25 ∈ [0.5, 3.6]，L2 距离 ∈ [0.9, 1.5]），直接加权等于让向量通道说了算，
  所以改用只看名次的 RRF。
- 一开始想用"标签精确匹配"过滤，后来发现标签在库里是逗号分隔的字符串，
  `tags = 'gnn'` 会漏掉 `gnn,message-passing`；改成 `tags LIKE '%gnn%'`，
  并且在 `sqlutil.sql_like()` 里把 `%` `_` 转义掉，避免通配符误伤。

---

## 5. 现在的状态与已知不足

**已完成并且每次跑都验证**：

- `bash scripts/setup.sh` → 幂等装依赖、起服务、建表建索引、注册模型端点；
- `bash scripts/run_demo.sh` → 8 步演示，产出 `records/` 全部证据；
- `bash scripts/verify.sh` → **11/11 项通过**；
- `bash tests/run_tests.sh` → **11 passed**（8 离线 + 3 集成）；
- `python scripts/capture_sample.py` → 抓检索样本（查询 + 命中行 + 各通道耗时）。

**已知不足（有意没有掩饰）**：

1. **本地模型服务不是真大模型**。`paperpocket/model_server.py` 是零依赖的确定性
   实现：`/v1/embeddings` 用与本地嵌入同一套哈希规则，`/v1/chat/completions` 用
   抽取式摘要。好处是离线可跑、结果可复现、`AI_EMBED` / `AI_COMPLETE` 走的
   确实是"数据库调模型端点"的真实链路；坏处是摘要质量谈不上好。
   **换成任何真实 OpenAI 兼容服务只需要改一个 URL**（`PAPERPOCKET_MODEL_SERVER_URL`）。
2. **规模很小**：7 篇资料 / 43 个段落 / 64 维向量。目的是把链路跑通，
   不是做效果评测。向量维度与维度相关的下标都受 `PAPERPOCKET_EMBED_DIM` 控制。
3. **记忆检索上限 50 条**（服务端限制），见坑 2。
4. **融合策略是手写的 RRF + 固定权重 0.35**，没有做权重调参；
   `RRF_K` 与 `MEMORY_WEIGHT` 是 `retrieval.py` 顶部的常量，改一下就能调。
5. **没有做并发压测**，也没有对比"纯 BM25 / 纯向量"的量化指标。
   `docs/validation-sample.md` 里的对比是**行为对比**（排序变化、分数变化、
   ANN 距离变化），不是离线标注集上的 Recall@K 评测——这一点在文档里也写明了。

---

## 6. 如果继续做下去

按优先级：

1. 把本地模型服务换成真实 embedding / chat 端点，做一版 **Recall@K 对照**
   （纯 BM25 / 纯向量 / 混合 / 混合+记忆 四组），这样"记忆到底提升了多少"才有数；
2. 语料扩到几百篇，加一个**离线标注集**（query → 相关段落），
   配合 `tests/` 做成回归基线；
3. 记忆检索分类型分批拉取，突破 50 条上限；
4. 把 `records/` 的累积记录加上 run id，支持多次运行之间的对比。
