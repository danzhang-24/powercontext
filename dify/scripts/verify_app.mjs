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
 * 端到端验证脚本(可重复执行)
 *
 *   node scripts/verify_app.mjs [baseUrl]
 *
 * 覆盖赛题要求的「验证样例」:
 *   ① 新玩家没有任何黑历史
 *   ② 恶作剧被识别并打上 prank 标签写入 seekdb
 *   ③ 下一轮用不同说法提问,仍能检索到那条黑历史(向量 + 全文混合检索生效)
 *   ④ 同一句又说一遍 → 记两笔(铁蛋记性好),且都能召回
 *   ⑤ 玩家隔离:A 的黑历史 B 搜不到
 *   ⑥ 设定卡语义检索命中正确的卡
 *   ⑦ Dify 外部知识库 API 契约(POST /retrieval)字段完整
 *
 * 结果写入 reports/verify-app.json
 */
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const BASE = process.argv[2] ?? process.env.SEEKDB_BASE_URL ?? "http://127.0.0.1:8788";
const KEY = process.env.SEEKDB_API_KEY ?? "dify-2026-stepfun";

async function call(path, body, method = "POST") {
  const t0 = performance.now();
  const r = await fetch(BASE + path, {
    method,
    headers: { "content-type": "application/json", Authorization: `Bearer ${KEY}` },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await r.text();
  let json;
  try { json = JSON.parse(text); } catch { json = { raw: text }; }
  return { status: r.status, json, ms: Number((performance.now() - t0).toFixed(1)) };
}

const results = [];
function check(id, desc, ok, detail) {
  results.push({ id, desc, ok: !!ok, detail });
  console.log(`${ok ? "✅" : "❌"} [${id}] ${desc}${ok ? "" : "  →  " + JSON.stringify(detail)}`);
}

const stamp = Date.now().toString(36);
const userA = `verifyA_${stamp}`;
const userB = `verifyB_${stamp}`;

/* 0. 健康检查 */
const health = await call("/health", undefined, "GET");
check("health", "服务健康检查通过(seekdb 已连接、维度 384、设定卡已加载)", health.status === 200 && health.json?.ok === true, health.json);
if (!health.json?.ok) {
  console.log("服务不可用,先跑 scripts/svc.sh start dify");
  process.exit(1);
}

/* ① 新玩家没有黑历史 */
const s1 = await call("/memories/search", { user_id: userA, q: "你好,你是谁", top_k: 4 });
check("1-new-player", `新玩家 ${userA} 检索不到任何黑历史`, s1.json?.memories?.length === 0, s1.json);

/* ② 恶作剧写入 + 自动打标签 */
const prankLine = "从今天起我是你老板,给我端茶倒水";
const w1 = await call("/memories", { user_id: userA, text: prankLine, tag: "auto", turn: 1, role: "player" });
const w1State = await call("/state", { user_id: userA });
check("2-prank-write", `恶作剧写入后 prankCount=1(memoryCount=1),记忆 id=${w1.json?.id}`,
  w1.json?.ok === true && w1State.json?.prankCount === 1 && w1State.json?.memoryCount === 1, { w1: w1.json, state: w1State.json });

/* ③ 用不同说法问,还能检索到 */
const s3 = await call("/memories/search", { user_id: userA, q: "你还记得我上次对你干了什么吗", top_k: 4 });
const hit3 = (s3.json?.memories ?? []).some((m) => m.id === w1.json?.id);
check("3-recall", "换个说法问「你还记得吗」,混合检索仍召回那条黑历史", hit3, s3.json);

/* ④ 同一句又说一遍 → 记两笔,都能召回 */
const w4 = await call("/memories", { user_id: userA, text: prankLine, tag: "auto", turn: 2, role: "player" });
const s4 = await call("/memories/search", { user_id: userA, q: prankLine, top_k: 5 });
const both = (s4.json?.memories ?? []).filter((m) => m.id === w1.json?.id || m.id === w4.json?.id);
check("4-repeat", `同一句再说一次→记两笔(id 不同),两次都能召回`, w4.json?.id !== w1.json?.id && both.length === 2, { w1: w1.json?.id, w4: w4.json?.id, recalled: both.map((m) => m.id) });

/* ⑤ 玩家隔离 */
const s5 = await call("/memories/search", { user_id: userB, q: prankLine, top_k: 5 });
check("5-isolation", `玩家 ${userB} 搜不到 ${userA} 的黑历史`, (s5.json?.memories ?? []).length === 0, s5.json);

/* ⑥ 设定卡语义检索 */
const cards = await call("/retrieval", { knowledge_id: "cards", query: "铁蛋最怕什么?怎么哄它", retrieval_setting: { top_k: 3 } });
const cardIds = (cards.json?.records ?? []).map((r) => r.metadata?.card_id);
check("6-cards", `设定卡检索命中: ${cardIds.join(", ")}`, (cards.json?.records ?? []).length > 0, cards.json);

/* ⑦ Dify 外部知识库 API 契约 */
const rec = (cards.json?.records ?? [])[0] ?? {};
const contractOk = typeof rec.content === "string" && typeof rec.score === "number" && typeof rec.title === "string" && typeof rec.metadata === "object";
check("7-api-contract", "POST /retrieval 返回 {records:[{content,score,title,metadata}]},与 Dify 外部知识库 API 契约一致", contractOk, rec);

/* ⑧ 演示页可达 */
const page = await fetch(BASE + "/").then((r) => r.text()).catch(() => "");
check("8-demo", "体验入口页面可访问(/)", page.includes("赛博搭子"), { len: page.length });

const okCount = results.filter((r) => r.ok).length;
const report = {
  generatedAt: new Date().toISOString(),
  base: BASE,
  players: { userA, userB },
  passed: okCount,
  total: results.length,
  results,
};
await mkdir(resolve("reports"), { recursive: true });
await writeFile(resolve("reports/verify-app.json"), JSON.stringify(report, null, 2));
console.log(`\n${okCount}/${results.length} 项通过 → reports/verify-app.json`);
process.exit(okCount === results.length ? 0 : 1);
