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
 * 运行配置(全部可用环境变量覆盖)
 */
import { resolve } from "node:path";

export const config = {
  port: Number(process.env.SEEKDB_SERVICE_PORT ?? 8788),
  host: process.env.HOST ?? "0.0.0.0",

  /** 外部知识库 API 的密钥(Dify 侧配置同一个值) */
  apiKey: process.env.SEEKDB_API_KEY ?? "dify-2026-stepfun",

  /** 本地 embedding 资源目录 */
  modelDir:
    process.env.EMBED_MODEL_DIR ??
    resolve(process.cwd(), "assets/models/Xenova/all-MiniLM-L6-v2"),
  ortDir: process.env.EMBED_ORT_DIR ?? resolve(process.cwd(), "assets/ort"),
  onnxFile: process.env.EMBED_ONNX_FILE ?? "model_quantized.onnx",

  /** 检索条数 */
  cardTopK: Number(process.env.CARD_TOP_K ?? 4),
  memoryTopK: Number(process.env.MEMORY_TOP_K ?? 4),

  /** 静态演示页 */
  demoDir: process.env.DEMO_DIR ?? resolve(process.cwd(), "demo/public"),
};
