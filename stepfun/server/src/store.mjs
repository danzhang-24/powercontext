/**
 * seekdb 数据层封装
 *
 * 职责边界(与赛题要求一致):
 *   - 向量、原文、元数据全部落在 seekdb;
 *   - 混合检索(全文 + 向量)完全交给 seekdb 的 DBMS_HYBRID_SEARCH 执行,
 *     服务端只负责把「浏览器端算好的 query 向量」和「关键词」传进去,
 *     绝不在客户端/服务端分别取两路结果再自己拼合;
 *   - 写入后调用 refresh_index() 刷新索引,保证增量导入立即可检索。
 */
import {
  SeekdbClient,
  SeekdbAdminClient,
  Schema,
  FulltextIndexConfig,
  VectorIndexConfig,
} from "seekdb";
import { config } from "./config.mjs";

export class KnowledgeStore {
  constructor(cfg = config) {
    this.cfg = cfg;
    this.client = null;
    this.collection = null;
    this.version = null;
    this.mode = cfg.mode;
  }

  async init() {
    const { mode, path, dbHost, dbPort, user, password, database, tenant } = this.cfg;

    const args =
      mode === "server"
        ? { host: dbHost, port: dbPort, user, password, database, ...(tenant ? { tenant } : {}) }
        : { path, database };

    if (mode === "server") await this.ensureDatabase({ host: dbHost, port: dbPort, user, password, database });

    this.client = new SeekdbClient(args);
    this.collection = await this.client.getOrCreateCollection({
      name: this.cfg.collection,
      schema: this.buildSchema(),
      // 显式置 null:向量由浏览器端产出,数据库侧不挂任何 embedding function,
      // 也就不需要安装 @seekdb/default-embed。
      embeddingFunction: null,
    });

    try {
      const rows = await this.client.execute("SELECT VERSION() AS version");
      this.version = rows?.[0]?.version ?? null;
    } catch {
      this.version = null;
    }
    return this;
  }

  /** server 模式下确保目标 database 存在(嵌入式模式由 SDK 自动管理) */
  async ensureDatabase({ host, port, user, password, database }) {
    const admin = new SeekdbAdminClient({ host, port, user, password });
    try {
      const list = await admin.listDatabases();
      const exists = (list ?? []).some((d) => d.name === database);
      if (!exists) {
        await admin.createDatabase(database);
        this.createdDatabase = true;
      }
    } finally {
      await admin.close?.();
    }
  }

  /** 集合 schema:document 列建全文索引,embedding 列建 HNSW 向量索引。 */
  buildSchema() {
    const schema = new Schema({
      fulltextIndex: new FulltextIndexConfig(this.cfg.analyzer, {
        ik_mode: "smart",
      }),
      vectorIndex: new VectorIndexConfig({
        hnsw: { dimension: this.cfg.dimension, distance: "cosine" },
        // 向量全部由浏览器端 Transformers.js/ONNX Runtime Web 产出,
        // 数据库侧不再挂任何 embedding function。
        embeddingFunction: null,
      }),
    });
    return schema;
  }

  /** 写入文档并刷新索引 */
  async addDocuments({ ids, documents, embeddings, metadatas }) {
    const t0 = performance.now();
    // 用 upsert 而不是 add:重复导入同一份内容时是「更新」而不是报主键冲突,
    // 这样增量导入可以随时重跑,不会把知识库搞坏。
    await this.collection.upsert({ ids, documents, embeddings, metadatas });
    const tWrite = performance.now() - t0;

    let tRefresh = 0;
    if (this.cfg.refreshOnWrite) {
      const t1 = performance.now();
      await this.collection.refresh_index();
      tRefresh = performance.now() - t1;
    }
    return { writeMs: tWrite, refreshMs: tRefresh };
  }

  /**
   * 混合检索:向量分支用浏览器端算好的 query 向量,全文分支用查询文本/关键词,
   * 两路结果在 seekdb 内部用 RRF 融合后一次性返回。
   *
   * 全文分支的三种形态(SEEKDB_FT_MODE):
   *   raw      —— 把原始查询交给 seekdb 的全文索引自己分词(ik),最贴近数据库原生能力
   *   keywords —— 用前端抽好的关键词做 OR 匹配
   *   both     —— 两者取并集,召回更稳
   */
  async hybridSearch({ queryEmbedding, queryText = "", keywords = [], nResults = 10 }) {
    const t0 = performance.now();
    const query = this.buildFulltextQuery({ queryText, keywords });

    const res = await this.collection.hybridSearch({
      ...(query ? { query } : {}),
      knn: { queryEmbeddings: [queryEmbedding] },
      rank: { rrf: { rankWindowSize: this.cfg.rrfWindow, rankConstant: this.cfg.rrfConstant } },
      nResults,
    });

    const ids = res.ids?.[0] ?? [];
    const docs = res.documents?.[0] ?? [];
    const metas = res.metadatas?.[0] ?? [];
    const dists = res.distances?.[0] ?? [];

    return {
      results: ids.map((id, i) => ({
        id,
        document: docs[i] ?? "",
        metadata: metas[i] ?? {},
        distance: dists[i] ?? null,
      })),
      searchMs: performance.now() - t0,
    };
  }

  /** 构造全文检索分支(query_string 表达式) */
  buildFulltextQuery({ queryText, keywords }) {
    const mode = this.cfg.fulltextMode;
    const raw = String(queryText ?? "").trim();
    const kws = (keywords ?? []).filter(Boolean);
    const clauses = [];

    if ((mode === "raw" || mode === "both") && raw) {
      // 去掉 query_string 的运算符字符,保留中英文、数字与空白
      const safe = raw.replace(/[+\-=&|><!(){}\[\]^"~*?:\\/]+/g, " ").replace(/\s+/g, " ").trim();
      if (safe) clauses.push({ $contains: safe });
    }
    if ((mode === "keywords" || mode === "both") && kws.length) {
      clauses.push(...kws.map((k) => ({ $contains: k })));
    }

    if (!clauses.length) return undefined;
    if (clauses.length === 1) return { whereDocument: clauses[0] };
    return { whereDocument: { $or: clauses } };
  }

  async count() {
    try {
      return await this.collection.count();
    } catch {
      return 0;
    }
  }

  /** 清空集合(演示用):删表重建,保证索引与元数据完全干净 */
  async reset() {
    try {
      await this.client.deleteCollection(this.cfg.collection);
    } catch {
      /* 集合不存在时忽略 */
    }
    this.collection = await this.client.createCollection({
      name: this.cfg.collection,
      schema: this.buildSchema(),
      embeddingFunction: null,
    });
    return this.collection;
  }

  async close() {
    await this.client?.close?.();
  }
}
