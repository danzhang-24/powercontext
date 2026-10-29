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
 * 把 onnxruntime-web 的 wasm 运行时拷到 web/public/ort/,
 * 让浏览器端推理完全走本地资源,不依赖外部 CDN。
 */
import { cp, mkdir, readdir, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "node_modules", "onnxruntime-web", "dist");
const dest = join(root, "web", "public", "ort");

if (!existsSync(src)) {
  console.error("找不到 onnxruntime-web/dist,请先执行 npm install");
  process.exit(1);
}

await mkdir(dest, { recursive: true });
const files = (await readdir(src)).filter(
  (f) => f.endsWith(".wasm") || f.endsWith(".mjs"),
);
for (const f of files) {
  await cp(join(src, f), join(dest, f));
  const s = await stat(join(dest, f));
  console.log(`copied ${f}  ${(s.size / 1048576).toFixed(1)} MB`);
}
console.log(`onnxruntime-web 运行时已就绪:${dest}`);
