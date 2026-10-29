/**
 * 下载端侧 embedding 模型(Transformers.js 格式)到 web/public/models/
 *
 * 默认优先从 ModelScope 拉取(国内网络可用),失败时回退 Hugging Face。
 *   MODEL_BASE=https://hf-mirror.com/Xenova/all-MiniLM-L6-v2 npm run model:fetch
 *
 * 三个精度版本都会下载,便于在界面里直接对比 FP32 / FP16 / INT8:
 *   onnx/model.onnx            FP32(基线)
 *   onnx/model_fp16.onnx       FP16
 *   onnx/model_quantized.onnx  INT8(q8)
 */
import { createWriteStream } from "node:fs";
import { mkdir, stat, rm } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { pipeline } from "node:stream/promises";
import { Readable } from "node:stream";

const REPO = process.env.MODEL_REPO ?? "Xenova/all-MiniLM-L6-v2";
const SOURCES = process.env.MODEL_BASE
  ? [process.env.MODEL_BASE]
  : [
      `https://modelscope.cn/api/v1/models/${REPO}/repo?Revision=master&FilePath=`,
      `https://huggingface.co/${REPO}/resolve/main/`,
    ];
const OUT = resolve(process.argv[2] ?? "web/public/models/Xenova/all-MiniLM-L6-v2");

const FILES = [
  "config.json",
  "tokenizer.json",
  "tokenizer_config.json",
  "special_tokens_map.json",
  "onnx/model.onnx", // fp32 基线
  "onnx/model_fp16.onnx", // FP16
  "onnx/model_quantized.onnx", // INT8
];

async function exists(p) {
  try {
    const s = await stat(p);
    return s.size > 0;
  } catch {
    return false;
  }
}

async function download(file) {
  const dest = join(OUT, file);
  if (await exists(dest)) {
    console.log(`skip  ${file}`);
    return;
  }
  await mkdir(dirname(dest), { recursive: true });

  let lastErr;
  for (const base of SOURCES) {
    const url = `${base}${base.includes("FilePath=") ? encodeURIComponent(file).replace(/%2F/g, "/") : file}`;
    try {
      const res = await fetch(url, { redirect: "follow" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await pipeline(Readable.fromWeb(res.body), createWriteStream(dest));
      const s = await stat(dest);
      console.log(`ok    ${file}  ${(s.size / 1048576).toFixed(1)} MB  (${base.split("/")[2]})`);
      return;
    } catch (e) {
      lastErr = e;
      await rm(dest, { force: true });
    }
  }
  throw new Error(`${file}: ${lastErr?.message ?? "全部源都失败"}`);
}

for (const f of FILES) {
  try {
    await download(f);
  } catch (e) {
    console.error(`fail  ${f}: ${e.message}`);
    process.exitCode = 1;
  }
}
console.log("model files ready in", OUT);
