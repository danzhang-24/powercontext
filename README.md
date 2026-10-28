# powercontext — 大赛参赛作品

OceanBase 大赛各赛题的参赛作品。共同点:**每一件都真的把技术用在了流程里**,不是把名字写进文档。

| 目录 | 赛题 | 一句话 | 技术栈 |
| --- | --- | --- | --- |
| [`stepfun/`](stepfun/) | 阶跃星辰 × seekdb | 浏览器端侧 embedding + seekdb 混合检索的迷你知识库 | Transformers.js(WebGPU / WASM)+ seekdb(server 模式) |
| [`dify/`](dify/) | Just for Fun(Dify) | 赛博搭子「铁蛋」——会记仇的 AI 室友 | Dify 编排 + seekdb 数据层(外部知识库 API 契约) |
| [`minimax/`](minimax/) | Just for Fun(MiniMax) | 规有所依——面向软件持续演进的 SDD 上下文管理系统 | MiniMax + 嵌入式 seekdb + PowerContext |
| [`gaode/`](gaode/) | 高德地图 | 周边去哪儿——基于高德的地点推荐助手 | 一个 `SKILL.md`(高德 MCP Server) |

每份作品都包含:可运行应用 / 交付物、源码、依赖与资源获取脚本、数据与表结构配置、
复现数据、一页技术说明 / README、验证脚本与证据。

## 本地快速验证

```bash
# stepfun
cd stepfun && npm install && npm run setup && npm run build && npm start
node scripts/e2e.mjs                    # 真实浏览器跑通全流程

# dify
cd dify && npm install --legacy-peer-deps && npm run setup && npm run seed && npm start
node scripts/validate_dsl.mjs           # Dify DSL 结构校验
node scripts/verify_app.mjs             # 端到端 9 项

# minimax
cd minimax && bash scripts/setup.sh && bash scripts/run_demo.sh
bash scripts/acceptance_check.sh        # 逐项自检赛题六项必做项

# gaode
cd gaode && node scripts/check_skill_contract.mjs --online   # 工具契约交叉校验
node scripts/dry_run.mjs                 # 筛选规则离线演练
```

`stepfun/` 与 `dify/` 的 `scripts/cleanroom_check.sh` 是「全新 clone → 装依赖 → 拉资源
→ 起服务 → 跑验证」的一键复现脚本。

## 踩过的坑(都写进了各自的 README)

- seekdb 的数据目录**不能放 NFS**,否则嵌入式模式报 `seekdb_open failed` / server 模式报
  `io_adapter pwrite failed`。`minimax/` 为此做了运行期目录自动探测。
- seekdb 客户端在**同一个连接上并发**发 `hybridSearch` 会串响应(表现为「明明有数据却一条都
  查不到」),必须串行化。
- `metadata` 过滤要写成运算符形式 `{kind: {$eq: "memory"}}`,且同一条 `where` 必须
  **同时**加到混合检索的 `knn` 分支。
- `onnxruntime-web` 的 WASM session **不是并发安全的**,两次 `run` 重叠会把中间张量写串
  (向量成 NaN → 检索全空),需要串行锁。
- `seekdb@1.4.0` 的可选 peer 依赖带 `workspace:*` 协议声明,`npm install` 必须加
  `--legacy-peer-deps`。
- 高德 MCP 的周边搜索结果**不含坐标**,必须再查一次详情才能算步行路线。
- `powercontext==1.2.0` 把运行期依赖放在 extras 里,只装基础包时 server 起不来。
