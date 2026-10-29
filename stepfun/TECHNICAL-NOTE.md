# 端侧 AI 推理性能优化与 seekdb 混合检索 —— 一页技术说明

> 赛题:2026 OceanBase 大赛「阶跃星辰 × seekdb」
> 作品:浏览器本地 embedding + seekdb 向量/全文混合检索的迷你知识库
> 全部数字来自本仓库脚本的实测(`reports/bench-wasm.json`、`reports/bench-webgpu.json`、
> `reports/quality.json`、`reports/quality-webgpu.json`、`reports/backend-consistency.json`),
> 测试在真实 Chromium 里跑,向量是真在浏览器里算出来的。

---

## 1. 模型与量化

| 项目 | 说明 |
| --- | --- |
| **模型名** | `Xenova/all-MiniLM-L6-v2`(Transformers.js 官方导出格式),基座模型 `sentence-transformers/all-MiniLM-L6-v2` |
| **来源** | Hugging Face 仓库 `Xenova/all-MiniLM-L6-v2`;国内网络经 ModelScope 镜像 `Xenova/all-MiniLM-L6-v2` 拉取(同一批文件,字节一致) |
| **许可** | MIT(可公开获取,符合赛题要求) |
| **版本** | 仓库 revision `master`;下表给出文件 sha256 指纹,用于精确锁定本次实测使用的权重 |
| **维度** | 384(与 seekdb 集合 `VECTOR(384)` 对齐) |
| **运行时** | `@huggingface/transformers@4.3.2` + `onnxruntime-web@1.31.0-dev.20260914-8d85527a0`(wasm 运行时本地化,不依赖 CDN) |
| **数据层** | `seekdb`(JS SDK)@1.4.0 + seekdb server 1.4.0.0(`5.7.25-OceanBase seekdb-v1.4.0.0`) |

**权重文件指纹(本次实测使用的文件)**

| 文件 | 字节数 | 体积 | sha256(前 16 位) |
| --- | --- | --- | --- |
| `onnx/model.onnx`(FP32 基线) | 90,387,606 | 86.2 MB | `759c3cd2b7fe7e93` |
| `onnx/model_fp16.onnx` | 45,297,825 | 43.2 MB | `2cdb5e58291813b6` |
| `onnx/model_quantized.onnx` | 22,972,370 | 21.9 MB | `afdb6f1a0e45b715` |
| `config.json` / `tokenizer.json` | 650 / 711,661 | — | `7135149f7cffa1a5` / `da0e79933b9ed517` |

### 量化产生方式

赛题要求「对 embedding 模型采用 INT8 或 FP16 方案,说明处理方式」。本项目的做法是**双轨**:

1. **直接使用上游官方导出的量化权重**(运行时实际加载的就是上面这三个文件):
   * `model_fp16.onnx`:FP32 → FP16,`onnxconverter_common.float16.convert_float_to_float16(keep_io_types=True)`,
     权重与计算转半精度,**模型输入输出仍保持 FP32**;
   * `model_quantized.onnx`:**动态 int8 量化**,`onnxruntime.quantization.quantize_dynamic(weight_type=QInt8,
     per_channel=False, reduce_range=False)`,权重存成 int8(`MatMulInteger` / `DynamicQuantizeLinear`),
     激活值在运行时按批次动态量化。
2. **提供可复现脚本** `scripts/quantize_model.py`,从同一份 FP32 基线现场复现这两份权重:

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple onnx onnxruntime onnxconverter-common
python scripts/quantize_model.py \
  --fp32 web/public/models/Xenova/all-MiniLM-L6-v2/onnx/model.onnx \
  --outdir web/public/models/Xenova/all-MiniLM-L6-v2/onnx
```

实测复现结果与官方文件对比:

| 权重 | 本地复现体积 | 官方体积 | 体积比(本地/官方) |
| --- | --- | --- | --- |
| INT8(动态量化) | 21.8 MB | 21.9 MB | **0.9955** |
| FP16 | 43.2 MB | 43.2 MB | **1.0000** |

即:官方量化权重可由 FP32 基线用标准 ONNX 工具链复现,体积基本一致(sha256 不同是因为导出流水线的
算子融合与 metadata 略有差异)。

**压缩比与质量变化**

| 配置 | 权重体积 | 压缩比(FP32/当前) |
| --- | --- | --- |
| FP32 基线 | 86.2 MB | 1.00× |
| FP16 | 43.2 MB | **2.00×** |
| INT8 (q8) | 21.9 MB | **3.94×** |

**检索质量**(同一评测集:12 篇中文语料 + 20 条人工标注查询,同一集合、同一查询集,唯一变量是模型精度;
指标 Recall@5 / nDCG@5,混合检索,INT8 与 FP32 的向量由 WASM 后端产出)

| 配置 | Recall@5 | nDCG@5 | 相对 FP32 |
| --- | --- | --- | --- |
| FP32 基线 | 0.950 | 0.8142 | — |
| FP16 | 0.950 | 0.8142 | **0.0000**(指标完全一致) |
| INT8 (q8) | 0.950 | 0.8127 | nDCG **-0.0015(-0.18%)**,Recall 不变 |

结论:INT8 以 3.94× 的体积压缩换来 <0.2% 的检索质量损失,端侧性价比最高;
FP16 体积减半且质量与 FP32 完全一致,适合 WebGPU。

---

## 2. 端侧运行(WebGPU 优先 + WASM 自动降级)

### 2.1 策略

* 启动时用 `navigator.gpu.requestAdapter()` **实际探测**(只看 `navigator.gpu` 存在会误判:
  它只在安全上下文且 GPU 可用时暴露),拿到 adapter 才以 `device: 'webgpu'` 建会话。
* 建会话阶段抛错也自动降级:例如某 adapter 不支持 fp16,Transformers.js 会直接抛
  `The device (webgpu) does not support fp16` —— 此时捕获异常、自动以 `device: 'wasm'` 重建,
  **不中断主流程**,并把原因写进界面横幅。
* 降级发生时页面顶部弹出:`⚠️ 当前浏览器/设备没有可用的 WebGPU adapter,已自动降级到 WASM`,
  右上角徽标同步显示「推理后端:WASM」;界面另提供「强制 WASM」选项,便于人工验证降级路径。
* WASM 线程数按 `crossOriginIsolated` 判断:未开启跨源隔离(COOP/COEP)时退化为单线程,避免 `SharedArrayBuffer` 报错。

### 2.2 两路均已验证(WebGPU 与 WASM 都跑通)

| 后端 | 验证方式 | 结果 |
| --- | --- | --- |
| WASM | Chromium 156 headless,`device: 'wasm'` | ✅ 端到端跑通(导入 → 向量化 → 写库 → 检索),降级横幅正常弹出 |
| WebGPU | Chromium 156 headless + `--enable-unsafe-webgpu --use-webgpu-adapter=swiftshader` | ✅ 端到端跑通,界面徽标显示「推理后端:WebGPU」,模型确实建在 WebGPU EP 上 |

WebGPU 路径的额外证据:

* **adapter 实测**:`adapter.info = { vendor: "google", architecture: "swiftshader" }`。
  本机容器没有 `/dev/dri`(无任何 GPU 设备节点),系统 Vulkan 初始化失败
  (浏览器日志 `vkCreateInstance() failed: -9`),Chrome 于是用自带的 **SwiftShader 软件 Vulkan**
  把 WebGPU 跑起来了 —— Dawn + WGSL shader + ONNX Runtime Web 的 WebGPU EP 全链路都真实执行过。
* **两路向量一致性**:同一模型、同一批 12 篇文本,两个后端各算一遍:
  * 平均余弦相似度 **0.997221**,单条最小余弦 0.9962,最大绝对偏差 1.81e-2;
  * 把两路向量分别写入 seekdb 再检索,**8 条查询 × Top5 的排序结果完全一致**。
  (差异来自两个后端 kernel 的浮点舍入,不影响检索语义。)
* **WebGPU 专属能力差异**:该 adapter 不支持 fp16,Transformers.js 直接报错,应用按设计降级到 WASM 并提示原因。

> ⚠️ **诚实边界**:测试机无独显,上表的 WebGPU 数值是**软件适配器(SwiftShader)**的结果,
> 只证明 WebGPU 代码路径正确可用,**不能代表真实独显的性能**(软件 Vulkan 比 WASM 慢很多)。
> 在有独显的 Chrome/Edge 上复测只需要一条命令:
> ```bash
> WEBGPU=1 BACKEND=webgpu node scripts/bench.mjs
> WEBGPU=1 BACKEND=webgpu node scripts/verify_backends.mjs
> ```
> 代码路径完全一致,换到有 GPU 的机器上即得真实 GPU 数值。

---

## 3. seekdb 使用(表结构、混合检索、增量写入)

### 3.1 集合/表结构(从运行中的实例 `SHOW CREATE TABLE` 导出)

```sql
CREATE TABLE `c$v2$dc2c4033d2b511f1bb4f00163e530593` (
  `_id`       varbinary(512) NOT NULL,
  `document`  string DEFAULT NULL,     -- 原文,全文索引列
  `embedding` VECTOR(384) DEFAULT NULL, -- 浏览器端算好的向量
  `metadata`  json DEFAULT NULL,        -- 来源、chunk 下标等元数据
  PRIMARY KEY (`_id`),
  FULLTEXT KEY `idx_fts` (`document`)
      WITH PARSER ik PARSER_PROPERTIES=(ik_mode="smart") BLOCK_SIZE 16384,
  VECTOR KEY `idx_vec` (`embedding`)
      WITH (DISTANCE=COSINE, TYPE=HNSW, LIB=VSAG, M=16, EF_CONSTRUCTION=200,
            EF_SEARCH=64, SYNC_MODE=ASYNC) BLOCK_SIZE 16384
) ORGANIZATION HEAP DEFAULT CHARSET = utf8mb4 ROW_FORMAT = DYNAMIC
  COMPRESSION = 'zstd_1.3.8' BLOCK_SIZE = 16384 TABLET_SIZE = 134217728
  PCTFREE = 0 LOB_INROW_THRESHOLD=78643;
```

* `FULLTEXT KEY idx_fts` + `PARSER ik (ik_mode="smart")`:中文全文索引;
* `VECTOR KEY idx_vec`:HNSW(库 VSAG),余弦距离,M=16 / EF_CONSTRUCTION=200 / EF_SEARCH=64;
* **`SYNC_MODE=ASYNC`**:向量索引异步构建 —— 这正是写入后必须显式刷新索引的原因(见 3.3)。

### 3.2 混合检索(检索与融合全部在数据库内完成)

调用 seekdb-js 的 `collection.hybridSearch()`,由数据库的 `DBMS_HYBRID_SEARCH` 统一完成
「向量召回 + 全文召回 + RRF 融合」,返回的已是排好序的**单一结果集**:

```js
await collection.hybridSearch({
  query: { whereDocument: { $or: keywords.map(k => ({ $contains: k })) } }, // 全文分支
  knn:   { queryEmbeddings: [queryEmbedding] },                              // 向量分支
  rank:  { rrf: { rankWindowSize: 60, rankConstant: 60 } },                  // RRF 融合
  nResults: 8,
});
```

客户端只负责把「浏览器端算出的查询向量」和「查询关键词」传下去,
**不存在分别取两路结果再自行拼合**的情况。

**混合 vs 纯向量**(同语料同查询,20 条标注查询)

| 检索方式 | Recall@5 | nDCG@5 |
| --- | --- | --- |
| 纯向量(HNSW) | 0.775 | 0.6539 |
| **向量 + 全文(RRF)** | **0.950** | **0.8142** |
| 提升 | **+22.6%** | **+24.5%** |

**全文分支三种策略实测**(FP32,同评测集),最终采用「前端抽词」:

| 全文分支策略 | Recall@5 | nDCG@5 | 结论 |
| --- | --- | --- | --- |
| raw:原始查询交给数据库 ik 分词 | 0.900 | 0.7969 | 实现最简单,但疑问词被当成宽泛条件,精度偏低 |
| **keywords:前端抽词(去虚词)+ DB 内 OR 匹配** | **0.950** | **0.8142** | **采用** |
| both:两者并集 | 0.900 | 0.7873 | 宽泛条件把弱相关文档带进来,反而变差 |

### 3.3 增量写入、索引刷新与集合状态

* 写入后调用 `collection.refresh_index()`(内部执行 `CALL dbms_index_manager.refresh()`),
  配合 `SYNC_MODE=ASYNC` 的向量索引,保证新文档刷新后立即可检索(实测刷新耗时 405 ~ 505 ms)。
* 写入用 `upsert` 而不是 `add`:重复导入同一份内容是「更新」而不是主键冲突,增量导入可随时重跑。
* e2e 实测:第一轮导入 5 篇 → 第二轮增量导入 1 篇(集合 5 → 6,**新内容立即可被检索到**)
  → 重复导入同一份内容(集合 6 → 6,无冲突)。
* 集合与会话状态:前端持有单一集合,服务端启动时 `getOrCreateCollection` 保证集合与索引结构存在,
  并显式声明 `embeddingFunction: null`(向量全部来自浏览器端,数据库侧不挂任何 embedding function,
  也就不会回落到服务端模型);`POST /api/reset` 提供「清空知识库」用于演示。

---

## 4. 性能数据

**测试环境**:Chromium 156(HeadlessChrome/156.0.0.0),容器 2 vCPU / 3 GB,**无 GPU**
(→ WebGPU 走 SwiftShader 软件适配器,见 2.2 的边界说明);语料 12 篇,查询集 8 条,每条重复 3 轮,
**全部指标取中位数**;seekdb 1.4.0.0 单节点本地 server(2881)。
每种精度都用**全新浏览器实例**跑,避免 WASM 运行时被上一个用例预热,保证「首次」与「预热后」可比。

### 4.1 赛题要求的三行对比表

| 配置 | 模型体积 | 向量化吞吐 | seekdb 检索延迟 | 端到端查询延迟 | 检索质量 |
| --- | --- | --- | --- | --- | --- |
| 量化前基线(FP32 + WASM) | 86.2 MB | 4.20 篇/s | 7.47 ms | 51 ms(P95 117) | Recall@5 0.950 / nDCG@5 0.8142 |
| **INT8 + WebGPU** | 21.9 MB(3.94×) | **0.16 篇/s**(软件适配器) | 8.29 ms | 633 ms(P95 818) | Recall@5 0.950 / nDCG@5 0.8224 |
| **INT8 + WASM** | 21.9 MB(3.94×) | **7.17 篇/s** | 5.95 ms | **48 ms**(P95 115) | Recall@5 0.950 / nDCG@5 0.8127 |

> WebGPU 行的吞吐受限于「无独显 → SwiftShader 软件 Vulkan」,**不代表真实 GPU**;
> 但它证明 WebGPU 代码路径(含 ORT WebGPU EP)完整可用,且检索质量与 WASM 一致。
> 真实独显上复测:`WEBGPU=1 BACKEND=webgpu node scripts/bench.mjs`。
> 三个配置里 **seekdb 检索延迟都稳定在 6 ~ 8 ms**,说明检索耗时几乎不受推理后端影响,瓶颈在端侧向量化。
> 本机只有 2 vCPU,同一配置重复测量存在 ±10% 波动,表中统一给中位数,原始数据见 `reports/`。

### 4.2 分阶段计时(中位数;首次与预热分开)

| 配置 | 模型下载 | 模型加载(含解析建 session) | 文档向量化(首次) | 文档向量化(预热后) | seekdb 写入 | 索引刷新 | 查询向量化 | seekdb 检索 | 端到端 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FP32 + WASM | 1003 ms | 7492 ms | 7170 ms | 2855 ms | 32 ms | 601 ms | 27.8 ms | 7.47 ms | 51 ms |
| FP16 + WASM | 905 ms | 7261 ms | 12537 ms | 2929 ms | 32 ms | 502 ms | 29.5 ms | 5.95 ms | 48 ms |
| INT8 + WASM | 836 ms | 5490 ms | 7123 ms | 1674 ms | 34 ms | 601 ms | 20.6 ms | 5.95 ms | 48 ms |
| INT8 + WebGPU(软件适配器) | 305 ms | 5752 ms | 87797 ms | 77408 ms | 77 ms | 529 ms | 598.0 ms | 8.29 ms | 633 ms |

口径说明:
* **模型下载**与**模型加载**分开计时:下载取 `PerformanceResourceTiming` 里权重文件的 duration,
  加载为「建 pipeline + 建 ONNX session」的总耗时(其中包含 ORT WASM 运行时初始化,本机约 5 s,与模型大小无关);
* **seekdb 写入**取 SDK 的 `add/upsert` 耗时,**索引刷新**取 `refresh_index()` 耗时 ——
  写本身只要 30 多 ms,真正的时间花在向量索引刷新(500 ~ 600 ms),这与 `SYNC_MODE=ASYNC` 的设计一致;
* 查询向量化在浏览器内计时,seekdb 检索在服务端计时,端到端为「用户点检索 → 结果渲染」的全程;
* 首屏(冷启动)与预热后分开报告,所有延迟类指标取中位数而非最快值。

### 4.3 已做的优化(每次只改一个变量)

| 优化点 | 做法 | 实测收益 |
| --- | --- | --- |
| INT8 动态量化 | `dtype: 'q8'` | 体积 -74.6%,向量化吞吐 4.20 → **7.17 篇/s(+71%)**,查询向量化 27.8 → **20.6 ms(-26%)**,端到端 51 → 48 ms,质量 -0.18% |
| FP16 量化 | `dtype: 'fp16'` | 体积 -49.9%,质量与 FP32 完全一致;本机 software adapter 不支持 fp16,自动降级 WASM(降级链路被实测触发) |
| 批量向量化 | 一次送 16 条(`pipe(texts[], {pooling:'mean', normalize:true})`) | 显著降低逐条推理的调度开销;批量大小是当前最主要的可调参数 |
| 模型实例复用 | 同一个 pipeline 服务「导入 + 全部查询」 | 避免重复建 session(每次重建约 5 s) |
| 索引刷新策略 | 写完立即 `refresh_index()` | 写入 30 ms + 刷新 ~0.55 s,新文档可检索延迟从不确定收敛到 ~0.6 s,查询不再出现「刚写入搜不到」 |
| 全文分支策略 | 前端抽词(去虚词)+ DB 内 OR 匹配 | Recall@5 0.900 → **0.950**,nDCG@5 0.7969 → **0.8142** |
| RRF 参数 | `rank_window_size=60`、`rank_constant=60` | 融合稳定,避免单路结果抖动主导排序 |

---

## 5. 复现方式

```bash
npm install          # 注意 .npmrc 里两个 workaround(见 README「已知坑」)
npm run setup        # 拉模型(约 150MB)+ 拷贝 onnxruntime-web 运行时
npm run build && npm start

node scripts/e2e.mjs             # 端到端 UI 验证(真实浏览器点击)+ 截图
node scripts/bench.mjs           # WASM 性能压测  -> reports/bench-wasm.json
WEBGPU=1 BACKEND=webgpu node scripts/bench.mjs   # WebGPU 压测 -> reports/bench-webgpu.json
node scripts/eval_quality.mjs    # 质量评测(Recall@K / nDCG@K)
WEBGPU=1 node scripts/verify_backends.mjs        # 两路后端向量一致性 + 排序一致性
python scripts/quantize_model.py --fp32 <model.onnx> --outdir <outdir>   # 量化复现
```
