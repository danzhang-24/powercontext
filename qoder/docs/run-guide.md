# PaperPocket / 研知库 —— 运行指南

本文说明如何在一台干净机器上把 PaperPocket 跑起来。

> **目录约定**：下面所有命令都在仓库的 `qoder/` 目录下执行。
>
> ```bash
> cd <仓库根目录>/qoder
> ```

---

## 1. 系统由哪些组件组成

| 组件 | 作用 | 默认地址 | 由谁启动 |
| --- | --- | --- | --- |
| **seekdb** | OceanBase 衍生版搜索数据库，提供 ngram 全文索引、HNSW 向量索引、`AI_EMBED` / `AI_COMPLETE` 函数 | `127.0.0.1:5881`（MySQL 协议） | 评测环境自带；没有的话按 §3 手动起 |
| **PowerContext Server** | 记忆层：保存研究方向、检索历史、阅读进度 | `http://127.0.0.1:8100` | `scripts/setup.sh` 自动拉起 |
| **本地 OpenAI 兼容模型服务** | 给 seekdb 的 `AI_EMBED` / `AI_COMPLETE` 提供推理端点 | `http://127.0.0.1:8300/v1` | `scripts/setup.sh` 自动拉起 |
| **PaperPocket CLI** | 演示主体（导入 / 检索 / 简报 / 记忆 / 验收） | – | `python -m paperpocket` |

---

## 2. 前置条件

- **Python 3.10+**（推荐 3.12）。脚本会创建两个虚拟环境：
  - `qoder/.venv`——PaperPocket 自身依赖（`pymysql==1.1.1`、`pytest`）；
  - `qoder/.venv-powercontext`——PowerContext Server 依赖（`powercontext[seekdb,cli,server]==1.2.0`）。
  装了 `uv` 会自动用 `uv venv` / `uv pip install` 加速，否则回退到标准 `venv` + `pip`。
- **`curl`**——脚本用它探测服务是否就绪。
- **一个跑在 5881 端口的 seekdb 实例**——评测环境通常已经提供；没有的话见 §3。
- 首次安装需要能访问 PyPI。

---

## 3. 启动 seekdb（评测环境未提供时）

seekdb 是单进程服务，指定 `--base-dir`（数据目录）与 `--port` 即可：

```bash
mkdir -p /tmp/seekdb-data
/path/to/seekdb_opt --nodaemon \
    --base-dir /tmp/seekdb-data \
    --port 5881 \
    --parameter memory_limit=8G \
    --parameter cpu_count=8
```

只要能连上 `127.0.0.1:5881` 且支持 MySQL 协议即可；本项目用到的能力是
ngram 全文索引、`VECTOR` 列 + HNSW(vsag) 向量索引、`DBMS_AI_SERVICE` 模型注册、
`AI_EMBED` / `AI_COMPLETE`。

用其它端口时，通过环境变量覆盖（见 §7）。

---

## 4. 三条命令跑通全流程

```bash
cd <仓库根目录>/qoder

# ① 装依赖 → 拉起 PowerContext Server 与本地模型服务 → 建库建表建索引
#    → 把模型端点注册到 seekdb（AI_EMBED / AI_COMPLETE）
bash scripts/setup.sh

# ② 端到端演示：导入语料 → 检索 → 写记忆 → 再检索 → 生成简报 → 记录阅读进度
#    → 独立进程读回记忆，并把全部 SQL / 记忆读写落盘到 records/
bash scripts/run_demo.sh

# ③ 验收自检：逐条核对"指定技术是否真的在项目功能里发挥作用"，任一项不过即非零退出
bash scripts/verify.sh
```

### `setup.sh` 做了什么

1. 创建 `qoder/.venv` 与 `qoder/.venv-powercontext` 两个虚拟环境并安装依赖；
2. 生成 `scripts/powercontext.env`（PowerContext Server 的配置，已存在则保持不变）；
3. 启动本地 OpenAI 兼容模型服务（`python -m paperpocket.model_server`，端口 8300）；
4. 启动 PowerContext Server（`powercontext server run --env-file scripts/powercontext.env`，端口 8100）；
5. 在 seekdb 上建库建表，并创建 **ngram 全文索引** 与 **HNSW(vsag) 向量索引**；
6. 通过 `CALL DBMS_AI_SERVICE.CREATE_AI_MODEL(_ENDPOINT)` 把本地模型服务注册到 seekdb；
7. 自检：`pymysql` / `pytest` 可导入、PowerContext 健康检查、模型服务 `/v1/models` 可达。

脚本全部是幂等的：重复执行 `setup.sh` 不会报错，已存在的索引会被跳过。

### `run_demo.sh` 做了什么

按 8 步跑完整个故事，并把过程写进 `records/`：

| 步骤 | 内容 |
| --- | --- |
| 1 | 建表结构、全文索引、向量索引 |
| 2 | 导入 `corpus/` 下的 7 篇论文 / 笔记，切成 43 个段落块 |
| 3 | **第一次检索**（PowerContext 里还没有记忆） |
| 4 | 把研究方向与常用标签写入 PowerContext |
| 5 | **第二次检索**（读回记忆，方向参与向量扩展、标签参与加权） |
| 6 | 生成研究简报（seekdb `AI_COMPLETE`） |
| 7 | 记录阅读进度（写回 PowerContext） |
| 8 | 读回全部记忆，验证"第二次读到了第一次写下的内容" |

脚本随后还会用**独立进程**再跑一次 `recall`（验证跨进程复用），并打印数据库与记忆状态。

### `verify.sh` 做了什么

跑 `python -m paperpocket verify`，输出 11 项验收清单：

1. seekdb 连接与版本
2. 表结构存在
3. 全文索引（ngram 全文检索）
4. 向量索引（HNSW + vsag）
5. 语料已导入 seekdb
6. 混合检索有命中
7. BM25 全文 + 向量 ANN 双通道融合
8. 结构化过滤（年份区间 / 标签）在 SQL 层生效
9. PowerContext 记忆写入后被独立进程读回
10. 研究简报生成
11. seekdb AI 函数（`AI_EMBED` / `AI_COMPLETE`）

任何一项失败都会以非零码退出；记录文件缺失、缺少写入或读回证据同样会失败。

---

## 5. 单独使用 CLI

```bash
# 导入语料
.venv/bin/python -m paperpocket ingest

# 混合检索（默认带记忆加权）
.venv/bin/python -m paperpocket search "图神经网络 消息传递 邻居聚合" --top-k 5 --show-sql

# 结构化过滤
.venv/bin/python -m paperpocket search "对比学习" --year-from 2020 --year-to 2024 --tag gnn

# 生成简报
.venv/bin/python -m paperpocket brief "图神经网络 消息传递" --top-k 5

# 记忆：写入研究方向 / 读回
.venv/bin/python -m paperpocket remember --direction "图神经网络 消息传递" --tag gnn --tag message-passing
.venv/bin/python -m paperpocket recall

# 看状态（表行数、索引、记忆）
.venv/bin/python -m paperpocket stats

# 验收自检 / 重置
.venv/bin/python -m paperpocket verify --query "图神经网络 消息传递"
.venv/bin/python -m paperpocket reset --wipe-memory
```

> **注意**：`--json` 是**全局**选项，必须写在子命令**前面**：
> `.venv/bin/python -m paperpocket --json recall`。

---

## 6. 跑测试

```bash
cd <仓库根目录>/qoder
bash tests/run_tests.sh
# 或者
.venv/bin/python -m pytest tests/ -v
```

- **离线单元测试**（8 个）：分词、哈希嵌入、向量混合、语料解析与切块、SQL 转义、
  结构化过滤片段、摘要片段定位、简报提示词往返。
- **集成测试**（3 个）：真实导入 → 双通道检索 → 结构化过滤收窄；
  写入记忆后由**另一个进程**读回；简报非空。

集成用例在 seekdb（5881）或 PowerContext（8100）没起来时会自动 `skip`，
离线用例仍然执行；只要按 §4 起了服务，11 个用例会全部真正执行。
任一用例失败 → pytest 非零退出。

---

## 7. 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PAPERPOCKET_DB_HOST` | `127.0.0.1` | seekdb 地址 |
| `PAPERPOCKET_DB_PORT` | `5881` | seekdb 端口 |
| `PAPERPOCKET_DB_NAME` | `paperpocket` | 数据库名 |
| `PAPERPOCKET_DB_USER` / `PAPERPOCKET_DB_PASSWORD` | `root` / 空 | 数据库账号 |
| `PAPERPOCKET_POWERCONTEXT_URL` | `http://127.0.0.1:8100` | PowerContext Server 地址 |
| `PAPERPOCKET_SCOPE_ID` | `paperpocket:research` | 记忆作用域的逻辑名 |
| `PAPERPOCKET_MODEL_SERVER_URL` | `http://127.0.0.1:8300/v1` | OpenAI 兼容模型服务地址 |
| `PAPERPOCKET_EMBED_DIM` | `64` | 向量维度（建表时写进 `vector(N)`） |
| `PAPERPOCKET_EMBED_MODE` | `auto` | `auto` / `ai` / `local`：`ai` 强制走 seekdb `AI_EMBED`，`local` 走本地确定性哈希嵌入 |
| `PAPERPOCKET_CORPUS_DIR` | `qoder/corpus` | 语料目录 |
| `PAPERPOCKET_RECORDS_DIR` | `qoder/records` | 记录输出目录 |
| `PAPERPOCKET_RUNTIME_DIR` | `qoder/runtime` | 运行期数据（作用域绑定、日志） |

例：换一个端口跑演示。

```bash
PAPERPOCKET_DB_PORT=5882 bash scripts/run_demo.sh
```

---

## 8. 产出物

跑完 `run_demo.sh` + `verify.sh` 后，`records/` 下会有：

| 文件 | 内容 |
| --- | --- |
| `demo_output.md` / `demo_run.log` | 演示全过程输出（8 个步骤的原文） |
| `db_query_record.md` / `.json` | 每一条真实执行的 seekdb SQL：步骤、命中行数、耗时 |
| `powercontext_memory_record.md` / `.json` | PowerContext 的写入（`POST /v1/memory/remember`）与读回（`POST /v1/memory/search`）证据 |
| `retrieval_sample.md` / `.json` | 单次检索的样本：检索词、命中行、各通道耗时 |
| `verify_run.log` | 验收自检清单 |

抓一份新的检索样本：

```bash
.venv/bin/python scripts/capture_sample.py --query "图神经网络 消息传递 邻居聚合"
```

---

## 9. 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| `连接 seekdb 失败（127.0.0.1:5881）` | seekdb 没起来或端口不对；用 `PAPERPOCKET_DB_PORT` 指定实际端口 |
| `PowerContext Server 启动超时` | 看 `runtime/powercontext.log`；确认 `scripts/powercontext.env` 里的 `POWERCONTEXT_SERVER_DATABASE_PATH` 可写 |
| `本地模型服务启动超时` | 看 `runtime/model_server.log`；8300 端口被占用时改 `PAPERPOCKET_MODEL_SERVER_PORT` |
| `No database selected (1046)` | 连接没有默认库；本项目已在 `SeekDB.connect()` 里自动 `USE` 目标库，若自定义数据库名请同步 `PAPERPOCKET_DB_NAME` |
| `AI_EMBED 可用：否` | 模型端点没注册成功；重跑 `bash scripts/setup.sh`（会重新 `CALL DBMS_AI_SERVICE.CREATE_AI_MODEL_ENDPOINT`） |
| 想从空记忆重跑 | `python -m paperpocket reset --wipe-memory`（删库 + 丢弃本地作用域绑定） |
