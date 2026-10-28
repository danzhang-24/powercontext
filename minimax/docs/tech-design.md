# 一页技术说明

**规有所依——面向软件持续演进的 SDD 上下文管理系统**

---

## 1. 模块结构

```
minimax/
├── sddctx/                      上下文模块（可安装、可调用的 Python 包）
│   ├── config.py                运行期配置（路径、端点、模型与密钥来源）
│   ├── store.py                 seekdb 存储层（建表、写入、按列查询）
│   ├── materials.py             资料解析：规格 Markdown / 代码 AST / 测试标记
│   ├── retrieval.py             检索与上下文组装（关键词 + 全文 + 规格回链）
│   ├── context.py               上下文数据模型（SpecRef/CodeRef/TestRef/…）
│   ├── minimax_client.py        MiniMax 客户端（http / cli / file 三种传输）
│   ├── assistant.py             提示词拼装、补丁解析与补丁应用
│   ├── verifier.py              测试执行与结果统计（命令/退出码/代码版本）
│   ├── task_state.py            任务状态模型 + PowerContext 读写
│   ├── reset.py / snapshot.py   工程重置与前后快照、差异生成
│   ├── pipeline.py              流程编排与三类技术使用记录
│   └── cli.py                   命令行入口
├── demo_project/                演示业务工程（订单优惠计算）
├── records/                     技术使用记录（MiniMax / 数据库 / PowerContext）
├── docs/                        运行说明、验证样例、本文件
├── scripts/                     安装、演示、前后对比、规格更新等脚本
└── tests/                       模块自身的单元测试
```

**入口**：`python -m sddctx <子命令>`（CLI）。
子命令：`import-materials` / `context` / `apply` / `verify` / `save-state` /
`resume` / `demo` / `reset` / `reset-state` / `snapshot`。

**输入**：任务描述（自然语言）、工程目录、PowerContext 地址、MiniMax 凭据。
**输出**：五节式开发上下文（Markdown / JSON）、补丁、测试结论、任务状态。

---

## 2. 上下文选择方式

上下文不是"把所有资料塞给模型"，而是由**数据库检索 + 规格回链**两条路径共同决定：

1. **关键词召回**：把任务描述切成检索词（中文 3-gram + ASCII 标识符），
   在 `spec_entry` / `code_symbol` / `test_case` 三张表上做 `LIKE` 打分查询，
   并叠加 `MATCH ... AGAINST`（ngram 全文索引）查询，两路结果合并后按分数排序。
2. **规格回链**：以命中的规格为锚点，沿规格的 **来源** 字段取回实现该规则的
   代码符号，沿 **验收** 字段取回覆盖该规格的测试用例。
   回链命中的条目分数置为最高，保证"要改哪里""用哪测"一定出现在上下文里。
3. **状态复用**：从 PowerContext 读回上次保存的任务状态（已完成、待办、验证结果），
   作为上下文的第四节。
4. **来源可核对**：每条上下文都带真实路径与行号，摘录直接从磁盘文件读取；
   规格声明的来源文件不存在时，导入阶段直接报错。

上下文固定输出五节：
**适用的规格条目 / 需要修改的代码文件或符号 / 用于验证功能及兼容性的测试 /
已有任务状态与验证结果 / 本次上下文使用的数据库查询**。

---

## 3. 各项技术分工

| 技术 | 承担的具体工作 | 落点 |
| --- | --- | --- |
| **MiniMax** | 依据上下文里的规格条目与代码摘录产出 unified diff，模块负责解析并应用 | `sddctx/minimax_client.py`、`sddctx/assistant.py`；HTTP `POST {base}/v1/chat/completions`（默认 `MiniMax-M3`），另支持 `mmx` CLI 与离线重放 |
| **seekdb** | 存放工程资料与索引：规格条目、代码符号、测试用例、验证结果、检索日志；检索结果直接进入任务上下文 | `sddctx/store.py`、`sddctx/materials.py`、`sddctx/retrieval.py`；嵌入式 `pylibseekdb`，也可通过 `SDDCTX_DB_DSN` 指向外部 seekdb / OceanBase |
| **PowerContext** | 保存任务进展与验证结果；模块重启后读取并用于后续上下文组装 | `sddctx/task_state.py`；HTTP API `POST /v1/scopes`、`POST /v1/memory/remember`、`POST /v1/memory/search`；作用域绑定写在 `runtime/scope.json`，重启后复用同一作用域 |

三者构成一条闭环：**数据库提供"事实"，模型基于事实产出改动，PowerContext 记住
"进展"**。改动落地后再由测试验证，验证结果写回数据库与 PowerContext，
下一次检索时作为上下文的一部分出现。

---

## 4. 一次演示的数据流

```
specs/*.md ┐
src/**/*.py├─ import-materials ─→ seekdb(spec_entry / code_symbol / test_case)
tests/*.py ┘
                              │
任务描述 ──────────────────────┼─ context ─→ 关键词召回 + 规格回链 ─→ 五节式上下文
                              │                                          │
PowerContext(scope.json) ────┘                                          ▼
                                                            MiniMax 生成 unified diff
                                                                      │
                                                                      ▼
                                             apply（模块自研补丁应用）→ 代码改动
                                                                      │
                                                                      ▼
                                      verify(target / regression) ─→ seekdb(verification_result)
                                                                      │
                                                                      ▼
                                     save-state ─→ PowerContext(memory) ─→ resume(复用)
```

---

## 5. 关键取舍

- **规格是唯一事实源**：代码与测试不参与"正确性判断"，只作为被规格回链的产物，
  因此新增规格即新增约束，不存在"代码说了算"的漂移。
- **回链优先于打分**：规格声明的来源与验收一定进入上下文，避免关键词打分把关键
  条目挤掉。
- **失败必须可解释**：修改前的失败记录为 `AssertionError` 而不是环境错误，
  且测试文件在修改前后逐字节一致（同一份快照），不允许删断言或改预期。
- **状态外置**：任务状态存在 PowerContext 而不是模块内存，重启模块后仍能续跑。
