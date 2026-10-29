/**
 * 纯 Node 端侧 embedding(无原生依赖、无浏览器)
 *
 *   分词: BERT WordPiece(uncased)—— 从 tokenizer.json 的 vocab 现场实现
 *   推理: onnxruntime-web(WASM),在 Node 里直接读本地 .wasm / .onnx 文件
 *
 * 为什么不用 transformers.js:
 *   它的 Node 构建依赖 onnxruntime-node 的原生二进制(受限网络下装不上),
 *   而 onnxruntime-web 是纯 WASM,在 Node 里同样能跑(见 scripts/verify_embedder.mjs 的交叉校验)。
 *
 * 正确性保证:
 *   本实现产出的向量与「浏览器里 Transformers.js 跑出来的向量」做过逐条比对,
 *   余弦相似度 > 0.9999(见 reports/embedder-parity.json)。
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

const PUNCTUATION =
  "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~¡§«¶·»¿‐‑‒–—―†‡•…‰′″‹›⁄\\‽€£¥₩";

/** 极简 ONNX Runtime Web 装载(直接读文件,不走 fetch) */
async function loadOrt() {
  const ortPath = require.resolve("onnxruntime-web");
  const ort = await import(ortPath);
  return ort;
}

export class Embedder {
  /**
   * @param {object} opts
   * @param {string} opts.modelDir  含 tokenizer.json 与 onnx/*.onnx 的目录
   * @param {string} opts.onnxFile   onnx 文件名(model_quantized.onnx / model_fp16.onnx / model.onnx)
   * @param {string} opts.ortDir     onnxruntime-web/dist 目录(放 .wasm)
   */
  constructor({ modelDir, onnxFile = "model_quantized.onnx", ortDir }) {
    this.modelDir = modelDir;
    this.onnxFile = onnxFile;
    this.ortDir = ortDir;
    this.session = null;
    this._queue = Promise.resolve();
    this.vocab = null;
    this.unk = null;
    this.cls = null;
    this.sep = null;
    this.pad = null;
    this.dim = 0;
    this.handleChineseChars = true;
  }

  async init() {
    // ---- 分词器资源 ----
    const tokPath = path.join(this.modelDir, "tokenizer.json");
    const tokenizerJson = JSON.parse(fs.readFileSync(tokPath, "utf8"));
    this.vocab = tokenizerJson.model.vocab;
    this.unk = tokenizerJson.model.unk_token ?? "[UNK]";
    this.maxCharsPerWord = tokenizerJson.model.max_input_chars_per_word ?? 100;
    this.handleChineseChars = tokenizerJson.normalizer?.handle_chinese_chars !== false;
    const added = tokenizerJson.added_tokens ?? [];
    const cfgPath = path.join(this.modelDir, "tokenizer_config.json");
    const cfg = fs.existsSync(cfgPath) ? JSON.parse(fs.readFileSync(cfgPath, "utf8")) : {};
    this.cls = cfg.cls_token ?? "[CLS]";
    this.sep = cfg.sep_token ?? "[SEP]";
    this.pad = cfg.pad_token ?? "[PAD]";
    let nextId = Object.values(this.vocab).reduce((m, v) => Math.max(m, Number(v) || 0), 0) + 1;
    for (const t of added) {
      if (t.content && this.vocab[t.content] === undefined) this.vocab[t.content] = nextId++;
    }

    // ---- ONNX 运行时 ----
    const ort = await loadOrt();
    ort.env.wasm.wasmPaths = this.ortDir.endsWith("/") ? this.ortDir : `${this.ortDir}/`;
    ort.env.wasm.numThreads = 1;
    ort.env.logLevel = "error";

    const modelPath = path.join(this.modelDir, "onnx", this.onnxFile);
    this.session = await ort.InferenceSession.create(
      new Uint8Array(fs.readFileSync(modelPath)),
    );
    this.ort = ort;
    // 从 session 的输出元数据里取隐藏维度(384)
    const meta = this.session.outputMetadata ?? [];
    const shape = meta.find((m) => Array.isArray(m.shape))?.shape;
    if (shape?.length) this.dim = Number(shape[shape.length - 1]);
    return this;
  }

  /* ------------------------------------------------------------------ */
  /* BERT WordPiece(uncased)                                             */
  /* ------------------------------------------------------------------ */

  /** BertNormalizer:小写 + 去重音 + 清理控制字符 */
  normalize(text) {
    let s = String(text ?? "");
    s = s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    s = s.toLowerCase();
    s = s.replace(/[\u0000-\u001f\u007f]/g, " ");
    s = s.replace(/\ufffd/g, "");
    // BertNormalizer(handle_chinese_chars=true):CJK 字符前后补空格
    if (this.handleChineseChars) {
      s = s.replace(/([\u4e00-\u9fff\u3400-\u4dbf])/g, " $1 ");
    }
    return s;
  }

  /** BertPreTokenizer:按空白切词,再把标点单独切出来 */
  preTokenize(text) {
    const out = [];
    for (const chunk of this.normalize(text).split(/\s+/)) {
      if (!chunk) continue;
      let buf = "";
      for (const ch of chunk) {
        if (PUNCTUATION.includes(ch)) {
          if (buf) { out.push(buf); buf = ""; }
          out.push(ch);
        } else {
          buf += ch;
        }
      }
      if (buf) out.push(buf);
    }
    return out;
  }

  /** WordPiece:贪心最长匹配,失败则整词记 [UNK] */
  wordPiece(word) {
    if (word.length > this.maxCharsPerWord) return [this.unk];
    const ids = [];
    let start = 0;
    while (start < word.length) {
      let end = word.length;
      let found = -1;
      while (start < end) {
        const sub = start > 0 ? `##${word.slice(start, end)}` : word.slice(start, end);
        const id = this.vocab[sub];
        if (id !== undefined) { found = id; break; }
        end--;
      }
      if (found < 0) return [this.vocab[this.unk] ?? 100];
      ids.push(found);
      start = end;
    }
    return ids;
  }

  /** 编码:返回 input_ids / attention_mask / token_type_ids */
  encode(text) {
    const ids = [this.vocab[this.cls]];
    for (const word of this.preTokenize(text)) ids.push(...this.wordPiece(word));
    ids.push(this.vocab[this.sep]);
    const maxLen = 512;
    const trimmed = ids.length > maxLen ? ids.slice(0, maxLen - 1).concat([this.vocab[this.sep]]) : ids;
    const mask = new Array(trimmed.length).fill(1);
    const typeIds = new Array(trimmed.length).fill(0);
    return { input_ids: trimmed, attention_mask: mask, token_type_ids: typeIds };
  }

  /* ------------------------------------------------------------------ */
  /* 推理                                                                */
  /* ------------------------------------------------------------------ */

  /**
   * 批量向量化
   * @param {string[]} texts
   * @returns {Promise<number[][]>} 归一化后的向量
   */
  async embed(texts) {
    // onnxruntime-web 的 WASM session 不是并发安全的:两次 run 重叠会把中间张量写串,
    // 结果就是「向量算成 NaN → 检索一条都召不回」。这里用一把串行锁把推理排队。
    return this._lock(() => this._embed(texts));
  }

  /** 简单的串行队列(保证同一时刻只有一次 session.run) */
  _lock(fn) {
    const run = this._queue.then(fn, fn);
    // 队列本身不因为失败而中断
    this._queue = run.then(() => undefined, () => undefined);
    return run;
  }

  async _embed(texts) {
    const enc = texts.map((t) => this.encode(t));
    const maxLen = Math.max(...enc.map((e) => e.input_ids.length));
    const n = enc.length;
    const padId = this.vocab[this.pad] ?? 0;

    const ids = new BigInt64Array(n * maxLen);
    const mask = new BigInt64Array(n * maxLen);
    const types = new BigInt64Array(n * maxLen);
    enc.forEach((e, i) => {
      for (let t = 0; t < maxLen; t++) {
        const id = t < e.input_ids.length ? e.input_ids[t] : padId;
        const m = t < e.attention_mask.length ? e.attention_mask[t] : 0;
        ids[i * maxLen + t] = BigInt(id);
        mask[i * maxLen + t] = BigInt(m);
        types[i * maxLen + t] = 0n;
      }
    });

    const dim = [n, maxLen];
    const feeds = {};
    for (const name of this.session.inputNames) {
      if (name.includes("mask")) feeds[name] = new this.ort.Tensor("int64", mask, dim);
      else if (name.includes("token_type")) feeds[name] = new this.ort.Tensor("int64", types, dim);
      else feeds[name] = new this.ort.Tensor("int64", ids, dim);
    }

    const out = await this.session.run(feeds);
    const key = Object.keys(out)[0];
    const tensor = out[key];
    const [, seq, hidden] = tensor.dims;
    const data = tensor.data;

    const vectors = [];
    for (let b = 0; b < n; b++) {
      const v = new Float64Array(hidden);
      for (let t = 0; t < seq; t++) {
        const m = Number(mask[b * seq + t]);
        if (!m) continue;
        for (let d = 0; d < hidden; d++) v[d] += data[b * seq * hidden + t * hidden + d] * m;
      }
      let norm = 0;
      for (const x of v) norm += x * x;
      norm = Math.sqrt(norm) || 1;
      vectors.push(Array.from(v, (x) => x / norm));
    }
    this.dim = hidden;
    return vectors;
  }

  async embedOne(text) {
    const [v] = await this.embed([text]);
    return v;
  }
}

export default Embedder;
