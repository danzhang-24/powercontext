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
 * 性能压测:在真实 Chromium 里跑完整链路
 *   模型加载 -> 文档向量化(批量) -> 写入 seekdb -> 混合检索 -> 端到端
 *
 * 每种精度都用**全新浏览器实例**,避免 WASM 运行时被上一个用例预热,
 * 这样「首次加载 / 冷启动」与「预热后」两组数据才是可比的。
 *
 * 输出:模型体积 / 压缩比 / 向量化吞吐 / seekdb 检索延迟 / 端到端延迟(中位数 + P95)
 *
 * 用法:
 *   node scripts/bench.mjs
 *   BACKEND=webgpu node scripts/bench.mjs
 *   BENCH_DOCS=120 REPEAT=10 node scripts/bench.mjs
 */
import { writeFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import {
  launchBrowser,
  openApp,
  waitForApi,
  loadModel,
  embed,
  search,
  apiPost,
  median,
  percentile,
} from "./lib/harness.mjs";

const BACKEND = process.env.BACKEND ?? "wasm";
const DTYPES = (process.env.DTYPES ?? "fp32,fp16,q8").split(",");
const BENCH_DOCS = Number(process.env.BENCH_DOCS ?? 60);
const REPEAT = Number(process.env.REPEAT ?? 5);
/** 预热后重复向量化次数(SwiftShader 下 WebGPU 很慢,可以调成 1) */
const WARM_REPEATS = Number(process.env.WARM_REPEATS ?? 3);
const QUERIES = [
  "混合检索是怎么做的",
  "浏览器里怎么跑 embedding 模型",
  "INT8 量化能压缩多少",
  "WebGPU 不可用时怎么降级",
  "中文全文检索用什么分词器",
  "为什么写入后要刷新索引",
  "OceanBase 和 seekdb 的关系",
  "怎么提高向量化吞吐",
];

const health = await waitForApi();
console.log(`seekdb: ${health.mode} / ${health.seekdbVersion} / collection=${health.collection}`);

const corpusSrc = await (await fetch("http://127.0.0.1:8787/corpus.json")).json();
/** 把基础语料扩到 BENCH_DOCS 条(内容带轮次后缀,保证文本各不相同) */
const corpus = [];
for (let i = 0; i < BENCH_DOCS; i++) {
  const d = corpusSrc[i % corpusSrc.length];
  const round = Math.floor(i / corpusSrc.length);
  corpus.push({
    id: `bench-${i}`,
    text: round === 0 ? `${d.title}。${d.text}` : `${d.title}(第${round + 1}版)。${d.text}`,
    metadata: { title: d.title, round },
  });
}

const report = {
  env: {
    backendRequested: BACKEND,
    corpusDocs: corpus.length,
    warmRepeats: WARM_REPEATS,
    querySet: QUERIES.length,
    repeat: REPEAT,
    seekdb: health,
  },
  runs: [],
};

for (const dtype of DTYPES) {
  console.log(`\n===== dtype=${dtype} backend=${BACKEND} =====`);
  const browser = await launchBrowser();
  const page = await openApp(browser);

  if (report.env.userAgent === undefined) {
    report.env.userAgent = await page.evaluate(() => navigator.userAgent);
    report.env.cores = await page.evaluate(() => navigator.hardwareConcurrency);
    report.env.webgpu = await page.evaluate(async () => {
      const gpu = navigator.gpu;
      if (!gpu) return { supported: false, reason: "navigator.gpu 不存在" };
      const a = await gpu.requestAdapter();
      return { supported: !!a, reason: a ? "adapter 可用" : "没有可用 adapter" };
    });
  }

  await apiPost("/api/reset");

  const info = await loadModel(page, dtype, BACKEND === "webgpu");
  console.log(
    `模型: backend=${info.backend} 下载=${(info.downloadMs ?? 0).toFixed(0)}ms 加载=${info.loadMs.toFixed(0)}ms 体积=${(info.modelBytes / 1048576).toFixed(1)}MB${info.fellBack ? ` (降级: ${info.reason})` : ""}`,
  );

  /* 冷启动:模型加载后的第一次向量化(含 WASM 运行时初始化) */
  const cold = await embed(page, corpus.map((c) => c.text), 16);
  /* 预热后再跑 3 次取中位数 */
  const warmRuns = [];
  for (let i = 0; i < WARM_REPEATS; i++) warmRuns.push(await embed(page, corpus.map((c) => c.text), 16));
  const warmMs = median(warmRuns.map((r) => r.ms));

  // 写入 + 索引刷新:重复 3 次取中位数(upsert 幂等,重复写安全)
  const writeMsList = [];
  const refreshMsList = [];
  const writeTotalList = [];
  for (let i = 0; i < 3; i++) {
    const tw = Date.now();
    const r = await apiPost("/api/documents", {
      documents: corpus.map((c) => ({ id: c.id, text: c.text, metadata: c.metadata })),
      embeddings: cold.vecs,
    });
    writeTotalList.push(Date.now() - tw);
    writeMsList.push(r.writeMs);
    refreshMsList.push(r.refreshMs);
  }
  const writeTotalMs = median(writeTotalList);

  /* 检索延迟 */
  const searchMs = [];
  const e2eMs = [];
  const embedQueryMs = [];
  for (let i = 0; i < REPEAT; i++) {
    for (const q of QUERIES) {
      const t0 = Date.now();
      const res = await search(page, q, 8);
      const tEnd = Date.now();
      embedQueryMs.push(res.queryEmbedMs);
      searchMs.push(res.searchMs);
      e2eMs.push(tEnd - t0);
    }
  }

  const run = {
    dtype,
    backend: info.backend,
    fellBack: info.fellBack,
    modelBytes: info.modelBytes,
    modelLoadMs: +info.loadMs.toFixed(1),
    modelDownloadMs: +(info.downloadMs ?? 0).toFixed(1),
    coldEmbedMs: +cold.ms.toFixed(1),
    warmEmbedMs: +warmMs.toFixed(1),
    embedThroughputDocsPerSec: +(corpus.length / (warmMs / 1000)).toFixed(2),
    writeTotalMs: +writeTotalMs.toFixed(1),
    seekdbWriteMsMedian: +median(writeMsList).toFixed(1),
    indexRefreshMsMedian: +median(refreshMsList).toFixed(1),
    queryEmbedMsMedian: +median(embedQueryMs).toFixed(2),
    seekdbSearchMsMedian: +median(searchMs).toFixed(2),
    seekdbSearchMsP95: +percentile(searchMs, 95).toFixed(2),
    endToEndMsMedian: +median(e2eMs).toFixed(2),
    endToEndMsP95: +percentile(e2eMs, 95).toFixed(2),
    samples: searchMs.length,
  };
  report.runs.push(run);
  console.log(
    `  体积=${(info.modelBytes / 1048576).toFixed(1)}MB 下载=${run.modelDownloadMs}ms 加载=${run.modelLoadMs}ms 冷启动向量化=${run.coldEmbedMs}ms 预热=${run.warmEmbedMs}ms 吞吐=${run.embedThroughputDocsPerSec}/s 检索中位=${run.seekdbSearchMsMedian}ms 端到端中位=${run.endToEndMsMedian}ms`,
  );

  await browser.close();
}

await mkdir(resolve("reports"), { recursive: true });
await writeFile(resolve(process.env.REPORT_FILE ?? "reports/bench.json"), JSON.stringify(report, null, 2));
console.log("\n报告已写入 reports/bench.json");
