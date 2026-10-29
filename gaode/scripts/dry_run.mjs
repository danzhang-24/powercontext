/**
 * SKILL.md 里那套筛选规则的离线演练(不需要高德 Key)
 *
 *   node scripts/dry_run.mjs
 *
 * 目的:把 SKILL.md 写下的规则真正跑一遍,确认它们互相不打架、单位换算没错、
 *      硬条件不会被「凑够 3 家」破坏、降级路径真的会触发。
 *
 * 用的是内置的 mock 高德返回(字段结构与官方 MCP Server 一致:
 * 周边搜索结果里没有 location,必须再查详情才有坐标)。
 */
import { resolve } from "node:path";
import { readFile } from "node:fs/promises";

/* ----------------------------- mock 的高德返回 ----------------------------- */

// 起点:杭州武林路地铁站(经度,纬度)
const ORIGIN = { lng: 120.1657, lat: 30.2766 };

// maps_around_search 的返回:注意没有 location 字段(与官方一致)
const AROUND_POIS = [
  { id: "B0FFH1", name: "蓝瓶咖啡(武林店)", address: "杭州市下城区延安路 511 号武林银泰 B1", typecode: "050000" },
  { id: "B0FFH2", name: "星巴克臻选(凤起路店)", address: "杭州市拱墅区凤起路 62 号", typecode: "050000" },
  { id: "B0FFH3", name: "漫咖啡(西湖银泰店)", address: "杭州市下城区延安路 258 号", typecode: "050000" },
  { id: "B0FFH4", name: "Manner Coffee(武林路店)", address: "杭州市拱墅区武林路 100 号", typecode: "050000" },
  { id: "B0FFH5", name: "麦咖啡(杭州大厦店)", address: "杭州市下城区武林广场 1 号", typecode: "050000" },
  { id: "B0FFH6", name: "Seesaw Coffee(嘉里中心店)", address: "杭州市下城区延安路 385 号嘉里中心 2F", typecode: "050000" },
];

// maps_search_detail 的返回:这里才有 location
const DETAILS = {
  B0FFH1: { location: "120.1613,30.2759", type: "餐饮服务;咖啡厅", biz_ext: { rating: "4.6", cost: "48" } },
  B0FFH2: { location: "120.1692,30.2745", type: "餐饮服务;咖啡厅", biz_ext: { rating: "4.4", cost: "42" } },
  B0FFH3: { location: "120.1606,30.2709", type: "餐饮服务;咖啡厅", biz_ext: { rating: "4.2", cost: "68" } },
  B0FFH4: { location: "120.1665,30.2772", type: "餐饮服务;咖啡厅", biz_ext: { rating: "4.7", cost: "22" } },
  B0FFH5: { location: "120.1648,30.2742", type: "餐饮服务;咖啡厅", biz_ext: { rating: "4.1", cost: "35" } },
  B0FFH6: { location: "120.1635,30.2762", type: "餐饮服务;咖啡厅", biz_ext: { rating: "4.5", cost: "55" } },
};

// maps_direction_walking 的返回:distance 米,duration 秒
const WALKING = {
  B0FFH1: { distance: 1120, duration: 720, steps: [{ instruction: "沿延安路向北约 800 米,右转进入武林路" }] },
  B0FFH2: { distance: 1450, duration: 890, steps: [{ instruction: "沿凤起路向北约 900 米,再向北步行 400 米" }] },
  B0FFH3: { distance: 2100, duration: 1280, steps: [{ instruction: "沿延安路向北约 1.9 公里" }] },
  B0FFH4: { distance: 680, duration: 460, steps: [{ instruction: "沿武林路向北约 500 米,右转" }] },
  B0FFH5: { distance: 1600, duration: 980, steps: [{ instruction: "沿武林广场向北步行约 1.4 公里" }] },
  B0FFH6: { distance: 950, duration: 610, steps: [{ instruction: "沿延安路向南约 700 米,进入嘉里中心" }] },
};

/* --------------------------- SKILL.md 里的规则实现 --------------------------- */

const WALK_SPEED_M_PER_MIN = 80; // 步速
const RADIUS_FACTOR = 1.5; // 路网绕行余量

/** 步骤 1:半径换算 */
function searchRadius(minutes) {
  return Math.round(minutes * WALK_SPEED_M_PER_MIN * RADIUS_FACTOR);
}

/** 步骤 2:候选(半径只作初筛,这里 mock 数据直接给出全部候选) */
function aroundSearch() {
  return AROUND_POIS.map((p) => ({ ...p }));
}

/** 步骤 3:补坐标 —— 必须查详情,周边搜索结果里没有 */
function searchDetail(id) {
  const d = DETAILS[id];
  if (!d) throw new Error(`maps_search_detail failed: ${id}`);
  return d;
}

/** 步骤 4:算步行 —— 距离米、时间秒 */
function directionWalking(id) {
  const w = WALKING[id];
  if (!w) throw new Error(`maps_direction_walking failed: ${id}`);
  return w;
}

const haversine = (a, b) => {
  const R = 6371000, rad = (x) => (x * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
};

/**
 * 完整流程
 * @param {{minutes:number, count:number, prefer?:'near'|'rating'}} req
 */
function recommend(req) {
  const { minutes, count = 3, prefer = "near" } = req;
  const radius = searchRadius(minutes);

  // 候选粗排:先补坐标,再按直线距离排,只对最近的 6 个查步行路线(省配额)
  const cands = aroundSearch()
    .map((p) => ({ ...p, detail: searchDetail(p.id) }))
    .map((p) => {
      const [lng, lat] = p.detail.location.split(",").map(Number);
      return { ...p, straightMeters: haversine(ORIGIN, { lng, lat }) };
    })
    .sort((a, b) => a.straightMeters - b.straightMeters)
    .slice(0, 6);

  // 逐个算真实步行路线
  const withRoute = cands.map((c) => {
    const route = directionWalking(c.id);
    return { ...c, route, durationSec: route.duration, distanceMeters: route.distance };
  });

  // 硬过滤:超出步行上限的一律不算符合条件
  const limit = minutes * 60;
  const ok = withRoute.filter((c) => c.durationSec <= limit);
  const rejected = withRoute.filter((c) => c.durationSec > limit);

  // 排序
  const sorted =
    prefer === "rating"
      ? [...ok].sort(
          (a, b) =>
            Number(b.detail.biz_ext?.rating ?? 0) - Number(a.detail.biz_ext?.rating ?? 0) ||
            a.durationSec - b.durationSec,
        )
      : [...ok].sort((a, b) => a.durationSec - b.durationSec);

  const picked = sorted.slice(0, Math.min(count, 3));

  return { radius, limit, picked, rejected, okCount: ok.length };
}

/* ------------------------------- 输出格式化 ------------------------------- */

const fmtKm = (m) => `${(m / 1000).toFixed(1)} 公里`;
// 分钟一律向上取整:610 秒四舍五入是 10 分钟,看着像达标项,实际超时
const fmtMin = (s) => `${Math.ceil(s / 60)} 分钟`;

function render(req, res) {
  const lines = [];
  lines.push(
    `按你的要求(步行 ≤ ${req.minutes} 分钟,最多 ${req.count} 家${req.prefer === "rating" ? ",评分优先" : ",近优先"}),推荐:`,
  );
  res.picked.forEach((c, i) => {
    lines.push(
      `${i + 1}. ${c.name}`,
      `   地址:${c.address}`,
      `   步行:约 ${fmtKm(c.distanceMeters)},约 ${fmtMin(c.durationSec)}`,
      `   推荐理由:${c.route.steps[0].instruction};类型为${c.detail.type.split(";")[1] ?? c.detail.type},人均 ${c.detail.biz_ext?.cost ?? "未核实"} 元(高德标注)`,
    );
  });
  if (res.picked.length < req.count) {
    lines.push(
      `步行 ${req.minutes} 分钟内只找到 ${res.picked.length} 家符合条件的地点` +
        (res.rejected.length ? `(另有 ${res.rejected.length} 家在 ${res.rejected.map((r) => fmtMin(r.durationSec)).join("、")},超出你要求的上限)` : "") +
        `,建议把步行上限放宽到 ${Math.ceil(res.rejected.reduce((m, r) => Math.max(m, r.durationSec), 0) / 60) || req.minutes + 5} 分钟。`,
    );
  }
  lines.push("说明:营业状态与排队情况未核实(高德接口未返回该字段)。");
  return lines.join("\n");
}

/* --------------------------------- 断言 --------------------------------- */

const results = [];
const check = (id, desc, ok, detail) => {
  results.push({ id, desc, ok: !!ok, detail });
  console.log(`${ok ? "✅" : "❌"} [${id}] ${desc}${ok ? "" : "  → " + JSON.stringify(detail)}`);
};

const r15 = recommend({ minutes: 15, count: 3 });
check("radius", "15 分钟 → 搜索半径 1800 米(80 m/min × 1.5)", searchRadius(15) === 1800, searchRadius(15));
check("hard-filter", "超过 15 分钟的候选被硬过滤掉(漫咖啡 1280s、麦咖啡 980s)",
  !r15.picked.some((c) => c.durationSec > 900) && r15.rejected.length === 2, r15.picked.map((c) => c.durationSec));
check("sort-near", "「优先近一点」→ 按步行时间升序", r15.picked.map((c) => c.durationSec).join() === "460,610,720", r15.picked.map((c) => [c.name, c.durationSec]));
check("count-cap", "最多返回 3 家", r15.picked.length === 3, r15.picked.length);
check("units", "单位换算:1120 米 → 1.1 公里;720 秒 → 12 分钟",
  fmtKm(1120) === "1.1 公里" && fmtMin(720) === "12 分钟", [fmtKm(1120), fmtMin(720)]);
check("ceil-not-round", "分钟向上取整:610 秒 → 11 分钟(不是 10 分钟,否则看着像达标)",
  fmtMin(610) === "11 分钟" && Math.round(610 / 60) === 10, [fmtMin(610), `${Math.round(610 / 60)} 分钟(四舍五入会错)`]);
check("from-route", "距离/时间取自路线查询,不是周边搜索的直线距离",
  r15.picked.every((c) => c.distanceMeters === WALKING[c.id].distance && c.durationSec === WALKING[c.id].duration),
  r15.picked.map((c) => c.id));

const r10 = recommend({ minutes: 10, count: 3 });
// 10 分钟 = 600 秒:只有 Manner(460s) 达标,Seesaw 610s / 蓝瓶 720s 都要被挡掉
check("insufficient", "10 分钟只够 1 家(610s 的 Seesaw 也被挡掉)→ 返回 1 家",
  r10.picked.length === 1 && r10.picked[0].durationSec === 460 && r10.rejected.length === 5,
  { picked: r10.picked.map((c) => c.durationSec), rejected: r10.rejected.map((c) => c.durationSec) });
check("insufficient-text", "输出里如实说明「只找到 1 家」并给出放宽建议",
  /只找到 1 家/.test(render({ minutes: 10, count: 3 }, r10)) &&
    /放宽/.test(render({ minutes: 10, count: 3 }, r10)),
  render({ minutes: 10, count: 3 }, r10).split("\n").slice(-2).join(" | "));
check("no-timeout-leak", "被过滤的超时地点不出现在推荐正文里",
  !render({ minutes: 10, count: 3 }, r10).includes("Seesaw"), render({ minutes: 10, count: 3 }, r10));
check("borderline", "边界值:610 秒在 10 分钟上限(600 秒)外,必须被挡掉",
  !r10.picked.some((c) => c.id === "B0FFH6") && r10.rejected.some((c) => c.id === "B0FFH6"),
  { picked: r10.picked.map((c) => c.id), rejected: r10.rejected.map((c) => c.id) });

const r3 = recommend({ minutes: 3, count: 3 });
check("empty", "3 分钟内一家都没有 → 不硬塞,返回 0 条", r3.picked.length === 0, r3.picked.length);
check("empty-text", "输出里说明没有找到并给出放宽建议",
  /没有|只找到 0 家/.test(render({ minutes: 3, count: 3 }, r3)), render({ minutes: 3, count: 3 }, r3).split("\n").pop());

const rRating = recommend({ minutes: 20, count: 3, prefer: "rating" });
check("prefer-rating", "「评分优先」→ 按高德评分降序,同分再按时间",
  rRating.picked[0].detail.biz_ext.rating === "4.7", rRating.picked.map((c) => c.detail.biz_ext.rating));

console.log("\n--- 示例渲染(15 分钟 / 近优先)---");
console.log(render({ minutes: 15, count: 3 }, r15));

const ok = results.filter((r) => r.ok).length;
console.log(`\n${ok}/${results.length} 项通过`);
process.exit(ok === results.length ? 0 : 1);
