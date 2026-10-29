# OceanBase 2026 大赛 · 参赛作品索引

本仓库是 [`oceanbase/powercontext`](https://github.com/oceanbase/powercontext) 的 fork。
下面每个目录都是本次大赛的**参赛作品**,每个目录**自包含、可独立运行**,
**不依赖**本仓库 `src/` 下的 PowerContext 核心功能代码 —— 评测时不需要理解内核实现,
按目录里的说明装好依赖就能跑起来。

| 赛题 | 子题 id | 交付目录 | 主要交付物 | 一键验证 |
| --- | --- | --- | --- | --- |
| 《Just for Fun——用 Dify 做一个好玩的智能应用》 | **800513** | [`dify/`](dify/) | 可直接导入 Dify 的应用 DSL + 记忆/设定卡数据层服务 | `bash dify/scripts/cleanroom_check.sh` |
| 《规有所依——面向软件持续演进的 SDD 上下文管理系统》 | 见训练营对应子题 | [`minimax/`](minimax/) | `sddctx` 上下文管理模块 + 规格/测试/任务状态全链路 | `bash minimax/scripts/acceptance_check.sh` |
| 《高德地图 · 周边去哪儿——基于高德的地点推荐助手》 | 见训练营对应子题 | [`gaode/`](gaode/) | `SKILL.md`(提测平台只上传这一个文件) | `node gaode/scripts/dry_run.mjs` |
| 《阶跃星辰 × seekdb》端侧 AI 迷你知识库 | 见训练营对应子题 | [`stepfun/`](stepfun/) | 浏览器端侧 embedding + seekdb 混合检索知识库 | `bash stepfun/scripts/cleanroom_check.sh` |
| 《Qoder》PaperPocket 混合检索 | 见训练营对应子题 | [`qoder/`](qoder/) | 论文语料混合检索 CLI + 记忆/回放记录 | `bash qoder/scripts/verify.sh` |

> **重要**:以上作品位于仓库的**默认分支 `master`**。
> 评测平台会从默认分支检出仓库,所以五个作品目录都在默认分支上,不需要切换任何分支。

---

## 目录说明

### [`dify/`](dify/) —— 赛博搭子「铁蛋」(Dify × seekdb)

- **一句话**:一个会记仇的 AI 室友。你今天对它做了什么,它会写进赛博账本;下次你客客气气地来,它照样翻旧账。
- **路线**:Dify 负责角色扮演与编排,seekdb 负责设定卡检索与黑历史记忆。
- **交付物**:
  - `dify/dsl/cyborg-tiedan.yml` —— Dify 应用 DSL(advanced-chat,7 节点),Dify 界面「导入 DSL」即可用;
  - `dify/service/` —— 记忆/设定卡数据层服务(seekdb 落库 + 混合检索);
  - `dify/scripts/verify_app.mjs`、`verify_demo.mjs`、`verify_embedder.mjs` —— 9/9、6/6 与向量一致性验证。
- **详细说明**:[`dify/README.md`](dify/README.md)

### [`minimax/`](minimax/) —— 规有所依(SDD 上下文管理系统)

- **一句话**:把规格、代码与测试导入 seekdb,按任务描述检索开发上下文交给 MiniMax 改代码,跑功能与回归测试,再把任务状态存入 PowerContext,重启后可读回复用。
- **交付物**:`minimax/sddctx/` 模块 + `demo_project/` + `records/`(实测记录)+ `docs/acceptance-checklist.md`(六项必做项逐项对照)。
- **详细说明**:[`minimax/README.md`](minimax/README.md)

### [`gaode/`](gaode/) —— 周边去哪儿(高德地点推荐助手)

- **一句话**:用一句话找到「附近值得去的地方」,并给出真实可核对的步行路线信息。
- **交付物**:**只有 `gaode/SKILL.md` 一个文件**(提测平台只上传这一个),是一份给 Agent 读的流程说明。
- **关键事实**(程序化提取自官方 MCP Server 源码,可用 `--online` 现场复核):`maps_around_search` / `maps_text_search` 返回的 POI **不含坐标**,必须再调 `maps_search_detail(id)` 才能算步行路线。
- **详细说明**:[`gaode/README.md`](gaode/README.md)

### [`stepfun/`](stepfun/) —— 端侧 AI 迷你知识库(阶跃星辰 × seekdb)

- **一句话**:浏览器本地跑 embedding,向量/原文/元数据全存 seekdb,混合检索交给 seekdb 内核的 `DBMS_HYBRID_SEARCH` + RRF,服务端不做任何推理。
- **实测**(本机沙箱,SwiftShader 软件渲染):FP32 86.2MB / 4.20 篇/s / 端到端 51ms / R@5 0.950;nDCG 0.8142;两路向量平均余弦 **0.997221**,检索排序完全一致。
- **详细说明**:[`stepfun/README.md`](stepfun/README.md)

### [`qoder/`](qoder/) —— PaperPocket 混合检索

- **交付物**:`qoder/paperpocket/` CLI + `corpus/` 论文语料 + `records/` 检索与记忆记录 + `docs/tech-design.md`。
- **详细说明**:[`qoder/docs/run-guide.md`](qoder/docs/run-guide.md)

---

## 本地验证

各作品目录都带独立的自检脚本,建议按顺序执行:

```bash
bash dify/scripts/cleanroom_check.sh          # Dify:干净环境复现 + 9/9 + 6/6
bash minimax/scripts/acceptance_check.sh      # MiniMax:六项必做项自检
node gaode/scripts/dry_run.mjs                # 高德:14/14 离线用例
node gaode/scripts/check_skill_contract.mjs --online   # 高德:工具契约联网复核
bash stepfun/scripts/cleanroom_check.sh       # 阶跃:端侧 embedding 复现
bash qoder/scripts/verify.sh                  # Qoder:检索与记忆校验
```

依赖安装统一走清华镜像;`notes/` 下是赛题题面存档(**非交付物**,仅备查)。
