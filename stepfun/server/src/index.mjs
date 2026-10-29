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
 * 本地 server:承接浏览器的写库 / 检索请求,真正的存储与混合检索全部由 seekdb 完成。
 *
 * 浏览器端(Transformers.js)负责:
 *   - 文档切片
 *   - 文档向量 & 查询向量(本地推理,WebGPU 优先,WASM 降级)
 *   - 查询关键词抽取(供 seekdb 全文分支使用)
 *
 * server 端(seekdb-js)负责:
 *   - 建集合/表(FULLTEXT INDEX + HNSW 向量索引)
 *   - 落库 + 索引刷新
 *   - DBMS_HYBRID_SEARCH:向量检索 + 全文检索 + RRF 融合
 */
import express from "express";
import cors from "cors";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { config } from "./config.mjs";
import { KnowledgeStore } from "./store.mjs";

const app = express();
app.use(cors());
app.use(express.json({ limit: "64mb" }));

const store = new KnowledgeStore(config);

const started = Date.now();

app.get("/api/health", async (_req, res) => {
  try {
    res.json({
      ok: true,
      mode: store.mode,
      seekdbVersion: store.version,
      collection: config.collection,
      dimension: config.dimension,
      analyzer: config.analyzer,
      fusion: "RRF (DBMS_HYBRID_SEARCH)",
      docCount: await store.count(),
      uptimeMs: Date.now() - started,
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

/** 写入文档:请求体里的 embeddings 由浏览器端本地推理产出 */
app.post("/api/documents", async (req, res) => {
  try {
    const { documents = [], embeddings = [] } = req.body ?? {};
    if (!documents.length) return res.status(400).json({ error: "documents 为空" });
    if (documents.length !== embeddings.length)
      return res.status(400).json({ error: "documents 与 embeddings 数量不一致" });

    const ids = documents.map((d) => String(d.id));
    const texts = documents.map((d) => String(d.text ?? ""));
    const metadatas = documents.map((d) => d.metadata ?? {});

    const { writeMs, refreshMs } = await store.addDocuments({
      ids,
      documents: texts,
      embeddings,
      metadatas,
    });

    res.json({
      ok: true,
      added: documents.length,
      total: await store.count(),
      writeMs,
      refreshMs,
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message, stack: e.stack });
  }
});

/** 混合检索:queryEmbedding 来自浏览器端,keywords 用于 seekdb 全文分支 */
app.post("/api/search", async (req, res) => {
  try {
    const { queryEmbedding, queryText = "", keywords = [], nResults = 10 } = req.body ?? {};
    if (!Array.isArray(queryEmbedding) || !queryEmbedding.length)
      return res.status(400).json({ error: "缺少 queryEmbedding" });

    const { results, searchMs } = await store.hybridSearch({
      queryEmbedding,
      queryText,
      keywords,
      nResults,
    });

    res.json({ ok: true, results, searchMs, fusion: "RRF" });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message, stack: e.stack });
  }
});

/** 重置集合 */
app.post("/api/reset", async (_req, res) => {
  try {
    await store.reset();
    res.json({ ok: true, docCount: await store.count() });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

/** 生产模式下直接托管前端产物(vite build 的输出目录) */
app.use(express.static(config.webDist));
app.get("*", (req, res, next) => {
  const indexFile = resolve(config.webDist, "index.html");
  if (req.path.startsWith("/api/") || !existsSync(indexFile)) return next();
  res.sendFile(indexFile);
});

async function main() {
  console.log(`[stepfun-kb] seekdb 模式=${config.mode}`, {
    embedded: { path: config.path, database: config.database },
    server: { host: config.dbHost, port: config.dbPort, database: config.database },
  });
  await store.init();
  console.log(
    `[stepfun-kb] seekdb 就绪: collection=${config.collection} dim=${config.dimension} version=${store.version}`,
  );
  app.listen(config.apiPort, config.apiHost, () => {
    console.log(`[stepfun-kb] API 监听 http://${config.apiHost}:${config.apiPort}`);
  });
}

main().catch((e) => {
  console.error("[stepfun-kb] 启动失败:", e);
  process.exit(1);
});
