# SDD 上下文管理系统（MiniMax 赛题）

面向软件持续演进的 SDD（Spec-Driven Development）上下文模块：把规格、代码与测试
导入 **seekdb**，按任务描述检索出开发上下文，交给 **MiniMax** 完成代码修改，
运行功能与回归测试，再把任务状态存入 **PowerContext**，模块重启后读取并复用。

### 提交信息

| 项 | 值 |
| --- | --- |
| 赛题 | 《规有所依——面向软件持续演进的 SDD 上下文管理系统》 |
| 交付目录 | `minimax/`(本目录) |
| 主要交付物 | `sddctx/` 上下文管理模块 + `demo_project/` + `records/` 实测记录 |
| 一键验证 | `bash minimax/scripts/acceptance_check.sh`(六项必做项自检) |
| 索引 | 仓库根目录 [`SUBMISSIONS.md`](../SUBMISSIONS.md) |

- 任务描述与验收要求：[`docs/validation-sample.md`](docs/validation-sample.md)
- **六项必做项逐项对照与复现命令**：[`docs/acceptance-checklist.md`](docs/acceptance-checklist.md)
- 运行说明（依赖版本、配置、入口、测试命令、已知限制）：[`docs/run-guide.md`](docs/run-guide.md)
- 一页技术说明（模块结构、上下文选择方式、技术分工）：[`docs/tech-design.md`](docs/tech-design.md)

---

## 快速开始

```bash
cd minimax
bash scripts/setup.sh          # 安装依赖（sddctx + PowerContext Server），生成服务端配置
bash scripts/run_demo.sh       # 端到端演示，产出记录与日志
bash scripts/acceptance_check.sh   # 逐项自检赛题六项必做项（日志写入 records/acceptance_run.log）
```

`setup.sh` 会顺手处理两件容易卡住的事：

1. **powercontext 的 extras**——它把 FastMCP / typer / pylibseekdb 等运行期依赖放在
   extras 里，基础包装不全，`powercontext server run` 会直接报 `ModuleNotFoundError`。
2. **运行期目录探测**——嵌入式 seekdb 底层用 O_DIRECT 直写，数据目录必须在本地
   文件系统上（NFS 会报 `seekdb_open failed: code=-1`）。脚本会探测候选目录并把
   可用的那个写进 `scripts/runtime.env`；也可以用 `SDDCTX_HOME=/本地路径` 指定。

单独复现验收要点：

```bash
bash scripts/verify_before_after.sh   # 同一组目标功能测试：修改前失败、修改后通过
bash scripts/spec_update_check.sh     # 规格更新并重新导入后使用更新后的内容
```

模块自身的单元测试：

```bash
.venv/bin/python -m pytest tests -q
```

---

## 目录结构

| 路径 | 内容 |
| --- | --- |
| `sddctx/` | 上下文模块源码（检索、模型调用、验证、状态存取） |
| `demo_project/` | 演示业务工程：订单优惠计算，含规格、源码、测试、前后快照与补丁 |
| `records/` | 技术使用记录：MiniMax 开发记录、数据库查询记录、PowerContext 状态记录 |
| `docs/` | 运行说明、验证样例、一页技术说明 |
| `scripts/` | 安装、演示、前后对比、规格更新检查等脚本 |
| `tests/` | 模块自身的单元测试 |

---

## 命令行入口

```
python -m sddctx <子命令> [全局参数]

子命令
  import-materials   把规格、代码与测试导入 seekdb
  context            按任务描述检索并输出开发上下文
  apply              把上下文交给 MiniMax 生成补丁并应用
  verify             运行目标功能测试与回归测试，结果写入 seekdb
  save-state         把任务状态写入 PowerContext
  resume             读取 PowerContext 中保存的任务状态（模块重启后复用）
  demo               按题目流程跑完整一遍并产出技术使用记录
  reset              把演示工程恢复到修改前状态
  reset-state        丢弃本地作用域绑定，下次从空状态开始
  snapshot           保存工程快照并生成前后 unified diff

全局参数
  --project --work-dir --records-dir --powercontext-url --scope-id --json
```

上下文输出固定包含五节：**适用的规格条目 / 需要修改的代码文件或符号 /
用于验证功能及兼容性的测试 / 已有任务状态与验证结果 / 本次上下文使用的数据库查询**，
每条来源都带真实路径与行号。

---

## 三项技术的接入方式

| 技术 | 接入方式 | 版本 |
| --- | --- | --- |
| MiniMax | HTTP `POST {base}/v1/chat/completions`（默认 `MiniMax-M3`）；另支持 `mmx` CLI 与离线重放 | 平台接口；本次记录为 `MiniMax-M3.1-Flash` |
| seekdb | 嵌入式 `pylibseekdb`；设置 `SDDCTX_DB_DSN` 可切换到外部 seekdb / OceanBase | 1.4.0.post1 |
| PowerContext | HTTP API：`/v1/scopes`、`/v1/memory/remember`、`/v1/memory/search` | 1.2.0 |

凭据一律通过环境变量或本地凭据文件注入，仓库里不存放任何真实密钥；
`scripts/powercontext.env` 与配置示例均为占位值。

> **本次提交的 MiniMax 调用方式**：开发任务由 MiniMax（`MiniMax-M3.1-Flash`）在
> Agent 会话中完成，上下文由 `sddctx` 从 seekdb 检索后提供，模型返回的原文存档于
> `records/minimax_response.json`；演示脚本默认以 `file` 传输重放该存档，所以记录中
> 没有 HTTP 层的 token 用量与耗时。拿到 `MINIMAX_API_KEY` 后执行
> `SDDCTX_TRANSPORT=http bash scripts/run_demo.sh` 即可走官方接口重新生成补丁。

---

## 提交材料对照

| 赛题要求 | 位置 |
| --- | --- |
| 完整源码 | `sddctx/`、`demo_project/` |
| 运行说明 | `docs/run-guide.md` |
| 验证样例 | `docs/validation-sample.md` |
| 修改前后代码快照 | `demo_project/snapshots/before/`、`demo_project/snapshots/after/` |
| 代码差异 | `demo_project/patches/before-after.patch`、`demo_project/patches/T-1.patch` |
| 新增功能测试 / 回归测试 | `demo_project/tests/test_order_discount.py`（`target` 4 个 / `regression` 6 个） |
| 运行日志 | `demo_project/logs/{before,after}-{target,regression}.log`、`records/demo_run.log`、`records/acceptance_run.log` |
| 六项必做项对照 | `docs/acceptance-checklist.md`（含一键自检脚本 `scripts/acceptance_check.sh`） |
| MiniMax 开发记录 | `records/minimax_dev_record.md` / `.json` |
| 数据库查询记录 | `records/db_query_record.md` / `.json` |
| PowerContext 状态写入与复用记录 | `records/powercontext_state_record.md` / `.json` |
| 规格更新后重新导入的验证 | `records/spec_update_record.md` |
| 一页技术说明 | `docs/tech-design.md` |
