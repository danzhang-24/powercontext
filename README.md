# powercontext — 大赛参赛作品

OceanBase 大赛「阶跃星辰 × seekdb」赛题的两个参赛作品,都跑在 **seekdb** 上,但技术路线不同:

| 目录 | 赛题 | 一句话 | 技术栈 |
| --- | --- | --- | --- |
| [`stepfun/`](stepfun/) | 阶跃星辰 × seekdb | 浏览器端侧 embedding + seekdb 混合检索的迷你知识库 | Transformers.js(WebGPU/ WASM)+ seekdb(server 模式) |
| [`dify/`](dify/) | Just for Fun(用 Dify 做一个好玩的智能应用) | 赛博搭子「铁蛋」——会记仇的 AI 室友 | Dify 编排 + seekdb 数据层(外部知识库 API 契约) |

两份作品各自都包含:可运行应用、源码、依赖/模型获取脚本、seekdb 表结构与索引配置、复现数据、一页技术说明 / README、验证脚本与证据。

## 本地快速验证

两边的验证都只需要一台能跑 Node ≥ 20 的机器 + 一个 seekdb 实例:

```bash
# stepfun
cd stepfun && npm install && npm run setup && npm run build && npm start
node scripts/e2e.mjs                    # 真实浏览器跑通全流程

# dify
cd dify && npm install --legacy-peer-deps && npm run setup && npm run seed && npm start
node scripts/validate_dsl.mjs           # Dify DSL 结构校验
node scripts/verify_app.mjs             # 端到端 9 项
```

两边的 `scripts/cleanroom_check.sh` 都是「全新 clone → 装依赖 → 拉资源 → 起服务 → 跑验证」的一键复现脚本。

## 两份作品踩过的坑(都写进了各自的 README)

- seekdb 的数据目录**不能放 NFS**,否则写入报 `io_adapter pwrite failed`;本仓库的 seekdb 用 server 模式跑。
- seekdb 客户端在**同一个连接上并发**发 `hybridSearch` 会串响应(表现为「明明有数据却一条都查不到」),必须串行化。
- `metadata` 过滤要写成运算符形式 `{kind: {$eq: "memory"}}`,且同一条 `where` 必须**同时**加到混合检索的 `knn` 分支。
- `onnxruntime-web` 的 WASM session **不是并发安全的**,两次 `run` 重叠会把中间张量写串(向量算成 NaN → 检索全空),需要串行锁。
- `seekdb@1.4.0` 的可选 peer 依赖带 `workspace:*` 协议声明,`npm install` 必须加 `--legacy-peer-deps`。

## 许可证 / 备注

两个作品均为本次大赛参赛作品;模型权重来自 `Xenova/all-MiniLM-L6-v2`(ModelScope / HuggingFace),由 `npm run setup` 自动获取。
