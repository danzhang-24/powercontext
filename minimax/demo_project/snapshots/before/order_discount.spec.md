"""订单优惠计算规格（Spec-Driven Development）。

本文件是演示任务的唯一规格来源。上下文模块把这里的条目导入 seekdb，
再根据开发任务检索出适用条目交给 MiniMax 修改代码。

每条规格包含：

- 规格编号：稳定标识，检索与验收都引用它。
- 状态：``已实现`` / ``待实现``。``待实现`` 表示当前代码不满足该规格。
- 规则：自然语言描述的可验收行为。
- 来源：实现该规则的代码位置。
- 验收：覆盖该规格的测试用例名。
"""

# 订单优惠计算规格

## SPEC-DISC-001 满减阶梯

- 优先级: P0
- 状态: 已实现
- 规则: 商品金额满足满减门槛时按阶梯减免：满 600 元减 80 元，满 300 元减 30 元，满 100 元减 10 元；门槛取"大于等于"，只命中最高一档。
- 来源: src/order_discount/engine.py::DISCOUNT_TIERS
- 验收: test_tier_300_subtotal, test_tier_600_subtotal, test_below_threshold_has_no_discount

## SPEC-DISC-002 满减门槛只按商品小计计算

- 优先级: P0
- 状态: 待实现
- 规则: 满减门槛只按商品小计（不含运费）计算。运费金额不计入门槛：商品小计 95 元、运费 20 元的订单不满足 100 元门槛；商品小计 99.99 元、运费 0.01 元的订单同样不满足门槛。
- 来源: src/order_discount/engine.py::compute_discount
- 验收: test_threshold_ignores_shipping, test_threshold_boundary_excludes_subtotal_below_100

## SPEC-DISC-003 含易碎品的订单不参与满减

- 优先级: P0
- 状态: 待实现
- 规则: 订单中只要包含一行易碎品商品（item.fragile 为真），整单不享受满减优惠，优惠金额为 0 元；运费不改变这一结论。
- 来源: src/order_discount/engine.py::compute_discount
- 验收: test_fragile_order_is_excluded_from_tier_discount, test_fragile_order_with_shipping_stays_excluded

## SPEC-DISC-004 会员在满减金额上再打 95 折

- 优先级: P1
- 状态: 已实现
- 规则: 会员订单在满减金额基础上再享受 5% 折扣，结果保留两位小数；无满减时会员折扣不产生优惠。
- 来源: src/order_discount/engine.py::MEMBER_DISCOUNT_RATE
- 验收: test_member_discount_applies_on_tier, test_empty_order_has_no_discount
