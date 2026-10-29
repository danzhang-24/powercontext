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
 * 高德 MCP Server 的本地模拟器(开发/评测用,不是交付物的一部分)
 *
 *   node scripts/mock_amap_cli.mjs maps_around_search '{"location":"120.1657,30.2766","keywords":"咖啡馆","radius":"1800"}'
 *   node scripts/mock_amap_cli.mjs maps_search_detail '{"id":"B0FFH1"}'
 *   node scripts/mock_amap_cli.mjs maps_direction_walking '{"origin":"120.1657,30.2766","destination":"120.1613,30.2759"}'
 *
 * 为什么要它:手上没有高德 API Key,但 SKILL.md 里最关键的一条规则是
 * 「周边搜索结果里没有坐标,必须再查一次详情」——这条规则靠肉眼看文档是验不出来的,
 * 得让另一个 Agent 真的按 SKILL.md 跑一遍,看它会不会漏这一步。
 *
 * 返回结构刻意与官方 @amap/amap-maps-mcp-server 对齐:
 *   - 周边/关键词搜索的 POI 只有 id/name/address/typecode/photos,**没有 location**
 *   - 详情查询才返回 location / type / biz_ext
 *   - 步行规划返回 route.paths[0].distance(米)、duration(秒)
 */
import { resolve, dirname } from "node:path";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const MOCK = JSON.parse(await readFile(resolve(HERE, "../references/mock-amap-data.json"), "utf8"));
const [tool, argsRaw] = process.argv.slice(2);
if (!tool) {
  console.error(`用法: node scripts/mock_amap_cli.mjs <tool> <json-args>
可用工具: ${Object.keys(MOCK.tools).join(", ")}`);
  process.exit(2);
}
const args = argsRaw ? JSON.parse(argsRaw) : {};
const src = MOCK.tools[tool];
if (!src) {
  console.error(`未知工具: ${tool}`);
  process.exit(2);
}
// JSON 里存的是函数体源码,这里现编成函数(MOCK 作为闭包变量传入)
const fn = new Function("MOCK", `return (${src});`)(MOCK);
const out = fn(args);
process.stdout.write(typeof out === "string" ? out : JSON.stringify(out, null, 2));
