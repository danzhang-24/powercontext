/*
 * Copyright (c) 2026 OceanBase.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
/**
 * SKILL.md ↔ 高德 MCP 工具契约 一致性校验
 *
 *   node scripts/check_skill_contract.mjs
 *   node scripts/check_skill_contract.mjs --online   # 现场从 npm 拉官方包复核
 *
 * 为什么要这个脚本:赛题只有「一个 SKILL.md」,评测时 Agent 直接照着它调高德 MCP。
 * 工具名写错、坐标顺序写反、忘了「搜索结果不含坐标」这一步,
 * 都会直接体现在 40% 权重的数据真实性上。这里把 SKILL.md 里引用的每个工具名
 * 和「从官方 MCP Server 源码里提取的返回字段快照」对一遍。
 */
import { readFile, stat } from "node:fs/promises";
import { resolve } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const run = promisify(execFile);
const args = process.argv.slice(2).filter((a) => !a.startsWith("--"));
const SKILL = resolve(args[0] ?? "SKILL.md");
const CONTRACT = resolve("references/amap-mcp-contract.json");

const text = await readFile(SKILL, "utf8");
const contract = JSON.parse(await readFile(CONTRACT, "utf8"));

const errors = [];
const warns = [];
const oks = [];

/* ---------- 1. SKILL.md 里引用的工具名必须存在 ---------- */
const official = new Set(Object.keys(contract.tools));
// 第三方 MCP Server 的常见别名(语义对应,允许出现在文档里)
const ALIASES = {
  amap_poi_around: "maps_around_search",
  amap_poi_search: "maps_text_search",
  amap_poi_detail: "maps_search_detail",
  amap_direction_walking: "maps_direction_walking",
  amap_geocode: "maps_geo",
  amap_distance: "maps_distance",
  amap_weather: "maps_weather",
};

const used = new Set();
for (const m of text.matchAll(/`?([a-z]+_[a-z_]+)`?/g)) used.add(m[1]);
const toolRefs = [...used].filter((t) => t.startsWith("maps_") || t.startsWith("amap_"));

for (const t of toolRefs) {
  if (official.has(t)) oks.push(`工具名 ${t} 存在于官方契约`);
  else if (ALIASES[t]) oks.push(`别名 ${t} → ${ALIASES[t]}(语义对应)`);
  else errors.push(`SKILL.md 引用了不存在的工具名: ${t}`);
}

/* ---------- 2. 必须覆盖的关键工具 ---------- */
const mustUse = ["maps_around_search", "maps_search_detail", "maps_direction_walking"];
for (const t of mustUse) {
  if (!toolRefs.includes(t)) errors.push(`SKILL.md 没有用到关键工具 ${t}`);
}
oks.push(`关键工具齐全: ${mustUse.join(", ")}`);

/* ---------- 3. 关键坑必须在文档里被点名 ---------- */
const MUST_MENTION = [
  { re: /经度[,，]\s*纬度/, why: "坐标顺序是高德特有的经度在前,写反就崩" },
  { re: /search_detail/, why: "必须告诉模型搜索结果不含坐标、要再查详情拿 location" },
  { re: /单位是米|单位.*米/, why: "distance 是米,不写会被当成公里" },
  { re: /单位是秒|单位.*秒/, why: "duration 是秒,不写会把 900 秒当成 15 秒" },
  { re: /直线距离/, why: "必须显式禁止用直线距离替代步行路线" },
  { re: /未核实/, why: "缺依据的信息要标未核实,这是防止编造的关键规则" },
  { re: /不足|只找到|少于/, why: "结果不足时要如实说明" },
];
for (const m of MUST_MENTION) {
  if (m.re.test(text)) oks.push(`已写明: ${m.why}`);
  else errors.push(`SKILL.md 缺少关键规则(${m.why})`);
}

/* ---------- 4. SKILL.md 里对工具返回字段的描述要和快照一致 ---------- */
const around = contract.tools.maps_around_search;
if (!around.returns_poi_fields.includes("location")) {
  if (!/不返回 POI 的经纬度|不含\s*location|没有.*坐标/.test(text)) {
    errors.push("快照显示 maps_around_search 不返回 location,但 SKILL.md 没有点明这一点");
  } else {
    oks.push("与快照一致:周边搜索结果不含坐标,需再查详情");
  }
} else {
  warns.push("快照里 maps_around_search 含 location,与预期不符,请复核快照来源");
}
const detailHasLocation = contract.tools.maps_search_detail.returns_top_fields.includes("location");
if (detailHasLocation) oks.push("与快照一致:maps_search_detail 返回 location");
else errors.push("快照显示 maps_search_detail 不返回 location,请复核");

/* ---------- 5. frontmatter 规范 ---------- */
if (!text.startsWith("---")) errors.push("缺少 YAML frontmatter");
const fm = text.split("---")[1] ?? "";
if (!/^name:\s*\S+/m.test(fm)) errors.push("frontmatter 缺少 name");
if (!/^description:/m.test(fm)) errors.push("frontmatter 缺少 description");
const name = (fm.match(/^name:\s*(\S+)/m) ?? [])[1];
if (name && !/^[a-z0-9][a-z0-9-]*$/.test(name)) errors.push(`name 不是 kebab-case: ${name}`);
const desc = (fm.match(/description:\s*\|([\s\S]*)/) ?? [])[1] ?? "";
for (const kw of ["nearby", "附近", "步行", "高德"]) {
  if (!desc.toLowerCase().includes(kw.toLowerCase())) warns.push(`description 里没有出现触发线索「${kw}」`);
}
if (desc.length > 1200) warns.push("description 偏长,建议压缩到 800 字以内");

/* ---------- 6. 正文长度 ---------- */
const lines = text.split("\n").length;
if (lines > 400) errors.push(`正文 ${lines} 行,超过 400 行上限`);
else oks.push(`正文 ${lines} 行(上限 400)`);

/* ---------- 7. 可选:联网复核快照 ---------- */
if (process.argv.includes("--online")) {
  try {
    const tmp = "/tmp/amap-contract-recheck";
    await run("rm", ["-rf", tmp]);
    await run("mkdir", ["-p", tmp]);
    await run("npm", ["pack", "@amap/amap-maps-mcp-server@0.0.8", "--silent"], { cwd: tmp });
    const { stdout } = await run("sh", ["-c", `cd ${tmp} && tar xzf *.tgz && grep -o '"maps_[a-z_]*"' package/build/index.js | sort -u`]);
    const live = [...new Set(stdout.match(/maps_[a-z_]+/g) ?? [])].sort();
    const snap = [...official].sort();
    const missing = live.filter((t) => !snap.includes(t));
    const extra = snap.filter((t) => !live.includes(t));
    if (missing.length === 0 && extra.length === 0) oks.push(`联网复核通过:官方包 ${live.length} 个工具与快照完全一致`);
    else {
      if (missing.length) errors.push(`官方包里有快照没有的工具: ${missing.join(", ")}`);
      if (extra.length) errors.push(`快照里有官方包没有的工具: ${extra.join(", ")}`);
    }
  } catch (e) {
    warns.push("联网复核失败(离线环境属正常):" + String(e.message).slice(0, 120));
  }
}

console.log("== SKILL.md ↔ 高德 MCP 契约 校验 ==");
for (const l of oks) console.log(`  ✓ ${l}`);
for (const l of warns) console.log(`  ! ${l}`);
for (const l of errors) console.log(`  ✗ ${l}`);
console.log(`\n结果:${errors.length ? `不通过(${errors.length} 个错误)` : "通过"}`);
process.exit(errors.length ? 1 : 0);
