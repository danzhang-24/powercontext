# MiniMax 开发记录

- 任务编号：T-1
- 任务描述：让满减门槛只按商品小计计算，并排除含易碎品的订单
- 记录时间：2026-10-28T16:42:20+00:00
- 模型：MiniMax-M3.1-Flash
- 接入方式：MiniMax 会话内调用（模型在开发助手的 Agent 会话中直接返回补丁；上下文由本模块从 seekdb 检索后提供，模型输出原文见本记录第 2 节）
- token 用量 / 耗时：会话内调用没有 HTTP 层的计费与耗时统计，故此处为空；本记录保存的是模型返回的**原始内容**，可与提交的代码差异逐字核对
- 修改的文件：src/order_discount/engine.py

## 1. 提供给模型的上下文

上下文由 seekdb 检索得到，包含以下来源：

- 规格 `SPEC-DISC-002` 满减门槛只按商品小计计算（specs/order_discount.spec.md:25-32）
- 规格 `SPEC-DISC-003` 含易碎品的订单不参与满减（specs/order_discount.spec.md:33-40）
- 规格 `SPEC-DISC-001` 满减阶梯（specs/order_discount.spec.md:17-24）
- 规格 `SPEC-DISC-004` 会员在满减金额上再打 95 折（specs/order_discount.spec.md:41-47）
- 代码 `compute_discount` @ src/order_discount/engine.py:21-38
- 代码 `MEMBER_DISCOUNT_RATE` @ src/order_discount/engine.py:18-18
- 代码 `Order` @ src/order_discount/models.py:30-53
- 代码 `Order.subtotal` @ src/order_discount/models.py:46-48
- 代码 `Order.total` @ src/order_discount/models.py:51-53
- 测试 `test_threshold_ignores_shipping` [target] @ tests/test_order_discount.py:33-36
- 测试 `test_threshold_boundary_excludes_subtotal_below_100` [target] @ tests/test_order_discount.py:40-43
- 测试 `test_fragile_order_is_excluded_from_tier_discount` [target] @ tests/test_order_discount.py:47-50
- 测试 `test_fragile_order_with_shipping_stays_excluded` [target] @ tests/test_order_discount.py:54-57
- 测试 `test_tier_300_subtotal` [regression] @ tests/test_order_discount.py:66-68
- 测试 `test_tier_600_subtotal` [regression] @ tests/test_order_discount.py:72-74
- 测试 `test_below_threshold_has_no_discount` [regression] @ tests/test_order_discount.py:78-80
- 测试 `test_member_discount_applies_on_tier` [regression] @ tests/test_order_discount.py:84-86
- 测试 `test_empty_order_has_no_discount` [regression] @ tests/test_order_discount.py:96-99

### 完整提示词

```text
# 开发任务
让满减门槛只按商品小计计算，并排除含易碎品的订单

# 目标工程
/run/csi/mount-root/nas/eab0d61a99b6696edb3d2aff87b585e8/pc/minimax/demo_project

# 适用规格条目（来自 seekdb 检索）

- SPEC-DISC-002 满减门槛只按商品小计计算 | 优先级 P0 | 状态 待实现
  规则：满减门槛只按商品小计（不含运费）计算。运费金额不计入门槛：商品小计 95 元、运费 20 元的订单不满足 100 元门槛；商品小计 99.99 元、运费 0.01 元的订单同样不满足门槛。
  规格位置：specs/order_discount.spec.md:25-32
  实现位置：src/order_discount/engine.py:21-38

- SPEC-DISC-003 含易碎品的订单不参与满减 | 优先级 P0 | 状态 待实现
  规则：订单中只要包含一行易碎品商品（item.fragile 为真），整单不享受满减优惠，优惠金额为 0 元；运费不改变这一结论。
  规格位置：specs/order_discount.spec.md:33-40
  实现位置：src/order_discount/engine.py:21-38

- SPEC-DISC-001 满减阶梯 | 优先级 P0 | 状态 已实现
  规则：商品金额满足满减门槛时按阶梯减免：满 600 元减 80 元，满 300 元减 30 元，满 100 元减 10 元；门槛取"大于等于"，只命中最高一档。
  规格位置：specs/order_discount.spec.md:17-24
  实现位置：src/order_discount/engine.py:18-18

- SPEC-DISC-004 会员在满减金额上再打 95 折 | 优先级 P1 | 状态 已实现
  规则：会员订单在满减金额基础上再享受 5% 折扣，结果保留两位小数；无满减时会员折扣不产生优惠。
  规格位置：specs/order_discount.spec.md:41-47
  实现位置：src/order_discount/engine.py:18-18

# 需要修改的代码

## 文件 src/order_discount/engine.py 符号 compute_discount (function) 行 21-38
def compute_discount(order: Order) -> float:
    """计算订单优惠金额。

    Args:
        order: 待计算的订单。

    Returns:
        优惠金额（元），保留两位小数。
    """
    amount = order.total
    discount = 0.0
    for threshold, reduction in DISCOUNT_TIERS:
        if amount >= threshold:
            discount = reduction
            break
    if discount and order.member:
        discount = round(discount * (1 - MEMBER_DISCOUNT_RATE), 2)
    return discount

## 文件 src/order_discount/engine.py 符号 MEMBER_DISCOUNT_RATE (constant) 行 18-18
MEMBER_DISCOUNT_RATE = 0.05

## 文件 src/order_discount/models.py 符号 Order (class) 行 30-53
class Order:
    """订单。

    Attributes:
        order_id: 订单号。
        items: 订单行。
        shipping_fee: 运费。规格 SPEC-DISC-002 规定运费不计入满减门槛。
        member: 是否会员。规格 SPEC-DISC-004 规定会员在满减金额上再打 95 折。
    """

    order_id: str
    items: tuple[OrderItem, ...]
    shipping_fee: float = 0.0
    member: bool = False

    @property
    def subtotal(self) -> float:
        """商品小计（不含运费）。"""
        return round(sum(item.subtotal for item in self.items), 2)

    @property
    def total(self) -> float:
        """订单实付金额（商品小计 + 运费）。"""
        return round(self.subtotal + self.shipping_fee, 2)

## 文件 src/order_discount/models.py 符号 Order.subtotal (method) 行 46-48
    def subtotal(self) -> float:
        """商品小计（不含运费）。"""
        return round(sum(item.subtotal for item in self.items), 2)

## 文件 src/order_discount/models.py 符号 Order.total (method) 行 51-53
    def total(self) -> float:
        """订单实付金额（商品小计 + 运费）。"""
        return round(self.subtotal + self.shipping_fee, 2)

# 用于验证的测试

## tests/test_order_discount.py::test_threshold_ignores_shipping [target] 行 33-36
def test_threshold_ignores_shipping():
    """SPEC-DISC-002：运费不计入满减门槛。"""
    order = _order(95.0, shipping=20.0)
    assert compute_discount(order) == 0.0

## tests/test_order_discount.py::test_threshold_boundary_excludes_subtotal_below_100 [target] 行 40-43
def test_threshold_boundary_excludes_subtotal_below_100():
    """SPEC-DISC-002：门槛取商品小计，小计 99.99 元不满足 100 元门槛。"""
    order = _order(99.99, shipping=0.01)
    assert compute_discount(order) == 0.0

## tests/test_order_discount.py::test_fragile_order_is_excluded_from_tier_discount [target] 行 47-50
def test_fragile_order_is_excluded_from_tier_discount():
    """SPEC-DISC-003：含易碎品的订单不享受满减。"""
    order = _order(500.0, fragile=True)
    assert compute_discount(order) == 0.0

## tests/test_order_discount.py::test_fragile_order_with_shipping_stays_excluded [target] 行 54-57
def test_fragile_order_with_shipping_stays_excluded():
    """SPEC-DISC-003：运费不改变易碎品订单不参与满减的结论。"""
    order = _order(95.0, shipping=30.0, fragile=True)
    assert compute_discount(order) == 0.0

## tests/test_order_discount.py::test_tier_300_subtotal [regression] 行 66-68
def test_tier_300_subtotal():
    """SPEC-DISC-001：满 300 元减 30 元。"""
    assert compute_discount(_order(300.0)) == 30.0

## tests/test_order_discount.py::test_tier_600_subtotal [regression] 行 72-74
def test_tier_600_subtotal():
    """SPEC-DISC-001：满 600 元减 80 元，只命中最高一档。"""
    assert compute_discount(_order(600.0)) == 80.0

## tests/test_order_discount.py::test_below_threshold_has_no_discount [regression] 行 78-80
def test_below_threshold_has_no_discount():
    """SPEC-DISC-001：小计 99 元不满足任何门槛。"""
    assert compute_discount(_order(99.0)) == 0.0

## tests/test_order_discount.py::test_member_discount_applies_on_tier [regression] 行 84-86
def test_member_discount_applies_on_tier():
    """SPEC-DISC-004：会员在满减 30 元基础上再打 95 折。"""
    assert compute_discount(_order(300.0, member=True)) == 28.5

## tests/test_order_discount.py::test_empty_order_has_no_discount [regression] 行 96-99
def test_empty_order_has_no_discount():
    """SPEC-DISC-004：无商品时没有优惠。"""
    order = Order(order_id="o-1002", items=(), shipping_fee=12.0, member=True)
    assert compute_discount(order) == 0.0

# 当前任务状态

已完成：导入资料：规格 4 条 / 代码 7 个 / 测试 10 条；MiniMax 完成代码修改：src/order_discount/engine.py
待办：（空）

已有验证结果：
- [before/target] exit=1 passed=0 failed=4 errored=0
- [before/regression] exit=0 passed=6 failed=0 errored=0
- [after/target] exit=0 passed=4 failed=0 errored=0
- [after/regression] exit=0 passed=6 failed=0 errored=0

# 输出要求

1. 严格按照上面给出的规格条目修改代码，只实现规格里"状态"为待实现的条目。
2. 不要修改测试文件，不要新增测试文件，不要修改规格文件。
3. 只修改上下文里列出的文件与符号；如确实需要改动其它文件，在补丁前用一行文字说明原因。
4. 输出一个 unified diff，路径相对于工程根目录，格式如下：

```diff
diff --git a/src/order_discount/engine.py b/src/order_discount/engine.py
--- a/src/order_discount/engine.py
+++ b/src/order_discount/engine.py
@@ -21,7 +21,12 @@
 ...
```

5. 除补丁外不要输出其它内容。
```

## 2. 模型的代码修改过程

模型返回内容（原文）：

```text
```diff
diff --git a/src/order_discount/engine.py b/src/order_discount/engine.py
--- a/src/order_discount/engine.py
+++ b/src/order_discount/engine.py
@@ -28,6 +28,8 @@
         优惠金额（元），保留两位小数。
     """
-    amount = order.total
+    if any(item.fragile for item in order.items):
+        return 0.0
+    amount = order.subtotal
     discount = 0.0
     for threshold, reduction in DISCOUNT_TIERS:
         if amount >= threshold:
```

```

从中解析出的 unified diff：

```diff
diff --git a/src/order_discount/engine.py b/src/order_discount/engine.py
--- a/src/order_discount/engine.py
+++ b/src/order_discount/engine.py
@@ -28,6 +28,8 @@
         优惠金额（元），保留两位小数。
     """
-    amount = order.total
+    if any(item.fragile for item in order.items):
+        return 0.0
+    amount = order.subtotal
     discount = 0.0
     for threshold, reduction in DISCOUNT_TIERS:
         if amount >= threshold:

```

## 3. 补丁与提交代码差异的对应关系

补丁应用后修改的文件即提交代码差异涉及的文件：

- `src/order_discount/engine.py`

