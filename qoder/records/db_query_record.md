# seekdb 查询记录

共执行 120 条 SQL，全部为项目运行时的真实调用（未做任何删改）。

| # | 步骤 | 命中行数 | 耗时(ms) | 说明 | SQL |
| --- | --- | --- | --- | --- | --- |
| 1 | 未标注 | 0 | 12.872 | 删除旧模型 pp_embed | `CALL DBMS_AI_SERVICE.DROP_AI_MODEL('pp_embed')` |
| 2 | 未标注 | 0 | 3.578 | 删除旧端点 pp_embed | `CALL DBMS_AI_SERVICE.DROP_AI_MODEL_ENDPOINT('pp_embed')` |
| 3 | 未标注 | 0 | 6.450 | 删除旧模型 pp_summarizer | `CALL DBMS_AI_SERVICE.DROP_AI_MODEL('pp_summarizer')` |
| 4 | 未标注 | 0 | 2.525 | 删除旧端点 pp_summarizer | `CALL DBMS_AI_SERVICE.DROP_AI_MODEL_ENDPOINT('pp_summarizer')` |
| 5 | 未标注 | 0 | 8.674 | 注册嵌入模型 pp_embed | `CALL DBMS_AI_SERVICE.CREATE_AI_MODEL('pp_embed', '{"type":"DENSE_EMBEDDING","model_name":"paperpocket-local"}')` |
| 6 | 未标注 | 0 | 5.292 | 注册嵌入端点 pp_embed | `CALL DBMS_AI_SERVICE.CREATE_AI_MODEL_ENDPOINT('pp_embed', '{"ai_model_name":"pp_embed","url":"http://127.0.0.1:8300/v1/embeddings","access_key":"local","provider":"openai","request_model_name":"paperpocket-local"}')` |
| 7 | 未标注 | 0 | 5.591 | 注册摘要模型 pp_summarizer | `CALL DBMS_AI_SERVICE.CREATE_AI_MODEL('pp_summarizer', '{"type":"COMPLETION","model_name":"paperpocket-local"}')` |
| 8 | 未标注 | 0 | 4.420 | 注册摘要端点 pp_summarizer | `CALL DBMS_AI_SERVICE.CREATE_AI_MODEL_ENDPOINT('pp_summarizer', '{"ai_model_name":"pp_summarizer","url":"http://127.0.0.1:8300/v1/chat/completions","access_key":"local","provider":"openai","request_model_name":"paperpocket-local"}')` |
| 9 | 未标注 | 1 | 0.473 | 探测 AI 模型是否已注册 | `SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = 'pp_embed'` |
| 10 | 未标注 | 1 | 0.544 | 探测 AI 模型端点是否已注册 | `SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS WHERE AI_MODEL_NAME = 'pp_embed'` |
| 11 | 未标注 | 1 | 0.333 | 探测摘要模型是否已注册 | `SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = 'pp_summarizer'` |
| 12 | 未标注 | 1 | 0.353 | 探测摘要端点是否已注册 | `SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS WHERE AI_MODEL_NAME = 'pp_summarizer'` |
| 13 | 建库建表 | 1 | 15.224 | 建库建表 | `CREATE DATABASE IF NOT EXISTS `paperpocket`` |
| 14 | 建库建表 | 0 | 2.279 | 建库建表 | `USE `paperpocket`` |
| 15 | 建库建表 | 0 | 56.618 | 建库建表 | `CREATE TABLE IF NOT EXISTS papers (             doc_key VARCHAR(96) NOT NULL,             title VARCHAR(512) NOT NULL,             authors VARCHAR(512) NOT NULL DEFAULT '',             year INT NOT NULL DEFAULT 0,             venue VARCHAR(256) NOT NULL DEFAULT '',             tags VARCHAR(256) NOT NULL DEFAULT '',             kind VARCHAR(32) NOT NULL DEFAULT 'paper',             source_path VARCHAR(512) NOT NULL DEFAULT '',             summary MEDIUMTEXT,             content MEDIUMTEXT NOT NULL,             emb VECTOR(64),             created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP         )` |
| 16 | 建库建表 | 0 | 31.070 | 建库建表 | `CREATE TABLE IF NOT EXISTS paper_chunks (             chunk_key VARCHAR(128) NOT NULL,             doc_key VARCHAR(96) NOT NULL,             title VARCHAR(512) NOT NULL,             authors VARCHAR(512) NOT NULL DEFAULT '',             year INT NOT NULL DEFAULT 0,             venue VARCHAR(256) NOT NULL DEFAULT '',             tags VARCHAR(256) NOT NULL DEFAULT '',             heading VARCHAR(256) NOT NULL DEFAULT '',             seq INT NOT NULL DEFAULT 0,             source_path VARCHAR(512) NOT NULL DEFAULT '',             start_line INT NOT NULL DEFAULT 0,             end_line INT NOT NULL DEFAULT 0,             content MEDIUMTEXT NOT NULL,             emb VECTOR(64),             created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP         )` |
| 17 | 建库建表 | 0 | 29.571 | 建库建表 | `CREATE TABLE IF NOT EXISTS reading_log (             id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,             doc_key VARCHAR(96) NOT NULL DEFAULT '',             chunk_key VARCHAR(128) NOT NULL DEFAULT '',             action VARCHAR(32) NOT NULL,             query_text VARCHAR(512) NOT NULL DEFAULT '',             score DOUBLE NOT NULL DEFAULT 0,             detail TEXT,             created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP         )` |
| 18 | 建库建表 | 0 | 27.131 | 建库建表 | `CREATE TABLE IF NOT EXISTS briefs (             id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,             query_text VARCHAR(512) NOT NULL,             brief_md MEDIUMTEXT NOT NULL,             engine VARCHAR(32) NOT NULL,             model_name VARCHAR(64) NOT NULL DEFAULT '',             source_keys TEXT,             created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP         )` |
| 19 | 建索引 | 0 | 6.409 | 查看 papers 的索引 | `SHOW INDEX FROM `paperpocket`.`papers`` |
| 20 | 建索引 | 0 | 74.877 | 建索引 | `CREATE UNIQUE INDEX uk_papers_doc ON papers (doc_key)` |
| 21 | 建索引 | 0 | 4.322 | 查看 paper_chunks 的索引 | `SHOW INDEX FROM `paperpocket`.`paper_chunks`` |
| 22 | 建索引 | 0 | 28.347 | 建索引 | `CREATE UNIQUE INDEX uk_chunks_key ON paper_chunks (chunk_key)` |
| 23 | 建索引 | 0 | 39.948 | 建索引 | `CREATE INDEX idx_chunks_doc ON paper_chunks (doc_key)` |
| 24 | 建索引 | 0 | 34.156 | 建索引 | `CREATE INDEX idx_chunks_year ON paper_chunks (year)` |
| 25 | 建索引 | 0 | 463.359 | 建索引 | `CREATE FULLTEXT INDEX ft_papers ON papers (title, content) WITH PARSER ngram` |
| 26 | 建索引 | 0 | 330.513 | 建索引 | `CREATE FULLTEXT INDEX ft_chunks ON paper_chunks (title, content) WITH PARSER ngram` |
| 27 | 建索引 | 0 | 437.198 | 建索引 | `CREATE VECTOR INDEX vi_papers ON papers (emb) WITH (distance=l2, type=hnsw, lib=vsag)` |
| 28 | 建索引 | 0 | 426.536 | 建索引 | `CREATE VECTOR INDEX vi_chunks ON paper_chunks (emb) WITH (distance=l2, type=hnsw, lib=vsag)` |
| 29 | 建索引 | 1 | 2.671 | 探测 AI 模型是否已注册 | `SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = 'pp_embed'` |
| 30 | 建索引 | 1 | 2.556 | 探测 AI 模型端点是否已注册 | `SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS WHERE AI_MODEL_NAME = 'pp_embed'` |
| 31 | 导入资料 | 0 | 6.208 | 清理旧段落 实验记录-邻居采样规模对图分类精度的影响 | `DELETE FROM paper_chunks WHERE doc_key = '实验记录-邻居采样规模对图分类精度的影响'` |
| 32 | 导入资料 | 0 | 3.501 | 清理旧论文 实验记录-邻居采样规模对图分类精度的影响 | `DELETE FROM papers WHERE doc_key = '实验记录-邻居采样规模对图分类精度的影响'` |
| 33 | 导入资料 | 1 | 0.662 | 探测 AI 模型是否已注册 | `SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = 'pp_embed'` |
| 34 | 导入资料 | 1 | 0.520 | 探测 AI 模型端点是否已注册 | `SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS WHERE AI_MODEL_NAME = 'pp_embed'` |
| 35 | 导入资料 | 1 | 20.053 | 写入论文 实验记录-邻居采样规模对图分类精度的影响 | `INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', 'note', 'notes/实验记录-邻居采样规模.md', '- 验证"邻居采样数量"这一超参对图分类精度的影响，并观察不同聚合算子（sum / mean / max / attention）之间的差异。\n- Cora 上采样 10 个邻居时精度最高，均值 0.813，标准差 0.009；\n- Citeseer 上采样 5 个邻居均值 0.706，采样全部邻居均值 0.712，差异在标准差范围内。\n来源：# 实验目的', '# 实验目的\n\n验证"邻居采样数量"这一超参对图分类精度的影响，并观察不同聚合算子（sum / mean / max / attention）之间的差异。\n\n# 实验设置\n\n数据集使用 Cora 与 Citeseer 两个引文网络，统一两层 GCN，第一层隐层维度 64，第二层 128，dropout 0.5，优化器 Adam，学习率 0.01，权重衰减 5e-4。采样邻居数分别取 5、10、20、全部。每个配置重复 10 次取均值与标准差。\n\n# 实验结果\n\nCora 上采样 10 个邻居时精度最高，均值 0.813，标准差 0.009；采样全部邻居均值 0.807，标准差 0.007。Citeseer 上采样 5 个邻居均值 0.706，采样全部邻居均值 0.712，差异在标准差范围内。\n\n注意力聚合在两个数据集上都略优于 sum 聚合，Cora 上均值 0.822 / Citeseer 上 0.715，但参数量与显存开销明显更高，训练时间约是 sum 聚合的 2.3 倍。\n\n# 结论与反思\n\n采���数量存在甜点区，太少会丢失信息，太多则增加计算量且收益有限。注意力聚合的优势在引文网络这种同配图上并不明显，在异配图上可能更值得关注——这一点还需要补充实验。\n\n# 下一步\n\n1. 补做 heterophilous 数据集（如 Texas）上的对比；\n2. 记录训练过程中的显存占用曲线；\n3. 把固定随机种子的配置写进实验脚本，保证结果可复现。', AI_EMBED('pp_embed', '实验记录：邻居采样规模对图分类精度的影响\n# 实验目的\n\n验证"邻居采样数量"这一超参对图分类精度的影响，并观察不同聚合算子（sum / mean / max / attention）之间的差异。\n\n# 实验设置\n\n数据集使用 Cora 与 Citeseer 两个引文网络，统一两层 GCN，第一层隐层维度 64，第二层 128，dropout 0.5，优化器 Adam，学习率 0.01，权重衰减 5e-4。采样邻居数分别取 5、10、20、全部。每个配置重复 10 次取均值与标准差。\n\n# 实验结果\n\nCora 上采样 10 个邻居时精度最高，均值 0.813，标准差 0.009；采样全部邻居均值 0.807，标准差 0.007。Citeseer 上采样 5 个邻居均值 0.706，采样全部邻居均值 0.712，差异在标准差范围内。\n\n注意力聚合在两个数据集上都略优于 sum 聚合，Cora 上均值 0.822 / Citeseer 上 0.715，但参数量与显存开销明显更高，训练时间约是 sum 聚合的 2.3 倍。\n\n# 结论与反思\n\n采���数量存在甜点区，太少会丢失信息，太多则增加计算量且收益有限。注意力聚合的优势在引文网络这种同配图上并不明显，在异配图上可能更值得关注——这一点还需要补充实验。\n\n# 下一步\n\n1. 补做 heterophilous 数据集（如 Texas）上的对比；\n2. 记录训练过程中的显存占用曲线；\n3. 把固定随机种子的配置写进实验脚本，保证结果可复现。'))` |
| 36 | 导入资料 | 1 | 10.847 | 写入段落 实验记录-邻居采样规模对图分类精度的影响#000 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响#000', '实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', '实验目的', 0, 'notes/实验记录-邻居采样规模.md', 2, 4, '验证"邻居采样数量"这一超参对图分类精度的影响，并观察不同聚合算子（sum / mean / max / attention）之间的差异。', AI_EMBED('pp_embed', '实验目的\n验证"邻居采样数量"这一超参对图分类精度的影响，并观察不同聚合算子（sum / mean / max / attention）之间的差异。'))` |
| 37 | 导入资料 | 1 | 5.506 | 写入段落 实验记录-邻居采样规模对图分类精度的影响#001 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响#001', '实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', '实验设置', 1, 'notes/实验记录-邻居采样规模.md', 6, 8, '数据集使用 Cora 与 Citeseer 两个引文网络，统一两层 GCN，第一层隐层维度 64，第二层 128，dropout 0.5，优化器 Adam，学习率 0.01，权重衰减 5e-4。采样邻居数分别取 5、10、20、全部。每个配置重复 10 次取均值与标准差。', AI_EMBED('pp_embed', '实验设置\n数据集使用 Cora 与 Citeseer 两个引文网络，统一两层 GCN，第一层隐层维度 64，第二层 128，dropout 0.5，优化器 Adam，学习率 0.01，权重衰减 5e-4。采样邻居数分别取 5、10、20、全部。每个配置重复 10 次取均值与标准差。'))` |
| 38 | 导入资料 | 1 | 4.863 | 写入段落 实验记录-邻居采样规模对图分类精度的影响#002 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响#002', '实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', '实验结果', 2, 'notes/实验记录-邻居采样规模.md', 10, 14, 'Cora 上采样 10 个邻居时精度最高，均值 0.813，标准差 0.009；采样全部邻居均值 0.807，标准差 0.007。Citeseer 上采样 5 个邻居均值 0.706，采样全部邻居均值 0.712，差异在标准差范围内。\n\n注意力聚合在两个数据集上都略优于 sum 聚合，Cora 上均值 0.822 / Citeseer 上 0.715，但参数量与显存开销明显更高，训练时间约是 sum 聚合的 2.3 倍。', AI_EMBED('pp_embed', '实验结果\nCora 上采样 10 个邻居时精度最高，均值 0.813，标准差 0.009；采样全部邻居均值 0.807，标准差 0.007。Citeseer 上采样 5 个邻居均值 0.706，采样全部邻居均值 0.712，差异在标准差范围内。\n\n注意力聚合在两个数据集上都略优于 sum 聚合，Cora 上均值 0.822 / Citeseer 上 0.715，但参数量与显存开销明显更高，训练时间约是 sum 聚合的 2.3 倍。'))` |
| 39 | 导入资料 | 1 | 6.818 | 写入段落 实验记录-邻居采样规模对图分类精度的影响#003 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响#003', '实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', '结论与反思', 3, 'notes/实验记录-邻居采样规模.md', 16, 18, '采���数量存在甜点区，太少会丢失信息，太多则增加计算量且收益有限。注意力聚合的优势在引文网络这种同配图上并不明显，在异配图上可能更值得关注——这一点还需要补充实验。', AI_EMBED('pp_embed', '结论与反思\n采���数量存在甜点区，太少会丢失信息，太多则增加计算量且收益有限。注意力聚合的优势在引文网络这种同配图上并不明显，在异配图上可能更值得关注——这一点还需要补充实验。'))` |
| 40 | 导入资料 | 1 | 3.920 | 写入段落 实验记录-邻居采样规模对图分类精度的影响#004 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响#004', '实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', '下一步', 4, 'notes/实验记录-邻居采样规模.md', 20, 23, '1. 补做 heterophilous 数据集（如 Texas）上的对比；\n2. 记录训练过程中的显存占用曲线；\n3. 把固定随机种子的配置写进实验脚本，保证结果可复现。', AI_EMBED('pp_embed', '下一步\n1. 补做 heterophilous 数据集（如 Texas）上的对比；\n2. 记录训练过程中的显存占用曲线；\n3. 把固定随机种子的配置写进实验脚本，保证结果可复现。'))` |
| 41 | 导入资料 | 1 | 10.940 | 记录日志 ingest | `INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('实验记录-邻居采样规模对图分类精度的影响', '', 'ingest', '', 0, '导入 5 个段落')` |
| 42 | 导入资料 | 0 | 0.577 | 清理旧段落 文献综述写作与检索习惯笔记 | `DELETE FROM paper_chunks WHERE doc_key = '文献综述写作与检索习惯笔记'` |
| 43 | 导入资料 | 0 | 0.310 | 清理旧论文 文献综述写作与检索习惯笔记 | `DELETE FROM papers WHERE doc_key = '文献综述写作与检索习惯笔记'` |
| 44 | 导入资料 | 1 | 6.268 | 写入论文 文献综述写作与检索习惯笔记 | `INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', 'note', 'notes/文献综述写作与检索习惯.md', '- # 二、检索习惯\n- 复习期末的笔记时，完全不记得当初把结论写在哪一篇里，希望系统能记住"我读过什么、读到哪一段"，再次检索时把已经读过的内容标出来或直接跳过。\n- 现在希望把论文和笔记都放进一个库里，用关键词加语义混合检索，三秒内定位到具体段落。\n来源：# 一、为什么要做文献库', '# 一、为什么要做文献库\n\n写综述时最大的成本不是读论文，而是"找不到读过的那篇"。以前用文件夹分类，文件名混乱，半年后完全检索不到。现在希望把论文和笔记都放进一个库里，用关键词加语义混合检索，三秒内定位到具体段落。\n\n# 二、检索习惯\n\n我习惯用两类词混合搜索：专业术语（例如"消息传递"、"过平滑"）用来精确命中，描述性表述（例如"邻居太多会不会学不出来"）用来找语义相近的段落。关键词检索负责前者，向量检索负责后者。\n\n另外经常需要按年份与标签过滤，例如"只看 2023 年之后的图神经网络相关笔记"。\n\n# 三、复习时的痛点\n\n复习期末的笔记时，完全不记得当初把结论写在哪一篇里，希望系统能记住"我读过什么、读到哪一段"，再次检索时把已经读过的内容标出来或直接跳过。\n\n# 四、工具链设想\n\n1. 导入：把 Markdown 笔记与论文正文切块入库；\n2. 检索：全文索引 + 向量索引 + 年份/标签过滤；\n3. 摘要：把命中的段落压缩成一段话；\n4. 记忆：记住研究方向、检索历史与阅读进度。\n\n# 五、写作规范\n\n每条结论都要能指回原文的段落位置，检索结果必须带出处，否则不敢引用。摘要只允许使用检索到的材料，不允许模型自由发挥。', AI_EMBED('pp_embed', '文献综述写作与检索习惯笔记\n# 一、为什么要做文献库\n\n写综述时最大的成本不是读论文，而是"找不到读过的那篇"。以前用文件夹分类，文件名混乱，半年后完全检索不到。现在希望把论文和笔记都放进一个库里，用关键词加语义混合检索，三秒内定位到具体段落。\n\n# 二、检索习惯\n\n我习惯用两类词混合搜索：专业术语（例如"消息传递"、"过平滑"）用来精确命中，描述性表述（例如"邻居太多会不会学不出来"）用来找语义相近的段落。关键词检索负责前者，向量检索负责后者。\n\n另外经常需要按年份与标签过滤，例如"只看 2023 年之后的图神经网络相关笔记"。\n\n# 三、复习时的痛点\n\n复习期末的笔记时，完全不记得当初把结论写在哪一篇里，希望系统能记住"我读过什么、读到哪一段"，再次检索时把已经读过的内容标出来或直接跳过。\n\n# 四、工具链设想\n\n1. 导入：把 Markdown 笔记与论文正文切块入库；\n2. 检索：全文索引 + 向量索引 + 年份/标签过滤；\n3. 摘要：把命中的段落压缩成一段话；\n4. 记忆：记住研究方向、检索历史与阅读进度。\n\n# 五、写作规范\n\n每条结论都要能指回原文的段落位置，检索结果必须带出处，否则不敢引用。摘要只允许使用检索到的材料，不允许模型自由发挥。'))` |
| 45 | 导入资料 | 1 | 4.104 | 写入段落 文献综述写作与检索习惯笔记#000 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('文献综述写作与检索习惯笔记#000', '文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', '一、为什么要做文献库', 0, 'notes/文献综述写作与检索习惯.md', 2, 4, '写综述时最大的成本不是读论文，而是"找不到读过的那篇"。以前用文件夹分类，文件名混乱，半年后完全检索不到。现在希望把论文和笔记都放进一个库里，用关键词加语义混合检索，三秒内定位到具体段落。', AI_EMBED('pp_embed', '一、为什么要做文献库\n写综述时最大的成本不是读论文，而是"找不到读过的那篇"。以前用文件夹分类，文件名混乱，半年后完全检索不到。现在希望把论文和笔记都放进一个库里，用关键词加语义混合检索，三秒内定位到具体段落。'))` |
| 46 | 导入资料 | 1 | 4.325 | 写入段落 文献综述写作与检索习惯笔记#001 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('文献综述写作与检索习惯笔记#001', '文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', '二、检索习惯', 1, 'notes/文献综述写作与检索习惯.md', 6, 10, '我习惯用两类词混合搜索：专业术语（例如"消息传递"、"过平滑"）用来精确命中，描述性表述（例如"邻居太多会不会学不出来"）用来找语义相近的段落。关键词检索负责前者，向量检索负责后者。\n\n另外经常需要按年份与标签过滤，例如"只看 2023 年之后的图神经网络相关笔记"。', AI_EMBED('pp_embed', '二、检索习惯\n我习惯用两类词混合搜索：专业术语（例如"消息传递"、"过平滑"）用来精确命中，描述性表述（例如"邻居太多会不会学不出来"）用来找语义相近的段落。关键词检索负责前者，向量检索负责后者。\n\n另外经常需要按年份与标签过滤，例如"只看 2023 年之后的图神经网络相关笔记"。'))` |
| 47 | 导入资料 | 1 | 4.036 | 写入段落 文献综述写作与检索习惯笔记#002 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('文献综述写作与检索习惯笔记#002', '文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', '三、复习时的痛点', 2, 'notes/文献综述写作与检索习惯.md', 12, 14, '复习期末的笔记时，完全不记得当初把结论写在哪一篇里，希望系统能记住"我读过什么、读到哪一段"，再次检索时把已经读过的内容标出来或直接跳过。', AI_EMBED('pp_embed', '三、复习时的痛点\n复习期末的笔记时，完全不记得当初把结论写在哪一篇里，希望系统能记住"我读过什么、读到哪一段"，再次检索时把已经读过的内容标出来或直接跳过。'))` |
| 48 | 导入资料 | 1 | 4.236 | 写入段落 文献综述写作与检索习惯笔记#003 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('文献综述写作与检索习惯笔记#003', '文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', '四、工具链设想', 3, 'notes/文献综述写作与检索习惯.md', 16, 21, '1. 导入：把 Markdown 笔记与论文正文切块入库；\n2. 检索：全文索引 + 向量索引 + 年份/标签过滤；\n3. 摘要：把命中的段落压缩成一段话；\n4. 记忆：记住研究方向、检索历史与阅读进度。', AI_EMBED('pp_embed', '四、工具链设想\n1. 导入：把 Markdown 笔记与论文正文切块入库；\n2. 检索：全文索引 + 向量索引 + 年份/标签过滤；\n3. 摘要：把命中的段落压缩成一段话；\n4. 记忆：记住研究方向、检索历史与阅读进度。'))` |
| 49 | 导入资料 | 1 | 4.244 | 写入段落 文献综述写作与检索习惯笔记#004 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('文献综述写作与检索习惯笔记#004', '文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', '五、写作规范', 4, 'notes/文献综述写作与检索习惯.md', 23, 24, '每条结论都要能指回原文的段落位置，检索结果必须带出处，否则不敢引用。摘要只允许使用检索到的材料，不允许模型自由发挥。', AI_EMBED('pp_embed', '五、写作规范\n每条结论都要能指回原文的段落位置，检索结果必须带出处，否则不敢引用。摘要只允许使用检索到的材料，不允许模型自由发挥。'))` |
| 50 | 导入资料 | 1 | 1.123 | 记录日志 ingest | `INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('文献综述写作与检索习惯笔记', '', 'ingest', '', 0, '导入 5 个段落')` |
| 51 | 导入资料 | 0 | 0.442 | 清理旧段落 课程笔记-图神经网络基础-第-6-9-周 | `DELETE FROM paper_chunks WHERE doc_key = '课程笔记-图神经网络基础-第-6-9-周'` |
| 52 | 导入资料 | 0 | 0.281 | 清理旧论文 课程笔记-图神经网络基础-第-6-9-周 | `DELETE FROM papers WHERE doc_key = '课程笔记-图神经网络基础-第-6-9-周'` |
| 53 | 导入资料 | 1 | 7.853 | 写入论文 课程笔记-图神经网络基础-第-6-9-周 | `INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', 'note', 'notes/课程笔记-图神经网络基础.md', '- 拉普拉斯矩阵 $L = D - A$ 是谱图卷积的基础，规格化版本 $L = I - D^{-1/2} A D^{-1/2}$ 的特征向量与图上的拉普拉斯算子特征函数一一对应。\n- 全图训练在 Cora 上没问题，但换成百万节点的引文网络就必须采样。\n- 3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。\n来源：# 第 6 周：图与邻接矩阵', '# 第 6 周：图与邻接矩阵\n\n今天从最基础的图表示开始。图 $G=(V,E)$ 可以用邻接矩阵 $A$ 稠密表示，也可以用边列表稀疏表示。稀疏表示在大图上更省内存，邻接矩阵方便写矩阵形式化的公式。度矩阵 $D$ 的对角线是每个节点的度。\n\n拉普拉斯矩阵 $L = D - A$ 是谱图卷积的基础，规格化版本 $L = I - D^{-1/2} A D^{-1/2}$ 的特征向量与图上的拉普拉斯算子特征函数一一对应。\n\n# 第 7 周：消息传递的三个步骤\n\n老师强调消息传递范式可以拆成 message、aggregate、update 三步。AGGREGATE 必须置换不变，这一点决定了不能用普通 MLP 直接对邻居表示做拼接。UPDATE 需要与邻居数量无关，否则节点度数差异会造成表示尺度不一致。\n\n作业：用 PyTorch 实现 sum / mean / max 三种聚合，并在一���小图上验证置换不变性。\n\n# 第 8 周：过平滑与残差连接\n\n过平滑的直观解释是：层数增加后，所有节点的表示互相靠拢，节点之间不再可区分。缓解手段里残差连接最容易实现，加上以后深层 GNN 的节点分类精度不再下降。PairNorm 的思路是对每一层的表示做标准化，强行维持方差。\n\n# 第 9 周：邻居采样\n\n采样是为了把大图切成小批。全图训练在 Cora 上没问题，但换成百万节点的引文网络就必须采样。GraphSAGE 的采样器每层固定采一定数量的邻居，Cluster-GCN 先做图聚类再切分。前者实现简单，后者对内存更友好。\n\n# 课后遗留问题\n\n1. 采样引入的方差如何在多层之间传递？\n2. 注意力聚合在度数差异大的图上是否稳定？\n3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。', AI_EMBED('pp_embed', '课程笔记：图神经网络基础（第 6-9 周）\n# 第 6 周：图与邻接矩阵\n\n今天从最基础的图表示开始。图 $G=(V,E)$ 可以用邻接矩阵 $A$ 稠密表示，也可以用边列表稀疏表示。稀疏表示在大图上更省内存，邻接矩阵方便写矩阵形式化的公式。度矩阵 $D$ 的对角线是每个节点的度。\n\n拉普拉斯矩阵 $L = D - A$ 是谱图卷积的基础，规格化版本 $L = I - D^{-1/2} A D^{-1/2}$ 的特征向量与图上的拉普拉斯算子特征函数一一对应。\n\n# 第 7 周：消息传递的三个步骤\n\n老师强调消息传递范式可以拆成 message、aggregate、update 三步。AGGREGATE 必须置换不变，这一点决定了不能用普通 MLP 直接对邻居表示做拼接。UPDATE 需要与邻居数量无关，否则节点度数差异会造成表示尺度不一致。\n\n作业：用 PyTorch 实现 sum / mean / max 三种聚合，并在一���小图上验证置换不变性。\n\n# 第 8 周：过平滑与残差连接\n\n过平滑的直观解释是：层数增加后，所有节点的表示互相靠拢，节点之间不再可区分。缓解手段里残差连接最容易实现，加上以后深层 GNN 的节点分类精度不再下降。PairNorm 的思路是对每一层的表示做标准化，强行维持方差。\n\n# 第 9 周：邻居采样\n\n采样是为了把大图切成小批。全图训练在 Cora 上没问题，但换成百万节点的引文网络就必须采样。GraphSAGE 的采样器每层固定采一定数量的邻居，Cluster-GCN 先做图聚类再切分。前者实现简单，后者对内存更友好。\n\n# 课后遗留问题\n\n1. 采样引入的方差如何在多层之间传递？\n2. 注意力聚合在度数差异大的图上是否稳定？\n3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。'))` |
| 54 | 导入资料 | 1 | 4.445 | 写入段落 课程笔记-图神经网络基础-第-6-9-周#000 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周#000', '课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', '第 6 周：图与邻接矩阵', 0, 'notes/课程笔记-图神经网络基础.md', 2, 6, '今天从最基础的图表示开始。图 $G=(V,E)$ 可以用邻接矩阵 $A$ 稠密表示，也可以用边列表稀疏表示。稀疏表示在大图上更省内存，邻接矩阵方便写矩阵形式化的公式。度矩阵 $D$ 的对角线是每个节点的度。\n\n拉普拉斯矩阵 $L = D - A$ 是谱图卷积的基础，规格化版本 $L = I - D^{-1/2} A D^{-1/2}$ 的特征向量与图上的拉普拉斯算子特征函数一一对应。', AI_EMBED('pp_embed', '第 6 周：图与邻接矩阵\n今天从最基础的图表示开始。图 $G=(V,E)$ 可以用邻接矩阵 $A$ 稠密表示，也可以用边列表稀疏表示。稀疏表示在大图上更省内存，邻接矩阵方便写矩阵形式化的公式。度矩阵 $D$ 的对角线是每个节点的度。\n\n拉普拉斯矩阵 $L = D - A$ 是谱图卷积的基础，规格化版本 $L = I - D^{-1/2} A D^{-1/2}$ 的特征向量与图上的拉普拉斯算子特征函数一一对应。'))` |
| 55 | 导入资料 | 1 | 4.506 | 写入段落 课程笔记-图神经网络基础-第-6-9-周#001 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周#001', '课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', '第 7 周：消息传递的三个步骤', 1, 'notes/课程笔记-图神经网络基础.md', 8, 12, '老师强调消息传递范式可以拆成 message、aggregate、update 三步。AGGREGATE 必须置换不变，这一点决定了不能用普通 MLP 直接对邻居表示做拼接。UPDATE 需要与邻居数量无关，否则节点度数差异会造成表示尺度不一致。\n\n作业：用 PyTorch 实现 sum / mean / max 三种聚合，并在一���小图上验证置换不变性。', AI_EMBED('pp_embed', '第 7 周：消息传递的三个步骤\n老师强调消息传递范式可以拆成 message、aggregate、update 三步。AGGREGATE 必须置换不变，这一点决定了不能用普通 MLP 直接对邻居表示做拼接。UPDATE 需要与邻居数量无关，否则节点度数差异会造成表示尺度不一致。\n\n作业：用 PyTorch 实现 sum / mean / max 三种聚合，并在一���小图上验证置换不变性。'))` |
| 56 | 导入资料 | 1 | 4.456 | 写入段落 课程笔记-图神经网络基础-第-6-9-周#002 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周#002', '课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', '第 8 周：过平滑与残差连接', 2, 'notes/课程笔记-图神经网络基础.md', 14, 16, '过平滑的直观解释是：层数增加后，所有节点的表示互相靠拢，节点之间不再可区分。缓解手段里残差连接最容易实现，加上以后深层 GNN 的节点分类精度不再下降。PairNorm 的思路是对每一层的表示做标准化，强行维持方差。', AI_EMBED('pp_embed', '第 8 周：过平滑与残差连接\n过平滑的直观解释是：层数增加后，所有节点的表示互相靠拢，节点之间不再可区分。缓解手段里残差连接最容易实现，加上以后深层 GNN 的节点分类精度不再下降。PairNorm 的思路是对每一层的表示做标准化，强行维持方差。'))` |
| 57 | 导入资料 | 1 | 4.496 | 写入段落 课程笔记-图神经网络基础-第-6-9-周#003 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周#003', '课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', '第 9 周：邻居采样', 3, 'notes/课程笔记-图神经网络基础.md', 18, 20, '采样是为了把大图切成小批。全图训练在 Cora 上没问题，但换成百万节点的引文网络就必须采样。GraphSAGE 的采样器每层固定采一定数量的邻居，Cluster-GCN 先做图聚类再切分。前者实现简单，后者对内存更友好。', AI_EMBED('pp_embed', '第 9 周：邻居采样\n采样是为了把大图切成小批。全图训练在 Cora 上没问题，但换成百万节点的引文网络就必须采样。GraphSAGE 的采样器每层固定采一定数量的邻居，Cluster-GCN 先做图聚类再切分。前者实现简单，后者对内存更友好。'))` |
| 58 | 导入资料 | 1 | 7.713 | 写入段落 课程笔记-图神经网络基础-第-6-9-周#004 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周#004', '课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', '课后遗留问题', 4, 'notes/课程笔记-图神经网络基础.md', 22, 25, '1. 采样引入的方差如何在多层之间传递？\n2. 注意力聚合在度数差异大的图上是否稳定？\n3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。', AI_EMBED('pp_embed', '课后遗留问题\n1. 采样引入的方差如何在多层之间传递？\n2. 注意力聚合在度数差异大的图上是否稳定？\n3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。'))` |
| 59 | 导入资料 | 1 | 1.418 | 记录日志 ingest | `INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('课程笔记-图神经网络基础-第-6-9-周', '', 'ingest', '', 0, '导入 5 个段落')` |
| 60 | 导入资料 | 0 | 0.600 | 清理旧段落 attention-is-all-you-need | `DELETE FROM paper_chunks WHERE doc_key = 'attention-is-all-you-need'` |
| 61 | 导入资料 | 0 | 0.459 | 清理旧论文 attention-is-all-you-need | `DELETE FROM papers WHERE doc_key = 'attention-is-all-you-need'` |
| 62 | 导入资料 | 1 | 8.230 | 写入论文 attention-is-all-you-need | `INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', 'paper', 'papers/attention_is_all_you_need.md', '- The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.\n- $$\\mathrm{Attention}(Q, K, V) = \\mathrm{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right) V$$\n- 给定输入矩阵 $Q \\in \\mathbb{R}^{n \\times d_k}$、$K \\in \\mathbb{R}^{n \\times d_k}$、$V \\in \\mathbb{R}^{n \\times d_v}$，注意力计算为\n来源：# Abstract', '# Abstract\n\nThe dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.\n\n# 一、自注意力机制\n\n自注意力把序列中每个位置表示为对所有位置加权和。给定输入矩阵 $Q \\in \\mathbb{R}^{n \\times d_k}$、$K \\in \\mathbb{R}^{n \\times d_k}$、$V \\in \\mathbb{R}^{n \\times d_v}$，注意力计算为\n\n$$\\mathrm{Attention}(Q, K, V) = \\mathrm{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right) V$$\n\n缩放因子 $\\sqrt{d_k}$ 用来避免维度变大时 softmax 进入饱和区���，梯度消失。多头注意力把表示切分成多份分别做注意力再拼接，使模型能在不同子空间里关注不同关系。\n\n# 二、位置编码\n\n由于自注意力本身不含位置信息，模型必须显式注入顺序。论文采用正弦位置编码\n\n$$PE_{(pos, 2i)} = \\sin\\left(pos / 10000^{2i/d_{model}}\\right)$$\n\n它既能表示绝对位置，也便于模型推断相对位置关系，并且可以外推到比训练时更长的序列。\n\n# 三、多头注意力的并行计算\n\n多头注意力的投影矩阵可以合并成一次大矩阵乘法实现，从而充分利用矩阵乘法的并行性。实践中注意力矩阵的显存占用是主要瓶颈，因此实现时通常使用 FlashAttention 一类的核融合算子把中间结果留在片上缓存。\n\n# 四、编码器与解码器\n\n编码器由多头自注意力、前馈网络、残差连接与层归一化堆叠六层组成；解码器额外引入交叉注意力，堆叠六层。残差连接放在层归一化之前，子层输出先残差相加再做归一化。\n\n# 五、复杂度分析\n\n自注意力的时间复杂度为 $O(n^2 d)$，序列长度 $n$ 增大时平方项成为主要开销。这是长序列建模的主要瓶颈，也是后续稀疏注意力、线性注意力与状态空间模型试图解决的问题。\n\n# 六、结论\n\nTransformer 用纯粹的注意力机制取代循环结构，在翻译任务上取得更好的效果，同时具备更高的并行度，成为后续大量模型的基础结构。', AI_EMBED('pp_embed', 'Attention Is All You Need\n# Abstract\n\nThe dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.\n\n# 一、自注意力机制\n\n自注意力把序列中每个位置表示为对所有位置加权和。给定输入矩阵 $Q \\in \\mathbb{R}^{n \\times d_k}$、$K \\in \\mathbb{R}^{n \\times d_k}$、$V \\in \\mathbb{R}^{n \\times d_v}$，注意力计算为\n\n$$\\mathrm{Attention}(Q, K, V) = \\mathrm{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right) V$$\n\n缩放因子 $\\sqrt{d_k}$ 用来避免维度变大时 softmax 进入饱和区���，梯度消失。多头注意力把表示切分成多份分别做注意力再拼接，使模型能在不同子空间里关注不同关系。\n\n# 二、位置编码\n\n由于自注意力本身不含位置信息，模型必须显式注入顺序。论文采用正弦位置编码\n\n$$PE_{(pos, 2i)} = \\sin\\left(pos / 10000^{2i/d_{model}}\\right)$$\n\n它既能表示绝对位置，也便于模型推断相对位置关系，并且可以外推到比训练时更长的序列。\n\n# 三、多头注意力的并行计算\n\n多头注意力的投影矩阵可以合并成一次大矩阵乘法实现，从而充分利用矩阵乘法的并行性。实践中注意力矩阵的显存占用是主要瓶颈，因此实现时通常使用 FlashAttention 一类的核融合算子把中间结果留在片上缓存。\n\n# 四、编码器与解码器\n\n编码器由多头自注意力、前馈网络、残差连接与层归一化堆叠六层组成；解码器额外引入交叉注意力，堆叠六层。残差连接放在层归一化之前，子层输出先残差相加再做归一化。\n\n# 五、复杂度分析\n\n自注意力的时间复杂度为 $O(n^2 d)$，序列长度 $n$ 增大时平方项成为主要开销。这是长序列建模的主要瓶颈，也是后续稀疏注意力、线性注意力与状态空间模型试图解决的问题。\n\n# 六、结论\n\nTransformer 用纯粹的注意力机制取代循环结构，在翻译任务上取得更好的效果，同时具备更高的并行度，成为后续大量模型的基础结构。'))` |
| 63 | 导入资料 | 1 | 4.716 | 写入段落 attention-is-all-you-need#000 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#000', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', 'Abstract', 0, 'papers/attention_is_all_you_need.md', 2, 4, 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.', AI_EMBED('pp_embed', 'Abstract\nThe dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.'))` |
| 64 | 导入资料 | 1 | 10.615 | 写入段落 attention-is-all-you-need#001 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#001', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '一、自注意力机制', 1, 'papers/attention_is_all_you_need.md', 6, 12, '自注意力把序列中每个位置表示为对所有位置加权和。给定输入矩阵 $Q \\in \\mathbb{R}^{n \\times d_k}$、$K \\in \\mathbb{R}^{n \\times d_k}$、$V \\in \\mathbb{R}^{n \\times d_v}$，注意力计算为\n\n$$\\mathrm{Attention}(Q, K, V) = \\mathrm{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right) V$$\n\n缩放因子 $\\sqrt{d_k}$ 用来避免维度变大时 softmax 进入饱和区���，梯度消失。多头注意力把表示切分成多份分别做注意力再拼接，使模型能在不同子空间里关注不同关系。', AI_EMBED('pp_embed', '一、自注意力机制\n自注意力把序列中每个位置表示为对所有位置加权和。给定输入矩阵 $Q \\in \\mathbb{R}^{n \\times d_k}$、$K \\in \\mathbb{R}^{n \\times d_k}$、$V \\in \\mathbb{R}^{n \\times d_v}$，注意力计算为\n\n$$\\mathrm{Attention}(Q, K, V) = \\mathrm{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right) V$$\n\n缩放因子 $\\sqrt{d_k}$ 用来避免维度变大时 softmax 进入饱和区���，梯度消失。多头注意力把表示切分成多份分别做注意力再拼接，使模型能在不同子空间里关注不同关系。'))` |
| 65 | 导入资料 | 1 | 6.976 | 写入段落 attention-is-all-you-need#002 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#002', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '二、位置编码', 2, 'papers/attention_is_all_you_need.md', 14, 20, '由于自注意力本身不含位置信息，模型必须显式注入顺序。论文采用正弦位置编码\n\n$$PE_{(pos, 2i)} = \\sin\\left(pos / 10000^{2i/d_{model}}\\right)$$\n\n它既能表示绝对位置，也便于模型推断相对位置关系，并且可以外推到比训练时更长的序列。', AI_EMBED('pp_embed', '二、位置编码\n由于自注意力本身不含位置信息，模型必须显式注入顺序。论文采用正弦位置编码\n\n$$PE_{(pos, 2i)} = \\sin\\left(pos / 10000^{2i/d_{model}}\\right)$$\n\n它既能表示绝对位置，也便于模型推断相对位置关系，并且可以外推到比训练时更长的序列。'))` |
| 66 | 导入资料 | 1 | 10.169 | 写入段落 attention-is-all-you-need#003 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#003', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '三、多头注意力的并行计算', 3, 'papers/attention_is_all_you_need.md', 22, 24, '多头注意力的投影矩阵可以合并成一次大矩阵乘法实现，从而充分利用矩阵乘法的并行性。实践中注意力矩阵的显存占用是主要瓶颈，因此实现时通常使用 FlashAttention 一类的核融合算子把中间结果留在片上缓存。', AI_EMBED('pp_embed', '三、多头注意力的并行计算\n多头注意力的投影矩阵可以合并成一次大矩阵乘法实现，从而充分利用矩阵乘法的并行性。实践中注意力矩阵的显存占用是主要瓶颈，因此实现时通常使用 FlashAttention 一类的核融合算子把中间结果留在片上缓存。'))` |
| 67 | 导入资料 | 1 | 4.680 | 写入段落 attention-is-all-you-need#004 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#004', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '四、编码器与解码器', 4, 'papers/attention_is_all_you_need.md', 26, 28, '编码器由多头自注意力、前馈网络、残差连接与层归一化堆叠六层组成；解码器额外引入交叉注意力，堆叠六层。残差连接放在层归一化之前，子层输出先残差相加再做归一化。', AI_EMBED('pp_embed', '四、编码器与解码器\n编码器由多头自注意力、前馈网络、残差连接与层归一化堆叠六层组成；解码器额外引入交叉注意力，堆叠六层。残差连接放在层归一化之前，子层输出先残差相加再做归一化。'))` |
| 68 | 导入资料 | 1 | 6.598 | 写入段落 attention-is-all-you-need#005 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#005', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '五、复杂度分析', 5, 'papers/attention_is_all_you_need.md', 30, 32, '自注意力的时间复杂度为 $O(n^2 d)$，序列长度 $n$ 增大时平方项成为主要开销。这是长序列建模的主要瓶颈，也是后续稀疏注意力、线性注意力与状态空间模型试图解决的问题。', AI_EMBED('pp_embed', '五、复杂度分析\n自注意力的时间复杂度为 $O(n^2 d)$，序列长度 $n$ 增大时平方项成为主要开销。这是长序列建模的主要瓶颈，也是后续稀疏注意力、线性注意力与状态空间模型试图解决的问题。'))` |
| 69 | 导入资料 | 1 | 5.657 | 写入段落 attention-is-all-you-need#006 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#006', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '六、结论', 6, 'papers/attention_is_all_you_need.md', 34, 35, 'Transformer 用纯粹的注意力机制取代循环结构，在翻译任务上取得更好的效果，同时具备更高的并行度，成为后续大量模型的基础结构。', AI_EMBED('pp_embed', '六、结论\nTransformer 用纯粹的注意力机制取代循环结构，在翻译任务上取得更好的效果，同时具备更高的并行度，成为后续大量模型的基础结构。'))` |
| 70 | 导入资料 | 1 | 1.306 | 记录日志 ingest | `INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('attention-is-all-you-need', '', 'ingest', '', 0, '导入 7 个段落')` |
| 71 | 导入资料 | 0 | 0.514 | 清理旧段落 bert-基于双向transformer的预训练语言模型 | `DELETE FROM paper_chunks WHERE doc_key = 'bert-基于双向transformer的预训练语言模型'` |
| 72 | 导入资料 | 0 | 0.512 | 清理旧论文 bert-基于双向transformer的预训练语言模型 | `DELETE FROM papers WHERE doc_key = 'bert-基于双向transformer的预训练语言模型'` |
| 73 | 导入资料 | 1 | 8.390 | 写入论文 bert-基于双向transformer的预训练语言模型 | `INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', 'paper', 'papers/bert_pretraining.md', '- 本文提出 BERT，一种基于双向 Transformer 的预训练语言表示模型。\n- BERT 证明了大规模无监督预训练加少量标注微调可以显著提升自然语言理解性能，并直接推动了预训练语言模型在检索、问答与摘要任务上的落地。\n- 双向的掩码预训练让每个位置都能同时利用左右两侧上下文，这是 BERT 与单向语言模型最本质的区别。\n来源：# 摘要', '# 摘要\n\n本文提出 BERT，一种基于双向 Transformer 的预训练语言表示模型。BERT 先在大规模无标注语料上进行掩码语言模型预训练，再针对具体任务做微调，在多个自然语言理解基准上刷新结果。\n\n# 一、预训练任务\n\n掩码语言模型（MLM）随机选择 15% 的输入 token 进行预测，其中 80% 替换为 [MASK]，10% 随机替换，10% 保持不变。句子对任务则使用下一句预测（NSP）作为辅助目标。双向的掩码预训练让每个位置都能同时利用左右两侧上下文，这是 BERT 与单向语言模型最本质的区别。\n\n# 二、微调阶段\n\n下游任务微调时在预训练模型顶部加一个轻量任务头，所有参数一起微调。句对分类、句子分类与问答任务的实现差异很小，这体现了"预训练 + 微调"范式的通用性。\n\n# 三、输入表示\n\nBERT 的输入由词向量、片段向量与位置向量三部分相加得到。片段向量区分句 A 与句 B，位置向量区分序列中的绝对位置。\n\n# 四、模型规模与训练代价\n\nBERT Base 使用 12 层 Transformer、隐藏维度 768、12 个注意力头，总参数量约一亿；BERT Large 参数量约三亿。训练使用 AdamW 优化器与学习率预热，在多卡环境下需要混合精度训练以控制显存。\n\n# 五、局限\n\nMLM 的 [MASK] token 在预训练与微调之间存在不一致，评测时也依赖人工构造的掩码。后来 ELECTRA 等工作用判别式替换检测缓解这一问题。此外 BERT 的输入长度上限为 512 个 token，长文档处理需要滑窗或分段策略。\n\n# 六、结论\n\nBERT 证明了大规模无监督预训练加少量标注微调可以显著提升自然语言理解性能，并直接推动了预训练语言模型在检索、问答与摘要任务上的落地。', AI_EMBED('pp_embed', 'BERT：基于双向Transformer的预训练语言模型\n# 摘要\n\n本文提出 BERT，一种基于双向 Transformer 的预训练语言表示模型。BERT 先在大规模无标注语料上进行掩码语言模型预训练，再针对具体任务做微调，在多个自然语言理解基准上刷新结果。\n\n# 一、预训练任务\n\n掩码语言模型（MLM）随机选择 15% 的输入 token 进行预测，其中 80% 替换为 [MASK]，10% 随机替换，10% 保持不变。句子对任务则使用下一句预测（NSP）作为辅助目标。双向的掩码预训练让每个位置都能同时利用左右两侧上下文，这是 BERT 与单向语言模型最本质的区别。\n\n# 二、微调阶段\n\n下游任务微调时在预训练模型顶部加一个轻量任务头，所有参数一起微调。句对分类、句子分类与问答任务的实现差异很小，这体现了"预训练 + 微调"范式的通用性。\n\n# 三、输入表示\n\nBERT 的输入由词向量、片段向量与位置向量三部分相加得到。片段向量区分句 A 与句 B，位置向量区分序列中的绝对位置。\n\n# 四、模型规模与训练代价\n\nBERT Base 使用 12 层 Transformer、隐藏维度 768、12 个注意力头，总参数量约一亿；BERT Large 参数量约三亿。训练使用 AdamW 优化器与学习率预热，在多卡环境下需要混合精度训练以控制显存。\n\n# 五、局限\n\nMLM 的 [MASK] token 在预训练与微调之间存在不一致，评测时也依赖人工构造的掩码。后来 ELECTRA 等工作用判别式替换检测缓解这一问题。此外 BERT 的输入长度上限为 512 个 token，长文档处理需要滑窗或分段策略。\n\n# 六、结论\n\nBERT 证明了大规模无监督预训练加少量标注微调可以显著提升自然语言理解性能，并直接推动了预训练语言模型在检索、问答与摘要任务上的落地。'))` |
| 74 | 导入资料 | 1 | 9.270 | 写入段落 bert-基于双向transformer的预训练语言模型#000 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#000', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '摘要', 0, 'papers/bert_pretraining.md', 2, 4, '本文提出 BERT，一种基于双向 Transformer 的预训练语言表示模型。BERT 先在大规模无标注语料上进行掩码语言模型预训练，再针对具体任务做微调，在多个自然语言理解基准上刷新结果。', AI_EMBED('pp_embed', '摘要\n本文提出 BERT，一种基于双向 Transformer 的预训练语言表示模型。BERT 先在大规模无标注语料上进行掩码语言模型预训练，再针对具体任务做微调，在多个自然语言理解基准上刷新结果。'))` |
| 75 | 导入资料 | 1 | 4.733 | 写入段落 bert-基于双向transformer的预训练语言模型#001 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#001', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '一、预训练任务', 1, 'papers/bert_pretraining.md', 6, 8, '掩码语言模型（MLM）随机选择 15% 的输入 token 进行预测，其中 80% 替换为 [MASK]，10% 随机替换，10% 保持不变。句子对任务则使用下一句预测（NSP）作为辅助目标。双向的掩码预训练让每个位置都能同时利用左右两侧上下文，这是 BERT 与单向语言模型最本质的区别。', AI_EMBED('pp_embed', '一、预训练任务\n掩码语言模型（MLM）随机选择 15% 的输入 token 进行预测，其中 80% 替换为 [MASK]，10% 随机替换，10% 保持不变。句子对任务则使用下一句预测（NSP）作为辅助目标。双向的掩码预训练让每个位置都能同时利用左右两侧上下文，这是 BERT 与单向语言模型最本质的区别。'))` |
| 76 | 导入资料 | 1 | 3.846 | 写入段落 bert-基于双向transformer的预训练语言模型#002 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#002', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '二、微调阶段', 2, 'papers/bert_pretraining.md', 10, 12, '下游任务微调时在预训练模型顶部加一个轻量任务头，所有参数一起微调。句对分类、句子分类与问答任务的实现差异很小，这体现了"预训练 + 微调"范式的通用性。', AI_EMBED('pp_embed', '二、微调阶段\n下游任务微调时在预训练模型顶部加一个轻量任务头，所有参数一起微调。句对分类、句子分类与问答任务的实现差异很小，这体现了"预训练 + 微调"范式的通用性。'))` |
| 77 | 导入资料 | 1 | 6.645 | 写入段落 bert-基于双向transformer的预训练语言模型#003 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#003', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '三、输入表示', 3, 'papers/bert_pretraining.md', 14, 16, 'BERT 的输入由词向量、片段向量与位置向量三部分相加得到。片段向量区分句 A 与句 B，位置向量区分序列中的绝对位置。', AI_EMBED('pp_embed', '三、输入表示\nBERT 的输入由词向量、片段向量与位置向量三部分相加得到。片段向量区分句 A 与句 B，位置向量区分序列中的绝对位置。'))` |
| 78 | 导入资料 | 1 | 4.046 | 写入段落 bert-基于双向transformer的预训练语言模型#004 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#004', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '四、模型规模与训练代价', 4, 'papers/bert_pretraining.md', 18, 20, 'BERT Base 使用 12 层 Transformer、隐藏维度 768、12 个注意力头，总参数量约一亿；BERT Large 参数量约三亿。训练使用 AdamW 优化器与学习率预热，在多卡环境下需要混合精度训练以控制显存。', AI_EMBED('pp_embed', '四、模型规模与训练代价\nBERT Base 使用 12 层 Transformer、隐藏维度 768、12 个注意力头，总参数量约一亿；BERT Large 参数量约三亿。训练使用 AdamW 优化器与学习率预热，在多卡环境下需要混合精度训练以控制显存。'))` |
| 79 | 导入资料 | 1 | 4.226 | 写入段落 bert-基于双向transformer的预训练语言模型#005 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#005', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '五、局限', 5, 'papers/bert_pretraining.md', 22, 24, 'MLM 的 [MASK] token 在预训练与微调之间存在不一致，评测时也依赖人工构造的掩码。后来 ELECTRA 等工作用判别式替换检测缓解这一问题。此外 BERT 的输入长度上限为 512 个 token，长文档处理需要滑窗或分段策略。', AI_EMBED('pp_embed', '五、局限\nMLM 的 [MASK] token 在预训练与微调之间存在不一致，评测时也依赖人工构造的掩码。后来 ELECTRA 等工作用判别式替换检测缓解这一问题。此外 BERT 的输入长度上限为 512 个 token，长文档处理需要滑窗或分段策略。'))` |
| 80 | 导入资料 | 1 | 3.494 | 写入段落 bert-基于双向transformer的预训练语言模型#006 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#006', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '六、结论', 6, 'papers/bert_pretraining.md', 26, 27, 'BERT 证明了大规模无监督预训练加少量标注微调可以显著提升自然语言理解性能，并直接推动了预训练语言模型在检索、问答与摘要任务上的落地。', AI_EMBED('pp_embed', '六、结论\nBERT 证明了大规模无监督预训练加少量标注微调可以显著提升自然语言理解性能，并直接推动了预训练语言模型在检索、问答与摘要任务上的落地。'))` |
| 81 | 导入资料 | 1 | 1.245 | 记录日志 ingest | `INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('bert-基于双向transformer的预训练语言模型', '', 'ingest', '', 0, '导入 7 个段落')` |
| 82 | 导入资料 | 0 | 0.453 | 清理旧段落 对比表示学习在检索场景中的实践 | `DELETE FROM paper_chunks WHERE doc_key = '对比表示学习在检索场景中的实践'` |
| 83 | 导入资料 | 0 | 0.320 | 清理旧论文 对比表示学习在检索场景中的实践 | `DELETE FROM papers WHERE doc_key = '对比表示学习在检索场景中的实践'` |
| 84 | 导入资料 | 1 | 8.108 | 写入论文 对比表示学习在检索场景中的实践 | `INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', 'paper', 'papers/contrastive_representation.md', '- 对比表示学习通过构造正负样本对，把语义相近的文本映射到向量空间中彼此靠近的位置。\n- 本文讨论其在文献检索场景中的落地方式，重点是如何让向量召回与关键词召回互补。\n- 对比学习让向量召回在语义层面补齐了关键词召回的短板，而混合召回加融合排序是在工程上稳健的默认方案。\n来源：# 摘要', '# 摘要\n\n对比表示学习通过构造正负样本对，把语义相近的文本映射到向量空间中彼此靠近的位置。本文讨论其在文献检索场景中的落地方式，重点是如何让向量召回与关键词召回互补。\n\n# 一、对比学习的基本形式\n\n给定锚点样本 $a$、正样本 $p$ 与负样本集合 $\\{n_i\\}$，InfoNCE 损失写作\n\n$$L = -\\log \\frac{\\exp(\\mathrm{sim}(a, p)/\\tau)}{\\exp(\\mathrm{sim}(a, p)/\\tau) + \\sum_i \\exp(\\mathrm{sim}(a, n_i)/\\tau)}$$\n\n温度系数 $\\tau$ 控制分布的尖锐程度，对效果影响很大。\n\n# 二、难负样本挖掘\n\n随机负样本过于简单，模型很快饱和。需要在候选池中挑选与锚点最相似但被标注为负的样本，也就是难负样本挖掘（hard negative mining）。在检索系统中可以直接用线上召回结果作为负样本池，让训练分布与推理分布一致。\n\n# 三、向量召回与关键词召回的互补性\n\n向量召回擅长处理同义改写与跨语言表达，关键词召回则擅长精确匹配专有名词、公式编号与罕见术语。生产系统通常把两路召回结果合并去重，再交给精排模型。\n\n# 四、向量索引的工程取舍\n\n近似最近邻索引在精度与延迟之间取舍。HNSW 适合内存充裕、查询并发高的场景；IVF 类索引在数据量大时更省内存。距离度量的选择同样重要，余弦距离适合归一化向量，L2 距离在未归一化时更稳定。\n\n# 五、评估方式\n\n除了常规的召回率与 NDCG，还要单独统计"向量召回独有问题"与"关键词召回独有问题"，据此决定是否继续投入优化某一路召回。混合排序常用倒数排名融合（RRF），它不依赖两路分数的量纲。\n\n# 六、结论\n\n对比学习让向量召回在语义层面补齐了关键词召回的短板，而混合召回加融合排序是在工程上稳健的默认方案。', AI_EMBED('pp_embed', '对比表示学习在检索场景中的实践\n# 摘要\n\n对比表示学习通过构造正负样本对，把语义相近的文本映射到向量空间中彼此靠近的位置。本文讨论其在文献检索场景中的落地方式，重点是如何让向量召回与关键词召回互补。\n\n# 一、对比学习的基本形式\n\n给定锚点样本 $a$、正样本 $p$ 与负样本集合 $\\{n_i\\}$，InfoNCE 损失写作\n\n$$L = -\\log \\frac{\\exp(\\mathrm{sim}(a, p)/\\tau)}{\\exp(\\mathrm{sim}(a, p)/\\tau) + \\sum_i \\exp(\\mathrm{sim}(a, n_i)/\\tau)}$$\n\n温度系数 $\\tau$ 控制分布的尖锐程度，对效果影响很大。\n\n# 二、难负样本挖掘\n\n随机负样本过于简单，模型很快饱和。需要在候选池中挑选与锚点最相似但被标注为负的样本，也就是难负样本挖掘（hard negative mining）。在检索系统中可以直接用线上召回结果作为负样本池，让训练分布与推理分布一致。\n\n# 三、向量召回与关键词召回的互补性\n\n向量召回擅长处理同义改写与跨语言表达，关键词召回则擅长精确匹配专有名词、公式编号与罕见术语。生产系统通常把两路召回结果合并去重，再交给精排模型。\n\n# 四、向量索引的工程取舍\n\n近似最近邻索引在精度与延迟之间取舍。HNSW 适合内存充裕、查询并发高的场景；IVF 类索引在数据量大时更省内存。距离度量的选择同样重要，余弦距离适合归一化向量，L2 距离在未归一化时更稳定。\n\n# 五、评估方式\n\n除了常规的召回率与 NDCG，还要单独统计"向量召回独有问题"与"关键词召回独有问题"，据此决定是否继续投入优化某一路召回。混合排序常用倒数排名融合（RRF），它不依赖两路分数的量纲。\n\n# 六、结论\n\n对比学习让向量召回在语义层面补齐了关键词召回的短板，而混合召回加融合排序是在工程上稳健的默认方案。'))` |
| 85 | 导入资料 | 1 | 3.574 | 写入段落 对比表示学习在检索场景中的实践#000 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#000', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '摘要', 0, 'papers/contrastive_representation.md', 2, 4, '对比表示学习通过构造正负样本对，把语义相近的文本映射到向量空间中彼此靠近的位置。本文讨论其在文献检索场景中的落地方式，重点是如何让向量召回与关键词召回互补。', AI_EMBED('pp_embed', '摘要\n对比表示学习通过构造正负样本对，把语义相近的文本映射到向量空间中彼此靠近的位置。本文讨论其在文献检索场景中的落地方式，重点是如何让向量召回与关键词召回互补。'))` |
| 86 | 导入资料 | 1 | 3.819 | 写入段落 对比表示学习在检索场景中的实践#001 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#001', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '一、对比学习的基本形式', 1, 'papers/contrastive_representation.md', 6, 12, '给定锚点样本 $a$、正样本 $p$ 与负样本集合 $\\{n_i\\}$，InfoNCE 损失写作\n\n$$L = -\\log \\frac{\\exp(\\mathrm{sim}(a, p)/\\tau)}{\\exp(\\mathrm{sim}(a, p)/\\tau) + \\sum_i \\exp(\\mathrm{sim}(a, n_i)/\\tau)}$$\n\n温度系数 $\\tau$ 控制分布的尖锐程度，对效果影响很大。', AI_EMBED('pp_embed', '一、对比学习的基本形式\n给定锚点样本 $a$、正样本 $p$ 与负样本集合 $\\{n_i\\}$，InfoNCE 损失写作\n\n$$L = -\\log \\frac{\\exp(\\mathrm{sim}(a, p)/\\tau)}{\\exp(\\mathrm{sim}(a, p)/\\tau) + \\sum_i \\exp(\\mathrm{sim}(a, n_i)/\\tau)}$$\n\n温度系数 $\\tau$ 控制分布的尖锐程度，对效果影响很大。'))` |
| 87 | 导入资料 | 1 | 4.567 | 写入段落 对比表示学习在检索场景中的实践#002 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#002', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '二、难负样本挖掘', 2, 'papers/contrastive_representation.md', 14, 16, '随机负样本过于简单，模型很快饱和。需要在候选池中挑选与锚点最相似但被标注为负的样本，也就是难负样本挖掘（hard negative mining）。在检索系统中可以直接用线上召回结果作为负样本池，让训练分布与推理分布一致。', AI_EMBED('pp_embed', '二、难负样本挖掘\n随机负样本过于简单，模型很快饱和。需要在候选池中挑选与锚点最相似但被标注为负的样本，也就是难负样本挖掘（hard negative mining）。在检索系统中可以直接用线上召回结果作为负样本池，让训练分布与推理分布一致。'))` |
| 88 | 导入资料 | 1 | 4.414 | 写入段落 对比表示学习在检索场景中的实践#003 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#003', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '三、向量召回与关键词召回的互补性', 3, 'papers/contrastive_representation.md', 18, 20, '向量召回擅长处理同义改写与跨语言表达，关键词召回则擅长精确匹配专有名词、公式编号与罕见术语。生产系统通常把两路召回结果合并去重，再交给精排模型。', AI_EMBED('pp_embed', '三、向量召回与关键词召回的互补性\n向量召回擅长处理同义改写与跨语言表达，关键词召回则擅长精确匹配专有名词、公式编号与罕见术语。生产系统通常把两路召回结果合并去重，再交给精排模型。'))` |
| 89 | 导入资料 | 1 | 3.848 | 写入段落 对比表示学习在检索场景中的实践#004 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#004', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '四、向量索引的工程取舍', 4, 'papers/contrastive_representation.md', 22, 24, '近似最近邻索引在精度与延迟之间取舍。HNSW 适合内存充裕、查询并发高的场景；IVF 类索引在数据量大时更省内存。距离度量的选择同样重要，余弦距离适合归一化向量，L2 距离在未归一化时更稳定。', AI_EMBED('pp_embed', '四、向量索引的工程取舍\n近似最近邻索引在精度与延迟之间取舍。HNSW 适合内存充裕、查询并发高的场景；IVF 类索引在数据量大时更省内存。距离度量的选择同样重要，余弦距离适合归一化向量，L2 距离在未归一化时更稳定。'))` |
| 90 | 导入资料 | 1 | 4.329 | 写入段落 对比表示学习在检索场景中的实践#005 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#005', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '五、评估方式', 5, 'papers/contrastive_representation.md', 26, 28, '除了常规的召回率与 NDCG，还要单独统计"向量召回独有问题"与"关键词召回独有问题"，据此决定是否继续投入优化某一路召回。混合排序常用倒数排名融合（RRF），它不依赖两路分数的量纲。', AI_EMBED('pp_embed', '五、评估方式\n除了常规的召回率与 NDCG，还要单独统计"向量召回独有问题"与"关键词召回独有问题"，据此决定是否继续投入优化某一路召回。混合排序常用倒数排名融合（RRF），它不依赖两路分数的量纲。'))` |
| 91 | 导入资料 | 1 | 3.941 | 写入段落 对比表示学习在检索场景中的实践#006 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#006', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '六、结论', 6, 'papers/contrastive_representation.md', 30, 31, '对比学习让向量召回在语义层面补齐了关键词召回的短板，而混合召回加融合排序是在工程上稳健的默认方案。', AI_EMBED('pp_embed', '六、结论\n对比学习让向量召回在语义层面补齐了关键词召回的短板，而混合召回加融合排序是在工程上稳健的默认方案。'))` |
| 92 | 导入资料 | 1 | 1.206 | 记录日志 ingest | `INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('对比表示学习在检索场景中的实践', '', 'ingest', '', 0, '导入 7 个段落')` |
| 93 | 导入资料 | 0 | 0.577 | 清理旧段落 图神经网络综述-从消息传递到可学习聚合 | `DELETE FROM paper_chunks WHERE doc_key = '图神经网络综述-从消息传递到可学习聚合'` |
| 94 | 导入资料 | 0 | 0.236 | 清理旧论文 图神经网络综述-从消息传递到可学习聚合 | `DELETE FROM papers WHERE doc_key = '图神经网络综述-从消息传递到可学习聚合'` |
| 95 | 导入资料 | 1 | 9.297 | 写入论文 图神经网络综述-从消息传递到可学习聚合 | `INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', 'paper', 'papers/gnn_survey.md', '- 消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。\n- 本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。\n- 可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。\n来源：# 摘要', '# 摘要\n\n图神经网络（Graph Neural Network, GNN）是一类直接在图结构上定义卷积运算的深度模型。本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。\n\n# 一、消息传递范式\n\n消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。设节点集合为 $V$，边集合为 $E$，第 $l$ 层的更新可以写成\n\n$$h_v^{(l+1)} = \\mathrm{UPDATE}^{(l)}\\left(h_v^{(l)}, \\mathrm{AGGREGATE}^{(l)}(\\{h_u^{(l)} : u \\in N(v)\\})\\right)$$\n\n其中 $N(v)$ 表示节点 $v$ 的一跳邻居集合。AGGREGATE 要求置换不变，UPDATE 要求与邻居数量无关，否则大度数节点会破坏规模一致性。\n\n# 二、邻居聚合算子\n\n常见聚合算子包括求和聚合、平均聚合、最大聚合以及基于注意力的加权聚合。求和聚合实现简单且表达能力强，在同配图上表现稳定；平均聚合对邻居数量不敏感，但会稀释信号；注意力聚合引入可学习权重，可以区分邻居的重要性，但额外增加了参数量与过拟合风险。\n\n# 三、过平滑与跳连\n\n随着层数增加，所有节点的表示会趋于一致，这就是过平滑现象。常用缓解手段包括残差连接、初始残差（initial residual）、PairNorm 归一化，以及把底层原始特征直接拼接到高层表示上。残差连接在实现上最简单，通常能带来稳定的收益。\n\n# 四、邻居采样与规模扩展\n\n全图卷积在节点规模达到百万级时显存开销无法接受。邻居采样（neighbor sampling）按层采样有限数量的邻居，把大图切成小批；GraphSAGE 的采样器按均匀分布抽取固定数量的邻居，Cluster-GCN 则按节点簇进行划分。采样引入的方差可以通过多层聚合与均值池化缓解。\n\n# 五、可学习聚合与超图\n\n可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。\n\n# 六、结论与展望\n\n消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。后续工作需要在表达能力、效率与可解释性之间继续寻找平衡。', AI_EMBED('pp_embed', '图神经网络综述：从消息传递到可学习聚合\n# 摘要\n\n图神经网络（Graph Neural Network, GNN）是一类直接在图结构上定义卷积运算的深度模型。本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。\n\n# 一、消息传递范式\n\n消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。设节点集合为 $V$，边集合为 $E$，第 $l$ 层的更新可以写成\n\n$$h_v^{(l+1)} = \\mathrm{UPDATE}^{(l)}\\left(h_v^{(l)}, \\mathrm{AGGREGATE}^{(l)}(\\{h_u^{(l)} : u \\in N(v)\\})\\right)$$\n\n其中 $N(v)$ 表示节点 $v$ 的一跳邻居集合。AGGREGATE 要求置换不变，UPDATE 要求与邻居数量无关，否则大度数节点会破坏规模一致性。\n\n# 二、邻居聚合算子\n\n常见聚合算子包括求和聚合、平均聚合、最大聚合以及基于注意力的加权聚合。求和聚合实现简单且表达能力强，在同配图上表现稳定；平均聚合对邻居数量不敏感，但会稀释信号；注意力聚合引入可学习权重，可以区分邻居的重要性，但额外增加了参数量与过拟合风险。\n\n# 三、过平滑与跳连\n\n随着层数增加，所有节点的表示会趋于一致，这就是过平滑现象。常用缓解手段包括残差连接、初始残差（initial residual）、PairNorm 归一化，以及把底层原始特征直接拼接到高层表示上。残差连接在实现上最简单，通常能带来稳定的收益。\n\n# 四、邻居采样与规模扩展\n\n全图卷积在节点规模达到百万级时显存开销无法接受。邻居采样（neighbor sampling）按层采样有限数量的邻居，把大图切成小批；GraphSAGE 的采样器按均匀分布抽取固定数量的邻居，Cluster-GCN 则按节点簇进行划分。采样引入的方差可以通过多层聚合与均值池化缓解。\n\n# 五、可学习聚合与超图\n\n可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。\n\n# 六、结论与展望\n\n消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。后续工作需要在表达能力、效率与可解释性之间继续寻找平衡。'))` |
| 96 | 导入资料 | 1 | 4.473 | 写入段落 图神经网络综述-从消息传递到可学习聚合#000 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#000', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '摘要', 0, 'papers/gnn_survey.md', 2, 4, '图神经网络（Graph Neural Network, GNN）是一类直接在图结构上定义卷积运算的深度模型。本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。', AI_EMBED('pp_embed', '摘要\n图神经网络（Graph Neural Network, GNN）是一类直接在图结构上定义卷积运算的深度模型。本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。'))` |
| 97 | 导入资料 | 1 | 4.100 | 写入段落 图神经网络综述-从消息传递到可学习聚合#001 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#001', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '一、消息传递范式', 1, 'papers/gnn_survey.md', 6, 12, '消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。设节点集合为 $V$，边集合为 $E$，第 $l$ 层的更新可以写成\n\n$$h_v^{(l+1)} = \\mathrm{UPDATE}^{(l)}\\left(h_v^{(l)}, \\mathrm{AGGREGATE}^{(l)}(\\{h_u^{(l)} : u \\in N(v)\\})\\right)$$\n\n其中 $N(v)$ 表示节点 $v$ 的一跳邻居集合。AGGREGATE 要求置换不变，UPDATE 要求与邻居数量无关，否则大度数节点会破坏规模一致性。', AI_EMBED('pp_embed', '一、消息传递范式\n消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。设节点集合为 $V$，边集合为 $E$，第 $l$ 层的更新可以写成\n\n$$h_v^{(l+1)} = \\mathrm{UPDATE}^{(l)}\\left(h_v^{(l)}, \\mathrm{AGGREGATE}^{(l)}(\\{h_u^{(l)} : u \\in N(v)\\})\\right)$$\n\n其中 $N(v)$ 表示节点 $v$ 的一跳邻居集合。AGGREGATE 要求置换不变，UPDATE 要求与邻居数量无关，否则大度数节点会破坏规模一致性。'))` |
| 98 | 导入资料 | 1 | 4.113 | 写入段落 图神经网络综述-从消息传递到可学习聚合#002 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#002', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '二、邻居聚合算子', 2, 'papers/gnn_survey.md', 14, 16, '常见聚合算子包括求和聚合、平均聚合、最大聚合以及基于注意力的加权聚合。求和聚合实现简单且表达能力强，在同配图上表现稳定；平均聚合对邻居数量不敏感，但会稀释信号；注意力聚合引入可学习权重，可以区分邻居的重要性，但额外增加了参数量与过拟合风险。', AI_EMBED('pp_embed', '二、邻居聚合算子\n常见聚合算子包括求和聚合、平均聚合、最大聚合以及基于注意力的加权聚合。求和聚合实现简单且表达能力强，在同配图上表现稳定；平均聚合对邻居数量不敏感，但会稀释信号；注意力聚合引入可学习权重，可以区分邻居的重要性，但额外增加了参数量与过拟合风险。'))` |
| 99 | 导入资料 | 1 | 4.631 | 写入段落 图神经网络综述-从消息传递到可学习聚合#003 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#003', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '三、过平滑与跳连', 3, 'papers/gnn_survey.md', 18, 20, '随着层数增加，所有节点的表示会趋于一致，这就是过平滑现象。常用缓解手段包括残差连接、初始残差（initial residual）、PairNorm 归一化，以及把底层原始特征直接拼接到高层表示上。残差连接在实现上最简单，通常能带来稳定的收益。', AI_EMBED('pp_embed', '三、过平滑与跳连\n随着层数增加，所有节点的表示会趋于一致，这就是过平滑现象。常用缓解手段包括残差连接、初始残差（initial residual）、PairNorm 归一化，以及把底层原始特征直接拼接到高层表示上。残差连接在实现上最简单，通常能带来稳定的收益。'))` |
| 100 | 导入资料 | 1 | 4.668 | 写入段落 图神经网络综述-从消息传递到可学习聚合#004 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#004', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '四、邻居采样与规模扩展', 4, 'papers/gnn_survey.md', 22, 24, '全图卷积在节点规模达到百万级时显存开销无法接受。邻居采样（neighbor sampling）按层采样有限数量的邻居，把大图切成小批；GraphSAGE 的采样器按均匀分布抽取固定数量的邻居，Cluster-GCN 则按节点簇进行划分。采样引入的方差可以通过多层聚合与均值池化缓解。', AI_EMBED('pp_embed', '四、邻居采样与规模扩展\n全图卷积在节点规模达到百万级时显存开销无法接受。邻居采样（neighbor sampling）按层采样有限数量的邻居，把大图切成小批；GraphSAGE 的采样器按均匀分布抽取固定数量的邻居，Cluster-GCN 则按节点簇进行划分。采样引入的方差可以通过多层聚合与均值池化缓解。'))` |
| 101 | 导入资料 | 1 | 4.553 | 写入段落 图神经网络综述-从消息传递到可学习聚合#005 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#005', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '五、可学习聚合与超图', 5, 'papers/gnn_survey.md', 26, 28, '可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。', AI_EMBED('pp_embed', '五、可学习聚合与超图\n可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。'))` |
| 102 | 导入资料 | 1 | 4.106 | 写入段落 图神经网络综述-从消息传递到可学习聚合#006 | `INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#006', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '六、结论与展望', 6, 'papers/gnn_survey.md', 30, 31, '消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。后续工作需要在表达能力、效率与可解释性之间继续寻找平衡。', AI_EMBED('pp_embed', '六、结论与展望\n消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。后续工作需要在表达能力、效率与可解释性之间继续寻找平衡。'))` |
| 103 | 导入资料 | 1 | 1.128 | 记录日志 ingest | `INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('图神经网络综述-从消息传递到可学习聚合', '', 'ingest', '', 0, '导入 7 个段落')` |
| 104 | 混合检索-全文通道 | 19 | 1.696 | BM25 全文检索 | `SELECT chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, MATCH(title, content) AGAINST ('图神经网络 消息传递 邻居聚合' IN NATURAL LANGUAGE MODE) AS bm25_score FROM paperpocket.paper_chunks WHERE MATCH(title, content) AGAINST ('图神经网络 消息传递 邻居聚合' IN NATURAL LANGUAGE MODE) ORDER BY bm25_score DESC LIMIT 40` |
| 105 | 混合检索-向量通道 | 40 | 6.639 | 向量 ANN 检索 | `SELECT chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, l2_distance(emb, '[0.000000,0.000000,0.316228,0.000000,0.316228,0.000000,-0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.316228,0.000000,0.316228,-0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,-0.316228,0.000000,0.000000,0.000000]') AS ann_distance FROM paperpocket.paper_chunks  ORDER BY l2_distance(emb, '[0.000000,0.000000,0.316228,0.000000,0.316228,0.000000,-0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.316228,0.000000,0.316228,-0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,-0.316228,0.000000,0.000000,0.000000]') APPROXIMATE LIMIT 40` |
| 106 | 混合检索-向量通道 | 40 | 1.913 | 向量 ANN 检索 | `SELECT chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, l2_distance(emb, '[0.000000,0.000000,0.343173,0.000000,0.343173,0.000000,-0.241955,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.343173,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.343173,0.000000,0.241955,0.000000,0.343173,-0.343173,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.241955,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,-0.343173,0.000000,0.000000,0.000000]') AS ann_distance FROM paperpocket.paper_chunks  ORDER BY l2_distance(emb, '[0.000000,0.000000,0.343173,0.000000,0.343173,0.000000,-0.241955,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.343173,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.343173,0.000000,0.241955,0.000000,0.343173,-0.343173,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.241955,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,-0.343173,0.000000,0.000000,0.000000]') APPROXIMATE LIMIT 40` |
| 107 | 混合检索-向量通道 | 1 | 0.681 | 探测摘要模型是否已注册 | `SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = 'pp_summarizer'` |
| 108 | 混合检索-向量通道 | 1 | 0.498 | 探测摘要端点是否已注册 | `SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS WHERE AI_MODEL_NAME = 'pp_summarizer'` |
| 109 | 简报生成-AI_COMPLETE | 1 | 3.633 | seekdb AI_COMPLETE 生成简报 | `SELECT AI_COMPLETE('pp_summarizer', '请根据下面的检索结果，用中文写一段不超过 200 字的研究简报。\n\n【检索词】\n图神经网络 消息传递 邻居聚合\n\n【资料片段】\n1. 《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:30-31\n消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。后续工作需要在表达能力、效率与可解释性之间继续寻找平衡。\n\n2. 《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:2-4\n图神经网络（Graph Neural Network, GNN）是一类直接在图结构上定义卷积运算的深度模型。本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。\n\n3. 《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:26-28\n可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。\n\n4. 《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:6-12\n消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。设节点集合为 $V$，边集合为 $E$，第 $l$ 层的更新可以写成\n\n$$h_v^{(l+1)} = \\mathrm{UPDATE}^{(l)}\\left(h_v^{(l)}, \\math\n\n5. 《课程笔记：图神经网络基础（第 6-9 周）》 notes/课程笔记-图神经网络基础.md:22-25\n1. 采样引入的方差如何在多层之间传递？\n2. 注意力聚合在度数差异大的图上是否稳定？\n3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。\n\n【要求】\n1. 只使用上面给出的资料，不要编造结论；\n2. 给出 3-5 条要点，每条一行，以「- 」开头；\n3. 末尾用一行标注主要来源文件。') AS brief` |
| 110 | 保存简报 | 1 | 7.650 | 保存简报 | `INSERT INTO briefs (query_text, brief_md, engine, model_name, source_keys) VALUES ('图神经网络 消息传递 邻居聚合', '- 消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。\n- 超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。\n- 本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。\n- 消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。\n- 可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。\n来源：《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:30-31；《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:26-28；《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:2-4', 'seekdb-ai-complete', 'pp_summarizer', '图神经网络综述-从消息传递到可学习聚合#006,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001,课程笔记-图神经网络基础-第-6-9-周#004')` |
| 111 | 记录简报来源 | 1 | 1.091 | 记录简报来源 | `INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('图神经网络综述-从消息传递到可学习聚合', '图神经网络综述-从消息传递到可学习聚合#006', 'brief', '图神经网络 消息传递 邻居聚合', 0.078054, '简报引用')` |
| 112 | 记录简报来源 | 1 | 1.033 | 记录简报来源 | `INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('图神经网络综述-从消息传递到可学习聚合', '图神经网络综述-从消息传递到可学习聚合#000', 'brief', '图神经网络 消息传递 邻居聚合', 0.076210, '简报引用')` |
| 113 | 未标注 | 0 | 0.225 | 切换默认数据库 | `USE `paperpocket`` |
| 114 | 未标注 | 1 | 2.388 | 统计 papers 行数 | `SELECT COUNT(*) AS cnt FROM `paperpocket`.`papers`` |
| 115 | 未标注 | 1 | 3.410 | 统计 paper_chunks 行数 | `SELECT COUNT(*) AS cnt FROM `paperpocket`.`paper_chunks`` |
| 116 | 未标注 | 1 | 2.157 | 统计 reading_log 行数 | `SELECT COUNT(*) AS cnt FROM `paperpocket`.`reading_log`` |
| 117 | 未标注 | 1 | 1.942 | 统计 briefs 行数 | `SELECT COUNT(*) AS cnt FROM `paperpocket`.`briefs`` |
| 118 | 未标注 | 4 | 2.781 | 查看 papers 的索引 | `SHOW INDEX FROM `paperpocket`.`papers`` |
| 119 | 未标注 | 6 | 2.797 | 查看 paper_chunks 的索引 | `SHOW INDEX FROM `paperpocket`.`paper_chunks`` |
| 120 | 未标注 | 1 | 1.044 | 服务端版本 | `SELECT version() AS version` |

## 全文可读版

### 1. 未标注（删除旧模型 pp_embed，0 行）

```sql
CALL DBMS_AI_SERVICE.DROP_AI_MODEL('pp_embed')
```

### 2. 未标注（删除旧端点 pp_embed，0 行）

```sql
CALL DBMS_AI_SERVICE.DROP_AI_MODEL_ENDPOINT('pp_embed')
```

### 3. 未标注（删除旧模型 pp_summarizer，0 行）

```sql
CALL DBMS_AI_SERVICE.DROP_AI_MODEL('pp_summarizer')
```

### 4. 未标注（删除旧端点 pp_summarizer，0 行）

```sql
CALL DBMS_AI_SERVICE.DROP_AI_MODEL_ENDPOINT('pp_summarizer')
```

### 5. 未标注（注册嵌入模型 pp_embed，0 行）

```sql
CALL DBMS_AI_SERVICE.CREATE_AI_MODEL('pp_embed', '{"type":"DENSE_EMBEDDING","model_name":"paperpocket-local"}')
```

### 6. 未标注（注册嵌入端点 pp_embed，0 行）

```sql
CALL DBMS_AI_SERVICE.CREATE_AI_MODEL_ENDPOINT('pp_embed', '{"ai_model_name":"pp_embed","url":"http://127.0.0.1:8300/v1/embeddings","access_key":"local","provider":"openai","request_model_name":"paperpocket-local"}')
```

### 7. 未标注（注册摘要模型 pp_summarizer，0 行）

```sql
CALL DBMS_AI_SERVICE.CREATE_AI_MODEL('pp_summarizer', '{"type":"COMPLETION","model_name":"paperpocket-local"}')
```

### 8. 未标注（注册摘要端点 pp_summarizer，0 行）

```sql
CALL DBMS_AI_SERVICE.CREATE_AI_MODEL_ENDPOINT('pp_summarizer', '{"ai_model_name":"pp_summarizer","url":"http://127.0.0.1:8300/v1/chat/completions","access_key":"local","provider":"openai","request_model_name":"paperpocket-local"}')
```

### 9. 未标注（探测 AI 模型是否已注册，1 行）

```sql
SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = 'pp_embed'
```

### 10. 未标注（探测 AI 模型端点是否已注册，1 行）

```sql
SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS WHERE AI_MODEL_NAME = 'pp_embed'
```

### 11. 未标注（探测摘要模型是否已注册，1 行）

```sql
SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = 'pp_summarizer'
```

### 12. 未标注（探测摘要端点是否已注册，1 行）

```sql
SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS WHERE AI_MODEL_NAME = 'pp_summarizer'
```

### 13. 建库建表（建库建表，1 行）

```sql
CREATE DATABASE IF NOT EXISTS `paperpocket`
```

### 14. 建库建表（建库建表，0 行）

```sql
USE `paperpocket`
```

### 15. 建库建表（建库建表，0 行）

```sql
CREATE TABLE IF NOT EXISTS papers (
            doc_key VARCHAR(96) NOT NULL,
            title VARCHAR(512) NOT NULL,
            authors VARCHAR(512) NOT NULL DEFAULT '',
            year INT NOT NULL DEFAULT 0,
            venue VARCHAR(256) NOT NULL DEFAULT '',
            tags VARCHAR(256) NOT NULL DEFAULT '',
            kind VARCHAR(32) NOT NULL DEFAULT 'paper',
            source_path VARCHAR(512) NOT NULL DEFAULT '',
            summary MEDIUMTEXT,
            content MEDIUMTEXT NOT NULL,
            emb VECTOR(64),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
```

### 16. 建库建表（建库建表，0 行）

```sql
CREATE TABLE IF NOT EXISTS paper_chunks (
            chunk_key VARCHAR(128) NOT NULL,
            doc_key VARCHAR(96) NOT NULL,
            title VARCHAR(512) NOT NULL,
            authors VARCHAR(512) NOT NULL DEFAULT '',
            year INT NOT NULL DEFAULT 0,
            venue VARCHAR(256) NOT NULL DEFAULT '',
            tags VARCHAR(256) NOT NULL DEFAULT '',
            heading VARCHAR(256) NOT NULL DEFAULT '',
            seq INT NOT NULL DEFAULT 0,
            source_path VARCHAR(512) NOT NULL DEFAULT '',
            start_line INT NOT NULL DEFAULT 0,
            end_line INT NOT NULL DEFAULT 0,
            content MEDIUMTEXT NOT NULL,
            emb VECTOR(64),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
```

### 17. 建库建表（建库建表，0 行）

```sql
CREATE TABLE IF NOT EXISTS reading_log (
            id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            doc_key VARCHAR(96) NOT NULL DEFAULT '',
            chunk_key VARCHAR(128) NOT NULL DEFAULT '',
            action VARCHAR(32) NOT NULL,
            query_text VARCHAR(512) NOT NULL DEFAULT '',
            score DOUBLE NOT NULL DEFAULT 0,
            detail TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
```

### 18. 建库建表（建库建表，0 行）

```sql
CREATE TABLE IF NOT EXISTS briefs (
            id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            query_text VARCHAR(512) NOT NULL,
            brief_md MEDIUMTEXT NOT NULL,
            engine VARCHAR(32) NOT NULL,
            model_name VARCHAR(64) NOT NULL DEFAULT '',
            source_keys TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
```

### 19. 建索引（查看 papers 的索引，0 行）

```sql
SHOW INDEX FROM `paperpocket`.`papers`
```

### 20. 建索引（建索引，0 行）

```sql
CREATE UNIQUE INDEX uk_papers_doc ON papers (doc_key)
```

### 21. 建索引（查看 paper_chunks 的索引，0 行）

```sql
SHOW INDEX FROM `paperpocket`.`paper_chunks`
```

### 22. 建索引（建索引，0 行）

```sql
CREATE UNIQUE INDEX uk_chunks_key ON paper_chunks (chunk_key)
```

### 23. 建索引（建索引，0 行）

```sql
CREATE INDEX idx_chunks_doc ON paper_chunks (doc_key)
```

### 24. 建索引（建索引，0 行）

```sql
CREATE INDEX idx_chunks_year ON paper_chunks (year)
```

### 25. 建索引（建索引，0 行）

```sql
CREATE FULLTEXT INDEX ft_papers ON papers (title, content) WITH PARSER ngram
```

### 26. 建索引（建索引，0 行）

```sql
CREATE FULLTEXT INDEX ft_chunks ON paper_chunks (title, content) WITH PARSER ngram
```

### 27. 建索引（建索引，0 行）

```sql
CREATE VECTOR INDEX vi_papers ON papers (emb) WITH (distance=l2, type=hnsw, lib=vsag)
```

### 28. 建索引（建索引，0 行）

```sql
CREATE VECTOR INDEX vi_chunks ON paper_chunks (emb) WITH (distance=l2, type=hnsw, lib=vsag)
```

### 29. 建索引（探测 AI 模型是否已注册，1 行）

```sql
SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = 'pp_embed'
```

### 30. 建索引（探测 AI 模型端点是否已注册，1 行）

```sql
SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS WHERE AI_MODEL_NAME = 'pp_embed'
```

### 31. 导入资料（清理旧段落 实验记录-邻居采样规模对图分类精度的影响，0 行）

```sql
DELETE FROM paper_chunks WHERE doc_key = '实验记录-邻居采样规模对图分类精度的影响'
```

### 32. 导入资料（清理旧论文 实验记录-邻居采样规模对图分类精度的影响，0 行）

```sql
DELETE FROM papers WHERE doc_key = '实验记录-邻居采样规模对图分类精度的影响'
```

### 33. 导入资料（探测 AI 模型是否已注册，1 行）

```sql
SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = 'pp_embed'
```

### 34. 导入资料（探测 AI 模型端点是否已注册，1 行）

```sql
SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS WHERE AI_MODEL_NAME = 'pp_embed'
```

### 35. 导入资料（写入论文 实验记录-邻居采样规模对图分类精度的影响，1 行）

```sql
INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', 'note', 'notes/实验记录-邻居采样规模.md', '- 验证"邻居采样数量"这一超参对图分类精度的影响，并观察不同聚合算子（sum / mean / max / attention）之间的差异。\n- Cora 上采样 10 个邻居时精度最高，均值 0.813，标准差 0.009；\n- Citeseer 上采样 5 个邻居均值 0.706，采样全部邻居均值 0.712，差异在标准差范围内。\n来源：# 实验目的', '# 实验目的\n\n验证"邻居采样数量"这一超参对图分类精度的影响，并观察不同聚合算子（sum / mean / max / attention）之间的差异。\n\n# 实验设置\n\n数据集使用 Cora 与 Citeseer 两个引文网络，统一两层 GCN，第一层隐层维度 64，第二层 128，dropout 0.5，优化器 Adam，学习率 0.01，权重衰减 5e-4。采样邻居数分别取 5、10、20、全部。每个配置重复 10 次取均值与标准差。\n\n# 实验结果\n\nCora 上采样 10 个邻居时精度最高，均值 0.813，标准差 0.009；采样全部邻居均值 0.807，标准差 0.007。Citeseer 上采样 5 个邻居均值 0.706，采样全部邻居均值 0.712，差异在标准差范围内。\n\n注意力聚合在两个数据集上都略优于 sum 聚合，Cora 上均值 0.822 / Citeseer 上 0.715，但参数量与显存开销明显更高，训练时间约是 sum 聚合的 2.3 倍。\n\n# 结论与反思\n\n采���数量存在甜点区，太少会丢失信息，太多则增加计算量且收益有限。注意力聚合的优势在引文网络这种同配图上并不明显，在异配图上可能更值得关注——这一点还需要补充实验。\n\n# 下一步\n\n1. 补做 heterophilous 数据集（如 Texas）上的对比；\n2. 记录训练过程中的显存占用曲线；\n3. 把固定随机种子的配置写进实验脚本，保证结果可复现。', AI_EMBED('pp_embed', '实验记录：邻居采样规模对图分类精度的影响\n# 实验目的\n\n验证"邻居采样数量"这一超参对图分类精度的影响，并观察不同聚合算子（sum / mean / max / attention）之间的差异。\n\n# 实验设置\n\n数据集使用 Cora 与 Citeseer 两个引文网络，统一两层 GCN，第一层隐层维度 64，第二层 128，dropout 0.5，优化器 Adam，学习率 0.01，权重衰减 5e-4。采样邻居数分别取 5、10、20、全部。每个配置重复 10 次取均值与标准差。\n\n# 实验结果\n\nCora 上采样 10 个邻居时精度最高，均值 0.813，标准差 0.009；采样全部邻居均值 0.807，标准差 0.007。Citeseer 上采样 5 个邻居均值 0.706，采样全部邻居均值 0.712，差异在标准差范围内。\n\n注意力聚合在两个数据集上都略优于 sum 聚合，Cora 上均值 0.822 / Citeseer 上 0.715，但参数量与显存开销明显更高，训练时间约是 sum 聚合的 2.3 倍。\n\n# 结论与反思\n\n采���数量存在甜点区，太少会丢失信息，太多则增加计算量且收益有限。注意力聚合的优势在引文网络这种同配图上并不明显，在异配图上可能更值得关注——这一点还需要补充实验。\n\n# 下一步\n\n1. 补做 heterophilous 数据集（如 Texas）上的对比；\n2. 记录训练过程中的显存占用曲线；\n3. 把固定随机种子的配置写进实验脚本，保证结果可复现。'))
```

### 36. 导入资料（写入段落 实验记录-邻居采样规模对图分类精度的影响#000，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响#000', '实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', '实验目的', 0, 'notes/实验记录-邻居采样规模.md', 2, 4, '验证"邻居采样数量"这一超参对图分类精度的影响，并观察不同聚合算子（sum / mean / max / attention）之间的差异。', AI_EMBED('pp_embed', '实验目的\n验证"邻居采样数量"这一超参对图分类精度的影响，并观察不同聚合算子（sum / mean / max / attention）之间的差异。'))
```

### 37. 导入资料（写入段落 实验记录-邻居采样规模对图分类精度的影响#001，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响#001', '实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', '实验设置', 1, 'notes/实验记录-邻居采样规模.md', 6, 8, '数据集使用 Cora 与 Citeseer 两个引文网络，统一两层 GCN，第一层隐层维度 64，第二层 128，dropout 0.5，优化器 Adam，学习率 0.01，权重衰减 5e-4。采样邻居数分别取 5、10、20、全部。每个配置重复 10 次取均值与标准差。', AI_EMBED('pp_embed', '实验设置\n数据集使用 Cora 与 Citeseer 两个引文网络，统一两层 GCN，第一层隐层维度 64，第二层 128，dropout 0.5，优化器 Adam，学习率 0.01，权重衰减 5e-4。采样邻居数分别取 5、10、20、全部。每个配置重复 10 次取均值与标准差。'))
```

### 38. 导入资料（写入段落 实验记录-邻居采样规模对图分类精度的影响#002，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响#002', '实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', '实验结果', 2, 'notes/实验记录-邻居采样规模.md', 10, 14, 'Cora 上采样 10 个邻居时精度最高，均值 0.813，标准差 0.009；采样全部邻居均值 0.807，标准差 0.007。Citeseer 上采样 5 个邻居均值 0.706，采样全部邻居均值 0.712，差异在标准差范围内。\n\n注意力聚合在两个数据集上都略优于 sum 聚合，Cora 上均值 0.822 / Citeseer 上 0.715，但参数量与显存开销明显更高，训练时间约是 sum 聚合的 2.3 倍。', AI_EMBED('pp_embed', '实验结果\nCora 上采样 10 个邻居时精度最高，均值 0.813，标准差 0.009；采样全部邻居均值 0.807，标准差 0.007。Citeseer 上采样 5 个邻居均值 0.706，采样全部邻居均值 0.712，差异在标准差范围内。\n\n注意力聚合在两个数据集上都略优于 sum 聚合，Cora 上均值 0.822 / Citeseer 上 0.715，但参数量与显存开销明显更高，训练时间约是 sum 聚合的 2.3 倍。'))
```

### 39. 导入资料（写入段落 实验记录-邻居采样规模对图分类精度的影响#003，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响#003', '实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', '结论与反思', 3, 'notes/实验记录-邻居采样规模.md', 16, 18, '采���数量存在甜点区，太少会丢失信息，太多则增加计算量且收益有限。注意力聚合的优势在引文网络这种同配图上并不明显，在异配图上可能更值得关注——这一点还需要补充实验。', AI_EMBED('pp_embed', '结论与反思\n采���数量存在甜点区，太少会丢失信息，太多则增加计算量且收益有限。注意力聚合的优势在引文网络这种同配图上并不明显，在异配图上可能更值得关注——这一点还需要补充实验。'))
```

### 40. 导入资料（写入段落 实验记录-邻居采样规模对图分类精度的影响#004，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('实验记录-邻居采样规模对图分类精度的影响#004', '实验记录-邻居采样规模对图分类精度的影响', '实验记录：邻居采样规模对图分类精度的影响', '本人', 2025, '课程项目日志', 'experiment,gnn,sampling,ablation', '下一步', 4, 'notes/实验记录-邻居采样规模.md', 20, 23, '1. 补做 heterophilous 数据集（如 Texas）上的对比；\n2. 记录训练过程中的显存占用曲线；\n3. 把固定随机种子的配置写进实验脚本，保证结果可复现。', AI_EMBED('pp_embed', '下一步\n1. 补做 heterophilous 数据集（如 Texas）上的对比；\n2. 记录训练过程中的显存占用曲线；\n3. 把固定随机种子的配置写进实验脚本，保证结果可复现。'))
```

### 41. 导入资料（记录日志 ingest，1 行）

```sql
INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('实验记录-邻居采样规模对图分类精度的影响', '', 'ingest', '', 0, '导入 5 个段落')
```

### 42. 导入资料（清理旧段落 文献综述写作与检索习惯笔记，0 行）

```sql
DELETE FROM paper_chunks WHERE doc_key = '文献综述写作与检索习惯笔记'
```

### 43. 导入资料（清理旧论文 文献综述写作与检索习惯笔记，0 行）

```sql
DELETE FROM papers WHERE doc_key = '文献综述写作与检索习惯笔记'
```

### 44. 导入资料（写入论文 文献综述写作与检索习惯笔记，1 行）

```sql
INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', 'note', 'notes/文献综述写作与检索习惯.md', '- # 二、检索习惯\n- 复习期末的笔记时，完全不记得当初把结论写在哪一篇里，希望系统能记住"我读过什么、读到哪一段"，再次检索时把已经读过的内容标出来或直接跳过。\n- 现在希望把论文和笔记都放进一个库里，用关键词加语义混合检索，三秒内定位到具体段落。\n来源：# 一、为什么要做文献库', '# 一、为什么要做文献库\n\n写综述时最大的成本不是读论文，而是"找不到读过的那篇"。以前用文件夹分类，文件名混乱，半年后完全检索不到。现在希望把论文和笔记都放进一个库里，用关键词加语义混合检索，三秒内定位到具体段落。\n\n# 二、检索习惯\n\n我习惯用两类词混合搜索：专业术语（例如"消息传递"、"过平滑"）用来精确命中，描述性表述（例如"邻居太多会不会学不出来"）用来找语义相近的段落。关键词检索负责前者，向量检索负责后者。\n\n另外经常需要按年份与标签过滤，例如"只看 2023 年之后的图神经网络相关笔记"。\n\n# 三、复习时的痛点\n\n复习期末的笔记时，完全不记得当初把结论写在哪一篇里，希望系统能记住"我读过什么、读到哪一段"，再次检索时把已经读过的内容标出来或直接跳过。\n\n# 四、工具链设想\n\n1. 导入：把 Markdown 笔记与论文正文切块入库；\n2. 检索：全文索引 + 向量索引 + 年份/标签过滤；\n3. 摘要：把命中的段落压缩成一段话；\n4. 记忆：记住研究方向、检索历史与阅读进度。\n\n# 五、写作规范\n\n每条结论都要能指回原文的段落位置，检索结果必须带出处，否则不敢引用。摘要只允许使用检索到的材料，不允许模型自由发挥。', AI_EMBED('pp_embed', '文献综述写作与检索习惯笔记\n# 一、为什么要做文献库\n\n写综述时最大的成本不是读论文，而是"找不到读过的那篇"。以前用文件夹分类，文件名混乱，半年后完全检索不到。现在希望把论文和笔记都放进一个库里，用关键词加语义混合检索，三秒内定位到具体段落。\n\n# 二、检索习惯\n\n我习惯用两类词混合搜索：专业术语（例如"消息传递"、"过平滑"）用来精确命中，描述性表述（例如"邻居太多会不会学不出来"）用来找语义相近的段落。关键词检索负责前者，向量检索负责后者。\n\n另外经常需要按年份与标签过滤，例如"只看 2023 年之后的图神经网络相关笔记"。\n\n# 三、复习时的痛点\n\n复习期末的笔记时，完全不记得当初把结论写在哪一篇里，希望系统能记住"我读过什么、读到哪一段"，再次检索时把已经读过的内容标出来或直接跳过。\n\n# 四、工具链设想\n\n1. 导入：把 Markdown 笔记与论文正文切块入库；\n2. 检索：全文索引 + 向量索引 + 年份/标签过滤；\n3. 摘要：把命中的段落压缩成一段话；\n4. 记忆：记住研究方向、检索历史与阅读进度。\n\n# 五、写作规范\n\n每条结论都要能指回原文的段落位置，检索结果必须带出处，否则不敢引用。摘要只允许使用检索到的材料，不允许模型自由发挥。'))
```

### 45. 导入资料（写入段落 文献综述写作与检索习惯笔记#000，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('文献综述写作与检索习惯笔记#000', '文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', '一、为什么要做文献库', 0, 'notes/文献综述写作与检索习惯.md', 2, 4, '写综述时最大的成本不是读论文，而是"找不到读过的那篇"。以前用文件夹分类，文件名混乱，半年后完全检索不到。现在希望把论文和笔记都放进一个库里，用关键词加语义混合检索，三秒内定位到具体段落。', AI_EMBED('pp_embed', '一、为什么要做文献库\n写综述时最大的成本不是读论文，而是"找不到读过的那篇"。以前用文件夹分类，文件名混乱，半年后完全检索不到。现在希望把论文和笔记都放进一个库里，用关键词加语义混合检索，三秒内定位到具体段落。'))
```

### 46. 导入资料（写入段落 文献综述写作与检索习惯笔记#001，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('文献综述写作与检索习惯笔记#001', '文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', '二、检索习惯', 1, 'notes/文献综述写作与检索习惯.md', 6, 10, '我习惯用两类词混合搜索：专业术语（例如"消息传递"、"过平滑"）用来精确命中，描述性表述（例如"邻居太多会不会学不出来"）用来找语义相近的段落。关键词检索负责前者，向量检索负责后者。\n\n另外经常需要按年份与标签过滤，例如"只看 2023 年之后的图神经网络相关笔记"。', AI_EMBED('pp_embed', '二、检索习惯\n我习惯用两类词混合搜索：专业术语（例如"消息传递"、"过平滑"）用来精确命中，描述性表述（例如"邻居太多会不会学不出来"）用来找语义相近的段落。关键词检索负责前者，向量检索负责后者。\n\n另外经常需要按年份与标签过滤，例如"只看 2023 年之后的图神经网络相关笔记"。'))
```

### 47. 导入资料（写入段落 文献综述写作与检索习惯笔记#002，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('文献综述写作与检索习惯笔记#002', '文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', '三、复习时的痛点', 2, 'notes/文献综述写作与检索习惯.md', 12, 14, '复习期末的笔记时，完全不记得当初把结论写在哪一篇里，希望系统能记住"我读过什么、读到哪一段"，再次检索时把已经读过的内容标出来或直接跳过。', AI_EMBED('pp_embed', '三、复习时的痛点\n复习期末的笔记时，完全不记得当初把结论写在哪一篇里，希望系统能记住"我读过什么、读到哪一段"，再次检索时把已经读过的内容标出来或直接跳过。'))
```

### 48. 导入资料（写入段落 文献综述写作与检索习惯笔记#003，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('文献综述写作与检索习惯笔记#003', '文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', '四、工具链设想', 3, 'notes/文献综述写作与检索习惯.md', 16, 21, '1. 导入：把 Markdown 笔记与论文正文切块入库；\n2. 检索：全文索引 + 向量索引 + 年份/标签过滤；\n3. 摘要：把命中的段落压缩成一段话；\n4. 记忆：记住研究方向、检索历史与阅读进度。', AI_EMBED('pp_embed', '四、工具链设想\n1. 导入：把 Markdown 笔记与论文正文切块入库；\n2. 检索：全文索引 + 向量索引 + 年份/标签过滤；\n3. 摘要：把命中的段落压缩成一段话；\n4. 记忆：记住研究方向、检索历史与阅读进度。'))
```

### 49. 导入资料（写入段落 文献综述写作与检索习惯笔记#004，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('文献综述写作与检索习惯笔记#004', '文献综述写作与检索习惯笔记', '文献综述写作与检索习惯笔记', '本人', 2024, '个人知识管理', 'writing,workflow,reading,note', '五、写作规范', 4, 'notes/文献综述写作与检索习惯.md', 23, 24, '每条结论都要能指回原文的段落位置，检索结果必须带出处，否则不敢引用。摘要只允许使用检索到的材料，不允许模型自由发挥。', AI_EMBED('pp_embed', '五、写作规范\n每条结论都要能指回原文的段落位置，检索结果必须带出处，否则不敢引用。摘要只允许使用检索到的材料，不允许模型自由发挥。'))
```

### 50. 导入资料（记录日志 ingest，1 行）

```sql
INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('文献综述写作与检索习惯笔记', '', 'ingest', '', 0, '导入 5 个段落')
```

### 51. 导入资料（清理旧段落 课程笔记-图神经网络基础-第-6-9-周，0 行）

```sql
DELETE FROM paper_chunks WHERE doc_key = '课程笔记-图神经网络基础-第-6-9-周'
```

### 52. 导入资料（清理旧论文 课程笔记-图神经网络基础-第-6-9-周，0 行）

```sql
DELETE FROM papers WHERE doc_key = '课程笔记-图神经网络基础-第-6-9-周'
```

### 53. 导入资料（写入论文 课程笔记-图神经网络基础-第-6-9-周，1 行）

```sql
INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', 'note', 'notes/课程笔记-图神经网络基础.md', '- 拉普拉斯矩阵 $L = D - A$ 是谱图卷积的基础，规格化版本 $L = I - D^{-1/2} A D^{-1/2}$ 的特征向量与图上的拉普拉斯算子特征函数一一对应。\n- 全图训练在 Cora 上没问题，但换成百万节点的引文网络就必须采样。\n- 3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。\n来源：# 第 6 周：图与邻接矩阵', '# 第 6 周：图与邻接矩阵\n\n今天从最基础的图表示开始。图 $G=(V,E)$ 可以用邻接矩阵 $A$ 稠密表示，也可以用边列表稀疏表示。稀疏表示在大图上更省内存，邻接矩阵方便写矩阵形式化的公式。度矩阵 $D$ 的对角线是每个节点的度。\n\n拉普拉斯矩阵 $L = D - A$ 是谱图卷积的基础，规格化版本 $L = I - D^{-1/2} A D^{-1/2}$ 的特征向量与图上的拉普拉斯算子特征函数一一对应。\n\n# 第 7 周：消息传递的三个步骤\n\n老师强调消息传递范式可以拆成 message、aggregate、update 三步。AGGREGATE 必须置换不变，这一点决定了不能用普通 MLP 直接对邻居表示做拼接。UPDATE 需要与邻居数量无关，否则节点度数差异会造成表示尺度不一致。\n\n作业：用 PyTorch 实现 sum / mean / max 三种聚合，并在一���小图上验证置换不变性。\n\n# 第 8 周：过平滑与残差连接\n\n过平滑的直观解释是：层数增加后，所有节点的表示互相靠拢，节点之间不再可区分。缓解手段里残差连接最容易实现，加上以后深层 GNN 的节点分类精度不再下降。PairNorm 的思路是对每一层的表示做标准化，强行维持方差。\n\n# 第 9 周：邻居采样\n\n采样是为了把大图切成小批。全图训练在 Cora 上没问题，但换成百万节点的引文网络就必须采样。GraphSAGE 的采样器每层固定采一定数量的邻居，Cluster-GCN 先做图聚类再切分。前者实现简单，后者对内存更友好。\n\n# 课后遗留问题\n\n1. 采样引入的方差如何在多层之间传递？\n2. 注意力聚合在度数差异大的图上是否稳定？\n3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。', AI_EMBED('pp_embed', '课程笔记：图神经网络基础（第 6-9 周）\n# 第 6 周：图与邻接矩阵\n\n今天从最基础的图表示开始。图 $G=(V,E)$ 可以用邻接矩阵 $A$ 稠密表示，也可以用边列表稀疏表示。稀疏表示在大图上更省内存，邻接矩阵方便写矩阵形式化的公式。度矩阵 $D$ 的对角线是每个节点的度。\n\n拉普拉斯矩阵 $L = D - A$ 是谱图卷积的基础，规格化版本 $L = I - D^{-1/2} A D^{-1/2}$ 的特征向量与图上的拉普拉斯算子特征函数一一对应。\n\n# 第 7 周：消息传递的三个步骤\n\n老师强调消息传递范式可以拆成 message、aggregate、update 三步。AGGREGATE 必须置换不变，这一点决定了不能用普通 MLP 直接对邻居表示做拼接。UPDATE 需要与邻居数量无关，否则节点度数差异会造成表示尺度不一致。\n\n作业：用 PyTorch 实现 sum / mean / max 三种聚合，并在一���小图上验证置换不变性。\n\n# 第 8 周：过平滑与残差连接\n\n过平滑的直观解释是：层数增加后，所有节点的表示互相靠拢，节点之间不再可区分。缓解手段里残差连接最容易实现，加上以后深层 GNN 的节点分类精度不再下降。PairNorm 的思路是对每一层的表示做标准化，强行维持方差。\n\n# 第 9 周：邻居采样\n\n采样是为了把大图切成小批。全图训练在 Cora 上没问题，但换成百万节点的引文网络就必须采样。GraphSAGE 的采样器每层固定采一定数量的邻居，Cluster-GCN 先做图聚类再切分。前者实现简单，后者对内存更友好。\n\n# 课后遗留问题\n\n1. 采样引入的方差如何在多层之间传递？\n2. 注意力聚合在度数差异大的图上是否稳定？\n3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。'))
```

### 54. 导入资料（写入段落 课程笔记-图神经网络基础-第-6-9-周#000，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周#000', '课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', '第 6 周：图与邻接矩阵', 0, 'notes/课程笔记-图神经网络基础.md', 2, 6, '今天从最基础的图表示开始。图 $G=(V,E)$ 可以用邻接矩阵 $A$ 稠密表示，也可以用边列表稀疏表示。稀疏表示在大图上更省内存，邻接矩阵方便写矩阵形式化的公式。度矩阵 $D$ 的对角线是每个节点的度。\n\n拉普拉斯矩阵 $L = D - A$ 是谱图卷积的基础，规格化版本 $L = I - D^{-1/2} A D^{-1/2}$ 的特征向量与图上的拉普拉斯算子特征函数一一对应。', AI_EMBED('pp_embed', '第 6 周：图与邻接矩阵\n今天从最基础的图表示开始。图 $G=(V,E)$ 可以用邻接矩阵 $A$ 稠密表示，也可以用边列表稀疏表示。稀疏表示在大图上更省内存，邻接矩阵方便写矩阵形式化的公式。度矩阵 $D$ 的对角线是每个节点的度。\n\n拉普拉斯矩阵 $L = D - A$ 是谱图卷积的基础，规格化版本 $L = I - D^{-1/2} A D^{-1/2}$ 的特征向量与图上的拉普拉斯算子特征函数一一对应。'))
```

### 55. 导入资料（写入段落 课程笔记-图神经网络基础-第-6-9-周#001，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周#001', '课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', '第 7 周：消息传递的三个步骤', 1, 'notes/课程笔记-图神经网络基础.md', 8, 12, '老师强调消息传递范式可以拆成 message、aggregate、update 三步。AGGREGATE 必须置换不变，这一点决定了不能用普通 MLP 直接对邻居表示做拼接。UPDATE 需要与邻居数量无关，否则节点度数差异会造成表示尺度不一致。\n\n作业：用 PyTorch 实现 sum / mean / max 三种聚合，并在一���小图上验证置换不变性。', AI_EMBED('pp_embed', '第 7 周：消息传递的三个步骤\n老师强调消息传递范式可以拆成 message、aggregate、update 三步。AGGREGATE 必须置换不变，这一点决定了不能用普通 MLP 直接对邻居表示做拼接。UPDATE 需要与邻居数量无关，否则节点度数差异会造成表示尺度不一致。\n\n作业：用 PyTorch 实现 sum / mean / max 三种聚合，并在一���小图上验证置换不变性。'))
```

### 56. 导入资料（写入段落 课程笔记-图神经网络基础-第-6-9-周#002，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周#002', '课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', '第 8 周：过平滑与残差连接', 2, 'notes/课程笔记-图神经网络基础.md', 14, 16, '过平滑的直观解释是：层数增加后，所有节点的表示互相靠拢，节点之间不再可区分。缓解手段里残差连接最容易实现，加上以后深层 GNN 的节点分类精度不再下降。PairNorm 的思路是对每一层的表示做标准化，强行维持方差。', AI_EMBED('pp_embed', '第 8 周：过平滑与残差连接\n过平滑的直观解释是：层数增加后，所有节点的表示互相靠拢，节点之间不再可区分。缓解手段里残差连接最容易实现，加上以后深层 GNN 的节点分类精度不再下降。PairNorm 的思路是对每一层的表示做标准化，强行维持方差。'))
```

### 57. 导入资料（写入段落 课程笔记-图神经网络基础-第-6-9-周#003，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周#003', '课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', '第 9 周：邻居采样', 3, 'notes/课程笔记-图神经网络基础.md', 18, 20, '采样是为了把大图切成小批。全图训练在 Cora 上没问题，但换成百万节点的引文网络就必须采样。GraphSAGE 的采样器每层固定采一定数量的邻居，Cluster-GCN 先做图聚类再切分。前者实现简单，后者对内存更友好。', AI_EMBED('pp_embed', '第 9 周：邻居采样\n采样是为了把大图切成小批。全图训练在 Cora 上没问题，但换成百万节点的引文网络就必须采样。GraphSAGE 的采样器每层固定采一定数量的邻居，Cluster-GCN 先做图聚类再切分。前者实现简单，后者对内存更友好。'))
```

### 58. 导入资料（写入段落 课程笔记-图神经网络基础-第-6-9-周#004，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('课程笔记-图神经网络基础-第-6-9-周#004', '课程笔记-图神经网络基础-第-6-9-周', '课程笔记：图神经网络基础（第 6-9 周）', '本人', 2024, '研究生课程《图机器学习》', 'gnn,message-passing,course-note,graph', '课后遗留问题', 4, 'notes/课程笔记-图神经网络基础.md', 22, 25, '1. 采样引入的方差如何在多层之间传递？\n2. 注意力聚合在度数差异大的图上是否稳定？\n3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。', AI_EMBED('pp_embed', '课后遗留问题\n1. 采样引入的方差如何在多层之间传递？\n2. 注意力聚合在度数差异大的图上是否稳定？\n3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。'))
```

### 59. 导入资料（记录日志 ingest，1 行）

```sql
INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('课程笔记-图神经网络基础-第-6-9-周', '', 'ingest', '', 0, '导入 5 个段落')
```

### 60. 导入资料（清理旧段落 attention-is-all-you-need，0 行）

```sql
DELETE FROM paper_chunks WHERE doc_key = 'attention-is-all-you-need'
```

### 61. 导入资料（清理旧论文 attention-is-all-you-need，0 行）

```sql
DELETE FROM papers WHERE doc_key = 'attention-is-all-you-need'
```

### 62. 导入资料（写入论文 attention-is-all-you-need，1 行）

```sql
INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', 'paper', 'papers/attention_is_all_you_need.md', '- The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.\n- $$\\mathrm{Attention}(Q, K, V) = \\mathrm{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right) V$$\n- 给定输入矩阵 $Q \\in \\mathbb{R}^{n \\times d_k}$、$K \\in \\mathbb{R}^{n \\times d_k}$、$V \\in \\mathbb{R}^{n \\times d_v}$，注意力计算为\n来源：# Abstract', '# Abstract\n\nThe dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.\n\n# 一、自注意力机制\n\n自注意力把序列中每个位置表示为对所有位置加权和。给定输入矩阵 $Q \\in \\mathbb{R}^{n \\times d_k}$、$K \\in \\mathbb{R}^{n \\times d_k}$、$V \\in \\mathbb{R}^{n \\times d_v}$，注意力计算为\n\n$$\\mathrm{Attention}(Q, K, V) = \\mathrm{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right) V$$\n\n缩放因子 $\\sqrt{d_k}$ 用来避免维度变大时 softmax 进入饱和区���，梯度消失。多头注意力把表示切分成多份分别做注意力再拼接，使模型能在不同子空间里关注不同关系。\n\n# 二、位置编码\n\n由于自注意力本身不含位置信息，模型必须显式注入顺序。论文采用正弦位置编码\n\n$$PE_{(pos, 2i)} = \\sin\\left(pos / 10000^{2i/d_{model}}\\right)$$\n\n它既能表示绝对位置，也便于模型推断相对位置关系，并且可以外推到比训练时更长的序列。\n\n# 三、多头注意力的并行计算\n\n多头注意力的投影矩阵可以合并成一次大矩阵乘法实现，从而充分利用矩阵乘法的并行性。实践中注意力矩阵的显存占用是主要瓶颈，因此实现时通常使用 FlashAttention 一类的核融合算子把中间结果留在片上缓存。\n\n# 四、编码器与解码器\n\n编码器由多头自注意力、前馈网络、残差连接与层归一化堆叠六层组成；解码器额外引入交叉注意力，堆叠六层。残差连接放在层归一化之前，子层输出先残差相加再做归一化。\n\n# 五、复杂度分析\n\n自注意力的时间复杂度为 $O(n^2 d)$，序列长度 $n$ 增大时平方项成为主要开销。这是长序列建模的主要瓶颈，也是后续稀疏注意力、线性注意力与状态空间模型试图解决的问题。\n\n# 六、结论\n\nTransformer 用纯粹的注意力机制取代循环结构，在翻译任务上取得更好的效果，同时具备更高的并行度，成为后续大量模型的基础结构。', AI_EMBED('pp_embed', 'Attention Is All You Need\n# Abstract\n\nThe dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.\n\n# 一、自注意力机制\n\n自注意力把序列中每个位置表示为对所有位置加权和。给定输入矩阵 $Q \\in \\mathbb{R}^{n \\times d_k}$、$K \\in \\mathbb{R}^{n \\times d_k}$、$V \\in \\mathbb{R}^{n \\times d_v}$，注意力计算为\n\n$$\\mathrm{Attention}(Q, K, V) = \\mathrm{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right) V$$\n\n缩放因子 $\\sqrt{d_k}$ 用来避免维度变大时 softmax 进入饱和区���，梯度消失。多头注意力把表示切分成多份分别做注意力再拼接，使模型能在不同子空间里关注不同关系。\n\n# 二、位置编码\n\n由于自注意力本身不含位置信息，模型必须显式注入顺序。论文采用正弦位置编码\n\n$$PE_{(pos, 2i)} = \\sin\\left(pos / 10000^{2i/d_{model}}\\right)$$\n\n它既能表示绝对位置，也便于模型推断相对位置关系，并且可以外推到比训练时更长的序列。\n\n# 三、多头注意力的并行计算\n\n多头注意力的投影矩阵可以合并成一次大矩阵乘法实现，从而充分利用矩阵乘法的并行性。实践中注意力矩阵的显存占用是主要瓶颈，因此实现时通常使用 FlashAttention 一类的核融合算子把中间结果留在片上缓存。\n\n# 四、编码器与解码器\n\n编码器由多头自注意力、前馈网络、残差连接与层归一化堆叠六层组成；解码器额外引入交叉注意力，堆叠六层。残差连接放在层归一化之前，子层输出先残差相加再做归一化。\n\n# 五、复杂度分析\n\n自注意力的时间复杂度为 $O(n^2 d)$，序列长度 $n$ 增大时平方项成为主要开销。这是长序列建模的主要瓶颈，也是后续稀疏注意力、线性注意力与状态空间模型试图解决的问题。\n\n# 六、结论\n\nTransformer 用纯粹的注意力机制取代循环结构，在翻译任务上取得更好的效果，同时具备更高的并行度，成为后续大量模型的基础结构。'))
```

### 63. 导入资料（写入段落 attention-is-all-you-need#000，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#000', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', 'Abstract', 0, 'papers/attention_is_all_you_need.md', 2, 4, 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.', AI_EMBED('pp_embed', 'Abstract\nThe dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.'))
```

### 64. 导入资料（写入段落 attention-is-all-you-need#001，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#001', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '一、自注意力机制', 1, 'papers/attention_is_all_you_need.md', 6, 12, '自注意力把序列中每个位置表示为对所有位置加权和。给定输入矩阵 $Q \\in \\mathbb{R}^{n \\times d_k}$、$K \\in \\mathbb{R}^{n \\times d_k}$、$V \\in \\mathbb{R}^{n \\times d_v}$，注意力计算为\n\n$$\\mathrm{Attention}(Q, K, V) = \\mathrm{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right) V$$\n\n缩放因子 $\\sqrt{d_k}$ 用来避免维度变大时 softmax 进入饱和区���，梯度消失。多头注意力把表示切分成多份分别做注意力再拼接，使模型能在不同子空间里关注不同关系。', AI_EMBED('pp_embed', '一、自注意力机制\n自注意力把序列中每个位置表示为对所有位置加权和。给定输入矩阵 $Q \\in \\mathbb{R}^{n \\times d_k}$、$K \\in \\mathbb{R}^{n \\times d_k}$、$V \\in \\mathbb{R}^{n \\times d_v}$，注意力计算为\n\n$$\\mathrm{Attention}(Q, K, V) = \\mathrm{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right) V$$\n\n缩放因子 $\\sqrt{d_k}$ 用来避免维度变大时 softmax 进入饱和区���，梯度消失。多头注意力把表示切分成多份分别做注意力再拼接，使模型能在不同子空间里关注不同关系。'))
```

### 65. 导入资料（写入段落 attention-is-all-you-need#002，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#002', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '二、位置编码', 2, 'papers/attention_is_all_you_need.md', 14, 20, '由于自注意力本身不含位置信息，模型必须显式注入顺序。论文采用正弦位置编码\n\n$$PE_{(pos, 2i)} = \\sin\\left(pos / 10000^{2i/d_{model}}\\right)$$\n\n它既能表示绝对位置，也便于模型推断相对位置关系，并且可以外推到比训练时更长的序列。', AI_EMBED('pp_embed', '二、位置编码\n由于自注意力本身不含位置信息，模型必须显式注入顺序。论文采用正弦位置编码\n\n$$PE_{(pos, 2i)} = \\sin\\left(pos / 10000^{2i/d_{model}}\\right)$$\n\n它既能表示绝对位置，也便于模型推断相对位置关系，并且可以外推到比训练时更长的序列。'))
```

### 66. 导入资料（写入段落 attention-is-all-you-need#003，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#003', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '三、多头注意力的并行计算', 3, 'papers/attention_is_all_you_need.md', 22, 24, '多头注意力的投影矩阵可以合并成一次大矩阵乘法实现，从而充分利用矩阵乘法的并行性。实践中注意力矩阵的显存占用是主要瓶颈，因此实现时通常使用 FlashAttention 一类的核融合算子把中间结果留在片上缓存。', AI_EMBED('pp_embed', '三、多头注意力的并行计算\n多头注意力的投影矩阵可以合并成一次大矩阵乘法实现，从而充分利用矩阵乘法的并行性。实践中注意力矩阵的显存占用是主要瓶颈，因此实现时通常使用 FlashAttention 一类的核融合算子把中间结果留在片上缓存。'))
```

### 67. 导入资料（写入段落 attention-is-all-you-need#004，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#004', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '四、编码器与解码器', 4, 'papers/attention_is_all_you_need.md', 26, 28, '编码器由多头自注意力、前馈网络、残差连接与层归一化堆叠六层组成；解码器额外引入交叉注意力，堆叠六层。残差连接放在层归一化之前，子层输出先残差相加再做归一化。', AI_EMBED('pp_embed', '四、编码器与解码器\n编码器由多头自注意力、前馈网络、残差连接与层归一化堆叠六层组成；解码器额外引入交叉注意力，堆叠六层。残差连接放在层归一化之前，子层输出先残差相加再做归一化。'))
```

### 68. 导入资料（写入段落 attention-is-all-you-need#005，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#005', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '五、复杂度分析', 5, 'papers/attention_is_all_you_need.md', 30, 32, '自注意力的时间复杂度为 $O(n^2 d)$，序列长度 $n$ 增大时平方项成为主要开销。这是长序列建模的主要瓶颈，也是后续稀疏注意力、线性注意力与状态空间模型试图解决的问题。', AI_EMBED('pp_embed', '五、复杂度分析\n自注意力的时间复杂度为 $O(n^2 d)$，序列长度 $n$ 增大时平方项成为主要开销。这是长序列建模的主要瓶颈，也是后续稀疏注意力、线性注意力与状态空间模型试图解决的问题。'))
```

### 69. 导入资料（写入段落 attention-is-all-you-need#006，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('attention-is-all-you-need#006', 'attention-is-all-you-need', 'Attention Is All You Need', 'Ashish Vaswani, Noam Shazeer', 2020, 'NeurIPS', 'transformer,attention,nlp,sequence', '六、结论', 6, 'papers/attention_is_all_you_need.md', 34, 35, 'Transformer 用纯粹的注意力机制取代循环结构，在翻译任务上取得更好的效果，同时具备更高的并行度，成为后续大量模型的基础结构。', AI_EMBED('pp_embed', '六、结论\nTransformer 用纯粹的注意力机制取代循环结构，在翻译任务上取得更好的效果，同时具备更高的并行度，成为后续大量模型的基础结构。'))
```

### 70. 导入资料（记录日志 ingest，1 行）

```sql
INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('attention-is-all-you-need', '', 'ingest', '', 0, '导入 7 个段落')
```

### 71. 导入资料（清理旧段落 bert-基于双向transformer的预训练语言模型，0 行）

```sql
DELETE FROM paper_chunks WHERE doc_key = 'bert-基于双向transformer的预训练语言模型'
```

### 72. 导入资料（清理旧论文 bert-基于双向transformer的预训练语言模型，0 行）

```sql
DELETE FROM papers WHERE doc_key = 'bert-基于双向transformer的预训练语言模型'
```

### 73. 导入资料（写入论文 bert-基于双向transformer的预训练语言模型，1 行）

```sql
INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', 'paper', 'papers/bert_pretraining.md', '- 本文提出 BERT，一种基于双向 Transformer 的预训练语言表示模型。\n- BERT 证明了大规模无监督预训练加少量标注微调可以显著提升自然语言理解性能，并直接推动了预训练语言模型在检索、问答与摘要任务上的落地。\n- 双向的掩码预训练让每个位置都能同时利用左右两侧上下文，这是 BERT 与单向语言模型最本质的区别。\n来源：# 摘要', '# 摘要\n\n本文提出 BERT，一种基于双向 Transformer 的预训练语言表示模型。BERT 先在大规模无标注语料上进行掩码语言模型预训练，再针对具体任务做微调，在多个自然语言理解基准上刷新结果。\n\n# 一、预训练任务\n\n掩码语言模型（MLM）随机选择 15% 的输入 token 进行预测，其中 80% 替换为 [MASK]，10% 随机替换，10% 保持不变。句子对任务则使用下一句预测（NSP）作为辅助目标。双向的掩码预训练让每个位置都能同时利用左右两侧上下文，这是 BERT 与单向语言模型最本质的区别。\n\n# 二、微调阶段\n\n下游任务微调时在预训练模型顶部加一个轻量任务头，所有参数一起微调。句对分类、句子分类与问答任务的实现差异很小，这体现了"预训练 + 微调"范式的通用性。\n\n# 三、输入表示\n\nBERT 的输入由词向量、片段向量与位置向量三部分相加得到。片段向量区分句 A 与句 B，位置向量区分序列中的绝对位置。\n\n# 四、模型规模与训练代价\n\nBERT Base 使用 12 层 Transformer、隐藏维度 768、12 个注意力头，总参数量约一亿；BERT Large 参数量约三亿。训练使用 AdamW 优化器与学习率预热，在多卡环境下需要混合精度训练以控制显存。\n\n# 五、局限\n\nMLM 的 [MASK] token 在预训练与微调之间存在不一致，评测时也依赖人工构造的掩码。后来 ELECTRA 等工作用判别式替换检测缓解这一问题。此外 BERT 的输入长度上限为 512 个 token，长文档处理需要滑窗或分段策略。\n\n# 六、结论\n\nBERT 证明了大规模无监督预训练加少量标注微调可以显著提升自然语言理解性能，并直接推动了预训练语言模型在检索、问答与摘要任务上的落地。', AI_EMBED('pp_embed', 'BERT：基于双向Transformer的预训练语言模型\n# 摘要\n\n本文提出 BERT，一种基于双向 Transformer 的预训练语言表示模型。BERT 先在大规模无标注语料上进行掩码语言模型预训练，再针对具体任务做微调，在多个自然语言理解基准上刷新结果。\n\n# 一、预训练任务\n\n掩码语言模型（MLM）随机选择 15% 的输入 token 进行预测，其中 80% 替换为 [MASK]，10% 随机替换，10% 保持不变。句子对任务则使用下一句预测（NSP）作为辅助目标。双向的掩码预训练让每个位置都能同时利用左右两侧上下文，这是 BERT 与单向语言模型最本质的区别。\n\n# 二、微调阶段\n\n下游任务微调时在预训练模型顶部加一个轻量任务头，所有参数一起微调。句对分类、句子分类与问答任务的实现差异很小，这体现了"预训练 + 微调"范式的通用性。\n\n# 三、输入表示\n\nBERT 的输入由词向量、片段向量与位置向量三部分相加得到。片段向量区分句 A 与句 B，位置向量区分序列中的绝对位置。\n\n# 四、模型规模与训练代价\n\nBERT Base 使用 12 层 Transformer、隐藏维度 768、12 个注意力头，总参数量约一亿；BERT Large 参数量约三亿。训练使用 AdamW 优化器与学习率预热，在多卡环境下需要混合精度训练以控制显存。\n\n# 五、局限\n\nMLM 的 [MASK] token 在预训练与微调之间存在不一致，评测时也依赖人工构造的掩码。后来 ELECTRA 等工作用判别式替换检测缓解这一问题。此外 BERT 的输入长度上限为 512 个 token，长文档处理需要滑窗或分段策略。\n\n# 六、结论\n\nBERT 证明了大规模无监督预训练加少量标注微调可以显著提升自然语言理解性能，并直接推动了预训练语言模型在检索、问答与摘要任务上的落地。'))
```

### 74. 导入资料（写入段落 bert-基于双向transformer的预训练语言模型#000，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#000', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '摘要', 0, 'papers/bert_pretraining.md', 2, 4, '本文提出 BERT，一种基于双向 Transformer 的预训练语言表示模型。BERT 先在大规模无标注语料上进行掩码语言模型预训练，再针对具体任务做微调，在多个自然语言理解基准上刷新结果。', AI_EMBED('pp_embed', '摘要\n本文提出 BERT，一种基于双向 Transformer 的预训练语言表示模型。BERT 先在大规模无标注语料上进行掩码语言模型预训练，再针对具体任务做微调，在多个自然语言理解基准上刷新结果。'))
```

### 75. 导入资料（写入段落 bert-基于双向transformer的预训练语言模型#001，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#001', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '一、预训练任务', 1, 'papers/bert_pretraining.md', 6, 8, '掩码语言模型（MLM）随机选择 15% 的输入 token 进行预测，其中 80% 替换为 [MASK]，10% 随机替换，10% 保持不变。句子对任务则使用下一句预测（NSP）作为辅助目标。双向的掩码预训练让每个位置都能同时利用左右两侧上下文，这是 BERT 与单向语言模型最本质的区别。', AI_EMBED('pp_embed', '一、预训练任务\n掩码语言模型（MLM）随机选择 15% 的输入 token 进行预测，其中 80% 替换为 [MASK]，10% 随机替换，10% 保持不变。句子对任务则使用下一句预测（NSP）作为辅助目标。双向的掩码预训练让每个位置都能同时利用左右两侧上下文，这是 BERT 与单向语言模型最本质的区别。'))
```

### 76. 导入资料（写入段落 bert-基于双向transformer的预训练语言模型#002，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#002', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '二、微调阶段', 2, 'papers/bert_pretraining.md', 10, 12, '下游任务微调时在预训练模型顶部加一个轻量任务头，所有参数一起微调。句对分类、句子分类与问答任务的实现差异很小，这体现了"预训练 + 微调"范式的通用性。', AI_EMBED('pp_embed', '二、微调阶段\n下游任务微调时在预训练模型顶部加一个轻量任务头，所有参数一起微调。句对分类、句子分类与问答任务的实现差异很小，这体现了"预训练 + 微调"范式的通用性。'))
```

### 77. 导入资料（写入段落 bert-基于双向transformer的预训练语言模型#003，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#003', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '三、输入表示', 3, 'papers/bert_pretraining.md', 14, 16, 'BERT 的输入由词向量、片段向量与位置向量三部分相加得到。片段向量区分句 A 与句 B，位置向量区分序列中的绝对位置。', AI_EMBED('pp_embed', '三、输入表示\nBERT 的输入由词向量、片段向量与位置向量三部分相加得到。片段向量区分句 A 与句 B，位置向量区分序列中的绝对位置。'))
```

### 78. 导入资料（写入段落 bert-基于双向transformer的预训练语言模型#004，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#004', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '四、模型规模与训练代价', 4, 'papers/bert_pretraining.md', 18, 20, 'BERT Base 使用 12 层 Transformer、隐藏维度 768、12 个注意力头，总参数量约一亿；BERT Large 参数量约三亿。训练使用 AdamW 优化器与学习率预热，在多卡环境下需要混合精度训练以控制显存。', AI_EMBED('pp_embed', '四、模型规模与训练代价\nBERT Base 使用 12 层 Transformer、隐藏维度 768、12 个注意力头，总参数量约一亿；BERT Large 参数量约三亿。训练使用 AdamW 优化器与学习率预热，在多卡环境下需要混合精度训练以控制显存。'))
```

### 79. 导入资料（写入段落 bert-基于双向transformer的预训练语言模型#005，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#005', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '五、局限', 5, 'papers/bert_pretraining.md', 22, 24, 'MLM 的 [MASK] token 在预训练与微调之间存在不一致，评测时也依赖人工构造的掩码。后来 ELECTRA 等工作用判别式替换检测缓解这一问题。此外 BERT 的输入长度上限为 512 个 token，长文档处理需要滑窗或分段策略。', AI_EMBED('pp_embed', '五、局限\nMLM 的 [MASK] token 在预训练与微调之间存在不一致，评测时也依赖人工构造的掩码。后来 ELECTRA 等工作用判别式替换检测缓解这一问题。此外 BERT 的输入长度上限为 512 个 token，长文档处理需要滑窗或分段策略。'))
```

### 80. 导入资料（写入段落 bert-基于双向transformer的预训练语言模型#006，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('bert-基于双向transformer的预训练语言模型#006', 'bert-基于双向transformer的预训练语言模型', 'BERT：基于双向Transformer的预训练语言模型', 'Jacob Devlin, Ming-Wei Chang', 2019, 'NAACL', 'nlp,pretraining,bert,language-model', '六、结论', 6, 'papers/bert_pretraining.md', 26, 27, 'BERT 证明了大规模无监督预训练加少量标注微调可以显著提升自然语言理解性能，并直接推动了预训练语言模型在检索、问答与摘要任务上的落地。', AI_EMBED('pp_embed', '六、结论\nBERT 证明了大规模无监督预训练加少量标注微调可以显著提升自然语言理解性能，并直接推动了预训练语言模型在检索、问答与摘要任务上的落地。'))
```

### 81. 导入资料（记录日志 ingest，1 行）

```sql
INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('bert-基于双向transformer的预训练语言模型', '', 'ingest', '', 0, '导入 7 个段落')
```

### 82. 导入资料（清理旧段落 对比表示学习在检索场景中的实践，0 行）

```sql
DELETE FROM paper_chunks WHERE doc_key = '对比表示学习在检索场景中的实践'
```

### 83. 导入资料（清理旧论文 对比表示学习在检索场景中的实践，0 行）

```sql
DELETE FROM papers WHERE doc_key = '对比表示学习在检索场景中的实践'
```

### 84. 导入资料（写入论文 对比表示学习在检索场景中的实践，1 行）

```sql
INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', 'paper', 'papers/contrastive_representation.md', '- 对比表示学习通过构造正负样本对，把语义相近的文本映射到向量空间中彼此靠近的位置。\n- 本文讨论其在文献检索场景中的落地方式，重点是如何让向量召回与关键词召回互补。\n- 对比学习让向量召回在语义层面补齐了关键词召回的短板，而混合召回加融合排序是在工程上稳健的默认方案。\n来源：# 摘要', '# 摘要\n\n对比表示学习通过构造正负样本对，把语义相近的文本映射到向量空间中彼此靠近的位置。本文讨论其在文献检索场景中的落地方式，重点是如何让向量召回与关键词召回互补。\n\n# 一、对比学习的基本形式\n\n给定锚点样本 $a$、正样本 $p$ 与负样本集合 $\\{n_i\\}$，InfoNCE 损失写作\n\n$$L = -\\log \\frac{\\exp(\\mathrm{sim}(a, p)/\\tau)}{\\exp(\\mathrm{sim}(a, p)/\\tau) + \\sum_i \\exp(\\mathrm{sim}(a, n_i)/\\tau)}$$\n\n温度系数 $\\tau$ 控制分布的尖锐程度，对效果影响很大。\n\n# 二、难负样本挖掘\n\n随机负样本过于简单，模型很快饱和。需要在候选池中挑选与锚点最相似但被标注为负的样本，也就是难负样本挖掘（hard negative mining）。在检索系统中可以直接用线上召回结果作为负样本池，让训练分布与推理分布一致。\n\n# 三、向量召回与关键词召回的互补性\n\n向量召回擅长处理同义改写与跨语言表达，关键词召回则擅长精确匹配专有名词、公式编号与罕见术语。生产系统通常把两路召回结果合并去重，再交给精排模型。\n\n# 四、向量索引的工程取舍\n\n近似最近邻索引在精度与延迟之间取舍。HNSW 适合内存充裕、查询并发高的场景；IVF 类索引在数据量大时更省内存。距离度量的选择同样重要，余弦距离适合归一化向量，L2 距离在未归一化时更稳定。\n\n# 五、评估方式\n\n除了常规的召回率与 NDCG，还要单独统计"向量召回独有问题"与"关键词召回独有问题"，据此决定是否继续投入优化某一路召回。混合排序常用倒数排名融合（RRF），它不依赖两路分数的量纲。\n\n# 六、结论\n\n对比学习让向量召回在语义层面补齐了关键词召回的短板，而混合召回加融合排序是在工程上稳健的默认方案。', AI_EMBED('pp_embed', '对比表示学习在检索场景中的实践\n# 摘要\n\n对比表示学习通过构造正负样本对，把语义相近的文本映射到向量空间中彼此靠近的位置。本文讨论其在文献检索场景中的落地方式，重点是如何让向量召回与关键词召回互补。\n\n# 一、对比学习的基本形式\n\n给定锚点样本 $a$、正样本 $p$ 与负样本集合 $\\{n_i\\}$，InfoNCE 损失写作\n\n$$L = -\\log \\frac{\\exp(\\mathrm{sim}(a, p)/\\tau)}{\\exp(\\mathrm{sim}(a, p)/\\tau) + \\sum_i \\exp(\\mathrm{sim}(a, n_i)/\\tau)}$$\n\n温度系数 $\\tau$ 控制分布的尖锐程度，对效果影响很大。\n\n# 二、难负样本挖掘\n\n随机负样本过于简单，模型很快饱和。需要在候选池中挑选与锚点最相似但被标注为负的样本，也就是难负样本挖掘（hard negative mining）。在检索系统中可以直接用线上召回结果作为负样本池，让训练分布与推理分布一致。\n\n# 三、向量召回与关键词召回的互补性\n\n向量召回擅长处理同义改写与跨语言表达，关键词召回则擅长精确匹配专有名词、公式编号与罕见术语。生产系统通常把两路召回结果合并去重，再交给精排模型。\n\n# 四、向量索引的工程取舍\n\n近似最近邻索引在精度与延迟之间取舍。HNSW 适合内存充裕、查询并发高的场景；IVF 类索引在数据量大时更省内存。距离度量的选择同样重要，余弦距离适合归一化向量，L2 距离在未归一化时更稳定。\n\n# 五、评估方式\n\n除了常规的召回率与 NDCG，还要单独统计"向量召回独有问题"与"关键词召回独有问题"，据此决定是否继续投入优化某一路召回。混合排序常用倒数排名融合（RRF），它不依赖两路分数的量纲。\n\n# 六、结论\n\n对比学习让向量召回在语义层面补齐了关键词召回的短板，而混合召回加融合排序是在工程上稳健的默认方案。'))
```

### 85. 导入资料（写入段落 对比表示学习在检索场景中的实践#000，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#000', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '摘要', 0, 'papers/contrastive_representation.md', 2, 4, '对比表示学习通过构造正负样本对，把语义相近的文本映射到向量空间中彼此靠近的位置。本文讨论其在文献检索场景中的落地方式，重点是如何让向量召回与关键词召回互补。', AI_EMBED('pp_embed', '摘要\n对比表示学习通过构造正负样本对，把语义相近的文本映射到向量空间中彼此靠近的位置。本文讨论其在文献检索场景中的落地方式，重点是如何让向量召回与关键词召回互补。'))
```

### 86. 导入资料（写入段落 对比表示学习在检索场景中的实践#001，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#001', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '一、对比学习的基本形式', 1, 'papers/contrastive_representation.md', 6, 12, '给定锚点样本 $a$、正样本 $p$ 与负样本集合 $\\{n_i\\}$，InfoNCE 损失写作\n\n$$L = -\\log \\frac{\\exp(\\mathrm{sim}(a, p)/\\tau)}{\\exp(\\mathrm{sim}(a, p)/\\tau) + \\sum_i \\exp(\\mathrm{sim}(a, n_i)/\\tau)}$$\n\n温度系数 $\\tau$ 控制分布的尖锐程度，对效果影响很大。', AI_EMBED('pp_embed', '一、对比学习的基本形式\n给定锚点样本 $a$、正样本 $p$ 与负样本集合 $\\{n_i\\}$，InfoNCE 损失写作\n\n$$L = -\\log \\frac{\\exp(\\mathrm{sim}(a, p)/\\tau)}{\\exp(\\mathrm{sim}(a, p)/\\tau) + \\sum_i \\exp(\\mathrm{sim}(a, n_i)/\\tau)}$$\n\n温度系数 $\\tau$ 控制分布的尖锐程度，对效果影响很大。'))
```

### 87. 导入资料（写入段落 对比表示学习在检索场景中的实践#002，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#002', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '二、难负样本挖掘', 2, 'papers/contrastive_representation.md', 14, 16, '随机负样本过于简单，模型很快饱和。需要在候选池中挑选与锚点最相似但被标注为负的样本，也就是难负样本挖掘（hard negative mining）。在检索系统中可以直接用线上召回结果作为负样本池，让训练分布与推理分布一致。', AI_EMBED('pp_embed', '二、难负样本挖掘\n随机负样本过于简单，模型很快饱和。需要在候选池中挑选与锚点最相似但被标注为负的样本，也就是难负样本挖掘（hard negative mining）。在检索系统中可以直接用线上召回结果作为负样本池，让训练分布与推理分布一致。'))
```

### 88. 导入资料（写入段落 对比表示学习在检索场景中的实践#003，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#003', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '三、向量召回与关键词召回的互补性', 3, 'papers/contrastive_representation.md', 18, 20, '向量召回擅长处理同义改写与跨语言表达，关键词召回则擅长精确匹配专有名词、公式编号与罕见术语。生产系统通常把两路召回结果合并去重，再交给精排模型。', AI_EMBED('pp_embed', '三、向量召回与关键词召回的互补性\n向量召回擅长处理同义改写与跨语言表达，关键词召回则擅长精确匹配专有名词、公式编号与罕见术语。生产系统通常把两路召回结果合并去重，再交给精排模型。'))
```

### 89. 导入资料（写入段落 对比表示学习在检索场景中的实践#004，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#004', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '四、向量索引的工程取舍', 4, 'papers/contrastive_representation.md', 22, 24, '近似最近邻索引在精度与延迟之间取舍。HNSW 适合内存充裕、查询并发高的场景；IVF 类索引在数据量大时更省内存。距离度量的选择同样重要，余弦距离适合归一化向量，L2 距离在未归一化时更稳定。', AI_EMBED('pp_embed', '四、向量索引的工程取舍\n近似最近邻索引在精度与延迟之间取舍。HNSW 适合内存充裕、查询并发高的场景；IVF 类索引在数据量大时更省内存。距离度量的选择同样重要，余弦距离适合归一化向量，L2 距离在未归一化时更稳定。'))
```

### 90. 导入资料（写入段落 对比表示学习在检索场景中的实践#005，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#005', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '五、评估方式', 5, 'papers/contrastive_representation.md', 26, 28, '除了常规的召回率与 NDCG，还要单独统计"向量召回独有问题"与"关键词召回独有问题"，据此决定是否继续投入优化某一路召回。混合排序常用倒数排名融合（RRF），它不依赖两路分数的量纲。', AI_EMBED('pp_embed', '五、评估方式\n除了常规的召回率与 NDCG，还要单独统计"向量召回独有问题"与"关键词召回独有问题"，据此决定是否继续投入优化某一路召回。混合排序常用倒数排名融合（RRF），它不依赖两路分数的量纲。'))
```

### 91. 导入资料（写入段落 对比表示学习在检索场景中的实践#006，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('对比表示学习在检索场景中的实践#006', '对比表示学习在检索场景中的实践', '对比表示学习在检索场景中的实践', '王沐', 2022, '推荐系统与技术实践', 'representation,contrastive,retrieval,embedding', '六、结论', 6, 'papers/contrastive_representation.md', 30, 31, '对比学习让向量召回在语义层面补齐了关键词召回的短板，而混合召回加融合排序是在工程上稳健的默认方案。', AI_EMBED('pp_embed', '六、结论\n对比学习让向量召回在语义层面补齐了关键词召回的短板，而混合召回加融合排序是在工程上稳健的默认方案。'))
```

### 92. 导入资料（记录日志 ingest，1 行）

```sql
INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('对比表示学习在检索场景中的实践', '', 'ingest', '', 0, '导入 7 个段落')
```

### 93. 导入资料（清理旧段落 图神经网络综述-从消息传递到可学习聚合，0 行）

```sql
DELETE FROM paper_chunks WHERE doc_key = '图神经网络综述-从消息传递到可学习聚合'
```

### 94. 导入资料（清理旧论文 图神经网络综述-从消息传递到可学习聚合，0 行）

```sql
DELETE FROM papers WHERE doc_key = '图神经网络综述-从消息传递到可学习聚合'
```

### 95. 导入资料（写入论文 图神经网络综述-从消息传递到可学习聚合，1 行）

```sql
INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, summary, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', 'paper', 'papers/gnn_survey.md', '- 消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。\n- 本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。\n- 可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。\n来源：# 摘要', '# 摘要\n\n图神经网络（Graph Neural Network, GNN）是一类直接在图结构上定义卷积运算的深度模型。本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。\n\n# 一、消息传递范式\n\n消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。设节点集合为 $V$，边集合为 $E$，第 $l$ 层的更新可以写成\n\n$$h_v^{(l+1)} = \\mathrm{UPDATE}^{(l)}\\left(h_v^{(l)}, \\mathrm{AGGREGATE}^{(l)}(\\{h_u^{(l)} : u \\in N(v)\\})\\right)$$\n\n其中 $N(v)$ 表示节点 $v$ 的一跳邻居集合。AGGREGATE 要求置换不变，UPDATE 要求与邻居数量无关，否则大度数节点会破坏规模一致性。\n\n# 二、邻居聚合算子\n\n常见聚合算子包括求和聚合、平均聚合、最大聚合以及基于注意力的加权聚合。求和聚合实现简单且表达能力强，在同配图上表现稳定；平均聚合对邻居数量不敏感，但会稀释信号；注意力聚合引入可学习权重，可以区分邻居的重要性，但额外增加了参数量与过拟合风险。\n\n# 三、过平滑与跳连\n\n随着层数增加，所有节点的表示会趋于一致，这就是过平滑现象。常用缓解手段包括残差连接、初始残差（initial residual）、PairNorm 归一化，以及把底层原始特征直接拼接到高层表示上。残差连接在实现上最简单，通常能带来稳定的收益。\n\n# 四、邻居采样与规模扩展\n\n全图卷积在节点规模达到百万级时显存开销无法接受。邻居采样（neighbor sampling）按层采样有限数量的邻居，把大图切成小批；GraphSAGE 的采样器按均匀分布抽取固定数量的邻居，Cluster-GCN 则按节点簇进行划分。采样引入的方差可以通过多层聚合与均值池化缓解。\n\n# 五、可学习聚合与超图\n\n可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。\n\n# 六、结论与展望\n\n消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。后续工作需要在表达能力、效率与可解释性之间继续寻找平衡。', AI_EMBED('pp_embed', '图神经网络综述：从消息传递到可学习聚合\n# 摘要\n\n图神经网络（Graph Neural Network, GNN）是一类直接在图结构上定义卷积运算的深度模型。本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。\n\n# 一、消息传递范式\n\n消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。设节点集合为 $V$，边集合为 $E$，第 $l$ 层的更新可以写成\n\n$$h_v^{(l+1)} = \\mathrm{UPDATE}^{(l)}\\left(h_v^{(l)}, \\mathrm{AGGREGATE}^{(l)}(\\{h_u^{(l)} : u \\in N(v)\\})\\right)$$\n\n其中 $N(v)$ 表示节点 $v$ 的一跳邻居集合。AGGREGATE 要求置换不变，UPDATE 要求与邻居数量无关，否则大度数节点会破坏规模一致性。\n\n# 二、邻居聚合算子\n\n常见聚合算子包括求和聚合、平均聚合、最大聚合以及基于注意力的加权聚合。求和聚合实现简单且表达能力强，在同配图上表现稳定；平均聚合对邻居数量不敏感，但会稀释信号；注意力聚合引入可学习权重，可以区分邻居的重要性，但额外增加了参数量与过拟合风险。\n\n# 三、过平滑与跳连\n\n随着层数增加，所有节点的表示会趋于一致，这就是过平滑现象。常用缓解手段包括残差连接、初始残差（initial residual）、PairNorm 归一化，以及把底层原始特征直接拼接到高层表示上。残差连接在实现上最简单，通常能带来稳定的收益。\n\n# 四、邻居采样与规模扩展\n\n全图卷积在节点规模达到百万级时显存开销无法接受。邻居采样（neighbor sampling）按层采样有限数量的邻居，把大图切成小批；GraphSAGE 的采样器按均匀分布抽取固定数量的邻居，Cluster-GCN 则按节点簇进行划分。采样引入的方差可以通过多层聚合与均值池化缓解。\n\n# 五、可学习聚合与超图\n\n可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。\n\n# 六、结论与展望\n\n消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。后续工作需要在表达能力、效率与可解释性之间继续寻找平衡。'))
```

### 96. 导入资料（写入段落 图神经网络综述-从消息传递到可学习聚合#000，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#000', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '摘要', 0, 'papers/gnn_survey.md', 2, 4, '图神经网络（Graph Neural Network, GNN）是一类直接在图结构上定义卷积运算的深度模型。本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。', AI_EMBED('pp_embed', '摘要\n图神经网络（Graph Neural Network, GNN）是一类直接在图结构上定义卷积运算的深度模型。本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。'))
```

### 97. 导入资料（写入段落 图神经网络综述-从消息传递到可学习聚合#001，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#001', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '一、消息传递范式', 1, 'papers/gnn_survey.md', 6, 12, '消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。设节点集合为 $V$，边集合为 $E$，第 $l$ 层的更新可以写成\n\n$$h_v^{(l+1)} = \\mathrm{UPDATE}^{(l)}\\left(h_v^{(l)}, \\mathrm{AGGREGATE}^{(l)}(\\{h_u^{(l)} : u \\in N(v)\\})\\right)$$\n\n其中 $N(v)$ 表示节点 $v$ 的一跳邻居集合。AGGREGATE 要求置换不变，UPDATE 要求与邻居数量无关，否则大度数节点会破坏规模一致性。', AI_EMBED('pp_embed', '一、消息传递范式\n消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。设节点集合为 $V$，边集合为 $E$，第 $l$ 层的更新可以写成\n\n$$h_v^{(l+1)} = \\mathrm{UPDATE}^{(l)}\\left(h_v^{(l)}, \\mathrm{AGGREGATE}^{(l)}(\\{h_u^{(l)} : u \\in N(v)\\})\\right)$$\n\n其中 $N(v)$ 表示节点 $v$ 的一跳邻居集合。AGGREGATE 要求置换不变，UPDATE 要求与邻居数量无关，否则大度数节点会破坏规模一致性。'))
```

### 98. 导入资料（写入段落 图神经网络综述-从消息传递到可学习聚合#002，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#002', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '二、邻居聚合算子', 2, 'papers/gnn_survey.md', 14, 16, '常见聚合算子包括求和聚合、平均聚合、最大聚合以及基于注意力的加权聚合。求和聚合实现简单且表达能力强，在同配图上表现稳定；平均聚合对邻居数量不敏感，但会稀释信号；注意力聚合引入可学习权重，可以区分邻居的重要性，但额外增加了参数量与过拟合风险。', AI_EMBED('pp_embed', '二、邻居聚合算子\n常见聚合算子包括求和聚合、平均聚合、最大聚合以及基于注意力的加权聚合。求和聚合实现简单且表达能力强，在同配图上表现稳定；平均聚合对邻居数量不敏感，但会稀释信号；注意力聚合引入可学习权重，可以区分邻居的重要性，但额外增加了参数量与过拟合风险。'))
```

### 99. 导入资料（写入段落 图神经网络综述-从消息传递到可学习聚合#003，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#003', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '三、过平滑与跳连', 3, 'papers/gnn_survey.md', 18, 20, '随着层数增加，所有节点的表示会趋于一致，这就是过平滑现象。常用缓解手段包括残差连接、初始残差（initial residual）、PairNorm 归一化，以及把底层原始特征直接拼接到高层表示上。残差连接在实现上最简单，通常能带来稳定的收益。', AI_EMBED('pp_embed', '三、过平滑与跳连\n随着层数增加，所有节点的表示会趋于一致，这就是过平滑现象。常用缓解手段包括残差连接、初始残差（initial residual）、PairNorm 归一化，以及把底层原始特征直接拼接到高层表示上。残差连接在实现上最简单，通常能带来稳定的收益。'))
```

### 100. 导入资料（写入段落 图神经网络综述-从消息传递到可学习聚合#004，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#004', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '四、邻居采样与规模扩展', 4, 'papers/gnn_survey.md', 22, 24, '全图卷积在节点规模达到百万级时显存开销无法接受。邻居采样（neighbor sampling）按层采样有限数量的邻居，把大图切成小批；GraphSAGE 的采样器按均匀分布抽取固定数量的邻居，Cluster-GCN 则按节点簇进行划分。采样引入的方差可以通过多层聚合与均值池化缓解。', AI_EMBED('pp_embed', '四、邻居采样与规模扩展\n全图卷积在节点规模达到百万级时显存开销无法接受。邻居采样（neighbor sampling）按层采样有限数量的邻居，把大图切成小批；GraphSAGE 的采样器按均匀分布抽取固定数量的邻居，Cluster-GCN 则按节点簇进行划分。采样引入的方差可以通过多层聚合与均值池化缓解。'))
```

### 101. 导入资料（写入段落 图神经网络综述-从消息传递到可学习聚合#005，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#005', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '五、可学习聚合与超图', 5, 'papers/gnn_survey.md', 26, 28, '可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。', AI_EMBED('pp_embed', '五、可学习聚合与超图\n可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。'))
```

### 102. 导入资料（写入段落 图神经网络综述-从消息传递到可学习聚合#006，1 行）

```sql
INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, emb) VALUES ('图神经网络综述-从消息传递到可学习聚合#006', '图神经网络综述-从消息传递到可学习聚合', '图神经网络综述：从消息传递到可学习聚合', '张一鸣, 李思远', 2023, '中文信息学报', 'gnn,message-passing,survey,graph', '六、结论与展望', 6, 'papers/gnn_survey.md', 30, 31, '消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。后续工作需要在表达能力、效率与可解释性之间继续寻找平衡。', AI_EMBED('pp_embed', '六、结论与展望\n消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。后续工作需要在表达能力、效率与可解释性之间继续寻找平衡。'))
```

### 103. 导入资料（记录日志 ingest，1 行）

```sql
INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('图神经网络综述-从消息传递到可学习聚合', '', 'ingest', '', 0, '导入 7 个段落')
```

### 104. 混合检索-全文通道（BM25 全文检索，19 行）

```sql
SELECT chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, MATCH(title, content) AGAINST ('图神经网络 消息传递 邻居聚合' IN NATURAL LANGUAGE MODE) AS bm25_score FROM paperpocket.paper_chunks WHERE MATCH(title, content) AGAINST ('图神经网络 消息传递 邻居聚合' IN NATURAL LANGUAGE MODE) ORDER BY bm25_score DESC LIMIT 40
```

### 105. 混合检索-向量通道（向量 ANN 检索，40 行）

```sql
SELECT chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, l2_distance(emb, '[0.000000,0.000000,0.316228,0.000000,0.316228,0.000000,-0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.316228,0.000000,0.316228,-0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,-0.316228,0.000000,0.000000,0.000000]') AS ann_distance FROM paperpocket.paper_chunks  ORDER BY l2_distance(emb, '[0.000000,0.000000,0.316228,0.000000,0.316228,0.000000,-0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.316228,0.000000,0.316228,-0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.316228,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,-0.316228,0.000000,0.000000,0.000000]') APPROXIMATE LIMIT 40
```

### 106. 混合检索-向量通道（向量 ANN 检索，40 行）

```sql
SELECT chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, source_path, start_line, end_line, content, l2_distance(emb, '[0.000000,0.000000,0.343173,0.000000,0.343173,0.000000,-0.241955,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.343173,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.343173,0.000000,0.241955,0.000000,0.343173,-0.343173,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.241955,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,-0.343173,0.000000,0.000000,0.000000]') AS ann_distance FROM paperpocket.paper_chunks  ORDER BY l2_distance(emb, '[0.000000,0.000000,0.343173,0.000000,0.343173,0.000000,-0.241955,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.343173,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.343173,0.000000,0.241955,0.000000,0.343173,-0.343173,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.241955,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000,-0.343173,0.000000,0.000000,0.000000]') APPROXIMATE LIMIT 40
```

### 107. 混合检索-向量通道（探测摘要模型是否已注册，1 行）

```sql
SELECT NAME FROM oceanbase.DBA_OB_AI_MODELS WHERE NAME = 'pp_summarizer'
```

### 108. 混合检索-向量通道（探测摘要端点是否已注册，1 行）

```sql
SELECT ENDPOINT_NAME FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS WHERE AI_MODEL_NAME = 'pp_summarizer'
```

### 109. 简报生成-AI_COMPLETE（seekdb AI_COMPLETE 生成简报，1 行）

```sql
SELECT AI_COMPLETE('pp_summarizer', '请根据下面的检索结果，用中文写一段不超过 200 字的研究简报。\n\n【检索词】\n图神经网络 消息传递 邻居聚合\n\n【资料片段】\n1. 《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:30-31\n消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。后续工作需要在表达能力、效率与可解释性之间继续寻找平衡。\n\n2. 《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:2-4\n图神经网络（Graph Neural Network, GNN）是一类直接在图结构上定义卷积运算的深度模型。本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。\n\n3. 《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:26-28\n可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。\n\n4. 《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:6-12\n消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。设节点集合为 $V$，边集合为 $E$，第 $l$ 层的更新可以写成\n\n$$h_v^{(l+1)} = \\mathrm{UPDATE}^{(l)}\\left(h_v^{(l)}, \\math\n\n5. 《课程笔记：图神经网络基础（第 6-9 周）》 notes/课程笔记-图神经网络基础.md:22-25\n1. 采样引入的方差如何在多层之间传递？\n2. 注意力聚合在度数差异大的图上是否稳定？\n3. 课程项目打算做"邻居聚合算子"的消融实验，需要固定随机种子。\n\n【要求】\n1. 只使用上面给出的资料，不要编造结论；\n2. 给出 3-5 条要点，每条一行，以「- 」开头；\n3. 末尾用一行标注主要来源文件。') AS brief
```

### 110. 保存简报（保存简报，1 行）

```sql
INSERT INTO briefs (query_text, brief_md, engine, model_name, source_keys) VALUES ('图神经网络 消息传递 邻居聚合', '- 消息传递范式仍是图神经网络的主流，但可学习聚合、超图表达与大规模采样三条路线都在快速演进。\n- 超图神经网络（Hypergraph Neural Network）是这一方向的延伸：把一条超边视为一个整体邻居，让聚合发生在超边而不是单个节点上，适用于分子图、交通网络等群体结构明显的场景。\n- 本文以消息传递（message passing）范式为主线，系统梳理节点表示学习、邻居聚合、子图采样与过平滑等关键问题，并讨论可学习聚合算子的设计思路。\n- 消息传递范式把一次图层更新拆成两步：每个节点先从邻居收集消息（message），再把消息聚合（aggregate）成新的节点表示。\n- 可学习聚合尝试用小型神经网络代替固定的 sum / mean 算子，让模型自行决定邻居的贡献方式。\n来源：《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:30-31；《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:26-28；《图神经网络综述：从消息传递到可学习聚合》 papers/gnn_survey.md:2-4', 'seekdb-ai-complete', 'pp_summarizer', '图神经网络综述-从消息传递到可学习聚合#006,图神经网络综述-从消息传递到可学习聚合#000,图神经网络综述-从消息传递到可学习聚合#005,图神经网络综述-从消息传递到可学习聚合#001,课程笔记-图神经网络基础-第-6-9-周#004')
```

### 111. 记录简报来源（记录简报来源，1 行）

```sql
INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('图神经网络综述-从消息传递到可学习聚合', '图神经网络综述-从消息传递到可学习聚合#006', 'brief', '图神经网络 消息传递 邻居聚合', 0.078054, '简报引用')
```

### 112. 记录简报来源（记录简报来源，1 行）

```sql
INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ('图神经网络综述-从消息传递到可学习聚合', '图神经网络综述-从消息传递到可学习聚合#000', 'brief', '图神经网络 消息传递 邻居聚合', 0.076210, '简报引用')
```

### 113. 未标注（切换默认数据库，0 行）

```sql
USE `paperpocket`
```

### 114. 未标注（统计 papers 行数，1 行）

```sql
SELECT COUNT(*) AS cnt FROM `paperpocket`.`papers`
```

### 115. 未标注（统计 paper_chunks 行数，1 行）

```sql
SELECT COUNT(*) AS cnt FROM `paperpocket`.`paper_chunks`
```

### 116. 未标注（统计 reading_log 行数，1 行）

```sql
SELECT COUNT(*) AS cnt FROM `paperpocket`.`reading_log`
```

### 117. 未标注（统计 briefs 行数，1 行）

```sql
SELECT COUNT(*) AS cnt FROM `paperpocket`.`briefs`
```

### 118. 未标注（查看 papers 的索引，4 行）

```sql
SHOW INDEX FROM `paperpocket`.`papers`
```

### 119. 未标注（查看 paper_chunks 的索引，6 行）

```sql
SHOW INDEX FROM `paperpocket`.`paper_chunks`
```

### 120. 未标注（服务端版本，1 行）

```sql
SELECT version() AS version
```
