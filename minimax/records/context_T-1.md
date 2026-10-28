# 开发上下文：T-1

- 任务描述：让满减门槛只按商品小计计算，并排除含易碎品的订单
- 工程目录：/home/zhangdan/pc2026/powercontext/minimax/demo_project
- 检索关键词：让满减, 满减门, 减门槛, 门槛只, 槛只按, 只按商, 按商品, 商品小, 品小计, 小计计, 计计算, 并排除, 排除含, 除含易, 含易碎, 易碎品, 碎品的, 品的订

## 1. 适用的规格条目
- [SPEC-DISC-002] 满减门槛只按商品小计计算（优先级 P0，状态 待实现）
  - 规格位置：specs/order_discount.spec.md:25-32
  - 实现位置：src/order_discount/engine.py:21-38
  - 规则：满减门槛只按商品小计（不含运费）计算。运费金额不计入门槛：商品小计 95 元、运费 20 元的订单不满足 100 元门槛；商品小计 99.99 元、运费 0.01 元的订单同样不满足门槛。
  - 验收测试：test_threshold_ignores_shipping, test_threshold_boundary_excludes_subtotal_below_100
- [SPEC-DISC-003] 含易碎品的订单不参与满减（优先级 P0，状态 待实现）
  - 规格位置：specs/order_discount.spec.md:33-40
  - 实现位置：src/order_discount/engine.py:21-38
  - 规则：订单中只要包含一行易碎品商品（item.fragile 为真），整单不享受满减优惠，优惠金额为 0 元；运费不改变这一结论。
  - 验收测试：test_fragile_order_is_excluded_from_tier_discount, test_fragile_order_with_shipping_stays_excluded
- [SPEC-DISC-001] 满减阶梯（优先级 P0，状态 已实现）
  - 规格位置：specs/order_discount.spec.md:17-24
  - 实现位置：src/order_discount/engine.py:18-18
  - 规则：商品金额满足满减门槛时按阶梯减免：满 600 元减 80 元，满 300 元减 30 元，满 100 元减 10 元；门槛取"大于等于"，只命中最高一档。
  - 验收测试：test_tier_300_subtotal, test_tier_600_subtotal, test_below_threshold_has_no_discount
- [SPEC-DISC-004] 会员在满减金额上再打 95 折（优先级 P1，状态 已实现）
  - 规格位置：specs/order_discount.spec.md:41-47
  - 实现位置：src/order_discount/engine.py:18-18
  - 规则：会员订单在满减金额基础上再享受 5% 折扣，结果保留两位小数；无满减时会员折扣不产生优惠。
  - 验收测试：test_member_discount_applies_on_tier, test_empty_order_has_no_discount

## 2. 需要修改的代码文件或符号
- compute_discount（function）@ src/order_discount/engine.py:21-38 — 规格 SPEC-DISC-002 声明的实现位置
  - 签名：def compute_discount(order: Order) -> float:
- MEMBER_DISCOUNT_RATE（constant）@ src/order_discount/engine.py:18-18 — 规格 SPEC-DISC-004 声明的实现位置
  - 签名：MEMBER_DISCOUNT_RATE = 0.05
- Order（class）@ src/order_discount/models.py:30-53 — 关键词命中：满减门, 减门槛
  - 签名：class Order:
- Order.subtotal（method）@ src/order_discount/models.py:46-48 — 关键词命中：商品小, 品小计
  - 签名：def subtotal(self) -> float:
- Order.total（method）@ src/order_discount/models.py:51-53 — 关键词命中：商品小, 品小计
  - 签名：def total(self) -> float:

## 3. 用于验证功能及兼容性的测试
- test_threshold_ignores_shipping [target] @ tests/test_order_discount.py:33-36 — 规格 SPEC-DISC-002 声明的验收测试
  - 说明：SPEC-DISC-002：运费不计入满减门槛。
- test_threshold_boundary_excludes_subtotal_below_100 [target] @ tests/test_order_discount.py:40-43 — 规格 SPEC-DISC-002 声明的验收测试
  - 说明：SPEC-DISC-002：门槛取商品小计，小计 99.99 元不满足 100 元门槛。
- test_fragile_order_is_excluded_from_tier_discount [target] @ tests/test_order_discount.py:47-50 — 规格 SPEC-DISC-003 声明的验收测试
  - 说明：SPEC-DISC-003：含易碎品的订单不享受满减。
- test_fragile_order_with_shipping_stays_excluded [target] @ tests/test_order_discount.py:54-57 — 规格 SPEC-DISC-003 声明的验收测试
  - 说明：SPEC-DISC-003：运费不改变易碎品订单不参与满减的结论。
- test_tier_300_subtotal [regression] @ tests/test_order_discount.py:66-68 — 规格 SPEC-DISC-001 声明的验收测试
  - 说明：SPEC-DISC-001：满 300 元减 30 元。
- test_tier_600_subtotal [regression] @ tests/test_order_discount.py:72-74 — 规格 SPEC-DISC-001 声明的验收测试
  - 说明：SPEC-DISC-001：满 600 元减 80 元，只命中最高一档。
- test_below_threshold_has_no_discount [regression] @ tests/test_order_discount.py:78-80 — 规格 SPEC-DISC-001 声明的验收测试
  - 说明：SPEC-DISC-001：小计 99 元不满足任何门槛。
- test_member_discount_applies_on_tier [regression] @ tests/test_order_discount.py:84-86 — 规格 SPEC-DISC-004 声明的验收测试
  - 说明：SPEC-DISC-004：会员在满减 30 元基础上再打 95 折。
- test_empty_order_has_no_discount [regression] @ tests/test_order_discount.py:96-99 — 规格 SPEC-DISC-004 声明的验收测试
  - 说明：SPEC-DISC-004：无商品时没有优惠。

## 4. 已有任务状态与验证结果
- 状态来源：powercontext（scope: sddctx:order-discount）
- 已完成：（空）
- 待办：（空）
- 已有验证结果：（空）

## 5. 本次上下文使用的数据库查询
1. [规格检索（seekdb 打分查询）] 命中 3 行
   ```sql
SELECT spec_id, title, priority, status, rule, acceptance, source_path, source_symbol, source_line_start, source_line_end, doc_path, doc_line_start, doc_line_end, CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%让满减%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%满减门%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%减门槛%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%门槛只%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%槛只按%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%只按商%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%按商品%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%商品小%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%品小计%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%小计计%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%计计算%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%并排除%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%排除含%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%除含易%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%含易碎%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%易碎品%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%碎品的%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%品的订%' THEN 6 ELSE 0 END AS score FROM spec_entry WHERE CONCAT_WS(' ', title, rule, acceptance) LIKE '%让满减%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%满减门%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%减门槛%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%门槛只%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%槛只按%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%只按商%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%按商品%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%商品小%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%品小计%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%小计计%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%计计算%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%并排除%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%排除含%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%除含易%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%含易碎%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%易碎品%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%碎品的%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%品的订%' ORDER BY score DESC, spec_id LIMIT 25
   ```
2. [规格检索（seekdb 全文索引 MATCH）] 命中 4 行
   ```sql
SELECT spec_id, title, priority, status, rule, acceptance, source_path, source_symbol, source_line_start, source_line_end, doc_path, doc_line_start, doc_line_end FROM spec_entry WHERE MATCH(title, rule) AGAINST ('让满减门槛只按商品小计计算，并排除含易碎品的订单' IN NATURAL LANGUAGE MODE) LIMIT 25
   ```
3. [代码回链（规格来源字段）] 命中 2 行
   ```sql
SELECT path, symbol, kind, line_start, line_end, signature, doc, body FROM code_symbol WHERE path IN ('src/order_discount/engine.py') ORDER BY path, line_start
   ```
4. [代码检索（seekdb 打分查询）] 命中 4 行
   ```sql
SELECT path, symbol, kind, line_start, line_end, signature, doc, body, CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%让满减%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%满减门%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%减门槛%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%门槛只%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%槛只按%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%只按商%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%按商品%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%商品小%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%品小计%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%小计计%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%计计算%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%并排除%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%排除含%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%除含易%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%含易碎%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%易碎品%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%碎品的%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%品的订%' THEN 4 ELSE 0 END AS score FROM code_symbol WHERE CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%让满减%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%满减门%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%减门槛%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%门槛只%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%槛只按%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%只按商%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%按商品%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%商品小%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%品小计%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%小计计%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%计计算%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%并排除%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%排除含%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%除含易%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%含易碎%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%易碎品%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%碎品的%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%品的订%' ORDER BY score DESC, path, line_start LIMIT 20
   ```
5. [测试回链（规格验收字段）] 命中 9 行
   ```sql
SELECT path, name, marker, doc, line_start, line_end FROM test_case WHERE name IN ('test_threshold_ignores_shipping', 'test_threshold_boundary_excludes_subtotal_below_100', 'test_fragile_order_is_excluded_from_tier_discount', 'test_fragile_order_with_shipping_stays_excluded', 'test_tier_300_subtotal', 'test_tier_600_subtotal', 'test_below_threshold_has_no_discount', 'test_member_discount_applies_on_tier', 'test_empty_order_has_no_discount') ORDER BY path, line_start
   ```
6. [测试检索（seekdb 打分查询）] 命中 4 行
   ```sql
SELECT path, name, marker, doc, line_start, line_end, CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%让满减%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%满减门%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%减门槛%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%门槛只%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%槛只按%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%只按商%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%按商品%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%商品小%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%品小计%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%小计计%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%计计算%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%并排除%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%排除含%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%除含易%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%含易碎%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%易碎品%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%碎品的%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%品的订%' THEN 6 ELSE 0 END AS score FROM test_case WHERE CONCAT_WS(' ', name, doc) LIKE '%让满减%' OR CONCAT_WS(' ', name, doc) LIKE '%满减门%' OR CONCAT_WS(' ', name, doc) LIKE '%减门槛%' OR CONCAT_WS(' ', name, doc) LIKE '%门槛只%' OR CONCAT_WS(' ', name, doc) LIKE '%槛只按%' OR CONCAT_WS(' ', name, doc) LIKE '%只按商%' OR CONCAT_WS(' ', name, doc) LIKE '%按商品%' OR CONCAT_WS(' ', name, doc) LIKE '%商品小%' OR CONCAT_WS(' ', name, doc) LIKE '%品小计%' OR CONCAT_WS(' ', name, doc) LIKE '%小计计%' OR CONCAT_WS(' ', name, doc) LIKE '%计计算%' OR CONCAT_WS(' ', name, doc) LIKE '%并排除%' OR CONCAT_WS(' ', name, doc) LIKE '%排除含%' OR CONCAT_WS(' ', name, doc) LIKE '%除含易%' OR CONCAT_WS(' ', name, doc) LIKE '%含易碎%' OR CONCAT_WS(' ', name, doc) LIKE '%易碎品%' OR CONCAT_WS(' ', name, doc) LIKE '%碎品的%' OR CONCAT_WS(' ', name, doc) LIKE '%品的订%' ORDER BY score DESC, path, line_start LIMIT 20
   ```