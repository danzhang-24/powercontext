/**
 * 准备本地资源:端侧 embedding 模型权重 + onnxruntime-web 的 wasm 运行时
 *
 * 优先复用同仓库里已有的模型目录(节省带宽),否则从 ModelScope 拉取
 * (国内可用;失败自动回退 Hugging Face)。
 *
 * 用法: node scripts/setup_assets.mjs
 */
import { createWriteStream } from "node:fs";
import { cp, mkdir, readdir, rm, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { pipeline } from "node:stream/promises";
import { Readable } from "node:stream";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const MODEL_ID = "Xenova/all-MiniLM-L6-v2";
const OUT = join(root, "assets", "models", MODEL_ID);
const ORT_OUT = join(root, "assets", "ort");
const ORT_SRC = join(root, "node_modules", "onnxruntime-web", "dist");

const SOURCES = [
  `https://modelscope.cn/api/v1/models/${MODEL_ID}/repo?Revision=master&FilePath=`,
  `https://huggingface.co/${MODEL_ID}/resolve/main/`,
];

const FILES = [
  "config.json",
  "tokenizer.json",
  "tokenizer_config.json",
  "special_tokens_map.json",
  "onnx/model_quantized.onnx",
  "onnx/model_fp16.onnx",
  "onnx/model.onnx",
];

const exists = async (p) => {
  try {
    return (await stat(p)).size > 0;
  } catch {
    return false;
  }
};

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
      console.log(`ok    ${file}  ${(s.size / 1048576).toFixed(1)} MB`);
      return;
    } catch (e) {
      lastErr = e;
      await rm(dest, { force: true });
    }
  }
  throw new Error(`${file}: ${lastErr?.message ?? "全部源失败"}`);
}

console.log("== 1/2 模型权重 ==");
// 同机已有 stepfun 的模型就直接复制,省一次 150MB 下载
const local = join(root, "..", "stepfun", "web", "public", "models", MODEL_ID);
if (! (await exists(join(local, "onnx", "model_quantized.onnx")))) {
  for (const f of FILES) await download(f);
} else {
  console.log("复用同仓库 stepfun 的模型目录");
  await cp(local, OUT, { recursive: true, force: true });
  console.log(`ok    已复制到 ${OUT}`);
}

console.log("== 2/2 onnxruntime-web 运行时 ==");
await mkdir(ORT_OUT, { recursive: true });
const ortFiles = (await readdir(ORT_SRC)).filter((f) => f.endsWith(".wasm") || f.endsWith(".mjs"));
for (const f of ortFiles) {
  await cp(join(ORT_SRC, f), join(ORT_OUT, f));
}
console.log(`ok    ${ortFiles.length} 个运行时文件 -> ${ORT_OUT}`);
console.log("资源就绪 ✅");
