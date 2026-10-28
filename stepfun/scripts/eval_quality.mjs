/**
 * 检索质量评测:量化前(FP32)vs 量化后(FP16 / INT8),并对比「混合检索」与「纯向量检索」
 *
 * 指标:
 *   Recall@K = 命中文档数 / 相关文档总数
 *   nDCG@K   = DCG@K / IDCG@K
 *
 * 评测集:data/eval-queries.json(查询 -> 相关文档标题)
 * 语料  :web/public/corpus.json(同一份语料、同一套查询,唯一变量是模型精度)
 *
 * 用法:node scripts/eval_quality.mjs
 */
import { writeFile, mkdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  launchBrowser,
  openApp,
  waitForApi,
  loadModel,
  embed,
  embedQuery,
  keywords,
  apiPost,
} from "./lib/harness.mjs";

const DTYPES = (process.env.DTYPES ?? "fp32,fp16,q8").split(",");
const K = Number(process.env.K ?? 5);

const health = await waitForApi();
const corpus = await (await fetch("http://127.0.0.1:8787/corpus.json")).json();
const evalSet = JSON.parse(await readFile(resolve("data/eval-queries.json"), "utf8"));

const docs = corpus.map((d, i) => ({
  id: `eval-${i}`,
  text: `${d.title}。${d.text}`,
  metadata: { title: d.title },
}));
const titleOf = new Map(docs.map((d) => [d.id, d.metadata.title]));

function recallAtK(rankedIds, relevantTitles, k) {
  const top = rankedIds.slice(0, k).map((id) => titleOf.get(id));
  const hit = top.filter((t) => relevantTitles.includes(t)).length;
  return hit / relevantTitles.length;
}

function ndcgAtK(rankedIds, relevantTitles, k) {
  const top = rankedIds.slice(0, k).map((id) => titleOf.get(id));
  const dcg = top
    .map((t) => (relevantTitles.includes(t) ? 1 : 0))
    .reduce((acc, g, i) => acc + g / Math.log2(i + 2), 0);
  const ideal = Array.from({ length: Math.min(k, relevantTitles.length) }, (_, i) => 1).reduce(
    (acc, g, i) => acc + g / Math.log2(i + 2),
    0,
  );
  return ideal > 0 ? dcg / ideal : 0;
}

const avg = (a) => +(a.reduce((x, y) => x + y, 0) / a.length).toFixed(4);

const browser = await launchBrowser();
const page = await openApp(browser);

const report = {
  k: K,
  corpusSize: docs.length,
  queryCount: evalSet.length,
  fulltextMode: process.env.SEEKDB_FT_MODE ?? "keywords",
  seekdb: { version: health.seekdbVersion, mode: health.mode, collection: health.collection },
  runs: [],
};

for (const dtype of DTYPES) {
  await apiPost("/api/reset");
  const info = await loadModel(page, dtype, process.env.BACKEND === "webgpu");

  const { vecs } = await embed(page, docs.map((d) => d.text), 16);
  await apiPost("/api/documents", {
    documents: docs.map((d) => ({ id: d.id, text: d.text, metadata: d.metadata })),
    embeddings: vecs,
  });

  const hybridR = [];
  const hybridN = [];
  const vectorR = [];
  const vectorN = [];
  const details = [];

  for (const item of evalSet) {
    const { vecs: qv } = await embedQuery(page, item.query);
    const kw = await keywords(page, item.query);

    // 混合检索:向量分支 + 全文分支,RRF 在 seekdb 内融合
    const hyb = await apiPost("/api/search", {
      queryEmbedding: qv[0],
      queryText: item.query,
      keywords: kw,
      nResults: K,
    });
    const hybIds = hyb.results.map((r) => r.id);

    // 纯向量检索:不带全文分支,作为对照组
    const vecOnly = await apiPost("/api/search", {
      queryEmbedding: qv[0],
      queryText: "",
      keywords: [],
      nResults: K,
    });
    const vecIds = vecOnly.results.map((r) => r.id);

    const hr = recallAtK(hybIds, item.relevant, K);
    const hn = ndcgAtK(hybIds, item.relevant, K);
    const vr = recallAtK(vecIds, item.relevant, K);
    const vn = ndcgAtK(vecIds, item.relevant, K);

    hybridR.push(hr);
    hybridN.push(hn);
    vectorR.push(vr);
    vectorN.push(vn);

    details.push({
      query: item.query,
      relevant: item.relevant,
      keywords: kw,
      hybridTop: hybIds.map((id) => titleOf.get(id)),
      vectorTop: vecIds.map((id) => titleOf.get(id)),
      hybridRecall: +hr.toFixed(4),
      hybridNdcg: +hn.toFixed(4),
      vectorRecall: +vr.toFixed(4),
      vectorNdcg: +vn.toFixed(4),
    });
  }

  const run = {
    dtype,
    backend: info.backend,
    modelBytes: info.modelBytes,
    hybrid: { recallAtK: avg(hybridR), ndcgAtK: avg(hybridN) },
    vectorOnly: { recallAtK: avg(vectorR), ndcgAtK: avg(vectorN) },
    details,
  };
  report.runs.push(run);
  console.log(
    `${dtype.padEnd(5)} 混合 Recall@${K}=${run.hybrid.recallAtK} nDCG@${K}=${run.hybrid.ndcgAtK} | ` +
      `纯向量 Recall@${K}=${run.vectorOnly.recallAtK} nDCG@${K}=${run.vectorOnly.ndcgAtK} | ` +
      `${(info.modelBytes / 1048576).toFixed(1)}MB`,
  );
}

await browser.close();
await mkdir(resolve("reports"), { recursive: true });
await writeFile(resolve(process.env.REPORT_FILE ?? "reports/quality.json"), JSON.stringify(report, null, 2));
console.log(`报告已写入 ${process.env.REPORT_FILE ?? "reports/quality.json"}`);
