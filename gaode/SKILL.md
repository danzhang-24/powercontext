---
name: gaode-nearby-explorer
description: |
  基于高德地图 MCP Server 的周边地点推荐助手(nearby places explorer)。用一句话找到「附近值得去的地方」并给出真实可核对的步行路线信息。
  Use this skill when the user asks 附近有什么 / 周边去哪 / 推荐附近的咖啡馆(餐厅、公园、书店、健身房……) / "我在这儿,想步行去某类地方",
  especially when the request contains a city, a starting point, a walking-time limit (步行不超过 15 分钟), a count (推荐 3 家),
  or a tie-breaker (优先近一点 / 优先评分高). Output: a short list of real POIs with address, walking distance and walking time
  taken from Amap walking-direction results, plus a data-grounded reason for each.
  Do NOT use for 驾车/公交/骑行导航, 多站行程规划, 单纯问距离或问天气, 以及不需要地点推荐的闲聊。
---

# 周边去哪儿 · 高德地点推荐

把一句自然语言需求变成**最多 3 个真实地点** + **可核对的步行距离与时间** + **有依据的推荐理由**。

评测会拿高德的工具调用记录逐条核对:地点、地址、步行距离、步行时间只要有一条对不上,数据真实性(权重 40%)就掉。所以**只写工具真实返回过的数据**,缺信息就标「未核实」,查不到就如实说查不到。

## 输入解析

从用户这句话里抽 5 个槽位,抽不到的用默认值,不要反问(评测是单轮任务):

| 槽位 | 默认值 | 说明 |
| --- | --- | --- |
| 地点类型 | 必填 | 从「咖啡馆/餐厅/公园/…」里抽。抽不出具体类型就按「餐饮」处理并说明 |
| 起点 | 必填 | 评测通常直接给**经纬度**;给的是地址或「XX 地铁站」这类地标,先用 `maps_geo` 转坐标 |
| 步行时间上限 | 15 分钟 | 用户说「10 分钟内」就用 10;没说就用 15,并在回答里注明按 15 分钟筛的。上限是**硬条件**:900 秒就是 900 秒,不因为显示成「15 分钟」就多给一家 |
| 推荐数量 | 3 | 用户说 2 家就 2 家;最多 3 |
| 偏好 | 近优先 | 「优先近一点」= 按步行时间升序;「评分高」= 按 `maps_search_detail` 返回的 `biz_ext.rating` 降序;没有该字段就按近优先 |

## 工具速查(高德 MCP Server)

主要工具(官方 `@amap/amap-maps-mcp-server`):

| 工具 | 参数 | 返回里**有**什么 |
| --- | --- | --- |
| `maps_around_search` | `keywords`、`location`、`radius` | `pois[{id,name,address,typecode,photos}]` |
| `maps_text_search` | `keywords`、`city`、`types` | `pois[{id,name,address,typecode,photos}]` |
| `maps_search_detail` | `id` | `location`、`address`、`business_area`、`city`、`type`、`alias` + `biz_ext`(可能有 `rating`/`cost`/`tag`) |
| `maps_direction_walking` | `origin`、`destination` | `route.paths[0].distance`(米)、`duration`(秒)、`steps[].instruction` |
| `maps_geo` | `address`、`city` | `location` |
| `maps_regeocode` | `location` | `addressComponent` |
| `maps_distance` | `origins`、`destination`、`type` | `results[]{distance,duration}`;`type`:`0`直线 / `1`驾车 / `3`步行 |

四个必须记住的坑:

1. **坐标格式是「经度,纬度」**(`116.481488,39.990464`),和高德 API 一样,不是 lat,lng。写反了路线规划会失败或算出离谱结果。
2. **`maps_around_search` 和 `maps_text_search` 不返回 POI 的经纬度**,只给 `id`。想拿坐标必须再调一次 `maps_search_detail(id)`。这是整个流程里最容易漏的一步。
3. **`distance` 单位是米,`duration` 单位是秒**。900 秒才是 15 分钟。
4. **直线距离(`maps_distance` 的 `type=0`)不能当步行距离用**。用户要的是「走过去要多久」,只能来自 `maps_direction_walking`。

如果环境里的工具名不是 `maps_*`(有些第三方 MCP Server 用 `amap_*` 前缀),按语义对应即可:`amap_poi_around`≈`maps_around_search`、`amap_poi_search`≈`maps_text_search`、`amap_direction_walking`≈`maps_direction_walking`、`amap_poi_detail`≈`maps_search_detail`、`amap_geocode`≈`maps_geo`。

## 流程

### 1. 把起点变成坐标

- 评测给的是 `经度,纬度` → 直接用。
- 给的是地址 → `maps_geo(address=…, city=…)` 取 `location`。
- 给的是地标(「武林路地铁站」)→ `maps_geo` 通常能解析;解析不出来再 `maps_text_search` 找到那个 POI 的 `id`,然后 `maps_search_detail` 取 `location`。
- 起点解析不出来 → 停下来说明缺什么,不要拿猜测的坐标继续查。

### 2. 取候选地点

`maps_around_search(keywords=类型关键词, location=起点坐标, radius=半径米)`

半径怎么定:成年人步速约 75–80 米/分钟,15 分钟 ≈ 1.1–1.2 公里;路网会绕行,实际步行距离比直线远。**半径取步行上限 × 80 米 × 1.5 倍余量**,15 分钟 → 约 1800 米(一般取 1500–2000)。半径太小会把步行可达的地点漏在候选外,后面再怎么筛也补不回来。

- 候选为空 → 换更宽的关键词(「咖啡馆」→「咖啡」)、去掉修饰词(「安静的书店」→「书店」)再试一次,仍为空则按「结果不足」处理。
- 候选太少(不足要推荐的 3 家) → 可以把半径放大到 1.5 倍再搜一轮,用来补充候选多样性;时间过滤规则不变,超时的照样不能进推荐。
- 候选太多 → 按后续流程粗筛,不用全查路线。

### 3. 给候选补坐标(必做)

对筛出来的每个候选调 `maps_search_detail(id=…)`,拿 `location`、`address`、`type`(中文类型全称,用来确认类型真的符合需求)和 `biz_ext`。

`biz_ext` 里如果带 `rating`/`cost`/`tag`,可以拿来做排序和推荐理由;没有就没有,别编。

### 4. 算真实步行距离与时间

对每个候选调 `maps_direction_walking(origin=起点坐标, destination=候选location)`:

```
distance = route.paths[0].distance   # 米
duration = route.paths[0].duration   # 秒
```

`steps[].instruction` 是分段的路线描述,可以用一句话概括「沿 XX 路向东走,再拐进 XX 路」,这是有依据的路线说明。

**调用预算**:最多给 5–8 个候选查路线。候选多于这个数时,先用 `maps_search_detail` 拿到的坐标做**粗排**(直线距离近的先查),再逐个查步行路线。粗排只是省配额的手段,**最终写进回答的距离和时间必须来自 `maps_direction_walking`**。

### 5. 筛选与排序

1. **硬过滤**:`duration ≤ 上限秒数`(15 分钟 = 900 秒)。比较的是**原始秒值**,不比较显示出来的分钟数。
2. **超时的地点不进推荐列表**。编号项里只放通过硬过滤的地点;哪怕加一句「如果放宽到 18 分钟可以考虑」,它也不该占一个编号——用户会把编号项当成满足条件的选项,而「只推荐步行上限内可达的地点」是硬性条件,评测会拿高德数据逐条核对。
   想给用户留后路,就在推荐列表**之后**单独写一句:「另有 2 家在 18–22 分钟,超出你要求的 15 分钟,放宽到 22 分钟可以选」。
3. **排序**:有明确偏好按偏好排;「优先近一点」按 `duration` 升序。排序和展示顺序要一致——用户说「优先近一点」,第一项就该是最近的。
4. **取前 N 家**(N ≤ 3)。达标数不足 N 就只给达标的那几家,并在列表后说明少了多少、为什么(时间不够还是这个品类就没有)。

### 6. 输出

用表格或列表,**每个地点必须有这五项**:名称、地址、预计步行距离、预计步行时间、推荐理由。

推荐理由只能由工具数据支撑,按这个优先级取:

- 路线特征:「沿中山北路走约 1.1 公里,中途经过 XX 路路口」
- 类型匹配:`maps_search_detail` 的 `type` 字段确认它确实是「咖啡厅」而不是「咖啡豆专卖店」→ 「类型为咖啡厅,符合你说的『咖啡馆』」
- 数据字段:`biz_ext.rating` / `biz_ext.cost` 有值才写,例如「人均 38 元(高德标注)」
- 距离优势:「步行约 8 分钟,是这几家里最近的」

**没有依据的信息一律标注「未核实」**,例如:

- 营业状态:`maps_search_detail` 不返回营业时间 → 写「营业状态未核实」
- 排队 / 拥挤程度:任何工具都不返回 → 写「排队情况未核实」
- 安静程度 / 氛围 / 户外座位 → 写「未核实」

宁可多标几个「未核实」,也不要写出一个评测一比对就穿帮的细节——编造的描述不能作为加分依据,反而会在数据真实性上扣分。

## 输出格式

```
按你的要求(步行 ≤ 15 分钟,最多 3 家,近优先),推荐:

1. <地点名称>
   地址:<maps_search_detail 的 address>
   步行:约 <distance 米,换算成公里> ,约 <duration 秒换算成分钟>
   推荐理由:<一句有数据依据的话>

2. ...

<如有需要:说明信息缺口(未核实项)、结果不足的原因或建议放宽的条件>
```

**「推荐列表」和「未纳入」要分开写**:编号项只放达标地点;超时的、查不到路线的、缺坐标的,统一放到编号项之后的说明里,并写清它们各自为什么没进推荐。这样用户不会把超时地点当成满足条件的选项,评测核对路线数据时也不会出现「列了但超时」的矛盾。

距离统一写成「约 1.1 公里(1120 米)」,时间统一写成「约 12 分钟(720 秒)」;换算口径 1 公里 = 1000 米,1 分钟 = 60 秒。

分钟数用**向上取整**(`ceil(duration/60)`),不要四舍五入:610 秒四舍五入是 10 分钟,看着正好卡在「10 分钟上限」上,容易被当成达标项(实际超时);向上取整显示成 11 分钟,和它真的超时这件事保持一致。距离同理,显示值永远不要比真实值更小。

## 失败与降级

| 情况 | 怎么做 |
| --- | --- |
| 某次工具调用报错 | 重试一次;仍失败就跳过这个候选,并在回答里说明「有 N 个候选因高德接口异常未能核实路线」 |
| `maps_search_detail` 拿不到坐标 | 跳过该候选,不猜坐标 |
| `maps_direction_walking` 算不出路线 | 跳过该候选,不用直线距离顶替 |
| 步行上限内一个都没有 | 如实说明「在步行 X 分钟内没有找到符合条件的地点」,并给出可放宽的方向(放宽到 Y 分钟 / 换关键词 / 换起点),不要硬塞一个超时的地点 |
| 只找到 1–2 家 | 就推荐 1–2 家,并说明「步行 X 分钟内只找到 N 家符合条件」;缺的额度不要用超时地点补上 |
| 起点无法解析 | 说明需要起点经纬度或更准确的地标名,不要用猜测坐标继续 |

## 示例

用户:「我在杭州武林路地铁站附近,想找一家咖啡馆,步行不超过 15 分钟,推荐最多 3 家,优先近一点。」

正确做法:`maps_geo` 定位起点 → `maps_around_search(keywords="咖啡馆", location=起点, radius=1800)` → 对前 5–6 个候选 `maps_search_detail` 拿坐标 → 逐个 `maps_direction_walking` → 只保留 duration ≤ 900 秒的 → 按 duration 升序取前 3 → 表格输出名称/地址/距离/时间/理由,并注明营业状态与排队情况未核实。

错误做法:直接用周边搜索返回的 POI 列表当答案(没有坐标、没有步行时间);或用直线距离换算步行分钟数(评测会用高德路线数据核对,必错)。
