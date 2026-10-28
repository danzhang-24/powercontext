import "./style.css";
import { Embedder, MODEL_ID, type Dtype } from "./embedder";
import { extractKeywords } from "./keyword";
import { chunkDocument, stableId } from "./chunk";

/* ------------------------------------------------------------------ */
/* 基础工具                                                            */
/* ------------------------------------------------------------------ */

const $ = <T extends HTMLElement = HTMLElement>(sel: string) => document.querySelector(sel) as T;

const api = {
  base: (import.meta as any).env?.VITE_API_BASE ?? "",
  async health() {
    const r = await fetch(`${api.base}/api/health`);
    if (!r.ok) throw new Error(`health ${r.status}`);
    return r.json();
  },
  async addDocuments(documents: unknown[], embeddings: number[][]) {
    const r = await fetch(`${api.base}/api/documents`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ documents, embeddings }),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error ?? `add ${r.status}`);
    return r.json();
  },
  async search(queryEmbedding: number[], queryText: string, keywords: string[], nResults: number) {
    const r = await fetch(`${api.base}/api/search`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ queryEmbedding, queryText, keywords, nResults }),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error ?? `search ${r.status}`);
    return r.json();
  },
  async reset() {
    const r = await fetch(`${api.base}/api/reset`, { method: "POST" });
    return r.json();
  },
};

const fmt = (n: number, d = 1) => (Number.isFinite(n) ? n.toFixed(d) : "-");
const fmtMs = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(2)} s` : `${n.toFixed(0)} ms`);
const fmtBytes = (b: number) =>
  b > 0 ? `${(b / 1048576).toFixed(1)} MB` : "-";

/* ------------------------------------------------------------------ */
/* 应用状态                                                            */
/* ------------------------------------------------------------------ */

const state = {
  embedder: new Embedder(),
  dtype: "q8" as Dtype,
  preferWebGPU: true,
  docCount: 0,
  lastTimings: null as null | Record<string, number>,
};

const app = document.querySelector<HTMLDivElement>("#app")!;
app.innerHTML = `
  <header class="topbar">
    <div class="brand">
      <h1>端侧 AI 迷你知识库</h1>
      <p class="sub">浏览器本地 embedding(Transformers.js / ONNX Runtime Web)+ seekdb 向量+全文混合检索</p>
    </div>
    <div class="badges">
      <span class="badge" id="badge-backend">推理后端:未加载</span>
      <span class="badge" id="badge-model">模型:未加载</span>
      <span class="badge" id="badge-db">seekdb:连接中…</span>
    </div>
  </header>

  <div class="banner warn" id="fallback-banner" hidden></div>
  <div class="banner info" id="info-banner" hidden></div>

  <main class="grid">
    <section class="panel">
      <h2><span class="step">1</span>端侧模型与量化</h2>
      <div class="row">
        <label>模型精度</label>
        <div class="segmented" id="dtype-group">
          <label><input type="radio" name="dtype" value="fp32" /> FP32(基线)</label>
          <label><input type="radio" name="dtype" value="fp16" /> FP16</label>
          <label><input type="radio" name="dtype" value="q8" checked /> INT8(q8)</label>
        </div>
      </div>
      <div class="row">
        <label>推理后端</label>
        <div class="segmented" id="backend-group">
          <label><input type="radio" name="backend" value="auto" checked /> 自动(WebGPU 优先)</label>
          <label><input type="radio" name="backend" value="wasm" /> 强制 WASM</label>
        </div>
      </div>
      <button id="btn-load" class="primary">加载模型(本地推理)</button>
      <div class="kv" id="model-info"></div>
    </section>

    <section class="panel">
      <h2><span class="step">2</span>导入语料并本地向量化</h2>
      <textarea id="corpus" rows="8" placeholder="粘贴文本,或选择 .txt/.md 文件;每段会切片后在浏览器本地算向量"></textarea>
      <div class="row">
        <input type="file" id="files" multiple accept=".txt,.md,.markdown" />
        <button id="btn-sample">载入示例语料</button>
        <button id="btn-reset" class="ghost">清空知识库</button>
      </div>
      <button id="btn-import" class="primary">导入 → 本地向量化 → 写入 seekdb</button>
      <div class="progress"><div id="bar"></div></div>
      <div class="kv" id="import-info"></div>
    </section>

    <section class="panel wide">
      <h2><span class="step">3</span>混合检索(向量 + 全文,RRF 融合在 seekdb 内完成)</h2>
      <div class="row">
        <input type="text" id="query" placeholder="输入查询,例如:seekdb 的混合检索是怎么做的?" />
        <button id="btn-search" class="primary">检索</button>
      </div>
      <div class="kv" id="timing"></div>
      <ol class="results" id="results"></ol>
    </section>
  </main>
`;

/* ------------------------------------------------------------------ */
/* 交互                                                                */
/* ------------------------------------------------------------------ */

/** 读取三种精度权重的真实体积,给出量化前后的体积与压缩比 */
async function refreshSizeTable() {
  const files: Array<[string, string]> = [
    ["FP32 基线", "model.onnx"],
    ["FP16", "model_fp16.onnx"],
    ["INT8 (q8)", "model_quantized.onnx"],
  ];
  const sizes: number[] = [];
  for (const [, f] of files) {
    try {
      const res = await fetch(`/models/Xenova/all-MiniLM-L6-v2/onnx/${f}`, { method: "HEAD" });
      sizes.push(Number(res.headers.get("content-length") ?? 0));
    } catch {
      sizes.push(0);
    }
  }
  const base = sizes[0] || 1;
  const el = $("#size-table");
  if (!el) return;
  el.innerHTML =
    `<div><span>精度</span><b>权重体积 / 压缩比</b></div>` +
    files
      .map(([name], i) => {
        const s = sizes[i];
        const ratio = s ? (base / s).toFixed(2) + "×" : "-";
        const mark = ["fp32", "fp16", "q8"][i] === state.dtype ? " ← 当前" : "";
        return `<div><span>${name}${mark}</span><b>${fmtBytes(s)} · ${ratio}</b></div>`;
      })
      .join("");
}

document.addEventListener("change", (e) => {
  const t = e.target as HTMLInputElement;
  if (t.name === "dtype") state.dtype = t.value as Dtype;
  if (t.name === "backend") state.preferWebGPU = t.value === "auto";
});

const badgeBackend = $("#badge-backend");
const badgeModel = $("#badge-model");
const badgeDb = $("#badge-db");
const fallbackBanner = $<HTMLElement>("#fallback-banner");
const infoBanner = $<HTMLElement>("#info-banner");

/* --- seekdb 健康检查 --- */
api
  .health()
  .then((h) => {
    state.docCount = h.docCount ?? 0;
    badgeDb.textContent = `seekdb:${h.mode} · 集合 ${h.collection} · ${h.docCount} 篇`;
    badgeDb.classList.add("ok");
    if (h.seekdbVersion) badgeDb.title = `seekdb version ${h.seekdbVersion}`;
  })
  .catch(() => {
    badgeDb.textContent = "seekdb:未连接";
    badgeDb.classList.add("bad");
  });

/* --- 加载模型 --- */
$("#btn-load").addEventListener("click", async () => {
  const btn = $<HTMLButtonElement>("#btn-load");
  btn.disabled = true;
  btn.textContent = "加载中…";
  try {
    const info = await state.embedder.load(state.dtype, state.preferWebGPU);
    const backend = info.backend;
    const adapterTxt = info.adapter
      ? [info.adapter.vendor, info.adapter.architecture, info.adapter.description]
          .filter(Boolean)
          .join(" / ")
      : "";
    badgeBackend.textContent = `推理后端:${backend === "webgpu" ? "WebGPU" : "WASM"}`;
    badgeBackend.classList.add(backend === "webgpu" ? "ok" : "warn");
    badgeBackend.title = backend === "webgpu" ? `WebGPU adapter:${adapterTxt || "未知"}` : "WASM (CPU)";
    badgeModel.textContent = `模型:${MODEL_ID.split("/").pop()} · ${state.dtype.toUpperCase()}`;
    badgeModel.classList.add("ok");

    const sizes: Record<string, number> = {
      fp32: 90_535_168,
      fp16: 45_304_320,
      q8: 22_956_288,
    };
    const base = sizes.fp32;
    const cur = info.modelBytes || sizes[state.dtype] || 0;
    $("#model-info").innerHTML = `
      <div><span>实际后端</span><b>${backend === "webgpu" ? "WebGPU (GPU 加速)" : "WASM (CPU)"}</b></div>
      <div><span>模型加载耗时</span><b>${fmtMs(info.loadMs)}</b></div>
      <div><span>本次权重体积</span><b>${fmtBytes(cur)}</b></div>
      <div><span>相对 FP32 压缩比</span><b>${cur ? (base / cur).toFixed(2) + "×" : "-"}</b></div>
      ${
        backend === "webgpu"
          ? `<div><span>WebGPU adapter</span><b>${adapterTxt || "未知"}</b></div>`
          : `<div><span>WebGPU adapter</span><b>不可用</b></div>`
      }
    `;
    void refreshSizeTable();
    if (info.fellBack) {
      fallbackBanner.hidden = false;
      fallbackBanner.textContent = `⚠️ ${info.reason}`;
    } else {
      fallbackBanner.hidden = true;
    }
  } catch (e) {
    infoBanner.hidden = false;
    infoBanner.textContent = `模型加载失败:${(e as Error).message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = "加载模型(本地推理)";
  }
});

/* --- 选择文件:把内容读进文本框 --- */
$("#files").addEventListener("change", async (e) => {
  const input = e.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  if (!files.length) return;
  const ta = $<HTMLTextAreaElement>("#corpus");
  const parts: string[] = [];
  for (const f of files) {
    const text = await f.text();
    parts.push(`## ${f.name}\n${text}`);
  }
  ta.value = ta.value ? `${ta.value}\n\n${parts.join("\n\n")}` : parts.join("\n\n");
  infoBanner.hidden = false;
  infoBanner.textContent = `已读取 ${files.length} 个文件到待导入文本框。`;
});

/* --- 导入 --- */
function setProgress(p: number, text: string) {
  ($("#bar") as HTMLElement).style.width = `${Math.round(p * 100)}%`;
  if (text) $("#import-info").innerHTML += `<div><span>${text}</span><b></b></div>`;
}

$("#btn-sample").addEventListener("click", async () => {
  const r = await fetch("/corpus.json");
  const data = await r.json();
  const ta = $<HTMLTextAreaElement>("#corpus");
  ta.value = (data as any[]).map((d: any) => `## ${d.title}\n${d.text}`).join("\n\n");
});

$("#btn-reset").addEventListener("click", async () => {
  const r = await api.reset();
  state.docCount = r.docCount ?? 0;
  badgeDb.textContent = `seekdb:${(await api.health()).mode} · 集合已清空`;
  $("#import-info").innerHTML = "";
  $("#results").innerHTML = "";
});

$("#btn-import").addEventListener("click", async () => {
  if (!state.embedder.loaded) {
    alert("请先加载模型(本地推理)再导入语料。");
    return;
  }
  const ta = $<HTMLTextAreaElement>("#corpus");
  const text = ta.value.trim();
  if (!text) {
    alert("请先粘贴或导入文本内容。");
    return;
  }

  const btn = $<HTMLButtonElement>("#btn-import");
  btn.disabled = true;
  $("#import-info").innerHTML = "";
  const t0 = performance.now();

  try {
    const chunks = chunkDocument(text, { source: "paste" }, { idPrefix: stableId("paste", text).slice(0, 10) });
    setProgress(0.1, `切片完成:${chunks.length} 块,开始本地向量化`);

    const batchSize = 16;
    const embeddings: number[][] = [];
    const tEmbed0 = performance.now();
    for (let i = 0; i < chunks.length; i += batchSize) {
      const batch = chunks.slice(i, i + batchSize);
      const vecs = await state.embedder.embed(
        batch.map((c) => c.text),
        batchSize,
      );
      embeddings.push(...vecs);
      setProgress(0.1 + 0.6 * ((i + batch.length) / chunks.length), `向量化 ${i + batch.length}/${chunks.length}`);
    }
    const embedMs = performance.now() - tEmbed0;

    setProgress(0.75, "写入 seekdb 并刷新索引…");
    const tWrite0 = performance.now();
    const res = await api.addDocuments(
      chunks.map((c) => ({ id: c.id, text: c.text, metadata: c.metadata })),
      embeddings,
    );
    const writeMs = performance.now() - tWrite0;

    state.docCount = res.total ?? state.docCount;
    badgeDb.textContent = `seekdb:集合 ${state.docCount} 篇`;

    setProgress(1, "");
    $("#import-info").innerHTML = `
      <div><span>切片 / 写入条数</span><b>${chunks.length} / ${res.added}</b></div>
      <div><span>本地向量化耗时</span><b>${fmtMs(embedMs)}</b></div>
      <div><span>seekdb 写入耗时</span><b>${fmtMs(res.writeMs)}</b></div>
      <div><span>索引刷新耗时</span><b>${fmtMs(res.refreshMs)}</b></div>
      <div><span>端到端导入耗时</span><b>${fmtMs(performance.now() - t0)}</b></div>
      <div><span>集合当前文档数</span><b>${state.docCount}</b></div>
    `;
  } catch (e) {
    infoBanner.hidden = false;
    infoBanner.textContent = `导入失败:${(e as Error).message}`;
  } finally {
    btn.disabled = false;
  }
});

/* --- 检索 --- */
$("#btn-search").addEventListener("click", async () => {
  if (!state.embedder.loaded) {
    alert("请先加载模型(本地推理)再检索。");
    return;
  }
  const input = $<HTMLInputElement>("#query");
  const q = input.value.trim();
  if (!q) return;

  const btn = $<HTMLButtonElement>("#btn-search");
  btn.disabled = true;
  const t0 = performance.now();
  try {
    const keywords = extractKeywords(q);
    const tEmbed0 = performance.now();
    const vec = await state.embedder.embedQuery(q);
    const embedMs = performance.now() - tEmbed0;

    const res = await api.search(vec, q, keywords, 8);
    const e2e = performance.now() - t0;

    state.lastTimings = { embedMs, searchMs: res.searchMs, e2e };
    $("#timing").innerHTML = `
      <div><span>查询向量化(本地)</span><b>${fmtMs(embedMs)}</b></div>
      <div><span>seekdb 混合检索</span><b>${fmtMs(res.searchMs)}</b></div>
      <div><span>端到端延迟</span><b>${fmtMs(e2e)}</b></div>
      <div><span>全文分支关键词</span><b>${keywords.join("、") || "-"}</b></div>
    `;

    const list = $("#results");
    list.innerHTML = (res.results as any[])
      .map(
        (r, i) => `
        <li>
          <div class="rank">#${i + 1}</div>
          <div class="body">
            <div class="meta">${r.metadata?.source ? `<span class="tag">${escapeHtml(String(r.metadata.source))}</span>` : ""}
              <span class="tag ghost">dist=${r.distance ?? "-"}</span></div>
            <p>${escapeHtml(r.document)}</p>
          </div>
        </li>`,
      )
      .join("");
  } catch (e) {
    infoBanner.hidden = false;
    infoBanner.textContent = `检索失败:${(e as Error).message}`;
  } finally {
    btn.disabled = false;
  }
});

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!,
  );
}

/* ------------------------------------------------------------------ */
/* e2e / 压测脚本的测试钩子(不影响正常业务流程)                          */
/* ------------------------------------------------------------------ */
(window as any).__kb = {
  state,
  api,
  loadModel: (dtype: Dtype, preferWebGPU: boolean) => state.embedder.load(dtype, preferWebGPU),
  embed: (texts: string[], batchSize = 16) => state.embedder.embed(texts, batchSize),
  embedTimed: async (texts: string[], batchSize = 16) => {
    const t0 = performance.now();
    const vecs = await state.embedder.embed(texts, batchSize);
    return { vecs, ms: performance.now() - t0 };
  },
  embedQuery: (text: string) => state.embedder.embedQuery(text),
  keywords: extractKeywords,
  chunk: chunkDocument,
};
