# 高德地图 · 周边去哪儿(基于高德的地点推荐助手)

赛题:《高德地图 · OceanBase 技术交流》——周边去哪儿:基于高德的地点推荐助手。

### 提交信息

| 项 | 值 |
| --- | --- |
| 赛题 | 《高德地图 · OceanBase 技术交流》——周边去哪儿:基于高德的地点推荐助手 |
| 交付目录 | `gaode/`(本目录) |
| 主要交付物 | **[`SKILL.md`](SKILL.md)** —— 提测平台只上传这一个文件 |
| 一键验证 | `node gaode/scripts/dry_run.mjs`(14/14)· `node gaode/scripts/check_skill_contract.mjs --online` |
| 索引 | 仓库根目录 [`SUBMISSIONS.md`](../SUBMISSIONS.md) |

**交付物只有一个文件:[`SKILL.md`](SKILL.md)**(提测平台只上传这一个文件)。它是一份给 Agent 读的流程说明,让 Agent 在**高德 MCP Server** 上完成「理解需求 → 查地点 → 算步行 → 筛选推荐 → 输出」。

## 目录

```
gaode/
├── SKILL.md                          # ★ 唯一交付物
├── references/
│   ├── amap-mcp-contract.json        # 高德 MCP 官方工具契约快照(从 npm 包源码提取)
│   └── mock-amap-data.json           # 本地模拟器用的 mock 数据(开发用)
└── scripts/
    ├── check_skill_contract.mjs      # SKILL.md ↔ 官方工具契约一致性校验
    ├── dry_run.mjs                   # 筛选规则的离线演练(14 项断言)
    └── mock_amap_cli.mjs             # 高德 MCP 的本地模拟器(开发/评测用)
```

## 这个 Skill 解决什么

一句话需求 → 最多 3 个**真实**地点 + **可核对**的步行距离与时间 + **有依据**的推荐理由。

评测会拿高德的工具调用记录逐条核对的字段(权重:数据真实性 40% / 需求满足 30% / 推荐合理性 20% / 表达清晰度 10%),所以这个 Skill 的重心不是"写得漂亮",而是:

| 风险 | Skill 里的对策 |
| --- | --- |
| 工具名写错,Agent 调不通 | 工具名对照官方包源码核对,`scripts/check_skill_contract.mjs` 守着 |
| **周边搜索结果里没有坐标**,Agent 直接拿 POI 列表当答案 | 明确要求先 `maps_search_detail(id)` 拿 `location`,再 `maps_direction_walking` |
| 坐标顺序写反(高德是**经度,纬度**) | 工具表里标注,列为必检项 |
| `distance` 是米、`duration` 是秒,被当成公里/分钟 | 写明单位,并规定分钟用**向上取整**显示 |
| 拿直线距离冒充步行时间 | 显式禁止;粗排可以用直线距离,但写进答案的必须来自路线查询 |
| 超时的地点被列进推荐 | 硬规则:编号项只放通过时间过滤的地点,其余放列表后的"未纳入"说明 |
| 缺依据的信息被编造(营业状态、排队、氛围) | 规定「未核实」标注,并列出哪些字段工具根本不返回 |
| 结果不足时硬凑数量 | 规定少给就说清少在哪、为什么不补超时项 |

## 三个脚本

```bash
node scripts/check_skill_contract.mjs            # SKILL.md ↔ 官方契约一致性(11 项)
node scripts/check_skill_contract.mjs --online   # 额外联网复核官方 npm 包
node scripts/dry_run.mjs                         # 筛选规则离线演练(14 项)
```

`check_skill_contract.mjs` 的联网复核会现场 `npm pack @amap/amap-maps-mcp-server@0.0.8`,把包里的 12 个工具名与 `references/amap-mcp-contract.json` 对一遍,确保没有写错。

`dry_run.mjs` 用内置 mock 数据把 Skill 里的规则真跑一遍:半径换算(15 分钟 → 1800 米)、硬过滤、边界值(610 秒 vs 600 秒上限)、近优先/评分优先排序、单位换算、结果不足与零结果的降级话术。

## 契约是怎么核准的

`references/amap-mcp-contract.json` 不是手抄的,是从官方包 `@amap/amap-maps-mcp-server@0.0.8` 的 `build/index.js` 里**程序化提取**的工具名、参数与返回字段。几个关键事实:

- 官方 12 个工具:`maps_geo` / `maps_regeocode` / `maps_ip_location` / `maps_weather` / `maps_text_search` / `maps_around_search` / `maps_search_detail` / `maps_direction_walking` / `maps_direction_driving` / `maps_direction_transit_integrated` / `maps_bicycling` / `maps_distance`
- `maps_around_search` 与 `maps_text_search` 返回的 POI 只有 `id / name / address / typecode / photos`,**没有 location**
- `maps_search_detail` 才返回 `location / type / business_area / biz_ext`(可能有 `rating`、`cost`)
- `maps_direction_walking` 返回 `route.paths[0].distance`(米)、`duration`(秒)、`steps[].instruction`
- `maps_distance` 的 `type`:`0` 直线 / `1` 驾车 / `3` 步行

## 实测情况(如实说明)

**手上没有高德 API Key,没有用真实高德数据跑过端到端。** 所以做了两件替代验证:

1. **规则层**:用 `dry_run.mjs` 把筛选逻辑跑通(14/14),确认换算、硬过滤、边界值、降级路径自洽。
2. **执行层**:写了一个返回结构与官方 MCP 完全一致的本地模拟器 `mock_amap_cli.mjs`(同样裁掉周边搜索结果里的 location),让另一个 Agent **只读 SKILL.md** 去跑真实任务,检查它会不会漏掉"必须先查详情拿坐标"这一步。

第 2 项跑出了两个真问题,都已经改进 SKILL.md:

- **Agent 会把超时地点放进编号项**。第一轮它把 12 分钟的店排在第 3 位(虽然加了说明),但用户会把编号项当成满足条件的选项,而这是硬性条件。现在写死:编号项只放通过时间过滤的地点。
- **我自己写的"四舍五入到分钟"把 610 秒显示成 10 分钟**,Agent 顺势认为它满足 10 分钟上限。现在改成**向上取整**,610 秒显示 11 分钟,和实际超时一致。

改动后重跑同一任务:推荐列表只剩 1 家达标地点,610 秒的候选被正确移到"未纳入"区。未加载 Skill 的对照组则把 610 秒和 720 秒两家都放进了编号项。

## 已知限制

- **没有真实高德数据联调**:没有 API Key,工具契约是从官方包源码核对的,行为与官方一致;但真实高德的返回可能还包含官方 MCP 未透传的字段(`biz_ext` 里的 `open_time` 等)。若评测环境的高德返回了营业时间,Skill 的"未核实"规则会让 Agent 少写一个可用信息——这是偏保守,不会导致编造。
- **不同 MCP Server 的工具名可能不同**:部分第三方高德 MCP 用 `amap_*` 前缀。Skill 里给了别名对应表;若评测用的是完全不同的命名,Agent 需要靠表里的语义描述对齐。
- **候选粗排用直线距离**:只用于决定"先查谁的路线"以省配额,写进答案的距离与时间一律来自 `maps_direction_walking`。
- 记忆、多轮反馈、跨城市迁移按赛题说明**不作为必做项**,本 Skill 未涉及。

## 复现

```bash
cd gaode
node scripts/check_skill_contract.mjs --online   # 需要联网拉官方 npm 包
node scripts/dry_run.mjs
```

想自己体验一遍(不需要高德 Key):

```bash
node scripts/mock_amap_cli.mjs maps_around_search '{"location":"120.1657,30.2766","keywords":"咖啡馆","radius":"1800"}'
node scripts/mock_amap_cli.mjs maps_search_detail '{"id":"B0FFH4"}'
node scripts/mock_amap_cli.mjs maps_direction_walking '{"origin":"120.1657,30.2766","destination":"120.1665,30.2772"}'
```
