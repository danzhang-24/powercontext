# 运行说明

本文档说明 `minimax/` 目录下的 SDD 上下文模块（`sddctx`）如何在干净环境里安装、
初始化、启动并执行验证样例。

---

## 1. 依赖与版本

| 组件 | 版本 | 用途 | 安装位置 |
| --- | --- | --- | --- |
| Python | 3.12 | 运行环境 | 操作系统自带 |
| pylibseekdb | 1.4.0.post1 | 嵌入式 seekdb，存规格/代码/测试索引 | `.venv` |
| pytest | 9.2.0 | 运行目标功能测试与回归测试 | `.venv` |
| powercontext | 1.2.0 | PowerContext Server，保存与读取任务状态 | `.venv-powercontext` |
| pymysql | 1.1.1 | PowerContext Server 的 MySQL 驱动（**必须锁版本**） | `.venv-powercontext` |
| aiomysql | 0.3.2 | PowerContext Server 依赖 | `.venv-powercontext` |

> **为什么必须锁 `pymysql==1.1.1`**：pymysql 1.2 及以上把 `escape_dict` /
> `escape_bytes_prefixed` 从函数改成了字符串哨兵，而 aiomysql 0.3.2 仍然按函数
> 调用它。两者同时出现时，PowerContext Server 的写接口（如
> `POST /v1/memory/remember`）会抛 `TypeError: 'str' object is not callable`
> 并返回 HTTP 500。锁定 1.1.1 即可规避。

### MiniMax 接入方式（版本与凭据）

| 接入方式 | 传输 | 版本 / 模型 | 凭据 |
| --- | --- | --- | --- |
| HTTP（默认） | `POST {base}/v1/chat/completions` | 模型默认 `MiniMax-M3`，可用 `MINIMAX_MODEL` 覆盖 | `MINIMAX_API_KEY` 环境变量 |
| CLI | `mmx text chat --message ... --system ...` | `mmx` CLI 已登录的账号 | `~/.mmx/credentials.json` |
| File（离线重放） | 本地 JSON 文件 | 记录在 `records/minimax_response.json` | 无 |

接口域名由 `MINIMAX_REGION` 决定：`global` → `https://api.minimax.io`，
`cn` → `https://api.minimaxi.com`，也可用 `MINIMAX_BASE_URL` 直接覆盖。

**本仓库提交的演示记录使用 `file` 传输**：评测环境没有 MiniMax 平台密钥时，
可以用已记录的模型响应离线重放同一条补丁，保证流程可完整复现。拿到
`MINIMAX_API_KEY` 后执行 `SDDCTX_TRANSPORT=http bash scripts/run_demo.sh`
即可走官方 HTTP 接口重新生成补丁。

---

## 2. 配置步骤

```bash
cd minimax
bash scripts/setup.sh
```

`setup.sh` 会：

1. 创建 `.venv`（sddctx 依赖）与 `.venv-powercontext`（PowerContext Server 依赖）
   两个虚拟环境，分别安装 `requirements.txt` 中锁定的依赖；
2. 生成 `scripts/powercontext.env`（PowerContext Server 的运行配置，占位值，
   可自行修改端口与存储路径）；
3. 打印自检结果与后续步骤。

PowerContext Server 的关键配置项（来自 powercontext 1.2.0 的 `.env.example`）：

| 配置项 | 含义 | 本演示取值 |
| --- | --- | --- |
| `POWERCONTEXT_SERVER_HTTP_HOST` / `_PORT` | 监听地址与端口 | `127.0.0.1` / `8000` |
| `POWERCONTEXT_SERVER_ACCESS_MODE` | 访问控制模式 | `disabled`（本地演示） |
| `POWERCONTEXT_SERVER_DATABASE_KIND` | 存储类型 | `seekdb` |
| `POWERCONTEXT_SERVER_DATABASE_PATH` | 存储路径 | `minimax/runtime/powercontext-seekdb` |
| `POWERCONTEXT_SERVER_WORKSPACE` | 工作区路径 | `minimax/runtime/powercontext-workspace` |

sddctx 自身的配置项（命令行参数优先于环境变量）：

| 命令行参数 | 环境变量 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `--project` | — | `minimax/demo_project` | 演示工程目录 |
| `--work-dir` | `SDDCTX_HOME` | `minimax/runtime` | 嵌入式 seekdb 与临时工作区 |
| `--records-dir` | `SDDCTX_RECORDS_DIR` | `minimax/records` | 技术使用记录输出目录 |
| `--powercontext-url` | `POWERCONTEXT_SERVER_URL` | `http://127.0.0.1:8000` | PowerContext Server 地址 |
| `--scope-id` | `SDDCTX_SCOPE_ID` | `sddctx:order-discount` | 逻辑作用域名 |
| — | `MINIMAX_API_KEY` | — | MiniMax API Key |
| — | `MINIMAX_MODEL` | `MiniMax-M3` | 使用的模型名 |
| — | `MINIMAX_REGION` | `global` | 接口域名 |

---

## 3. 数据初始化

```bash
# 1) 启动 PowerContext Server（scripts/run_demo.sh 会自动启动，这里是手动方式）
.venv-powercontext/bin/powercontext server run --env-file scripts/powercontext.env

# 2) 导入规格 / 代码 /测试到嵌入式 seekdb
.venv/bin/python -m sddctx import-materials
```

导入后 seekdb（库名 `sddctx`）里有五张表：

| 表 | 内容 | 写入时机 |
| --- | --- | --- |
| `spec_entry` | 规格条目（编号、状态、规则、来源、验收、文档行号） | `import-materials` |
| `code_symbol` | 代码符号（文件、符号、类型、行号、签名、文档、函数体） | `import-materials` |
| `test_case` | 测试用例（文件、用例名、pytest 标记、行号） | `import-materials` |
| `verification_result` | 每次测试运行的命令、退出码、统计与代码版本 | `verify` / `demo` |
| `query_log` | 检索过程实际执行的 SQL 与命中行数 | `context` / `demo` |

嵌入式 seekdb 的数据目录是 `minimax/runtime/seekdb`（已加入 `.gitignore`），
删除该目录即可完全重建。

---

## 4. 调用入口

模块入口是命令行：`python -m sddctx <子命令>`（等价于 `python -m sddctx.cli`）。

| 子命令 | 作用 | 关键参数 |
| --- | --- | --- |
| `import-materials` | 把规格、代码、测试导入 seekdb | — |
| `context` | 检索并输出开发上下文 | `--task` `--task-id` `--out` `--no-state` |
| `apply` | 把上下文交给 MiniMax 生成补丁并应用 | `--transport {http,cli,file}` `--recorded` `--model` `--no-apply` |
| `verify` | 运行目标功能测试与回归测试，结果写回 seekdb | `--suite {target,regression,all}` `--phase {before,after}` `--log-dir` |
| `save-state` | 把任务状态写入 PowerContext | `--done` `--pending` `--artifact` |
| `resume` | 读取 PowerContext 中保存的任务状态 | `--task-id` |
| `demo` | 按题目流程跑完整一遍并产出技术使用记录 | `--transport` `--recorded` `--reset` `--skip-apply` `--skip-verify` |
| `reset` | 把演示工程恢复到修改前状态 | `--project` |
| `reset-state` | 丢弃本地作用域绑定，下次从空状态开始 | — |
| `snapshot` | 保存工程快照并生成前后 unified diff | `--name` `--diff-out` |

所有子命令都支持 `--json`（结构化输出）与全局参数
（`--project` `--work-dir` `--records-dir` `--powercontext-url` `--scope-id`）。

**上下文模块的输出**（`context` 子命令，Markdown 与 JSON 两种形式）固定包含五节：

1. 适用的规格条目（含规格编号、状态、规则、文档行号、实现位置、验收测试名）
2. 需要修改的代码文件或符号（含文件、行号、签名、命中原因）
3. 用于验证功能及兼容性的测试（含用例名、pytest 标记、行号、命中原因）
4. 已有任务状态与验证结果（来自 PowerContext）
5. 本次上下文使用的数据库查询（SQL 与命中行数）

### 一键脚本

| 脚本 | 作用 |
| --- | --- |
| `scripts/setup.sh` | 安装依赖、生成服务端配置 |
| `scripts/run_demo.sh` | 端到端演示，产出全部记录与日志 |
| `scripts/verify_before_after.sh` | 单独复现"修改前失败 / 修改后通过"，并校验四组结果 |
| `scripts/reset_demo.sh` | 把演示工程恢复为修改前状态（`--wipe-runtime` 连运行期数据一起清） |
| `scripts/spec_update_check.sh` | 验证"规格更新并重新导入后使用更新后的内容" |

---

## 5. 测试命令

```bash
cd minimax

# sddctx 模块自身的单元测试
.venv/bin/python -m pytest tests -q

# 演示工程的目标功能测试（修改前必须失败，修改后必须通过）
cd demo_project && ../.venv/bin/python -m pytest -p no:cacheprovider -q -m target

# 演示工程的回归测试（修改前后都必须通过）
cd demo_project && ../.venv/bin/python -m pytest -p no:cacheprovider -q -m regression

# 全部用例
cd demo_project && ../.venv/bin/python -m pytest -p no:cacheprovider -q
```

也可以直接调用模块子命令，它会同时把结果写进 seekdb 与日志文件：

```bash
.venv/bin/python -m sddctx verify --phase before --suite target --log-dir demo_project/logs
.venv/bin/python -m sddctx verify --phase after  --suite all    --log-dir demo_project/logs
```

---

## 6. 已知限制

1. **演示用的 MiniMax 响应是离线记录**。评测环境若无 `MINIMAX_API_KEY`，
   `apply` 走 `file` 传输读取 `records/minimax_response.json`；该文件里保存的是
   MiniMax-M3.1-Flash 返回的真实 unified diff，可被逐字复核。拿到密钥后用
   `SDDCTX_TRANSPORT=http` 即可走官方接口重跑同一流程。
2. **检索是关键词 + 规格回链的混合召回**，没有向量语义检索。中文按 3-gram
   切分后做 `LIKE` 打分，并叠加 `MATCH ... AGAINST`（ngram 全文索引）与
   "规格声明的来源/验收"回链。对本演示的 4 条规格足够，换成更大工程需要
   补充召回策略。
3. **嵌入式 seekdb 不支持参数绑定与结果集元数据**。`pylibseekdb` 的游标只有
   `execute/fetchall/fetchone`，没有 `description`、没有 `rowcount`、没有
   占位符，因此所有动态值都在 `sddctx/store.py` 里手工转义成 SQL 字面量，
   查询必须显式给出列名。
4. **补丁应用是自研的最小实现**，只支持标准 unified diff 的单文件/多文件
   hunk，且要求上下文能定位；上下文不匹配时会明确报错而不是强行打补丁。
5. **PowerContext 的状态检索是按作用域内的记忆条目做文本匹配**，
   `latest()` 依赖 `updated_at` 排序；同一作用域内多次保存会累积历史条目，
   需要"从空状态开始"时执行 `python -m sddctx reset-state`。
6. **单进程假设**：模块假定同一时刻只有一个进程在写同一个演示工程。
