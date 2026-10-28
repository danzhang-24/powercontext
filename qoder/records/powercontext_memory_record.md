# PowerContext 记忆记录

## 一、写入（POST /v1/memory/remember）

### 写入 1：`history`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`
- 写入原因：记住检索历史：图神经网络 消息传递 邻居聚合
- 条目 ID：`mem_ent_b8aa475596cc44b5bb05620be39da391`（修订号 0）
- 记忆正文：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,课程笔记-图神经网络基础-第-6-9-周#004,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001
at: 2026-10-28T17:07:03+00:00
```

### 写入 2：`profile`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`
- 写入原因：记住研究方向：图神经网络 消息传递
- 条目 ID：`mem_ent_0f06232287bd48c2933b9e22e12e99ad`（修订号 0）
- 记忆正文：

```text
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:07:03+00:00
```

### 写入 3：`history`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`
- 写入原因：记住检索历史：图神经网络 消息传递 邻居聚合
- 条目 ID：`mem_ent_9888f599472448dbb14f902533d42a64`（修订号 0）
- 记忆正文：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001,课程笔记-图神经网络基础-第-6-9-周#004
at: 2026-10-28T17:07:03+00:00
```

### 写入 4：`history`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`
- 写入原因：记住检索历史：图神经网络 消息传递 邻居聚合
- 记忆正文：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001,课程笔记-图神经网络基础-第-6-9-周#004
at: 2026-10-28T17:07:03+00:00
```

### 写入 5：`progress`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`
- 写入原因：记住阅读进度：图神经网络综述：从消息传递到可学习聚合
- 条目 ID：`mem_ent_7656149a65a54cdf937ee79f327543a8`（修订号 0）
- 记忆正文：

```text
paperpocket-memory v1
type: progress
doc_key: 图神经网络综述-从消息传递到可学习聚合
title: 图神经网络综述：从消息传递到可学习聚合
status: read
at: 2026-10-28T17:07:03+00:00
```

## 二、读回（POST /v1/memory/search）

### 读回 1：检索词 `paperpocket`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`，命中 0 条

### 读回 2：检索词 `paperpocket`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`，命中 2 条
- 命中条目（分数 0.01639344262295082）：

```text
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.016129032258064516）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,课程笔记-图神经网络基础-第-6-9-周#004,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001
at: 2026-10-28T17:07:03+00:00
```

### 读回 3：检索词 `paperpocket`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`，命中 2 条
- 命中条目（分数 0.01639344262295082）：

```text
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.016129032258064516）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,课程笔记-图神经网络基础-第-6-9-周#004,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001
at: 2026-10-28T17:07:03+00:00
```

### 读回 4：检索词 `paperpocket`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`，命中 3 条
- 命中条目（分数 0.01639344262295082）：

```text
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.016129032258064516）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001,课程笔记-图神经网络基础-第-6-9-周#004
at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.015873015873015872）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,课程笔记-图神经网络基础-第-6-9-周#004,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001
at: 2026-10-28T17:07:03+00:00
```

### 读回 5：检索词 `paperpocket`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`，命中 4 条
- 命中条目（分数 0.01639344262295082）：

```text
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.016129032258064516）：

```text
paperpocket-memory v1
type: progress
doc_key: 图神经网络综述-从消息传递到可学习聚合
title: 图神经网络综述：从消息传递到可学习聚合
status: read
at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.015873015873015872）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001,课程笔记-图神经网络基础-第-6-9-周#004
at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.015625）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,课程笔记-图神经网络基础-第-6-9-周#004,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001
at: 2026-10-28T17:07:03+00:00
```

### 读回 6：检索词 `paperpocket`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`，命中 4 条
- 命中条目（分数 0.01639344262295082）：

```text
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.016129032258064516）：

```text
paperpocket-memory v1
type: progress
doc_key: 图神经网络综述-从消息传递到可学习聚合
title: 图神经网络综述：从消息传递到可学习聚合
status: read
at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.015873015873015872）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001,课程笔记-图神经网络基础-第-6-9-周#004
at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.015625）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,课程笔记-图神经网络基础-第-6-9-周#004,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001
at: 2026-10-28T17:07:03+00:00
```

### 读回 7：检索词 `paperpocket`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`，命中 5 条
- 命中条目（分数 0.01639344262295082）：

```text
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.016129032258064516）：

```text
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:07:05+00:00
```
- 命中条目（分数 0.015873015873015872）：

```text
paperpocket-memory v1
type: progress
doc_key: 图神经网络综述-从消息传递到可学习聚合
title: 图神经网络综述：从消息传递到可学习聚合
status: read
at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.015625）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001,课程笔记-图神经网络基础-第-6-9-周#004
at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.015384615384615385）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,课程笔记-图神经网络基础-第-6-9-周#004,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001
at: 2026-10-28T17:07:03+00:00
```

### 读回 8：检索词 `paperpocket`

- 作用域：`scp_3rzeg7wma1qc4m655tesj6c46a`，命中 6 条
- 命中条目（分数 0.01639344262295082）：

```text
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.016129032258064516）：

```text
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:07:05+00:00
```
- 命中条目（分数 0.015873015873015872）：

```text
paperpocket-memory v1
type: profile
direction: 图神经网络 消息传递
tags: gnn,message-passing
updated_at: 2026-10-28T17:07:06+00:00
```
- 命中条目（分数 0.015625）：

```text
paperpocket-memory v1
type: progress
doc_key: 图神经网络综述-从消息传递到可学习聚合
title: 图神经网络综述：从消息传递到可学习聚合
status: read
at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.015384615384615385）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001,课程笔记-图神经网络基础-第-6-9-周#004
at: 2026-10-28T17:07:03+00:00
```
- 命中条目（分数 0.015151515151515152）：

```text
paperpocket-memory v1
type: history
query: 图神经网络 消息传递 邻居聚合
top_keys: 图神经网络综述-从消息传递到可学习聚合#006,课程笔记-图神经网络基础-第-6-9-周#004,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001
at: 2026-10-28T17:07:03+00:00
```
