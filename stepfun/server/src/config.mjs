/**
 * 运行配置。所有配置项都可以用环境变量覆盖,便于同一份代码在
 * 「嵌入式(embedded)」与「本地 server」两种 seekdb 部署方式之间切换。
 */
import { resolve } from "node:path";

const num = (v, d) => (v === undefined || v === "" ? d : Number(v));
const bool = (v, d) => (v === undefined || v === "" ? d : /^(1|true|yes|on)$/i.test(v));

export const config = {
  /* ---------------- 本地 API server ---------------- */
  apiPort: num(process.env.PORT, 8787),
  apiHost: process.env.HOST ?? "0.0.0.0",

  /* ---------------- seekdb 连接 ---------------- */
  /** 部署方式:embedded(默认,本地目录) | server(连接 seekdb/OceanBase 服务) */
  mode: (process.env.SEEKDB_MODE ?? (process.env.SEEKDB_HOST ? "server" : "embedded")).toLowerCase(),

  /** embedded 模式的数据目录。
   *  注意:必须放在本地文件系统上。NFS / 对象存储挂载下 seekdb 的日志块
   *  直写(O_DIRECT)会失败,表现为 block manager / pwrite 报错。 */
  path: process.env.SEEKDB_PATH ?? resolve(process.cwd(), "data/seekdb"),

  /** server 模式连接参数 */
  dbHost: process.env.SEEKDB_HOST ?? "127.0.0.1",
  dbPort: num(process.env.SEEKDB_PORT, 2881),
  user: process.env.SEEKDB_USER ?? "root",
  password: process.env.SEEKDB_PASSWORD ?? "",
  database: process.env.SEEKDB_DATABASE ?? "stepfun_kb",
  tenant: process.env.SEEKDB_TENANT || undefined,

  /** 集合名与向量维度(all-MiniLM-L6-v2 -> 384 维) */
  collection: process.env.SEEKDB_COLLECTION ?? "kb_documents",
  dimension: num(process.env.SEEKDB_DIMENSION, 384),

  /** 全文索引分词器:ik(中文) | ngram | basic */
  analyzer: process.env.SEEKDB_ANALYZER ?? "ik",

  /** 全文检索分支形态:raw(数据库自己分词) | keywords(前端抽词) | both */
  fulltextMode: (process.env.SEEKDB_FT_MODE ?? "keywords").toLowerCase(),

  /** RRF 融合参数 */
  rrfWindow: num(process.env.SEEKDB_RRF_WINDOW, 60),
  rrfConstant: num(process.env.SEEKDB_RRF_CONSTANT, 60),

  /** 是否在写入后立刻刷新向量索引(保证新导入文档立即可检索) */
  refreshOnWrite: bool(process.env.SEEKDB_REFRESH_ON_WRITE, true),

  /** 静态资源目录(生产模式下由本服务直接托管前端产物) */
  webDist: process.env.WEB_DIST ?? resolve(process.cwd(), "web/dist"),
};
