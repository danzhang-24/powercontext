# 验证样例

本样例是赛题要求的"验证样例"，明确了**要改什么**与**哪些原有行为必须保持**，
并给出可重复执行的操作步骤、预期结果与重置方法。

---

## 1. 任务描述

> **让满减门槛只按商品小计计算，并排除含易碎品的订单。**

### 1.1 要改什么（目标行为）

| 编号 | 目标行为 | 规格条目 |
| --- | --- | --- |
| G-1 | 满减门槛只按商品小计（不含运费）计算。商品小计 95 元、运费 20 元的订单不满足 100 元门槛；商品小计 99.99 元、运费 0.01 元的订单同样不满足门槛。 | SPEC-DISC-002 |
| G-2 | 订单中只要包含一行易碎品商品，整单不享受满减优惠，优惠金额为 0 元；运费不改变这一结论。 | SPEC-DISC-003 |

对应到代码，只允许修改 `src/order_discount/engine.py::compute_discount`。

### 1.2 哪些原有行为必须保持（回归约束）

| 编号 | 必须保持的行为 | 规格条目 | 对应回归测试 |
| --- | --- | --- | --- |
| K-1 | 满 600 元减 80 元，满 300 元减 30 元，满 100 元减 10 元；门槛取"大于等于"，只命中最高一档。 | SPEC-DISC-001 | `test_tier_600_subtotal`、`test_tier_300_subtotal`、`test_below_threshold_has_no_discount` |
| K-2 | 会员订单在满减金额基础上再享受 5% 折扣，保留两位小数；无满减时会员折扣不产生优惠。 | SPEC-DISC-004 | `test_member_discount_applies_on_tier`、`test_empty_order_has_no_discount` |
| K-3 | 已达门槛的订单，运费不改变优惠金额。 | SPEC-DISC-002 | `test_shipping_does_not_change_qualifying_discount` |

### 1.3 任务描述中"哪些原有行为必须保持"如何进入上下文

上下文模块在检索时除了按任务描述做关键词召回，还会沿规格的 **来源** 字段
回链到需要修改的符号、沿 **验收** 字段回链到测试用例，因此上面 1.1 与 1.2
两组约束都会出现在交给 MiniMax 的上下文里（见
`records/context_T-1.md` 与 `records/minimax_dev_record.md` 的"提供给模型的上下文"）。

---

## 2. 有效规格

规格文件：`demo_project/specs/order_discount.spec.md`

| 编号 | 标题 | 优先级 | 状态 | 来源 | 验收测试 |
| --- | --- | --- | --- | --- | --- |
| SPEC-DISC-001 | 满减阶梯 | P0 | 已实现 | `src/order_discount/engine.py::DISCOUNT_TIERS` | `test_tier_300_subtotal`、`test_tier_600_subtotal`、`test_below_threshold_has_no_discount` |
| SPEC-DISC-002 | 满减门槛只按商品小计计算 | P0 | **待实现** | `src/order_discount/engine.py::compute_discount` | `test_threshold_ignores_shipping`、`test_threshold_boundary_excludes_subtotal_below_100` |
| SPEC-DISC-003 | 含易碎品的订单不参与满减 | P0 | **待实现** | `src/order_discount/engine.py::compute_discount` | `test_fragile_order_is_excluded_from_tier_discount`、`test_fragile_order_with_shipping_stays_excluded` |
| SPEC-DISC-004 | 会员在满减金额上再打 95 折 | P1 | 已实现 | `src/order_discount/engine.py::MEMBER_DISCOUNT_RATE` | `test_member_discount_applies_on_tier`、`test_empty_order_has_no_discount` |

规格条目里的"来源"与"验收"都指向真实存在的文件与用例；导入时若来源文件不存在，
模块直接报错，不会生成假来源。

---

## 3. 初始数据

初始数据是演示工程 `demo_project/`，初始状态保存在
`demo_project/snapshots/before/`：

```
demo_project/
├── specs/order_discount.spec.md     # 规格（4 条）
├── src/order_discount/
│   ├── __init__.py
│   ├── models.py                    # OrderItem / Order
│   └── engine.py                    # compute_discount（待修改）
├── tests/test_order_discount.py     # 10 个用例：4 个 target + 6 个 regression
├── pytest.ini                       # 注册 target / regression 标记
├── patches/                         # 生成的 unified diff
├── logs/                            # 修改前后四组测试的运行日志
└── snapshots/before|after/          # 修改前后代码快照
```

初始的 `compute_discount` 实现：

```python
def compute_discount(order: Order) -> float:
    amount = order.total          # ← 门槛含运费，不满足 SPEC-DISC-002
    discount = 0.0
    for threshold, reduction in DISCOUNT_TIERS:
        if amount >= threshold:
            discount = reduction
            break
    if discount and order.member:
        discount = round(discount * (1 - MEMBER_DISCOUNT_RATE), 2)
    return discount               # ← 未处理易碎品，不满足 SPEC-DISC-003
```

数据库侧初始数据为空：`import-materials` 是第一次写入；`runtime/seekdb`
被删除后即回到"无任何资料"的状态。

PowerContext 侧初始状态为空：`python -m sddctx reset-state` 会丢弃本地作用域绑定，
下次保存状态时新建一个空作用域。

---

## 4. 操作步骤

```bash
cd minimax
bash scripts/setup.sh          # 一次性：安装依赖、生成服务端配置
bash scripts/run_demo.sh       # 端到端演示（等价于下面 4.1 的命令序列）
```

### 4.1 等价的手工命令序列

```bash
# 0) 启动 PowerContext Server
.venv-powercontext/bin/powercontext server run --env-file scripts/powercontext.env &

# 1) 从空状态开始
.venv/bin/python -m sddctx reset-state
.venv/bin/python -m sddctx reset              # 工程回到修改前状态

# 2) 导入资料到 seekdb
.venv/bin/python -m sddctx import-materials

# 3) 检索开发上下文
.venv/bin/python -m sddctx context \
    --task "让满减门槛只按商品小计计算，并排除含易碎品的订单" \
    --out records/context_T-1.md

# 4) 修改前跑测试（target 必须失败、regression 必须通过）
.venv/bin/python -m sddctx verify --phase before --log-dir demo_project/logs

# 5) 把上下文交给 MiniMax 生成补丁并应用
.venv/bin/python -m sddctx apply --transport file \
    --recorded records/minimax_response.json
#   有 MINIMAX_API_KEY 时改为：--transport http

# 6) 修改后跑测试（两组都必须通过）
.venv/bin/python -m sddctx verify --phase after --log-dir demo_project/logs

# 7) 保存任务状态到 PowerContext
.venv/bin/python -m sddctx save-state --task-id T-1 --phase after \
    --done "导入资料并检索上下文" --done "MiniMax 完成代码修改"

# 8) 重启模块后读取并复用状态（独立进程）
.venv/bin/python -m sddctx resume --task-id T-1

# 9) 保存修改后快照并生成前后差异
.venv/bin/python -m sddctx snapshot --name after
```

### 4.2 单独复现"修改前失败 / 修改后通过"

```bash
bash scripts/verify_before_after.sh
```

脚本会跑完上述第 1、4、5、6 步并逐项校验四组结果，不符合预期时以非零码退出。

### 4.3 单独复现"规格更新后重新导入"

```bash
bash scripts/spec_update_check.sh
```

脚本会在 SPEC-DISC-003 的规则末尾追加一条新约束，用独立工作目录重新导入并重新
检索，然后检查检索输出中出现的是**更新后**的规则文本；结束时自动还原规格文件。
证据保存在 `records/spec_update_record.md`。

---

## 5. 预期结果

### 5.1 检索上下文（步骤 3）

`records/context_T-1.md` 必须包含：

- 规格条目按相关度排序，**SPEC-DISC-002 与 SPEC-DISC-003 在前两位**；
- 每条规格给出规则原文、文档行号、实现位置（`src/order_discount/engine.py:行区间`）、
  验收测试名；
- 代码部分包含 `compute_discount`（命中原因："规格 SPEC-DISC-002 声明的实现位置"）
  以及 `Order.subtotal` / `Order.total` 等关键词命中项；
- 测试部分包含全部 4 个 `target` 用例与 6 个 `regression` 用例及其行号；
- 第五节列出本次实际执行的 SQL。

### 5.2 修改前（步骤 4）

| 套件 | 退出码 | 统计 | 说明 |
| --- | --- | --- | --- |
| `target` | **1** | 0 通过 / **4 失败** | 失败必须是 `AssertionError`（如 `assert 10.0 == 0.0`），不是缺依赖或无法启动 |
| `regression` | **0** | **6 通过** / 0 失败 | 原有行为保持 |

日志：`demo_project/logs/before-target.log`、`demo_project/logs/before-regression.log`。

### 5.3 修改后（步骤 6）

| 套件 | 退出码 | 统计 |
| --- | --- | --- |
| `target` | **0** | **4 通过** / 0 失败 |
| `regression` | **0** | **6 通过** / 0 失败 |

日志：`demo_project/logs/after-target.log`、`demo_project/logs/after-regression.log`。
两份日志都记录了命令、退出码、统计、代码版本（`git:<sha>+content:<sha12>`）与完整输出。

### 5.4 状态复用（步骤 7、8）

- `save-state` 返回 200，并在 PowerContext 里留下作用域 `scp_...` 的一条记忆，
  记忆正文是 `sddctx-state v1` 开头的状态文本；
- **另起一个进程**执行 `resume`，能读回同一条状态：包含已完成事项、待办事项、
  产出物，以及四条验证结果（修改前后的 target / regression）；
- 该状态在后续检索中会作为"已有任务状态与验证结果"进入上下文。

记录：`records/powercontext_state_record.md`。

### 5.5 实际观测到的结果

| 项 | 结果 |
| --- | --- |
| 导入 | 规格 4 条 / 代码符号 7 个 / 测试用例 10 条 |
| 检索命中规格 | `SPEC-DISC-002, SPEC-DISC-003, SPEC-DISC-001, SPEC-DISC-004` |
| 检索命中代码 | `compute_discount, MEMBER_DISCOUNT_RATE, Order, Order.subtotal, Order.total` |
| 修改前 target | exit=1，0 通过 / 4 失败（全部 `AssertionError`） |
| 修改前 regression | exit=0，6 通过 |
| 修改后 target | exit=0，4 通过 |
| 修改后 regression | exit=0，6 通过 |
| 状态写入 / 重启读取 | 是 / 是 |

---

## 6. 重置方法

```bash
# 把演示工程恢复到修改前状态
bash scripts/reset_demo.sh

# 连运行期数据（seekdb 索引、PowerContext 本地库）一起清空
bash scripts/reset_demo.sh --wipe-runtime
```

等价的手工命令：

```bash
# 工程回到修改前
.venv/bin/python -m sddctx reset

# PowerContext 侧从空状态开始
.venv/bin/python -m sddctx reset-state
```

`reset` 会用 `demo_project/snapshots/before/` 覆盖 `src/`、`tests/`、`pytest.ini`
与规格文件，并删除 `patches/*.patch` 与 `logs/`；`reset-state` 会删除本地作用域
绑定文件 `runtime/scope.json`，下次保存状态时 PowerContext 会新建一个空作用域。

验证样例本身是幂等的：重复执行第 4 节的命令序列会得到同样的结果。
