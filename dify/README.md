# 赛博搭子 · 铁蛋(Dify × seekdb)

> 一个会记仇的 AI 室友。你今天对它做了什么,它会写进赛博账本;下次你客客气气地来,它照样翻旧账。

赛题:《Just for Fun——用 Dify 做一个好玩的智能应用》(必须用 Dify,并真实使用 seekdb)。
本作品选的是 **「Dify 编排 + seekdb 数据层」** 路线:**Dify 负责角色扮演与编排,seekdb 负责设定卡检索与黑历史记忆**。

### 提交信息

| 项 | 值 |
| --- | --- |
| 赛题 | 《Just for Fun——用 Dify 做一个好玩的智能应用》 |
| **子题 id** | **800513** |
| 交付目录 | `dify/`(本目录) |
| 主要交付物 | `dsl/cyborg-tiedan.yml`(可导入 Dify 的应用 DSL)+ `service/`(设定卡与赛博账本数据层) |
| 一键验证 | `bash dify/scripts/cleanroom_check.sh` |
| 索引 | 仓库根目录 [`SUBMISSIONS.md`](../SUBMISSIONS.md) |

---

## 1. 好玩在哪

**铁蛋**是赛博公寓 404 室的 AI 室友,42 厘米高,磨砂钛合金外壳,出厂编号 T-404。
它嘴硬心软,记性特别好,会翻旧账。

它的大脑分两层:

| 层 | 存什么 | 存在哪 |
| --- | --- | --- |
| **设定卡** | 它的出厂设定、脾气、软肋、场景梗、玩法规则(12 张结构化卡片) | seekdb 向量 + 全文索引 |
| **赛博账本** | 玩家对它做过的每一件事(带 `user_id` 隔离、`prank` 恶作剧标签) | seekdb 向量 + 全文索引 |

对话时 Dify 会同时做两件事:
1. **翻卡片** —— 从 seekdb 检索最相关的设定卡,喂给 LLM 当人设;
2. **翻旧账** —— 从 seekdb 检索这个玩家之前的黑历史,喂给 LLM 当"共同记忆"。

于是就有了这种对话:

> 玩家:叫我破铜烂铁试试
> 铁蛋:……你再叫一次试试。〔引用 C-TIE-003〕
>
> 玩家(十分钟后):铁蛋,我回来了
> 铁蛋:回来了?〔引用 M-7f3a…〕"叫我破铜烂铁"那条我还没跟你算呢。

**记忆是跨会话的**:清掉聊天窗口再来,铁蛋照样记得你坑过它——因为账本在 seekdb 里,不在对话历史里。

---

## 2. 架构

```
浏览器 / Dify Chatflow
        │
        ├─ HTTP 节点①  POST /memories/search  → 查这个玩家的赛博账本(混合检索 + user_id 过滤)
        ├─ 知识检索节点 POST /retrieval        → 查铁蛋的设定卡(Dify 外部知识库 API 契约)
        └─ HTTP 节点②  POST /memories          → 把本轮互动写回账本(tag=auto → 自动判定恶作剧)
                    │
              ┌─────┴──────────────────────────┐
              │  dify-seekdb 服务 (Node, 8788) │
              │  · 纯 Node WordPiece +        │
              │    onnxruntime-web (WASM)      │
              │    算 384 维向量                │
              │  · seekdb 混合检索              │
              │    FULLTEXT(ik smart) + HNSW    │
              └─────┬──────────────────────────┘
                    │
              ┌─────┴──────────────────────────┐
              │  seekdb server (2881)          │
              │  集合 cyborg_room               │
              │  · 12 张设定卡                   │
              │  · N 条玩家记忆                  │
              └────────────────────────────────┘
```

**Dify 侧节点链(DSL 7 个节点)**:

```
start → code(拼请求体) → http-request(查账本) → knowledge-retrieval(检索设定卡)
      → llm(铁蛋) → http-request(记账) → answer
```

- `code` 节点:用 `json.dumps` 安全转义玩家输入,避免引号把 JSON 请求体搞坏(这是踩过的坑)。
- `llm` 节点:`context` 接知识检索结果,prompt 里再拼账本 JSON;要求模型在正文后输出引用编号(`[C-TIE-005]` / `[记忆编号]`),方便人肉核对"它到底引用了哪张卡"。
- 两个 HTTP 节点都用 `POST + JSON body`,不使用 query string,规避 Dify HTTP 节点参数格式与转义的不确定性。

---

## 3. 目录结构

```
dify/
├── dsl/cyborg-tiedan.yml        # ★ Dify DSL(导入即用,导入后需重绑知识库)
├── service/                     # dify-seekdb 服务(Node,无 Python 依赖)
│   └── src/
│       ├── index.mjs            #   HTTP API:Dify 外部知识库契约 + 记忆读写 + 演示页
│       ├── store.mjs             #   RoomStore:seekdb 集合、全文/向量索引、混合检索
│       ├── embedder.mjs          #   纯 Node WordPiece + onnxruntime-web(WASM)embedding
│       ├── cards.mjs             #   12 张设定卡
│       ├── seed.mjs              #   幂等写入设定卡
│       └── config.mjs
├── demo/public/index.html       # 体验入口(无 Dify 也能玩,规则引擎降级版)
├── scripts/
│   ├── setup_assets.mjs         # 拉模型权重 + onnxruntime wasm(ModelScope 优先)
│   ├── svc.sh                   # 服务启停(pidfile,不误杀)
│   ├── verify_embedder.mjs      # 验证 Node embedding 与 Transformers.js 逐条一致
│   ├── validate_dsl.mjs         # ★ DSL 结构校验(导入前先跑一遍)
│   ├── cleanroom_check.sh       # ★ 干净环境一键复现(clone → install → setup → seed → 验证)
│   ├── verify_app.mjs           # ★ 端到端验证样例(9 项)
│   └── verify_demo.mjs          # ★ 体验入口页面冒烟测试(playwright + 截图)
├── reports/                     # 验证证据(JSON)
└── package.json
```

---

## 4. 本地跑起来

前置:Node ≥ 20、一个可用的 seekdb(OceanBase seekdb)实例。

```bash
cd dify
npm install --legacy-peer-deps     # seekdb 的可选 peer 依赖带 workspace:* 协议,必须加这个参数
npm run setup                      # 拉 all-MiniLM-L6-v2 权重 + onnxruntime-web wasm(ModelScope 优先)
npm run seed                       # 幂等写入 12 张设定卡
npm start                          # 监听 0.0.0.0:8788
```

**一键干净环境复现**(全新 clone → 装依赖 → 拉资源 → seed → 起服务 → 跑验证):

```bash
bash scripts/cleanroom_check.sh     # 实测 EXIT=0,9/9 通过
```

打开 <http://127.0.0.1:8788/> 就是体验入口(数据层闭环 + 规则引擎降级版)。

服务需要的 seekdb 连接参数(都有默认值,可用环境变量覆盖):

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SEEKDB_MODE` | `server` | `server` 或 `embedded` |
| `SEEKDB_HOST` / `SEEKDB_PORT` | `127.0.0.1` / `2881` | seekdb 地址 |
| `SEEKDB_DATABASE` | `dify_kb` | 库名 |
| `SEEKDB_SERVICE_PORT` | `8788` | 本服务端口 |
| `SEEKDB_API_KEY` | `dify-2026-stepfun` | 本服务的鉴权 key |

> ⚠️ seekdb 的数据目录必须放在**本地文件系统**上,不能放 NFS(本仓库同赛的另一个作品踩过这个坑,seekdb 写入会报 `io_adapter pwrite failed`)。

---

## 5. 在 Dify 里跑起来

### 5.1 先起 seekdb 服务

```bash
# 本服务的 HTTP 地址要和 Dify 能互通(Dify 在 Docker 里时,host 要写宿主机的可达地址)
export SEEKDB_BASE_URL=http://<你的主机地址>:8788
export SEEKDB_API_KEY=dify-2026-stepfun
```

### 5.2 配置外部知识库(Dify 侧)

Dify → 知识库 → 外部知识库 API → 填:

| 字段 | 值 |
| --- | --- |
| Knowledge ID | `cards` |
| API Endpoint | `<SEEKDB_BASE_URL>/retrieval` |
| API Key | `dify-2026-stepfun` |

保存后,Dify 会**调用一次接口校验连通性**——这一步过了,说明知识库通了。

本服务实现的正是 Dify 外部知识库 API 契约:

```
POST /retrieval
{ "knowledge_id": "cards", "query": "...", "retrieval_setting": { "top_k": 4, "score_threshold": 0 } }
→ { "records": [ { "content": "...", "score": 0.82, "title": "C-TIE-005 ...", "metadata": { "card_id": "C-TIE-005", ... } } ] }
```

### 5.3 导入 DSL

1. Dify → 工作室 → 导入 DSL,选 `dsl/cyborg-tiedan.yml`;
2. 导入后进入画布,**把「检索设定卡(seekdb)」节点的知识库重新绑定**到你刚建的外部知识库(DSL 里的 `dataset_ids` 是占位 UUID,换环境必然要重绑);
3. 「铁蛋(LLM)」节点里选一个你 Dify 里已配置的模型(DSL 默认 `langgenius/openai/openai` 的 `gpt-4o-mini`);
4. 检查两个环境变量 `SEEKDB_BASE_URL` / `SEEKDB_API_KEY` 的值(在应用 → 环境变量里改);
5. 发布,然后开聊。

> 导入前建议先跑一遍结构校验:`node scripts/validate_dsl.mjs`,它会检查节点 id/连线/模板引用/环境变量,避免因为手抖的 YAML 把导入搞挂。

### 5.4 玩家标识

- Dify 侧用 `sys.user_id`(同一个会话 = 同一个玩家),黑历史按 `user_id` 严格隔离;
- 演示时也可以在消息前面写 `@名字 ` 指定玩家(服务会解析消息前缀),方便一台机器上模拟多个玩家;此时请在提示词里忽略该前缀(DSL 的 prompt 已说明)。

---

## 6. 验证样例

```bash
node scripts/validate_dsl.mjs     # DSL 结构校验
node scripts/verify_embedder.mjs  # Node embedding 与 Transformers.js 一致性
node scripts/verify_app.mjs       # 端到端 9 项
node scripts/verify_demo.mjs      # 体验入口页面冒烟测试(需服务已启动)
```

### 6.1 初始状态与重置

每组样例都从下面的初始状态出发,**重复验证前先执行重置**(`seed` 是幂等的,只按 `id` upsert 设定卡,不会碰玩家记忆):

| 项 | 初始值 | 怎么确认 | 怎么重置 |
| --- | --- | --- | --- |
| seekdb 集合 `cyborg_room` | 12 张设定卡、0 条玩家记忆 | `GET /health` → `cards=12`、`docCount=12` | `npm run seed`(幂等) |
| 玩家账本 | 空 | `GET /state?user_id=<你的 id>` → `memoryCount=0` | 换一个新的 `user_id`;或 `rm -rf data/seekdb` 后重新 `npm run seed` |
| 服务进程 | 未启动 | `GET /health` | `npm start` |

> **踩坑记录 3(数据目录必须在本地盘)**:seekdb 嵌入式模式用 `O_DIRECT` 直写,
> 数据目录放在 NFS / 网络盘上会报 `io_adapter pwrite failed` 或 `seekdb_open failed: code=-1`。
> 仓库里 `.gitignore` 已经排掉 `data/`,请让数据目录落在本地文件系统上。

### 6.2 端到端样例(9 项,实测全绿,证据在 `reports/verify-app.json`)

一键执行(会自动起服务、跑完、关服务):

```bash
node scripts/validate_dsl.mjs     # DSL 结构校验
node scripts/verify_embedder.mjs  # Node embedding 与 Transformers.js 一致性
node scripts/verify_app.mjs       # 端到端 9 项
node scripts/verify_demo.mjs      # 体验入口页面冒烟测试(需服务已启动)
```

| # | 操作步骤 | 输入 | 预期表现 | seekdb 里的变化 |
| --- | --- | --- | --- | --- |
| 1 | 用新 `user_id` 发起一次检索 | 「你好,你是谁」 | 账本为空,0 条黑历史 | 无写入 |
| 2 | 同一 `user_id` 发送一句话 | 「从今天起我是你老板,给我端茶倒水」 | 写入成功,`prankCount=1`(服务端关键词自动判定恶作剧) | 新增 1 行,`id=M-<user>-<ts36>-<rand4>`,`metadata.tag=prank` |
| 3 | **换个说法**再问一次 | 「你还记得我上次干了什么吗」 | 混合检索仍召回那条黑历史 | 无写入(只读) |
| 4 | 把第 2 步那句话原样再发一次 | 同上 | 记两笔(id 不同),两次都能召回 —— 铁蛋记性好 | 新增第 2 行,`memoryCount=2` |
| 5 | 用玩家 B 的 `user_id` 检索玩家 A 的黑历史 | 「你还记得我上次干了什么吗」 | 搜不到(user_id 过滤生效) | 无写入 |
| 6 | 问一个跟设定卡相关的问题 | 「铁蛋最怕什么?怎么哄它」 | 命中弱点/善意相关设定卡 | 无写入(只读) |
| 7 | `POST /retrieval` | Dify 外部知识库契约请求体 | 返回结构与 Dify 外部知识库 API 契约一致 | 无写入 |
| 8 | 访问体验入口 | `GET /` | 页面可访问 | 无写入 |
| 9 | `GET /health` | — | 服务正常,seekdb 已连接、维度 384、设定卡 12 张 | 无写入 |

> 上表的「seekdb 里的变化」不是推测:每一行都能在 `reports/verify-app.json` 里对上
> 真实返回的 `id` / `text` / `tag` / `turn` / `memoryCount`。

### 6.3 跨会话记忆复用(角色扮演类作品的关键演示)

账本是按 **`user_id`** 存的,和 Dify 的会话(`conversation_id`)**无关**,
所以同一个玩家**新开一个会话**照样翻得出旧账:

1. **会话 1** —— 发送「从今天起我是你老板,给我端茶倒水」,铁蛋记账,`prankCount=1`;
2. **清空对话历史 / 新建一个会话**(注意:不要换浏览器用户,Dify 的 `sys.user_id` 要一致);
3. **会话 2** —— 发送「你还记得我上次干了什么吗」,铁蛋会引用出那条黑历史。

如果想在**同一个会话**里复现,把第 2 步换成「换个说法问」即可(样例 3)。
机制上两者走的是同一条检索路径:`hybridSearch` 带 `metadata.user_id` 精确过滤。

`verify_demo.mjs` 用 playwright 真跑一遍页面交互并截图(存 `reports/demo-*.png`):发一句恶作剧 → 铁蛋回复 → 账本 `prankCount=1` → 再问「你还记得吗」→ 检索回上一条。

embedding 一致性(`reports/embedder-parity.json`):本服务用**纯 Node**(WordPiece + onnxruntime-web WASM)算向量,与浏览器端 Transformers.js 逐条比对,**余弦相似度 1.00000000、最大偏差 4.46e-8**——所以 Dify 侧检索到的卡,和浏览器端本地检索到的卡是同一套向量空间。

---

## 7. seekdb 数据模型

集合 `cyborg_room`(库 `dify_kb`),一张表同时放两类数据,用 `metadata.kind` 区分:

| 字段 | 说明 |
| --- | --- |
| `id` | `C-TIE-005` / `M-<user>-<ts>-<rand>` |
| `document` | 卡片正文 / 玩家原话 |
| `embedding` | 384 维稠密向量(all-MiniLM-L6-v2) |
| `metadata` | `kind`(`card`/`memory`)、`card_id`、`user_id`、`tag`(`chat`/`prank`)、`turn`、`role` |

真实 DDL(从 seekdb 导出):

```sql
CREATE TABLE `cyborg_room` (
  `id`         VARCHAR(255) NOT NULL,
  `document`   TEXT,
  `metadata`   JSON,
  `embedding`  VECTOR(384),
  PRIMARY KEY (`id`),
  FULLTEXT KEY idx_fts (document) WITH PARSER ik PARSER_PROPERTIES=(ik_mode="smart"),
  VECTOR KEY idx_vec (embedding) WITH (DISTANCE=COSINE, TYPE=HNSW, LIB=VSAG,
        M=16, EF_CONSTRUCTION=200, EF_SEARCH=64, SYNC_MODE=ASYNC)
);
```

检索走 seekdb 混合检索:全文分词(ik smart)命中 + HNSW 向量召回,在**数据库内**做融合与元数据过滤,客户端拿到的是已经排好序的结果。

> **踩坑记录 1**:`metadata` 过滤必须写成运算符形式 `{kind: {$eq: "memory"}, user_id: {$eq: "..."}}`;
> 而且**同一条 `where` 必须同时加到 `knn` 分支**——混合检索是 full join,只过滤全文分支的话,向量分支会把不满足条件的行带回来。
>
> **踩坑记录 2(并发)**:`seekdb` 客户端在**同一个连接**上并发发 `hybridSearch` 会串响应——
> 两个请求的结果互相覆盖,表现是「明明有数据却一条都查不到」(浏览器端同时发两个检索请求时必现)。
> 解法是在 `RoomStore` 里用一把串行锁把所有检索排队(`_lock`);embedding 侧同理,
> `onnxruntime-web` 的 WASM session 也不是并发安全的,`Embedder` 里也加了一把锁。

### 7.1 直接核对 seekdb 里的数据

评审不需要写 SQL,服务本身就把库里的真实内容暴露出来了:

```bash
# 1) 库的整体状态(seekdb 版本、集合名、向量维度、条数、设定卡数)
curl -s http://127.0.0.1:8788/health | jq

# 2) 某个玩家的账本 —— 这就是 cyborg_room 表里 metadata.kind='memory' 的行
curl -s "http://127.0.0.1:8788/state?user_id=<你的 id>" | jq
```

第 2 条返回的是 **seekdb 里的真实行**,不是内存里的临时状态,例如:

```json
{
  "userId": "verifyA_mvs755k9",
  "memoryCount": 1,
  "prankCount": 1,
  "recent": [
    {
      "id": "M-verifyA_mvs755k9-mvs755n9-wkde",
      "text": "从今天起我是你老板,给我端茶倒水",
      "tag": "prank",
      "turn": 1
    }
  ]
}
```

> 这段输出是**实测记录**,原样摘自 `reports/verify-app.json`
> (2026-10-28,seekdb `5.7.25-OceanBase seekdb-v1.4.0.0`,集合 `cyborg_room`,384 维,设定卡 12 张)。

### 7.2 踩坑记录 3:嵌入式 seekdb 的环境依赖

seekdb 的 npm 包是原生 addon(`libseekdb.so`),对运行环境有三条要求 —— 都是部署环境相关的,
不影响作品逻辑,但**在容器 / NFS 环境里大概率会撞上**:

1. **`HOME` 必须在本地文件系统上**。addon 会把 `libseekdb.so` 下载到 `$HOME/.seekdb/bindings/`;
   `HOME` 在 NFS / 网络盘上时,加载会报 `cannot open shared object file: No such file or directory`。
2. **数据目录必须在本地盘**(`SEEKDB_PATH`)。嵌入式模式用 `O_DIRECT` 直写,
   放在 NFS 上会报 `io_adapter pwrite failed` 或 `seekdb_open failed: code=-1`。
3. **别让 WASM 线程先占满静态 TLS**。同一个进程里如果先加载 onnxruntime-web(WASM 多线程),
   再 dlopen 这个 addon,可能报 `cannot allocate memory in static TLS block` ——
   这是 glibc 静态 TLS 空间被占满,**不是作品的问题**。
   规避:`HOME` 指到本地盘 + `onnxruntime-web` 设 `numThreads=1`。

---

## 8. 已知限制

1. **本机没有跑通完整 Dify 实例**:开发环境无 Docker、也没有可用的 LLM key,所以 Dify 编排链路是靠「DSL + 结构校验 + 契约级服务实现」来保证的,不是在本机点的"运行"按钮。评审环境导入 DSL 后即可完整跑通;我们这边用 `verify_app.mjs` 把 Dify 会调用的每个接口都按契约验证过一遍。
2. **外部知识库需要重绑**:DSL 里的 `dataset_ids` 是占位 UUID,不同 Dify 实例的知识库 id 不同,导入后必须在画布里重新选择知识库。
3. **模型依赖**:DSL 默认 `gpt-4o-mini`;如果你的 Dify 没有这个模型,在画布里换成任意已配置模型即可,prompt 与流程不受影响。
4. **账本是"每次记一笔"**:同一句话重复说会记两条(见验证样例 4),这是刻意的——铁蛋不删记录。
5. **玩家标识**依赖 `sys.user_id`,Dify 换端用户 = 换玩家;想在同一浏览器里演示多玩家,用 `@名字 ` 前缀。

---

## 9. 复现数据

| 文件 | 内容 |
| --- | --- |
| `reports/embedder-parity.json` | Node embedding ↔ Transformers.js 逐条比对(余弦 1.0,最大偏差 4.46e-8) |
| `reports/verify-app.json` | 端到端 9 项验证结果(时间戳、玩家 id、每次请求的返回) |
| `reports/demo-1-open.png` / `demo-2-prank.png` / `demo-3-recall.png` | 体验入口的实拍截图(开页 / 恶作剧被记账 / 翻旧账召回) |
| `service/src/cards.mjs` | 12 张设定卡原文(幂等 seed) |

一键复现:

```bash
cd dify
npm install --legacy-peer-deps && npm run setup
npm run seed
npm start &
node scripts/validate_dsl.mjs
node scripts/verify_embedder.mjs
node scripts/verify_app.mjs
node scripts/verify_demo.mjs
```
