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
 * seekdb 数据层(Dify 赛题)
 *
 * 一张集合 `cyborg_room` 同时承载三类数据,靠 metadata.kind 区分:
 *   kind='card'    角色设定卡 / 场景卡 / 梗(给 Dify 知识检索节点用)
 *   kind='memory'  玩家与铁蛋的互动记录(黑历史 / 梗 / 偏好),带 user_id
 *   kind='state'   玩家状态快照(好感度、被恶作剧次数……)
 *
 * 检索全部走 seekdb 的 DBMS_HYBRID_SEARCH(向量 + 全文 + 结构化条件 + RRF),
 * 前端/Dify 只是把 query 向量传进来,不自己拼合两路结果。
 */
import {
  SeekdbClient,
  SeekdbAdminClient,
  Schema,
  FulltextIndexConfig,
  VectorIndexConfig,
} from "seekdb";

export const COLLECTION = process.env.SEEKDB_COLLECTION ?? "cyborg_room";
export const DIM = 384;

export class RoomStore {
  /**
   * seekdb 客户端在同一个连接上并发发 hybridSearch 会串响应
   * (两个请求的结果互相覆盖,表现为「查不到任何东西」),所以这里统一串行化。
   */
  _lock(fn) {
    const run = this._queue.then(fn, fn);
    this._queue = run.then(() => undefined, () => undefined);
    return run;
  }

  constructor(cfg = {}) {
    this._queue = Promise.resolve();
    this.cfg = {
      mode: process.env.SEEKDB_MODE ?? "server",
      host: process.env.SEEKDB_HOST ?? "127.0.0.1",
      port: Number(process.env.SEEKDB_PORT ?? 2881),
      user: process.env.SEEKDB_USER ?? "root",
      password: process.env.SEEKDB_PASSWORD ?? "",
      database: process.env.SEEKDB_DATABASE ?? "dify_kb",
      collection: COLLECTION,
      dimension: DIM,
      ...cfg,
    };
    this.client = null;
    this.collection = null;
  }

  async init() {
    const { mode, host, port, user, password, database } = this.cfg;
    if (mode === "server") {
      const admin = new SeekdbAdminClient({ host, port, user, password });
      try {
        const list = await admin.listDatabases();
        if (!(list ?? []).some((d) => d.name === database)) await admin.createDatabase(database);
      } finally {
        await admin.close?.();
      }
    }
    this.client = new SeekdbClient(
      mode === "server"
        ? { host, port, user, password, database }
        : { path: process.env.SEEKDB_PATH ?? "./data/seekdb", database },
    );
    this.collection = await this.client.getOrCreateCollection({
      name: this.cfg.collection,
      schema: new Schema({
        fulltextIndex: new FulltextIndexConfig("ik", { ik_mode: "smart" }),
        vectorIndex: new VectorIndexConfig({
          hnsw: { dimension: this.cfg.dimension, distance: "cosine" },
          embeddingFunction: null,
        }),
      }),
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

  /* ------------------------------------------------------------------ */
  /* 写入                                                                */
  /* ------------------------------------------------------------------ */

  /** 批量写入/更新(upsert,重复执行不会报主键冲突) */
  async upsert(rows) {
    await this.collection.upsert({
      ids: rows.map((r) => r.id),
      documents: rows.map((r) => r.document),
      embeddings: rows.map((r) => r.embedding),
      metadatas: rows.map((r) => r.metadata),
    });
    await this.collection.refresh_index();
  }

  /* ------------------------------------------------------------------ */
  /* 检索                                                                */
  /* ------------------------------------------------------------------ */

  /**
   * 角色设定卡 / 场景卡检索:向量 + 全文 + kind 过滤
   * @returns {Array<{id,document,metadata,score}>}
   */
  async retrieveCards(args) {
    return this._lock(() => this._retrieveCards(args));
  }

  async _retrieveCards({ queryEmbedding, queryText = "", kinds = ["card"], topK = 4 }) {
    // metadata 过滤必须用运算符写法($eq),裸值会被拼成非法的 "metadata.kind = ?" 语义
    const where =
      kinds.length === 1
        ? { kind: { $eq: kinds[0] } }
        : { $or: kinds.map((k) => ({ kind: { $eq: k } })) };
    const whereDocument = queryText ? { $contains: queryText } : undefined;
    const res = await this.collection.hybridSearch({
      query: { where, ...(whereDocument ? { whereDocument } : {}) },
      // 结构化过滤必须同时加在 knn 分支上:混合检索是 full join,
      // 只过滤全文分支的话,向量分支仍会把不满足条件的行带回来。
      knn: { queryEmbeddings: [queryEmbedding], where },
      rank: { rrf: { rankWindowSize: 60, rankConstant: 60 } },
      nResults: topK,
    });
    return this._rows(res);
  }

  /**
   * 玩家黑历史检索:向量 + 结构化条件(user_id + kind=memory)
   */
  async retrieveMemories(args) {
    return this._lock(() => this._retrieveMemories(args));
  }

  async _retrieveMemories({ userId, queryEmbedding, queryText = "", topK = 5 }) {
    const where = { kind: { $eq: "memory" }, user_id: { $eq: userId } };
    const whereDocument = queryText ? { $contains: queryText } : undefined;
    const res = await this.collection.hybridSearch({
      query: { where, ...(whereDocument ? { whereDocument } : {}) },
      knn: { queryEmbeddings: [queryEmbedding], where },
      rank: { rrf: { rankWindowSize: 60, rankConstant: 60 } },
      nResults: topK,
    });
    return this._rows(res);
  }

  _rows(res) {
    const ids = res.ids?.[0] ?? [];
    const docs = res.documents?.[0] ?? [];
    const metas = res.metadatas?.[0] ?? [];
    const dists = res.distances?.[0] ?? [];
    return ids.map((id, i) => ({
      id,
      document: docs[i] ?? "",
      metadata: metas[i] ?? {},
      distance: dists[i] ?? null,
    }));
  }

  /** 玩家状态:黑历史条数 / 恶作剧次数 / 最近几条 */
  async getState(userId) {
    return this._lock(() => this._getState(userId));
  }

  async _getState(userId) {
    const where = { kind: { $eq: "memory" }, user_id: { $eq: userId } };
    const res = await this.collection.hybridSearch({
      query: { where },
      knn: { queryEmbeddings: [new Array(DIM).fill(0)], where },
      nResults: 50,
    });
    const rows = this._rows(res);
    const pranks = rows.filter((r) => r.metadata?.tag === "prank");
    return {
      userId,
      memoryCount: rows.length,
      prankCount: pranks.length,
      recent: rows.slice(0, 5).map((r) => ({
        id: r.id,
        text: r.document,
        tag: r.metadata?.tag ?? null,
        turn: r.metadata?.turn ?? null,
      })),
    };
  }

  async count() {
    try {
      return await this.collection.count();
    } catch {
      return 0;
    }
  }

  async close() {
    await this.client?.close?.();
  }
}
