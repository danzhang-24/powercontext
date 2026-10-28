# SDD 上下文管理系统（MiniMax 赛题）

面向软件持续演进的 SDD（Spec-Driven Development）上下文模块：把规格、代码与测试
导入 **seekdb**，按任务描述检索出开发上下文，交给 **MiniMax** 完成代码修改，
运行功能与回归测试，再把任务状态存入 **PowerContext**，模块重启后读取并复用。

- 任务描述与验收要求：[`docs/validation-sample.md`](docs/validation-sample.md)
- 运行说明（依赖版本、配置、入口、测试命令、已知限制）：[`docs/run-guide.md`](docs/run-guide.md)
- 一页技术说明（模块结构、上下文选择方式、技术分工）：[`docs/tech-design.md`](docs/tech-design.md)

---

## 快速开始

```bash
cd minimax
bash scripts/setup.sh        # 安装依赖（sddctx + PowerContext Server），生成服务端配置
bash scripts/run_demo.sh     # 端到端演示，产出记录与日志
```

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
| MiniMax | HTTP `POST {base}/v1/chat/completions`（默认 `MiniMax-M3`）；另支持 `mmx` CLI 与离线重放 | 平台接口 |
| seekdb | 嵌入式 `pylibseekdb`；设置 `SDDCTX_DB_DSN` 可切换到外部 seekdb / OceanBase | 1.4.0.post1 |
| PowerContext | HTTP API：`/v1/scopes`、`/v1/memory/remember`、`/v1/memory/search` | 1.2.0 |

凭据一律通过环境变量或本地凭据文件注入，仓库里不存放任何真实密钥；
`scripts/powercontext.env` 与配置示例均为占位值。

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
| 运行日志 | `demo_project/logs/{before,after}-{target,regression}.log` |
| MiniMax 开发记录 | `records/minimax_dev_record.md` / `.json` |
| 数据库查询记录 | `records/db_query_record.md` / `.json` |
| PowerContext 状态写入与复用记录 | `records/powercontext_state_record.md` / `.json` |
| 规格更新后重新导入的验证 | `records/spec_update_record.md` |
| 一页技术说明 | `docs/tech-design.md` |
