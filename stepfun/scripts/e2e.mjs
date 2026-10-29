/**
 * 端到端 UI 测试:用真实浏览器走一遍
 *   加载模型 -> 导入 -> 本地向量化 -> 写入 seekdb -> 检索
 *   -> 增量导入(第二轮) -> 验证新文档立即可检索 -> 重复导入(upsert 不报错)
 * 并保存截图(用于技术说明与验收材料)。
 *
 * 用法:node scripts/e2e.mjs [--headed] [--shot reports/ui-e2e.png]
 */
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { launchBrowser, openApp, waitForApi } from "./lib/harness.mjs";

const headed = process.argv.includes("--headed");
const shotArg = process.argv.indexOf("--shot");
const shotPath = shotArg > -1 ? process.argv[shotArg + 1] : "reports/ui-e2e.png";

const health = await waitForApi();
console.log(`seekdb: ${health.mode} ${health.seekdbVersion}`);

const browser = await launchBrowser({ headless: !headed });
const page = await openApp(browser);

const countOf = async () => {
  const t = await page.textContent("#badge-db");
  const m = t.match(/(\d+)\s*篇/);
  return m ? Number(m[1]) : -1;
};

console.log("0) 清空知识库(干净起点)");
await page.click("#btn-reset");
await page.waitForTimeout(1500);

console.log("1) 载入示例语料");
await page.click("#btn-sample");
await page.waitForTimeout(300);

console.log("2) 加载模型(端侧推理)");
await page.click("#btn-load");
await page.waitForFunction(
  () => document.querySelector("#model-info")?.textContent?.includes("实际后端"),
  null,
  { timeout: 180_000 },
);
console.log("   ", (await page.textContent("#model-info")).replace(/\s+/g, " ").trim());
if (await page.isVisible("#fallback-banner"))
  console.log("    降级提示:", (await page.textContent("#fallback-banner")).trim());

console.log("3) 第一轮导入并本地向量化");
await page.click("#btn-import");
await page.waitForFunction(
  () => document.querySelector("#import-info")?.textContent?.includes("端到端导入耗时"),
  null,
  { timeout: 180_000 },
);
console.log("   ", (await page.textContent("#import-info")).replace(/\s+/g, " ").trim());
const count1 = await countOf();
console.log("    集合文档数:", count1);

console.log("4) 检索");
await page.fill("#query", "seekdb 的混合检索是怎么做的?");
await page.click("#btn-search");
await page.waitForFunction(() => document.querySelectorAll("#results li").length > 0, null, {
  timeout: 120_000,
});
console.log("   计时:", (await page.textContent("#timing")).replace(/\s+/g, " ").trim());
for (const h of await page.$$eval("#results li", (els) =>
  els.map((el) => `${el.querySelector(".rank")?.textContent?.trim()} ${el.querySelector("p")?.textContent?.trim().slice(0, 46)}`),
))
  console.log("   ", h);

console.log("5) 增量导入第二轮(验证索引刷新后新文档立即可检索)");
await page.fill(
  "#corpus",
  "## 增量导入验证\n这条内容只在第二轮导入时写入,用于验证写完刷新索引之后能立刻被检索到。\n\n## 向量库运维\n向量库的运维包括索引刷新、集合清理与增量写入。",
);
await page.click("#btn-import");
await page.waitForFunction(
  () => document.querySelector("#import-info")?.textContent?.includes("端到端导入耗时"),
  null,
  { timeout: 180_000 },
);
const count2 = await countOf();
console.log("    集合文档数:", count1, "->", count2);
if (count2 <= count1) throw new Error("增量导入后集合文档数没有增加");

await page.fill("#query", "向量库的运维包括哪些工作");
await page.click("#btn-search");
await page.waitForFunction(() => document.querySelectorAll("#results li").length > 0, null, {
  timeout: 120_000,
});
const newHit = await page.$$eval("#results li", (els) =>
  els.map((el) => el.querySelector("p")?.textContent ?? ""),
);
const found = newHit.some((t) => t.includes("索引刷新"));
console.log("    新导入内容可检索:", found ? "是" : "否");
if (!found) throw new Error("增量导入的新文档没有被检索到");

console.log("6) 重复导入同一份内容(upsert,不应报主键冲突)");
await page.fill(
  "#corpus",
  "## 增量导入验证\n这条内容只在第二轮导入时写入,用于验证写完刷新索引之后能立刻被检索到。\n\n## 向量库运维\n向量库的运维包括索引刷新、集合清理与增量写入。",
);
await page.click("#btn-import");
await page.waitForFunction(
  () => document.querySelector("#import-info")?.textContent?.includes("端到端导入耗时"),
  null,
  { timeout: 180_000 },
);
const count3 = await countOf();
console.log("    集合文档数:", count2, "->", count3, "(upsert 应保持不变)");

await mkdir(resolve(shotPath, ".."), { recursive: true });
await page.screenshot({ path: resolve(shotPath), fullPage: true });
console.log("截图:", shotPath);

await browser.close();
console.log("\nE2E OK");
