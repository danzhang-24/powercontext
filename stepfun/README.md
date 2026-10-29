# 端侧 AI 迷你知识库(浏览器本地 embedding + seekdb 混合检索)

2026 OceanBase 大赛「阶跃星辰 × seekdb」赛题实现。

### 提交信息

| 项 | 值 |
| --- | --- |
| 赛题 | 《阶跃星辰 × seekdb》端侧 AI 迷你知识库 |
| 交付目录 | `stepfun/`(本目录) |
| 主要交付物 | 浏览器端侧 embedding(Transformers.js + ONNX Runtime Web)+ seekdb 混合检索知识库 |
| 一键验证 | `bash stepfun/scripts/cleanroom_check.sh` |
| 索引 | 仓库根目录 [`SUBMISSIONS.md`](../SUBMISSIONS.md) |

* **前端**:浏览器本地跑 embedding(Transformers.js v4 + ONNX Runtime Web),WebGPU 优先、WASM 自动降级;
* **数据层**:向量 / 原文 / 元数据全部存 seekdb,向量+全文的混合检索由 seekdb 内部 `DBMS_HYBRID_SEARCH` + RRF 完成;
* **服务端**:一个很薄的 Node 服务,只做「接收浏览器算好的向量 → 调 seekdb-js 落库 / 检索」,
  不做任何模型推理,也不做两路结果的客户端拼合。

> 评测与性能结论见 **[TECHNICAL-NOTE.md](./TECHNICAL-NOTE.md)**(实测数据),原始数据在 `reports/`。

---

## 1. 架构

```
┌──────────────────────── 浏览器(用户设备)────────────────────────┐
│  Transformers.js + ONNX Runtime Web                               │
│    · 文档切片                                                     │
│    · 文档向量化 / 查询向量化  ← 100% 本地推理,无云端 API            │
│    · 查询关键词抽取(给全文分支用)                                  │
│    · WebGPU 优先,失败自动降级 WASM 并在界面提示                      │
└───────────────┬────────────────────────────────────────────────┘
                │  POST /api/documents  {documents, embeddings}
                │  POST /api/search     {queryEmbedding, queryText, keywords}
┌───────────────▼────────────────────────────────────────────────┐
│  Node server(server/src)                                          │
│    · seekdb-js: upsert / refresh_index / hybridSearch             │
└───────────────┬────────────────────────────────────────────────┘
                │  MySQL 协议(2881)
┌───────────────▼────────────────────────────────────────────────┐
│  seekdb 1.4.0(OceanBase seekdb 单节点)                            │
│    FULLTEXT INDEX(document, ik) + HNSW VECTOR INDEX(embedding,384)  │
│    DBMS_HYBRID_SEARCH: 向量召回 + 全文召回 + RRF 融合              │
└─────────────────────────────────────────────────────────────────┘
```

关键点:**向量在浏览器算,检索在数据库做**。前端只把「查询向量 + 关键词」传给数据库,
拿回来的是数据库已经融合排序好的单一结果集,不存在「客户端分别取两路结果再拼合」的情况。

## 2. 快速开始

### 2.1 准备 seekdb

两种方式任选:

**A. 本地 server 模式(推荐,本仓库实测环境)**

从 [oceanbase/seekdb releases](https://github.com/oceanbase/seekdb/releases) 下载对应系统包
(如 `seekdb_1.4.0-*debian12_amd64.deb`),解包后:

```bash
SEEKDB_BIN=/opt/seekdb/usr/bin/seekdb scripts/start_seekdb.sh
```

**B. 嵌入式模式(embedded)**

不需要额外进程,seekdb-js 直接以本地目录为数据文件:

```bash
export SEEKDB_MODE=embedded
export SEEKDB_PATH=/var/lib/seekdb-kb     # 必须是本地文件系统,见下方「已知坑」
```

> ⚠️ **已知坑 1:数据目录必须放在本地文件系统。**
> 放到 NFS / 对象存储挂载上时,seekdb 的日志块直写(O_DIRECT)会失败,
> 日志里表现为 `block manager start fail` / `io_adapter pwrite failed`(errcode -4006)。
> 本项目的默认路径 `./data/seekdb` 在普通开发机上没问题;如果在容器/NFS 里跑,请用 `SEEKDB_PATH` 指到本地盘。

### 2.2 安装依赖与模型

```bash
npm install
npm run setup     # 拉取端侧模型(约 150MB)+ 拷贝 onnxruntime-web 的 wasm 运行时
```

> ⚠️ **已知坑 2:仓库里的 `.npmrc` 是必须的。**
> * `seekdb@1.4.0` 的可选 peer 依赖 `@seekdb/default-embed@1.4.0` 里带了 `workspace:*` 协议声明,
>   npm 会直接报 `EUNSUPPORTEDPROTOCOL` 安装失败。本项目不需要它(向量全部在浏览器端算),
>   所以关掉 peer 自动安装:`legacy-peer-deps=true`。
> * `@huggingface/transformers` 把 `onnxruntime-node` 列为普通依赖,它的 postinstall 要去下载
>   Node 平台的原生二进制(受限网络下会失败并中断整体安装)。浏览器端用的是 `onnxruntime-web`
>   的预编译产物,所以直接跳过安装脚本:`ignore-scripts=true`。

模型默认从 ModelScope 拉取(国内可用),失败时自动回退 Hugging Face:

```bash
npm run model:fetch
# 或指定源:
MODEL_BASE=https://hf-mirror.com/Xenova/all-MiniLM-L6-v2 npm run model:fetch
```

### 2.3 启动

```bash
# 方式一:开发模式(Vite dev server + API server)
npm run dev          # 前端 http://localhost:5173,API http://localhost:8787

# 方式二:生产模式(单端口,API 同时托管前端产物)
npm run build && npm start   # http://localhost:8787
```

### 2.4 跑验证与压测

```bash
node scripts/e2e.mjs            # 端到端 UI 验证(真实浏览器点击 + 截图)
node scripts/bench.mjs          # WASM 性能压测  -> reports/bench-wasm.json
node scripts/eval_quality.mjs   # 质量评测(Recall@K / nDCG@K)-> reports/quality.json

# WebGPU 相关(需要 GPU 的机器上跑;无 GPU 容器请加 WEBGPU=1 走软件适配器)
WEBGPU=1 BACKEND=webgpu node scripts/bench.mjs           # -> reports/bench-webgpu.json
WEBGPU=1 node scripts/verify_backends.mjs               # 两路后端向量/排序一致性
```

三个脚本都用 Playwright 驱动真实 Chromium(默认用系统 `/usr/bin/chromium`),
所有向量都在浏览器里真实算出来,不是模拟值。

### 2.5 复现量化权重

官方仓库里已经带了三份权重(FP32 / FP16 / INT8),直接用即可。
如果想从 FP32 基线自己复现量化:

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple onnx onnxruntime onnxconverter-common
python scripts/quantize_model.py \
  --fp32 web/public/models/Xenova/all-MiniLM-L6-v2/onnx/model.onnx \
  --outdir web/public/models/Xenova/all-MiniLM-L6-v2/onnx
```

脚本会打印复现产物与官方权重的体积/sha256 对比(实测 INT8 体积比 0.9955、FP16 1.0000)。

## 3. 配置项(环境变量)

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | 8787 | 本地 API 端口 |
| `SEEKDB_MODE` | `embedded`(设置了 `SEEKDB_HOST` 则为 `server`) | seekdb 接入方式 |
| `SEEKDB_PATH` | `./data/seekdb` | embedded 模式数据目录(需本地 fs) |
| `SEEKDB_HOST` / `SEEKDB_PORT` | `127.0.0.1` / `2881` | server 模式连接地址 |
| `SEEKDB_USER` / `SEEKDB_PASSWORD` | `root` / 空 | server 模式账号 |
| `SEEKDB_DATABASE` | `stepfun_kb` | 数据库名(不存在会自动创建) |
| `SEEKDB_COLLECTION` | `kb_documents` | 集合名 |
| `SEEKDB_DIMENSION` | 384 | 向量维度(与模型一致) |
| `SEEKDB_ANALYZER` | `ik` | 全文索引分词器(ik / ngram / basic) |
| `SEEKDB_FT_MODE` | `keywords` | 全文分支策略:`keywords` / `raw` / `both`(见技术说明的对比数据) |
| `SEEKDB_REFRESH_ON_WRITE` | `true` | 写入后是否立即刷新向量索引 |

## 4. 目录结构

```
stepfun/
├── server/src/
│   ├── index.mjs        # Express API: /api/health /api/documents /api/search /api/reset
│   ├── store.mjs        # seekdb-js 封装:集合 schema、upsert、refresh_index、hybridSearch
│   └── config.mjs       # 环境变量配置
├── web/
│   ├── index.html
│   ├── src/
│   │   ├── main.ts      # 界面与交互
│   │   ├── embedder.ts  # 端侧推理:WebGPU 优先 / WASM 降级 / 精度切换
│   │   ├── keyword.ts   # 查询关键词抽取(中英文)
│   │   ├── chunk.ts     # 文档切片
│   │   └── style.css
│   └── public/
│       ├── models/Xenova/all-MiniLM-L6-v2/  # 三种精度的权重(FP32/FP16/INT8)
│       ├── ort/                             # onnxruntime-web 运行时(本地化)
│       └── corpus.json                      # 示例语料
├── scripts/
│   ├── e2e.mjs          # 端到端 UI 测试
│   ├── bench.mjs        # 性能压测
│   ├── eval_quality.mjs # Recall@K / nDCG@K 评测
│   ├── verify_backends.mjs # WASM vs WebGPU 向量/排序一致性
│   ├── quantize_model.py   # 从 FP32 复现 FP16 / INT8 权重
│   ├── fetch_model.mjs  # 模型下载
│   ├── copy_ort.mjs     # 拷贝 onnxruntime-web 运行时
│   └── start_seekdb.sh  # 启动本地 seekdb server
├── data/eval-queries.json  # 评测集(查询 -> 相关文档)
├── reports/               # 实测原始数据(bench.json / quality.json / 截图)
├── TECHNICAL-NOTE.md      # 一页技术说明
└── README.md
```

## 5. 验收对照

| 赛题要求 | 实现位置 | 状态 |
| --- | --- | --- |
| 导入 → 本地向量化 → 写 seekdb → 查询 → 展示排序结果 | `web/src/main.ts` + `server/src/index.mjs` | ✅ e2e 实测 |
| 文档与查询 embedding 都在浏览器本地计算,无云端推理 API | `web/src/embedder.ts` | ✅ 模型权重与 wasm 全部本地 |
| INT8 / FP16 量化,给出体积、压缩比、质量变化 | `TECHNICAL-NOTE.md` 第 1 节 | ✅ 实测 3.94× / 2.00× |
| WebGPU 优先,不支持时降级 WASM 并明确提示 | `web/src/embedder.ts` + 界面横幅 | ✅ **WebGPU 与 WASM 两路均已验证**,降级路径实测通过 |
| 模型来源、版本、量化产生方式 | `TECHNICAL-NOTE.md` 第 1 节 + `scripts/quantize_model.py` | ✅ 名称/来源/许可/文件指纹 + 量化复现体积比 0.9955 |
| 用 seekdb 存向量/原文/元数据,混合检索在 seekdb 内完成 | `server/src/store.mjs`(`hybridSearch` → `DBMS_HYBRID_SEARCH`) | ✅ 混合 vs 纯向量 Recall +22.6% |
| 写入后刷新索引,新文档可检索 | `collection.refresh_index()` | ✅ e2e 实测(5→6 篇,新内容立即命中) |
| 增量写入 / 集合与会话状态 | `upsert` + `/api/reset` + 单一集合 | ✅ e2e 实测(重复导入不冲突) |
| 分阶段计时(含模型下载/模型加载)+ 首次/预热分开 + 报中位数 | `scripts/bench.mjs` → `reports/bench-wasm.json`、`reports/bench-webgpu.json` | ✅ |
| Recall@K / nDCG@K 对比量化前后 | `scripts/eval_quality.mjs` → `reports/quality.json` | ✅ |

## 6. 已知限制

* **WebGPU 与 WASM 两路均已实测通过**:WASM 在 Chromium 156 headless 上完整跑通;
  WebGPU 也完整跑通,但测试机是**无 GPU 容器**(`/dev/dri` 不存在),WebGPU 走的是 Chrome 自带的
  **SwiftShader 软件 Vulkan 适配器**(`adapter.info = { vendor: "google", architecture: "swiftshader" }`)。
  因此它证明的是 **WebGPU 代码路径正确可用**(模型确实建在 ORT WebGPU EP 上、
  与 WASM 的向量平均余弦 0.997221、8 条查询 × Top5 检索排序完全一致),
  **不代表真实独显的性能**。在有独显的 Chrome/Edge 上复测真实数值:
  `WEBGPU=1 BACKEND=webgpu node scripts/bench.mjs`。
* 降级逻辑本身保留并且被实测触发:无 adapter 时直接走 WASM 并弹横幅;
  WebGPU 建 session 失败时(本次即遇到 adapter 不支持 fp16)自动重试 WASM 并提示原因。
* 嵌入式模式在 NFS 挂载上无法启动(见「已知坑 1」),本次实测用本地 server 模式。
* 评测语料为 12 篇中文文档 / 20 条查询,规模偏小,用于横向对比不同配置,不追求绝对指标。
* 测试机只有 2 vCPU,同一配置的重复测量存在 ±10% 波动,报告统一给中位数;原始数据在 `reports/`。
