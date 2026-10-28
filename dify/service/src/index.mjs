/**
 * Dify × seekdb 服务
 *
 * 对外提供四类接口:
 *   POST /retrieval  Dify「外部知识库 API」协议 —— Dify 的知识检索节点直接调它
 *   GET  /memories   查这个玩家的黑历史(向量 + 全文 + 结构化过滤,全部在 seekdb 内完成)
 *   POST /memories   记一条新的互动(铁蛋的赛博账本)
 *   GET  /state      玩家状态(黑历史条数 / 恶作剧次数 / 最近几条)
 *   GET  /health     健康检查
 *
 * 认证:除 /health 外都需要 `Authorization: Bearer <SEEKDB_API_KEY>`。
 */
import express from "express";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { config } from "./config.mjs";
import { RoomStore } from "./store.mjs";
import { Embedder } from "./embedder.mjs";
import { CARDS } from "./cards.mjs";

const app = express();
app.use(express.json({ limit: "8mb" }));

const store = new RoomStore();
const embedder = new Embedder({
  modelDir: config.modelDir,
  onnxFile: config.onnxFile,
  ortDir: config.ortDir,
});

/* ------------------------------ 鉴权 ------------------------------ */
function auth(req, res, next) {
  const h = req.get("authorization") ?? "";
  const key = h.replace(/^Bearer\s+/i, "").trim();
  if (!key || key !== config.apiKey) {
    return res.status(401).json({ error: "invalid api key" });
  }
  next();
}

/* --------------------------- 健康检查 --------------------------- */
app.get("/health", async (_req, res) => {
  try {
    res.json({
      ok: true,
      service: "dify-seekdb-room",
      seekdbVersion: store.version,
      collection: store.cfg.collection,
      dimension: embedder.dim,
      docCount: await store.count(),
      cards: CARDS.length,
      apiKeyConfigured: Boolean(config.apiKey),
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

/* ------------------- Dify 外部知识库 API(检索) ------------------- */
app.post("/retrieval", auth, async (req, res) => {
  try {
    const { query = "", retrieval_setting = {} } = req.body ?? {};
    const topK = Number(retrieval_setting.top_k ?? config.cardTopK);
    const threshold = Number(retrieval_setting.score_threshold ?? 0);

    const embedding = await embedder.embedOne(query);
    const rows = await store.retrieveCards({
      queryEmbedding: embedding,
      queryText: query,
      kinds: ["card"],
      topK,
    });

    const records = rows
      .filter((r) => (threshold ? 1 - (r.distance ?? 1) >= threshold : true))
      .map((r) => ({
        content: r.document,
        score: Number((1 - (r.distance ?? 1)).toFixed(6)),
        title: r.metadata?.title ?? r.id,
        metadata: { ...r.metadata, card_id: r.id },
      }));

    res.json({ records });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

/* ------------------------- 黑历史:读 ------------------------- */
// POST 版本(Dify 的 HTTP 节点用 POST + JSON body,避免 query string 的转义坑)
app.post("/memories/search", auth, async (req, res) => {
  try {
    const userId = String(req.body?.user_id ?? "").trim();
    const q = String(req.body?.q ?? "").trim();
    const topK = Number(req.body?.top_k ?? config.memoryTopK);
    if (!userId) return res.status(400).json({ error: "user_id 必填" });
    const embedding = await embedder.embedOne(q || "玩家和铁蛋的互动");
    const rows = await store.retrieveMemories({ userId, queryEmbedding: embedding, queryText: q, topK });
    res.json({
      user_id: userId,
      memories: rows.map((r) => ({
        id: r.id,
        text: r.document,
        tag: r.metadata?.tag ?? null,
        turn: r.metadata?.turn ?? null,
        score: Number((1 - (r.distance ?? 1)).toFixed(6)),
      })),
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/memories", auth, async (req, res) => {
  try {
    const userId = String(req.query.user_id ?? "").trim();
    const q = String(req.query.q ?? "").trim();
    if (!userId) return res.status(400).json({ error: "user_id 必填" });
    const topK = Number(req.query.top_k ?? config.memoryTopK);
    const embedding = await embedder.embedOne(q || "玩家和铁蛋的互动");
    const rows = await store.retrieveMemories({
      userId,
      queryEmbedding: embedding,
      queryText: q,
      topK,
    });
    res.json({
      user_id: userId,
      memories: rows.map((r) => ({
        id: r.id,
        text: r.document,
        tag: r.metadata?.tag ?? null,
        turn: r.metadata?.turn ?? null,
        score: Number((1 - (r.distance ?? 1)).toFixed(6)),
      })),
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

/* ------------------------- 黑历史:写 ------------------------- */
app.post("/memories", auth, async (req, res) => {
  try {
    const { user_id: userId, text, tag = "chat", turn = null, role = "player" } = req.body ?? {};
    if (!userId || !text) return res.status(400).json({ error: "user_id 与 text 必填" });
    const finalTag = tag === "auto" ? classifyTag(String(text)) : tag;

    const embedding = await embedder.embedOne(String(text));
    const id = `M-${String(userId)}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    await store.upsert([
      {
        id,
        document: String(text),
        embedding,
        metadata: { kind: "memory", user_id: String(userId), tag: finalTag, turn, role },
      },
    ]);
    const state = await store.getState(String(userId));
    res.json({ ok: true, id, memoryCount: state.memoryCount, prankCount: state.prankCount });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

/** 判断这条互动是不是「恶作剧」(Dify 侧只管传原文,判定逻辑放在服务端,便于单测) */
function classifyTag(text) {
  const PRANK = /老板|老大|上司|端茶|倒水|命令|吩咐|骗|忽悠|偷|藏|恶作剧|整蛊|欺负|吓唬|威胁|滚|闭嘴|没用|垃圾机|破铜烂铁|拔电源|格式化/i;
  return PRANK.test(text) ? "prank" : "chat";
}

/* --------------------------- 玩家状态 --------------------------- */
app.post("/state", auth, async (req, res) => {
  try {
    const userId = String(req.body?.user_id ?? "").trim();
    if (!userId) return res.status(400).json({ error: "user_id 必填" });
    res.json(await store.getState(userId));
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});
app.get("/state", auth, async (req, res) => {
  try {
    const userId = String(req.query.user_id ?? "").trim();
    if (!userId) return res.status(400).json({ error: "user_id 必填" });
    res.json(await store.getState(userId));
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

/* --------------------------- 演示页 --------------------------- */
if (existsSync(config.demoDir)) {
  app.use(express.static(config.demoDir));
  app.get("/", (_req, res) => res.sendFile(resolve(config.demoDir, "index.html")));
}

async function main() {
  await store.init();
  await embedder.init();
  console.log(`[dify-seekdb] seekdb ${store.version} / 集合 ${store.cfg.collection}`);
  console.log(`[dify-seekdb] embedding 就绪 dim=${embedder.dim} (${config.onnxFile})`);
  app.listen(config.port, config.host, () => {
    console.log(`[dify-seekdb] 监听 http://${config.host}:${config.port}`);
  });
}

main().catch((e) => {
  console.error("[dify-seekdb] 启动失败:", e);
  process.exit(1);
});
