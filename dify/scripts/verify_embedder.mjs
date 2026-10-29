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
 * 交叉校验:纯 Node 的 WordPiece+ORT-WASM embedding vs 浏览器里 Transformers.js 的结果
 *
 * 目的:证明 service/src/embedder.mjs(无浏览器、无原生依赖)的分词与推理
 *       和 Transformers.js 官方管线产出的向量一致。
 *
 * 用法:
 *   node scripts/verify_embedder.mjs
 * 依赖:
 *   - 浏览器侧:已构建并运行的 stepfun 应用(默认 http://127.0.0.1:8787)
 *   - 模型目录:SEEKDB_EMBED_MODEL_DIR / ORT 目录:SEEKDB_EMBED_ORT_DIR
 */
import { writeFile, mkdir, stat } from "node:fs/promises";
import { resolve } from "node:path";
import { chromium } from "playwright";
import { Embedder } from "../service/src/embedder.mjs";

const APP_URL = process.env.APP_URL ?? "http://127.0.0.1:8787/";
const exists = async (p) => { try { return (await stat(p)).isDirectory(); } catch { return false; } };
// 模型目录:优先用本项目的 assets(setup 脚本拉过),否则复用同仓库 stepfun 项目的
const MODEL_CANDIDATES = [
  process.env.SEEKDB_EMBED_MODEL_DIR,
  resolve("assets/models/Xenova/all-MiniLM-L6-v2"),
  resolve("../stepfun/web/public/models/Xenova/all-MiniLM-L6-v2"),
].filter(Boolean);
let MODEL_DIR = MODEL_CANDIDATES[0];
for (const c of MODEL_CANDIDATES) { if (await exists(c)) { MODEL_DIR = c; break; } }
const ORT_CANDIDATES = [
  process.env.SEEKDB_EMBED_ORT_DIR,
  resolve("assets/ort"),
  resolve("../stepfun/web/public/ort"),
].filter(Boolean);
let ORT_DIR = ORT_CANDIDATES[0];
for (const c of ORT_CANDIDATES) { if (await exists(c)) { ORT_DIR = c; break; } }
const ONNX_FILE = process.env.EMBED_ONNX_FILE ?? "model_quantized.onnx";

const TEXTS = [
  "赛博混合检索",
  "浏览器里的 AI 推理",
  "混合检索把全文检索与向量检索通过 RRF 融合,提升召回质量。",
  "铁蛋你这个铁皮,还记得我上次骗你说你是我老板吗?",
  "INT8 量化把模型权重从 32 位浮点压缩成 8 位整数",
  "hello world",
  "海豹在冲浪时被海浪拍飞",
];

function cosine(a, b) {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}
function maxAbsDiff(a, b) {
  let m = 0;
  for (let i = 0; i < a.length; i++) m = Math.max(m, Math.abs(a[i] - b[i]));
  return m;
}

console.log("== Node 侧(WordPiece + onnxruntime-web WASM)==");
const t0 = Date.now();
const emb = new Embedder({ modelDir: MODEL_DIR, onnxFile: ONNX_FILE, ortDir: ORT_DIR });
await emb.init();
console.log(`   模型就绪 ${Date.now() - t0} ms, 维度 ${emb.dim}`);
const t1 = Date.now();
const nodeVecs = await emb.embed(TEXTS);
console.log(`   ${TEXTS.length} 条向量化 ${Date.now() - t1} ms`);

console.log("== 浏览器侧(Transformers.js,浏览器 WebGPU/WASM 运行时)==");
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROMIUM_PATH ?? "/usr/bin/chromium",
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage();
await page.goto(APP_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => !!window.__kb, null, { timeout: 30_000 });
await page.evaluate(async () => {
  await window.__kb.loadModel("q8", false); // 用 WASM 后端做同口径对比
});
const { vecs: browserVecs } = await page.evaluate(
  async (texts) => window.__kb.embedTimed(texts, 16),
  TEXTS,
);
await browser.close();

const rows = TEXTS.map((t, i) => ({
  text: t,
  cosine: +cosine(nodeVecs[i], browserVecs[i]).toFixed(8),
  maxAbsDiff: maxAbsDiff(nodeVecs[i], browserVecs[i]),
}));
console.log("\n== 逐条比对 ==");
for (const r of rows) {
  console.log(`   cos=${r.cosine.toFixed(8)}  maxdiff=${r.maxAbsDiff.toExponential(2)}  ${r.text.slice(0, 24)}`);
}
const minCos = Math.min(...rows.map((r) => r.cosine));
const maxDiff = Math.max(...rows.map((r) => r.maxAbsDiff));
console.log(`\n最小余弦 = ${minCos.toFixed(8)} | 最大绝对偏差 = ${maxDiff.toExponential(2)}`);
const pass = minCos > 0.999 && maxDiff < 0.05;
console.log(pass ? "✅ 交叉校验通过(Node 与 Transformers.js 向量一致)" : "❌ 交叉校验未通过");

await mkdir(resolve("reports"), { recursive: true });
await writeFile(
  resolve("reports/embedder-parity.json"),
  JSON.stringify(
    {
      modelDir: MODEL_DIR,
      onnxFile: ONNX_FILE,
      dim: emb.dim,
      minCosine: minCos,
      maxAbsDiff: maxDiff,
      rows,
      nodeVectors: nodeVecs,
      browserVectors: browserVecs,
    },
    null,
    2,
  ),
);
console.log("报告已写入 reports/embedder-parity.json");
process.exit(pass ? 0 : 1);
