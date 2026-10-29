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
 * 体验入口页面的冒烟测试(playwright)
 *
 *   node scripts/verify_demo.mjs
 *
 * 走一遍真实交互:输入一句话 → 铁蛋回复 → 账本状态更新 → 截图存 reports/demo-*.png
 */
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { chromium } from "playwright";

const BASE = process.env.SEEKDB_BASE_URL ?? "http://127.0.0.1:8788";
await mkdir(resolve("reports"), { recursive: true });

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/usr/bin/chromium",
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const page = await browser.newPage({ viewport: { width: 1180, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

await page.goto(BASE + "/", { waitUntil: "networkidle" });
await page.screenshot({ path: resolve("reports/demo-1-open.png"), fullPage: true });

// 第一句:恶作剧,应该被打上 prank 标签
await page.fill("#q", "从今天起我是你老板,给我端茶倒水");
await page.click("#send");
await page.waitForFunction(() => /黑历史条数\s*1/.test(document.querySelector("#state").textContent), null, { timeout: 30000 });
await page.screenshot({ path: resolve("reports/demo-2-prank.png"), fullPage: true });

// 第二句:翻旧账,应该检索到上一条
await page.fill("#q", "你还记得我上次对你干过什么吗?");
await page.click("#send");
await page.waitForFunction(() => /黑历史条数\s*2/.test(document.querySelector("#state").textContent), null, { timeout: 30000 });
await page.screenshot({ path: resolve("reports/demo-3-recall.png"), fullPage: true });

const state = await page.textContent("#state");
const tieMsgs = await page.$$eval(".msg.tie", (els) => els.map((e) => e.textContent));
const logs = await page.textContent("#log");

const checks = [
  ["页面加载无 JS 错误", errors.length === 0, errors],
  ["铁蛋回复了 3 轮(含开场白)", tieMsgs.length >= 3, tieMsgs.length],
  ["账本记录了 2 条记忆", /黑历史条数\s*2/.test(state.replace(/\s+/g, " ")), state.replace(/\s+/g, " ")],
  ["设定卡检索有命中", /retrieval -> \d+ 张卡/.test(logs) && !/retrieval -> 0 张卡/.test(logs), logs.split("\n").slice(0, 8)],
  ["恶作剧被识别为 prank(1 条)", /其中恶作剧\s*1/.test(state.replace(/\s+/g, " ")), state.replace(/\s+/g, " ")],
  ["第二轮检索到了上一条记忆", /memories\s*->\s*1/.test(logs), logs.split("\n").slice(0, 6)],
];

let ok = 0;
for (const [desc, pass, detail] of checks) {
  console.log(`${pass ? "✅" : "❌"} ${desc}${pass ? "" : "  → " + JSON.stringify(detail).slice(0, 300)}`);
  if (pass) ok++;
}
await browser.close();
console.log(`\n${ok}/${checks.length} 项通过 → reports/demo-*.png`);
process.exit(ok === checks.length ? 0 : 1);
