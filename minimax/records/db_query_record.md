# 数据库（seekdb）查询记录

- 任务编号：T-1
- 记录时间：2026-10-28T04:14:42+00:00
- 存储：seekdb 嵌入式实例（pylibseekdb），库名 sddctx
- 表：spec_entry / code_symbol / test_case / verification_result / query_log

## 1. 用于构造任务上下文的查询

### 查询 1：规格检索（seekdb 打分查询）（命中 3 行）

```sql
SELECT spec_id, title, priority, status, rule, acceptance, source_path, source_symbol, source_line_start, source_line_end, doc_path, doc_line_start, doc_line_end, CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%让满减%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%满减门%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%减门槛%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%门槛只%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%槛只按%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%只按商%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%按商品%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%商品小%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%品小计%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%小计计%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%计计算%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%并排除%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%排除含%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%除含易%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%含易碎%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%易碎品%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%碎品的%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', title, rule, acceptance) LIKE '%品的订%' THEN 6 ELSE 0 END AS score FROM spec_entry WHERE CONCAT_WS(' ', title, rule, acceptance) LIKE '%让满减%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%满减门%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%减门槛%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%门槛只%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%槛只按%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%只按商%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%按商品%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%商品小%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%品小计%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%小计计%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%计计算%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%并排除%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%排除含%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%除含易%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%含易碎%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%易碎品%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%碎品的%' OR CONCAT_WS(' ', title, rule, acceptance) LIKE '%品的订%' ORDER BY score DESC, spec_id LIMIT 25
```

### 查询 2：规格检索（seekdb 全文索引 MATCH）（命中 4 行）

```sql
SELECT spec_id, title, priority, status, rule, acceptance, source_path, source_symbol, source_line_start, source_line_end, doc_path, doc_line_start, doc_line_end FROM spec_entry WHERE MATCH(title, rule) AGAINST ('让满减门槛只按商品小计计算，并排除含易碎品的订单' IN NATURAL LANGUAGE MODE) LIMIT 25
```

### 查询 3：代码回链（规格来源字段）（命中 2 行）

```sql
SELECT path, symbol, kind, line_start, line_end, signature, doc, body FROM code_symbol WHERE path IN ('src/order_discount/engine.py') ORDER BY path, line_start
```

### 查询 4：代码检索（seekdb 打分查询）（命中 4 行）

```sql
SELECT path, symbol, kind, line_start, line_end, signature, doc, body, CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%让满减%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%满减门%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%减门槛%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%门槛只%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%槛只按%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%只按商%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%按商品%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%商品小%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%品小计%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%小计计%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%计计算%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%并排除%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%排除含%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%除含易%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%含易碎%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%易碎品%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%碎品的%' THEN 4 ELSE 0 END + CASE WHEN CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%品的订%' THEN 4 ELSE 0 END AS score FROM code_symbol WHERE CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%让满减%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%满减门%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%减门槛%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%门槛只%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%槛只按%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%只按商%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%按商品%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%商品小%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%品小计%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%小计计%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%计计算%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%并排除%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%排除含%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%除含易%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%含易碎%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%易碎品%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%碎品的%' OR CONCAT_WS(' ', symbol, signature, doc, body) LIKE '%品的订%' ORDER BY score DESC, path, line_start LIMIT 20
```

### 查询 5：测试回链（规格验收字段）（命中 9 行）

```sql
SELECT path, name, marker, doc, line_start, line_end FROM test_case WHERE name IN ('test_threshold_ignores_shipping', 'test_threshold_boundary_excludes_subtotal_below_100', 'test_fragile_order_is_excluded_from_tier_discount', 'test_fragile_order_with_shipping_stays_excluded', 'test_tier_300_subtotal', 'test_tier_600_subtotal', 'test_below_threshold_has_no_discount', 'test_member_discount_applies_on_tier', 'test_empty_order_has_no_discount') ORDER BY path, line_start
```

### 查询 6：测试检索（seekdb 打分查询）（命中 4 行）

```sql
SELECT path, name, marker, doc, line_start, line_end, CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%让满减%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%满减门%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%减门槛%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%门槛只%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%槛只按%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%只按商%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%按商品%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%商品小%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%品小计%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%小计计%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%计计算%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%并排除%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%排除含%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%除含易%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%含易碎%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%易碎品%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%碎品的%' THEN 6 ELSE 0 END + CASE WHEN CONCAT_WS(' ', name, doc) LIKE '%品的订%' THEN 6 ELSE 0 END AS score FROM test_case WHERE CONCAT_WS(' ', name, doc) LIKE '%让满减%' OR CONCAT_WS(' ', name, doc) LIKE '%满减门%' OR CONCAT_WS(' ', name, doc) LIKE '%减门槛%' OR CONCAT_WS(' ', name, doc) LIKE '%门槛只%' OR CONCAT_WS(' ', name, doc) LIKE '%槛只按%' OR CONCAT_WS(' ', name, doc) LIKE '%只按商%' OR CONCAT_WS(' ', name, doc) LIKE '%按商品%' OR CONCAT_WS(' ', name, doc) LIKE '%商品小%' OR CONCAT_WS(' ', name, doc) LIKE '%品小计%' OR CONCAT_WS(' ', name, doc) LIKE '%小计计%' OR CONCAT_WS(' ', name, doc) LIKE '%计计算%' OR CONCAT_WS(' ', name, doc) LIKE '%并排除%' OR CONCAT_WS(' ', name, doc) LIKE '%排除含%' OR CONCAT_WS(' ', name, doc) LIKE '%除含易%' OR CONCAT_WS(' ', name, doc) LIKE '%含易碎%' OR CONCAT_WS(' ', name, doc) LIKE '%易碎品%' OR CONCAT_WS(' ', name, doc) LIKE '%碎品的%' OR CONCAT_WS(' ', name, doc) LIKE '%品的订%' ORDER BY score DESC, path, line_start LIMIT 20
```

## 2. 查询结果如何进入上下文

- 规格 `SPEC-DISC-002`（打分 63.0，命中检索词 满减门, 减门槛, 门槛只, 槛只按, 只按商, 按商品, 商品小, 品小计, 小计计, 计计算）
- 规格 `SPEC-DISC-003`（打分 27.0，命中检索词 含易碎, 易碎品, 碎品的, 品的订）
- 规格 `SPEC-DISC-001`（打分 15.0，命中检索词 满减门, 减门槛）
- 规格 `SPEC-DISC-004`（打分 3.0，命中检索词 任务点名）
- 代码 `compute_discount` @ src/order_discount/engine.py:21-38（规格 SPEC-DISC-002 声明的实现位置）
- 代码 `MEMBER_DISCOUNT_RATE` @ src/order_discount/engine.py:18-18（规格 SPEC-DISC-004 声明的实现位置）
- 代码 `Order` @ src/order_discount/models.py:30-53（关键词命中：满减门, 减门槛）
- 代码 `Order.subtotal` @ src/order_discount/models.py:46-48（关键词命中：商品小, 品小计）
- 代码 `Order.total` @ src/order_discount/models.py:51-53（关键词命中：商品小, 品小计）
- 测试 `test_threshold_ignores_shipping` @ tests/test_order_discount.py:33-36（规格 SPEC-DISC-002 声明的验收测试）
- 测试 `test_threshold_boundary_excludes_subtotal_below_100` @ tests/test_order_discount.py:40-43（规格 SPEC-DISC-002 声明的验收测试）
- 测试 `test_fragile_order_is_excluded_from_tier_discount` @ tests/test_order_discount.py:47-50（规格 SPEC-DISC-003 声明的验收测试）
- 测试 `test_fragile_order_with_shipping_stays_excluded` @ tests/test_order_discount.py:54-57（规格 SPEC-DISC-003 声明的验收测试）
- 测试 `test_tier_300_subtotal` @ tests/test_order_discount.py:66-68（规格 SPEC-DISC-001 声明的验收测试）
- 测试 `test_tier_600_subtotal` @ tests/test_order_discount.py:72-74（规格 SPEC-DISC-001 声明的验收测试）
- 测试 `test_below_threshold_has_no_discount` @ tests/test_order_discount.py:78-80（规格 SPEC-DISC-001 声明的验收测试）
- 测试 `test_member_discount_applies_on_tier` @ tests/test_order_discount.py:84-86（规格 SPEC-DISC-004 声明的验收测试）
- 测试 `test_empty_order_has_no_discount` @ tests/test_order_discount.py:96-99（规格 SPEC-DISC-004 声明的验收测试）

## 3. 验证结果（同一 seekdb 实例落库）

- [before/target] 命令 `/home/zhangdan/pc2026/mmxenv/bin/python -m pytest -p no:cacheprovider -q -m target`，退出码 1，通过 0、失败 4、错误 0，版本 d647275c308e+content:00421e725ebb
- [before/regression] 命令 `/home/zhangdan/pc2026/mmxenv/bin/python -m pytest -p no:cacheprovider -q -m regression`，退出码 0，通过 6、失败 0、错误 0，版本 d647275c308e+content:00421e725ebb
- [after/target] 命令 `/home/zhangdan/pc2026/mmxenv/bin/python -m pytest -p no:cacheprovider -q -m target`，退出码 0，通过 4、失败 0、错误 0，版本 d647275c308e+content:e168b3b33781
- [after/regression] 命令 `/home/zhangdan/pc2026/mmxenv/bin/python -m pytest -p no:cacheprovider -q -m regression`，退出码 0，通过 6、失败 0、错误 0，版本 d647275c308e+content:e168b3b33781

## 4. query_log 表原始记录

| id | purpose | row_count | created_at |
| --- | --- | --- | --- |
| 1 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T01:35:06+00:00 |
| 2 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T01:35:06+00:00 |
| 3 | 代码回链（规格来源字段） | 2 | 2026-10-28T01:35:06+00:00 |
| 4 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T01:35:06+00:00 |
| 5 | 测试回链（规格验收字段） | 9 | 2026-10-28T01:35:06+00:00 |
| 6 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T01:35:06+00:00 |
| 1000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T01:58:24+00:00 |
| 1000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T01:58:24+00:00 |
| 1000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T01:58:24+00:00 |
| 1000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T01:58:24+00:00 |
| 1000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T01:58:24+00:00 |
| 1000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T01:58:24+00:00 |
| 2000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T01:59:41+00:00 |
| 2000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T01:59:41+00:00 |
| 2000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T01:59:41+00:00 |
| 2000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T01:59:41+00:00 |
| 2000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T01:59:41+00:00 |
| 2000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T01:59:41+00:00 |
| 3000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T02:07:54+00:00 |
| 3000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T02:07:54+00:00 |
| 3000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T02:07:54+00:00 |
| 3000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T02:07:54+00:00 |
| 3000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T02:07:54+00:00 |
| 3000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T02:07:54+00:00 |
| 4000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T02:07:56+00:00 |
| 4000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T02:07:56+00:00 |
| 4000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T02:07:56+00:00 |
| 4000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T02:07:56+00:00 |
| 4000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T02:07:56+00:00 |
| 4000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T02:07:56+00:00 |
| 5000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T02:11:30+00:00 |
| 5000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T02:11:30+00:00 |
| 5000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T02:11:30+00:00 |
| 5000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T02:11:30+00:00 |
| 5000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T02:11:30+00:00 |
| 5000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T02:11:30+00:00 |
| 6000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T02:11:32+00:00 |
| 6000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T02:11:32+00:00 |
| 6000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T02:11:32+00:00 |
| 6000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T02:11:32+00:00 |
| 6000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T02:11:32+00:00 |
| 6000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T02:11:32+00:00 |
| 7000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T02:11:55+00:00 |
| 7000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T02:11:55+00:00 |
| 7000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T02:11:55+00:00 |
| 7000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T02:11:55+00:00 |
| 7000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T02:11:55+00:00 |
| 7000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T02:11:55+00:00 |
| 8000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T02:13:24+00:00 |
| 8000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T02:13:24+00:00 |
| 8000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T02:13:24+00:00 |
| 8000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T02:13:24+00:00 |
| 8000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T02:13:24+00:00 |
| 8000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T02:13:24+00:00 |
| 9000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T02:13:26+00:00 |
| 9000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T02:13:26+00:00 |
| 9000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T02:13:26+00:00 |
| 9000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T02:13:26+00:00 |
| 9000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T02:13:26+00:00 |
| 9000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T02:13:26+00:00 |
| 10000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T02:14:02+00:00 |
| 10000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T02:14:02+00:00 |
| 10000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T02:14:02+00:00 |
| 10000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T02:14:02+00:00 |
| 10000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T02:14:02+00:00 |
| 10000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T02:14:02+00:00 |
| 11000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T02:14:03+00:00 |
| 11000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T02:14:03+00:00 |
| 11000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T02:14:03+00:00 |
| 11000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T02:14:03+00:00 |
| 11000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T02:14:03+00:00 |
| 11000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T02:14:03+00:00 |
| 12000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T04:14:37+00:00 |
| 12000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T04:14:37+00:00 |
| 12000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T04:14:37+00:00 |
| 12000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T04:14:37+00:00 |
| 12000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T04:14:37+00:00 |
| 12000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T04:14:37+00:00 |
| 13000001 | 规格检索（seekdb 打分查询） | 3 | 2026-10-28T04:14:39+00:00 |
| 13000002 | 规格检索（seekdb 全文索引 MATCH） | 4 | 2026-10-28T04:14:39+00:00 |
| 13000003 | 代码回链（规格来源字段） | 2 | 2026-10-28T04:14:39+00:00 |
| 13000004 | 代码检索（seekdb 打分查询） | 4 | 2026-10-28T04:14:39+00:00 |
| 13000005 | 测试回链（规格验收字段） | 9 | 2026-10-28T04:14:39+00:00 |
| 13000006 | 测试检索（seekdb 打分查询） | 4 | 2026-10-28T04:14:39+00:00 |

