# 验收对照表（赛题六项必做项）

赛题规则：**六项必做项全部通过得 20 分，任一项不通过得 0 分。** 本文件逐项给出
复现命令、对应产出与实测结果，评审可按此顺序核验。

一键自检：

```bash
cd minimax
bash scripts/setup.sh          # 安装依赖 + 探测运行期目录
bash scripts/acceptance_check.sh   # 逐项跑完六项必做项，日志写入 records/acceptance_run.log
```

最近一次自检结果：**11 项全部通过（未通过 0 项）**，完整日志见
`records/acceptance_run.log`。

| # | 验收项 | 复现命令 | 对应产出 | 实测结果 |
| --- | --- | --- | --- | --- |
| 1 | 能够运行 | `bash scripts/setup.sh` → `bash scripts/run_demo.sh` | `records/demo_run.log` | exit=0，流程 6 步全部完成 |
| 2 | MiniMax 实际参与 | 查看 `records/minimax_dev_record.md` | 提供给模型的完整提示词（检索到的规格/代码/测试来源）、模型返回原文、解析出的 diff、补丁与提交差异的对应关系 | 记录含上下文 / 模型原文 / 差异对应三节 |
| 3 | 上下文正确 | `bash scripts/spec_update_check.sh` | `records/spec_update_record.md`、`records/context_T-1.md` | 规格更新并重新导入后，检索结果使用更新后的规则文本 |
| 4 | 数据库实际参与 | 查看 `records/db_query_record.md` | 每条检索的真实 SQL、命中行数、写入的表 | 6 条查询命中规格 3/4 行、代码 4 行、测试 9 行 |
| 5 | 状态能够复用 | `reset-state` → `demo` → `resume`（新进程） | `records/powercontext_state_record.md` | 从空状态开始保存，新进程重启后读回并用于后续上下文 |
| 6 | 代码修改有效 | `bash scripts/verify_before_after.sh` | `demo_project/logs/{before,after}-{target,regression}.log`、`demo_project/patches/before-after.patch` | 修改前 target 退出码 1（4 个断言失败，非环境错误）；修改后 target 退出码 0（4 passed）；回归测试前后均退出码 0（6 passed） |

附加：`python -m pytest tests -q`（模块自身单元测试）21 passed。

## 逐项说明

### 1. 能够运行

`scripts/setup.sh` 做两件容易卡住的事：

- **powercontext 的 extras**——`powercontext 1.2.0` 把 FastMCP / typer / pylibseekdb
  等运行期依赖放在 extras 里，只装基础包时 `powercontext server run` 会直接报
  `ModuleNotFoundError: No module named 'typer'`。脚本按
  `powercontext[server,seekdb,cli]==1.2.0` 安装。
- **运行期目录探测**——嵌入式 seekdb 底层用 O_DIRECT 直写，数据目录必须落在
  支持 O_DIRECT 的本地文件系统上；放在 NFS 上会报
  `seekdb_open failed: code=-1`。脚本用 `scripts/probe_runtime_dir.py` 逐个探测候选
  目录，写入 `scripts/runtime.env`（该文件含本机路径，不进版本库）。

`scripts/run_demo.sh` 跑完整流程：导入资料 → 检索上下文 → MiniMax 改码 →
修改前/后两轮测试 → 保存状态 → 重启读取 → 生成前后差异。

### 2. MiniMax 实际参与

`records/minimax_dev_record.md` 分四节：提供给模型的上下文（含完整提示词）、
模型的代码修改过程（模型返回原文 + 解析出的 unified diff）、补丁与提交代码差异
的对应关系。

**本次提交里的响应是离线存档**：开发任务由 MiniMax（`MiniMax-M3.1-Flash`）在 Agent
会话中完成，上下文由本模块从 seekdb 检索后提供，模型返回的原文存档在
`records/minimax_response.json`，演示脚本以 `file` 传输重放它。因为不是 HTTP 调用，
记录里没有 token 用量与耗时统计。评审若持有 `MINIMAX_API_KEY`，执行

```bash
SDDCTX_TRANSPORT=http bash scripts/run_demo.sh
```

即可走 MiniMax 官方 HTTP 接口重新生成补丁，流程与产物结构完全一致。

### 3. 上下文正确

`scripts/spec_update_check.sh` 会备份规格 → 在 SPEC-DISC-003 追加一条新约束 →
用独立工作目录重新导入并重新检索 → 校验检索输出里出现的是**更新后**的规则文本 →
还原规格文件。结果见 `records/spec_update_record.md`。

### 4. 数据库实际参与

工程资料全部落在 seekdb（嵌入式 `pylibseekdb`，库名 `sddctx`）的五张表里：
`spec_entry`（规格条目）、`code_symbol`（代码符号）、`test_case`（测试用例）、
`verification_result`（验证结果）、`query_log`（检索日志）。

`records/db_query_record.md` 记录了构造上下文时**实际执行**的 SQL 与命中行数，
包括规格打分查询、全文索引 `MATCH ... AGAINST` 查询、规格回链查询等。

### 5. 状态能够复用

任务状态写入 PowerContext（HTTP API：`/v1/scopes`、`/v1/memory/remember`、
`/v1/memory/search`），作用域绑定写在 `runtime/scope.json`。
验收脚本的顺序是：清空作用域绑定（从空状态开始）→ 跑一遍流程写入状态 → **用新进程**
读取，证明模块重启后状态可读，且下一轮检索会把它作为上下文的一部分带出来。

### 6. 代码修改有效

目标：让满减门槛只按商品小计计算，并排除含易碎品的订单
（规格 `SPEC-DISC-002`、`SPEC-DISC-003`，状态为「待实现」）。

- 目标功能测试（`target`，4 个）：修改前**因断言不成立而失败**（退出码 1），
  修改后全部通过（退出码 0）。
- 回归测试（`regression`，6 个）：修改前后都通过（退出码 0）。

`scripts/verify_before_after.sh` 除了比对退出码，还会检查修改前的失败**确实是功能断言
不成立**（`AssertionError`），而不是缺依赖、起不来之类的环境错误——赛题明确禁止用
环境错误冒充修改前的功能失败。

## 已知限制

见 `docs/run-guide.md` 第 6 节。其中与评审直接相关的两条：

1. 本次提交的 MiniMax 响应是离线存档（原因与复现方式见上文第 2 项）。
2. 嵌入式 seekdb 的数据目录必须在本地文件系统上，`setup.sh` 会自动探测。
