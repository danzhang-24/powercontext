/**
 * 初始化:把设定卡向量化后写进 seekdb
 *
 * 用法:node service/src/seed.mjs
 */
import { RoomStore } from "./store.mjs";
import { Embedder } from "./embedder.mjs";
import { CARDS } from "./cards.mjs";
import { config } from "./config.mjs";

const store = new RoomStore();
const embedder = new Embedder({
  modelDir: config.modelDir,
  onnxFile: config.onnxFile,
  ortDir: config.ortDir,
});

await store.init();
console.log(`[seed] seekdb ${store.version} / 集合 ${store.cfg.collection}`);
await embedder.init();


const vectors = await embedder.embed(CARDS.map((c) => `${c.title}。${c.text}`));
console.log(`[seed] ${CARDS.length} 张卡片已向量化 dim=${embedder.dim}`);

const rows = CARDS.map((c, i) => ({
  id: c.id,
  document: `${c.title}。${c.text}`,
  embedding: vectors[i],
  metadata: {
    kind: "card",
    tag: c.tag,
    title: c.title,
    keywords: c.keywords,
  },
}));

await store.upsert(rows);
console.log(`[seed] 写入完成,集合当前 ${await store.count()} 条`);
await store.close();
process.exit(0);
