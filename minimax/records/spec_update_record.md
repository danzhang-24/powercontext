# 规格更新后的重新导入验证

本文件验证验收项：更新样例中的规格并重新导入后，模块应使用更新后的内容，
而不是始终返回固定答案。

## 操作

1. 备份 `demo_project/specs/order_discount.spec.md`；
2. 在 SPEC-DISC-003 的规则末尾追加约束：

   > 易碎品订单即使满 600 元也不享受任何满减减免

3. 用独立工作目录执行 `import-materials` 重新导入；
4. 执行 `context` 重新检索；
5. 检查检索输出中出现的是更新后的规则文本；
6. 还原规格文件。

## 结果

- 检索输出中出现新增约束：**是**
- 重新检索到的 SPEC-DISC-003 规则原文：

  - 规则：订单中只要包含一行易碎品商品（item.fragile 为真），整单不享受满减优惠，优惠金额为 0 元；运费不改变这一结论；易碎品订单即使满 600 元也不享受任何满减减免。

## 重置方法

规格文件在脚本结束时已自动还原；如需手工还原，用 `snapshots/before/order_discount.spec.md` 覆盖即可：

```bash
cp demo_project/snapshots/before/order_discount.spec.md demo_project/specs/order_discount.spec.md
```

