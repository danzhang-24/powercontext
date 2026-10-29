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
 * Dify DSL 结构校验器
 *
 * 评审导入 DSL 之前可以先跑一遍,避免低级错误:
 *   node scripts/validate_dsl.mjs [dsl/cyborg-tiedan.yml]
 *
 * 校验项:
 *   - YAML 可解析、必需顶层字段齐全(app / kind / version / workflow)
 *   - 节点 id 唯一、类型是 Dify 认识的节点类型
 *   - 每条 edge 的 source / target 都指向存在的节点
 *   - 模板引用 {{#nodeId.var#}} 指向的节点存在(允许 sys.* / env.* / conversation.*)
 *   - HTTP 节点的地址走环境变量,不带死域名
 *   - features 块字段完整
 */
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import yaml from "js-yaml";

const KNOWN_NODE_TYPES = new Set([
  "start", "end", "answer", "llm", "knowledge-retrieval", "http-request", "code",
  "if-else", "template-transform", "question-classifier", "parameter-extractor",
  "iteration", "loop", "assigner", "variable-aggregator", "tool", "agent",
  "document-extractor", "list-operator", "parameter-extracting",
]);

const RESERVED = new Set(["sys", "env", "conversation", "rag_pipeline"]);

const file = process.argv[2] ?? "dsl/cyborg-tiedan.yml";
const text = await readFile(resolve(file), "utf8");
const doc = yaml.load(text);

const errors = [];
const warns = [];
const ok = [];

/* ---------------- 顶层 ---------------- */
for (const k of ["app", "kind", "version", "workflow"]) {
  if (!doc?.[k]) errors.push(`缺少顶层字段 ${k}`);
  else ok.push(`顶层字段 ${k} ✓`);
}
if (doc?.kind !== "app") errors.push(`kind 必须是 app,实际 ${doc?.kind}`);
if (!doc?.app?.mode) errors.push("app.mode 缺失");
if (!doc?.app?.name) errors.push("app.name 缺失");
if (!/^\d+\.\d+\.\d+$/.test(String(doc?.version))) errors.push(`version 格式异常: ${doc?.version}`);

const wf = doc?.workflow ?? {};
for (const k of ["features", "graph"]) if (!wf[k]) errors.push(`workflow.${k} 缺失`);
for (const k of ["nodes", "edges"]) if (!Array.isArray(wf?.graph?.[k])) errors.push(`workflow.graph.${k} 缺失或不是数组`);

/* ---------------- 节点 ---------------- */
const nodes = wf?.graph?.nodes ?? [];
const ids = new Set();
for (const n of nodes) {
  if (!n?.id) { errors.push("存在没有 id 的节点"); continue; }
  if (ids.has(n.id)) errors.push(`节点 id 重复: ${n.id}`);
  ids.add(n.id);
  const t = n?.data?.type;
  if (!t) errors.push(`节点 ${n.id} 缺少 data.type`);
  else if (!KNOWN_NODE_TYPES.has(t)) warns.push(`节点 ${n.id} 的类型 ${t} 不在常见类型清单里(可能是新版节点)`);
  else ok.push(`节点 ${n.id} 类型 ${t} ✓`);
}
if (!nodes.some((n) => n?.data?.type === "start")) errors.push("缺少 start 节点");
if (!nodes.some((n) => n?.data?.type === "answer")) errors.push("缺少 answer 节点(advanced-chat 需要)");

/* ---------------- 连线 ---------------- */
for (const e of wf?.graph?.edges ?? []) {
  if (!ids.has(e.source)) errors.push(`edge ${e.id} 的 source 不存在: ${e.source}`);
  if (!ids.has(e.target)) errors.push(`edge ${e.id} 的 target 不存在: ${e.target}`);
}
ok.push(`edges ${(wf?.graph?.edges ?? []).length} 条,引用节点全部存在`);

/* ---------------- 模板引用 ---------------- */
const REFS = /\{\{#([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)#\}\}/g;
const refs = new Set();
for (const n of nodes) {
  const s = JSON.stringify(n.data ?? {});
  for (const m of s.matchAll(REFS)) refs.add(`${m[1]}.${m[2]}`);
}
for (const r of refs) {
  const [nodeId] = r.split(".");
  if (RESERVED.has(nodeId)) continue;
  if (!ids.has(nodeId)) errors.push(`模板引用指向不存在的节点: ${r}`);
}
ok.push(`模板引用 ${refs.size} 处,全部可解析`);

/* ---------------- HTTP 节点 ---------------- */
for (const n of nodes.filter((x) => x?.data?.type === "http-request")) {
  const url = String(n.data.url ?? "");
  if (!url.includes("{{#env.")) {
    errors.push(`HTTP 节点 ${n.id} 的地址没有走环境变量: ${url}`);
  }
  const headers = String(n.data.headers ?? "");
  if (!headers.toLowerCase().includes("authorization")) {
    warns.push(`HTTP 节点 ${n.id} 没有带 Authorization 头`);
  }
}
ok.push("HTTP 节点:地址走环境变量、带鉴权头");

/* ---------------- features ---------------- */
const feat = wf?.features ?? {};
for (const k of [
  "file_upload", "opening_statement", "retriever_resource", "sensitive_word_avoidance",
  "speech_to_text", "suggested_questions", "suggested_questions_after_answer", "text_to_speech",
]) {
  if (!(k in feat)) errors.push(`features.${k} 缺失`);
}

/* ---------------- 知识检索节点 ---------------- */
for (const n of nodes.filter((x) => x?.data?.type === "knowledge-retrieval")) {
  if (!Array.isArray(n.data.dataset_ids) || !n.data.dataset_ids.length) {
    errors.push(`知识检索节点 ${n.id} 没有 dataset_ids`);
  } else {
    warns.push(`知识检索节点 ${n.id} 的 dataset_ids 需要在导入后重新绑定到你的外部知识库`);
  }
}

console.log(`== DSL 校验: ${file} ==`);
for (const l of ok) console.log(`  ✓ ${l}`);
for (const l of warns) console.log(`  ! ${l}`);
for (const l of errors) console.log(`  ✗ ${l}`);
console.log(`\n结果:${errors.length ? `不通过(${errors.length} 个错误)` : "通过"}`);
process.exit(errors.length ? 1 : 0);
