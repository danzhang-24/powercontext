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
 * e2e / 压测公共骨架:用真实 Chromium 打开应用,驱动浏览器内的端侧推理。
 */
import { chromium } from "playwright";
import { existsSync } from "node:fs";

export const APP_URL = process.env.APP_URL ?? "http://127.0.0.1:8787/";
/** API 基址:默认与页面同源,可用 API_BASE / APP_URL 覆盖 */
export const API_BASE = (process.env.API_BASE ?? APP_URL.replace(/\/$/, "")).replace(/\/$/, "");

/** 优先用 Playwright 自带的 Chromium;没有就退回系统 Chromium */
const SYSTEM_CHROMIUM = ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"];

function resolveExecutable() {
  if (process.env.CHROMIUM_PATH) return process.env.CHROMIUM_PATH;
  for (const p of SYSTEM_CHROMIUM) if (existsSync(p)) return p;
  return undefined;
}

/**
 * Chromium 启动参数。
 *
 * WEBGPU=1 时额外打开 WebGPU:
 *   --enable-unsafe-webgpu              允许在无独显环境暴露 navigator.gpu
 *   --use-webgpu-adapter=swiftshader    让 WebGPU 走 SwiftShader(软件 Vulkan)适配器
 *   --disable-vulkan-surface             无显示器环境下避免 surface 创建失败
 * 没有独显时用 SwiftShader 也能完整跑通 WebGPU 代码路径(Dawn + WGSL shader),
 * 只是绝对耗时不能代表真实 GPU 性能。
 */
export const CHROMIUM_ARGS = [
  "--no-sandbox",
  "--disable-dev-shm-usage",
  "--enable-unsafe-swiftshader",
  "--enable-features=Vulkan",
  "--use-angle=swiftshader",
  ...(process.env.WEBGPU === "1"
    ? [
        "--enable-unsafe-webgpu",
        "--use-webgpu-adapter=swiftshader",
        "--disable-vulkan-surface",
        "--enable-dawn-features=allow_unsafe_apis",
      ]
    : []),
];

export async function launchBrowser({ headless = true } = {}) {
  return chromium.launch({
    headless,
    executablePath: resolveExecutable(),
    args: CHROMIUM_ARGS,
  });
}

/** 打开应用并等待脚本初始化完成 */
export async function openApp(browser, { url = APP_URL } = {}) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on("console", (m) => {
    const t = m.text();
    if (m.type() === "error") console.log("  [page error]", t);
  });
  page.on("pageerror", (e) => console.log("  [page exception]", e.message));
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => !!window.__kb, null, { timeout: 30_000 });
  return page;
}

/** 等待 API 侧可用 */
export async function waitForApi(base = API_BASE) {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`${base}/api/health`);
      if (r.ok) return await r.json();
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("API 未就绪");
}

/** 页面内:加载指定精度的模型 */
export async function loadModel(page, dtype, preferWebGPU = true) {
  return page.evaluate(
    async ([d, g]) => {
      const info = await window.__kb.loadModel(d, g);
      return {
        backend: info.backend,
        dtype: info.dtype,
        loadMs: info.loadMs,
        downloadMs: info.downloadMs ?? 0,
        modelBytes: info.modelBytes,
        fellBack: info.fellBack,
        reason: info.reason ?? null,
      };
    },
    [dtype, preferWebGPU],
  );
}

/** 页面内:批量向量化 */
export async function embed(page, texts, batchSize = 16) {
  return page.evaluate(
    async ([t, bs]) => {
      const t0 = performance.now();
      const vecs = await window.__kb.embed(t, bs);
      return { vecs, ms: performance.now() - t0 };
    },
    [texts, batchSize],
  );
}

/** 页面内:抽取关键词 */
export async function keywords(page, q) {
  return page.evaluate((s) => window.__kb.keywords(s), q);
}

/** 页面内:查询向量(页面内计时,不含 IPC 开销) */
export async function embedQuery(page, q) {
  return page.evaluate(async (s) => window.__kb.embedTimed([s], 1), q);
}

export async function apiPost(path, body) {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!r.ok) throw new Error(`${path} -> ${r.status} ${await r.text()}`);
  return r.json();
}

/** 页面内:向量化 + 抽关键词 + 调 API 检索 */
export async function search(page, query, nResults = 5) {
  const kw = await keywords(page, query);
  const { vecs, ms } = await embedQuery(page, query);
  const res = await apiPost("/api/search", {
    queryEmbedding: vecs[0],
    queryText: query,
    keywords: kw,
    nResults,
  });
  return { ...res, keywords: kw, queryEmbedMs: ms };
}

export function percentile(arr, p) {
  if (!arr.length) return 0;
  const s = [...arr].sort((a, b) => a - b);
  const idx = Math.min(s.length - 1, Math.max(0, Math.ceil((p / 100) * s.length) - 1));
  return s[idx];
}

export const median = (arr) => percentile(arr, 50);
