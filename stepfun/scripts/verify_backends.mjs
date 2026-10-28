/**
 * 两路后端一致性验证:WASM vs WebGPU
 *
 * 同一模型、同一批文本,分别在两个后端上跑端侧推理,比较:
 *   1) 向量的最大绝对偏差 / 平均余弦相似度
 *   2) 用两路向量分别写入 seekdb 并检索,排序结果是否一致
 *
 * 目的:证明「WebGPU 这条路」不只是能跑,而是算出了和 WASM 等价的向量。
 *
 * 用法:
 *   WEBGPU=1 node scripts/verify_backends.mjs
 */
import { writeFile, mkdir } from "node:fs/promises";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { launchBrowser, openApp, waitForApi, loadModel, embed, apiPost } from "./lib/harness.mjs";

const DTYPE = process.env.DTYPE ?? "q8";
const health = await waitForApi();
const corpus = await (await fetch("http://127.0.0.1:8787/corpus.json")).json();
const evalSet = JSON.parse(await readFile(resolve("data/eval-queries.json"), "utf8"));

const texts = corpus.map((d) => `${d.title}。${d.text}`);

const browser = await launchBrowser();

async function runBackend(preferWebGPU) {
  const page = await openApp(browser);
  const info = await loadModel(page, DTYPE, preferWebGPU);
  const { vecs, ms } = await embed(page, texts, 16);
  console.log(
    `  ${info.backend.padEnd(7)} 加载=${info.loadMs.toFixed(0)}ms 向量化(12篇)=${ms.toFixed(0)}ms` +
      `${info.fellBack ? ` [降级:${info.reason}]` : ""}`,
  );
  return { backend: info.backend, fellBack: info.fellBack, reason: info.reason ?? null, vecs, ms };
}

console.log(`模型精度=${DTYPE}  seekdb=${health.seekdbVersion}`);
console.log("跑 WASM:");
const wasm = await runBackend(false);
console.log("跑 WebGPU:");
const webgpu = await runBackend(true);

const diffs = wasm.vecs.map((v, i) => {
  let maxAbs = 0;
  let dot = 0;
  let n1 = 0;
  let n2 = 0;
  for (let j = 0; j < v.length; j++) {
    maxAbs = Math.max(maxAbs, Math.abs(v[j] - webgpu.vecs[i][j]));
    dot += v[j] * webgpu.vecs[i][j];
    n1 += v[j] * v[j];
    n2 += webgpu.vecs[i][j] * webgpu.vecs[i][j];
  }
  return { maxAbs, cosine: dot / (Math.sqrt(n1) * Math.sqrt(n2)) };
});

const avgCos = diffs.reduce((a, d) => a + d.cosine, 0) / diffs.length;
const maxAbs = Math.max(...diffs.map((d) => d.maxAbs));
console.log(`\n向量一致性: 平均余弦相似度=${avgCos.toFixed(6)}  最大绝对偏差=${maxAbs.toExponential(2)}`);

/* 用两路向量分别入库检索,比较 Top-K 排序 */
async function topK(vecs) {
  await apiPost("/api/reset");
  await apiPost("/api/documents", {
    documents: corpus.map((d, i) => ({ id: `cmp-${i}`, text: `${d.title}。${d.text}`, metadata: { title: d.title } })),
    embeddings: vecs,
  });
  const out = [];
  for (const item of evalSet.slice(0, 8)) {
    const res = await apiPost("/api/search", {
      queryEmbedding: vecs[0],
      queryText: item.query,
      keywords: [],
      nResults: 5,
    });
    out.push(res.results.map((r) => r.id));
  }
  return out;
}

const topWasm = await topK(wasm.vecs);
const topWebgpu = await topK(webgpu.vecs);
const same = JSON.stringify(topWasm) === JSON.stringify(topWebgpu);
console.log(`检索排序一致性(8 条查询 × Top5): ${same ? "完全一致" : "存在差异"}`);

const report = {
  dtype: DTYPE,
  wasm: { backend: wasm.backend, fellBack: wasm.fellBack, embedMs: wasm.ms },
  webgpu: { backend: webgpu.backend, fellBack: webgpu.fellBack, reason: webgpu.reason, embedMs: webgpu.ms },
  vectorConsistency: {
    avgCosine: +avgCos.toFixed(6),
    maxAbsDiff: maxAbs,
    minCosine: +Math.min(...diffs.map((d) => d.cosine)).toFixed(6),
  },
  rankingIdentical: same,
  topK: { wasm: topWasm, webgpu: topWebgpu },
};
await browser.close();
await mkdir(resolve("reports"), { recursive: true });
await writeFile(resolve("reports/backend-consistency.json"), JSON.stringify(report, null, 2));
console.log("报告已写入 reports/backend-consistency.json");
